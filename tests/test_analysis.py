import tempfile
import unittest
from pathlib import Path

import geopandas as gpd

from gis_analysis import (
    DATA_PATH,
    build_summary_table,
    create_interactive_map,
    load_boroughs,
    write_outputs,
)


class BoroughAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gdf = load_boroughs(DATA_PATH)

    def test_five_boroughs_in_projected_crs(self):
        self.assertEqual(len(self.gdf), 5)
        self.assertEqual(self.gdf.crs.to_epsg(), 2263)
        self.assertIn("Brooklyn", self.gdf.index)
        self.assertIn("Staten Island", self.gdf.index)

    def test_area_values_match_known_boroughs(self):
        self.assertAlmostEqual(self.gdf.loc["Queens", "area_sqkm"], 282.91, places=1)
        self.assertAlmostEqual(self.gdf.loc["Brooklyn", "area_sqkm"], 180.0, places=1)
        self.assertAlmostEqual(self.gdf.loc["Manhattan", "area_sqkm"], 59.13, places=1)
        self.assertGreater(
            self.gdf.loc["Queens", "area_sqkm"],
            self.gdf.loc["Bronx", "area_sqkm"],
        )

    def test_distance_and_density_columns(self):
        self.assertEqual(self.gdf.loc["Brooklyn", "distance_to_brooklyn_km"], 0)
        self.assertGreater(
            self.gdf.loc["Bronx", "distance_to_brooklyn_km"], 20
        )
        self.assertGreater(
            self.gdf.loc["Manhattan", "density_per_sqkm"], 25_000
        )
        self.assertGreater(self.gdf.loc["Manhattan", "convex_hull_ratio"], 1)

    def test_summary_table_is_sorted_and_complete(self):
        summary = build_summary_table(self.gdf)
        self.assertEqual(summary.index[0], "Queens")
        self.assertEqual(summary.index[-1], "Manhattan")
        self.assertIn("density_per_sqkm", summary.columns)
        self.assertIn("buffer_intersects_brooklyn", summary.columns)
        self.assertEqual(len(summary), 5)

    def test_buffer_flags(self):
        self.assertTrue(self.gdf.loc["Queens", "buffered_intersects_brooklyn"])
        self.assertFalse(self.gdf.loc["Bronx", "buffered_intersects_brooklyn"])
        self.assertFalse(self.gdf.loc["Brooklyn", "within"])

    def test_write_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = write_outputs(self.gdf, Path(directory))
            self.assertTrue(paths["csv"].exists())
            self.assertTrue(paths["figure"].exists())
            self.assertTrue(paths["geojson"].exists())
            self.assertGreater(paths["csv"].stat().st_size, 100)
            self.assertGreater(paths["figure"].stat().st_size, 10_000)
            exported = gpd.read_file(paths["geojson"])
            self.assertEqual(len(exported), 5)

    def test_interactive_map_contains_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "map.html"
            create_interactive_map(self.gdf, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("Borough area", text)
            self.assertIn("Convex hull", text)
            self.assertIn("Centroid distance", text)


if __name__ == "__main__":
    unittest.main()
