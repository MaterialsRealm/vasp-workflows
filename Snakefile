import os
import numpy as np
import shutil
import yaml
import json

from vasp_snake.force import parse_forces_and_check_zero
from vasp_snake.report import FolderClassifier


def find_folders():
    """Return folders that need rerun (PENDING + NOT_CONVERGED) using FolderClassifier API."""
    fc = FolderClassifier.from_directory(".")
    return fc.to_rerun()


rule all:
    input:
        expand("{folder}/done.txt", folder=find_folders()),


rule link:
    input:
        poscar="{folder}/POSCAR",
        incar="INCAR",
        potcar="POTCAR",
        runsh="run.sh",
    output:
        touch("{folder}/.linked"),
    params:
        folder="{folder}",
    shell:
        """
        cd {params.folder}
        ln -sf ../INCAR .
        ln -sf ../POTCAR .
        ln -sf ../run.sh .
        touch .linked
        """


rule run:
    input:
        lambda wildcards: [f"{folder}/POSCAR" for folder in find_folders()],
    output:
        expand("{folder}/done.txt", folder=find_folders()),
    run:
        folders = find_folders()
        for folder in folders:
            print(f"Submitting job in {folder} ...")
            os.system(f"cd {folder} && sbatch run.sh && touch done.txt")


rule clean:
    run:
        folders = find_folders()
        for folder in folders:
            print(f"Cleaning {folder} ...")
            for f in os.listdir(folder):
                if f not in ["POSCAR", "INCAR", "POTCAR", "run.sh"]:
                    file_to_delete = os.path.join(folder, f)
                    if os.path.isdir(file_to_delete):
                        shutil.rmtree(file_to_delete)
                    else:
                        os.remove(file_to_delete)
        print(f"Finished cleaning {len(folders)} folders.")


rule report_status:
    output:
        "report_status.json",
    run:
        # Use FolderClassifier API for reporting
        fc = FolderClassifier.from_directory(".")
        report_data = fc.dumps_status("json")
        with open(output[0], "w") as f:
            json.dump(report_data, f, indent=4)
