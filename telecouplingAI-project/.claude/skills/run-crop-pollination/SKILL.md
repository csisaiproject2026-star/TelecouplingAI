# Skill: run-crop-pollination

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/pollination.py
Import: natcap.invest.pollination
Tool name: run_crop_pollination

invest_args keys (InVEST 3.14.3):
- workspace_dir
- landcover_raster_path (required; NOTE: key is 'landcover_raster_path' not 'lulc_path' in 3.14.3)
- guild_table_path (required; columns: species, nesting_suitability_*, foraging_activity_*_spring/summer/fall)
- landcover_biophysical_table_path (required; columns: lucode, nesting_*, floral_resources_*)
- farm_vector_path (optional; polygon shapefile of farms with crop yield data)

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first.

**Required parameters**:
- landcover_raster_path: land cover raster (pixel values = land class codes)
- guild_table_path: CSV defining each pollinator species/guild — includes nesting preferences and seasonal foraging activity per land cover season
- landcover_biophysical_table_path: CSV mapping each land cover class to nesting habitat suitability and floral resource availability by season

**Optional parameters**:
- farm_vector_path: shapefile of agricultural fields — if provided, enables on-farm pollination supply and yield estimates per crop

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| pollinator_abundance_<species>_<season>.tif | Download | Relative abundance of each pollinator species by season on the landscape |
| pollinator_supply_<species>.tif | Download | Pollinator supply index — foragers available from each habitat pixel |
| farm_results.shp | Download | Per-farm pollination supply and yield estimates (if farm_vector_path provided) |
| farm_results.csv | Table | Tabular per-farm results |

### Domain knowledge — understanding Pollination outputs

**What pollinator abundance represents**:
- The model tracks two processes: (1) nesting — where bees establish colonies, and (2) foraging — where bees collect resources within their flight range
- pollinator_abundance rasters show relative foraging activity on each pixel across seasons (spring, summer, fall)
- Values are relative indices (0–1), not absolute bee counts — useful for spatial comparisons within the study area

**How to read the spatial pattern**:
- High abundance near semi-natural habitats (forests, hedgerows, meadows) that provide both nesting and foraging resources
- Low abundance in monoculture croplands or urban areas with minimal floral resources
- Abundance drops off with distance from source habitat (limited by foraging range defined in guild table)

**Farm-level outputs (when farm_vector_path provided)**:
- Pollination supply to each farm: fraction of pollinators visiting the farm relative to its demand
- Deficit farms (supply < demand) may show yield penalties for insect-pollinated crops
- Use this to prioritize habitat restoration near farms with the greatest pollination deficits

**Seasonal interpretation**:
- Spring abundance matters most for early-flowering crops (apple, cherry)
- Summer abundance for staple crops (sunflower, squash, berry)
- Fall abundance for late-season crops and colony overwinter resource accumulation

**Limitations**:
- Model does not include managed honeybees — it represents wild/native pollinators only
- Abundance index is sensitive to guild table parameterization (nesting preferences, flight distances)

### Suggested next steps
- Download pollinator_abundance rasters to map seasonal pollinator hotspots
- If farm_vector_path was provided, review farm_results.csv to identify fields with pollination deficits
- Overlay abundance maps with Habitat Quality (quality_c.tif) to identify dual-purpose conservation areas
- To improve pollination, target habitat restoration in the foraging radius (~1–2 km) around deficit farms
