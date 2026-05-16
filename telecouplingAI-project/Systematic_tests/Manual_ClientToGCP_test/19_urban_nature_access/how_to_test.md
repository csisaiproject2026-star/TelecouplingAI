# Tool 19: Urban Nature Access

**Tool call name**: `run_urban_nature_access`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/19_urban_nature_access/`:
- `paris-lulc.tif`
- `lulc-attributes.csv`
- `population.tif`
- `administrative-units.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `pop-group-radii.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Urban Nature Access on the uploaded files. search_radius_mode=radius per population group, decay_function=dichotomy, urban_nature_demand=250, aggregate_by_pop_group=true.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Nature access raster
  - Per-admin-unit supply/demand CSV

---

## Notes

No special notes.
