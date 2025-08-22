"""Utilities to collect structured results from VASP calculation directories.

Traverse a directory tree, classify work directories, parse structure, energy,
volume, and magnetization information, and expose them as Python dict, JSON, or
pandas DataFrame representations.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .cell import get_energies, get_volume
from .dirs import WorkdirClassifier, WorkStatus
from .force import classify_by_force
from .magnetization import MagnetizationParser
from .poscar import ElementCounter

__all__ = ["ResultCollector"]


class ResultCollector:
    """Collect structured information from VASP calculation directories.

    An instance scans a root directory for completed calculations (as determined
    by `WorkdirClassifier`) and extracts volume, composition, energies, and
    magnetization. Parsed values are stored in `structure_info` as a mapping
    from relative directory names to attribute dictionaries once `collect()` is
    invoked.
    """

    def __init__(self, root=".", atol=1e-6):
        """Initialize the collector.

        Args:
            root: Root directory to search for results.
            atol: Absolute tolerance for energy comparison.
        """
        self.root = Path(root)
        self.atol = atol
        self._structure_info = {}
        self._collected = False

    @property
    def structure_info(self):
        """Collected structure information mapping.

        On first access, trigger `collect()` to populate the data. Always
        return a dictionary (empty if no results found).
        """
        if not self._collected:
            self.collect()
        return self._structure_info

    def collect(self):
        """Collect information from VASP calculation subdirectories.

        Scan subdirectories, classify calculation status, and for completed
        runs parse structure (volume, composition), total magnetization (from
        OUTCAR/OSZICAR), and energies. Store results in `self.structure_info`.

        Example:
            collector = ResultCollector(root="./vasp_runs")
            collector.collect()
        """
        status_dict = WorkdirClassifier.from_root(self.root, classify_by_force, atol=self.atol).details
        structure_info = {}

        for folder, info in status_dict.items():
            if info["status"] == WorkStatus.DONE:
                contcar_path = self.root / folder / "CONTCAR"
                poscar_path = self.root / folder / "POSCAR"
                abs_path = str(contcar_path.resolve())
                outcar_path = self.root / folder / "OUTCAR"
                oszicar_path = self.root / folder / "OSZICAR"

                tot_mag_outcar = None
                tot_mag_oszicar = None
                free_energy, internal_energy = None, None

                if outcar_path.exists():
                    tot_mag_outcar = MagnetizationParser.from_outcar(outcar_path)

                if oszicar_path.exists():
                    tot_mag_oszicar = MagnetizationParser.from_oszicar(oszicar_path)
                    free_energy, internal_energy = get_energies(oszicar_path)

                # Check for CONTCAR, fallback to POSCAR if missing
                structure_file = None
                if contcar_path.exists():
                    structure_file = contcar_path
                elif poscar_path.exists():
                    structure_file = poscar_path
                if structure_file is None:
                    structure_info[folder] = {
                        "abs_path": abs_path,
                        "volume": np.nan,
                        "composition": None,
                        "tot_mag_outcar": tot_mag_outcar,
                        "tot_mag_oszicar": tot_mag_oszicar,
                        "F": free_energy,
                        "E0": internal_energy,
                        "magnetization": None,
                        "energy per atom": None,
                        "reason": "CONTCAR missing",
                    }
                    continue
                try:
                    volume = get_volume(structure_file)
                    composition = ElementCounter.from_file(structure_file)
                except Exception as e:
                    structure_info[folder] = {
                        "abs_path": abs_path,
                        "volume": np.nan,
                        "composition": None,
                        "tot_mag_outcar": tot_mag_outcar,
                        "tot_mag_oszicar": tot_mag_oszicar,
                        "F": free_energy,
                        "E0": internal_energy,
                        "magnetization": None,
                        "energy per atom": None,
                        "reason": f"Failed to parse structure file: {e}",
                    }
                else:
                    # Calculate magnetization and energy per atom
                    magnetization = None
                    energy_per_atom = None
                    if tot_mag_outcar is not None and volume not in [None, 0, np.nan]:
                        try:
                            magnetization = tot_mag_outcar / volume
                        except Exception:
                            magnetization = None
                    if free_energy is not None and isinstance(composition, dict) and sum(composition.values()) > 0:
                        try:
                            energy_per_atom = free_energy / sum(composition.values())
                        except Exception:
                            energy_per_atom = None
                    structure_info[folder] = {
                        "abs_path": abs_path,
                        "volume": volume,
                        "composition": composition,
                        "tot_mag_outcar": tot_mag_outcar,
                        "tot_mag_oszicar": tot_mag_oszicar,
                        "F": free_energy,
                        "E0": internal_energy,
                        "magnetization": magnetization,
                        "energy per atom": energy_per_atom,
                        "reason": "Success",
                    }
        # Store into internal storage and mark collected.
        self._structure_info = structure_info
        self._collected = True

    def to_json(self, output="structure_info.json"):
        """Save collected structure information to a JSON file.

        Args:
            output: Path to the output JSON file.

        Raises:
            ValueError: If `collect()` has not been called yet.

        Example:
            collector.to_json("my_results.json")
        """

        def safe(o):
            if isinstance(o, float) and np.isnan(o):
                return None
            return o

        Path(output).write_text(json.dumps(self.structure_info, indent=2, default=safe))

    def to_dataframe(self):
        """Convert collected structure information to a pandas DataFrame.

        Expands the `composition` mapping into individual element columns.

        Raises:
            ValueError: If `collect()` has not been called yet.

        Example:
            df = collector.to_dataframe()
        """
        df = pd.DataFrame.from_dict(self.structure_info, orient="index")
        df = df.reset_index().rename(columns={"index": "index"})
        # Expand composition dictionary into columns
        composition_df = df["composition"].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series)
        df = pd.concat([df.drop(columns=["composition"]), composition_df], axis=1)
        return df
