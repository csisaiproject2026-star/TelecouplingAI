# Tool 23: Wave Energy

**Tool call name**: `run_wave_energy_production`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/23_wave_energy/input/`:
- `Machine_AquaBuOY_Performance.csv`
- `Machine_AquaBuOY_Parameter.csv`
- `AOI_WCVI.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

WaveData (~811 MB) and the global DEM are **not** uploaded — the tool uses the server's built-in copies automatically. No server paths needed.

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Wave Energy on the uploaded files. analysis_area=West Coast of North America and Hawaii, valuation_container=false.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Wave energy raster
  - Captured wave energy raster

---

## Notes

Do not pass wave_base_data_path or bathymetry_path — omit them and the tool automatically uses the server's built-in WaveData and global DEM, then notes in its reply that the built-in defaults were used.
