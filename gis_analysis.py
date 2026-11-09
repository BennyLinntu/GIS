"""New York City borough analysis with GeoPandas, Matplotlib and Folium.

Run:
    python gis_analysis.py
    python gis_analysis.py --open-browser --show-plots
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parent
DATA_PATH = WORKSPACE / "data" / "nyc_boroughs.geojson"
DEFAULT_OUTPUT = WORKSPACE
FEET_TO_KM = 0.0003048
SQFT_TO_SQKM = 0.09290304 / 1_000_000
BUFFER_FEET = 10_000
PROJECTED_CRS = "EPSG:2263"
GEOGRAPHIC_CRS = "EPSG:4326"

# 2020 U.S. Census borough counts, used only for density context.
POPULATION = {
    "Brooklyn": 2_736_074,
    "Queens": 2_405_464,
    "Manhattan": 1_694_251,
    "Bronx": 1_472_654,
    "Staten Island": 495_747,
}


def load_boroughs(path: Path | str = DATA_PATH) -> gpd.GeoDataFrame:
    """Load the bundled boundaries and derive the analysis columns."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(GEOGRAPHIC_CRS)
    if gdf.crs.to_epsg() != 2263:
        gdf = gdf.to_crs(PROJECTED_CRS)
    gdf = gdf.set_index("BoroName")

    gdf["area_sqft"] = gdf.area
    gdf["area_sqkm"] = gdf["area_sqft"] * SQFT_TO_SQKM
    gdf["boundary"] = gdf.boundary
    gdf["boundary_km"] = gdf.length * FEET_TO_KM
    gdf["centroid"] = gdf.centroid
    gdf["convex_hull"] = gdf.convex_hull
    gdf["convex_hull_ratio"] = gdf["convex_hull"].area / gdf["area_sqft"]
    gdf["buffered"] = gdf.buffer(BUFFER_FEET)
    gdf["buffered_centroid"] = gdf["centroid"].buffer(BUFFER_FEET)

    brooklyn = gdf.loc["Brooklyn", "geometry"]
    brooklyn_centroid = gdf.loc["Brooklyn", "centroid"]
    gdf["distance_to_brooklyn_km"] = (
        gdf["centroid"].distance(brooklyn_centroid) * FEET_TO_KM
    )
    gdf["buffered_intersects_brooklyn"] = gdf["buffered"].intersects(brooklyn)
    gdf["within"] = gdf["buffered_centroid"].within(gdf["geometry"])
    gdf["population"] = gdf.index.map(POPULATION)
    gdf["density_per_sqkm"] = gdf["population"] / gdf["area_sqkm"]
    return gdf


