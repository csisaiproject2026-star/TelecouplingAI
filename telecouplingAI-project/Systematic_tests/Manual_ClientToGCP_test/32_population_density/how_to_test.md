# Tool 32: Population Density

**Tool call name**: `run_population_density`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/32_population_density/`:
- `population.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Population Density analysis on the uploaded CSV. population_field=pop_2020, area_km2_field=area_km2.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Density summary CSV
  - Choropleth map data

---

## Notes

No special notes.
