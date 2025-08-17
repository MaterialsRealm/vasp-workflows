import shutil
from pathlib import Path

import pystache

from .dirs import WorkdirFinder
from .logger import LOGGER

__all__ = ["TemplateDistributor", "TemplateModifier"]


class TemplateDistributor:
    """A class for distributing template input files to VASP working directories."""

    def __init__(self, src_files):
        """Initialize with a list of source file paths to be copied.

        Args:
            src_files: List of file paths to be distributed to VASP working directories.
        """
        self.src_files = [str(Path(src_file).resolve()) for src_file in src_files if Path(src_file).is_file()]
        for src_file in src_files:
            if not Path(src_file).is_file():
                LOGGER.warning(f"Source file '{src_file}' does not exist and will be skipped.")

    def distribute_templates(self, start_dir, overwrite=False):
        """Copy the specified source files to all VASP working directories found under the start directory.

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
                dest_file = Path(work_dir) / Path(src_file).name
                try:
                    if dest_file.exists() and not overwrite:
                        LOGGER.info(f"Skipping '{dest_file}' as it already exists (overwrite=False).")
                        continue
                    shutil.copy2(src_file, dest_file)
                    LOGGER.info(f"Copied '{src_file}' to '{dest_file}'.")
                    copied_files = True
                except (PermissionError, OSError) as e:
                    LOGGER.error(f"Failed to copy '{src_file}' to '{dest_file}': {e}")
            if copied_files:
                successful_dirs.add(work_dir)

        return successful_dirs


class TemplateModifier:
    """A class representing a single template file, supporting rendering with Mustache syntax
    and modification of target files in append or overwrite modes.
    """

    def __init__(self, template, target_file):
        """Initialize with the template text (Mustache syntax) and the target filename.

        Args:
            template: The raw template string with Mustache placeholders.
            target_file: The name of the file to modify in each working directory.
        """
        self.template = template
        self.target_file = target_file

    def render(self, target_dir, variables, mode="append"):
        """Render the template with provided variables, handling file content based on mode.

        Args:
            target_dir: Path to the directory containing the target file.
            variables: Dictionary of variables for rendering the Mustache template.
            mode: 'append' to add rendered text to existing content; 'overwrite' to replace it.

        Returns:
            str: The final content to write to the file.
        """
        target_path = Path(target_dir) / self.target_file
        rendered = pystache.render(self.template, variables)

        if mode == "append":
            if target_path.exists():
                existing = target_path.read_text(encoding="ascii")
                return existing + "\n" + rendered
            return rendered
        if mode == "overwrite":
            return rendered
        msg = f"{mode} is invalid; must be 'append' or 'overwrite'."
        raise ValueError(msg)

    def modify(self, target_dir, final_content, mode="append"):
        """Write the final content to the target file in the given directory.

        Args:
            target_dir: Path to the directory containing the target file.
            final_content: The final content to write to the file.
            mode: Mode used for logging purposes ('append' or 'overwrite').

        Returns:
            bool: True if modification was successful, False otherwise.
        """
        assert mode in {"append", "overwrite"}, "`mode` must be 'append' or 'overwrite'."

        target_path = Path(target_dir) / self.target_file

        if mode == "overwrite" and target_path.exists():
            try:
                lines = target_path.read_text(encoding="ascii").splitlines(True)
                num_lines = len(lines)
                blank_content = "\n" * num_lines
                target_path.write_text(blank_content, encoding="ascii")
                LOGGER.warning(f"Performed intermediate blanking on '{target_path}'.")
            except OSError as e:
                LOGGER.error(f"Failed to blank '{target_path}': {e}")
                return False

        try:
            target_path.write_text(final_content, encoding="ascii")
            if mode == "append":
                LOGGER.info(f"Appended rendered template to '{target_path}'.")
            else:  # Overwrite
                LOGGER.warning(f"Overwrote '{target_path}' with rendered template")
            return True
        except OSError as e:
            LOGGER.error(f"Failed to modify '{target_path}': {e}")
            return False

    def render_modify(self, target_dir, variables, mode="append"):
        """Render the template with provided variables and modify the target file in the given directory.

        Args:
            target_dir: Path to the directory containing the target file.
            variables: Dictionary of variables for rendering the Mustache template.
            mode: 'append' to add rendered text to existing content; 'overwrite' to replace it.

        Returns:
            bool: True if modification was successful, False otherwise.
        """
        final_content = self.render(target_dir, variables, mode)
        return self.modify(target_dir, final_content, mode)
