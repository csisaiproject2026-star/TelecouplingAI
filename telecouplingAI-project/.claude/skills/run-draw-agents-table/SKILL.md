# Skill: run-draw-agents-table

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/draw_agents_table.py
Tool name: run_draw_agents_from_table

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first. Only ask for genuinely missing inputs.

**Required parameters**:
- input_csv: path to the CSV file containing agent location data with coordinates already specified
- x_field: column name for the X coordinate (longitude) of each agent
- y_field: column name for the Y coordinate (latitude) of each agent

**Optional parameters**:
- name_field: column name for agent names or labels (optional; features will be unlabeled if not provided)
- crs: coordinate reference system of the input coordinates (default: 'EPSG:4326' for WGS84 lat/lon)

**Key notes**:
- This tool is the batch/table-driven counterpart to run_add_agents_interactively; it is used when the user has a ready-made table of agent coordinates rather than entering them interactively
- Trigger words: draw agents from table, upload agent coordinates, batch agent mapping, agent CSV, agents from spreadsheet

---

## [POST_EXECUTION]

### Output files

| File | Type | Description |
|------|------|-------------|
| agents_from_table.geojson | Download | GeoJSON Point features derived from the uploaded table; one point per agent |
| agents_from_table.shp | Download | Shapefile equivalent; suitable for GIS analysis |
| agents_from_table.csv | CSV | Cleaned tabular copy of all agents with coordinates and attributes as processed |

### Suggested next steps
- Visualize agents_from_table.geojson on the map to verify all points are correctly placed
- Overlay with system boundaries from run_draw_systems_from_table to contextualize agent locations
- Combine with run_draw_radial_flows to visualize flows between agent locations
- If agent data was entered interactively row-by-row, consider switching to run_add_agents_interactively for a guided workflow
