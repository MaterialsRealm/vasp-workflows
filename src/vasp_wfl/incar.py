import os
from fnmatch import fnmatch

__all__ = ["VaspDirFinder"]


class VaspDirFinder:
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
            if file in VaspDirFinder.INPUT_FILES:
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
        return {d for d in dir_list if VaspDirFinder.is_workdir(d)}

    @staticmethod
    def find_workdirs(start_dir: str) -> list[str]:
        """
        Identify all VASP working directories within a given starting directory and its entire
        subdirectory tree (recursive), including the start directory if applicable.

        Hidden directories (starting with '.') are excluded from traversal.

        Args:
            start_dir: Path to the starting directory for recursive search.

        Returns:
            list: List of VASP working directory paths (absolute paths).
        """
        workdirs = []
        for current_dir, subdirs, files in os.walk(start_dir, topdown=True):
            # Exclude hidden subdirectories from further traversal
            subdirs[:] = [d for d in subdirs if not d.startswith(".")]
            # Check if the current directory is a working directory
            if VaspDirFinder.is_workdir(current_dir):
                workdirs.append(os.path.abspath(current_dir))

        return workdirs
