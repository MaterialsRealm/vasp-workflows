"""Create a word-cloud-style PNG from element appearance counts."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("counts_json", type=Path)
    parser.add_argument("output_png", type=Path)
    parser.add_argument("--width", type=int, default=2200)
    parser.add_argument("--height", type=int, default=1400)
    parser.add_argument("--max-words", type=int, default=89)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/SFCompact.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def intersects(box: tuple[int, int, int, int], boxes: list[tuple[int, int, int, int]]) -> bool:
    left, top, right, bottom = box
    return any(
        left < other_right
        and right > other_left
        and top < other_bottom
        and bottom > other_top
        for other_left, other_top, other_right, other_bottom in boxes
    )


def candidate_positions(
    center_x: int, center_y: int, width: int, height: int
) -> list[tuple[int, int]]:
    positions = [(center_x, center_y)]
    for radius in range(5, max(width, height), 8):
        for angle in range(0, 360, 11):
            radians = math.radians(angle)
            positions.append(
                (
                    int(center_x + radius * math.cos(radians)),
                    int(center_y + radius * math.sin(radians)),
                )
            )
    return positions


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    counts = json.loads(args.counts_json.read_text(encoding="utf-8"))
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)[: args.max_words]
    max_count = ranked[0][1]
    min_count = ranked[-1][1]

    image = Image.new("RGB", (args.width, args.height), "#f7f7f3")
    draw = ImageDraw.Draw(image)
    palette = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#386cb0"]
    boxes: list[tuple[int, int, int, int]] = []
    center_x = args.width // 2
    center_y = args.height // 2

    for index, (element, count) in enumerate(ranked):
        scaled = (math.log(count) - math.log(min_count)) / (math.log(max_count) - math.log(min_count))
        font_size = int(18 + scaled * 125)
        font = load_font(font_size)
        label = element
        text_box = draw.textbbox((0, 0), label, font=font)
        text_width = text_box[2] - text_box[0]
        text_height = text_box[3] - text_box[1]
        margin = 5
        placed = False

        positions = candidate_positions(center_x, center_y, args.width, args.height)
        random.shuffle(positions)
        positions.sort(key=lambda p: (p[0] - center_x) ** 2 + (p[1] - center_y) ** 2)

        for x, y in positions:
            left = x - text_width // 2 - margin
            top = y - text_height // 2 - margin
            right = left + text_width + margin * 2
            bottom = top + text_height + margin * 2
            if left < 20 or top < 20 or right > args.width - 20 or bottom > args.height - 20:
                continue
            box = (left, top, right, bottom)
            if intersects(box, boxes):
                continue
            color = palette[index % len(palette)]
            draw.text((left + margin, top + margin), label, fill=color, font=font)
            boxes.append(box)
            placed = True
            break

        if not placed:
            print(f"Skipped {element}: no open space")

    args.output_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output_png)


if __name__ == "__main__":
    main()
