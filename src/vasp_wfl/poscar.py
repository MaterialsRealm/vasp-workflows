import os
import re
import shutil
from abc import ABC, abstractmethod
from collections import Counter

from ase.io import read, write
from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar

__all__ = [
    "StructureParser",
    "ElementExtractor",
    "ElementCounter",
    "SiteExtractor",
    "SymmetryDetector",
    "cif_to_poscar",
    "mv_contcar_to_poscar",
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
        poscar = Poscar.from_file(poscar_file)
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
        file_ext = os.path.splitext(path)[1].lower()
        if file_ext == ".cif":
            return StructureParser.from_cif(path)
        elif file_ext in ("", ".poscar"):
            return StructureParser.from_poscar(path)
        else:
            raise ValueError(f"Unsupported file type: '{file_ext}'.")


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
    for cif_file in cif_files:
        cif_dir = os.path.dirname(os.path.abspath(cif_file))
        structure_name = os.path.splitext(os.path.basename(cif_file))[0]
        out_dir = os.path.join(cif_dir, structure_name)
        os.makedirs(out_dir, exist_ok=True)
        atoms = read(cif_file)
        poscar_path = os.path.join(out_dir, "POSCAR")
        write(poscar_path, atoms, format="vasp")


def mv_contcar_to_poscar(folder):
    """
    Ensure POSCAR exists in the given folder.

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
    has_poscar = os.path.exists(poscar)
    has_contcar = os.path.exists(contcar)
    if has_poscar:
        if has_contcar:
            existing = [f for f in os.listdir(folder) if re.match(r"POSCAR_\d+$", f)]
            indices = [
                int(m.group(1)) for f in existing if (m := re.search(r"_(\d+)$", f))
            ]
            next_index = max(indices, default=0) + 1
            backup = os.path.join(folder, f"POSCAR_{next_index}")
            print(f"[{folder}] Backing up POSCAR → {backup}")
            shutil.move(poscar, backup)
            shutil.move(contcar, poscar)
            print(f"[{folder}] Replaced POSCAR with CONTCAR.")
        else:
            print(f"[{folder}] POSCAR exists; no update needed.")
    elif has_contcar:
        shutil.move(contcar, poscar)
        print(f"[{folder}] No POSCAR found; using CONTCAR as POSCAR.")
    else:
        raise FileNotFoundError(f"[{folder}] Neither POSCAR nor CONTCAR exists.")
