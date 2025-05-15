import os
from glob import glob
from pymatgen.io.vasp import Oszicar
import shutil

# Threshold for convergence
threshold = 0.001


def find_folders():
    """Find folders needing rerun, skipping .snakemake and other system dirs."""
    folders = []
    for folder in next(os.walk("."))[1]:
        if folder.startswith("."):
            continue  # Skip .snakemake, .venv, etc.
        outcar_path = os.path.join(folder, "OUTCAR")
        oszicar_path = os.path.join(folder, "OSZICAR")

        rerun = False
        if not os.path.exists(outcar_path):
            print(f"{folder}: OUTCAR missing, needs rerun.")
            rerun = True
        elif os.path.exists(oszicar_path):
            try:
                osz = Oszicar(oszicar_path)
                if not osz.ionic_steps:
                    raise ValueError("No ionic steps")
                last_step = osz.ionic_steps[-1]
                dE = last_step["dE"]
                if abs(dE) >= threshold:
                    print(f"{folder}: |dE|={abs(dE)} >= {threshold}, needs rerun.")
                    rerun = True
                else:
                    print(f"{folder}: |dE|={abs(dE)} < {threshold}, OK.")
            except Exception as e:
                print(f"{folder}: OSZICAR read error ({e}), needs rerun.")
                rerun = True
        else:
            print(f"{folder}: No OSZICAR, needs rerun.")
            rerun = True

        if rerun:
            folders.append(folder)
    return folders


rule all:
    input:
        expand("{folder}/done.txt", folder=find_folders()),


rule link_and_run:
    input:
        poscar="{folder}/POSCAR",
        incar="INCAR",
        potcar="POTCAR",
        runsh="run.sh",
    output:
        done="{folder}/done.txt",
    params:
        folder="{folder}",
    shell:
        """
        cd {params.folder}
        ln -sf ../INCAR .
        ln -sf ../POTCAR .
        ln -sf ../run.sh .
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
