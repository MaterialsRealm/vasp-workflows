import os
import numpy as np
import shutil
import yaml
import json

# Configurable filename
report_file = config.get("report_file", "report_status.yaml")
report_ext = os.path.splitext(report_file)[1].lower()

assert report_ext in [
    ".yaml",
    ".yml",
    ".json",
], "report_file must end with .yaml, .yml, or .json"


def parse_forces_and_check_zero(filename):
    with open(filename, "r") as f:
        lines = f.readlines()

    results = []
    i = 0
    while i < len(lines):
        if "POSITION" in lines[i] and "TOTAL-FORCE" in lines[i]:
            start = i + 2
            end = start
            while end < len(lines) and "total drift" not in lines[end]:
                end += 1

            forces = []
            for line in lines[start:end]:
                if line.strip() == "" or "---" in line:
                    continue
                parts = line.split()
                force = list(map(float, parts[3:6]))
                forces.append(force)

            forces = np.array(forces)
            forces_sum = np.sum(forces, axis=0)

            match = np.allclose(forces_sum, [0.0, 0.0, 0.0], atol=1e-6)

            results.append((forces_sum, match))

            i = end + 1
        else:
            i += 1

    return results


def classify_folders():
    """Classify folders into not_run, not_converged, good."""
    not_run = []
    not_converged = []
    good = []

    for folder in next(os.walk("."))[1]:
        if folder.startswith("."):
            continue
        outcar_path = os.path.join(folder, "OUTCAR")

        if not os.path.exists(outcar_path):
            not_run.append(folder)
        else:
            try:
                force_checks = parse_forces_and_check_zero(outcar_path)
                if not force_checks:
                    not_converged.append(folder)
                else:
                    last_forces_sum, match = force_checks[-1]
                    if not match:
                        not_converged.append(folder)
                    else:
                        good.append(folder)
            except Exception as e:
                print(
                    f"{folder}: Error parsing OUTCAR ({e}), treating as not converged."
                )
                not_converged.append(folder)

    return not_run, not_converged, good


def find_folders():
    """Return folders that need rerun (not_run + not_converged)."""
    not_run, not_converged, _ = classify_folders()
    return not_run + not_converged


rule all:
    input:
        expand("{folder}/done.txt", folder=find_folders()),
        report_file,


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


rule report_status:
    output:
        report_file,
    run:
        not_run, not_converged, good = classify_folders()

        report_data = {
            "not_run": sorted(not_run),
            "not_converged": sorted(not_converged),
            "finished": sorted(good),
        }

        if report_ext in [".yaml", ".yml"]:
            with open(output[0], "w") as f:
                yaml.dump(report_data, f, default_flow_style=False)
        elif report_ext == ".json":
            with open(output[0], "w") as f:
                json.dump(report_data, f, indent=4)

        print(f"\nReport generated: {output[0]}")
        print(f"  {len(not_run)} folders not run.")
        print(f"  {len(not_converged)} folders not converged.")
        print(f"  {len(good)} folders finished successfully.")
