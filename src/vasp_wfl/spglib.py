from pathlib import Path

import attrs
import numpy as np
from pymatgen.core import Structure
from pymatgen.io.vasp import Incar, Outcar, Poscar
from spglib import get_magnetic_symmetry_dataset, get_symmetry_dataset

from .poscar import AtomsExtractor, LatticeExtractor, SiteExtractor

__all__ = [
    "SpglibCell",
    "cell_from_input",
    "cell_from_output",
    "cell_to_input",
]


@attrs.define
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

    lattice: np.ndarray = attrs.field(converter=np.asarray)
    positions: np.ndarray = attrs.field(converter=np.asarray)
    atoms: np.ndarray = attrs.field(converter=np.asarray)
    magmoms: np.ndarray | None = attrs.field(default=None, converter=lambda x: x if x is None else np.asarray(x))
    symprec: float = attrs.field(default=1e-5)
    angle_tolerance: float = attrs.field(default=-1.0)
    hall_number: int = attrs.field(default=0, converter=int)
    mag_symprec: float = attrs.field(default=-1.0)
    is_axial: bool | None = attrs.field(default=None, converter=lambda x: x if x is None else bool(x))

    def __attrs_post_init__(self):
        if self.lattice.shape != (3, 3):
            msg = "lattice must be a 3x3 array-like structure"
            raise ValueError(msg)
        n_sites = len(self.positions)
        if len(self.atoms) != n_sites:
            msg = "atoms and positions must have the same length"
            raise ValueError(msg)
        if self.magmoms is not None and len(self.magmoms) != n_sites:
            msg = "magmoms must have the same length as positions and atoms"
            raise ValueError(msg)

    def astuple(self, use_identifiers=True):
        atoms = self.atom_identifiers if use_identifiers else self.atoms
        return (
            self.lattice.copy(),
            self.positions.copy(),
            atoms.copy(),
            self.magmoms.copy() if self.magmoms is not None else None,
        )

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
        cell = self.astuple(use_identifiers=True)
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
        mapping: dict[object, int] = {}
        identifiers: list[int] = []
        next_id = 1
        for atom in self.atoms:
            if atom not in mapping:
                mapping[atom] = next_id
                next_id += 1
            identifiers.append(mapping[atom])
        return identifiers


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
