import json
import os
from collections import Counter
from enum import StrEnum

import numpy as np
import yaml

from .force import parse_forces_and_check_zero

__all__ = ["JobStatus", "FolderClassifier"]


class JobStatus(StrEnum):
    """Enumeration of possible job statuses for VASP calculations."""

    PENDING = "PENDING"
    DONE = "DONE"
    NOT_CONVERGED = "NOT_CONVERGED"


class FolderClassifier:
    """Classifies VASP calculation folders by job status and provides summary and filtering utilities."""

    def __init__(self, details):
        """
        Args:
            details (dict): Dictionary mapping folder names to job status details.
        """
        self._details = details

    @classmethod
    def from_directory(cls, root=".", atol=1e-6):
        """
        Scan a directory for VASP calculation folders and classify their job status.

        Args:
            root (str): Root directory to scan. Defaults to current directory.
            atol (float): Absolute tolerance for force convergence. Defaults to 1e-6.

        Returns:
            FolderClassifier: An instance with details populated from the directory.
        """
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
        """
        Compute the fraction of jobs in each status.

        Returns:
            dict: Mapping of job status to fraction of jobs in that status.
        """
        status_list = [v["status"] for v in self._details.values()]
        total = len(status_list)
        counter = Counter(status_list)
        return {
            status: counter.get(status, 0) / total if total else 0.0
            for status in [s.value for s in JobStatus]
        }

    @property
    def details(self):
        """
        Get the raw details dictionary.

        Returns:
            dict: Folder details with job status, force sum, and reason.
        """
        return self._details

    def list_pending(self):
        """
        List folders with PENDING status.

        Returns:
            list: Folder names with status PENDING.
        """
        return [k for k, v in self.details.items() if v["status"] == JobStatus.PENDING]

    def list_done(self):
        """
        List folders with DONE status.

        Returns:
            list: Folder names with status DONE.
        """
        return [k for k, v in self.details.items() if v["status"] == JobStatus.DONE]

    def list_incomplete(self):
        """
        List folders with NOT_CONVERGED status.

        Returns:
            list: Folder names with status NOT_CONVERGED.
        """
        return [
            k for k, v in self.details.items() if v["status"] == JobStatus.NOT_CONVERGED
        ]

    def dumps_status(self, format="json"):
        """
        Dump the folder status (only folder name and status) in JSON or YAML format as a string.

        Args:
            format (str): Output format, either 'json' or 'yaml'. Defaults to 'json'.

        Returns:
            str: The folder-to-status mapping serialized in the requested format.

        Raises:
            ValueError: If the format is not 'json' or 'yaml'.
        """
        status_map = {k: v["status"] for k, v in self.details.items()}
        if format == "json":
            return json.dumps(status_map, indent=2)
        elif format == "yaml":
            return yaml.dump(status_map, sort_keys=False)
        else:
            raise ValueError("Format must be 'json' or 'yaml'.")
