# Tool 25: Offshore Wind Energy

**Tool call name**: `run_offshore_wind_energy`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/25_wind_energy/input/`:
- `New_England_US_Aoi.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `global_wind_energy_parameters.csv`
- `3_6_turbine.csv`
- `ECNA_EEZ_WEBPAR_Aug27_2012.csv`

**Do NOT upload** (pre-installed on server, pass as server paths in prompt):
- `global_dem.tif` — at `Test_data/_shared/Base_Data/global_dem.tif`
- `global_polygon.shp` — at `Test_data/_shared/Base_Data/global_polygon.shp`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Offshore Wind Energy on the uploaded files. bathymetry_path=/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/Test_data/_shared/Base_Data/global_dem.tif, land_polygon_vector_path=/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/Test_data/_shared/Base_Data/global_polygon.shp, number_of_turbines=80, min_depth=3, max_depth=60, min_distance=0, max_distance=200000, avg_grid_distance=4, valuation_container=false.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Wind energy density raster
  - Harvested energy raster
  - Turbine site shapefile

---

## Notes

Global DEM and land polygon are pre-installed on the GCP server. Pass their server-side absolute paths in the prompt — do NOT upload them.
