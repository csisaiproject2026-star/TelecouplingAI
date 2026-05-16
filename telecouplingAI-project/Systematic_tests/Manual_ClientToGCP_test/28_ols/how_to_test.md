# Tool 28: OLS Regression

**Tool call name**: `run_ols_regression`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/28_ols/`:
- `ols_data.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run OLS Regression on the uploaded CSV. dependent_variable=y, independent_variables=x1,x2,x3.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Regression summary JSON
  - Coefficient table

---

## Notes

No special notes.
