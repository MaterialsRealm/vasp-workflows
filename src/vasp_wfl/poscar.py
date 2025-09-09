import os
import re
import shutil
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path

from ase.io import read, write
from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar

from .logger import LOGGER
from .workdir import WorkdirFinder

__all__ = [
    "ElementCounter",
    "ElementExtractor",
    "PoscarContcarMover",
    "LatticeExtractor",
    "SiteExtractor",
    "AtomsExtractor",
    "StructureParser",
    "SymmetryDetector",
    "cif_to_poscar",
]


class StructureParser:
    """Parser class to extract structures from CIF and POSCAR files."""

    @staticmethod
    def from_cif(cif_file):
        """Extract structure from a CIF file.

        Args:
            cif_file (str): Path to the CIF file.

        Returns:
            pymatgen.Structure: Parsed structure.
        """
        parser = CifParser(cif_file)
        return parser.parse_structures()[0]  # Only one structure expected

    @staticmethod
    def from_poscar(poscar_file):
        """Extract structure from a POSCAR file.

        Args:
            poscar_file (str): Path to the POSCAR file.

        Returns:
            pymatgen.Structure: Parsed structure.
        """
        content = Path(poscar_file).read_text(encoding="ascii")
        poscar = Poscar.from_str(content)  # FIXME: `from_file` will parse wrongly!
        return poscar.structure

    @staticmethod
    def from_file(path):
        """Extract structure based on file extension.

        Args:
            path (str): Path to the file (.cif or .poscar).

        Returns:
            pymatgen.Structure: Parsed structure.

        Raises:
            ValueError: If file type is unsupported.
        """
        file_ext = Path(path).suffix.lower()
        if file_ext == ".cif":
            return StructureParser.from_cif(path)
        if file_ext in {"", ".poscar"}:
            return StructureParser.from_poscar(path)
        msg = f"Unsupported file type: '{file_ext}'."
        raise ValueError(msg)


class StructureProcessor(ABC):
    """Abstract base class for processing structures."""

    @classmethod
    def from_file(cls, path):
        """Process structure from a single file.

        Args:
            path (str): Path to the file (.cif or .poscar).

        Returns:
            Result of processing as defined by subclass implementation.
        """
        structure = StructureParser.from_file(path)
        return cls.process(structure)

    @classmethod
    def from_files(cls, files):
        """Process structures from multiple files.

        Args:
            files (list): List of file paths (.cif or .poscar).

        Returns:
            list: List of processed results.
        """
        return [cls.from_file(f) for f in files]

    @staticmethod
    @abstractmethod
    def process(structure):
        """Abstract method to process a single structure.

        Args:
            structure (pymatgen.Structure): Structure to process.

        Returns:
            Defined by subclass implementation.
        """
        raise NotImplementedError


class ElementExtractor(StructureProcessor):
    """Class to extract unique elements from a structure."""

    @staticmethod
    def process(structure):
        """Extract unique elements from structure.

        Args:
            structure (pymatgen.Structure): Structure to process.

        Returns:
            list: List of unique elements.
        """
        return structure.elements


class ElementCounter(StructureProcessor):
    """Class to count occurrences of elements in a structure."""

    @staticmethod
    def process(structure):
        """Count occurrences of each element in structure.

        Args:
            structure (pymatgen.Structure): Structure to process.

        Returns:
            Counter: Element counts.
        """
        return Counter(structure.species)


class LatticeExtractor(StructureProcessor):
    """Class to extract lattice information from a structure."""

    @staticmethod
    def process(structure):
        """Extract lattice from structure.

        Args:
            structure (pymatgen.Structure): Structure to process.

        Returns:
            pymatgen.Lattice: Lattice information.
        """
        return structure.lattice


class SiteExtractor(StructureProcessor):
    """Class to extract atomic sites from a structure."""

    @staticmethod
    def process(structure):
        """Extract atomic sites from structure.

        Args:
            structure (pymatgen.Structure): Structure to process.

        Returns:
            list: List of atomic sites.
        """
        return structure.sites


