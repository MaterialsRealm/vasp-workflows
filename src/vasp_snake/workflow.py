import os
import subprocess

import click

from vasp_snake.collect_info import ResultCollector
from vasp_snake.report import FolderClassifier
from vasp_snake.restart import mv_contcar_to_poscar


class VaspWorkflow:
    def __init__(self, root=os.getcwd()):
        self.root = root

    def filter_folders(self):
        return FolderClassifier.from_directory(self.root).to_rerun()

    def run_all(self):
        folders = self.filter_folders()
        for folder in folders:
            self.run(folder)
        return None

    def run(self, folder):
        poscar = os.path.join(self.root, folder, "POSCAR")
        if not os.path.exists(poscar):
            print(f"POSCAR not found in {folder}, skipping.")
            return None
        mv_contcar_to_poscar(folder)
        run_sh = os.path.join(self.root, folder, "run.sh")
        if os.path.exists(run_sh):
            subprocess.run(["sbatch", run_sh], cwd=os.path.join(self.root, folder))
        done_txt = os.path.join(self.root, folder, "done.txt")
        with open(done_txt, "w") as _:
            pass  # Creates an empty file
        print(f"Job submitted and done.txt touched for {folder}")
        return None

    def report_status(self):
        FolderClassifier.from_directory(self.root).dump_status()
        print("report_status.json written.")
        return None

    def collect_info(self, filename="structure_info.csv"):
        folders = self.filter_folders()
        # Check if all done.txt exist
        for folder in folders:
            done_txt = os.path.join(self.root, folder, "done.txt")
            if not os.path.exists(done_txt):
                print(f"Warning: {done_txt} does not exist.")
        rc = ResultCollector(self.root)
        rc.collect()
        df = rc.to_dataframe()
        df.to_csv(os.path.join(self.root, filename))
        print(f"{filename} written.")
        return None


@click.group()
def cli():
    """VASP Workflow Manager - Command line interface for managing VASP workflows."""
    pass


@cli.command("all")
def run_all():
    """Run all VASP calculations that are ready for processing.

    Usage:
        vsn all

    Returns:
        None
    """
    workflow = VaspWorkflow()
    workflow.run_all()
    return None


@cli.command("run")
@click.option("--folder", help="Specific folder to run calculation in")
def run(folder):
    """Run VASP calculation in a specific folder or all eligible folders.

    Args:
        folder: Path to the folder to run calculation in

    Usage:
        vsn run --folder path/to/folder  # Run in specific folder
        vsn run                          # Run in all eligible folders

    Returns:
        None
    """
    workflow = VaspWorkflow()
    if folder:
        workflow.run(folder)
    else:
        workflow.run_all()
    return None


@cli.command("report-status")
def report_status():
    """Generate a status report of all VASP calculations.

    Usage:
        vsn report-status

    Returns:
        None
    """
    workflow = VaspWorkflow()
    workflow.report_status()
    return None


@cli.command("collect-info")
@click.option(
    "--filename",
    default="structure_info.csv",
    help="Output CSV filename for collected information",
)
def collect_info(filename):
    """Collect results from completed VASP calculations into a CSV file.

    Args:
        filename: Output CSV filename for collected information

    Usage:
        vsn collect-info                        # Default output to structure_info.csv
        vsn collect-info --filename results.csv # Custom filename

    Returns:
        None
    """
    workflow = VaspWorkflow()
    workflow.collect_info(filename)
    return None
