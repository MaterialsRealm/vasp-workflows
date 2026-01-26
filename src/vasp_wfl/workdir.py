import json
import threading
from abc import ABC, abstractmethod
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import Path

import yaml

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
        """Return True if the directory is a VASP working directory (contains any VASP input file)."""
        if not self.path.is_dir():
            return False
        return any(self.is_input(file) for file in self.files)

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


class WorkdirProcessor(ABC):
    """Abstract base class for processing VASP working directories.

    Provide a default `threading.Lock` that subclasses can use to protect
    internal mutable state when processing directories concurrently.
    """

    def __init__(self):
        """Initialize synchronization primitives for the processor."""
        # Provide a default lock for subclasses to use for thread-safety.
        self._lock = threading.Lock()

    @abstractmethod
    def process(self, workdir: Workdir, *args, **kwargs) -> object:
        """Process a single Workdir instance and return a result.

        Implementations may return any object representing the processing result.

        Args:
            workdir: A Workdir instance to process.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Any: The processing result for the given workdir.
        """
        pass

    def from_dirs(self, dirs, max_workers: int = 1, *args, **kwargs):
        """Instantiate and process a set of directories as Workdir instances.

        This method can process directories in parallel using threads by setting
        ``max_workers`` to an integer > 1. For thread-safety, subclasses that
        mutate internal state should handle synchronization (e.g., using locks).

        Args:
            dirs: Iterable of directory paths.
            max_workers: Number of worker threads to use for concurrent processing.
                If ``<= 1`` processing is performed sequentially. Defaults to ``1``.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            tuple[list[Future], list[Workdir]]: `(futures, workdirs)`. Returns a
                list of :class:`concurrent.futures.Future` objects (one per workdir) and a list of
                :class:`Workdir` in submission order. The method uses a :class:`ThreadPoolExecutor`
                and waits for all tasks to complete before returning, so the returned futures
                will be completed on return. Exceptions from processing are captured in their
                corresponding futures.
        """
        # Build Workdir objects in submission order; keep uniqueness and order (deduplicate while preserving order)
        workdirs = list(dirs)
        # Normalize `max_workers` to at least 1 and submit all tasks through a ThreadPoolExecutor.
        # Using the executor's context manager waits for completion, so returned futures will be done.
        worker_count = max(1, int(max_workers))
        with ThreadPoolExecutor(max_workers=worker_count) as ex:
            futures = [ex.submit(self.process, workdir, *args, **kwargs) for workdir in workdirs]
        return futures, workdirs

    @staticmethod
    def fetch_results(futures, workdirs):
        """Fetch and return results from futures in submission order.

        Calls ``result()`` on each future in the same order as ``workdirs`` and
        collects the returned values into an :class:`OrderedSet` of results.

        Args:
            futures: Sequence of :class:`concurrent.futures.Future` aligned with ``workdirs``.
            workdirs: Sequence of :class:`Workdir` in submission order.

        Returns:
            list: Results returned by each future, in submission order.

        Raises:
            RuntimeError: If any future raised an exception. The first failure is
                reported in submission order.
        """
        results = []
        # Build Workdir objects in submission order; keep uniqueness and order
        workdirs = list(workdirs)
        for future, workdir in zip(futures, workdirs, strict=True):
            # This will raise the underlying exception if the future failed.
            try:
                result = future.result()
            except Exception as exc:
                msg = f"Processing failed for {workdir}: {exc}"
                raise RuntimeError(msg) from exc
            results.append(result)
        return results, workdirs

    def from_rootdir(self, rootdir, max_workers: int = 1, *args, ignore_patterns=None, **kwargs):
        """Find all valid Workdir directories under `rootdir` and process them.

        This will discover valid workdirs (using :class:`WorkdirFinder`) and
        submit them for processing via :meth:`from_dirs`. When running in
        parallel mode (``max_workers > 1``) the method returns a tuple
        ``(results, workdirs)`` where ``results`` is an :class:`OrderedSet`
        of results returned by each Workdir, in submission order.

        Args:
            rootdir: Path to the root directory to search for Workdirs.
            max_workers: Number of worker threads to use for concurrent processing.
                If ``<= 1`` processing is sequential. Defaults to ``1``.
            *args: Additional positional arguments.
            ignore_patterns: List of patterns to ignore (uses fnmatch syntax, e.g., `['*backup*', 'temp_*']`).
            **kwargs: Additional keyword arguments for `WorkdirFinder`.

        Returns:
            tuple[OrderedSet, OrderedSet[Workdir]]: ``(results, workdirs)`` where
            ``results`` is an :class:`OrderedSet` of results returned by each Workdir
            (empty if nothing was run in parallel), and ``workdirs`` is the ordered set of discovered
            work directories.
        """
        finder = WorkdirFinder(ignore_patterns=ignore_patterns)
        found = finder.find(rootdir)
        futures, workdirs = self.from_dirs(found, max_workers, *args, **kwargs)
        if futures:
            results, workdirs = self.fetch_results(futures, workdirs)
            return results, workdirs
        return [], workdirs


class WorkStatus(StrEnum):
    """Enumeration of possible work statuses for VASP calculations."""

    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


class WorkdirClassifier(WorkdirProcessor):
    """Classify VASP calculation folders by work status and provide summary and filtering utilities."""

    # Note: WorkdirProcessor now provides an internal lock (`self._lock`) for subclasses

    def __init__(self):
        """Initialize an empty WorkdirClassifier.

        Call :class:`WorkdirProcessor.__init__` to ensure a lock is available for
        concurrent processing.
        """
        super().__init__()
        self._details: dict[Workdir, dict] = OrderedDict()

    def process(self, workdir: Workdir, *args, **kwargs):
        """Classify a single Workdir by work status using a callback and store the result.

        The classifier expects the callback function to be supplied as the second positional
        argument (i.e., ``process(workdir, func, *args, **kwargs)``) for backward
        compatibility.

        Args:
            workdir: A Workdir instance to classify.
            *args: Positional arguments where the first should be the callback `func`.
            **kwargs: Keyword arguments passed to `func`.
        """
        if not args or not callable(args[0]):
            msg = "Classifier must be called with a callable `func` as the second argument!"
            raise ValueError(msg)
        func = args[0]
        func_args = args[1:]
        subdetails = func(workdir, *func_args, **kwargs)
        if not isinstance(subdetails, dict) or "status" not in subdetails:
            msg = "Classifier must return a dict with key 'status'!"
            raise ValueError(msg)
        # Protect concurrent writes to the internal details mapping
        with self._lock:
            self._details[workdir] = subdetails

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
