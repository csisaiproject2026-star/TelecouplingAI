# Tool 30: CO2 Emissions

**Tool call name**: `run_co2_emissions`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/30_co2_emissions/`:
- `co2_data.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run CO2 Emissions analysis on the uploaded CSV. animal_count_field=animals, length_km_field=distance_km, capacity_per_trip=50, co2_per_km_per_trip=2.6.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - CO2 emissions summary CSV
  - Bar chart

---

## Notes

No special notes.
