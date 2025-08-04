import os
import re
import shutil

from ase.io import read, write
from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar

__all__ = ["ElementExtractor", "cif_to_poscar", "mv_contcar_to_poscar"]


class ElementExtractor:
    """Class for extracting element symbols from various file formats."""

    @staticmethod
    def from_cif(cif_file):
        """Extract all unique elements from a single CIF file.

        Args:
            cif_file: Path to a CIF file to parse.

        Returns:
            set: A set of unique element names (strings) found in the CIF file.
        """
        parser = CifParser(cif_file)
        structure = parser.parse_structures()[0]
        return {element.name for element in structure.elements}

    @staticmethod
    def from_poscar(poscar_file):
        """Extract unique element symbols from a POSCAR file.

        Args:
            poscar_file: Path to the POSCAR file.

        Returns:
            set: A set of unique element symbols in the order they appear.
        """
        poscar = Poscar.from_file(poscar_file)
        return set(poscar.site_symbols)

    @staticmethod
    def from_file(path):
        """Extract unique elements from a file based on its extension.

        Args:
            path: Path to the file (CIF or POSCAR).

        Returns:
            set: Set of unique element names found in the file.
        """
        file_ext = os.path.splitext(path)[1].lower()
        if not os.path.exists(path):
            return None
        if file_ext == ".cif":
            return ElementExtractor.from_cif(path)
        elif file_ext == "" or file_ext == ".poscar":
            return ElementExtractor.from_poscar(path)
        else:
            raise ValueError(f"Unsupported file type: '{file_ext}'.")

    @staticmethod
    def from_files(files):
        """Extract unique elements from a list of files based on their extensions.

        Processes CIF files (.cif) and POSCAR files (others) separately.

        Args:
            files: List of file paths (CIF or POSCAR files).

        Returns:
            set: Set of unique element names found across all files.
        """
        return {
            element
            for file in files
            for element in ElementExtractor.from_file(file) or set()  # In case of `None`
        }


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
