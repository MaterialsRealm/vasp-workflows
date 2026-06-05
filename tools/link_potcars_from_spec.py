#!/usr/bin/env python3
"""Link and concatenate POTCAR files based on POTCAR.spec in VASP working directories.

This script scans one or more root directories using `WorkdirFinder` to locate
VASP working directories. For each directory that contains a `POTCAR.spec`:
1. Links the corresponding POTCARs from the database directly in the folder as `<potential_name>.POTCAR`.
2. Concatenates them into a single `POTCAR` file in the same folder in the order of appearance.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to Python path to import vasp_wfl
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

try:
    from vasp_wfl.workdir import WorkdirFinder
except ImportError as e:
    print(f"Error: Could not import WorkdirFinder: {e}", file=sys.stderr)
    sys.exit(1)

DEFAULT_DB_DIR = Path("~/.mnt.noindex/Work/potpaw_PBE.54").expanduser()


def parse_potcar_spec(spec_path: Path) -> list[str]:
    """Parse POTCAR.spec and return list of potentials/folders."""
    potentials: list[str] = []
    with spec_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            tokens = line.split()
            if len(tokens) == 1:
                potentials.append(tokens[0])
            elif len(tokens) >= 2:
                # If there are multiple tokens, the second token is the potential name
                potentials.append(tokens[1])
    return potentials


def process_workdir(target_dir: Path, db_dir: Path) -> None:
    """Process a single VASP workdir containing POTCAR.spec."""
    spec_path = target_dir / "POTCAR.spec"
    if not spec_path.is_file():
        return

    print(f"\nProcessing {target_dir}")
    potentials = parse_potcar_spec(spec_path)
    if not potentials:
        print(f"  Warning: POTCAR.spec is empty in {target_dir}")
        return

    concatenated_contents = []
    for pot in potentials:
        source_pot_dir = db_dir / pot
        source_potcar = source_pot_dir / "POTCAR"

        if not source_pot_dir.is_dir():
            print(f"  Error: Potential directory {source_pot_dir} does not exist.")
            continue
        if not source_potcar.is_file():
            print(f"  Error: POTCAR not found in {source_pot_dir}.")
            continue

        dest_potcar = target_dir / f"{pot}.POTCAR"
        if dest_potcar.exists() or dest_potcar.is_symlink():
            print(f"  [Exists] {dest_potcar.name}")
        else:
            try:
                dest_potcar.symlink_to(source_potcar)
                print(f"  [Linked] {dest_potcar.name} -> {source_potcar}")
            except Exception as e:
                print(f"  [Failed Link] {dest_potcar.name}: {e}")
                continue

        try:
            concatenated_contents.append(source_potcar.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [Failed Read] {source_potcar}: {e}")

    if concatenated_contents:
        output_potcar = target_dir / "POTCAR"
        try:
            output_potcar.write_text("".join(concatenated_contents), encoding="utf-8")
            print(f"  [Concatenated] -> {output_potcar.name}")
        except Exception as e:
            print(f"  [Failed Write] {output_potcar.name}: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan paths for VASP directories and link/concatenate POTCARs using POTCAR.spec"
    )
    parser.add_argument(
        "roots",
        type=Path,
        nargs="+",
        help="One or more root paths to search for VASP workdirs.",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=DEFAULT_DB_DIR,
        help=f"Path to potentials database directory (default: {DEFAULT_DB_DIR})",
    )
    args = parser.parse_args()

    db_dir = args.db_dir.expanduser().resolve()
    if not db_dir.is_dir():
        print(f"Error: Potentials database directory not found: {db_dir}", file=sys.stderr)
        return 1

    finder = WorkdirFinder()
    processed_count = 0

    for root_path in args.roots:
        root_path = root_path.expanduser().resolve()
        if not root_path.exists():
            print(f"\nRoot path does not exist: {root_path}")
            continue

        print(f"\nScanning root: {root_path}")
        try:
            workdirs = finder.find(root_path)
            print(f"Found {len(workdirs)} VASP workdir(s).")
            for wd in workdirs:
                if (wd.path / "POTCAR.spec").is_file():
                    process_workdir(wd.path, db_dir)
                    processed_count += 1
        except Exception as e:
            print(f"Error scanning {root_path}: {e}", file=sys.stderr)

    print(f"\nFinished. Processed {processed_count} workdir(s) containing POTCAR.spec.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
