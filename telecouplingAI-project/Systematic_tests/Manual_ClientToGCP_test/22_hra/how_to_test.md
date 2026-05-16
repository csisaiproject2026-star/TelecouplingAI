# Tool 22: HRA

**Tool call name**: `run_habitat_risk_assessment`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/22_hra/Input/`:
- `habitat_stressor_info.csv`
- `exposure_consequence_criteria.csv`
- `subregions.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Habitat Risk Assessment (HRA) on the uploaded files. resolution=500, max_rating=3, risk_eq=Euclidean, decay_eq=linear, n_overlapping_stressors=2, visualize_outputs=false.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Risk rasters per habitat
  - Risk summary CSV

---

## Notes

No special notes.
