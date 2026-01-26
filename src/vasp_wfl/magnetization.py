from pandas import DataFrame
from pymatgen.io.vasp import Oszicar, Outcar

from .workdir import Workdir, WorkdirProcessor

__all__ = ["MagnetizationParser"]


class MagnetizationParser(WorkdirProcessor):
    """Parse magnetization data from VASP output files.

    Instances provide a single entrypoint `process()` which parses magnetization
    data from a VASP workdir.
    """

    def __init__(self):
        """Initialize the parser."""
        super().__init__()

    @staticmethod
    def from_outcar(file):
        """Return magnetization DataFrame parsed from OUTCAR, or ``None`` on failure.

        Only common I/O and parsing errors are caught and result in ``None``.
        """
        try:
            outcar = Outcar(file)
            data = outcar.magnetization
            if not data:
                return None
            return DataFrame(data)
        except (OSError, ValueError, AttributeError):
            return None

    @staticmethod
    def from_oszicar(file):
        """Return magnetization values parsed from OSZICAR, or ``None`` on failure."""
        try:
            oszicar = Oszicar(file)
            return DataFrame(oszicar.ionic_steps).mag
        except (OSError, ValueError, AttributeError):
            return None

    def process(self, workdir: Workdir, *, sum: bool = False, **kwargs) -> object:
        """Process a workdir and return parsed magnetization data.

        Args:
            workdir: Workdir instance.
            sum: Whether to return the sum of magnetization values. If ``True``, the
                result is obtained by calling ``self.from_outcar(outcar_file).sum()``.
            **kwargs: Ignored.

        Returns:
            A :class:`pandas.DataFrame` or pandas `Series` with magnetization data, a
            scalar when ``sum`` is ``True``, or ``None`` if no suitable file was
            found or parsing failed.
        """
        assert isinstance(workdir, Workdir)
        outcar_file = workdir.path / "OUTCAR"
        if outcar_file.exists():
            df = self.from_outcar(outcar_file)
            if df is None:
                return None
            return df.sum() if sum else df
        oszicar_file = workdir.path / "OSZICAR"
        if oszicar_file.exists():
            return self.from_oszicar(oszicar_file)
        return None
