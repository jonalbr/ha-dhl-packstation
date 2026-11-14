"""Exercise release guards and the actual integration archive builder."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts import prepare_release as release


@pytest.fixture
def release_repo(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1]
    root = tmp_path / "repository"
    root.mkdir()
    for name in (
        "pyproject.toml",
        "hacs.json",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "uv.lock",
        "DEVELOPMENT.md",
        "RELEASING.md",
    ):
        shutil.copyfile(source / name, root / name)
    for name in ("scripts", "custom_components", "examples"):
        shutil.copytree(
            source / name, root / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    monkeypatch.setattr(release, "ROOT", root)
    version = json.loads(
        (root / "custom_components/dhl_packstation_monitor/manifest.json").read_text(
            encoding="utf-8"
        )
    )["version"]
    return root, version


def test_release_contains_matching_notes_and_component_files(release_repo):
    root, version = release_repo
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## Unreleased\n\n- Future work.\n\n"
        f"## {version} - 2026-11-15\n\n- Ready for users.\n\n"
        "## 0.0.1 - Initial implementation\n\n- Old work.\n",
        encoding="utf-8",
    )
    notes = root / "notes.md"

    asset = release.prepare_release(f"v{version}", notes)

    assert notes.read_text(encoding="utf-8") == "- Ready for users.\n"
    assert asset.name == f"dhl_packstation_monitor-{version}.zip"
    with ZipFile(asset) as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read("manifest.json"))["version"] == version
        assert "__init__.py" in archive.namelist()
        assert "brand/icon.svg" in archive.namelist()
        assert not any(
            name.startswith(("custom_components/", "tests/", "scripts/"))
            or "__pycache__" in name
            for name in archive.namelist()
        )


def test_mismatched_tag_cannot_build_release(release_repo):
    root, version = release_repo
    notes = root / "notes.md"

    with pytest.raises(ValueError, match="must match manifest version"):
        release.prepare_release(f"v{version}.1", notes)

    assert not (root / "dist").exists()
    assert not notes.exists()


def test_prerelease_tag_cannot_publish_as_stable(release_repo):
    root, version = release_repo
    manifest = root / "custom_components/dhl_packstation_monitor/manifest.json"
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    metadata["version"] = f"{version}b1"
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    notes = root / "notes.md"

    with pytest.raises(ValueError, match="must match manifest version"):
        release.prepare_release(f"v{version}b1", notes)

    assert not (root / "dist").exists()
    assert not notes.exists()


def test_cli_outputs_paths_used_by_publishing_job(release_repo, monkeypatch):
    root, version = release_repo
    (root / "CHANGELOG.md").write_text(
        f"## {version} - 2026-11-15\n\n- Ready for users.\n", encoding="utf-8"
    )
    notes = root / "release notes.md"
    output = root / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/prepare_release.py"),
            "--tag",
            f"v{version}",
            "--notes-file",
            str(notes),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    paths = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines()
    )
    asset = Path(paths["asset_path"])
    assert asset == (root / "dist" / f"dhl_packstation_monitor-{version}.zip").resolve()
    assert asset.is_file()
    assert Path(paths["notes_path"]) == notes.resolve()
    assert notes.read_text(encoding="utf-8") == "- Ready for users.\n"


@pytest.mark.parametrize("section", ["## Unreleased\n\n- Future work.\n", ""])
def test_missing_or_empty_notes_cannot_build_release(release_repo, section):
    root, version = release_repo
    changelog = section or f"## {version} - 2026-11-15\n\n"
    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    notes = root / "notes.md"

    with pytest.raises(ValueError, match="Missing dated changelog notes"):
        release.prepare_release(f"v{version}", notes)

    assert not (root / "dist").exists()
    assert not notes.exists()
