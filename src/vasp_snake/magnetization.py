from pymatgen.io.vasp import Outcar

__all__ = ["parse_total_magnetization", "parse_last_total_magnetization"]


def parse_total_magnetization(file):
    try:
        outcar = Outcar(file)
        data = outcar.magnetization
        if not data:
            return None
        # Sum the "tot" field for all atoms
        return sum(datum["tot"] for datum in data)
    except Exception:
        return None
