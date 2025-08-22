from pathlib import Path

import numpy as np

from .dirs import WorkStatus

__all__ = ["classify_by_force", "parse_forces_and_check_zero"]


def parse_forces_and_check_zero(filename, atol=1e-6):
    """Parse the final `POSITION ... TOTAL-FORCE` block and check force sum.

    Read the file at `filename`, locate the last block that begins with
    a line containing both `POSITION` and `TOTAL-FORCE`, and compute the
    vector sum of the per-atom forces in that block. Determine whether the
    L2 norm of the force-sum is less than `atol`.

    Args:
        filename: Path to the file to read (e.g., an OUTCAR).
        atol: Absolute tolerance used to decide if the force-sum is negligible.

    Returns:
        A tuple `(forces_sum, is_converged)` where `forces_sum` is a length-3
        `numpy.ndarray` with the summed forces and `is_converged` is a
        `bool` indicating whether `||forces_sum||_2 < atol`. If no force block
        is found, returns `(None, None)`.
    """
    with open(filename) as f:
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
    """Classify a VASP calculation's status by inspecting forces in OUTCAR.

    Read the final force block from the OUTCAR file and determine whether the
    vector sum of forces is within the absolute tolerance. The function returns
    a dictionary with a status string (from WorkStatus), the force-sum vector,
    and a human-readable reason.

    Args:
        folder_path: Path to the VASP calculation folder.
        atol: Absolute tolerance for force convergence.

    Returns:
        A dict containing `status`, `forces_sum`, and `reason`.
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
