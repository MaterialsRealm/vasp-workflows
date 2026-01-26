from pandas import DataFrame
from pymatgen.io.vasp import Oszicar, Outcar

from .workdir import Workdir
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    @staticmethod
    def from_dirs(dirs, max_workers: int | None = 1, return_mapping: bool = False):
        """Parse magnetization information from multiple directories in parallel.

        Args:
            dirs: Iterable of directory paths or :class:`Workdir` instances.
            max_workers: Number of worker threads to use. If ``None`` or ``<= 1`` parsing
                is performed sequentially. Defaults to 8.
            return_mapping: If True return ``{Workdir: result}``, otherwise return a
                list of results in the same order as ``dirs``.

        Returns:
            dict or list: Parsed magnetization data.
        """
        dirs_list = list(dirs)
        workdirs = []
        for d in dirs_list:
            try:
                workdirs.append(Workdir(d))
            except ValueError:
                # invalid workdir -> preserve order with None
                workdirs.append(None)

        # Sequential path
        if not max_workers or max_workers <= 1:
            results = [MagnetizationParser.from_dir(wd) if wd is not None else None for wd in workdirs]
            if return_mapping:
                return dict(zip(workdirs, results))
            return results

        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(MagnetizationParser.from_dir, wd): wd for wd in workdirs if wd is not None}
            for fut in as_completed(futures):
                wd = futures[fut]
                exc = fut.exception()
                if exc is not None:
                    results[wd] = None
                else:
                    results[wd] = fut.result()
        # include invalid (None) entries with None result
        if return_mapping:
            for wd in workdirs:
                if wd is None and wd not in results:
                    results[wd] = None
            return results
        return [results.get(wd) for wd in workdirs]
