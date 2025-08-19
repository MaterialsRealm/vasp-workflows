import json
from collections import Counter
from collections.abc import Callable
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import Path

import yaml

__all__ = ["WorkdirClassifier", "WorkdirFinder"]

VASP_INPUT_FILES = {
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


class WorkdirFinder:
    """A class for identifying VASP working directories based on the presence of specific input files."""

    @staticmethod
    def is_workdir(directory) -> bool:
        """Determine if a given directory is a VASP working directory by checking for the presence
        of any VASP input files (without recursing into subdirectories).

        Args:
            directory: Path to the directory to check.

        Returns:
            bool: True if the directory contains at least one VASP input file, False otherwise.
        """
        path = Path(directory)
        if not path.is_dir():
            return False
        try:
            files = [f.name for f in path.iterdir() if f.is_file()]
        except OSError:
            return False
        for file in files:
            if file in VASP_INPUT_FILES:
                return True
            if fnmatch(file, "WFULL????.tmp") or fnmatch(file, "W????.tmp"):
                return True
        return False

    @staticmethod
    def filter_workdirs(dir_list):
        """Filter a list of directories to include only those that are VASP working directories.

        Args:
            dir_list: List of directory paths to filter.

        Returns:
            list: List of paths that are VASP working directories.
        """
        return {d for d in dir_list if WorkdirFinder.is_workdir(d)}

    @staticmethod
    def find_workdirs(start_dir, ignore_patterns=None):
        """Identify all VASP working directories within a given starting directory and its entire subdirectory tree (recursive), including the start directory if applicable.

        Hidden directories (starting with '.') are excluded from traversal.

        This implementation uses `pathlib.Path.walk` (available in Python 3.12+).

        Args:
            start_dir: Path to the starting directory for recursive search.
            ignore_patterns: List of patterns to ignore (uses fnmatch syntax, e.g., ['*backup*', 'temp_*']).

        Returns:
            set: Set of VASP working directory paths (absolute paths).

        Raises:
            RuntimeError: If run on a Python version older than 3.12 where `Path.walk` is not available.
        """
        workdirs = set()
        ignore_patterns = ignore_patterns or []

        start_path = Path(start_dir)
        if not hasattr(start_path, "walk"):
            msg = "Use Python 3.12+ to run this function!"
            raise RuntimeError(msg)

        for current_dir, subdirs, _ in start_path.walk(follow_symlinks=True):
            # Exclude hidden subdirectories and pattern-matched directories from further traversal
            subdirs[:] = [
                d
                for d in subdirs
                if not d.startswith(".") and not any(fnmatch(d, pattern) for pattern in ignore_patterns)
            ]
            # Check if the current directory is a working directory
            if WorkdirFinder.is_workdir(current_dir):
                workdirs.add(Path(current_dir).resolve())

        return workdirs


class WorkStatus(StrEnum):
    """Enumeration of possible work statuses for VASP calculations."""

    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


class WorkdirClassifier:
    """Classifies VASP calculation folders by work status and provides summary and filtering utilities."""

    def __init__(self, directories, func: Callable[..., dict], *args, **kwargs):
        """Initialize and classify VASP calculation folders by work status.

        Args:
            directories (list): List of directory paths to classify.
            func (Callable[..., dict]): Function to classify work status.
                Should take `(folder_path, *args, **kwargs)` and return a dict with at least 'status' key.
            *args: Additional positional arguments passed to `func`.
            **kwargs: Additional keyword arguments passed to `func`.
        """
        details = {}
        for directory in directories:
            folder = Path(directory).name
            if not Path(directory).is_dir() or folder.startswith("."):
                continue

            subdetails = func(directory, *args, **kwargs)
            if not isinstance(subdetails, dict) or "status" not in subdetails:
                msg = "Classifier must return a dict with key 'status'!"
                raise ValueError(msg)
            details[folder] = subdetails
        self._details = details

    @classmethod
    def from_root(
        cls,
        root_dir,
        func: Callable[..., dict],
        *args,
        ignore_patterns=None,
        **kwargs,
    ):
        """Create a WorkdirClassifier from a root directory by finding and classifying all VASP workdirs.

        Args:
            root_dir: Root directory to search for VASP workdirs.
            func (Callable[..., dict]): Function to classify work status.
                Should take `(folder_path, *args, **kwargs)` and return a dict with at least 'status' key.
            *args: Additional positional arguments passed to `func`.
            ignore_patterns (list, optional): Patterns to ignore during search.
            **kwargs: Additional keyword arguments passed to `func`.

        Returns:
            WorkdirClassifier: An instance with details populated from the found directories.
        """
        workdirs = WorkdirFinder.find_workdirs(root_dir, ignore_patterns=ignore_patterns)
        return cls(workdirs, func, *args, **kwargs)

    @property
    def summary(self):
        """Compute the fraction of works in each status.

        Returns:
            dict: Mapping of work status to fraction of works in that status.
        """
        status_list = [v["status"] for v in self._details.values()]
        total = len(status_list)
        counter = Counter(status_list)
        return {status: counter.get(status, 0) / total if total else 0.0 for status in [s.value for s in WorkStatus]}

    @property
    def details(self):
        """Get the raw details dictionary.

        Returns:
            dict: Folder details with work status, force sum, and reason.
        """
        return self._details

    def list_pending(self):
        """List folders with `PENDING` status.

        Returns:
            list: Folder names with status `PENDING`.
        """
        return [k for k, v in self.details.items() if v["status"] == WorkStatus.PENDING]

    def list_done(self):
        """List folders with `DONE` status.

        Returns:
            list: Folder names with status `DONE`.
        """
        return [k for k, v in self.details.items() if v["status"] == WorkStatus.DONE]

    def list_incomplete(self):
        """List folders with `NOT_CONVERGED` status.

        Returns:
            list: Folder names with status `NOT_CONVERGED`.
        """
        return [k for k, v in self.details.items() if v["status"] == WorkStatus.NOT_CONVERGED]

    def dump_status(self, filename="status.yaml", key_by="status"):
        """Dump the folder status to a JSON or YAML file, format determined by file extension.

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
            msg = "key_by must be 'folder' or 'status'."
            raise ValueError(msg)
        ext = Path(filename).suffix.lower()
        path = Path(filename)
        if ext == ".json":
            with path.open("w", encoding="utf-8") as f:
                json.dump(status_map, f, indent=2)
        elif ext in {".yaml", ".yml"}:
            with path.open("w", encoding="utf-8") as f:
                yaml.dump(status_map, f, sort_keys=False)
        else:
            msg = f"Unsupported file extension: {ext}. Use .json, .yaml, or .yml"
            raise ValueError(msg)

    def to_rerun(self):
        """Generate a list of folders that need to be rerun based on their status.

        Returns:
            list: Folder names that are either PENDING or NOT_CONVERGED.
        """
        return self.list_pending() + self.list_incomplete()
