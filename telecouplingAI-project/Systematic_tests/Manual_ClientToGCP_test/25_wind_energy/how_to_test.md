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

The global DEM and global land polygon are **not** uploaded — the tool uses the server's built-in copies automatically. No server paths needed.

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Offshore Wind Energy on the uploaded files. number_of_turbines=80, min_depth=3, max_depth=60, min_distance=0, max_distance=200000, avg_grid_distance=4, valuation_container=false.
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

Do not pass bathymetry_path or land_polygon_vector_path — omit them and the tool automatically uses the server's built-in global DEM and land polygon, then notes in its reply that the built-in defaults were used.
