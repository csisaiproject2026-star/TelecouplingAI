# Tool 41: Food Security

**Tool call name**: `run_food_security`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/41_food_security/`:
- `fao_food_security.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Food Security analysis on the uploaded CSV. countries=China,India,USA, indicator_field=Prevalence of undernourishment.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Food security index CSV
  - Country comparison chart

---

## Notes

No special notes.
