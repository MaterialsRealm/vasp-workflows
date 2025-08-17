from collections import Counter

from pymatgen.core.periodic_table import Element
from pymatgen.io.vasp import Oszicar, Poscar

__all__ = ["count_elements", "get_cell", "get_energies", "get_volume"]


def get_cell(filename):
    """Get the cell from a VASP POSCAR file."""
    poscar = Poscar.from_file(filename)
    return poscar.structure


def get_volume(filename):
    """Get the volume of the cell from a VASP POSCAR file."""
    poscar = Poscar.from_file(filename)
    return poscar.structure.volume


def count_elements(filename):
    """Count the number of atoms for each element in a VASP POSCAR file."""
    poscar = Poscar.from_file(filename)
    atomic_numbers = poscar.structure.atomic_numbers
    # Convert atomic numbers to element symbols
    symbols = [Element.from_Z(z).symbol for z in atomic_numbers]
    counts = dict(Counter(symbols))
    return counts


def get_energies(filename):
    """Extract the energies from a VASP OSZICAR file.

    Returns a tuple of (F, E0) from the last ionic step.
    F is the free energy and E0 is the energy without entropy.

    Args:
        filename: Path to the OSZICAR file

    Returns:
        tuple: (F, E0) energies or (None, None) if not available
    """
    oszicar = Oszicar(filename)
    if not oszicar.ionic_steps:
        return None, None
    last_step = oszicar.ionic_steps[-1]
    F = last_step.get("F", None)
    E0 = last_step.get("E0", None)
    return F, E0
