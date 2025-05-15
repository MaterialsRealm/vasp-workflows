from collections import Counter

from pymatgen.core.periodic_table import Element
from pymatgen.io.vasp import Poscar

__all__ = ["get_cell", "get_volume", "count_elements"]


def get_cell(filename):
    """
    Get the cell from a VASP POSCAR file.
    """
    poscar = Poscar.from_file(filename)
    return poscar.structure


def get_volume(filename):
    """
    Get the volume of the cell from a VASP POSCAR file.
    """
    poscar = Poscar.from_file(filename)
    return poscar.structure.volume


def count_elements(filename):
    """
    Count the number of atoms for each element in a VASP POSCAR file.
    Returns a dict: {element_symbol: count, ...}
    """
    poscar = Poscar.from_file(filename)
    atomic_numbers = poscar.structure.atomic_numbers
    # Convert atomic numbers to element symbols
    symbols = [Element.from_Z(z).symbol for z in atomic_numbers]
    counts = dict(Counter(symbols))
    return counts
