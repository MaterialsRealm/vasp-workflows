import json
import os

import numpy as np
import pandas as pd

from .cell import count_elements, get_energies, get_volume
from .dirs import WorkdirClassifier
from .magnetization import MagnetizationParser
from .report import Status, default_classifier

__all__ = ["ResultCollector"]


class ResultCollector:
    def __init__(self, root=".", atol=1e-6):
        """Initializes the ResultCollector.

        Args:
            root (str):
                Root directory to search for results. Defaults to current directory.
            atol (float):
                Absolute tolerance for energy comparison. Defaults to 1e-6.
        """
        self.root = root
        self.atol = atol
        self.structure_info = None

    def collect(self):
        """Collects information from VASP calculation folders.

        Scans subdirectories for calculation results, parses relevant files (CONTCAR, OUTCAR, OSZICAR),
        and stores structure and energy information in self.structure_info.

        Returns:
            None

        Example:
            collector = ResultCollector(root="./vasp_runs")
            collector.collect()
        """
        status_dict = WorkdirClassifier.from_root(self.root, default_classifier, atol=self.atol).details
        structure_info = {}

        for folder, info in status_dict.items():
            if info["status"] == Status.DONE:
                contcar_path = os.path.join(self.root, folder, "CONTCAR")
                abs_path = os.path.abspath(contcar_path)
                outcar_path = os.path.join(self.root, folder, "OUTCAR")
                oszicar_path = os.path.join(self.root, folder, "OSZICAR")

                tot_mag_outcar = None
                tot_mag_oszicar = None
                free_energy, internal_energy = None, None

                if os.path.exists(outcar_path):
                    tot_mag_outcar = MagnetizationParser.from_outcar(outcar_path)

                if os.path.exists(oszicar_path):
                    tot_mag_oszicar = MagnetizationParser.from_oszicar(oszicar_path)
                    free_energy, internal_energy = get_energies(oszicar_path)

                if not os.path.exists(contcar_path):
                    structure_info[folder] = {
                        "abs_path": abs_path,
                        "volume": np.nan,
                        "composition": None,
                        "tot_mag_outcar": tot_mag_outcar,
                        "tot_mag_oszicar": tot_mag_oszicar,
                        "F": free_energy,
                        "E0": internal_energy,
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
                        "F": free_energy,
                        "E0": internal_energy,
                        "reason": f"Failed to parse CONTCAR: {e}",
                    }
                else:
                    structure_info[folder] = {
                        "abs_path": abs_path,
                        "volume": volume,
                        "composition": composition,
                        "tot_mag_outcar": tot_mag_outcar,
                        "tot_mag_oszicar": tot_mag_oszicar,
                        "F": free_energy,
                        "E0": internal_energy,
                        "reason": "Success",
                    }
        self.structure_info = structure_info

    def to_json(self, output="structure_info.json"):
        """Saves the collected structure information to a JSON file.

        Args:
            output (str):
                Path to the output JSON file. Defaults to 'structure_info.json'.

        Returns:
            None

        Raises:
            ValueError: If collect() has not been run before calling this method.

        Example:
            collector.to_json("my_results.json")
        """
        if self.structure_info is None:
            raise ValueError("You must run collect() before saving JSON.")

        def safe(o):
            if isinstance(o, float) and np.isnan(o):
                return None
            return o

        with open(output, "w") as f:
            json.dump(self.structure_info, f, indent=2, default=safe)

    def to_dict(self):
        """Returns the collected structure information as a dictionary.

        Returns:
            dict: The structure information collected from calculation folders.

        Raises:
            ValueError: If collect() has not been run before calling this method.

        Example:
            info = collector.to_dict()
        """
        if self.structure_info is None:
            raise ValueError("You must run collect() before returning dict.")
        return self.structure_info

    def to_dataframe(self):
        """Converts the collected structure information to a pandas DataFrame.

        Returns:
            pandas.DataFrame: DataFrame containing structure and energy information for each folder.

        Raises:
            ValueError: If collect() has not been run before calling this method.

        Example:
            df = collector.to_dataframe()
        """
        if self.structure_info is None:
            raise ValueError("You must run collect() before converting to DataFrame.")
        df = pd.DataFrame.from_dict(self.structure_info, orient="index")
        df = df.reset_index().rename(columns={"index": "index"})
        # Expand composition dictionary into columns
        composition_df = df["composition"].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series)
        df = pd.concat([df.drop(columns=["composition"]), composition_df], axis=1)
        return df
