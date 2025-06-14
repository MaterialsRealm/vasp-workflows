from pymatgen.io.vasp import Oszicar, Outcar

__all__ = ["MagnetizationParser"]


class MagnetizationParser:
    @staticmethod
    def from_outcar(file):
        try:
            outcar = Outcar(file)
            data = outcar.magnetization
            if not data:
                return None
            return sum(datum["tot"] for datum in data)
        except Exception:
            return None

    @staticmethod
    def from_oszicar(file):
        try:
            oszicar = Oszicar(file)
            last_step = oszicar.ionic_steps[-1]
            mag = last_step.get("mag", None)
            return mag
        except Exception:
            return None
