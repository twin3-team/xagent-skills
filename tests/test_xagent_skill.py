import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock, patch
import urllib.error


MODULE_PATH = Path(__file__).resolve().parents[1] / "skills/xagent-id/scripts/xagent_read.py"
SPEC = importlib.util.spec_from_file_location("xagent_skill_read", MODULE_PATH)
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class XagentSkillTests(unittest.TestCase):
    def invoke(self, args, body=b'{"ok":true}', error=None):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = body
        opener = Mock()
        opener.open.return_value = response
        opener.open.side_effect = error
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(CLIENT.sys, "argv", [str(MODULE_PATH), *args]), patch.object(CLIENT.urllib.request, "build_opener", return_value=opener), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                status = CLIENT.main()
            except SystemExit as exc:
                status = exc.code
        return status, output.getvalue(), errors.getvalue(), opener

    def test_domain_card_preserves_evidence_and_uses_only_fixed_origin(self):
        evidence = {"ok": True, "agent_card": {"name": "Example"}, "company_lifecycle": {"consistency": "unknown"}, "featured_display_fallbacks": ["description"]}
        status, output, errors, opener = self.invoke(["card", "--domain", "EXAMPLE.COM"], json.dumps(evidence).encode())
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output), evidence)
        self.assertEqual(errors, "")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://xagent.id/example.com.json")
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)
        self.assertFalse(request.has_header("Authorization"))

    def test_invalid_targets_never_issue_requests(self):
        for domain in ["https://example.com", "example.com/a", "example.com?token=secret", "user@example.com", "example.com:443", "127.0.0.1", "-bad.com", "a..com", "localhost"]:
            with self.subTest(domain=domain):
                status, _, _, opener = self.invoke(["card", "--domain", domain])
                self.assertEqual(status, 2)
                opener.open.assert_not_called()
        for args in [["company", "--registration-id", "bad"], ["health", "--domain", "example.com"], ["card", "--domain", "example.com", "--registration-id", "22099131"]]:
            with self.subTest(args=args):
                status, _, _, opener = self.invoke(args)
                self.assertEqual(status, 2)
                opener.open.assert_not_called()

    def test_unready_and_missing_install_metadata_fail_closed(self):
        for value in [{}, {"release": {"ready": False}, "invocation": {}}, {"release": {"ready": True}, "invocation": {"status": "release_not_ready"}}, {"release": {"ready": True}}, {"release": {"ready": True}, "invocation": {}}]:
            with self.subTest(value=value):
                status, _, _, _ = self.invoke(["install-status"], json.dumps(value).encode())
                self.assertEqual(status, 2)

    def test_invalid_and_oversized_responses_are_not_success(self):
        for body in [b'[]', b'not-json', b'x' * 2097153]:
            with self.subTest(size=len(body)):
                status, output, errors, _ = self.invoke(["health"], body)
                self.assertEqual(status, 1)
                self.assertEqual(output, "")
                self.assertFalse(json.loads(errors)["ok"])

    def test_ready_metadata_reports_status_without_executing_it(self):
        value = {"release": {"ready": True, "version": "1.2.3"}, "invocation": {"mcp_servers": {"xagent-id": {"command": "npx", "args": ["--yes", "@twin3-ai/agent-id@1.2.3", "mcp"]}}}, "tools": [{"name": "unused"}]}
        status, output, _, opener = self.invoke(["install-status"], json.dumps(value).encode())
        self.assertEqual(status, 0)
        self.assertEqual(set(json.loads(output)), {"release", "invocation"})
        self.assertEqual(opener.open.call_count, 1)

    def test_service_failure_is_distinct_from_success(self):
        error = urllib.error.HTTPError("https://xagent.id", 503, "unavailable", {}, None)
        status, output, errors, _ = self.invoke(["company", "--registration-id", "22099131"], error=error)
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertEqual(json.loads(errors), {"ok": False, "http_status": 503})

    def test_redirects_are_not_followed(self):
        self.assertIsNone(CLIENT.NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.example"))
