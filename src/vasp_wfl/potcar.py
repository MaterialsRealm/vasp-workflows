import os

from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar

__all__ = [
    "list_elements",
    "find_potentials",
    "concatenate_potcar",
    "generate_potcars",
    "find_folders",
]


def list_elements(files):
    """Extract all unique elements from a list of CIF files.

    Given a list of CIF files, this function parses each file and extracts
    all unique chemical elements present in the crystal structures.

    Args:
        files (list): List of CIF file paths to parse.

    Returns:
        set: Set of unique element names (strings) found across all CIF files.
    """
    elements = set()
    for cif in files:
        parser = CifParser(cif)
        structure = parser.parse_structures()[0]
        elements.update(element.name for element in structure.elements)
    return elements


def find_potentials(potential_dir, elements):
    """Find corresponding VASP potentials for given elements.

    Given a root directory containing VASP potential files and a set of elements,
    this function locates the POTCAR file for each element. The function expects
    potentials to be organized in subdirectories named after each element.

    Args:
        potential_dir (str): Root directory path containing potential subdirectories.
        elements (set): Set of element names to find potentials for.

    Returns:
        dict: Dictionary mapping element names to their POTCAR file paths.

    Raises:
        FileNotFoundError: If POTCAR file for any element is not found.
    """
    potentials = {}
    for element in elements:
        file = os.path.join(potential_dir, element, "POTCAR")
        potentials[element] = file
        if not os.path.isfile(file):
            raise FileNotFoundError(f"POTCAR file for {element} not found in {file}")
    return potentials


def find_folders(root_dir):
    """
    Find all subfolders in a given root directory, excluding hidden folders.

    Args:
        root_dir (str): Path to the root directory to search.

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


def concatenate_potcar(poscar_path, potcar_map):
    """
    Concatenate POTCAR files according to the order of site symbols in the POSCAR file.

    Args:
        poscar_path (str): Path to the POSCAR file.
        potcar_map (dict): Mapping from element symbol to POTCAR file path, e.g. {'Fe': 'POTCAR_Fe', ...}

    Returns:
        str: Concatenated POTCAR content as a string.
    """
    poscars = Poscar.from_file(poscar_path)
    potcar_contents = []
    for symbol in poscars.site_symbols:
        potcar_file = potcar_map.get(symbol)
        if not potcar_file or not os.path.exists(potcar_file):
            raise FileNotFoundError(
                f"POTCAR file for {symbol} not found: {potcar_file}"
            )
        with open(potcar_file, "r") as f:
            potcar_contents.append(f.read())
    return "".join(potcar_contents)


def generate_potcars(folders, potcar_map):
    """
    For each folder, read the POSCAR, concatenate POTCARs, and write to POTCAR file.

    Args:
        folders (list): List of folder paths.
        potcar_map (dict): Mapping from element symbol to POTCAR file path.

    Raises:
        FileNotFoundError: If POSCAR or POTCAR file is missing.
    """
    for folder in folders:
        poscar_path = os.path.join(folder, "POSCAR")
        if not os.path.exists(poscar_path):
            raise FileNotFoundError(f"POSCAR not found in {folder}")
        potcar_content = concatenate_potcar(poscar_path, potcar_map)
        potcar_file = os.path.join(folder, "POTCAR")
        with open(potcar_file, "w") as f:
            f.write(potcar_content)
