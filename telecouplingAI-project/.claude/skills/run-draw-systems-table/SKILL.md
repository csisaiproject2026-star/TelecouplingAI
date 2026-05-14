# Skill: run-draw-systems-table

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/draw_systems_table.py
Tool name: run_draw_systems_from_table

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first. Only ask for genuinely missing inputs.

**Required parameters**:
- input_csv: path to the CSV file containing system location data with coordinates already specified
- x_field: column name for the X coordinate (longitude) of each system
- y_field: column name for the Y coordinate (latitude) of each system

**Optional parameters**:
- crs: coordinate reference system of the input coordinates (default: 'EPSG:4326' for WGS84 lat/lon)

**Key notes**:
- This tool is the batch/table-driven counterpart to run_add_systems_interactively; it is used when the user has a ready-made table of system coordinates
- Any additional columns in input_csv beyond x_field and y_field are preserved as attributes in the output GeoJSON/SHP
- Trigger words: draw systems from table, upload system coordinates, batch system mapping, systems from spreadsheet, systems CSV

---

## [POST_EXECUTION]

### Output files

| File | Type | Description |
|------|------|-------------|
| systems_from_table.geojson | Download | GeoJSON Point features derived from the uploaded table; one point per system with all CSV attributes |
| systems_from_table.shp | Download | Shapefile equivalent; suitable for GIS analysis in QGIS or ArcGIS |
| systems_from_table.csv | CSV | Cleaned tabular copy of all systems with coordinates and attributes as processed |

### Suggested next steps
- Visualize systems_from_table.geojson on the map to verify system locations
- Overlay with flow lines (run_draw_radial_flows, run_commodity_trade) to create a complete telecoupling map
- Combine with agents (run_draw_agents_from_table) and causes (run_add_causes) for a full telecoupling framework visualization
- If systems need to be entered one-by-one with guided prompts, use run_add_systems_interactively instead
