from dataclasses import dataclass

import numpy as np
from pymatgen.core import Structure

__all__ = ["SpglibCell"]


@dataclass
class SpglibCell:
    """A data class to store input for the spglib library, representing a crystal structure.

    Attributes:
        lattice: The lattice vectors as a 3x3 list of floats.
        positions: The fractional coordinates of atoms.
        atoms: A list of integers representing the atomic species (atomic numbers).
        magmoms: Optional magnetic moments for each atom. Can be a list of scalars
                 for collinear magnetism or a list of 3D vectors for non-collinear
                 magnetism. Defaults to `None`.
    """

    lattice: list[list[float]]
    positions: list[list[float]]
    atoms: list[int]
    magmoms: list[float] | list[list[float]] | None = None

    def __eq__(self, other):
        """Check for value equality between two `SpglibCell` objects."""
        if not isinstance(other, SpglibCell):
            return NotImplemented

        if not np.array_equal(self.lattice, other.lattice):
            return False
        if not np.array_equal(self.positions, other.positions):
            return False
        if self.atoms != other.atoms:
            return False

        # Compare magmoms, which can be None or numpy arrays
        if self.magmoms is None and other.magmoms is None:
            return True
        if self.magmoms is None or other.magmoms is None:
            return False
        return np.array_equal(self.magmoms, other.magmoms)

    @classmethod
    def from_structure(cls, structure: Structure):
        """Create a `SpglibCell` from a pymatgen `Structure` object.

        Args:
            structure: The input structure.

        Returns:
            SpglibCell: The corresponding SpglibCell object.
        """
        lattice = structure.lattice.matrix
        positions = structure.frac_coords
        atoms = [site.specie.Z for site in structure.sites]
        magmoms = None
        if structure.site_properties.get("magmom"):
            magmoms = structure.site_properties["magmom"]
            if isinstance(magmoms[0], (int, float)):
                magmoms = [float(m) for m in magmoms]
            else:
                magmoms = [list(map(float, m)) for m in magmoms]

        return cls(lattice=lattice, positions=positions, atoms=atoms, magmoms=magmoms)

    def to_structure(self) -> Structure:
        return Structure(lattice=self.lattice, species=self.atoms, coords=self.positions)
