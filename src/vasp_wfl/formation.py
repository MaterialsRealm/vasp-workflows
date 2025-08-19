from dataclasses import dataclass

__all__ = ["Compound"]


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
