import os

from .poscar import ElementCounter
from .templating import TemplateModifier

__all__ = ["update_incar_templates"]


def update_incar_templates(template_str, dirs):
    """Update INCAR files in the provided VASP working directories by rendering and applying
    a dynamic template for SYSTEM and MAGMOM based on POSCAR element counts.

    Args:
        dirs: List of VASP working directory paths.
        mode: Modification mode ('append' or 'overwrite') for the target INCAR file.

    Returns:
        set: Set of directories where the INCAR was successfully modified.
    """
    modifier = TemplateModifier(template_str, "INCAR")
    successful_dirs = set()
    for dir in dirs:
        poscar_path = os.path.join(dir, "POSCAR")
        if not os.path.exists(poscar_path):
            logger.warning(f"POSCAR not found in directory '{dir}'. Skipping.")
            continue

        counter = ElementCounter.from_file(poscar_path)
        system_name = os.path.basename(dir)
        magmoms = counter.values()
        variables = {"system_name": system_name, "magmoms": magmoms}
        if modifier.render_modify(dir, variables, "overwrite"):
            successful_dirs.add(dir)

    return successful_dirs
