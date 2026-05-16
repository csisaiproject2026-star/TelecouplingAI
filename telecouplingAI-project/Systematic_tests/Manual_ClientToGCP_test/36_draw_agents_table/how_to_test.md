# Tool 36: Draw Agents Table

**Tool call name**: `run_draw_agents_table`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/36_draw_agents_table/`:
- `agents_table.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Draw agents from the uploaded table. x_field=longitude, y_field=latitude, name_field=name.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Agent table rendered on map

---

## Notes

No special notes.
