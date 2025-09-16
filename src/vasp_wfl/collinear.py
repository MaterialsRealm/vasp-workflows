from collections import Counter, OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from itertools import combinations
from math import comb
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from pymatgen.io.vasp import Incar, Outcar, Poscar

if TYPE_CHECKING:
    from spglib import SpglibMagneticDataset

from .logger import LOGGER
from .poscar import AtomsExtractor, LatticeExtractor, SiteExtractor
from .spglib import SpglibCell
from .workdir import WorkdirFinder

__all__ = [
    "AntiferromagneticSetter",
    "FerromagneticSetter",
    "SpinFlipper",
    "cell_from_input",
    "cell_from_output",
    "cell_to_input",
    "filter_unique_magspg",
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


class FerromagneticSetter:
    """Batch processor for VASP collinear work directories."""

    @staticmethod
    def from_dirs(dirs, mapping: Mapping):
        """Process a list of directories to set cells ferromagnetic and update INCAR/POSCAR files.

        For each directory, read `INCAR` and `POSCAR`, set the cell to ferromagnetic
        using the provided mapping, and write the updated files back.

        Args:
            dirs: List of directory paths containing `INCAR` and `POSCAR` files.
            mapping: Mapping from atom name to magnetic moment value.
        """
        for d in dirs:
            incar = Path(d) / "INCAR"
            poscar = Path(d) / "POSCAR"
            cell = cell_from_input(incar, poscar)
            set_ferromagnetic(cell, mapping)
            cell_to_input(cell, incar, poscar)

    @staticmethod
    def from_rootdir(root_dir, mapping: Mapping, **kwargs):
        """Find all VASP workdirs under root_dir and process them with the given mapping.

        Args:
            root_dir: Root directory to search for VASP workdirs.
            mapping: Mapping from atom name to magnetic moment value.
            **kwargs: Additional keyword arguments for `WorkdirFinder.find`.
        """
        dirs = list(WorkdirFinder(**kwargs).find(root_dir))
        FerromagneticSetter.from_dirs(dirs, mapping)


class SpinFlipper:
    """Compose sign patterns of 'ups' (+a) and 'downs' (-a) for multiple segments.

    Each segment is defined by a key in `system`, with value `(length, a)`:
        - `length`: Even integer ≥ 0, the number of sites in the segment.
        - `a`: Any positive value, the magnitude of each site's value.

    Attributes:
        system: OrderedDict mapping keys to (length, a) tuples.
    """

    def __init__(self, system: OrderedDict | None = None) -> None:
        if system is None:
            self._system: OrderedDict[str, tuple[int, int]] = OrderedDict()
        else:
            system = OrderedDict(system)
            self._validate(system)
            self._system = system

    @property
    def system(self):
        return self._system

    @system.setter
    def system(self, system: Mapping):
        system = OrderedDict(system)
        self._validate(system)
        self._system = system

    @staticmethod
    def _validate(od: OrderedDict):
        for k, v in od.items():
            if not (isinstance(v, tuple) and len(v) == 2):
                msg = f"system[{k!r}] must be a (length, a) tuple"
                raise TypeError(msg)
            length, a = v
            if not isinstance(length, int):
                msg = f"system[{k!r}]: length must be int"
                raise TypeError(msg)
            if length < 0:
                msg = f"system[{k!r}]: length must be nonnegative"
                raise ValueError(msg)
            if length % 2:
                msg = f"system[{k!r}]: length must be even"
                raise ValueError(msg)
            if not (isinstance(a, (int, float, np.floating, np.integer)) and a > 0):
                msg = f"system[{k!r}]: a must be a positive value"
                raise ValueError(msg)

    @staticmethod
    def count_segment(length: int):
        """Return the number of balanced ups/downs for a segment of given length.

        Args:
            length: Even integer ≥ 0.

        Returns:
            The number of ways to assign half 'ups' and half 'downs'.
        """
        return 0 if length % 2 else comb(length, length // 2)

    @property
    def count(self):
        """Return the total number of combinations for the current system.

        The result is the product over all segments of C(length, length // 2).
        """
        total = 1
        for length, _ in self.system.values():
            total *= self.count_segment(length)
        return total

    def flip_segment(self, base: Sequence, downs: Sequence[int]):
        """Return a copy of `base` with values at `downs` indices flipped in sign.

        Args:
            base: Sequence of values (all 'ups').
            downs: Indices to flip to 'downs' (-a).

        Returns:
            A numpy array with specified indices negated.
        """
        out = np.asarray(base).copy()
        if downs:
            out[np.fromiter(downs, dtype=int)] *= -1
        return out

    def iter_segment(self, length: int, a=1):
        """Yield all balanced sign vectors for a segment.

        Each vector has exactly half entries as 'downs' (-a), the rest as 'ups' (+a).

        Args:
            length: Even integer ≥ 0.
            a: Any positive value, the magnitude for each entry.

        Yields:
            Numpy arrays of shape (length,) with balanced +a/-a entries.

        Raises:
            ValueError: If length is not even/nonnegative or a ≤ 0.
        """
        if length < 0 or length % 2 or not (isinstance(a, (int, float, np.floating, np.integer)) and a > 0):
            raise ValueError("length must be even/nonnegative and a > 0")
        n = length // 2
        base = np.full(length, a)  # all 'ups'
        for downs in combinations(range(length), n):
            yield self.flip_segment(base, downs)

    def iter_all(self):
        """Yield all concatenated sign vectors across all segments in system order.

        Each yielded array is the concatenation of one balanced vector per segment.

        Yields:
            Numpy arrays of shape (sum of all lengths,) with balanced +a/-a entries.
        """
        items = list(self.system.items())  # already validated in __init__/setter
        if not items:
            return

        # Backtracking to avoid materializing huge Cartesian products.
        def _dfs_join(i: int, parts: list[np.ndarray]):
            if i == len(items):
                yield np.concatenate(parts, dtype=int)
                return
            _, (length, a) = items[i]
            base = np.full(length, a, dtype=int)
            n = length // 2
            for downs in combinations(range(length), n):
                parts.append(self.flip_segment(base, downs))
                yield from _dfs_join(i + 1, parts)
                parts.pop()

        yield from _dfs_join(0, [])


class AntiferromagneticSetter:
    """Generate all possible antiferromagnetic magmom assignments for a SpglibCell.

    If `cell.magmoms` is None, use a SpinFlipper system to enumerate all balanced
    +a/-a assignments for each atom type (with even counts). Otherwise, return self.
    """

    def __init__(self, cell):
        self.cell = cell
        self._validate_even_counts()

    def _validate_even_counts(self):
        """Ensure all atom counts are even."""
        counts = Counter(self.cell.atoms)
        for atom, count in counts.items():
            if count % 2 != 0:
                msg = f"Atom '{atom}' count {count} is not even for antiferromagnetic assignment"
                raise ValueError(msg)

    def preprocess(self, spins, counter: Counter):
        """Return an OrderedDict mapping atom type to (count, spin) tuples.

        Args:
            spins: Sequence of positive spins, one per atom type, in order of counter.
            counter: Counter of atom counts, order-preserving.

        Returns:
            OrderedDict suitable for SpinFlipper.
        """
        if len(spins) != len(counter):
            msg = "Length of spins must match number of atom types in counter"
            raise ValueError(msg)
        return OrderedDict((atom, (count, spin)) for (atom, count), spin in zip(counter.items(), spins, strict=True))

    def generate(self, system: Counter, spins=None):
        """Yield SpglibCell copies with all possible balanced magmom assignments.

        Args:
            system: Counter mapping atom type to count (order-preserving).
            spins: Sequence of positive spins, one per atom type, in order.

        Yields:
            SpglibCell: New cell with magmoms set to each balanced configuration.
        """
        if self.cell.magmoms is not None:
            yield self.cell
            return

        if spins is None:
            msg = "spins must be provided as a sequence of positive values"
            raise ValueError(msg)

        flipper_system = self.preprocess(spins, system)
        flipper = SpinFlipper(flipper_system)
        atoms = list(self.cell.atoms)
        idx = 0
        for k, (length, _) in flipper_system.items():
            if atoms[idx : idx + length].count(k) != length:
                msg = f"System segment '{k}' does not match atom sequence in cell"
                raise ValueError(msg)
            idx += length

        for magmoms in flipper.iter_all():
            new_cell = SpglibCell(self.cell.lattice, self.cell.positions, self.cell.atoms, magmoms.copy())
            yield new_cell

    def __call__(self, system: Counter, spins=None):
        """Alias for generate()."""
        yield from self.generate(system, spins)


def filter_unique_magspg(cells: Iterable[SpglibCell]):
    """Filter cells to keep only unique (magmoms, spg) combinations.

    Args:
        cells: Iterable of SpglibCell objects.

    Yields:
        SpglibCell objects with unique (magmoms, spg) pairs.
    """
    seen: dict[SpglibMagneticDataset, SpglibCell] = {}
    for cell in cells:
        if cell.magmoms is None:
            continue
        dataset = cell.symmetry
        if dataset is not None and dataset not in seen:
            seen[dataset] = cell
    return seen
