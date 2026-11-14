"""Export the editable SVG master to Home Assistant's required PNG sizes."""

import argparse
from pathlib import Path

import resvg_py

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components/dhl_packstation_monitor/brand"


def build(check=False):
    master = (BRAND / "icon.svg").read_text(encoding="utf-8")
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        rendered = resvg_py.svg_to_bytes(svg_string=master, width=size, height=size)
        target = BRAND / name
        if check:
            assert target.read_bytes() == rendered, f"Regenerate {name} from icon.svg"
        else:
            target.write_bytes(rendered)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Verify PNGs match the SVG master"
    )
    build(check=parser.parse_args().check)
