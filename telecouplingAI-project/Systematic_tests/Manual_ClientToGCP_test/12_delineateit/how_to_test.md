# Tool 12: DelineateIt

**Tool call name**: `run_delineateit`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/12_delineateit/`:
- `DEM_gura.tif`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run DelineateIt on the uploaded DEM. detect_pour_points=true.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Watershed shapefile
  - Pour points shapefile

---

## Notes

No special notes.
