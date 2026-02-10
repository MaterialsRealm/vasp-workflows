"""Utilities to collect structured results from VASP calculation directories.

Traverse a directory tree, classify work directories, parse structure, energy,
volume, and magnetization information, and expose them as Python dict, JSON, or
pandas DataFrame representations.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from .cell import get_energies, get_volume
from .force import classify_by_force
from .magnetization import MagnetizationParser
from .poscar import ElementCounter
from .workdir import Workdir, WorkdirClassifier, WorkdirProcessor

__all__ = ["DefaultParser", "ResultCollector"]


class DefaultParser:
    """Functor for processing a single VASP workdir and extracting structured results.

    Parses magnetization from OUTCAR/OSZICAR, energy from OSZICAR, and
    structure from CONTCAR/POSCAR. Computes derived quantities
    (magnetization per volume, energy per atom).
    """

    def __call__(self, workdir: Workdir):
        """Process a single workdir and return parsed information.

        Args:
            workdir: Workdir instance to process.

        Returns:
            dict: Parsed information with keys: abs_path, volume, composition,
                  tot_mag_outcar, tot_mag_oszicar, F, E0, magnetization,
                  energy per atom, reason.
        """
        path = workdir.path
        contcar_path = path / "CONTCAR"
        poscar_path = path / "POSCAR"
        outcar_path = path / "OUTCAR"
        oszicar_path = path / "OSZICAR"

        # Parse magnetizations and energies if available.
        tot_mag_outcar = None
        tot_mag_oszicar = None
        free_energy, internal_energy = None, None

        if outcar_path.exists():
            tot_mag_outcar = MagnetizationParser.from_outcar(outcar_path).sum().sum()

        if oszicar_path.exists():
            tot_mag_oszicar = MagnetizationParser.from_oszicar(oszicar_path).iloc[-1]
            free_energy, internal_energy = get_energies(oszicar_path)

        # Determine which structure file to use, prefer CONTCAR over POSCAR.
        structure_file = None
        if contcar_path.exists():
            structure_file = contcar_path
        elif poscar_path.exists():
            structure_file = poscar_path

        # Base result shared across all return paths.
        abs_path = str(path.resolve())
        if structure_file is not None:
            abs_path = str(structure_file.resolve())

        result = {
            "abs_path": abs_path,
            "volume": np.nan,
            "composition": None,
            "tot_mag_outcar": tot_mag_outcar,
            "tot_mag_oszicar": tot_mag_oszicar,
            "F": free_energy,
            "E0": internal_energy,
            "magnetization": None,
            "energy per atom": None,
            "reason": None,
        }

        if structure_file is None:
            result["reason"] = "CONTCAR missing"
            return result

        try:
            volume = get_volume(structure_file)
            composition = ElementCounter.from_file(structure_file)
        except Exception as e:
            result["reason"] = f"Failed to parse structure file: {e}"
            return result

        # Compute derived quantities in the success path.
        magnetization = None
        energy_per_atom = None

        # Robust checks for volume: ensure numeric, non-zero, and not NaN.
        if tot_mag_outcar is not None:
            if volume != 0 and not np.isnan(volume):
                try:
                    magnetization = tot_mag_outcar / volume
                except Exception:
                    magnetization = None

        if free_energy is not None and isinstance(composition, dict) and sum(composition.values()) > 0:
            try:
                energy_per_atom = free_energy / sum(composition.values())
            except Exception:
                energy_per_atom = None

        result.update(
            volume=volume,
            composition=composition,
            magnetization=magnetization,
            **{"energy per atom": energy_per_atom},
        )
        result["reason"] = "Success"
        return result


class ResultCollector:
    """Collect structured information from VASP calculation directories.

    An instance scans a root directory for completed calculations (as determined
    by `WorkdirClassifier`) and extracts volume, composition, energies, and
    magnetization. Parsed values are stored in `info` as a mapping
    from relative directory names to attribute dictionaries once `collect()` is
    invoked.
    """

    def __init__(self, rootdir=".", atol=1e-6):
        """Initialize the collector.

        Args:
            rootdir: Root directory to search for results.
            atol: Absolute tolerance for energy comparison.
        """
        self.rootdir = Path(rootdir)
        self.atol = atol
        self._info = {}
        self._collected = False

    @property
    def info(self):
        """Collected structure information mapping.

        On first access, trigger `collect()` to populate the data. Always
        return a dictionary (empty if no results found).
        """
        if not self._collected:
            self.collect()
        return self._info

    def collect(self, parser=None, max_workers=4):
        """Collect information from VASP calculation subdirectories in parallel.

        Scan subdirectories, classify calculation status, and for completed
        runs process them using the provided functor. Store results in `self.info`.

        Args:
            parser: Callable accepting a Workdir and returning a dict of results.
                       Defaults to DefaultParser().
            max_workers: Number of worker threads for parallel processing.
                         Defaults to 4. Use 1 for sequential processing.

        Example:
            collector = ResultCollector(root="./vasp_runs")
            collector.collect(parser=DefaultParser(), max_workers=4)
        """
        if parser is None:
            parser = DefaultParser()

        classifier = WorkdirClassifier()
        classifier.from_rootdir(self.rootdir, classify_by_force, atol=self.atol)

        # Filter for DONE directories
        done_workdirs = classifier.list_done()

        # Process in parallel using WorkdirProcessor
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
            pairs = WorkdirProcessor.from_dirs(done_workdirs, parser, executor=executor)
            results = WorkdirProcessor.fetch_results(pairs, show_progress=True)

        # Aggregate results into self._info
        self._info = {workdir: result for workdir, result in results}
        self._collected = True

    def to_json(self, output="info.json"):
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

        Path(output).write_text(json.dumps(self.info, indent=2, default=safe))

    def to_dataframe(self):
        """Convert collected structure information to a pandas DataFrame.

        Raises:
            ValueError: If `collect()` has not been called yet.

        Example:
            df = collector.to_dataframe()
        """
        df = pd.DataFrame.from_dict(self.info, orient="index")
        df.insert(0, "name", [workdir.path.name for workdir in self.info])
        df = df.reset_index(drop=True)
        # Expand composition dictionary into columns
        composition_df = df["composition"].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series)
        df = pd.concat([df, composition_df], axis=1)
        return df
