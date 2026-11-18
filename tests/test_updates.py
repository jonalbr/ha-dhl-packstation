"""Offline regressions for stale-version detection and HA compatibility holds."""

import json
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from scripts import check_updates as updates


def package(name, latest, versions=None, requires=None):
    return {
        "info": {"name": name, "version": latest, "requires_dist": requires or []},
        "releases": {version: [{}] for version in versions or [latest]},
    }


@pytest.fixture
def upstream():
    project = {
        "dependency-groups": {
            "dev": [
                "homeassistant==2026.11.2",
                "pytest-homeassistant==2026.11.2",
                "pytest==9.0.3",
                "ruff==0.17.4",
                "home-assistant-frontend==20261028.6",
            ]
        }
    }
    data = {
        "homeassistant": package("homeassistant", "2026.11.2"),
        "pytest-homeassistant": package(
            "pytest-homeassistant",
            "2026.11.2",
            requires=[
                "homeassistant==2026.11.2",
                "pytest==9.0.3",
                "pytest==1.0; extra == 'unused'",
            ],
        ),
        "pytest": package("pytest", "9.2.0", ["9.0.3", "9.2.0"]),
        "ruff": package("ruff", "0.17.5"),
        "home-assistant-frontend": package(
            "home-assistant-frontend", "20261028.7", ["20261028.6", "20261028.7"]
        ),
    }

    def get_json(url):
        return data[url.split("/")[-2]]

    return project, data, get_json


def test_latest_supported_skips_prerelease_yanked_and_unsupported_python():
    data = package("example", "2.0")
    data["releases"] = {
        "legacy": [{}],
        "1.0": [{}],
        "1.1": [{"yanked": True}],
        "1.2": [{"requires_python": ">=3.15"}],
        "2.0rc1": [{}],
        "2.0.dev1": [{}],
    }
    assert updates.newest_supported(data, "3.14.10", []) == "1.0"


def test_no_compatible_release_does_not_silently_pass():
    with pytest.raises(ValueError, match="No compatible stable release"):
        updates.newest_supported(
            package("example", "2.0"), "3.14.10", [SpecifierSet("==1.0")]
        )


def test_ha_pins_are_held_but_stale_independent_tools_are_reported(upstream):
    project, _data, get_json = upstream
    report = updates.check_packages(
        project,
        "3.14.10",
        get_json,
        lambda url: "# Matching frontend\nhome-assistant-frontend==20261028.6\n",
    )
    by_name = {item.name: item for item in report}
    assert by_name["pytest"].status == "held"
    assert by_name["pytest"].expected == "9.0.3"
    assert by_name["home-assistant-frontend"].status == "held"
    assert by_name["ruff"].status == "outdated"
    assert by_name["ruff"].expected == "0.17.5"


def test_latest_ha_and_lagging_test_plugin_cannot_pass_as_a_hold(upstream):
    project, data, get_json = upstream
    data["homeassistant"]["info"]["version"] = "2026.11.3"
    report = updates.check_packages(
        project, "3.14.10", get_json, lambda url: "home-assistant-frontend==20261028.6"
    )
    assert any(
        item.name == "HA/test-plugin alignment" and item.status == "error"
        for item in report
    )
    assert (
        next(item for item in report if item.name == "homeassistant").status
        == "outdated"
    )


def test_platform_specific_direct_dependencies_are_checked_too(upstream):
    project, _data, get_json = upstream
    project["dependency-groups"]["dev"][3] = "ruff==0.17.4; sys_platform == 'win32'"
    report = updates.check_packages(
        project, "3.14.10", get_json, lambda url: "home-assistant-frontend==20261028.6"
    )
    assert next(item for item in report if item.name == "ruff").status == "outdated"


def test_conflicting_platform_pins_need_an_explicit_policy(upstream):
    project, _data, get_json = upstream
    project["dependency-groups"]["dev"].append("ruff==0.17.3; sys_platform == 'win32'")
    with pytest.raises(ValueError, match="Conflicting direct pins"):
        updates.check_packages(project, "3.14.10", get_json, lambda url: "")


