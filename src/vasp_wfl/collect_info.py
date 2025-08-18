import json
from pathlib import Path

import numpy as np
import pandas as pd

from .cell import get_energies, get_volume
from .dirs import WorkdirClassifier
from .magnetization import MagnetizationParser
from .poscar import ElementCounter
from .report import WorkStatus, classify_by_force

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
        self.root = Path(root)
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
        status_dict = WorkdirClassifier.from_root(self.root, classify_by_force, atol=self.atol).details
        structure_info = {}

        for folder, info in status_dict.items():
            if info["status"] == WorkStatus.DONE:
                contcar_path = self.root / folder / "CONTCAR"
                abs_path = str(contcar_path.resolve())
                outcar_path = self.root / folder / "OUTCAR"
                oszicar_path = self.root / folder / "OSZICAR"

                tot_mag_outcar = None
                tot_mag_oszicar = None
                free_energy, internal_energy = None, None

                if outcar_path.exists():
                    tot_mag_outcar = MagnetizationParser.from_outcar(str(outcar_path))

                if oszicar_path.exists():
                    tot_mag_oszicar = MagnetizationParser.from_oszicar(str(oszicar_path))
                    free_energy, internal_energy = get_energies(str(oszicar_path))

                if not contcar_path.exists():
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
                    composition = ElementCounter.from_file(contcar_path)
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

        Path(output).write_text(json.dumps(self.structure_info, indent=2, default=safe))

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
