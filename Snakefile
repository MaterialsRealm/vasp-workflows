import os
import numpy as np
import shutil
import yaml
import json

from vasp_snake.collect_info import ResultCollector
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
        poscar="{folder}/POSCAR",
        linked="{folder}/.linked",
    output:
        done="{folder}/done.txt",
    params:
        folder="{folder}",
    shell:
        """
        cd {params.folder}
        sbatch run.sh
        touch done.txt
        """


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
        FolderClassifier.from_directory(".").dump_status()


rule collect_info:
    input:
        expand("{folder}/done.txt", folder=find_folders()),
    output:
        "structure_info.csv",
    run:
        rc = ResultCollector(".")
        rc.collect()
        df = rc.to_dataframe()
        df.to_csv(output[0])
