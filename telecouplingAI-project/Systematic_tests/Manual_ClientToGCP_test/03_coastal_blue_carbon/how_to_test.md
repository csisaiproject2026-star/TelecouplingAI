# Tool 03: Coastal Blue Carbon

**Tool call name**: `run_coastal_blue_carbon`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/02_coastal_blue_carbon_preprocessor/`:
- `snapshots.csv`

From GCP server path `Test_data/03_coastal_blue_carbon/outputs_preprocessor/`:
- `transitions_sample.csv`

From GCP **patch** path `AI_GCP_direct_test/03_coastal_blue_carbon/output/_patch/`:
- `biophysical_p.csv`  *(patched version required)*

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Coastal Blue Carbon main model on the uploaded files. analysis_year=2060, do_economic_analysis=false, use_price_table=false.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Carbon stock rasters
  - Net sequestration CSV

---

## Notes

`biophysical_p.csv` is a patched biophysical table from the AI_GCP_direct_test output. Download it from the patch path above.
