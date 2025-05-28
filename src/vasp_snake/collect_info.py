import json
import os

import numpy as np
import pandas as pd

from .cell import count_elements, get_volume
from .magnetization import MagnetizationParser
from .report import FolderClassifier, JobStatus

__all__ = ["ResultCollector"]


class ResultCollector:
    def __init__(self, root=".", atol=1e-6):
        self.root = root
        self.atol = atol
        self.structure_info = None

    def collect(self):
        status_dict = FolderClassifier.from_directory(self.root, self.atol).details
        structure_info = {}

        for folder, info in status_dict.items():
            if info["status"] == JobStatus.DONE:
                contcar_path = os.path.join(self.root, folder, "CONTCAR")
                abs_path = os.path.abspath(contcar_path)
                outcar_path = os.path.join(self.root, folder, "OUTCAR")
                oszicar_path = os.path.join(self.root, folder, "OSZICAR")

                tot_mag_outcar = None
                tot_mag_oszicar = None

                if os.path.exists(outcar_path):
                    tot_mag_outcar = MagnetizationParser.from_outcar(outcar_path)

                if os.path.exists(oszicar_path):
                    tot_mag_oszicar = MagnetizationParser.from_oszicar(oszicar_path)

                if not os.path.exists(contcar_path):
                    structure_info[folder] = {
                        "abs_path": abs_path,
                        "volume": np.nan,
                        "composition": None,
                        "tot_mag_outcar": tot_mag_outcar,
                        "tot_mag_oszicar": tot_mag_oszicar,
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
                        "tot_mag_outcar": tot_mag_outcar,
                        "tot_mag_oszicar": tot_mag_oszicar,
                        "reason": f"Failed to parse CONTCAR: {e}",
                    }
                else:
                    structure_info[folder] = {
                        "abs_path": abs_path,
                        "volume": volume,
                        "composition": composition,
                        "tot_mag_outcar": tot_mag_outcar,
                        "tot_mag_oszicar": tot_mag_oszicar,
                        "reason": "Success",
                    }
        self.structure_info = structure_info

    def to_json(self, output="structure_info.json"):
        if self.structure_info is None:
            raise ValueError("You must run collect() before saving JSON.")

        def safe(o):
            if isinstance(o, float) and np.isnan(o):
                return None
            return o

        with open(output, "w") as f:
            json.dump(self.structure_info, f, indent=2, default=safe)

    def to_dict(self):
        if self.structure_info is None:
            raise ValueError("You must run collect() before returning dict.")
        return self.structure_info

    def to_dataframe(self):
        if self.structure_info is None:
            raise ValueError("You must run collect() before converting to DataFrame.")
        df = pd.DataFrame.from_dict(self.structure_info, orient="index")
        # Expand composition dictionary into columns
        composition_df = (
            df["composition"]
            .apply(lambda x: x if isinstance(x, dict) else {})
            .apply(pd.Series)
        )
        df = pd.concat([df.drop(columns=["composition"]), composition_df], axis=1)
        return df
