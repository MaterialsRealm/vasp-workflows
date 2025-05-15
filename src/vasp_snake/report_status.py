import json
import os
from collections import Counter
from enum import Enum

import click
import numpy as np
import yaml

from .force import parse_forces_and_check_zero

__all__ = ["classify_folders", "write_status_report"]


class JobStatus(Enum):
    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


def classify_folders(root=".", atol=1e-6):
    details = {}
    for folder in sorted(os.listdir(root)):
        folder_path = os.path.join(root, folder)
        if not os.path.isdir(folder_path) or folder.startswith("."):
            continue
        outcar = os.path.join(folder_path, "OUTCAR")
        if not os.path.exists(outcar):
            forces_sum = [np.nan, np.nan, np.nan]
            job_status = JobStatus.PENDING
            reason = "OUTCAR missing"
        else:
            forces_sum, is_converged = parse_forces_and_check_zero(outcar, atol=atol)
            if forces_sum is None:
                forces_sum = [np.nan, np.nan, np.nan]
                job_status = JobStatus.NOT_CONVERGED
                reason = "No force block found"
            elif is_converged:
                job_status = JobStatus.DONE
                reason = "Forces converged"
            else:
                job_status = JobStatus.NOT_CONVERGED
                reason = (
                    f"Force sum norm {np.linalg.norm(forces_sum):.3g} >= atol {atol}"
                )
            forces_sum = [
                float(f)
                for f in (forces_sum if forces_sum is not None else [np.nan] * 3)
            ]
        details[folder] = {
            "status": job_status.value,
            "forces_sum": forces_sum,
            "reason": reason,
        }
    # Compute summary percentages
    status_list = [v["status"] for v in details.values()]
    total = len(status_list)
    counter = Counter(status_list)
    summary = {
        status: counter.get(status, 0) / total if total else 0.0
        for status in [s.value for s in JobStatus]
    }
    return {"summary": summary, "details": details}


def write_status_report(status_dict, filename):
    # Numpy floats/nans don't serialize well with json/yaml, so convert
    def convert(obj):
        if isinstance(obj, float) and np.isnan(obj):
            return None  # Or "NaN" if you want the string
        if isinstance(obj, (np.generic, np.ndarray)):
            return obj.tolist()
        return obj

    # Recursively convert NaN in all nested structures
    def recursive_convert(o):
        if isinstance(o, dict):
            return {k: recursive_convert(v) for k, v in o.items()}
        elif isinstance(o, list):
            return [recursive_convert(x) for x in o]
        else:
            return convert(o)

    output = recursive_convert(status_dict)
    ext = os.path.splitext(filename)[-1].lower()
    if ext in [".json"]:
        with open(filename, "w") as f:
            json.dump(output, f, indent=2)
    elif ext in [".yaml", ".yml"]:
        with open(filename, "w") as f:
            yaml.dump(output, f, sort_keys=False)
    else:
        raise ValueError(f"Unknown file extension: {ext}")


@click.command()
@click.option(
    "--output",
    default="vasp_status.json",
    help="Output file name (default: vasp_status.json)",
)
@click.option("--folders", default=".", help="Root directory containing folders")
@click.option(
    "--atol",
    default=1e-6,
    type=float,
    show_default=True,
    help="Convergence tolerance for force sum norm",
)
def main(output, folders, atol):
    status = classify_folders(folders, atol=atol)
    write_status_report(status, output)


# Optional: CLI interface
if __name__ == "__main__":
    main()
