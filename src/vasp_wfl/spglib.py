import numpy as np
from pymatgen.core import Structure
from spglib import get_magnetic_symmetry_dataset, get_symmetry_dataset

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

    def __init__(
        self,
        lattice,
        positions,
        atoms,
        magmoms=None,
        *,
        symprec=1e-5,
        angle_tolerance=-1.0,
        hall_number=0,
        mag_symprec=-1.0,
        is_axial=None,
    ):
        """Initialize a SpglibCell and validate input shapes and lengths.

        Args:
            lattice: The lattice vectors as a 3x3 list of floats.
            positions: The fractional coordinates of atoms.
            atoms: A list of integers representing the atomic species (atomic numbers).
            magmoms: Optional magnetic moments for each atom.
            symprec: Symmetry search tolerance in the unit of length.
            angle_tolerance: Symmetry search tolerance in the unit of angle degree.
            hall_number: The Hall symbol is given by the serial number in between 1 and 530.
            mag_symprec: Tolerance for magnetic symmetry search in the unit of magnetic moments.
            is_axial: Whether moments are axial (for magnetic symmetry).

        Raises:
            ValueError: If input shapes or lengths are inconsistent.
        """
        lattice = np.asarray(lattice)
        positions = np.asarray(positions)
        atoms = np.asarray(atoms)
        magmoms = None if magmoms is None else np.asarray(magmoms)
        if lattice.shape != (3, 3):
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
        self._symprec = symprec
        self._angle_tolerance = angle_tolerance
        self._hall_number = int(hall_number)
        self._mag_symprec = mag_symprec
        self._is_axial = None if is_axial is None else bool(is_axial)

    @property
    def symprec(self):
        """The symmetry finding tolerance."""
        return self._symprec

    @symprec.setter
    def symprec(self, value):
        self._symprec = value

    @property
    def angle_tolerance(self):
        """The angle tolerance for symmetry finding."""
        return self._angle_tolerance

    @angle_tolerance.setter
    def angle_tolerance(self, value):
        self._angle_tolerance = value

    @property
    def hall_number(self):
        """The Hall number for symmetry dataset."""
        return self._hall_number

    @hall_number.setter
    def hall_number(self, value):
        self._hall_number = int(value)

    @property
    def mag_symprec(self):
        """The magnetic symmetry tolerance."""
        return self._mag_symprec

    @mag_symprec.setter
    def mag_symprec(self, value):
        self._mag_symprec = value

    @property
    def is_axial(self):
        """Whether moments are axial (for magnetic symmetry)."""
        return self._is_axial

    @is_axial.setter
    def is_axial(self, value):
        self._is_axial = None if value is None else bool(value)

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

    def __repr__(self):
        """Return a reconstructable, multi-line string representation of the instance."""
        lattice_str = np.array2string(
            np.asarray(self.lattice),
            separator=", ",
            prefix="    ",
            max_line_width=120,
        )
        positions_str = np.array2string(
            np.asarray(self.positions),
            separator=", ",
            prefix="    ",
            max_line_width=120,
        )
        atoms_str = np.array2string(
            np.asarray(self.atoms),
            separator=", ",
            prefix="    ",
            max_line_width=120,
        )
        magmoms_str = (
            np.array2string(
                np.asarray(self.magmoms),
                separator=", ",
                prefix="    ",
                max_line_width=120,
            )
            if self.magmoms is not None
            else "None"
        )
        return (
            f"SpglibCell(\n"
            f"    lattice={lattice_str},\n"
            f"    positions={positions_str},\n"
            f"    atoms={atoms_str},\n"
            f"    magmoms={magmoms_str}\n"
            f")"
        )

    def __str__(self):
        """Return a readable, pretty-printed summary of the cell."""
        magmoms_str = (
            np.array2string(np.asarray(self.magmoms), separator=", ", prefix="    ")
            if self.magmoms is not None
            else "None"
        )
        summary = [
            "SpglibCell:",
            "  Lattice:",
            np.array2string(np.asarray(self.lattice), separator=", ", prefix="    "),
            "  Positions:",
            np.array2string(np.asarray(self.positions), separator=", ", prefix="    "),
            "  Atoms:",
            np.array2string(np.asarray(self.atoms), separator=", ", prefix="    "),
            "  Magmoms:",
            magmoms_str,
        ]
        return "\n".join(summary)

    @property
    def symmetry(self):
        """The symmetry dataset for the cell using spglib."""
        cell = (
            self.lattice,
            self.positions,
            self.atom_identifiers,
            self.magmoms,
        )
        if self.magmoms is None:
            return get_symmetry_dataset(
                cell,
                symprec=self.symprec,
                angle_tolerance=self.angle_tolerance,
                hall_number=self.hall_number,
            )
        # else:
        is_axial = self.is_axial
        if is_axial is None:  # Determine is_axial if not set
            num_atoms = len(self.atoms)
            if self.magmoms.shape == (num_atoms,):
                is_axial = False
            elif self.magmoms.shape == (num_atoms, 3):
                is_axial = True
            else:
                msg = "Cannot determine is_axial: magmoms shape is invalid."
                raise ValueError(msg)
        return get_magnetic_symmetry_dataset(
            cell,
            is_axial=is_axial,
            symprec=self.symprec,
            angle_tolerance=self.angle_tolerance,
            mag_symprec=self.mag_symprec,
        )

    @property
    def atom_identifiers(self):
        """Return a list of integer identifiers for each atom type in order of appearance.

        The first unique atomic number is assigned 1, the second unique 2, etc.
        Atoms of the same type receive the same identifier as their first occurrence.
        """
        mapping = {}
        identifiers = []
        next_id = 1
        for atom in self.atoms:
            print(atom)
            if atom not in mapping:
                mapping[atom] = next_id
                next_id += 1
            identifiers.append(mapping[atom])
        return identifiers
