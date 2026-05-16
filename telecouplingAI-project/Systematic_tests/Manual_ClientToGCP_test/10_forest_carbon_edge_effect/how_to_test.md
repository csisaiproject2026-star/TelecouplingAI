# Tool 10: Forest Carbon Edge

**Tool call name**: `run_forest_carbon_edge`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/10_forest_carbon_edge_effect/`:
- `forest_carbon_edge_lulc_demo.tif`
- `forest_edge_carbon_lu_table.csv`
- `forest_carbon_edge_demo_aoi.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `core_data/forest_carbon_edge_regression_model_parameters.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Forest Carbon Edge Effect on the uploaded files. n_nearest_model_points=10, biomass_to_carbon_conversion_factor=0.47, compute_forest_edge_effects=true, pools_to_calculate=all.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Carbon stock raster
  - Edge effect raster

---

## Notes

The regression model parameters shapefile lives in a `core_data/` subdirectory. Upload all sidecar files (.dbf .shx .prj) for both shapefiles.
