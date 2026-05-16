# Tool 37: Add Causes

**Tool call name**: `run_add_causes`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/37_add_causes/`:
- `causes.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Add causes from the uploaded CSV. x_field=longitude, y_field=latitude, description_field=cause_description.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Cause markers added to map

---

## Notes

No special notes.
