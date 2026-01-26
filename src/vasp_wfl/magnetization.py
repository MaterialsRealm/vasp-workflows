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

    def process(self, workdir, *args, **kwargs) -> object:
        """Process a workdir and return parsed magnetization data.

        Accept either a :class:`Workdir` or a path-like pointing to a folder.

        Args:
            workdir: Workdir instance or path-like to a VASP working directory.
            *args: Additional positional arguments (ignored).
            **kwargs: Additional keyword arguments (ignored).

        Returns:
            A :class:`pandas.DataFrame` or pandas `Series` with magnetization data, or
            ``None`` if no suitable file was found or parsing failed.
        """
        try:
            wd = Workdir(workdir) if not isinstance(workdir, Workdir) else workdir
        except ValueError:
            # invalid path -> return None to preserve original API behavior
            return None

        outcar_file = wd.path / "OUTCAR"
        if outcar_file.exists():
            return self.from_outcar(outcar_file)
        oszicar_file = wd.path / "OSZICAR"
        if oszicar_file.exists():
            return self.from_oszicar(oszicar_file)
        return None
