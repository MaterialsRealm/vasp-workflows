from collections import OrderedDict
from collections.abc import Iterator, Mapping, Sequence
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
from pymatgen.io.vasp import Incar, Outcar, Poscar

from .logger import LOGGER
from .poscar import AtomsExtractor, LatticeExtractor, SiteExtractor
from .spglib import SpglibCell
from .workdir import WorkdirFinder

__all__ = [
    "FerromagneticSetter",
    "SpinFlipper",
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
    def system(self) -> OrderedDict:
        return self._system

    @system.setter
    def system(self, system: Mapping) -> None:
        system = OrderedDict(system)
        self._validate(system)
        self._system = system

    @staticmethod
    def _validate(od: OrderedDict) -> None:
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
    def count_segment(length: int) -> int:
        """Return the number of balanced ups/downs for a segment of given length.

        Args:
            length: Even integer ≥ 0.

        Returns:
            The number of ways to assign half 'ups' and half 'downs'.
        """
        return 0 if length % 2 else comb(length, length // 2)

    @property
    def count(self) -> int:
        """Return the total number of combinations for the current system.

        The result is the product over all segments of C(length, length // 2).
        """
        total = 1
        for length, _ in self.system.values():
            total *= self.count_segment(length)
        return total

    def flip_segment(self, base: Sequence, downs: Sequence[int]) -> np.ndarray:
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

    def iter_segment(self, length: int, a=1) -> Iterator[np.ndarray]:
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

    def iter_all(self) -> Iterator[np.ndarray]:
        """Yield all concatenated sign vectors across all segments in system order.

        Each yielded array is the concatenation of one balanced vector per segment.

        Yields:
            Numpy arrays of shape (sum of all lengths,) with balanced +a/-a entries.
        """
        items = list(self.system.items())  # already validated in __init__/setter
        if not items:
            return

        # Backtracking to avoid materializing huge Cartesian products.
        def _dfs_join(i: int, parts: list[np.ndarray]) -> Iterator[np.ndarray]:
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
