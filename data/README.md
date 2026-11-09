# Data source

`nyc_boroughs.geojson` contains the five New York City borough boundaries.

- **Original dataset:** NYC Open Data — Borough Boundaries (`nybb`)
- **Accessed via:** [`geodatasets`](https://github.com/geopandas/geodatasets) (`geodatasets.get_path("nybb")`)
- **CRS:** EPSG:4326 (WGS 84), simplified with a tolerance of `0.00008°`
- **Fields:** `BoroCode`, `BoroName`, `Shape_Leng`, `Shape_Area`, `geometry`

The GeoJSON is bundled so the analysis and tests run offline. The script projects it to
**EPSG:2263** (NAD83 / New York Long Island, US feet) for accurate area, distance and
buffer calculations.

Population figures in `gis_analysis.py` are 2020 U.S. Census borough counts, used only to
derive population density for the chart and table.

NYC Open Data is published under the [NYC Open Data Terms of Use](https://opendata.cityofnewyork.us/overview/#termsofuse).
