# Tool 18: Urban Stormwater

**Tool call name**: `run_urban_stormwater`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/18_urban_stormwater/`:
- `lulc.tif`
- `soil_groups.tif`
- `precipitation.tif`
- `biophysical_table.csv`
- `streets.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `watershed.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Urban Stormwater Retention on the uploaded files. adjust_retention_ratios=true, retention_radius=20, replacement_cost=1.59.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Retention ratio raster
  - Runoff raster
  - Replacement cost raster

---

## Notes

No special notes.
