# Tool 38: Add Systems

**Tool call name**: `run_add_systems`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/38_add_systems/`:
- `systems.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Add systems from the uploaded CSV. x_field=longitude, y_field=latitude, name_field=system_name.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - System markers added to map

---

## Notes

No special notes.
