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
        response = io.BytesIO(b"untrusted response body")
        error = urllib.error.HTTPError("https://xagent.id", 503, "unavailable", {}, response)
        status, output, errors, _ = self.invoke(["company", "--registration-id", "22099131"], error=error)
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertEqual(json.loads(errors), {"ok": False, "http_status": 503})
        self.assertTrue(response.closed)

    PRICING = {"currency": "USD", "billing_period": "monthly", "sellable_plan_ids": ["identity", "ainbox"], "plans": [{"id": "identity", "name": "Identity", "price": 29.99}, {"id": "ainbox", "name": "AInbox", "price": 49.99}, {"id": "operate", "name": "Operate", "price": 299.0}]}

    def test_checkout_link_returns_prefilled_claim_url_for_sellable_plan(self):
        status, output, errors, opener = self.invoke(["checkout-link", "--domain", "Example.COM", "--plan", "ainbox", "--source", "claude-code"], json.dumps(self.PRICING).encode())
        self.assertEqual(status, 0)
        self.assertEqual(errors, "")
        result = json.loads(output)
        self.assertEqual(result["checkout_url"], "https://xagent.id/claim?host=example.com&plan=ainbox&source=skill-claude-code")
        self.assertEqual((result["plan_name"], result["price"], result["currency"]), ("AInbox", 49.99, "USD"))
        self.assertIn("no_payment_made", result["not_done"])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://xagent.id/api/agent/pricing")
        self.assertEqual(request.get_method(), "GET")

    def test_checkout_link_defaults_unknown_source(self):
        status, output, _, _ = self.invoke(["checkout-link", "--domain", "example.com", "--plan", "identity"], json.dumps(self.PRICING).encode())
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(output)["checkout_url"].endswith("&source=skill-unknown"))

    def test_checkout_link_refuses_plan_that_is_not_sellable(self):
        for pricing in [self.PRICING, {**self.PRICING, "sellable_plan_ids": None}, {**self.PRICING, "plans": None}]:
            with self.subTest(pricing=pricing):
                status, output, errors, _ = self.invoke(["checkout-link", "--domain", "example.com", "--plan", "operate"], json.dumps(pricing).encode())
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertEqual(json.loads(errors)["error"], "plan_not_sellable")

    def test_checkout_link_invalid_arguments_never_issue_requests(self):
        for args in [["checkout-link", "--domain", "example.com"], ["checkout-link", "--plan", "identity"], ["checkout-link", "--domain", "https://example.com", "--plan", "identity"], ["checkout-link", "--domain", "example.com", "--plan", "Identity"], ["checkout-link", "--domain", "example.com", "--plan", "identity", "--source", "Bad Source"], ["pricing", "--plan", "identity"], ["card", "--domain", "example.com", "--source", "codex"]]:
            with self.subTest(args=args):
                status, _, _, opener = self.invoke(args)
                self.assertEqual(status, 2)
                opener.open.assert_not_called()

    def test_redirects_are_not_followed(self):
        self.assertIsNone(CLIENT.NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.example"))
