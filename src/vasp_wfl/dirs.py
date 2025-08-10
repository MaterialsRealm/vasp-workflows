import json
import os
from collections import Counter
from enum import StrEnum
from fnmatch import fnmatch
from typing import Any

import numpy as np
import yaml

from .force import parse_forces_and_check_zero

__all__ = ["WorkdirFinder", "WorkdirClassifier"]


class WorkdirFinder:
    """
    A class for identifying VASP working directories based on the presence of specific input files.
    """

    INPUT_FILES = {
        "CHGCAR",
        "DYNMATFULL",
        "GAMMA",
        "ICONST",
        "INCAR",
        "KPOINTS",
        "KPOINTS_OPT",
        "KPOINTS_WAN",
        "ML_AB",
        "ML_FF",
        "PENALTYPOT",
        "POSCAR",
        "POTCAR",
        "QPOINTS",
        "Vasp.lock",
        "Vaspin.h5",
        "WANPROJ",
        "WAVECAR",
        "WAVEDER",
        "STOPCAR",
    }
    """
    Set of fixed-name VASP input files for detection. Temporary files with patterns
    (e.g., WFULLxxxx.tmp, Wxxxx.tmp) are handled separately using pattern matching.
    """

    @staticmethod
    def is_workdir(dir_path) -> bool:
        """
        Determine if a given directory is a VASP working directory by checking for the presence
        of any VASP input files (without recursing into subdirectories).

        Args:
            dir_path: Path to the directory to check.

        Returns:
            bool: True if the directory contains at least one VASP input file, False otherwise.
        """
        if not os.path.isdir(dir_path):
            return False
        try:
            files = os.listdir(dir_path)
        except Exception:
            return False
        for file in files:
            if file in WorkdirFinder.INPUT_FILES:
                return True
            if fnmatch(file, "WFULL????.tmp") or fnmatch(file, "W????.tmp"):
                return True
        return False

    @staticmethod
    def filter_workdirs(dir_list):
        """
        Filter a list of directories to include only those that are VASP working directories.

        Args:
            dir_list: List of directory paths to filter.

        Returns:
            list: List of paths that are VASP working directories.
        """
        return {d for d in dir_list if WorkdirFinder.is_workdir(d)}

    @staticmethod
    def find_workdirs(start_dir, ignore_patterns=None):
        """
        Identify all VASP working directories within a given starting directory and its entire
        subdirectory tree (recursive), including the start directory if applicable.

        Hidden directories (starting with '.') are excluded from traversal.

        Args:
            start_dir: Path to the starting directory for recursive search.
            ignore_patterns: List of patterns to ignore (uses fnmatch syntax, e.g., ['*backup*', 'temp_*']).

        Returns:
            set: Set of VASP working directory paths (absolute paths).
        """
        workdirs = set()
        ignore_patterns = ignore_patterns or []

        for current_dir, subdirs, files in os.walk(start_dir, topdown=True):
            # Exclude hidden subdirectories and pattern-matched directories from further traversal
            subdirs[:] = [
                d
                for d in subdirs
                if not d.startswith(".")
                and not any(fnmatch(d, pattern) for pattern in ignore_patterns)
            ]
            # Check if the current directory is a working directory
            if WorkdirFinder.is_workdir(current_dir):
                workdirs.add(os.path.abspath(current_dir))

        return workdirs


class Status(StrEnum):
    """Enumeration of possible job statuses for VASP calculations."""

    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


