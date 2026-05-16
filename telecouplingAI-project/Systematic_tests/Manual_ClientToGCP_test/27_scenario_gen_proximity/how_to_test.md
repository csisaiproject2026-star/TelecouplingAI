# Tool 27: Scenario Gen Proximity

**Tool call name**: `run_scenario_gen_proximity`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/27_scenario_gen_proximity/`:
- `scenario_proximity_lulc.tif`
- `scenario_proximity_aoi.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Scenario Generator Proximity on the uploaded files. replacement_lucode=12, area_to_convert=20000, focal_landcover_codes=1 2 3 4 5, convertible_landcover_codes=1 2 3 4 5, convert_nearest_to_edge=true, convert_farthest_from_edge=true, n_steps=1.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Modified LULC raster
  - Conversion statistics CSV

---

## Notes

No special notes.
