# Tool 33: Radial Flows

**Tool call name**: `run_radial_flows`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/33_radial_flows/`:
- `flows.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Draw Radial Flows from the uploaded CSV. from_x_field=from_lon, from_y_field=from_lat, to_x_field=to_lon, to_y_field=to_lat, value_field=flow_value.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Radial flow map rendering

---

## Notes

No special notes.
