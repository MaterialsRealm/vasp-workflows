import os

from ase.io import read, write

__all__ = ["cif_to_poscar"]


def cif_to_poscar(cif_files):
    for cif_file in cif_files:
        cif_dir = os.path.dirname(os.path.abspath(cif_file))
        structure_name = os.path.splitext(os.path.basename(cif_file))[0]
        out_dir = os.path.join(cif_dir, structure_name)
        os.makedirs(out_dir, exist_ok=True)
        atoms = read(cif_file)
        poscar_path = os.path.join(out_dir, "POSCAR")
        write(poscar_path, atoms, format="vasp")
