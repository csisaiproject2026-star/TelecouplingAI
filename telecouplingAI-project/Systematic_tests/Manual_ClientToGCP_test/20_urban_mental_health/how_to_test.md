# Tool 20: Urban Mental Health

**Tool call name**: `run_urban_mental_health`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/20_urban_mental_health/`:
- `paris-lulc.tif`
- `lulc-attributes.csv`
- `population.tif`
- `administrative-units.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Urban Mental Health on the uploaded files. search_radius_mode=uniform radius, search_radius=300, decay_function=gaussian, urban_nature_demand=250.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Mental health index raster
  - Per-admin-unit summary CSV

---

## Notes

No special notes.
