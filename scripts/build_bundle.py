import hashlib
import json
import os
from pathlib import Path
import zipfile
import yaml


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ("skills/xagent-id/SKILL.md", "xagent-id/SKILL.md"),
    ("skills/xagent-id/agents/openai.yaml", "xagent-id/agents/openai.yaml"),
    ("skills/xagent-id/references/api.md", "xagent-id/references/api.md"),
    ("skills/xagent-id/scripts/xagent_read.py", "xagent-id/scripts/xagent_read.py"),
    ("skills/xagent-id/LICENSE", "xagent-id/LICENSE"),
    ("skills/xagent-id/NOTICE", "xagent-id/NOTICE"),
)


def main():
    data = yaml.safe_load((ROOT / FILES[0][0]).read_text().split("---", 2)[1])
    version = data["metadata"]["version"]
    requested = os.environ.get("RELEASE_VERSION", version)
    if requested != version:
        raise ValueError("requested release version does not match skill metadata")
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    target = output / f"xagent-id-{version}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, destination in FILES:
            path = ROOT / source
            if path.is_symlink() or not path.is_file():
                raise ValueError("bundle source must be a regular file")
            entry = zipfile.ZipInfo(destination, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, path.read_bytes())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {target.name}\n")
    (output / "release.json").write_text(json.dumps({"skill": "xagent-id", "version": version, "source_commit": os.environ.get("GITHUB_SHA"), "archive": target.name, "sha256": digest}, indent=2) + "\n")
    print(f"Built {target.name}: {digest}")


if __name__ == "__main__":
    main()
