"""Verify the delivered manual package, not only its builder's return value."""

import importlib.util
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def test_package_is_complete_and_deterministic(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "package_builder", ROOT / "scripts/build_release.py"
    )
    builder = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = builder
    spec.loader.exec_module(builder)
    package = builder.build()
    first = package.read_bytes()
    assert builder.build().read_bytes() == first
    with ZipFile(package) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert "translations/de.json" in names
        assert "brand/icon.png" in names
        assert "brand/icon@2x.png" in names
        assert "brand/icon.svg" in names
        assert all(not name.startswith(("custom_components/", "tests/", ".")) for name in names)
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
