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

**Do NOT upload** (pre-installed on server, pass as server paths in prompt):
- `WaveData/` directory (~811 MB) — at `Test_data/23_wave_energy/input/WaveData`
- `global_dem.tif` — at `Test_data/_shared/Base_Data/global_dem.tif`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Wave Energy on the uploaded files. analysis_area=West Coast of North America and Hawaii, wave_base_data_path=/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/Test_data/23_wave_energy/input/WaveData, bathymetry_path=/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/Test_data/_shared/Base_Data/global_dem.tif, valuation_container=false.
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

WaveData (~811 MB) and global DEM are pre-installed on the GCP server. Pass their server-side absolute paths in the prompt — do NOT upload them from your local machine.
