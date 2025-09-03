from pymatgen.io.vasp import Incar

from .poscar import AtomsExtractor, LatticeExtractor, SiteExtractor
from .spglib import SpglibCell

__all__ = ["cell_from_input"]


def cell_from_input(incar, poscar):
    """Create a cell object from INCAR and POSCAR files."""
    incar_data = Incar.from_file(incar)
    magmoms = incar_data.get("MAGMOM", None)
    lattice = LatticeExtractor.from_file(poscar).matrix
    positions = [site.frac_coords for site in SiteExtractor.from_file(poscar)]
    atoms = AtomsExtractor.from_file(poscar)
    return SpglibCell(lattice, positions, atoms, magmoms)