def test_pins_must_identify_an_exact_release():
    with pytest.raises(ValueError, match="exact release pin"):
        updates.exact_pin(Requirement("ruff>=0.17"))


def test_ci_actions_uv_and_node_lts_are_checked():
    text = """
      - uses: actions/checkout@v7.0.0
      - uses: hacs/action@main
      - uses: astral-sh/setup-uv@v10.3.3
        with:
          version: "0.13.8"
      - uses: actions/setup-node@v7.1.0
        with:
          node-version: "24"
    """

    def get_json(url):
        if "/commits/" in url:
            return {"sha": "abcdef0123456789"}
        if "nodejs.org" in url:
            return [
                {"version": "v27.0.0", "lts": False},
                {"version": "v26.13.1", "lts": "Lithium"},
            ]
        return {
            "tag_name": {
                "actions/checkout": "v7.0.1",
                "astral-sh/setup-uv": "v10.3.3",
                "actions/setup-node": "v7.1.0",
                "astral-sh/uv": "0.13.9",
            }[url.removeprefix(updates.GITHUB).split("/releases/")[0]]
        }

    by_name = {item.name: item for item in updates.check_workflows(text, get_json)}
    assert by_name["actions/checkout"].status == "outdated"
    assert by_name["hacs/action"].status == "current"
    assert by_name["CI uv"].status == "outdated"
    assert by_name["CI Node LTS"].expected == "26.13.1"
    assert by_name["CI Node LTS"].status == "outdated"


def test_python_patch_check_ignores_unreleased_tags():
    refs = [
        {"ref": value}
        for value in (
            "refs/tags/v3.14.9",
            "refs/tags/v3.14.10",
            "refs/tags/v3.14.11rc1",
        )
    ]
    assert updates.check_python("3.14.9", lambda url: refs).status == "outdated"
    assert updates.check_python("3.14.10", lambda url: refs).status == "current"


def setup_cli(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[dependency-groups]\n")
    (tmp_path / ".python-version").write_text("3.14.10")
    monkeypatch.setattr(updates, "ROOT", tmp_path)
    monkeypatch.setattr(
        updates,
        "check_lockfile",
        lambda *args: updates.Finding("uv.lock", "current", "current", "current"),
    )


@pytest.mark.parametrize("changed", [False, True])
def test_lockfile_updates_are_checked_without_mutating_the_repository(
    tmp_path, changed
):
    for name in ("pyproject.toml", "uv.lock", ".python-version"):
        (tmp_path / name).write_text("original")

    def resolve(command, **kwargs):
        project = Path(command[-1])
        assert project != tmp_path
        assert "--upgrade" in command
        if changed:
            (project / "uv.lock").write_text("updated")

    result = updates.check_lockfile(tmp_path, resolve)
    assert result.status == ("outdated" if changed else "current")
    assert (tmp_path / "uv.lock").read_text() == "original"


def test_unavailable_upstream_blocks_release(tmp_path, monkeypatch):
    setup_cli(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["check_updates.py"])

    def unavailable(*args):
        raise OSError("Upstream unavailable")

    monkeypatch.setattr(updates, "check_packages", unavailable)
    with pytest.raises(SystemExit) as error:
        updates.main()
    assert error.value.code == 2


def test_cli_records_findings_and_blocks_stale_release(tmp_path, monkeypatch):
    setup_cli(tmp_path, monkeypatch)
    report = tmp_path / "output" / "updates.json"
    monkeypatch.setattr(sys, "argv", ["check_updates.py", "--json-file", str(report)])
    monkeypatch.setattr(
        updates,
        "check_packages",
        lambda *args: [updates.Finding("ruff", "0.17.4", "0.17.5", "outdated")],
    )
    monkeypatch.setattr(updates, "check_workflows", lambda *args: [])
    monkeypatch.setattr(
        updates,
        "check_python",
        lambda *args: updates.Finding("Python", "3.14.10", "3.14.10", "current"),
    )
    with pytest.raises(SystemExit) as error:
        updates.main()
    assert error.value.code == 1
    assert any(item["status"] == "outdated" for item in json.loads(report.read_text()))
