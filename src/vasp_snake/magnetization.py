import re

__all__ = ["parse_total_magnetization", "parse_last_total_magnetization"]


def parse_total_magnetization(text):
    """
    Parse the total magnetization from the 'tot' column below the dashed line.
    """
    lines = text.strip().splitlines()
    # Find the dashed line that marks the end of per-atom data
    dash_idx = None
    for i, line in enumerate(lines):
        if re.match(r"-{5,}", line):
            dash_idx = i
            break
    if dash_idx is None:
        raise ValueError("No dashed line found in input.")

    # Look for the line that starts with "tot" after the dashed line
    for line in lines[dash_idx + 1 :]:
        if line.strip().startswith("tot"):
            parts = line.split()
            try:
                # "tot" is first entry, the last column is the total
                total_magnetization = float(parts[-1])
                return total_magnetization
            except (IndexError, ValueError):
                raise ValueError(
                    f"Could not parse total magnetization from line: {line}"
                )
    raise ValueError("No 'tot' line found after dashed line.")


def parse_last_total_magnetization(text):
    """
    Parse only the last total magnetization from the 'tot' column below the LAST dashed line.
    """
    lines = text.strip().splitlines()
    # Find indices of all dashed lines
    dash_indices = [i for i, line in enumerate(lines) if re.match(r"-{5,}", line)]
    if not dash_indices:
        raise ValueError("No dashed lines found in input.")

    last_dash_idx = dash_indices[-1]

    # Look for the line starting with "tot" after the last dashed line
    for line in lines[last_dash_idx + 1 :]:
        if line.strip().startswith("tot"):
            parts = line.split()
            try:
                total_magnetization = float(parts[-1])
                return total_magnetization
            except (IndexError, ValueError):
                raise ValueError(
                    f"Could not parse total magnetization from line: {line}"
                )
    raise ValueError("No 'tot' line found after the last dashed line.")
