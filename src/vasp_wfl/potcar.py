from collections import OrderedDict
from pathlib import Path

from .poscar import ElementExtractor

__all__ = ["PotcarGenerator"]


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

    def from_files(self, files, output_dir=None):
        """Generate POTCAR files for multiple structure files, using the instance's element-potential mapping.

        For each file, generates a POTCAR in the same directory or specified output directory.

        Args:
            files: List of structure file paths (CIF or POSCAR).
            output_dir: Directory to write POTCAR files. If None, writes to same directory as input file.
        """
        for file_path in files:
            output_path = Path(output_dir) / "POTCAR" if output_dir else Path(file_path).parent / "POTCAR"
            self.from_file(file_path, output_path)
