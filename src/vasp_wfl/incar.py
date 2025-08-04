import logging
import os
import shutil
from fnmatch import fnmatch

import pystache

__all__ = ["WorkdirFinder", "TemplateDistributor", "TemplateModifier"]


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
        self.src_files = [
            os.path.abspath(src_file)
            for src_file in src_files
            if os.path.isfile(src_file)
        ]
        for src_file in src_files:
            if not os.path.isfile(src_file):
                logger.warning(
                    f"Source file '{src_file}' does not exist and will be skipped."
                )

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
        finder = WorkdirFinder()
        work_dirs = finder.find_workdirs(start_dir)
        successful_dirs = set()
        for work_dir in work_dirs:
            copied_files = False
            for src_file in self.src_files:
                dest_file = os.path.join(work_dir, os.path.basename(src_file))
                try:
                    if os.path.exists(dest_file) and not overwrite:
                        logger.info(
                            f"Skipping '{dest_file}' as it already exists (overwrite=False)."
                        )
                        continue
                    shutil.copy2(src_file, dest_file)
                    logger.info(f"Copied '{src_file}' to '{dest_file}'.")
                    copied_files = True
                except (PermissionError, OSError) as e:
                    logger.error(f"Failed to copy '{src_file}' to '{dest_file}': {e}")
            if copied_files:
                successful_dirs.add(work_dir)

        return successful_dirs


class TemplateModifier:
    """
    A class representing a single template file, supporting rendering with Mustache syntax
    and modification of target files in append or overwrite modes.
    """

    def __init__(self, template, target_file):
        """
        Initialize with the template text (Mustache syntax) and the target filename.

        Args:
            template: The raw template string with Mustache placeholders.
            target_file: The name of the file to modify in each working directory.
        """
        self.template = template
        self.target_file = target_file

    def render_and_modify(self, target_dir, variables, mode="append"):
        """
        Render the template with provided variables and modify the target file in the given directory.

        Args:
            target_dir: Path to the directory containing the target file.
            variables: Dictionary of variables for rendering the Mustache template.
            mode: 'append' to add rendered text to existing content; 'overwrite' to replace it.

        Returns:
            bool: True if modification was successful, False otherwise.
        """
        target_path = os.path.join(target_dir, self.target_file)
        if not os.path.exists(target_path):
            logger.warning(f"Target file '{target_path}' does not exist; creating it.")
            with open(target_path, "w") as f:
                f.write("")  # Create empty file if needed

        # Render the template
        rendered = pystache.render(self.template, variables)
        try:
            if mode == "append":
                # Read existing content and append rendered
                with open(target_path, "r") as f:
                    existing = f.read()
                new_content = existing + "\n" + rendered  # Add newline for separation
                with open(target_path, "w") as f:
                    f.write(new_content)
                logger.info(f"Appended rendered template to '{target_path}'.")
            elif mode == "overwrite":
                # Read original line count and blank with newlines
                with open(target_path, "r") as f:
                    lines = f.readlines()
                num_lines = len(lines)
                blank_content = "\n" * num_lines
                with open(target_path, "w") as f:
                    f.write(blank_content)
                logger.warning(f"Performed intermediate blanking on '{target_path}'.")
                # Final overwrite with rendered content
                with open(target_path, "w") as f:
                    f.write(rendered)
                logger.warning(f"Overwrote '{target_path}' with rendered template")
            else:
                raise ValueError("Invalid mode; must be 'append' or 'overwrite'.")
            return True
        except Exception as e:
            logger.error(f"Failed to modify '{target_path}': {e}")
            return False
