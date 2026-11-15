# SPDX-License-Identifier: GPL-3.0-only
"""Plot crystal structures and per-site properties with pymatviz."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any

import numpy as np
from pymatgen.core import Element, Structure

from .spglib import SpglibCell

if TYPE_CHECKING:
    from plotly.graph_objects import Figure

__all__ = ["plot_structure"]


def plot_structure(
    cell: SpglibCell | tuple,
    *site_features: Mapping[str, Sequence[Any] | np.ndarray],
    species: Mapping[int, str] | None = None,
    **kwargs: Any,
) -> Figure:
    """Return an interactive 3D crystal plot with optional per-atom features.

    Convert fractional coordinates to a pymatgen structure and call
    `pymatviz.structure_3d`. Preserve the input cell and feature arrays. Disable
    structure standardization by default to preserve site order and properties.

    Args:
        cell: A `SpglibCell` or a spglib tuple `(lattice, positions, numbers)`
            with an optional fourth item containing magnetic moments. Lattice
            vectors are rows in angstroms; positions are fractional coordinates.
            Numbers are interpreted as atomic numbers unless `species` is given.
            For `SpglibCell.astuple()`, use `use_identifiers=False` to retain
            atomic numbers, or supply a mapping for the generated type IDs.
        *site_features: Mappings from property names to one value per input site,
            such as `{"forces": forces, "charge": charges}`. Mappings are merged
            left to right; later values replace earlier values, including the
            cell's `"magmom"` property. Scalar properties appear in hover text.
            To draw arrows, provide Cartesian three-component vectors and select
            their name with `show_site_vectors="forces"`. Scalar magnetic moments
            are preserved without assuming a spatial spin direction.
        species: Optional mapping from spglib type IDs to element symbols, such
            as `{1: "Fe", 2: "O"}`. Every type in the cell must be mapped.
        **kwargs: Forward plotting controls to `pymatviz.structure_3d`, including
            `show_cell`, `show_bonds`, `show_image_sites`, `atom_size`,
            `elem_colors`, `site_labels`, `show_site_vectors`, and `vector_kwargs`.
            When several vector names are supplied, pymatviz draws the first
            available field. Set titles, dimensions, and camera using the returned
            figure's `update_layout` method.

    Returns:
        A Plotly figure. Call `show()` to display it or `write_html()` to save an
        interactive plot. The function does not open a viewer or write files.
    """
    # Defer the plotting import because the package imports all public modules.
    from pymatviz import structure_3d

    if isinstance(cell, SpglibCell):
        lattice, positions, numbers, magmoms = (
            cell.lattice, cell.positions, cell.atoms, cell.magmoms
        )
    elif isinstance(cell, tuple) and len(cell) in (3, 4):
        lattice, positions, numbers = cell[:3]
        magmoms = cell[3] if len(cell) == 4 else None
    else:
        raise TypeError("cell must be a SpglibCell or a three- or four-item spglib tuple")

    lattice = np.array(lattice, dtype=float, copy=True)
    positions = np.array(positions, dtype=float, copy=True)
    numbers = np.asarray(numbers)
    if lattice.shape != (3, 3) or not np.isfinite(lattice).all():
        raise ValueError("lattice must be a finite 3x3 array")
    if positions.ndim != 2 or positions.shape[1] != 3 or not np.isfinite(positions).all():
        raise ValueError("positions must be a finite Nx3 array of fractional coordinates")
    n_sites = len(positions)
    if n_sites == 0:
        raise ValueError("cell must contain at least one site")
    if numbers.shape != (n_sites,) or not np.issubdtype(numbers.dtype, np.integer):
        raise ValueError("numbers must contain one integer atomic number or type ID per site")

    if species is None:
        if np.any((numbers < 1) | (numbers > 118)):
            raise ValueError("numbers must be atomic numbers in 1..118; supply species for type IDs")
        elements = [Element.from_Z(int(number)) for number in numbers]
    else:
        missing = set(map(int, numbers)) - species.keys()
        if missing:
            raise ValueError(f"species is missing type IDs: {sorted(missing)}")
        elements = [Element(species[int(number)]) for number in numbers]

    properties = {"magmom": magmoms} if magmoms is not None else {}
    for features in site_features:
        if not isinstance(features, Mapping):
            raise TypeError("each positional site feature argument must be a mapping")
        properties.update(features)
    for name, values in properties.items():
        if not isinstance(name, str):
            raise TypeError("site property names must be strings")
        try:
            valid_length = not isinstance(values, (str, bytes)) and len(values) == n_sites
        except TypeError:
            valid_length = False
        if not valid_length:
            raise ValueError(f"site property {name!r} must contain one value per site ({n_sites})")

    structure = Structure(
        lattice=lattice,
        species=elements,
        coords=positions,
        coords_are_cartesian=False,
        site_properties=deepcopy(properties),
    )
    kwargs.setdefault("standardize_struct", False)
    return structure_3d(structure, **kwargs)
