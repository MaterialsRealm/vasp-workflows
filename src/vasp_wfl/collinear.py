from pathlib import Path

from pymatgen.io.vasp import Incar, Poscar

from .poscar import AtomsExtractor, LatticeExtractor, SiteExtractor
from .spglib import SpglibCell

__all__ = ["cell_from_input", "cell_to_input"]


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