def build_summary_table(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return a presentation-ready, sorted summary table."""
    summary = pd.DataFrame(
        {
            "BoroCode": gdf["BoroCode"],
            "area_sqkm": gdf["area_sqkm"].round(2),
            "boundary_km": gdf["boundary_km"].round(2),
            "distance_to_brooklyn_km": gdf["distance_to_brooklyn_km"].round(2),
            "population": gdf["population"],
            "density_per_sqkm": gdf["density_per_sqkm"].round(0).astype("Int64"),
            "convex_hull_ratio": gdf["convex_hull_ratio"].round(3),
            "buffer_intersects_brooklyn": gdf["buffered_intersects_brooklyn"],
            "centroid_buffer_within": gdf["within"],
        }
    )
    return summary.sort_values("area_sqkm", ascending=False)


def print_analysis(gdf: gpd.GeoDataFrame, summary: pd.DataFrame) -> None:
    total_area = gdf["area_sqkm"].sum()
    total_population = int(gdf["population"].sum())
    largest = gdf["area_sqkm"].idxmax()
    smallest = gdf["area_sqkm"].idxmin()
    densest = gdf["density_per_sqkm"].idxmax()

    print("\n=== NYC Borough GIS Analysis ===")
    print(f"CRS: {gdf.crs}")
    print(f"Boroughs: {len(gdf)}")
    print(f"Total area: {total_area:,.2f} km²")
    print(f"Total population: {total_population:,}")
    print(
        f"Largest: {largest} ({gdf.loc[largest, 'area_sqkm']:.2f} km²)"
    )
    print(
        f"Smallest: {smallest} ({gdf.loc[smallest, 'area_sqkm']:.2f} km²)"
    )
    print(
        f"Densest: {densest} ({gdf.loc[densest, 'density_per_sqkm']:,.0f} people/km²)"
    )
    print("\n=== Borough summary ===")
    print(summary.to_string())


def _style_axis(axis, title: str) -> None:
    axis.set_title(title, fontsize=12, fontweight="bold", pad=8)
    axis.set_axis_off()


def create_static_figure(gdf: gpd.GeoDataFrame, output: Path) -> Path:
    """Create a six-panel Matplotlib overview."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    axes = axes.flatten()

    gdf.plot(
        column="area_sqkm",
        cmap="OrRd",
        legend=True,
        edgecolor="#333333",
        linewidth=0.7,
        ax=axes[0],
    )
    _style_axis(axes[0], "Borough area (km²)")

    gdf.plot(
        column="density_per_sqkm",
        cmap="YlGnBu",
        legend=True,
        edgecolor="#333333",
        linewidth=0.7,
        ax=axes[1],
    )
    _style_axis(axes[1], "Population density (people / km²)")

    gdf["boundary"].plot(ax=axes[2], color="#333333", linewidth=0.8)
    gdf.set_geometry("convex_hull").plot(
        ax=axes[2],
        alpha=0.32,
        color="#2a9d8f",
        edgecolor="#1d6f63",
    )
    _style_axis(axes[2], "Convex hull vs. actual boundary")

    gdf.set_geometry("buffered").plot(
        ax=axes[3],
        alpha=0.32,
        color="#8ecae6",
        edgecolor="#457b9d",
    )
    gdf.set_geometry("buffered_centroid").plot(
        ax=axes[3],
        alpha=0.4,
        color="#d62828",
        edgecolor="#8d0801",
    )
    gdf["boundary"].plot(ax=axes[3], color="white", linewidth=0.7)
    _style_axis(axes[3], "10,000 ft buffers")

    gdf["boundary"].plot(ax=axes[4], color="#333333", linewidth=0.8)
    gdf.set_geometry("centroid").plot(
        column="distance_to_brooklyn_km",
        cmap="Blues",
        legend=True,
        markersize=100,
        ax=axes[4],
    )
    _style_axis(axes[4], "Centroid distance to Brooklyn (km)")

    gdf["boundary"].plot(ax=axes[5], color="black", linewidth=0.8)
    gdf.set_geometry("buffered_centroid").plot(
        column="within",
        categorical=True,
        legend=True,
        cmap="Set1",
        alpha=0.7,
        ax=axes[5],
    )
    _style_axis(axes[5], "Buffered centroid inside the borough")

    fig.suptitle(
        "New York City boroughs — spatial analysis",
        fontsize=20,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, bbox_inches="tight")
    return output


def create_interactive_map(gdf: gpd.GeoDataFrame, output: Path):
    """Create the layered Folium map and return the map object."""
    import folium

    boroughs = gdf.set_geometry("geometry").to_crs(GEOGRAPHIC_CRS)
    centroids = gdf.set_geometry("centroid").to_crs(GEOGRAPHIC_CRS)
    hulls = gdf.set_geometry("convex_hull").to_crs(GEOGRAPHIC_CRS)
    buffers = gdf.set_geometry("buffered").to_crs(GEOGRAPHIC_CRS)
    centroid_buffers = gdf.set_geometry("buffered_centroid").to_crs(GEOGRAPHIC_CRS)

    fields = [
        "BoroCode",
        "area_sqkm",
        "boundary_km",
        "population",
        "density_per_sqkm",
        "distance_to_brooklyn_km",
        "buffered_intersects_brooklyn",
        "within",
    ]
    aliases = [
        "Borough code",
        "Area (km²)",
        "Boundary (km)",
        "Population",
        "Density (people/km²)",
        "Distance to Brooklyn (km)",
        "Buffer intersects Brooklyn",
        "Centroid buffer inside borough",
    ]

    interactive = boroughs.explore(
        column="area_sqkm",
        cmap="YlOrRd",
        tiles="OpenStreetMap",
        legend=True,
        tooltip=fields,
        tooltip_kwds={"aliases": aliases},
        style_kwds={"weight": 1.2, "color": "#4a4a4a", "fillOpacity": 0.62},
        name="Borough area",
    )

    hulls.explore(
        m=interactive,
        color="#2a9d8f",
        style_kwds={"fillOpacity": 0.08, "weight": 2},
        name="Convex hull",
    )
    buffers.explore(
        m=interactive,
        color="#457b9d",
        style_kwds={"fillOpacity": 0.05, "weight": 1.2},
        name="10,000 ft buffer",
    )
    centroid_buffers.explore(
        m=interactive,
        column="within",
        cmap="Set1",
        categorical=True,
        legend=True,
        style_kwds={"fillOpacity": 0.3, "weight": 1},
        name="Buffered centroid",
    )
    centroids.explore(
        m=interactive,
        column="distance_to_brooklyn_km",
        cmap="Blues",
        marker_type="circle_marker",
        marker_kwds={"radius": 8, "fill": True},
        legend=True,
        tooltip=["BoroCode", "distance_to_brooklyn_km"],
        tooltip_kwds={"aliases": ["Borough code", "Distance (km)"]},
        name="Centroid distance",
    )

    folium.LayerControl(collapsed=False).add_to(interactive)
    output.parent.mkdir(parents=True, exist_ok=True)
    interactive.save(output)
    return interactive


def write_outputs(gdf: gpd.GeoDataFrame, output_dir: Path) -> dict[str, Path]:
    """Write CSV, GeoJSON and chart artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary_table(gdf)
    paths = {
        "csv": output_dir / "borough_statistics.csv",
        "figure": output_dir / "nybb_analysis.png",
        "geojson": output_dir / "borough_statistics.geojson",
    }
    summary.to_csv(paths["csv"], encoding="utf-8-sig")
    create_static_figure(gdf, paths["figure"])
    export = gdf.reset_index()[
        [
            "BoroName",
            "BoroCode",
            "area_sqkm",
            "boundary_km",
            "distance_to_brooklyn_km",
            "population",
            "density_per_sqkm",
            "convex_hull_ratio",
            "geometry",
        ]
    ].to_crs(GEOGRAPHIC_CRS)
    export.to_file(paths["geojson"], driver="GeoJSON")
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze NYC borough boundaries with GeoPandas."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Folder for generated CSV, PNG, GeoJSON and HTML (default: repo root).",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DATA_PATH,
        help="Path to the borough GeoJSON.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the interactive map after generating it.",
    )
    parser.add_argument(
        "--show-plots",
        action="store_true",
        help="Display the Matplotlib figure (interactive sessions only).",
    )
    parser.add_argument(
        "--no-map",
        action="store_true",
        help="Skip generating the interactive Folium map.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gdf = load_boroughs(args.data)
    summary = build_summary_table(gdf)
    print_analysis(gdf, summary)

    paths = write_outputs(gdf, args.output_dir)
    print(f"\nCSV: {paths['csv']}")
    print(f"Chart: {paths['figure']}")
    print(f"GeoJSON: {paths['geojson']}")

    if not args.no_map:
        map_path = args.output_dir / "my_map.html"
        create_interactive_map(gdf, map_path)
        print(f"Interactive map: {map_path}")
        if args.open_browser:
            webbrowser.open(map_path.resolve().as_uri())

    if args.show_plots:
        plt.show()
    else:
        plt.close("all")


if __name__ == "__main__":
    main()
