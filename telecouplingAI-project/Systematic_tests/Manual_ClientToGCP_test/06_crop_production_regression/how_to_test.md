# Tool 06: Crop Regression

**Tool call name**: `run_crop_regression`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/05_crop_production_percentile/sample_user_data/`:
- `landcover.tif`
- `landcover_to_crop_table.csv`
- `crop_fertilization_rates.csv`
- `aggregate_shape.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

From GCP **patch** path `AI_GCP_direct_test/05_crop_production_percentile/output/model_data_reg/`:
- All files in that directory  *(patched model data required)*

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Crop Production Regression on the uploaded files.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Regression yield CSV
  - Regression rasters

---

## Notes

The `model_data_reg/` folder contains patched regression model data. Download all files from the patch path and upload them.
