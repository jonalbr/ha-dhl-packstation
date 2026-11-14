"""Draw original generic locker icons using only the standard library."""

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def draw(size):
    rows = []
    for y in range(size):
        row = bytearray(b"\0")
        for x in range(size):
            u, v = x / size, y / size
            color = (0, 0, 0, 0)
            if 0.12 <= u <= 0.88 and 0.08 <= v <= 0.92:
                color = (42, 54, 65, 255)
                if 0.17 <= u <= 0.83 and 0.13 <= v <= 0.87:
                    color = (231, 173, 55, 255)
                if 0.49 <= u <= 0.51 or any(abs(v - line) < 0.012 for line in (0.36, 0.61)):
                    color = (42, 54, 65, 255)
                if (0.41 < u < 0.45 or 0.74 < u < 0.78) and any(
                    abs(v - line) < 0.014 for line in (0.25, 0.48, 0.74)
                ):
                    color = (42, 54, 65, 255)
            row.extend(color)
        rows.append(row)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


def build():
    destination = ROOT / "custom_components/dhl_packstation_monitor/brand"
    destination.mkdir(exist_ok=True)
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        (destination / name).write_bytes(draw(size))


if __name__ == "__main__":
    build()
