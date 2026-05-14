# Skill: run-commodity-trade

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/commodity_trade.py
Tool name: run_commodity_trade

Built-in ISO3 centroids are available for most countries; a custom centroids_csv is only needed for non-standard or sub-national units.

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first. Only ask for genuinely missing inputs.

**Required parameters**:
- trade_csv: path to the CSV file containing bilateral trade flow records
- from_country_field: column name in trade_csv identifying the exporting/origin country (ISO3 or full name)
- to_country_field: column name in trade_csv identifying the importing/destination country (ISO3 or full name)
- value_field: column name in trade_csv holding the trade value (e.g., USD, tonnes)

**Optional parameters**:
- year_field: column name in trade_csv holding the year of each trade record (used for filtering)
- year: specific year to filter trade data (e.g., 2020); if omitted, all years are included
- top_n_partners: if specified, retains only the top N trading partners by total value per country
- centroids_csv: path to a custom CSV providing geographic centroids for countries or units not in the built-in list; must contain columns: country (or name), lon, lat

**Key notes**:
- The tool uses built-in ISO3 country centroids for common countries; no centroids_csv is needed for standard country-level trade data
- Provide centroids_csv only when using non-standard country names, territories, or sub-national units
- Trigger words: commodity trade, bilateral trade, trade flows, import export mapping, trade network, trade partners

---

## [POST_EXECUTION]

### Output files

| File | Type | Description |
|------|------|-------------|
| commodity_trade_flows.geojson | Download | GeoJSON LineString features; one line per bilateral flow with trade value and country attributes |
| commodity_trade_flows.shp | Download | Shapefile equivalent; suitable for GIS analysis in QGIS or ArcGIS |
| commodity_trade_summary.csv | CSV | Aggregated summary: total trade value by country pair, top exporters/importers, and overall network statistics |

### Suggested next steps
- Visualize commodity_trade_flows.geojson on the map to see trade network geography
- Filter by value_field in the GeoJSON attributes to highlight dominant trade corridors
- Use top_n_partners to focus the map on the most important trading relationships and reduce visual clutter
- Combine with run_network_analysis to detect trade community structure and identify trading blocs
- Combine with run_radial_flows if flows originate from a single focal country (hub-and-spoke analysis)
