from collections.abc import Mapping
from pathlib import Path

import numpy as np
from pymatgen.io.vasp import Incar, Outcar, Poscar

from .logger import LOGGER
from .poscar import AtomsExtractor, LatticeExtractor, SiteExtractor
from .spglib import SpglibCell

__all__ = [
    "cell_from_input",
    "cell_from_output",
    "cell_to_input",
    "set_ferromagnetic",
]


def cell_from_input(incar, poscar):
    """Create a cell object from INCAR and POSCAR files."""
    incar_data = Incar.from_file(incar)
    magmoms = incar_data.get("MAGMOM", None)
    lattice = LatticeExtractor.from_file(poscar).matrix
    positions = [site.frac_coords for site in SiteExtractor.from_file(poscar)]
    atoms = AtomsExtractor.from_file(poscar)
    return SpglibCell(lattice, positions, atoms, magmoms)


def cell_to_input(cell, incar, poscar):
    """Write a cell object to INCAR and POSCAR files."""
    incar, poscar = Path(incar), Path(poscar)
    if not incar.exists() or not poscar.exists():
        incar.touch(exist_ok=True)
        poscar.touch(exist_ok=True)
    incar_data = Incar.from_file(incar)
    if cell.magmoms is not None:
        incar_data["MAGMOM"] = cell.magmoms
    incar_data.write_file(incar)
    Poscar(cell.to_structure()).write_file(poscar)


def cell_from_output(outcar, poscar):
    """Create a cell object from OUTCAR and POSCAR files."""
    outcar_data = Outcar(outcar)
    magmoms = [magnetization["tot"] for magnetization in outcar_data.magnetization]
    lattice = LatticeExtractor.from_file(poscar).matrix
    positions = [site.frac_coords for site in SiteExtractor.from_file(poscar)]
    atoms = AtomsExtractor.from_file(poscar)
    return SpglibCell(lattice, positions, atoms, magmoms)


def set_ferromagnetic(cell: SpglibCell, mapping: Mapping):
    """Set the cell to a ferromagnetic state based on the provided mapping.

    Log a warning if an atom is not found in the mapping.
    """
    if cell.magmoms is None:
        cell.magmoms = np.full(len(cell.atoms), -9999)
    for i, atom in enumerate(cell.atoms):
        if atom in mapping:
            cell.magmoms[i] = mapping[atom]
        else:
            LOGGER.warning(f"Atom '{atom}' at index {i} not found in mapping; magmom left unchanged.")
    return cell
