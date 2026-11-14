"""Check package metadata locally; upstream validators run separately."""

import json
import re
import struct
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/dhl_packstation_monitor"


def keys(value, prefix=""):
    if isinstance(value, dict):
        return {path for key, item in value.items() for path in keys(item, f"{prefix}/{key}")}
    return {prefix}


def check():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = manifest["version"]
    assert version == project["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:b\d+)?", version)
    assert manifest["domain"] == COMPONENT.name
    assert manifest["codeowners"] == ["@jonalbr"]
    assert manifest["config_flow"] and manifest["single_config_entry"]
    assert manifest["requirements"] == []
    for key in ("documentation", "issue_tracker"):
        assert manifest[key].startswith("https://github.com/jonalbr/ha-dhl-packstation")
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["homeassistant"] == "2026.11.1"
    assert hacs["country"] == "DE"
    english = json.loads((COMPONENT / "translations/en.json").read_text(encoding="utf-8"))
    assert english == json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    german = json.loads((COMPONENT / "translations/de.json").read_text(encoding="utf-8"))
    assert keys(english) == keys(german)
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        image = (COMPONENT / "brand" / name).read_bytes()
        assert image[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", image[16:24]) == (size, size)
    for name in (
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "uv.lock",
        "DEVELOPMENT.md",
        "RELEASING.md",
        "examples/tile.yaml",
    ):
        assert (ROOT / name).is_file(), name
    assert version in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert (COMPONENT / "quality_scale.yaml").is_file()
    print("Local package checks passed")


if __name__ == "__main__":
    check()
