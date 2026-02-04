from pathlib import Path

from pandas import DataFrame
from pymatgen.io.vasp import Oszicar, Outcar

from .poscar import ElementCounter
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

        The returned DataFrame excludes the `tot` column (if present) and will
        return ``None`` if no orbital columns remain.

        Only common I/O and parsing errors are caught and result in ``None``.
        """
        try:
            outcar = Outcar(file)
            data = outcar.magnetization
            if not data:
                return None
            df = DataFrame(data)
            # Drop the total column if present; keep only orbital columns.
            if "tot" in df.columns:
                df = df.drop(columns=["tot"])
            if df.empty:
                return None
            return df
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

    @staticmethod
    def element_average_magnetization(workdir: Workdir, *, flatten: bool = False):
        """Calculate average magnetization per element.

        Reads structure from CONTCAR/POSCAR and magnetization from OUTCAR.
        Dynamically averages all orbital columns (excluding 'tot').

        Args:
            workdir: Workdir instance.
            flatten: If ``True``, return a 1D series ordered by element then orbital,
                e.g. ``Fe_s, Fe_p, Fe_d, Co_s, ...``. Defaults to ``False``.

        Returns:
            pandas.DataFrame: DataFrame with element index and orbital columns,
            containing average values. Rows are sorted by element occurrence order
            as recorded by `ElementCounter`. If ``flatten`` is ``True``, returns a
            pandas.Series with index labels in element-then-orbital order.
            Returns `None` if files are missing or parsing fails.
        """
        try:
            path = workdir.path
            source = path / "CONTCAR" if (path / "CONTCAR").exists() else path / "POSCAR"
            if not source.exists() or not (outcar := path / "OUTCAR").exists():
                return None

            counts = ElementCounter.from_file(source)
            # Reconstruct atom list assuming VASP block order preserved in ElementCounter
            atom_labels = []
            for element, count in counts.items():
                atom_labels.extend([element.symbol] * count)
            mag = MagnetizationParser.from_outcar(outcar)
            if mag is None or len(mag) != len(atom_labels):
                return None

            mag["element"] = atom_labels
            cols = [col for col in mag.columns if col not in {"tot", "element"}]

            if not cols:
                return None

            df = mag.groupby("element")[cols].mean()
            # Use the insertion order of ElementCounter keys for the index
            df = df.reindex([element.symbol for element in counts])
            if not flatten:
                return df

            # Flatten to a 1D series in element-then-orbital order.
            values = []
            labels = []
            for element in df.index:
                for col in cols:
                    labels.append(f"{element}_{col}")
                    values.append(df.loc[element, col])
            return DataFrame(values, index=labels).iloc[:, 0]
        except Exception:  # FIXME: Not all files have the same order of Fe-Co-S
            return None

    @staticmethod
    def element_total_magnetization(workdir: Workdir, *, flatten: bool = False):
        """Calculate total magnetization per element.

        Reads structure from CONTCAR/POSCAR and magnetization from OUTCAR.
        Dynamically sums all orbital columns (excluding 'tot').

        Args:
            workdir: Workdir instance.
            flatten: If ``True``, return a 1D series ordered by element then orbital,
                e.g. ``Fe_s, Fe_p, Fe_d, Co_s, ...``. Defaults to ``False``.

        Returns:
            pandas.DataFrame: DataFrame with element index and orbital columns,
            containing summed values. Rows are sorted by element occurrence order
            as recorded by `ElementCounter`. If ``flatten`` is ``True``, returns a
            pandas.Series with index labels in element-then-orbital order.
            Returns `None` if files are missing or parsing fails.
        """
        try:
            path = workdir.path
            source = path / "CONTCAR" if (path / "CONTCAR").exists() else path / "POSCAR"
            if not source.exists() or not (outcar := path / "OUTCAR").exists():
                return None

            counts = ElementCounter.from_file(source)
            # Reconstruct atom list assuming VASP block order preserved in ElementCounter
            atom_labels = []
            for element, count in counts.items():
                atom_labels.extend([element.symbol] * count)

            mag = MagnetizationParser.from_outcar(outcar)
            if mag is None or len(mag) != len(atom_labels):
                return None

            mag["element"] = atom_labels
            cols = [col for col in mag.columns if col not in {"tot", "element"}]

            if not cols:
                return None

            df = mag.groupby("element")[cols].sum()
            df = df.reindex([element.symbol for element in counts])
            if not flatten:
                return df

            values = []
            labels = []
            for element in df.index:
                for col in cols:
                    labels.append(f"{element}_{col}")
                    values.append(df.loc[element, col])
            return DataFrame(values, index=labels).iloc[:, 0]
        except Exception:
            return None

    @staticmethod
    def to_csv(
        rootdir,
        orbitals=("s", "p", "d"),
        element_order=None,
        output=None,
    ):
        """Aggregate element-average magnetization across subfolders into a CSV-ready table.

        Iterates immediate subdirectories of ``rootdir`` and computes element-average
        magnetization for each. Rows are indexed by the subdirectory name (base name).

        Args:
            rootdir: Root directory containing subfolders with VASP outputs.
            orbitals: Orbital column order to stack per element (default: s, p, d).
            element_order: Optional explicit element order (e.g., ["Fe", "Co", "S"]).
                If None, uses the element order from the first valid workdir.
            output: Optional path to write the CSV. If None, only returns DataFrame.

        Returns:
            pandas.DataFrame with rows per subfolder and columns ordered by
            element then orbital, e.g. ``Fe_s, Fe_p, Fe_d, Co_s, ...``.
        """
        root = Path(rootdir).expanduser().resolve()
        rows = {}
        col_order = None

        for sub in sorted([p for p in root.iterdir() if p.is_dir()]):
            try:
                wd = Workdir(sub)
            except ValueError:
                rows[sub.name] = {}
                continue

            df = MagnetizationParser.element_average_magnetization(wd, flatten=False)
            if df is None or df.empty:
                rows[sub.name] = {}
                continue

            elements = list(element_order) if element_order is not None else list(df.index)
            if col_order is None:
                col_order = [f"{el}_{orb}" for el in elements for orb in orbitals]

            row = {}
            for el in elements:
                for orb in orbitals:
                    col = f"{el}_{orb}"
                    if el in df.index and orb in df.columns:
                        row[col] = df.loc[el, orb]
                    else:
                        row[col] = float("nan")

            rows[sub.name] = row

        result = DataFrame.from_dict(rows, orient="index")
        if col_order is None:
            col_order = []
        extras = [c for c in result.columns if c not in col_order]
        result = result.reindex(columns=col_order + extras)

        if output is not None:
            output_path = Path(output).expanduser()
            result.to_csv(output_path, index=True)

        return result

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
