import json
import os

import numpy as np

from .cell import count_elements, get_volume
from .report_status import JobStatus, classify_folders

__all__ = ["collect_structure_info"]


def collect_structure_info(root=".", atol=1e-6, output="structure_info.json"):
    status_dict = classify_folders(root=root, atol=atol)["details"]
    structure_info = {}
    for folder, info in status_dict.items():
        if info["status"] == JobStatus.DONE.value:
            contcar_path = os.path.join(root, folder, "CONTCAR")
            abs_path = os.path.abspath(contcar_path)
            outcar_path = os.path.join(root, folder, "OUTCAR")
            total_magnetization = None
            if os.path.exists(outcar_path):  # << Only try if OUTCAR exists
                try:
                    with open(outcar_path) as f:
                        outcar_text = f.read()
                    total_magnetization = parse_total_magnetization(outcar_text)
                except Exception:
                    total_magnetization = None
            if not os.path.exists(contcar_path):
                structure_info[folder] = {
                    "abs_path": abs_path,
                    "volume": np.nan,
                    "composition": None,
                    "last_total_magnetization": total_magnetization,
                    "reason": "CONTCAR missing",
                }
                continue
            try:
                volume = get_volume(contcar_path)
                composition = count_elements(contcar_path)
            except Exception as e:
                structure_info[folder] = {
                    "abs_path": abs_path,
                    "volume": np.nan,
                    "composition": None,
                    "last_total_magnetization": total_magnetization,
                    "reason": f"Failed to parse CONTCAR: {e}",
                }
            else:
                structure_info[folder] = {
                    "abs_path": abs_path,
                    "volume": volume,
                    "composition": composition,
                    "last_total_magnetization": total_magnetization,
                    "reason": "Success",
                }
    # Save as JSON
    with open(output, "w") as f:

        def safe(o):
            if isinstance(o, float) and np.isnan(o):
                return None
            return o

        json.dump(structure_info, f, indent=2, default=safe)
