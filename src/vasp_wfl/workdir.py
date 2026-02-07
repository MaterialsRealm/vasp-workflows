import json
import threading
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from fnmatch import fnmatch
from functools import partial
from pathlib import Path

import yaml
from tqdm import tqdm

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
        """Initialize with the path to the directory or another Workdir instance.

        Args:
            directory: Path-like object or another :class:`Workdir`.
        """
        path = directory.path if isinstance(directory, Workdir) else Path(directory)
        # Normalize to a resolved path and validate early
        path = path.resolve()
        if not path.exists() or not path.is_dir():
            msg = f"The path '{path}' does not exist or is not a directory."
            raise ValueError(msg)
        # Store as a private attribute to make the public `path` read-only
        self._path: Path = path

    @property
    def path(self) -> Path:
        """Return the `Path` of the workdir (read-only)."""
        return self._path

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
        """Return True if the directory is a VASP working directory (contains any VASP input or output file)."""
        if not self.path.is_dir():
            return False
        return any(self.is_input(file) or self.is_output(file) for file in self.files)

    @property
    def files(self):
        """List of all file names in the directory."""
        return [f.name for f in self.path.iterdir() if f.is_file()]

    @property
    def input_files(self):
        """List of all VASP input files present in the directory."""
        return [f for f in self.files if self.is_input(f)]

    @property
    def output_files(self):
        """List of all VASP output files present in the directory."""
        return [f for f in self.files if self.is_output(f)]

    @property
    def other_files(self):
        """List of all files in the directory that are not recognized as VASP input or output files."""
        return [f for f in self.files if f not in self.input_files and f not in self.output_files]

    def __repr__(self):
        """Return the official string representation of the Workdir."""
        return f"{self.__class__.__name__}('{self.path.absolute()}')"

    def __eq__(self, other):
        """Return True if the other Workdir has the same path."""
        if isinstance(other, Workdir):
            return self.path == other.path
        return NotImplemented

    def __hash__(self):
        """Return the hash based on the path."""
        return hash(self.path)


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
            list: List of paths that are VASP working directories (duplicates removed).
        """
        return list(dict.fromkeys(d for d in directories if Workdir(d).is_valid()))

    def find(self, rootdir):
        """Identify all VASP working directories within a given root directory and its entire subdirectory tree.

        Hidden directories (starting with '.') are excluded from traversal.

        This implementation uses `pathlib.Path.walk` (available in Python 3.12+).

        Args:
            rootdir: Path to the starting directory for recursive search.

        Returns:
            OrderedSet: Set of VASP working directory paths (absolute paths).

        Raises:
            RuntimeError: If run on a Python version older than 3.12 where `Path.walk` is not available.
        """
        workdirs = []
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
            workdir = Workdir(current_dir.resolve())
            if workdir.is_valid() and workdir not in workdirs:
                workdirs.append(workdir)
        return workdirs


class WorkdirProcessor:
    """Utilities for parallel processing of VASP working directories."""

    @staticmethod
    def from_dirs(dirs, fn, *, executor):
        """Submit ``fn(workdir)`` for each dir.

        Args:
            dirs: Iterable of :class:`Workdir` instances.
            fn: Callable accepting a single :class:`Workdir` argument.
            executor: A :class:`concurrent.futures.Executor` used to submit tasks.

        Returns:
            zip: Lazy ``zip(workdirs, futures)`` in submission order.
        """
        workdirs = list(dirs)
        futures = [executor.submit(fn, wd) for wd in workdirs]
        return zip(workdirs, futures)

    @staticmethod
    def from_rootdir(rootdir, fn, *, executor, ignore_patterns=None):
        """Discover workdirs under *rootdir* and submit *fn* for each.

        Args:
            rootdir: Path to the root directory to search.
            fn: Callable accepting a single :class:`Workdir` argument.
            executor: A :class:`concurrent.futures.Executor` used to submit tasks.
            ignore_patterns: Optional list of fnmatch patterns to skip directories.

        Returns:
            zip: Lazy ``zip(workdirs, futures)`` in submission order.
        """
        finder = WorkdirFinder(ignore_patterns=ignore_patterns)
        found = finder.find(rootdir)
        return WorkdirProcessor.from_dirs(found, fn, executor=executor)

    @staticmethod
    def fetch_results(workdirs_futures, *, show_progress=True):
        """Consume ``(workdir, future)`` pairs and collect results.

        Args:
            workdirs_futures: Iterable of ``(workdir, future)`` pairs.
            show_progress: If ``True``, display a tqdm progress bar.

        Returns:
            list[tuple[Workdir, Any]]: Collected ``(workdir, result)`` pairs.

        Raises:
            RuntimeError: If any future raised an exception.
        """
        pairs = list(workdirs_futures)
        results = []
        iterable = tqdm(pairs, desc="Processing", unit="workdir") if show_progress else pairs
        for workdir, future in iterable:
            try:
                result = future.result()
            except Exception as exc:
                raise RuntimeError(f"Processing failed for {workdir}: {exc}") from exc
            results.append((workdir, result))
        return results


class WorkStatus(StrEnum):
    """Enumeration of possible work statuses for VASP calculations."""

    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


class WorkdirClassifier:
    """Classify VASP calculation folders by work status and provide summary and filtering utilities."""

    def __init__(self):
        """Initialize an empty WorkdirClassifier."""
        self._lock = threading.Lock()
        self._details: dict[Workdir, dict] = OrderedDict()

    def _wrap_callback(self, fn):
        """Wrap *fn* so that its result is validated and stored thread-safely."""

        def _inner(workdir):
            subdetails = fn(workdir)
            if not isinstance(subdetails, dict) or "status" not in subdetails:
                raise ValueError("Classifier callback must return a dict with key 'status'!")
            with self._lock:
                self._details[workdir] = subdetails

        return _inner

    def from_rootdir(self, rootdir, fn, *, max_workers=1, ignore_patterns=None, **kwargs):
        """Discover workdirs under *rootdir*, classify each with *fn*.

        Args:
            rootdir: Root directory to search.
            fn: Callable accepting a :class:`Workdir` and returning a dict with key ``'status'``.
            max_workers: Number of worker threads. Defaults to ``1``.
            ignore_patterns: Optional list of fnmatch patterns to skip directories.
            **kwargs: Extra keyword arguments forwarded to *fn* via :func:`functools.partial`.
        """
        callback = partial(fn, **kwargs) if kwargs else fn
        wrapped = self._wrap_callback(callback)
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
            pairs = WorkdirProcessor.from_rootdir(rootdir, wrapped, executor=ex, ignore_patterns=ignore_patterns)
            WorkdirProcessor.fetch_results(pairs, show_progress=False)

    def from_dirs(self, dirs, fn, *, max_workers=1, **kwargs):
        """Classify each directory in *dirs* with *fn*.

        Args:
            dirs: Iterable of :class:`Workdir` instances.
            fn: Callable accepting a :class:`Workdir` and returning a dict with key ``'status'``.
            max_workers: Number of worker threads. Defaults to ``1``.
            **kwargs: Extra keyword arguments forwarded to *fn* via :func:`functools.partial`.
        """
        callback = partial(fn, **kwargs) if kwargs else fn
        wrapped = self._wrap_callback(callback)
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
            pairs = WorkdirProcessor.from_dirs(dirs, wrapped, executor=ex)
            WorkdirProcessor.fetch_results(pairs, show_progress=False)

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
