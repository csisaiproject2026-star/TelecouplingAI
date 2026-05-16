# Tool 21: Scenic Quality

**Tool call name**: `run_scenic_quality`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/21_scenic_quality/Input/`:
- `AOI_WCVI.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `AquaWEM_points.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `claybark_dem.tif`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Scenic Quality on the uploaded files. refraction=0.13, do_valuation=false.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Viewshed raster
  - Scenic quality raster

---

## Notes

No special notes.
