import numpy as np


__all__ = ["parse_forces_and_check_zero"]


def parse_forces_and_check_zero(filename):
    with open(filename, "r") as f:
        lines = f.readlines()

    last_forces_sum = None
    last_forces_close = None

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
            match = np.allclose(forces_sum, [0.0, 0.0, 0.0], atol=1e-6)

            last_forces_sum = forces_sum
            last_forces_close = match

            i = end + 1
        else:
            i += 1

    # If we found no force block, treat as not converged
    return last_forces_sum, last_forces_close
