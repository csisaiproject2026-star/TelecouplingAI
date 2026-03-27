# Skill: run-network-analysis

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/network_analysis.py → backend/r_scripts/network_analysis.R
Reference: references/3 Network_Analysis_Grouping*.md (contains full R script)

R script arg mapping:
- nodes_table_path, links_table_path, shapefile_path
- nodes_table_join (= nodes_join_attri)
- in_telecoupling_layer_join (= layer_join_attri)
- clustering_algorithm: "walktrap" | "spin_glass"

R script rules:
- Always use variable in_telecoupling_layer_join, never hardcode "ISO_3_code"
- Color count guard: brewer.pal(min(max(n_communities, 3), 12), color_set)

Test data: datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\

---

## [PRE_EXECUTION]

**Uploaded files**: If nodes CSV, links CSV, or shapefile have been uploaded, extract their paths directly — do not ask for them again. Only ask for genuinely missing inputs.

**Parameters to collect**:
- nodes_table: path to nodes CSV file (must contain node attributes and a join column)
- links_table: path to edges/links CSV file (source and target node identifiers)
- shapefile_path: path to basemap shapefile for geographic visualization
- nodes_join_attri: column name in nodes CSV used to join with shapefile (e.g. "CODE")
- layer_join_attri: column name in shapefile attribute table used for joining (e.g. "ISO_3_CODE")
- clustering_algorithm: "walktrap" or "spin_glass" — if not specified, recommend "walktrap" and confirm
- Optional (have defaults, only ask if user wants to adjust): weight_within_clusters=10, weight_between_clusters=2, color_set="Set3", node_size=0.05, edge_width=0.833333, label_size=0.8

**Key notes**:
- nodes_join_attri and layer_join_attri are JOIN column names, not data values — ask explicitly if not provided

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| network_plot_*.pdf | Download | Full network visualization with nodes colored by community; suitable for publication |
| network_stats_*.csv | Table | Per-node statistics: degree, closeness centrality, betweenness centrality |
| output_*_preview.png | Preview image | Map of geographic units colored by community membership, overlaid on satellite basemap |
| output_*.shp | Download | Shapefile with cluster_id column; can be used for further GIS analysis |

### Result interpretation
- Tell the user how many community groups were detected
- High degree nodes = key hubs in the network
- High betweenness nodes = bridges connecting different communities

### Suggested next steps
- Try the other clustering algorithm (walktrap vs spin_glass) to compare results
- Adjust weight_within_clusters / weight_between_clusters to tune cluster cohesion
