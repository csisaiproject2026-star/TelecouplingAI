# Tool 35: Add Agents

**Tool call name**: `run_add_agents`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/35_add_agents/`:
- `agents.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Add agents from the uploaded CSV. x_field=longitude, y_field=latitude, name_field=agent_name.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Agent layer added to map

---

## Notes

No special notes.
