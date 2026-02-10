import copy
from dataclasses import dataclass

import pandas as pd

__all__ = ["Compound", "FormationEnergy"]


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


class FormationEnergy:
    """Calculates formation energies from calculation results.

    This class provides functionality to calculate formation energies from a collection
    of VASP calculation results, automatically identifying reference energies from
    pure element calculations within the dataset.
    """

    def __init__(self, data: dict | pd.DataFrame):
        """Initialize with calculation data.

        Args:
            data: Input data containing calculation results.
                Can be a dictionary where keys are identifiers and values are dictionaries
                with 'composition', 'F' (total energy), and 'energy per atom'.
                Or a pandas DataFrame with these fields as columns.
        """
        if isinstance(data, dict):
            self._df = pd.DataFrame.from_dict(data, orient="index")
        elif isinstance(data, pd.DataFrame):
            self._df = data.copy()
        else:
            raise TypeError("Input data must be a dict or pandas.DataFrame")

    def calculate(self) -> pd.Series:
        """Calculate formation energies per atom.

        Returns:
            pd.Series: Series of formation energies indexed by the input keys.
                Pure elements are excluded from the results.

        Raises:
            ValueError: If reference energies are missing for any element in a compound.
        """
        # Ensure required columns exist
        required_cols = ["composition", "F", "energy per atom"]
        missing_cols = [c for c in required_cols if c not in self._df.columns]
        if missing_cols:
            return pd.Series(dtype=float)

        # Filter valid rows: composition must be a dict, energies must be present
        valid_mask = (
            self._df["composition"].apply(lambda x: isinstance(x, dict))
            & self._df["F"].notna()
            & self._df["energy per atom"].notna()
        )
        df = self._df[valid_mask].copy()

        if df.empty:
            return pd.Series(dtype=float)

        # Create stoichiometry matrix (rows=compounds, cols=elements)
        stoichiometry = df["composition"].apply(pd.Series).fillna(0)

        # Identify pure elements (rows with exactly one element type)
        n_elements = (stoichiometry > 0).sum(axis=1)
        is_pure = n_elements == 1

        # Calculate reference energies (min energy per atom for each pure element)
        reference_energies = {}
        for element in stoichiometry.columns:
            # Mask for pure 'element'
            pure_mask = is_pure & (stoichiometry[element] > 0)
            if pure_mask.any():
                min_energy = df.loc[pure_mask, "energy per atom"].min()
                reference_energies[element] = min_energy

        # Check for missing reference energies for compounds
        compounds_stoich = stoichiometry[~is_pure]
        if not compounds_stoich.empty:
            # Elements used in compounds
            used_elements_mask = (compounds_stoich > 0).any()
            used_elements = stoichiometry.columns[used_elements_mask]

            missing_refs = set(used_elements) - set(reference_energies.keys())

            if missing_refs:
                # Find the first compound that uses a missing reference
                missing_cols = list(missing_refs)
                bad_rows = compounds_stoich[missing_cols].sum(axis=1) > 0

                if bad_rows.any():
                    first_bad_idx = bad_rows.idxmax()
                    row_stoich = compounds_stoich.loc[first_bad_idx]
                    missing_in_row = [c for c in missing_cols if row_stoich[c] > 0]

                    raise ValueError(
                        f"Missing reference energies for elements: {sorted(missing_in_row)} in folder '{first_bad_idx}'",
                    )

        # Calculate formation energy
        # E_f = (E_total - sum(n_i * E_ref_i)) / sum(n_i)

        # Align reference energies to stoichiometry columns
        ref_vector = pd.Series(reference_energies).reindex(stoichiometry.columns).fillna(0)

        # Calculate sum(n_i * E_ref_i)
        ref_sum = stoichiometry.dot(ref_vector)

        # Calculate sum(n_i)
        total_atoms = stoichiometry.sum(axis=1)

        # Calculate formation energy
        formation_energies = (df["F"] - ref_sum) / total_atoms

        # Return only for compounds
        return formation_energies[~is_pure]


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
