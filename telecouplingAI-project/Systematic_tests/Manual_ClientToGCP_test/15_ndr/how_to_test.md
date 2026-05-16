# Tool 15: NDR

**Tool call name**: `run_ndr`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/15_ndr/`:
- `DEM_gura.tif`
- `land_use_gura.tif`
- `precipitation_gura.tif`
- `watershed_gura.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

From GCP **patch** path `AI_GCP_direct_test/15_ndr/output/_patch/`:
- `bio_ndr_p.csv`  *(patched biophysical table required)*

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Nutrient Delivery Ratio (NDR) on the uploaded files. threshold_flow_accumulation=1000, k_param=2, calc_n=true, calc_p=false, subsurface_critical_length_n=150, subsurface_eff_n=0.8.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - N export raster
  - NDR raster
  - Per-watershed nutrient table

---

## Notes

`bio_ndr_p.csv` is a patched biophysical table. Download it from the patch path and upload it with the other files.
