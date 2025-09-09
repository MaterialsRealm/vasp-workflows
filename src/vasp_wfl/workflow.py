import os
import subprocess

import click

from .collect_info import ResultCollector
from .force import classify_by_force
from .poscar import PoscarContcarMover
from .workdir import WorkdirClassifier


class VaspWorkflow:
    def __init__(self, root=None):
        self.root = root or os.getcwd()

    def filter_folders(self):
        return WorkdirClassifier.from_root(self.root, classify_by_force).to_rerun()

    def run_all(self):
        folders = self.filter_folders()
        for folder in folders:
            self.run(folder)

    def run(self, folder):
        poscar = os.path.join(self.root, folder, "POSCAR")
        if not os.path.exists(poscar):
            print(f"POSCAR not found in {folder}, skipping.")
            return
        PoscarContcarMover.update_dir(folder)
        run_sh = os.path.join(self.root, folder, "run.sh")
        if os.path.exists(run_sh):
            subprocess.run(["sbatch", run_sh], check=True, cwd=os.path.join(self.root, folder))
        done_txt = os.path.join(self.root, folder, "done.txt")
        with open(done_txt, "w") as _:
            pass  # Creates an empty file
        print(f"Job submitted and done.txt touched for {folder}")
        return

    def report_status(self):
        WorkdirClassifier.from_root(self.root, classify_by_force).dump_status()
        print("report_status.json written.")

    def collect_info(self, filename="info.csv"):
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


@cli.command("collect-info")
@click.option(
    "--filename",
    default="info.csv",
    help="Output CSV filename for collected information",
)
def collect_info(filename):
    """Collect results from completed VASP calculations into a CSV file.

    Args:
        filename: Output CSV filename for collected information

    Usage:
        vsn collect-info                        # Default output to info.csv
        vsn collect-info --filename results.csv # Custom filename

    Returns:
        None
    """
    workflow = VaspWorkflow()
    workflow.collect_info(filename)
