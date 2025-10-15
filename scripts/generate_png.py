from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

Color = Tuple[int, int, int, int]


def write_png(path: Path, width: int, height: int, pixels: Sequence[Sequence[Color]]) -> None:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    for row in pixels:
        raw.append(0)  # no filter
        for r, g, b, a in row:
            raw.extend((r, g, b, a))

    png_bytes = bytearray()
    png_bytes.extend(b"\x89PNG\r\n\x1a\n")
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_bytes.extend(chunk(b"IHDR", ihdr))
    png_bytes.extend(chunk(b"IDAT", zlib.compress(bytes(raw), level=9)))
    png_bytes.extend(chunk(b"IEND", b""))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes)


def gradient_row(width: int, start: Color, end: Color) -> List[Color]:
    return [
        (
            int(start[0] + (end[0] - start[0]) * x / (width - 1)),
            int(start[1] + (end[1] - start[1]) * x / (width - 1)),
            int(start[2] + (end[2] - start[2]) * x / (width - 1)),
            int(start[3] + (end[3] - start[3]) * x / (width - 1)),
        )
        for x in range(width)
    ]


def pirate_deck(width: int = 256, height: int = 144) -> List[List[Color]]:
    pixels: List[List[Color]] = []
    horizon = int(height * 0.45)
    deck_line = int(height * 0.7)

    sky_top = (30, 80, 160, 255)
    sky_bottom = (90, 150, 210, 255)
    sea_top = (15, 60, 120, 255)
    sea_bottom = (5, 25, 80, 255)
    deck_color = (120, 85, 45, 255)

    for y in range(height):
        if y < horizon:
            pixels.append(gradient_row(width, sky_top, sky_bottom))
        elif y < deck_line:
            pixels.append(gradient_row(width, sea_top, sea_bottom))
        else:
            pixels.append([deck_color for _ in range(width)])

    # mast
    mast_x = width // 2
    for y in range(int(height * 0.45), int(height * 0.9)):
        for dx in (-2, -1, 0, 1, 2):
            if 0 <= mast_x + dx < width:
                pixels[y][mast_x + dx] = (110, 70, 40, 255)

    # sail
    sail_height = int(height * 0.18)
    sail_width = int(width * 0.25)
    top = int(height * 0.38)
    left = mast_x - sail_width // 2
    sail_color = (240, 240, 235, 255)
    for y in range(top, top + sail_height):
        blend = (y - top) / max(1, sail_height - 1)
        for x in range(left, left + sail_width):
            if 0 <= x < width:
                shade = int(240 - 40 * blend)
                pixels[y][x] = (shade, shade, shade + 10, 255)

    # deck rails
    rail_color = (80, 50, 30, 255)
    for x in range(0, width, 6):
        for y in range(deck_line, min(height, deck_line + 6)):
            pixels[y][x] = rail_color

    return pixels


def captains_cabin(width: int = 256, height: int = 144) -> List[List[Color]]:
    pixels: List[List[Color]] = []
    wall_top = (70, 40, 25, 255)
    wall_bottom = (40, 20, 12, 255)
    floor = (60, 35, 20, 255)

    floor_line = int(height * 0.65)
    for y in range(height):
        if y < floor_line:
            pixels.append(gradient_row(width, wall_top, wall_bottom))
        else:
            pixels.append([floor for _ in range(width)])

    # map table
    table_top = int(height * 0.55)
    table_left = int(width * 0.3)
    table_right = int(width * 0.7)
    table_color = (100, 65, 35, 255)
    for y in range(table_top, table_top + 4):
        for x in range(table_left, table_right):
            pixels[y][x] = table_color

    # map surface
    map_top = table_top - int(height * 0.18)
    map_left = table_left + int(width * 0.06)
    map_right = table_right - int(width * 0.06)
    map_bottom = table_top - 2
    parchment = (220, 205, 160, 255)
    for y in range(map_top, map_bottom):
        for x in range(map_left, map_right):
            tone = parchment[0] - (y - map_top) * 2
            pixels[y][x] = (tone, tone - 10, tone - 20, 255)

    # treasure X
    x_center = (map_left + map_right) // 2
    y_center = (map_top + map_bottom) // 2
    x_color = (200, 40, 40, 255)
    for delta in range(-20, 21):
        if map_top <= y_center + delta < map_bottom:
            if map_left <= x_center + delta < map_right:
                pixels[y_center + delta][x_center + delta] = x_color
            if map_left <= x_center - delta < map_right:
                pixels[y_center + delta][x_center - delta] = x_color

    # lantern glow
    lantern_center = (int(width * 0.8), int(height * 0.25))
    for y in range(height):
        for x in range(width):
            dx = x - lantern_center[0]
            dy = y - lantern_center[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 40:
                strength = (40 - dist) / 40
                existing = pixels[y][x]
                pixels[y][x] = (
                    min(255, int(existing[0] + 80 * strength)),
                    min(255, int(existing[1] + 60 * strength)),
                    min(255, int(existing[2] + 20 * strength)),
                    255,
                )

    return pixels


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    write_png(root / "images" / "pirate_deck.png", 256, 144, pirate_deck())
    write_png(root / "images" / "captains_cabin.png", 256, 144, captains_cabin())


if __name__ == "__main__":
    main()
