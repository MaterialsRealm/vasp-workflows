import os

from pymatgen.io.vasp import Poscar

__all__ = ["concatenate_potcar", "generate_potcars"]


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