class AtomsExtractor(StructureProcessor):
    """Class to extract atomic positions from a structure."""

    @staticmethod
    def process(structure):
        """Extract atomic positions from structure.

        Args:
            structure (pymatgen.Structure): Structure to process.

        Returns:
            list: List of atomic positions.
        """
        return [site.species.iupac_formula for site in structure.sites]


class SymmetryDetector(StructureProcessor):
    """Class to detect symmetry information from a structure."""

    @staticmethod
    def process(structure):
        """Detect symmetry information from structure.

        Args:
            structure (pymatgen.Structure): Structure to process.

        Returns:
            tuple: Space group information.
        """
        return structure.get_space_group_info()


def cif_to_poscar(cif_files):
    """Convert CIF files to POSCAR files, organizing them by directory.

    If all CIF files are in the same directory, create a subdirectory for each file (named after the file
    without the .cif extension), move the CIF file there, and write the POSCAR in that subdirectory. If not,
    write the POSCAR in the same directory as each CIF file.

    Args:
        cif_files: List of CIF file paths.

    Returns:
        List of new CIF file paths (if moved), or the original list if not moved.
    """
    cif_paths = [Path(f).resolve() for f in cif_files]
    cif_dirs = {path.parent for path in cif_paths}
    move_to_subdir = len(cif_dirs) == 1
    result_cifs = []
    for orig_cif_path in cif_paths:
        cif_path = orig_cif_path
        if move_to_subdir:
            # Extract the only element from the set
            base_dir = next(iter(cif_dirs))
            name = cif_path.stem
            target_dir = base_dir / name
            target_dir.mkdir(parents=True, exist_ok=True)
            target_cif = target_dir / cif_path.name
            shutil.move(cif_path, target_cif)
            cif_path = target_cif
        atoms = read(cif_path)
        poscar_path = cif_path.parent / "POSCAR"
        write(poscar_path, atoms, format="vasp")
        result_cifs.append(str(cif_path))
    return result_cifs


class PoscarContcarMover:
    """Class to manage POSCAR/CONTCAR file operations in one or multiple VASP workdirs."""

    @staticmethod
    def update_dir(folder):
        """Ensure POSCAR exists in the given folder, with backup if needed.

        Cases:
        - If POSCAR exists:
            - If CONTCAR exists:
                - Backup POSCAR as POSCAR_{n}
                - Move CONTCAR → POSCAR
            - Else:
                - Do nothing
        - If POSCAR is missing but CONTCAR exists:
            - Move CONTCAR → POSCAR
        - If both are missing:
            - Raise FileNotFoundError
        """
        poscar = os.path.join(folder, "POSCAR")
        contcar = os.path.join(folder, "CONTCAR")
        has_poscar = Path(poscar).exists()
        has_contcar = Path(contcar).exists()
        if has_poscar:
            if has_contcar:
                existing = [f for f in os.listdir(folder) if re.match(r"POSCAR_\\d+$", f)]
                indices = [int(m.group(1)) for f in existing if (m := re.search(r"_(\\d+)$", f))]
                next_index = max(indices, default=0) + 1
                backup = os.path.join(folder, f"POSCAR_{next_index}")
                LOGGER.info("Backing up POSCAR → %s in %s", backup, folder)
                shutil.move(poscar, backup)
                shutil.move(contcar, poscar)
                LOGGER.info("Replaced POSCAR with CONTCAR in %s", folder)
            else:
                LOGGER.info("POSCAR exists; no update needed in %s", folder)
        elif has_contcar:
            shutil.move(contcar, poscar)
            LOGGER.info("No POSCAR found; using CONTCAR as POSCAR in %s", folder)
        else:
            msg = f"Neither POSCAR nor CONTCAR exists in {folder}."
            raise FileNotFoundError(msg)

    @classmethod
    def update_rootdir(cls, root_dir, ignore_patterns=None):
        """Recursively update POSCAR in all VASP workdirs under `root_dir`."""
        workdirs = WorkdirFinder(ignore_patterns).find(root_dir)
        try:
            for workdir in workdirs:
                cls.update_dir(workdir)
        except FileNotFoundError as e:
            LOGGER.warning("%s", e)
