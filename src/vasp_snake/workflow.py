import os
import subprocess

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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VASP Workflow Manager")
    parser.add_argument(
        "command",
        choices=["all", "run", "clean", "report_status", "collect_info"],
        help="Workflow command to run",
    )
    parser.add_argument("--folder", help="Specific folder for 'run' command")
    args = parser.parse_args()

    workflow = VaspWorkflow()
    if args.command == "all":
        workflow.run_all()
    elif args.command == "run":
        if args.folder:
            workflow.run(args.folder)
        else:
            workflow.run_all()
    elif args.command == "clean":
        workflow.clean()
    elif args.command == "report_status":
        workflow.report_status()
    elif args.command == "collect_info":
        workflow.collect_info()
