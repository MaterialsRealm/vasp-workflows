from pandas import DataFrame
from pymatgen.io.vasp import Oszicar, Outcar

from .workdir import Workdir

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

    @staticmethod
    def from_dir(workdir: Workdir):
        """Return magnetization information from a `Workdir`.

        Check for `OUTCAR` first and parse it with :meth:`from_outcar`.
        If `OUTCAR` is missing, try `OSZICAR` with :meth:`from_oszicar`.

        Args:
            workdir: A :class:`Workdir` instance or path-like pointing to a folder.

        Returns:
            A :class:`pandas.DataFrame` or pandas Series with magnetization data, or
            ``None`` if no suitable file was found or parsing failed.
        """
        try:
            # accept either Workdir or path-like input
            root = workdir.path
            outcar_file = root / "OUTCAR"
            if outcar_file.exists():
                return MagnetizationParser.from_outcar(outcar_file)
            oszicar_file = root / "OSZICAR"
            if oszicar_file.exists():
                return MagnetizationParser.from_oszicar(oszicar_file)
            return None
        except FileNotFoundError:
            return None
