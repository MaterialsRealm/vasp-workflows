"""Parse energy data from VASP OUTCAR files."""

from pathlib import Path

from pymatgen.io.vasp import Outcar

from .workdir import Workdir

__all__ = ["EnergyParser"]


class EnergyParser:
    """Parse final free energy from VASP OUTCAR files."""

    @staticmethod
    def from_outcar(outcar_path):
        """Parse final free energy from an OUTCAR file.

        Args:
            outcar_path: Path to OUTCAR file (str or Path).

        Returns:
            float: Final free energy in eV, or None if parsing fails.
        """
        outcar_path = Path(outcar_path)
        if not outcar_path.exists():
            return None
        try:
            return Outcar(str(outcar_path)).final_fr_energy
        except (OSError, ValueError, AttributeError, KeyError):
            return None

    @staticmethod
    def __call__(workdir):
        """Parse energy from a Workdir's OUTCAR.

        Args:
            workdir: Workdir instance.
            **kwargs: Ignored (for compatibility with WorkdirProcessor).

        Returns:
            float: Final free energy in eV, or None if parsing fails.
        """
        assert isinstance(workdir, Workdir)
        outcar_path = workdir.path / "OUTCAR"
        return EnergyParser.from_outcar(outcar_path)
