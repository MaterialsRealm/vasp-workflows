# VASP workflows

This repo contains some of the workflows code I used during research.

## Crystal structure plotting

`plot_structure` uses [pymatviz](https://pymatviz.janosh.dev/), a materials
visualization library with crystal-aware atom, unit-cell, bond, and vector
rendering. It returns an interactive Plotly figure that can be rotated and
exported to standalone HTML. Install the project's dependencies with `uv sync`.

```python
from vasp_wfl import plot_structure

# cell is an existing SpglibCell or a spglib tuple:
# (lattice, fractional_positions, atomic_numbers[, magnetic_moments])
fig = plot_structure(
    cell,
    {"forces": forces},        # one Cartesian three-component vector per atom
    {"charge": charges},       # one scalar per atom, included in hover text
    show_site_vectors="forces",
    vector_kwargs={"forces": {"scale": 0.5}},
    show_cell=True,
    show_bonds=True,
    show_image_sites=False,
    atom_size=25,
)
fig.update_layout(title="Crystal structure", width=900, height=700)
fig.show()
fig.write_html("structure.html")
```

Additional positional arguments are mappings of per-atom property names to
values in the input site order. Later mappings override earlier properties,
including magnetic moments copied from the cell under `"magmom"`. Input arrays
are not modified. The wrapper defaults to `standardize_struct=False` to preserve
site order and the supplied cell; this can be overridden explicitly.

Raw spglib type IDs do not necessarily identify chemical elements. The wrapper
interprets them as atomic numbers by default. If they are arbitrary identifiers,
provide the element mapping explicitly:

```python
fig = plot_structure(
    (lattice, fractional_positions, type_ids),
    species={1: "Fe", 2: "O"},
)
```

Pass a `SpglibCell` directly, or call `cell.astuple(use_identifiers=False)` to
retain its atomic numbers. The default `cell.astuple()` renumbers species and
therefore needs a matching `species` mapping.

Scalar magnetic moments remain scalar properties; no spin direction is assumed.
For magnetic arrows, pass Cartesian vectors under `"magmom"` and use
`show_site_vectors="magmom"`. Pymatviz displays the first available vector field
when several names are requested. Other keyword arguments are forwarded to
[`pymatviz.structure_3d`](https://pymatviz.janosh.dev/api); Plotly layout options
such as title, size, and camera belong in `fig.update_layout(...)`.

For PDF export, `fig.write_image("structure.pdf")` requires the optional
Kaleido package and, with Kaleido 1 or later, Chrome/Chromium. Plotly's 3D content
is rasterized inside the PDF; HTML preserves the interactive view. See the
[Plotly export documentation](https://plotly.com/python/static-image-export/).
