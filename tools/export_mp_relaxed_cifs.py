#!/usr/bin/env python
"""Export CIFs from mp-* VASP folders, preferring CONTCAR over POSCAR."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path


def usable_file(path: Path) -> bool:
    """Return True when a structure file exists and is non-empty."""
    return path.is_file() and path.stat().st_size > 0


def choose_structure_file(folder: Path) -> Path | None:
    """Choose CONTCAR if usable, otherwise POSCAR if usable."""
    contcar = folder / "CONTCAR"
    if usable_file(contcar):
        return contcar

    poscar = folder / "POSCAR"
    if usable_file(poscar):
        return poscar

    return None


def export_mp_cifs(root: Path, output_dir: Path) -> tuple[list[Path], list[Path]]:
    """Convert selected POSCAR/CONTCAR files from mp-* folders to CIF files."""
    if not root.is_dir():
        msg = f"Run root does not exist or is not a directory: {root}"
        raise FileNotFoundError(msg)

    from vasp_wfl.poscar import poscar_to_cif

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[Path] = []

    if root.name.startswith("mp-"):
        mp_folders = [root]
    else:
        mp_folders = sorted(
            path for path in root.iterdir() if path.is_dir() and path.name.startswith("mp-")
        )
    for folder in mp_folders:
        structure_file = choose_structure_file(folder)
        if structure_file is None:
            skipped.append(folder)
            continue

        with tempfile.TemporaryDirectory(prefix="poscar_to_cif_") as tmpdir:
            converted = Path(poscar_to_cif([structure_file], output_dir=tmpdir)[0])
            target = output_dir / f"{folder.name}.cif"
            converted.replace(target)

        written.append(target)
        print(f"{target}\tfrom {structure_file}")

    return written, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate mp-<number>.cif files from mp-* folders under a VASP run root.",
    )
    parser.add_argument(
        "rootdir",
        type=Path,
        help="Root directory containing mp-* folders.",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Directory where CIF files are written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        written, skipped = export_mp_cifs(
            args.rootdir.expanduser(),
            args.output_dir.expanduser(),
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(f"converted={len(written)}")
    print(f"skipped={len(skipped)}")
    if skipped:
        print("skipped folders without non-empty CONTCAR or POSCAR:")
        for folder in skipped:
            print(folder)


if __name__ == "__main__":
    main()
