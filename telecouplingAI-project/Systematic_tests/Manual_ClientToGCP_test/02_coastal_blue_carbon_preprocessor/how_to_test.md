# Tool 02: CBC Preprocessor

**Tool call name**: `run_cbc_preprocessor`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/02_coastal_blue_carbon_preprocessor/`:
- `snapshots.csv`

From GCP **patch** path `AI_GCP_direct_test/02_coastal_blue_carbon_preprocessor/output/_patch/`:
- `lulc_lookup_p.csv`  *(patched version required)*

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Coastal Blue Carbon Preprocessor on the uploaded files.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - transitions.csv
  - Carbon lookup table

---

## Notes

`lulc_lookup_p.csv` is a patched lookup table from the AI_GCP_direct_test output. Download it from the patch path above; do NOT use the original.
