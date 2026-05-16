# Tool 34: Commodity Trade

**Tool call name**: `run_commodity_trade`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/34_commodity_trade/`:
- `trade.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Commodity Trade analysis on the uploaded CSV. from_country_field=exporter_iso3, to_country_field=importer_iso3, value_field=trade_usd.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Trade flow map
  - Summary trade table

---

## Notes

No special notes.
