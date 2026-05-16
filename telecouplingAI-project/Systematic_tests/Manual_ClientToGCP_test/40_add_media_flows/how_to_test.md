# Tool 40: Add Media Flows

**Tool call name**: `run_add_media_flows`  
**Category**: TeleBox  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/40_add_media_flows/`:
- `article.html`
- `country_centroids.csv`

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Add media flows from the uploaded HTML article. source_lon=116.4, source_lat=39.9.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Media flow arcs rendered on map

---

## Notes

No special notes.
