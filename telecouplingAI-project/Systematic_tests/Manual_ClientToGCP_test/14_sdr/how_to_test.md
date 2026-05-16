# Tool 14: SDR

**Tool call name**: `run_sdr`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/14_sdr/`:
- `DEM_gura.tif`
- `erosivity_gura.tif`
- `erodibility_gura.tif`
- `land_use_gura.tif`
- `watershed_gura.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `biophysical_table_Gura.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Sediment Delivery Ratio (SDR) on the uploaded files. threshold_flow_accumulation=1000, k_param=2, sdr_max=0.8, ic_0_param=0.5, l_max=122.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - SDR raster
  - Sediment export raster
  - Per-watershed summary CSV

---

## Notes

No special notes.
