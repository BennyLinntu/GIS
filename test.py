import argparse
from pathlib import Path
import webbrowser

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from geodatasets import get_path


WORKSPACE = Path(__file__).resolve().parent
HTML_OUTPUT = WORKSPACE / "my_map.html"
FIGURE_OUTPUT = WORKSPACE / "nybb_analysis.png"
CSV_OUTPUT = WORKSPACE / "borough_statistics.csv"
FEET_TO_KM = 0.0003048
SQFT_TO_SQKM = 0.09290304 / 1_000_000


def load_and_prepare_data() -> gpd.GeoDataFrame:
	path_to_data = get_path("nybb")
	gdf = gpd.read_file(path_to_data).set_index("BoroName")

	gdf["area_sqft"] = gdf.area
	gdf["area_sqkm"] = gdf["area_sqft"] * SQFT_TO_SQKM
	gdf["boundary"] = gdf.boundary
	gdf["boundary_km"] = gdf.length * FEET_TO_KM
	gdf["centroid"] = gdf.centroid
	gdf["convex_hull"] = gdf.convex_hull
	gdf["buffered"] = gdf.buffer(10000)
	gdf["buffered_centroid"] = gdf["centroid"].buffer(10000)

	brooklyn = gdf.loc["Brooklyn", "geometry"]
	brooklyn_centroid = gdf.loc["Brooklyn", "centroid"]
	gdf["distance_to_brooklyn_km"] = (
		gdf["centroid"].distance(brooklyn_centroid) * FEET_TO_KM
	)
	gdf["buffered_intersects_brooklyn"] = gdf["buffered"].intersects(brooklyn)
	gdf["within"] = gdf["buffered_centroid"].within(gdf["geometry"])
	return gdf


