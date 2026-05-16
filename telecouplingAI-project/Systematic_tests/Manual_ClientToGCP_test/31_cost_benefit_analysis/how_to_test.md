# Tool 31: Cost-Benefit Analysis

**Tool call name**: `run_cost_benefit_analysis`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/31_cost_benefit_analysis/`:
- `projects.csv`
- `economic_data.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Cost-Benefit Analysis on the uploaded CSVs. key_field=project_id, cost_field=cost_usd, revenue_field=revenue_usd.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - NPV table
  - BCR summary CSV

---

## Notes

No special notes.
