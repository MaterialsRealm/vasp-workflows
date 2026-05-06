"""Create a standalone element disk-cloud HTML file from a counts JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vasp_wfl.disk_cloud import DiskCloudParams, write_disk_cloud_html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("counts_json", type=Path)
    parser.add_argument("output_html", type=Path)
    parser.add_argument("--title", default="Element Appearance Cloud")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = json.loads(args.counts_json.read_text(encoding="utf-8"))
    write_disk_cloud_html(counts, args.output_html, DiskCloudParams(), title=args.title)


if __name__ == "__main__":
    main()
