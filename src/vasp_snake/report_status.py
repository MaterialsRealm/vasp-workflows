import json
import os
from enum import Enum

import numpy as np

try:
    import yaml
except ImportError:
    yaml = None

from vasp_snake.force import parse_forces_and_check_zero

__all__ = ["classify_folders", "write_status_report"]


class JobStatus(Enum):
    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


def classify_folders(root=".", atol=1e-6):
    status = {}
    for folder in sorted(os.listdir(root)):
        folder_path = os.path.join(root, folder)
        if not os.path.isdir(folder_path) or folder.startswith("."):
            continue
        outcar = os.path.join(folder_path, "OUTCAR")
        if not os.path.exists(outcar):
            forces_sum = [np.nan] * 3
            job_status = JobStatus.PENDING
            reason = "OUTCAR missing"
        else:
            forces_sum, is_converged = parse_forces_and_check_zero(outcar, atol=atol)
            if forces_sum is None:
                forces_sum = [np.nan] * 3
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
        status[folder] = {
            "status": job_status.value,
            "forces_sum": forces_sum,
            "reason": reason,
        }
    return status


def write_status_report(status_dict, filename, out_format="json"):
    if out_format == "json":
        with open(filename, "w") as f:
            json.dump(status_dict, f, indent=2)
    elif out_format == "yaml":
        if yaml is None:
            raise ImportError("pyyaml is required for YAML output.")
        with open(filename, "w") as f:
            yaml.dump(status_dict, f, sort_keys=False)
    else:
        raise ValueError("Unsupported format: {}".format(out_format))


# Optional: CLI interface
if __name__ == "__main__":
    import click

    @click.command()
    @click.option(
        "--format",
        "out_format",
        type=click.Choice(["json", "yaml"], case_sensitive=False),
        default="json",
        help="Output format (json or yaml)",
    )
    @click.option("--output", default=None, help="Output file name (optional)")
    @click.option("--folders", default=".", help="Root directory containing folders")
    @click.option(
        "--atol",
        default=1e-6,
        type=float,
        show_default=True,
        help="Convergence tolerance for force sum norm",
    )
    def main(out_format, output, folders, atol):
        status = classify_folders(folders, atol=atol)
        if output is None:
            output = f"vasp_status.{out_format}"
        write_status_report(status, output, out_format)

    main()
