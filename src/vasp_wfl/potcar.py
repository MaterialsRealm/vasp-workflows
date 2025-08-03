import os

from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar

__all__ = [
    "ElementExtractor",
    "PotcarGenerator",
    "find_folders",
]


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


class PotcarGenerator:
    """Class for generating POTCAR files from structure files."""

    def __init__(self, potential_dir):
        """Initialize PotcarGenerator with potential directory.

        Args:
            potential_dir: Root directory path containing potential subdirectories.
        """
        self.potential_dir = potential_dir

    def find_potentials(self, elements):
        """Find corresponding VASP potentials for given elements.

        Args:
            elements: Set of element names to find potentials for.

        Returns:
            dict: Dictionary mapping element names to their POTCAR file paths.

        Raises:
            FileNotFoundError: If POTCAR file for any element is not found.
        """
        potentials = {}
        for element in elements:
            file = os.path.join(self.potential_dir, element, "POTCAR")
            potentials[element] = file
            if not os.path.isfile(file):
                raise FileNotFoundError(
                    f"POTCAR file for {element} not found in {file}"
                )
        return potentials

    def concatenate_potcar_content(self, elements, potcar_map=None):
        """Concatenate POTCAR files for given elements.

        Args:
            elements: List of element symbols in order.
            potcar_map: Mapping from element symbol to POTCAR file path.
                        If None, will be generated using find_potentials.

        Returns:
            str: Concatenated POTCAR content as a string.

        Raises:
            FileNotFoundError: If POTCAR file for any element is not found.
        """
        if potcar_map is None:
            potcar_map = self.find_potentials(elements)

        potcar_contents = []
        for element in elements:
            potcar_file = potcar_map.get(element)
            if not potcar_file or not os.path.exists(potcar_file):
                raise FileNotFoundError(
                    f"POTCAR file for {element} not found: {potcar_file}"
                )
            with open(potcar_file, "r") as f:
                potcar_contents.append(f.read())
        return "".join(potcar_contents)

    def from_cif(self, cif_file, output_path):
        """Generate POTCAR from a CIF file.

        Args:
            cif_file: Path to the CIF file.
            output_path: Path where POTCAR file will be written.
        """
        elements = ElementExtractor.from_cif(cif_file)
        potcar_content = self.concatenate_potcar_content(elements)

        with open(output_path, "w") as f:
            f.write(potcar_content)

    def from_poscar(self, poscar_file, output_path):
        """Generate POTCAR from a POSCAR file.

        Args:
            poscar_file: Path to the POSCAR file.
            output_path: Path where POTCAR file will be written.
        """
        elements = ElementExtractor.from_poscar(poscar_file)
        potcar_content = self.concatenate_potcar_content(elements)

        with open(output_path, "w") as f:
            f.write(potcar_content)

    def from_files(self, files, output_dir):
        """Generate POTCAR files for multiple structure files.

        For each file, generates a POTCAR in the same directory or specified output directory.

        Args:
            files: List of structure file paths (CIF or POSCAR).
            output_dir: Directory to write POTCAR files. If None, writes to same directory as input file.
        """
        for file_path in files:
            file_dir = os.path.dirname(file_path)  # Determine output path
            output_path = os.path.join(file_dir, "POTCAR")
            file_ext = os.path.splitext(file_path)[1].lower()
            # Generate POTCAR based on file type
            if file_ext == ".cif":
                self.from_cif(file_path, output_path)
            else:
                self.from_poscar(file_path, output_path)


def find_folders(root_dir):
    """
    Find all subfolders in a given root directory, excluding hidden folders.

    Args:
        root_dir: Path to the root directory to search.

    Returns:
        list: List of folder paths (absolute paths).
    """
    folders = []
    for item in os.listdir(root_dir):
        if not item.startswith("."):
            full_path = os.path.join(root_dir, item)
            if os.path.isdir(full_path):
                folders.append(full_path)
    return folders
