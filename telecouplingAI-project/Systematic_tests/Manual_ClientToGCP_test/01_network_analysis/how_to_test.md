# Tool 01: Network Analysis

**Tool call name**: `run_network_analysis`  
**Category**: InVEST  
**GCP URL**: http://34.42.83.50/

---

## Files to Upload

From GCP server path `Test_data/01_network_analysis/Network Analysis Grouping/`:
- `nodes.csv`
- `links.csv`
- `World_countries_2002.shp` (+ sidecars: `.dbf` `.shx` `.prj`)

*(Download these files via SCP from the GCP server, or use the GCP browser directly)*

---

## Prompt

Copy and paste this into the chat box:

```
Run Network Analysis on the uploaded files. nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, clustering_algorithm=walktrap.
```

---

## Expected Result

- Blue card appears → LLM called the tool  ✓
- Green card → computation complete  ✓
- Output files:
  - Network graph JSON
  - Clustering result CSV

---

## Notes

No special notes.
