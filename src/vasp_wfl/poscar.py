import os

from ase.io import read, write
from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar

__all__ = ["ElementExtractor", "cif_to_poscar"]


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
    def from_poscar(poscar_path):
        """Extract unique element symbols from a POSCAR file.

        Args:
            poscar_path: Path to the POSCAR file.

        Returns:
            set: A set of unique element symbols in the order they appear.
        """
        poscar = Poscar.from_file(poscar_path)
        return set(poscar.site_symbols)

    @staticmethod
    def from_files(files):
        """Extract unique elements from a list of files based on their extensions.

        Processes CIF files (.cif) and POSCAR files (others) separately.

        Args:
            files: List of file paths (CIF or POSCAR files).

        Returns:
            set: Set of unique element names found across all files.
        """
        all_elements = set()
        for file_path in files:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == ".cif":
                # Handle as CIF file
                elements = ElementExtractor.from_cif(file_path)
                all_elements.update(elements)
            else:
                # Handle as POSCAR file
                elements = ElementExtractor.from_poscar(file_path)
                all_elements.update(elements)

        return all_elements


def cif_to_poscar(cif_files):
    for cif_file in cif_files:
        cif_dir = os.path.dirname(os.path.abspath(cif_file))
        structure_name = os.path.splitext(os.path.basename(cif_file))[0]
        out_dir = os.path.join(cif_dir, structure_name)
        os.makedirs(out_dir, exist_ok=True)
        atoms = read(cif_file)
        poscar_path = os.path.join(out_dir, "POSCAR")
        write(poscar_path, atoms, format="vasp")
