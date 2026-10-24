from pathlib import Path
import re
import yaml


ROOT = Path(__file__).resolve().parents[1]


def main():
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    if not skills:
        raise ValueError("no skills found")
    for path in skills:
        parts = path.read_text().split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            raise ValueError("missing frontmatter")
        data = yaml.safe_load(parts[1])
        if not isinstance(data, dict) or data.get("name") != path.parent.name:
            raise ValueError("skill name does not match directory")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data["name"]) or len(data["name"]) > 64:
            raise ValueError("invalid skill name")
        description = data.get("description")
        if not isinstance(description, str) or not 1 <= len(description) <= 1024:
            raise ValueError("invalid skill description")
        if data.get("license") != "MIT":
            raise ValueError("client license must be explicit")
        metadata = data.get("metadata")
        if not isinstance(metadata, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()):
            raise ValueError("invalid metadata")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", metadata.get("version", "")):
            raise ValueError("invalid skill version")
        for relative in ("references/api.md", "agents/openai.yaml", "scripts/xagent_read.py", "LICENSE", "NOTICE"):
            if not (path.parent / relative).is_file():
                raise ValueError("missing bundled resource")
        ui = yaml.safe_load((path.parent / "agents/openai.yaml").read_text())
        if not isinstance(ui, dict) or not isinstance(ui.get("interface"), dict):
            raise ValueError("invalid client UI metadata")
        print(f"Validated {data['name']} {metadata['version']}")


if __name__ == "__main__":
    main()
