import os
import re
import shutil

__all__ = ["mv_contcar_to_poscar"]


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
