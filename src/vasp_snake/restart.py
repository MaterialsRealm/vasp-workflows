import os
import re
import shutil

__all__ = ["mv_contcar_to_poscar"]


def mv_contcar_to_poscar(folder):
    """
    For a single folder:
      - If CONTCAR exists:
        - Backup POSCAR as POSCAR_{n}, where n is the next available index.
        - Replace POSCAR with CONTCAR.
    """
    poscar = os.path.join(folder, "POSCAR")
    contcar = os.path.join(folder, "CONTCAR")

    if os.path.exists(contcar):
        existing = [f for f in os.listdir(folder) if re.match(r"POSCAR_\d+$", f)]
        indices = [
            int(re.search(r"_(\d+)$", f).group(1))
            for f in existing
            if re.search(r"_(\d+)$", f)
        ]
        next_index = max(indices) + 1 if indices else 1
        backup_poscar = os.path.join(folder, f"POSCAR_{next_index}")

        print(f"[{folder}] Backing up POSCAR → {backup_poscar}")
        shutil.move(poscar, backup_poscar)
        shutil.move(contcar, poscar)
    else:
        print(f"[{folder}] No CONTCAR found; skipping replacement.")
