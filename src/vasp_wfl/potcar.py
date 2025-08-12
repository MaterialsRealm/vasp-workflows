import os

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
            dict: Dictionary mapping element symbols to their POTCAR file paths.

        Raises:
            FileNotFoundError: If POTCAR file for any element is not found.
        """
        potentials = {}
        for element in elements:
            if self.element_pot_map:  # `dict` not empty
                potential_name = self.element_pot_map.get(element, element)
            else:
                potential_name = element
            file = os.path.join(self.potential_dir, potential_name, "POTCAR")
            potentials[element] = file
            if not os.path.isfile(file):
                raise FileNotFoundError(
                    f"POTCAR file for {element} (potential {potential_name}) not found in {file}"
                )
        return potentials

    def concatenate_potcar_content(self, elements):
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
            if not potcar_file or not os.path.exists(potcar_file):
                raise FileNotFoundError(
                    f"POTCAR file for {element} not found: {potcar_file}"
                )
            with open(potcar_file, "r") as f:
                potcar_contents.append(f.read())
        return "".join(potcar_contents)

    def from_file(self, structure_file, output_path):
        """Generate POTCAR from a structure file (CIF or POSCAR), using the instance's element-potential mapping.

        Args:
            structure_file: Path to the structure file (CIF or POSCAR).
            output_path: Path where POTCAR file will be written.
        """
        elements = ElementExtractor.from_file(structure_file)
        symbols = [element.name for element in elements]
        potcar_content = self.concatenate_potcar_content(symbols)

        with open(output_path, "w") as f:
            f.write(potcar_content)

    def from_files(self, files, output_dir=None):
        """Generate POTCAR files for multiple structure files, using the instance's element-potential mapping.

        For each file, generates a POTCAR in the same directory or specified output directory.

        Args:
            files: List of structure file paths (CIF or POSCAR).
            output_dir: Directory to write POTCAR files. If None, writes to same directory as input file.
        """
        for file_path in files:
            if output_dir:
                output_path = os.path.join(output_dir, "POTCAR")
            else:
                file_dir = os.path.dirname(file_path)
                output_path = os.path.join(file_dir, "POTCAR")
            self.from_file(file_path, output_path)
