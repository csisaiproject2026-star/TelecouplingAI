# Tool 29: FAMD

**Tool call name**: `run_famd`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/29_famd/`:
- `famd_data.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run FAMD factor analysis on the uploaded CSV. quantitative_variables=age,income, qualitative_variables=gender,region.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - FAMD component scores CSV
  - Variance explained chart

---

## Notes

No special notes.
