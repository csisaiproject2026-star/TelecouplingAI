# Tool 09: Annual Water Yield

**Tool call name**: `run_annual_water_yield`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/09_annual_water_yield/`:
- `reference_ET_gura.tif`
- `precipitation_gura.tif`
- `depth_to_root_restricting_layer_gura.tif`
- `plant_available_water_fraction_gura.tif`
- `land_use_gura.tif`
- `watershed_gura.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `biophysical_table_gura.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Annual Water Yield on the uploaded files. seasonality_constant=15.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Annual yield raster
  - Per-watershed yield table

---

## Notes

No special notes.
