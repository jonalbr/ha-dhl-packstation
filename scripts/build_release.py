"""Build a deterministic manual-install ZIP; never publish it."""

import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from check_release import COMPONENT, ROOT, check


def build():
    check()
    version = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))[
        "version"
    ]
    target = ROOT / "dist" / f"dhl_packstation_monitor-{version}.zip"
    target.parent.mkdir(exist_ok=True)
    files = {
        path.relative_to(COMPONENT).as_posix(): path
        for path in COMPONENT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    files["LICENSE"] = ROOT / "LICENSE"
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        assert "manifest.json" in archive.namelist()
    print(target)
    return target


if __name__ == "__main__":
    build()
