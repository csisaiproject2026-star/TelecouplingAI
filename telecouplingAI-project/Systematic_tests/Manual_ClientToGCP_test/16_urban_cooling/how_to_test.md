# Tool 16: Urban Cooling

**Tool call name**: `run_urban_cooling`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/16_urban_cooling/`:
- `lulc.tif`
- `et0.tif`
- `aoi.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `Biophysical_UHI_fake.csv`
- `sample_buildings.shp` (+ sidecars: `.dbf` `.shx` `.prj`)
- `Fake_energy_savings.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Urban Cooling on the uploaded files. t_ref=21.5, uhi_max=3.5, t_air_average_radius=2000, green_area_cooling_distance=1000, cc_method=factors, cc_weight_shade=0.6, cc_weight_albedo=0.2, cc_weight_eti=0.2, avg_rel_humidity=30, do_energy_valuation=true, do_productivity_valuation=true.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - HM raster
  - T_air raster
  - Energy savings CSV
  - Work productivity CSV

---

## Notes

No special notes.
