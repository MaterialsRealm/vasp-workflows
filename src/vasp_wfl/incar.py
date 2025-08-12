import logging
import os
import shutil


import pystache

from .dirs import WorkdirFinder
from .poscar import ElementCounter

__all__ = [
    "TemplateDistributor",
    "TemplateModifier",
    "update_incar_templates",
]


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

    def render(self, target_dir, variables, mode="append"):
        """
        Render the template with provided variables, handling file content based on mode.

        Args:
            target_dir: Path to the directory containing the target file.
            variables: Dictionary of variables for rendering the Mustache template.
            mode: 'append' to add rendered text to existing content; 'overwrite' to replace it.

        Returns:
            str: The final content to write to the file.
        """
        target_path = os.path.join(target_dir, self.target_file)
        rendered = pystache.render(self.template, variables)

        if mode == "append":
            if os.path.exists(target_path):
                with open(target_path, "r") as f:
                    existing = f.read()
                return existing + "\n" + rendered
            else:
                return rendered
        elif mode == "overwrite":
            return rendered
        else:
            raise ValueError("Invalid mode; must be 'append' or 'overwrite'.")

    def modify(self, target_dir, final_content, mode="append"):
        """
        Write the final content to the target file in the given directory.

        Args:
            target_dir: Path to the directory containing the target file.
            final_content: The final content to write to the file.
            mode: Mode used for logging purposes ('append' or 'overwrite').

        Returns:
            bool: True if modification was successful, False otherwise.
        """
        assert mode in ("append", "overwrite"), (
            "`mode` must be 'append' or 'overwrite'."
        )

        target_path = os.path.join(target_dir, self.target_file)

        if mode == "overwrite" and os.path.exists(target_path):
            try:
                with open(target_path, "r") as f:
                    lines = f.readlines()
                num_lines = len(lines)
                blank_content = "\n" * num_lines
                with open(target_path, "w") as f:
                    f.write(blank_content)
                logger.warning(f"Performed intermediate blanking on '{target_path}'.")
            except Exception as e:
                logger.error(f"Failed to blank '{target_path}': {e}")
                return False

        try:
            with open(target_path, "w") as f:
                f.write(final_content)
            if mode == "append":
                logger.info(f"Appended rendered template to '{target_path}'.")
            else:  # Overwrite
                logger.warning(f"Overwrote '{target_path}' with rendered template")
            return True
        except Exception as e:
            logger.error(f"Failed to modify '{target_path}': {e}")
            return False

    def render_modify(self, target_dir, variables, mode="append"):
        """
        Render the template with provided variables and modify the target file in the given directory.

        Args:
            target_dir: Path to the directory containing the target file.
            variables: Dictionary of variables for rendering the Mustache template.
            mode: 'append' to add rendered text to existing content; 'overwrite' to replace it.

        Returns:
            bool: True if modification was successful, False otherwise.
        """
        final_content = self.render(target_dir, variables, mode)
        return self.modify(target_dir, final_content, mode)


def update_incar_templates(template_str, dirs):
    """
    Update INCAR files in the provided VASP working directories by rendering and applying
    a dynamic template for SYSTEM and MAGMOM based on POSCAR element counts.

    Args:
        dirs: List of VASP working directory paths.
        mode: Modification mode ('append' or 'overwrite') for the target INCAR file.

    Returns:
        set: Set of directories where the INCAR was successfully modified.
    """
    modifier = TemplateModifier(template_str, "INCAR")
    successful_dirs = set()
    for dir in dirs:
        poscar_path = os.path.join(dir, "POSCAR")
        if not os.path.exists(poscar_path):
            logger.warning(f"POSCAR not found in directory '{dir}'. Skipping.")
            continue

        counter = ElementCounter.from_file(poscar_path)
        system_name = os.path.basename(dir)
        magmoms = [{"count": count} for count in counter.values()]
        variables = {"system_name": system_name, "magmoms": magmoms}
        if modifier.render_modify(dir, variables, "overwrite"):
            successful_dirs.add(dir)

    return successful_dirs
