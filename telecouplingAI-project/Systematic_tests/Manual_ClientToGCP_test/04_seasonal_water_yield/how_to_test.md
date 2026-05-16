# Tool 04: Seasonal Water Yield

**Tool call name**: `run_seasonal_water_yield`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/04_seasonal_water_yield/`:
- `watershed_gura.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `DEM_gura.tif`
- `land_use_gura.tif`
- `soil_group_gura.tif`
- `biophysical_table_gura_SWY.csv`
- `rain_events_gura.csv`
- All 12 files in `ET0_monthly/` directory
- All 12 files in `Precipitation_monthly/` directory

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Seasonal Water Yield on the uploaded files. threshold_flow_accumulation=1000, alpha_m=1/12, beta_i=1, gamma=1, monthly_alpha=false, user_defined_climate_zones=false, user_defined_local_recharge=false, flow_dir_algorithm=MFD.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - QF rasters (monthly)
  - B rasters
  - L raster

---

## Notes

Upload the 24 monthly rasters individually (12 ET0 + 12 precipitation). Total file count is large; allow extra time for upload.
