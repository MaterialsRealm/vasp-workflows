import os
from collections import Counter
from enum import StrEnum

import numpy as np

from .force import parse_forces_and_check_zero

__all__ = ["JobStatus", "FolderClassifier"]


class JobStatus(StrEnum):
    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


class FolderClassifier:
    def __init__(self, details):
        self._details = details

    @classmethod
    def from_directory(cls, root=".", atol=1e-6):
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
                forces_sum, is_converged = parse_forces_and_check_zero(
                    outcar, atol=atol
                )
                if forces_sum is None:
                    forces_sum = [np.nan, np.nan, np.nan]
                    job_status = JobStatus.NOT_CONVERGED
                    reason = "No force block found"
                elif is_converged:
                    job_status = JobStatus.DONE
                    reason = "Forces converged"
                else:
                    job_status = JobStatus.NOT_CONVERGED
                    reason = f"Force sum norm {np.linalg.norm(forces_sum):.3g} >= atol {atol}"
                forces_sum = [
                    float(f)
                    for f in (forces_sum if forces_sum is not None else [np.nan] * 3)
                ]
            details[folder] = {
                "status": job_status.value,
                "forces_sum": forces_sum,
                "reason": reason,
            }
        return cls(details)

    @property
    def summary(self):
        status_list = [v["status"] for v in self._details.values()]
        total = len(status_list)
        counter = Counter(status_list)
        return {
            status: counter.get(status, 0) / total if total else 0.0
            for status in [s.value for s in JobStatus]
        }

    @property
    def details(self):
        return self._details
