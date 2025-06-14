import numpy as np


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
