# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import patch

import numpy as np
from plotly.graph_objects import Figure

from vasp_wfl import SpglibCell, plot_structure


class PlotStructureTests(unittest.TestCase):
    def setUp(self):
        self.lattice = np.array([[3.0, 0.0, 0.0], [0.4, 4.0, 0.0], [0.2, 0.3, 5.0]])
        self.positions = np.array([[0.2, 0.3, 0.4], [0.6, 0.7, -0.1]])
        self.numbers = np.array([26, 8])
        self.cell = SpglibCell(self.lattice, self.positions, self.numbers, [2.0, -0.2])

    def test_fractional_coordinates_and_species_are_preserved(self):
        with patch("pymatviz.structure_3d") as backend:
            result = plot_structure(self.cell, show_cell=False, atom_size=31)
        structure = backend.call_args.args[0]
        np.testing.assert_allclose(structure.lattice.matrix, self.lattice)
        np.testing.assert_allclose(structure.frac_coords, self.positions)
        np.testing.assert_allclose(structure.cart_coords, self.positions @ self.lattice)
        self.assertEqual([site.specie.symbol for site in structure], ["Fe", "O"])
        self.assertEqual(structure.site_properties["magmom"], [2.0, -0.2])
        self.assertEqual(
            backend.call_args.kwargs,
            {"show_cell": False, "atom_size": 31, "standardize_struct": False},
        )
        self.assertIs(result, backend.return_value)

    def test_raw_tuples_with_and_without_moments(self):
        cell = (self.lattice.tolist(), self.positions.tolist(), self.numbers.tolist())
        for raw_cell in (cell, (*cell, None), (*cell, [1.0, -1.0])):
            with self.subTest(items=len(raw_cell)), patch("pymatviz.structure_3d") as backend:
                plot_structure(raw_cell)
                structure = backend.call_args.args[0]
                if len(raw_cell) == 4 and raw_cell[3] is not None:
                    self.assertEqual(structure.site_properties["magmom"], [1.0, -1.0])
                else:
                    self.assertNotIn("magmom", structure.site_properties)

    def test_type_ids_require_and_use_the_supplied_element_mapping(self):
        raw_cell = (self.lattice, self.positions, [101, 205])
        with self.assertRaisesRegex(ValueError, "supply species"):
            plot_structure(raw_cell)
        with patch("pymatviz.structure_3d") as backend:
            plot_structure(raw_cell, species={101: "Fe", 205: "O"})
        self.assertEqual(
            [site.specie.symbol for site in backend.call_args.args[0]], ["Fe", "O"]
        )
        with self.assertRaisesRegex(ValueError, "missing type IDs"):
            plot_structure(raw_cell, species={101: "Fe"})

    def test_features_override_moments_and_do_not_alias_input(self):
        vectors = np.array([[0.0, 0.0, 2.0], [0.0, 0.0, -0.2]])
        labels = [["first"], ["second"]]
        with patch("pymatviz.structure_3d") as backend:
            plot_structure(
                self.cell,
                {"magmom": vectors, "charge": [1, 2], "labels": labels},
                {"charge": [3, 4]},
            )
        structure = backend.call_args.args[0]
        self.assertEqual(structure.site_properties["charge"], [3, 4])
        np.testing.assert_array_equal(structure.site_properties["magmom"], vectors)
        structure[0].properties["magmom"][2] = 99
        structure[0].properties["labels"][0] = "changed"
        structure.translate_sites([0], [0.1, 0.0, 0.0], to_unit_cell=False)
        self.assertEqual(vectors[0, 2], 2.0)
        self.assertEqual(labels[0], ["first"])
        np.testing.assert_array_equal(self.cell.magmoms, [2.0, -0.2])
        np.testing.assert_array_equal(self.cell.positions, self.positions)

    def test_standardization_can_be_explicitly_enabled(self):
        with patch("pymatviz.structure_3d") as backend:
            plot_structure(self.cell, standardize_struct=True)
        self.assertTrue(backend.call_args.kwargs["standardize_struct"])

    def test_invalid_feature_lengths_and_types_are_rejected(self):
        for values in ([1], 1, np.array(1), "ab"):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "one value per site"):
                plot_structure(self.cell, {"charge": values})
        with self.assertRaisesRegex(TypeError, "must be a mapping"):
            plot_structure(self.cell, [1, 2])
        with self.assertRaisesRegex(TypeError, "names must be strings"):
            plot_structure(self.cell, {1: [1, 2]})

    def test_invalid_cell_geometry_and_species_are_rejected(self):
        invalid_cells = [
            (np.eye(2), self.positions, self.numbers),
            (self.lattice, [[0, 0], [1, 1]], self.numbers),
            (self.lattice, [[np.nan, 0, 0], [1, 1, 1]], self.numbers),
            (self.lattice, self.positions, [26]),
            (self.lattice, self.positions, [26.5, 8.0]),
            (self.lattice, self.positions, [[26], [8]]),
            (self.lattice, self.positions, [0, 119]),
            (self.lattice, np.empty((0, 3)), []),
            (self.lattice, self.positions, self.numbers, [1]),
        ]
        for cell in invalid_cells:
            with self.subTest(cell=cell), self.assertRaises(ValueError):
                plot_structure(cell)
        with self.assertRaises(TypeError):
            plot_structure((self.lattice, self.positions))

    def test_real_backend_renders_vectors_hover_and_standalone_html(self):
        original = self.cell.positions.copy()
        fig = plot_structure(
            self.cell,
            {"forces": [[0.1, 0, 0], [0, 0.2, 0]], "charge": [1.25, -1.25]},
            show_site_vectors="forces",
            vector_kwargs={"forces": {"scale": 0.5}},
            show_image_sites=False,
            show_bonds=True,
            site_labels="species",
        )
        self.assertIsInstance(fig, Figure)
        self.assertTrue(any(trace.type == "cone" for trace in fig.data))
        hover = " ".join(str(getattr(trace, "hovertext", "")) for trace in fig.data)
        self.assertIn("charge", hover)
        self.assertIn("1.25", hover)
        self.assertIn("magmom", hover)
        fig.update_layout(title="Crystal structure", width=900, height=700)
        html = fig.to_html(full_html=True, include_plotlyjs=True)
        self.assertIn("Plotly.newPlot", html)
        self.assertIn("Crystal structure", html)
        np.testing.assert_array_equal(self.cell.positions, original)

    def test_scalar_moments_do_not_invent_a_vector_direction(self):
        fig = plot_structure(self.cell, show_image_sites=False)
        self.assertFalse(any(trace.type == "cone" for trace in fig.data))

    def test_noncollinear_cell_moments_render_as_arrows(self):
        cell = (self.lattice, self.positions, self.numbers, [[0, 0, 2], [0, 0, -0.2]])
        fig = plot_structure(cell, show_image_sites=False, show_site_vectors="magmom")
        self.assertTrue(any(trace.type == "cone" for trace in fig.data))

    def test_unknown_plotting_keyword_is_not_silently_discarded(self):
        with self.assertRaises(TypeError):
            plot_structure(self.cell, misspelled_plot_option=True)


if __name__ == "__main__":
    unittest.main()
