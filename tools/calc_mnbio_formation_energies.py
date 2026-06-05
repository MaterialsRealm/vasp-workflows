"""Append Mn-Bi-O formation energies to an energies CSV.

The default paths match the current Mn-Bi-O calculation layout used by this
repository's local workflows.
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pymatgen.io.cif import CifParser

from vasp_wfl.energy import EnergyParser
from vasp_wfl.poscar import StructureParser


ELEMENTS = ("Mn", "Bi", "O")


@dataclass(frozen=True)
class ReferenceEnergy:
    element: str
    phase: str
    directory: Path
    total_energy: float
    atom_count: int
    energy_per_atom: float


def expand_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def count_cif_species(cif_path: Path) -> Counter[str]:
    if not cif_path.exists():
        raise FileNotFoundError(f"Missing CIF: {cif_path}")

    try:
        structure = CifParser(str(cif_path)).parse_structures(primitive=False)[0]
    except Exception as exc:
        raise ValueError(f"Failed to parse CIF {cif_path}: {exc}") from exc

    return Counter(str(species) for species in structure.species)


def count_poscar_species(poscar_path: Path) -> Counter[str]:
    if not poscar_path.exists():
        raise FileNotFoundError(f"Missing structure file: {poscar_path}")

    try:
        structure = StructureParser.from_poscar(poscar_path)
    except Exception as exc:
        raise ValueError(f"Failed to parse structure file {poscar_path}: {exc}") from exc

    return Counter(str(species) for species in structure.species)


def reference_from_dir(element: str, directory: Path) -> ReferenceEnergy:
    outcar = directory / "OUTCAR"
    contcar = directory / "CONTCAR"
    if not outcar.exists():
        raise FileNotFoundError(f"Missing reference OUTCAR for {element}: {outcar}")
    if not contcar.exists():
        raise FileNotFoundError(f"Missing reference CONTCAR for {element}: {contcar}")

    total_energy = EnergyParser.from_outcar(outcar)
    if total_energy is None:
        raise ValueError(f"Failed to parse reference energy for {element}: {outcar}")

    composition = count_poscar_species(contcar)
    unexpected = set(composition) - {element}
    if unexpected:
        raise ValueError(
            f"Reference {directory} for {element} contains unexpected elements: {sorted(unexpected)}",
        )

    atom_count = composition.get(element, 0)
    if atom_count == 0:
        raise ValueError(f"Reference {directory} has zero {element} atoms")

    return ReferenceEnergy(
        element=element,
        phase=directory.name,
        directory=directory,
        total_energy=total_energy,
        atom_count=atom_count,
        energy_per_atom=total_energy / atom_count,
    )


def lowest_reference(element: str, directories: list[Path]) -> ReferenceEnergy:
    if not directories:
        raise ValueError(f"No reference directories provided for {element}")

    references = [reference_from_dir(element, directory) for directory in directories]
    return min(references, key=lambda reference: reference.energy_per_atom)


def build_reference_candidates(args: argparse.Namespace) -> dict[str, list[ReferenceEnergy]]:
    mn_root = expand_path(args.mn_reference_root)
    mn_dirs = sorted(path for path in mn_root.glob("mp-*") if path.is_dir())

    candidates = {
        "Mn": mn_dirs,
        "Bi": [expand_path(args.bi_reference_dir)],
        "O": [expand_path(path) for path in args.o_reference_dirs],
    }

    return {
        element: [reference_from_dir(element, directory) for directory in directories]
        for element, directories in candidates.items()
    }


def build_lowest_references(candidates: dict[str, list[ReferenceEnergy]]) -> dict[str, ReferenceEnergy]:
    references = {}
    for element, element_candidates in candidates.items():
        if not element_candidates:
            raise ValueError(f"No reference directories provided for {element}")
        references[element] = min(element_candidates, key=lambda reference: reference.energy_per_atom)
    return references


def reference_row(
    reference: ReferenceEnergy,
    reference_energies: dict[str, float],
) -> dict[str, float | int | str]:
    atom_counts = {element: 0 for element in ELEMENTS}
    atom_counts[reference.element] = reference.atom_count

    ref_sum = sum(atom_counts[element] * reference_energies[element] for element in ELEMENTS)
    formation_energy = (reference.total_energy - ref_sum) / reference.atom_count
    if not math.isfinite(formation_energy):
        raise ValueError(f"{reference.phase} produced non-finite formation energy: {formation_energy}")

    return {
        "ID": reference.phase,
        "DFT_raw_energy": reference.total_energy,
        "n_Mn": atom_counts["Mn"],
        "n_Bi": atom_counts["Bi"],
        "n_O": atom_counts["O"],
        "num_atoms": reference.atom_count,
        "formation_energy": formation_energy,
    }


def append_formation_energies(args: argparse.Namespace) -> pd.DataFrame:
    energies_csv = expand_path(args.energies_csv)
    cif_dir = expand_path(args.cif_dir)

    if not energies_csv.exists():
        raise FileNotFoundError(f"Missing energies CSV: {energies_csv}")
    if not cif_dir.is_dir():
        raise NotADirectoryError(f"Missing CIF directory: {cif_dir}")

    df = pd.read_csv(energies_csv)

    missing_columns = {"ID", "DFT_raw_energy"} - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required CSV columns: {sorted(missing_columns)}")

    reference_candidates = build_reference_candidates(args)
    references = build_lowest_references(reference_candidates)
    reference_energies = {element: references[element].energy_per_atom for element in ELEMENTS}
    reference_ids = {
        reference.phase
        for element_candidates in reference_candidates.values()
        for reference in element_candidates
    }

    old_reference_columns = [f"{element}_ref_energy_per_atom" for element in ELEMENTS]
    df = df.drop(columns=[column for column in old_reference_columns if column in df.columns])

    compound_df = df[~df["ID"].astype(str).isin(reference_ids)].copy()
    original_compounds = compound_df[["ID", "DFT_raw_energy"]].copy()

    counts_by_element: dict[str, list[int]] = {element: [] for element in ELEMENTS}
    num_atoms: list[int] = []
    formation_energies: list[float] = []

    for row in compound_df.itertuples(index=False):
        material_id = str(getattr(row, "ID"))
        total_energy = float(getattr(row, "DFT_raw_energy"))
        cif_path = cif_dir / f"{material_id}.cif"

        composition = count_cif_species(cif_path)
        unexpected = set(composition) - set(ELEMENTS)
        if unexpected:
            raise ValueError(f"{material_id} contains unexpected elements: {sorted(unexpected)}")

        atom_counts = {element: int(composition.get(element, 0)) for element in ELEMENTS}
        total_atoms = sum(atom_counts.values())
        if total_atoms == 0:
            raise ValueError(f"{material_id} has zero counted Mn/Bi/O atoms in {cif_path}")

        ref_sum = sum(atom_counts[element] * reference_energies[element] for element in ELEMENTS)
        formation_energy = (total_energy - ref_sum) / total_atoms
        if not math.isfinite(formation_energy):
            raise ValueError(f"{material_id} produced non-finite formation energy: {formation_energy}")

        for element in ELEMENTS:
            counts_by_element[element].append(atom_counts[element])
        num_atoms.append(total_atoms)
        formation_energies.append(formation_energy)

    compound_df["n_Mn"] = counts_by_element["Mn"]
    compound_df["n_Bi"] = counts_by_element["Bi"]
    compound_df["n_O"] = counts_by_element["O"]
    compound_df["num_atoms"] = num_atoms
    compound_df["formation_energy"] = formation_energies

    reference_rows = [
        reference_row(reference, reference_energies)
        for element in ELEMENTS
        for reference in reference_candidates[element]
    ]
    reference_df = pd.DataFrame(reference_rows)
    df = pd.concat([compound_df, reference_df], ignore_index=True)

    expected_rows = len(compound_df) + len(reference_rows)
    if len(df) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows, found {len(df)}")
    if not compound_df[["ID", "DFT_raw_energy"]].equals(original_compounds):
        raise ValueError("Original ID or DFT_raw_energy columns changed unexpectedly")
    if not df["formation_energy"].apply(math.isfinite).all():
        raise ValueError("At least one formation_energy value is not finite")

    output_columns = ["ID", "DFT_raw_energy", "n_Mn", "n_Bi", "n_O", "num_atoms", "formation_energy"]
    df = df[output_columns]
    df.to_csv(energies_csv, index=False, float_format="%.17g")

    print(f"Wrote {len(df)} rows to {energies_csv}")
    print("Selected lowest elemental references:")
    for element in ELEMENTS:
        reference = references[element]
        print(
            f"  {element}: {reference.phase} "
            f"{reference.energy_per_atom:.15g} eV/atom "
            f"({reference.total_energy:.15g} eV / {reference.atom_count} atoms)",
        )
    print("Appended reference phases:")
    for element in ELEMENTS:
        for reference in reference_candidates[element]:
            print(
                f"  {reference.phase}: {element} "
                f"{reference.total_energy:.15g} eV, "
                f"{reference.atom_count} atoms, "
                f"{reference.energy_per_atom:.15g} eV/atom",
            )

    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append Mn-Bi-O formation energies to an energies CSV.",
    )
    parser.add_argument(
        "--energies-csv",
        default="~/Library/CloudStorage/CloudMounter-StampedeWork/run/MnBiO/energies.csv",
        help="CSV containing ID and DFT_raw_energy columns.",
    )
    parser.add_argument(
        "--cif-dir",
        default="~/Downloads/predict/MnBiO",
        help="Directory containing CIFs named {ID}.cif.",
    )
    parser.add_argument(
        "--bi-reference-dir",
        default="~/Library/CloudStorage/CloudMounter-StampedeWork/run/Bi+/mp-23152",
        help="Pure Bi reference calculation directory.",
    )
    parser.add_argument(
        "--mn-reference-root",
        default="~/Library/CloudStorage/CloudMounter-StampedeWork/run/Mn+",
        help="Directory containing pure Mn mp-* reference calculation directories.",
    )
    parser.add_argument(
        "--o-reference-dirs",
        nargs="+",
        default=[
            "~/Library/CloudStorage/CloudMounter-StampedeWork/run/O/mp-12957",
            "~/Library/CloudStorage/CloudMounter-StampedeWork/run/O/mp-1524462",
        ],
        help="Pure O reference calculation directories to consider.",
    )
    return parser.parse_args()


def main() -> None:
    append_formation_energies(parse_args())


if __name__ == "__main__":
    main()
