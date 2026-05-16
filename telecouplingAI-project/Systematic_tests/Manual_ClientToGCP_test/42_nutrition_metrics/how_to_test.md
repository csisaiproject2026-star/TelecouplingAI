# Tool 42: Nutrition Metrics

**Tool call name**: `run_nutrition_metrics`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/42_nutrition_metrics/`:
- `nutrition_data.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Nutrition Metrics on the uploaded CSV. age_col=age_group, sex_col=sex, weight_col=weight_kg, population_col=population.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Nutrition summary CSV
  - Demographic breakdown chart

---

## Notes

No special notes.
