import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        shutil.copytree(ROOT / "skills", self.root / "skills", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "scripts", self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))

    def build(self, **values):
        environment = {**os.environ, "RELEASE_VERSION": "0.1.0", "GITHUB_SHA": "a" * 40, **values}
        return subprocess.run([sys.executable, str(self.root / "scripts/build_bundle.py")], env=environment, capture_output=True, text=True)

    def test_archive_is_complete_deterministic_and_bound_to_source(self):
        self.assertEqual(self.build().returncode, 0)
        archive = self.root / "dist/xagent-id-0.1.0.zip"
        first = archive.read_bytes()
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual(first, archive.read_bytes())
        with zipfile.ZipFile(archive) as content:
            self.assertEqual(set(content.namelist()), {"xagent-id/SKILL.md", "xagent-id/scripts/xagent_read.py", "xagent-id/agents/openai.yaml", "xagent-id/references/api.md", "xagent-id/LICENSE", "xagent-id/NOTICE"})
            self.assertIn(b"MIT License", content.read("xagent-id/LICENSE"))
            self.assertIsNone(content.testzip())
        receipt = json.loads((self.root / "dist/release.json").read_text())
        self.assertEqual(receipt["source_commit"], "a" * 40)
        self.assertEqual(receipt["sha256"], hashlib.sha256(first).hexdigest())

    def test_version_mismatch_does_not_create_release(self):
        self.assertNotEqual(self.build(RELEASE_VERSION="9.9.9").returncode, 0)
        self.assertFalse((self.root / "dist").exists())

    def test_symlink_cannot_add_outside_content(self):
        source = self.root / "skills/xagent-id/scripts/xagent_read.py"
        source.unlink()
        outside = self.root / "private.txt"
        outside.write_text("not public")
        source.symlink_to(outside)
        self.assertNotEqual(self.build().returncode, 0)
