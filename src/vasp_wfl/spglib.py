import numpy as np
from pymatgen.core import Structure

__all__ = ["SpglibCell"]


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

    def __init__(self, lattice, positions, atoms, magmoms=None):
        """Initialize a SpglibCell and validate input shapes and lengths.

        Args:
            lattice: The lattice vectors as a 3x3 list of floats.
            positions: The fractional coordinates of atoms.
            atoms: A list of integers representing the atomic species (atomic numbers).
            magmoms: Optional magnetic moments for each atom.

        Raises:
            ValueError: If input shapes or lengths are inconsistent.
        """
        if np.shape(lattice) != (3, 3):
            msg = "lattice must be a 3x3 array-like structure"
            raise ValueError(msg)
        n_sites = len(positions)
        if len(atoms) != n_sites:
            msg = "atoms and positions must have the same length"
            raise ValueError(msg)
        if magmoms is not None and len(magmoms) != n_sites:
            msg = "magmoms must have the same length as positions and atoms"
            raise ValueError(msg)
        self.lattice = lattice
        self.positions = positions
        self.atoms = atoms
        self.magmoms = magmoms

    def __eq__(self, other):
        """Check for value equality between two `SpglibCell` objects."""
        if not isinstance(other, SpglibCell):
            return NotImplemented
        checks = [
            np.array_equal(self.lattice, other.lattice),
            np.array_equal(self.positions, other.positions),
            np.array_equal(self.atoms, other.atoms),
        ]
        if not all(checks):
            return False
        if self.magmoms is None and other.magmoms is None:
            return True
        if self.magmoms is None or other.magmoms is None:
            return False
        return np.array_equal(self.magmoms, other.magmoms)

    def __hash__(self):
        """Return a hash value for the `SpglibCell` instance.

        Converts lists and NumPy arrays to tuples for hashing. Handles `magmoms` robustly.
        """
        lattice_tuple = tuple(tuple(row) for row in np.asarray(self.lattice))
        positions_tuple = tuple(tuple(row) for row in np.asarray(self.positions))
        atoms_tuple = tuple(self.atoms)
        if self.magmoms is None:
            magmoms_tuple = None
        else:
            magmoms_arr = np.asarray(self.magmoms)
            if magmoms_arr.ndim == 1:
                magmoms_tuple = tuple(float(x) for x in magmoms_arr)
            else:
                magmoms_tuple = tuple(tuple(float(x) for x in row) for row in magmoms_arr)
        return hash((lattice_tuple, positions_tuple, atoms_tuple, magmoms_tuple))

    @classmethod
    def from_structure(cls, structure: Structure):
        """Create a `SpglibCell` from a pymatgen `Structure` object.

        Args:
            structure: The input structure.

        Returns:
            SpglibCell: The corresponding cell object.
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
        """Return a pymatgen `Structure` from this cell.

        Converts atomic numbers to element symbols for species.
        """
        return Structure(lattice=self.lattice, species=self.atoms, coords=self.positions)