def build_summary_table(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
	summary = pd.DataFrame(
		{
			"BoroCode": gdf["BoroCode"],
			"面积(km²)": gdf["area_sqkm"].round(2),
			"边界长度(km)": gdf["boundary_km"].round(2),
			"质心到Brooklyn质心距离(km)": gdf["distance_to_brooklyn_km"].round(2),
			"10000英尺缓冲区与Brooklyn相交": gdf["buffered_intersects_brooklyn"],
			"质心缓冲区完全位于原多边形内": gdf["within"],
		}
	)
	return summary.sort_values("面积(km²)", ascending=False)


def print_analysis(gdf: gpd.GeoDataFrame, summary: pd.DataFrame) -> None:
	total_area = gdf["area_sqkm"].sum()
	largest_borough = gdf["area_sqkm"].idxmax()
	smallest_borough = gdf["area_sqkm"].idxmin()
	mean_distance = gdf["distance_to_brooklyn_km"].mean()

	print("\n=== NYC Borough GIS Analysis ===")
	print(f"CRS: {gdf.crs}")
	print(f"行政区数量: {len(gdf)}")
	print(f"总面积: {total_area:.2f} km²")
	print(f"最大行政区: {largest_borough} ({gdf.loc[largest_borough, 'area_sqkm']:.2f} km²)")
	print(f"最小行政区: {smallest_borough} ({gdf.loc[smallest_borough, 'area_sqkm']:.2f} km²)")
	print(f"平均质心距离: {mean_distance:.2f} km")
	print("\n=== 分区统计表 ===")
	print(summary.to_string())


def create_static_figure(gdf: gpd.GeoDataFrame) -> None:
	fig, axes = plt.subplots(2, 3, figsize=(18, 12))
	axes = axes.flatten()

	gdf.plot(
		column="area_sqkm",
		cmap="OrRd",
		legend=True,
		edgecolor="#333333",
		linewidth=0.8,
		ax=axes[0],
	)
	axes[0].set_title("Borough Area (km²)")
	axes[0].set_axis_off()

	gdf["boundary"].plot(ax=axes[1], color="white", linewidth=0.8)
	gdf.set_geometry("convex_hull").plot(
		ax=axes[1],
		alpha=0.45,
		color="#2a9d8f",
		edgecolor="#1d6f63",
	)
	axes[1].set_title("Convex Hull vs Boundary")
	axes[1].set_axis_off()

	gdf.set_geometry("buffered").plot(
		ax=axes[2],
		alpha=0.4,
		color="#8ecae6",
		edgecolor="#457b9d",
	)
	gdf.set_geometry("buffered_centroid").plot(
		ax=axes[2],
		alpha=0.45,
		color="#d62828",
		edgecolor="#8d0801",
	)
	gdf["boundary"].plot(ax=axes[2], color="white", linewidth=0.8)
	axes[2].set_title("10,000 ft Buffers")
	axes[2].set_axis_off()

	gdf["boundary"].plot(ax=axes[3], color="#333333", linewidth=0.8)
	gdf.set_geometry("centroid").plot(
		column="distance_to_brooklyn_km",
		cmap="Blues",
		legend=True,
		markersize=90,
		ax=axes[3],
	)
	axes[3].set_title("Centroid Distance to Brooklyn (km)")
	axes[3].set_axis_off()

	gdf["boundary"].plot(ax=axes[4], color="black", linewidth=0.8)
	gdf.set_geometry("buffered_centroid").plot(
		column="within",
		categorical=True,
		legend=True,
		cmap="Set1",
		alpha=0.7,
		ax=axes[4],
	)
	axes[4].set_title("Buffered Centroid Within Original Polygon")
	axes[4].set_axis_off()

	boroughs_4326 = gdf.set_geometry("geometry").to_crs("EPSG:4326")
	boroughs_4326.plot(
		column="area_sqkm",
		cmap="YlGnBu",
		legend=True,
		edgecolor="#333333",
		linewidth=0.8,
		ax=axes[5],
	)
	axes[5].set_title("Reprojected to EPSG:4326")
	axes[5].set_axis_off()

	fig.suptitle("New York Borough GIS Analysis", fontsize=18, fontweight="bold")
	fig.tight_layout(rect=(0, 0, 1, 0.97))
	fig.savefig(FIGURE_OUTPUT, dpi=220, bbox_inches="tight")


def create_interactive_map(gdf: gpd.GeoDataFrame) -> None:
	boroughs_4326 = gdf.set_geometry("geometry").to_crs("EPSG:4326")
	centroids_4326 = gdf.set_geometry("centroid").to_crs("EPSG:4326")
	convex_hulls_4326 = gdf.set_geometry("convex_hull").to_crs("EPSG:4326")
	buffered_4326 = gdf.set_geometry("buffered").to_crs("EPSG:4326")
	buffered_centroid_4326 = gdf.set_geometry("buffered_centroid").to_crs("EPSG:4326")

	tooltip_fields = [
		"BoroCode",
		"area_sqkm",
		"boundary_km",
		"distance_to_brooklyn_km",
		"buffered_intersects_brooklyn",
		"within",
	]
	tooltip_aliases = [
		"行政区编码",
		"面积(km²)",
		"边界长度(km)",
		"质心到Brooklyn距离(km)",
		"缓冲区与Brooklyn相交",
		"质心缓冲区在原区域内",
	]

	interactive_map = boroughs_4326.explore(
		column="area_sqkm",
		cmap="YlOrRd",
		tiles="CartoDB positron",
		legend=True,
		tooltip=tooltip_fields,
		tooltip_kwds={"aliases": tooltip_aliases},
		style_kwds={"weight": 1.2, "color": "#4a4a4a", "fillOpacity": 0.65},
		name="Borough Area",
	)

	convex_hulls_4326.explore(
		m=interactive_map,
		color="#2a9d8f",
		style_kwds={"fillOpacity": 0.1, "weight": 2},
		name="Convex Hull",
	)

	buffered_4326.explore(
		m=interactive_map,
		color="#457b9d",
		style_kwds={"fillOpacity": 0.08, "weight": 1.2},
		name="Buffered Boroughs",
	)

	buffered_centroid_4326.explore(
		m=interactive_map,
		column="within",
		cmap="Set1",
		categorical=True,
		legend=True,
		style_kwds={"fillOpacity": 0.35, "weight": 1},
		name="Buffered Centroid Within",
	)

	centroids_4326.explore(
		m=interactive_map,
		column="distance_to_brooklyn_km",
		cmap="Blues",
		marker_type="circle_marker",
		marker_kwds={"radius": 8, "fill": True},
		legend=True,
		tooltip=["BoroCode", "distance_to_brooklyn_km"],
		tooltip_kwds={"aliases": ["行政区编码", "质心距离(km)"]},
		name="Centroids",
	)

	import folium

	folium.LayerControl(collapsed=False).add_to(interactive_map)
	interactive_map.save(HTML_OUTPUT)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Generate a complete GeoPandas GIS analysis demo.")
	parser.add_argument(
		"--show-plots",
		action="store_true",
		help="Display matplotlib figures after saving them.",
	)
	parser.add_argument(
		"--open-browser",
		action="store_true",
		help="Open the exported HTML map in the default browser.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	gdf = load_and_prepare_data()
	summary = build_summary_table(gdf)

	summary.to_csv(CSV_OUTPUT, encoding="utf-8-sig")
	print_analysis(gdf, summary)
	create_static_figure(gdf)
	create_interactive_map(gdf)

	print(f"\n统计表已保存: {CSV_OUTPUT}")
	print(f"分析图已保存: {FIGURE_OUTPUT}")
	print(f"交互地图已保存: {HTML_OUTPUT}")

	if args.open_browser:
		webbrowser.open(HTML_OUTPUT.resolve().as_uri())

	if args.show_plots:
		plt.show()
	else:
		plt.close("all")


if __name__ == "__main__":
	main()