#!/usr/bin/env python3
"""Generate POTCAR files from a POTCAR.spec and a potentials directory.

This script reads a `POTCAR.spec` file, builds an element-to-potential-name
mapping, and then generates POTCAR files in each immediate subdirectory of the
specified workdir root.

Each workdir must contain a supported structure file such as `POSCAR`,
`CONTCAR`, or a CIF file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RECOGNIZED_STRUCTURE_NAMES = ["POSCAR", "CONTCAR"]
RECOGNIZED_CIF_GLOBS = ["*.cif", "*.CIF"]


def parse_potcar_spec(spec_path: Path) -> dict[str, str]:
    """Parse `POTCAR.spec` into an element -> potential-name mapping."""
    mapping: dict[str, str] = {}
    with spec_path.open("r", encoding="utf-8") as handle:
        for lineno, raw_line in enumerate(handle, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            tokens = line.split()
            if len(tokens) == 1:
                symbol = tokens[0]
                potential_name = tokens[0]
            else:
                symbol, potential_name = tokens[:2]
            mapping[symbol] = potential_name
    return mapping


def find_structure_file(workdir: Path) -> Path | None:
    """Find the first supported structure file in a work directory."""
    for filename in RECOGNIZED_STRUCTURE_NAMES:
        candidate = workdir / filename
        if candidate.is_file():
            return candidate
    for pattern in RECOGNIZED_CIF_GLOBS:
        for candidate in workdir.glob(pattern):
            if candidate.is_file():
                return candidate
    return None


def iter_workdirs(root: Path) -> list[Path]:
    """Return immediate subdirectories of the root that contain a structure file."""
    workdirs: list[Path] = []
    if root.is_file():
        parent = root.parent
        if find_structure_file(parent) is not None:
            workdirs.append(parent)
        return workdirs

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if find_structure_file(child) is not None:
            workdirs.append(child)
    return workdirs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate POTCAR files from POTCAR.spec for many workdirs."
    )
    parser.add_argument(
        "spec",
        type=Path,
        help="Path to POTCAR.spec",
    )
    parser.add_argument(
        "potentials_dir",
        type=Path,
        help="Root potentials directory containing potential subfolders",
    )
    parser.add_argument(
        "workdir_root",
        type=Path,
        help="Root folder whose immediate subdirectories hold structure files",
    )
    parser.add_argument(
        "--output-name",
        default="POTCAR",
        help="Output filename to write in each workdir (default: POTCAR)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from vasp_wfl.potcar import PotcarGenerator

    spec_path = args.spec.expanduser().resolve()
    potentials_dir = args.potentials_dir.expanduser().resolve()
    workdir_root = args.workdir_root.expanduser().resolve()

    if not spec_path.is_file():
        raise FileNotFoundError(f"POTCAR.spec not found: {spec_path}")
    if not potentials_dir.is_dir():
        raise FileNotFoundError(f"Potentials directory not found: {potentials_dir}")
    if not workdir_root.exists():
        raise FileNotFoundError(f"Workdir root not found: {workdir_root}")

    element_pot_map = parse_potcar_spec(spec_path)
    if not element_pot_map:
        raise ValueError(f"No valid entries found in {spec_path}")

    generator = PotcarGenerator(potentials_dir, element_pot_map)
    workdirs = iter_workdirs(workdir_root)

    if not workdirs:
        print(f"No workdirs with a supported structure file were found under {workdir_root}")
        return 1

    print(f"Using POTCAR.spec: {spec_path}")
    print(f"Using potentials_dir: {potentials_dir}")
    print(f"Workdirs to process: {len(workdirs)}")
    print(f"Element mapping: {element_pot_map}")

    failures: list[tuple[Path, str]] = []

    for workdir in workdirs:
        structure_file = find_structure_file(workdir)
        if structure_file is None:
            continue
        output_path = workdir / args.output_name
        print(f"Processing {workdir} -> {output_path}")
        if args.dry_run:
            continue
        try:
            generator.from_file(structure_file, output_path=output_path)
        except Exception as exc:
            failures.append((workdir, str(exc)))
            print(f"  ERROR: {exc}")

    print(f"\nFinished. Generated POTCAR in {len(workdirs) - len(failures)} workdirs.")
    if failures:
        print(f"Failed in {len(failures)} workdirs:")
        for workdir, reason in failures:
            print(f"  {workdir}: {reason}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
