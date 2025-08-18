from pathlib import Path

import numpy as np

from .dirs import WorkStatus
from .force import parse_forces_and_check_zero

__all__ = ["classify_by_force"]


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
