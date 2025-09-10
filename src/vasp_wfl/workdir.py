import json
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import Path

import yaml
from ordered_set import OrderedSet

__all__ = ["Workdir", "WorkdirClassifier", "WorkdirFinder", "WorkdirProcessor"]

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

VASP_OUTPUT_FILES = {
    "BSEFATBAND",
    "CHG",
    "CHGCAR",
    "CONTCAR",
    "CONTCAR_ELPH",
    "DOSCAR",
    "DYNMATFULL",
    "EIGENVAL",
    "ELFCAR",
    "IBZKPT",
    "LOCPOT",
    "ML_ABN",
    "ML_EATOM",
    "ML_FFN",
    "ML_HEAT",
    "ML_HIS",
    "ML_LOGFILE",
    "ML_REG",
    "NMRCURBX",
    "OSZICAR",
    "OUTCAR",
    "Output",
    "PCDAT",
    "PARCHG",
    "Phelel_params.hdf5",
    "POT",
    "PRJCAR",
    "PROCAR",
    "PROCAR_OPT",
    "PROOUT",
    "REPORT",
    "TMPCAR",
    "UIJKL",
    "URijkl",
    "Vaspelph.h5",
    "Vaspout.h5",
    "Vaspwave.h5",
    "vasprun.xml",
    "VIJKL",
    "VRijkl",
    "WANPROJ",
    "WAVECAR",
    "WAVEDER",
    "XDATCAR",
}
"""Set of fixed-name VASP output files for reference.
See https://www.vasp.at/wiki/index.php/Category:Output_files
"""


class Workdir:
    """Represents a VASP working directory and provides file classification utilities."""

    def __init__(self, directory):
        """Initialize with the path to the directory."""
        self.path = Path(directory)
        if not self.path.exists() or not self.path.is_dir():
            msg = f"The path '{directory}' does not exist or is not a directory."
            raise ValueError(msg)

    @staticmethod
    def is_input(filename: str) -> bool:
        """Return True if the filename is a VASP input file (including patterns)."""
        name = Path(filename).name
        if name in VASP_INPUT_FILES:
            return True
        return fnmatch(name, "WFULL????.tmp") or fnmatch(name, "W????.tmp")

    @staticmethod
    def is_output(filename: str) -> bool:
        """Return True if the filename is a VASP output file (including patterns)."""
        name = Path(filename).name
        if name in VASP_OUTPUT_FILES:
            return True
        return fnmatch(name, "WFULL????.tmp") or fnmatch(name, "W????.tmp")

    def is_valid(self) -> bool:
        """Return True if the directory is a VASP working directory (contains any VASP input file)."""
        if not self.path.is_dir():
            return False
        return any(self.is_input(file) for file in self.files)

    @property
    def files(self):
        """OrderedSet of all file names in the directory."""
        return OrderedSet(f.name for f in self.path.iterdir() if f.is_file())

    @property
    def input_files(self):
        """OrderedSet of all VASP input files present in the directory."""
        return OrderedSet(f for f in self.files if self.is_input(f))

    @property
    def output_files(self):
        """OrderedSet of all VASP output files present in the directory."""
        return OrderedSet(f for f in self.files if self.is_output(f))

    @property
    def other_files(self):
        """OrderedSet of all files in the directory that are not recognized as VASP input or output files."""
        return self.files - self.input_files - self.output_files

    def __repr__(self):
        """Return the official string representation of the Workdir."""
        return f"{self.__class__.__name__}('{self.path}')"


class WorkdirFinder:
    """A class for identifying VASP working directories based on the presence of specific input files."""

    def __init__(self, ignore_patterns=None):
        """Initialize with optional ignore patterns.

        Args:
            ignore_patterns: List of patterns to ignore (uses fnmatch syntax, e.g., `['*backup*', 'temp_*']`).
        """
        self.ignore_patterns = ignore_patterns or []

    @staticmethod
    def filter(directories):
        """Filter a list of directories to include only those that are VASP working directories.

        Args:
            directories: List of directory paths to filter.

        Returns:
            list: List of paths that are VASP working directories.
        """
        return OrderedSet(d for d in directories if Workdir(d).is_valid())

    def find(self, rootdir):
        """Identify all VASP working directories within a given root directory and its entire subdirectory tree.

        Hidden directories (starting with '.') are excluded from traversal.

        This implementation uses `pathlib.Path.walk` (available in Python 3.12+).

        Args:
            rootdir: Path to the starting directory for recursive search.

        Returns:
            set: Set of VASP working directory paths (absolute paths).

        Raises:
            RuntimeError: If run on a Python version older than 3.12 where `Path.walk` is not available.
        """
        workdirs = set()
        root_path = Path(rootdir)
        if not hasattr(root_path, "walk"):
            msg = "Use Python 3.12+ to run this function!"
            raise RuntimeError(msg)

        for current_dir, subdirs, _ in root_path.walk(follow_symlinks=True):
            # Exclude hidden subdirectories and pattern-matched directories from further traversal
            subdirs[:] = [
                d
                for d in subdirs
                if not d.startswith(".") and not any(fnmatch(d, pattern) for pattern in self.ignore_patterns)
            ]
            # Check if the current directory is a working directory
            if Workdir(current_dir).is_valid():
                workdirs.add(Path(current_dir).resolve())

        return workdirs


class WorkdirProcessor(ABC):
    """Abstract base class for processing VASP working directories."""

    @abstractmethod
    def process(self, workdir: Workdir, *args, **kwargs):
        """Process a single Workdir instance. Must be implemented by subclasses.

        Args:
            workdir: A Workdir instance to process.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        pass

    @classmethod
    def from_dirs(cls, dirs, *args, **kwargs):
        """Instantiate and process a set of directories as Workdir instances.

        Args:
            dirs: Iterable of directory paths.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        processor = cls()
        for d in dirs:
            workdir = Workdir(d)
            processor.process(workdir, *args, **kwargs)

    @classmethod
    def from_rootdir(cls, rootdir, *args, ignore_patterns=None, **kwargs):
        """Find all valid Workdir directories under rootdir and process them.

        Args:
            rootdir: Path to the root directory to search for Workdirs.
            *args: Additional positional arguments.
            ignore_patterns: List of patterns to ignore (uses fnmatch syntax, e.g., `['*backup*', 'temp_*']`).
            **kwargs: Additional keyword arguments for `WorkdirFinder`.
        """
        finder = WorkdirFinder(ignore_patterns=ignore_patterns)
        workdirs = finder.find(rootdir)
        cls.from_dirs(workdirs, *args, **kwargs)


class WorkStatus(StrEnum):
    """Enumeration of possible work statuses for VASP calculations."""

    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


class WorkdirClassifier(WorkdirProcessor):
    """Classifies VASP calculation folders by work status and provides summary and filtering utilities."""

    def __init__(self):
        """Initialize an empty WorkdirClassifier."""
        self._details = {}

    def process(self, workdir: Workdir, func: Callable[..., dict], *args, **kwargs):
        """Classify a single Workdir by work status using a callback and store the result.

        Args:
            workdir: A Workdir instance to classify.
            func (Callable[..., dict]): Function to classify work status.
                Should take `(folder_path, *args, **kwargs)` and return a dict with at least 'status' key.
            *args: Additional positional arguments passed to `func`.
            **kwargs: Additional keyword arguments passed to `func`.
        """
        subdetails = func(workdir, *args, **kwargs)
        if not isinstance(subdetails, dict) or "status" not in subdetails:
            msg = "Classifier must return a dict with key 'status'!"
            raise ValueError(msg)
        self._details[str(workdir.path)] = subdetails

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
