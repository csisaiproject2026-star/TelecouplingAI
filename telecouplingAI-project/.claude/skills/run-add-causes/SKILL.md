# Skill: run-add-causes

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/add_causes.py
Tool name: run_add_causes_interactively

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first. Only ask for genuinely missing inputs.

**Required parameters**:
- input_csv: path to the CSV file containing cause location and description data
- x_field: column name for the X coordinate (longitude) of each cause location
- y_field: column name for the Y coordinate (latitude) of each cause location

**Optional parameters**:
- description_field: column name for a textual description of the cause or driver (default: 'DESCRIPTION')
- crs: coordinate reference system of the input coordinates (default: 'EPSG:4326' for WGS84 lat/lon)

**Key notes**:
- Causes in the telecoupling framework are the drivers or pressures that initiate or sustain telecoupling interactions (e.g., population growth, trade policies, climate change, demand for resources)
- Each row in input_csv becomes one cause point feature on the map
- Trigger words: add causes, telecoupling causes, drivers, pressures, cause points, telecoupling drivers, forcing factors

---

## [POST_EXECUTION]

### Output files

| File | Type | Description |
|------|------|-------------|
| causes.geojson | Download | GeoJSON Point features; one point per cause with description attribute |
| causes.shp | Download | Shapefile equivalent; suitable for GIS analysis |
| causes_table.csv | CSV | Tabular copy of all causes with coordinates and description attributes |

### Suggested next steps
- Visualize causes.geojson on the map to show spatial distribution of telecoupling drivers
- Overlay cause points with system boundaries (run_add_systems) to contextualize where drivers operate
- Combine with agent points (run_add_agents) to show which actors are associated with which drivers
- Use causes_table.csv for telecoupling case study documentation and reporting
