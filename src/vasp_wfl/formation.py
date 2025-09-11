import copy
from dataclasses import dataclass

import pandas as pd

__all__ = ["Compound", "calculate_formation_energies"]


@dataclass
class Compound:
    """Represents a chemical compound with elements and stoichiometry.

    Attributes:
        elements: Dictionary of elements and their stoichiometric numbers.
    """

    elements: dict[str, float | int]

    def formation_energy(self, energy, component_energies: dict[str, float]) -> float:
        r"""Calculate formation energy per atom.

        The formation energy per atom is calculated as:

        .. math::

            E_f = \frac{E_{\text{total}} - \sum_i n_i E_i}{\sum_i n_i}

        where:
            - :math:`E_f`: formation energy per atom,
            - :math:`E_{\text{total}}`: total energy of the compound,
            - :math:`n_i`: stoichiometric number of element :math:`i`,
            - :math:`E_i`: reference energy per atom of element :math:`i`.

        Args:
            energy: Total energy of the compound.
            component_energies: Reference energies per atom for each element.

        Returns:
            float: Formation energy per atom.
        """
        total_atoms = sum(self.elements.values())
        ref_sum = sum(self.elements[element] * component_energies[element] for element in self.elements)
        return (energy - ref_sum) / total_atoms


def calculate_formation_energies(info: dict) -> dict:
    """Calculate formation energies for compounds in info.

    Args:
        info (dict): Output from ResultCollector.collect().

    Returns:
        dict: Mapping from folder name to formation energy (per atom).

    Raises:
        ValueError: If a compound contains an element not found in reference energies.
    """
    # Collect pure element reference energies
    reference_energies = {}
    for values in info.values():
        composition = values.get("composition")
        energy_per_atom = values.get("energy per atom")
        if not isinstance(composition, dict) or energy_per_atom is None:
            continue
        if len(composition) == 1:
            element = next(iter(composition))
            reference_energies[element] = energy_per_atom
    # Calculate formation energies for compounds
    formation_energies = {}
    for folder, values in info.items():
        composition = values.get("composition")
        energy = values.get("F")
        if not isinstance(composition, dict) or energy is None:
            continue
        # Skip pure elements in this round
        if len(composition) == 1:
            continue
        # Check all elements are present in reference energies
        missing_elements = set(composition).difference(reference_energies)
        if missing_elements:
            error_msg = f"Missing reference energies for elements: {sorted(missing_elements)} in folder '{folder}'"
            raise ValueError(error_msg)
        compound = Compound(composition)
        formation_energy = compound.formation_energy(energy, reference_energies)
        formation_energies[folder] = formation_energy
    return formation_energies


def merge_inner_dicts(info: dict, values: dict, key=None) -> dict:
    """Return a new dict with values from `values` merged into the inner dicts of `info` by key.

    The original `info` is not modified. For each key in `values`, update a copy of the corresponding inner dict in `info` with the value from `values`.
    If the key does not exist in `info`, it is ignored.

    Args:
        info: Dictionary of dictionaries to copy and update.
        values: Dictionary of values to merge into the inner dicts of `info`.
        key: If `values` contains non-dict values, use this as the key for insertion.

    Returns:
        A new dictionary with merged inner dicts.
    """
    result = {k: copy.deepcopy(v) for k, v in info.items()}
    for k, v in values.items():
        if k in result and isinstance(result[k], dict):
            if isinstance(v, dict):
                result[k].update(v)
            elif key is not None:
                result[k][key] = v
    return result


def merge_dfs(df1: pd.DataFrame, df2: pd.DataFrame):
    """Return a new DataFrame with columns from `df2` merged into `df1` by index.

    The original DataFrames are not modified. `df2` should have a single column.
    The column from `df2` is added to `df1` by index alignment.
    If an index is missing in either DataFrame, the result will have NaN for missing values.

    Args:
        df1: DataFrame with multiple columns.
        df2: DataFrame with a single column to merge into `df1`.

    Returns:
        A new DataFrame with columns from both inputs.
    """
    return df1.join(df2)
