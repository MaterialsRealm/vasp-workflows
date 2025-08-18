from pathlib import Path

import numpy as np

from .dirs import WorkStatus

__all__ = ["parse_forces_and_check_zero"]


def parse_forces_and_check_zero(filename, atol=1e-6):
    with open(filename, "r") as f:
        lines = f.readlines()

    last_forces_sum = None
    last_is_converged = None

    i = 0
    while i < len(lines):
        if "POSITION" in lines[i] and "TOTAL-FORCE" in lines[i]:
            start = i + 2  # Skip header and dashed line
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
            is_converged = np.linalg.norm(forces_sum) < atol

            last_forces_sum = forces_sum
            last_is_converged = is_converged
            i = end + 1
        else:
            i += 1

    # None if never found any block
    if last_forces_sum is None:
        return None, None
    return last_forces_sum, last_is_converged


def classify_by_force(folder_path, atol: float = 1e-6) -> dict:
    """Default classification function for VASP calculation status.

    Args:
        folder_path (str): Path to the VASP calculation folder.
        atol (float): Absolute tolerance for force convergence.
        **kwargs: Additional keyword arguments (unused in default classifier).

    Returns:
        dict: Dictionary with at least 'status' key, and optionally other keys like
              'forces_sum', 'reason', etc.
    """
    outcar = Path(folder_path) / "OUTCAR"
    if not outcar.exists():
        forces_sum = [np.nan, np.nan, np.nan]
        job_status = WorkStatus.PENDING
        reason = "OUTCAR missing"
    else:
        forces_sum, is_converged = parse_forces_and_check_zero(outcar, atol=atol)
        if forces_sum is None:
            forces_sum = [np.nan, np.nan, np.nan]
            job_status = WorkStatus.NOT_CONVERGED
            reason = "No force block found"
        elif is_converged:
            job_status = WorkStatus.DONE
            reason = "Forces converged"
        else:
            job_status = WorkStatus.NOT_CONVERGED
            reason = f"Force sum norm {np.linalg.norm(forces_sum):.3g} >= atol {atol}"
        forces_sum = [float(f) for f in (forces_sum if forces_sum is not None else [np.nan] * 3)]

    return {
        "status": job_status.value,
        "forces_sum": forces_sum,
        "reason": reason,
    }
