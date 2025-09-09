from collections import OrderedDict
from pathlib import Path

from pymatgen.io.vasp import Potcar

from .poscar import ElementExtractor
from .workdir import WorkdirFinder

__all__ = ["PotcarGenerator", "PotcarValidator"]


class PotcarGenerator:
    """Class for generating POTCAR files from structure files."""

    def __init__(self, potential_dir, element_pot_map=None):
        """Initialize PotcarGenerator with potential directory and optional element-potential mapping.

        Args:
            potential_dir: Root directory path containing potential subdirectories.
            element_pot_map: Optional dict mapping element symbols to potential names (e.g., {"Si": "Si_GW", "O": "O_s"}).
        """
        self.potential_dir = potential_dir
        self.element_pot_map = element_pot_map

    def locate_potcars(self, elements):
        """Locate POTCAR file paths for given elements using the instance's element-potential mapping.

        Args:
            elements: Set of element names to locate POTCAR files for.

        Returns:
            OrderedDict: A mapping of element symbols to their POTCAR file paths.

        Raises:
            FileNotFoundError: If POTCAR file for any element is not found.
        """
        potentials = OrderedDict()
        for element in elements:
            potential_name = self.element_pot_map.get(element, element) if self.element_pot_map else element
            file = Path(self.potential_dir) / potential_name / "POTCAR"
            potentials[element] = file
            if not file.is_file():
                msg = f"POTCAR file for {element} (potential {potential_name}) not found in {file}"
                raise FileNotFoundError(msg)
        return potentials

    def concat_potcars(self, elements):
        """Concatenate POTCAR files for given elements using the instance's element-potential mapping.

        Args:
            elements: List of element symbols in order.

        Returns:
            str: Concatenated POTCAR content as a string.

        Raises:
            FileNotFoundError: If POTCAR file for any element is not found.
        """
        potcar_map = self.locate_potcars(elements)
        potcar_contents = []
        for element in elements:
            potcar_file = potcar_map.get(element)
            if not potcar_file or not Path(potcar_file).exists():
                msg = f"POTCAR file for {element} not found: {potcar_file}"
                raise FileNotFoundError(msg)
            potcar_contents.append(Path(potcar_file).read_text(encoding="ascii"))
        return "".join(potcar_contents)

    def from_file(self, file, output_path=None):
        """Generate POTCAR from a structure file (CIF or POSCAR), using the instance's element-potential mapping.

        Args:
            file: Path to the structure file (CIF or POSCAR).
            output_path: Path where POTCAR file will be written. If `None`, writes to same directory as input file.
        """
        elements = ElementExtractor.from_file(file)
        symbols = [element.name for element in elements]
        potcar_content = self.concat_potcars(symbols)
        output_path = Path(file).parent / "POTCAR" if not output_path else Path(output_path)
        output_path.write_text(potcar_content, encoding="utf-8")

    def from_files(self, files):
        """Generate POTCAR files for multiple structure files, using the instance's element-potential mapping.

        For each file, generates a POTCAR in the same directory as the input file.

        Args:
            files: List of structure file paths (CIF or POSCAR).
        """
        for file_path in files:
            output_path = Path(file_path).parent / "POTCAR"
            self.from_file(file_path, output_path)


class PotcarValidator:
    """Class for validating POTCAR files against structure files."""

    @classmethod
    def validate(cls, potcar_file, poscar_file):
        """Validate that POTCAR symbols match and are in the same order as elements in a POSCAR file.

        Args:
            potcar_file: Path to the `POTCAR` file.
            poscar_file: Path to the `POSCAR`/structure file.

        Returns:
            bool: `True` if the POTCAR symbols match the POSCAR elements, `False` otherwise.
        """
        poscar_elements = ElementExtractor.from_file(poscar_file)
        symbols_from_poscar = [element.name for element in poscar_elements]
        # Potcar.from_file can read concatenated POTCAR files.
        # The .symbols attribute returns a list of element symbols in order.
        potcar = Potcar.from_file(potcar_file)
        symbols_from_potcar = potcar.symbols
        return symbols_from_poscar == symbols_from_potcar

    @classmethod
    def validate_batch(cls, potcar_files, poscar_files):
        """Validate that each POTCAR in a list matches the corresponding POSCAR.

        Args:
            potcar_files (list): A list of paths to POTCAR files.
            poscar_files (list): A list of paths to POSCAR files.

        Returns:
            bool: `True` if all pairs are valid, `False` otherwise.

        Raises:
            ValueError: If the lists of files have different lengths.
        """
        if len(potcar_files) != len(poscar_files):
            msg = f"The number of POTCAR files ({len(potcar_files)}) and POSCAR files ({len(poscar_files)}) must equal."
            raise ValueError(msg)

        return all(map(cls.validate, potcar_files, poscar_files))

    @classmethod
    def validate_from_root(cls, root_dir, **kwargs):
        """Find and validate all POTCAR/POSCAR pairs in subdirectories.

        Args:
            root_dir (str or Path): The root directory to start the search from.
            **kwargs: Keyword arguments passed to `WorkdirFinder.find`.

        Returns:
            bool: `True` if all found POTCAR/POSCAR pairs are valid. Returns `True` if no
                  such pairs are found. Returns `False` if any pair is invalid.
        """
        workdirs = WorkdirFinder(**kwargs).find(root_dir)
        pairs_to_check = []
        for workdir_str in workdirs:
            workdir = Path(workdir_str)
            potcar_path = workdir / "POTCAR"
            poscar_path = workdir / "POSCAR"
            if potcar_path.exists() and poscar_path.exists():
                pairs_to_check.append((potcar_path, poscar_path))

        if not pairs_to_check:
            return True

        potcars, poscars = zip(*pairs_to_check, strict=True)
        return cls.validate_batch(list(potcars), list(poscars))
