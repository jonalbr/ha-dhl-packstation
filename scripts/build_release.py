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
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(COMPONENT.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            info = ZipInfo(
                path.relative_to(COMPONENT).as_posix(), (2026, 1, 1, 0, 0, 0)
            )
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
