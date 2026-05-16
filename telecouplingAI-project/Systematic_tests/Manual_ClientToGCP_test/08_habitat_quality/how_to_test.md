# Tool 08: Habitat Quality

**Tool call name**: `run_habitat_quality`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/08_habitat_quality/`:
- `lulc_current_willamette.tif`
- `threats_willamette.csv`

From GCP **patch** path `AI_GCP_direct_test/08_habitat_quality/output/_patch/`:
- `sensitivity_p.csv`  *(patched version required)*

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Habitat Quality on the uploaded files. half_saturation_constant=0.5.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Habitat quality raster
  - Habitat degradation raster

---

## Notes

`sensitivity_p.csv` is a patched sensitivity table. Download it from the patch path above.
