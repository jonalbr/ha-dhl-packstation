"""Block stale releases while honoring Home Assistant's dependency constraints."""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from urllib.request import Request, urlopen

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
PYPI = "https://pypi.org/pypi/{}/json"
GITHUB = "https://api.github.com/repos/"


@dataclass
class Finding:
    name: str
    current: str
    expected: str
    status: str
    note: str = ""


@cache
def read_text(url):
    headers = {"User-Agent": "ha-dhl-packstation-release-check"}
    if url.startswith(GITHUB) and (token := os.environ.get("GH_TOKEN")):
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read().decode("utf-8")


@cache
def read_json(url):
    return json.loads(read_text(url))


def exact_pin(requirement):
    pins = [spec.version for spec in requirement.specifier if spec.operator == "=="]
    if len(pins) != 1 or "*" in pins[0]:
        raise ValueError(f"Expected an exact release pin: {requirement}")
    return pins[0]


def applicable(requirement, python):
    return requirement.marker is None or requirement.marker.evaluate(
        {
            "sys_platform": "linux",
            "platform_system": "Linux",
            "os_name": "posix",
            "python_version": ".".join(python.split(".")[:2]),
            "python_full_version": python,
            "extra": "",
        }
    )


def newest_supported(data, python, constraints):
    candidates = []
    for release, files in data["releases"].items():
        try:
            version = Version(release)
        except InvalidVersion:
            continue
        if version.is_prerelease or version.is_devrelease:
            continue
        if not all(version in specifier for specifier in constraints):
            continue
        if any(
            not file.get("yanked", False)
            and Version(python) in SpecifierSet(file.get("requires_python") or "")
            for file in files
        ):
            candidates.append(version)
    if not candidates:
        raise ValueError(f"No compatible stable release of {data['info']['name']}")
    return str(max(candidates))


def check_packages(project, python, get_json=read_json, get_text=read_text):
    requirements = {}
    for group in project["dependency-groups"].values():
        for text in group:
            requirement = Requirement(text)
            name = canonicalize_name(requirement.name)
            if name in requirements and exact_pin(requirements[name]) != exact_pin(
                requirement
            ):
                raise ValueError(
                    f"Conflicting direct pins require an explicit update policy: {name}"
                )
            requirements[name] = requirement
    with ThreadPoolExecutor(max_workers=6) as pool:
        metadata = dict(
            zip(
                requirements,
                pool.map(lambda name: get_json(PYPI.format(name)), requirements),
            )
        )
    ha = metadata["homeassistant"]["info"]["version"]
    constraints = {}
    lines = get_text(
        f"https://raw.githubusercontent.com/home-assistant/core/{ha}/"
        "homeassistant/package_constraints.txt"
    ).splitlines()
    for info in (
        metadata["homeassistant"]["info"],
        metadata["pytest-homeassistant"]["info"],
    ):
        lines.extend(info.get("requires_dist") or [])
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        requirement = Requirement(line)
        if applicable(requirement, python):
            constraints.setdefault(canonicalize_name(requirement.name), []).append(
                requirement.specifier
            )
    findings = []
    if not all(Version(ha) in spec for spec in constraints.get("homeassistant", [])):
        findings.append(
            Finding(
                "HA/test-plugin alignment",
                ha,
                ha,
                "error",
                "Latest official test plugin does not match latest HA",
            )
        )
    for name, requirement in requirements.items():
        current = exact_pin(requirement)
        data = metadata[name]
        latest = data["info"]["version"]
        expected = (
            latest
            if name in {"homeassistant", "pytest-homeassistant"}
            else newest_supported(data, python, constraints.get(name, []))
        )
        status = "outdated" if Version(current) != Version(expected) else "current"
        note = ""
        if status == "current" and Version(expected) != Version(latest):
            status = "held"
            note = f"Latest {latest}; held by HA {ha}/test-plugin or Python constraints"
        findings.append(Finding(name, current, expected, status, note))
    return findings


def check_workflows(text, get_json=read_json):
    findings = []
    actions = set(re.findall(r"uses:\s*([\w.-]+/[\w./-]+)@([^\s#]+)", text))
    for action, ref in sorted(actions):
        repository = "/".join(action.split("/")[:2])
        if ref in {"main", "master"}:
            head = get_json(f"{GITHUB}{repository}/commits/{ref}")["sha"]
            findings.append(
                Finding(action, ref, head[:12], "current", "Tracks upstream branch")
            )
        else:
            latest = get_json(f"{GITHUB}{repository}/releases/latest")["tag_name"]
            findings.append(
                Finding(action, ref, latest, "current" if ref == latest else "outdated")
            )
    latest_uv = get_json(f"{GITHUB}astral-sh/uv/releases/latest")[
        "tag_name"
    ].removeprefix("v")
    for version in sorted(
        set(re.findall(r'(?m)^\s+version:\s*["\']?(\d+\.\d+\.\d+)', text))
    ):
        findings.append(
            Finding(
                "CI uv",
                version,
                latest_uv,
                "current" if version == latest_uv else "outdated",
            )
        )
    node = max(
        Version(row["version"].removeprefix("v"))
        for row in get_json("https://nodejs.org/dist/index.json")
        if row["lts"]
    )
    for pin in sorted(set(re.findall(r'node-version:\s*["\']?([\d.]+)', text))):
        matches = pin == str(node.major) or pin == str(node)
        findings.append(
            Finding("CI Node LTS", pin, str(node), "current" if matches else "outdated")
        )
    return findings


def check_python(python, get_json=read_json):
    minor = ".".join(python.split(".")[:2])
    refs = get_json(f"{GITHUB}python/cpython/git/matching-refs/tags/v{minor}.")
    releases = [
        Version(match[1])
        for row in refs
        if (match := re.fullmatch(r"refs/tags/v(\d+\.\d+\.\d+)", row["ref"]))
    ]
    latest = str(max(releases))
    return Finding(
        f"Python {minor}", python, latest, "current" if python == latest else "outdated"
    )


def check_lockfile(root, run=subprocess.run):
    """Resolve updates in a disposable copy, leaving the real lockfile untouched."""
    with tempfile.TemporaryDirectory(prefix="packstation-update-check-") as folder:
        project = Path(folder)
        for name in ("pyproject.toml", "uv.lock", ".python-version"):
            shutil.copy2(root / name, project / name)
        run(
            ["uv", "lock", "--upgrade", "--project", str(project)],
            check=True,
            capture_output=True,
            text=True,
        )
        current = (root / "uv.lock").read_bytes() == (project / "uv.lock").read_bytes()
    return Finding(
        "uv.lock",
        "committed resolution",
        "latest compatible resolution",
        "current" if current else "outdated",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-file", type=Path)
    args = parser.parse_args()
    try:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        python = (ROOT / ".python-version").read_text().strip()
        workflows = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / ".github/workflows").glob("*.yml")
        )
        findings = [
            check_lockfile(ROOT),
            *check_packages(project, python),
            *check_workflows(workflows),
            check_python(python),
        ]
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as err:
        parser.exit(2, f"Unable to verify upstream updates: {err}\n")
    for item in findings:
        print(
            f"{item.status:8} {item.name}: {item.current} -> {item.expected} {item.note}"
        )
    if args.json_file:
        args.json_file.parent.mkdir(parents=True, exist_ok=True)
        args.json_file.write_text(
            json.dumps([asdict(item) for item in findings], indent=2) + "\n"
        )
    raise SystemExit(any(item.status in {"outdated", "error"} for item in findings))


if __name__ == "__main__":
    main()
