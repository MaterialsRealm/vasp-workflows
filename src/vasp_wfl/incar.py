import logging
import os
import shutil
from fnmatch import fnmatch

__all__ = ["VaspDirFinder", "TemplateDistributor"]


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
    def find_workdirs(start_dir):
        """
        Identify all VASP working directories within a given starting directory and its entire
        subdirectory tree (recursive), including the start directory if applicable.

        Hidden directories (starting with '.') are excluded from traversal.

        Args:
            start_dir: Path to the starting directory for recursive search.

        Returns:
            set: Set of VASP working directory paths (absolute paths).
        """
        workdirs = set()

        for current_dir, subdirs, files in os.walk(start_dir, topdown=True):
            # Exclude hidden subdirectories from further traversal
            subdirs[:] = [d for d in subdirs if not d.startswith(".")]
            # Check if the current directory is a working directory
            if VaspDirFinder.is_workdir(current_dir):
                workdirs.add(os.path.abspath(current_dir))

        return workdirs


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class TemplateDistributor:
    """
    A class for distributing template input files to VASP working directories.
    """

    def __init__(self, src_files):
        """
        Initialize with a list of source file paths to be copied.

        Args:
            src_files: List of file paths to be distributed to VASP working directories.
        """
        self.src_files = [os.path.abspath(src_file) for src_file in src_files if os.path.isfile(src_file)]
        for src_file in src_files:
            if not os.path.isfile(src_file):
                logger.warning(f"Source file '{src_file}' does not exist and will be skipped.")

    def distribute_templates(self, start_dir, overwrite=False):
        """
        Copy the specified source files to all VASP working directories found under the start directory.

        Args:
            start_dir: Path to the starting directory for recursive search of VASP working directories.
            overwrite: If True, overwrite existing files in target directories; if False, skip them.

        Returns:
            set: Set of VASP working directory paths where files were successfully copied.
        """
        # Initialize VaspDirFinder to locate working directories
        vasp_finder = VaspDirFinder()
        work_dirs = vasp_finder.find_workdirs(start_dir)
        successful_dirs = set()
        for work_dir in work_dirs:
            copied_files = False
            for src_file in self.src_files:
                dest_file = os.path.join(work_dir, os.path.basename(src_file))
                try:
                    if os.path.exists(dest_file) and not overwrite:
                        logger.info(f"Skipping '{dest_file}' as it already exists (overwrite=False).")
                        continue
                    shutil.copy2(src_file, dest_file)
                    logger.info(f"Copied '{src_file}' to '{dest_file}'.")
                    copied_files = True
                except (PermissionError, OSError) as e:
                    logger.error(f"Failed to copy '{src_file}' to '{dest_file}': {e}")
            if copied_files:
                successful_dirs.add(work_dir)

        return successful_dirs
