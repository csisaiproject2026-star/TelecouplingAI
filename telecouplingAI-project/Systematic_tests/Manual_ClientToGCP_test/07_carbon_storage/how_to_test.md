# Tool 07: Carbon Storage

**Tool call name**: `run_carbon_storage`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/07_carbon_storage/`:
- `lulc_current_willamette.tif`
- `carbon_pools_willamette.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Carbon Storage on the uploaded files. calc_sequestration=false, do_valuation=false.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Total carbon stock raster
  - Carbon pool summary CSV

---

## Notes

No special notes.
