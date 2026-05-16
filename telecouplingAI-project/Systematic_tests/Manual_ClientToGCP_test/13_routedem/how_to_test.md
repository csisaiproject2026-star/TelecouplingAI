# Tool 13: RouteDEM

**Tool call name**: `run_routedem`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/13_routedem/`:
- `DEM_gura.tif`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run RouteDEM on the uploaded DEM. algorithm=D8, calculate_flow_direction=true, calculate_flow_accumulation=true.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Flow direction raster
  - Flow accumulation raster

---

## Notes

No special notes.