class WorkdirClassifier:
    """Classifies VASP calculation folders by job status and provides summary and filtering utilities."""

    def __init__(self, details):
        """
        Args:
            details (dict): Dictionary mapping folder names to job status details.
        """
        self._details = details

    @classmethod
    def from_directories(cls, directories, atol=1e-6):
        """
        Classify a list of directories by VASP job status.

        Args:
            directories (list): List of directory paths to classify.
            atol (float): Absolute tolerance for force convergence. Defaults to 1e-6.

        Returns:
            WorkdirClassifier: An instance with details populated from the directories.
        """
        details: dict[str, Any] = {}
        for folder_path in directories:
            folder = os.path.basename(folder_path.rstrip(os.sep))
            if not os.path.isdir(folder_path) or folder.startswith("."):
                continue
            outcar = os.path.join(folder_path, "OUTCAR")
            if not os.path.exists(outcar):
                forces_sum = [np.nan, np.nan, np.nan]
                job_status = Status.PENDING
                reason = "OUTCAR missing"
            else:
                forces_sum, is_converged = parse_forces_and_check_zero(
                    outcar, atol=atol
                )
                if forces_sum is None:
                    forces_sum = [np.nan, np.nan, np.nan]
                    job_status = Status.NOT_CONVERGED
                    reason = "No force block found"
                elif is_converged:
                    job_status = Status.DONE
                    reason = "Forces converged"
                else:
                    job_status = Status.NOT_CONVERGED
                    reason = f"Force sum norm {np.linalg.norm(forces_sum):.3g} >= atol {atol}"
                forces_sum = [
                    float(f)
                    for f in (forces_sum if forces_sum is not None else [np.nan] * 3)
                ]
            details[folder] = {
                "status": job_status.value,
                "forces_sum": forces_sum,
                "reason": reason,
            }
        return cls(details)

    @classmethod
    def from_root(cls, root_dir, atol=1e-6, ignore_patterns=None):
        """
        Create a WorkdirClassifier from a root directory by finding and classifying all VASP workdirs.

        Args:
            root_dir (str): Root directory to search for VASP workdirs.
            atol (float): Absolute tolerance for force convergence. Defaults to 1e-6.
            ignore_patterns (list, optional): Patterns to ignore during search.

        Returns:
            WorkdirClassifier: An instance with details populated from the found directories.
        """
        workdirs = WorkdirFinder.find_workdirs(
            root_dir, ignore_patterns=ignore_patterns
        )
        return cls.from_directories(workdirs, atol=atol)

    @property
    def summary(self):
        """
        Compute the fraction of jobs in each status.

        Returns:
            dict: Mapping of job status to fraction of jobs in that status.
        """
        status_list = [v["status"] for v in self._details.values()]
        total = len(status_list)
        counter = Counter(status_list)
        return {
            status: counter.get(status, 0) / total if total else 0.0
            for status in [s.value for s in Status]
        }

    @property
    def details(self):
        """
        Get the raw details dictionary.

        Returns:
            dict: Folder details with job status, force sum, and reason.
        """
        return self._details

    def list_pending(self):
        """
        List folders with PENDING status.

        Returns:
            list: Folder names with status PENDING.
        """
        return [k for k, v in self.details.items() if v["status"] == Status.PENDING]

    def list_done(self):
        """
        List folders with DONE status.

        Returns:
            list: Folder names with status DONE.
        """
        return [k for k, v in self.details.items() if v["status"] == Status.DONE]

    def list_incomplete(self):
        """
        List folders with NOT_CONVERGED status.

        Returns:
            list: Folder names with status NOT_CONVERGED.
        """
        return [
            k for k, v in self.details.items() if v["status"] == Status.NOT_CONVERGED
        ]

    def dump_status(self, filename="status.yaml", key_by="status"):
        """
        Dump the folder status to a JSON or YAML file, format determined by file extension.

        Args:
            filename (str): Output filename. Format is determined by extension (.json, .yaml, .yml).
            key_by (str): 'folder' (default) for {folder: status}, or 'status' for {status: [folders]}.

        Raises:
            ValueError: If the file extension is not supported, or key_by is invalid.
        """
        if key_by == "folder":
            status_map = {k: v["status"] for k, v in self.details.items()}
        elif key_by == "status":
            status_map = {}
            for k, v in self.details.items():
                status = v["status"]
                status_map.setdefault(status, []).append(k)
        else:
            raise ValueError("key_by must be 'folder' or 'status'.")
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".json":
            with open(filename, "w") as f:
                json.dump(status_map, f, indent=2)
        elif ext in (".yaml", ".yml"):
            with open(filename, "w") as f:
                yaml.dump(status_map, f, sort_keys=False)
        else:
            raise ValueError(
                "Unsupported file extension: {}. Use .json, .yaml, or .yml".format(ext)
            )

    def to_rerun(self):
        """
        Generate a list of folders that need to be rerun based on their status.

        Returns:
            list: Folder names that are either PENDING or NOT_CONVERGED.
        """
        return self.list_pending() + self.list_incomplete()
