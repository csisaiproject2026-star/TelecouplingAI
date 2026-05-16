# Tool 17: Urban Flood

**Tool call name**: `run_urban_flood`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/17_urban_flood/`:
- `watersheds.gpkg`
- `lulc.tif`
- `soilgroup.tif`
- `Biophysical_water_SF.csv`
- `infrastructure.gpkg`
- `Damage.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Urban Flood Risk Mitigation on the uploaded files. rainfall_depth=40.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Runoff raster
  - Retention raster
  - Infrastructure damage CSV

---

## Notes

Input files are GeoPackage (.gpkg) format — upload as-is.
