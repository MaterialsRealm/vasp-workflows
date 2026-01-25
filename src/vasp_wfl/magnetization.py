from pandas import DataFrame
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
            return DataFrame(data)
        except Exception:
            return None

    @staticmethod
    def from_oszicar(file):
        try:
            oszicar = Oszicar(file)
            return DataFrame(oszicar.ionic_steps).mag
        except Exception:
            return None
