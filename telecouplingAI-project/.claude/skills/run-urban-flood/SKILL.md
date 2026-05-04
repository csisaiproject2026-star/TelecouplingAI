# Skill: run-urban-flood

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/urban_flood.py
Import: natcap.invest.urban_flood_risk_mitigation
Tool name: run_urban_flood_risk_mitigation

invest_args keys:
- workspace_dir
- aoi_watersheds_path (required; polygon shapefile of study watersheds)
- rainfall_depth (required float; design storm depth, mm)
- lulc_path (required)
- soils_hydrological_group_raster_path (required; raster of SCS hydrological soil groups A/B/C/D encoded as 1/2/3/4)
- curve_number_table_path (required; columns: lucode, CN_A, CN_B, CN_C, CN_D)
- built_infrastructure_vector_path (optional; polygon shapefile of buildings/infrastructure)
- infrastructure_damage_loss_table_path (optional; CSV of damage costs by infrastructure type)

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first.

**Required parameters**:
- aoi_watersheds_path: polygon shapefile defining the study watersheds (used for spatial aggregation)
- rainfall_depth: design storm depth in millimeters (e.g. 50 for a 50mm storm; ask the user for their design storm return period if they're unsure)
- lulc_path: land use / land cover raster for the urban area
- soils_hydrological_group_raster_path: raster of SCS hydrological soil groups (A=well drained, D=poorly drained) encoded as integers 1–4
- curve_number_table_path: CSV with Curve Number (CN) values for each LULC class × soil group combination (columns: lucode, CN_A, CN_B, CN_C, CN_D)

**Optional — damage valuation** (ask only if user wants economic estimates):
- built_infrastructure_vector_path: polygon shapefile of buildings/roads/infrastructure footprints (must have 'type' field)
- infrastructure_damage_loss_table_path: CSV mapping infrastructure type to damage cost per unit area flooded

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| Runoff_retention.tif | Download | Runoff retention volume per pixel (m³); how much stormwater is absorbed vs. runs off |
| Runoff_retention_ret.tif | Download | Runoff retention ratio (0–1) per pixel |
| Q_mm.tif | Download | Runoff depth (mm) per pixel for the design storm |
| flood_risk_service.tif | Download | Relative flood risk mitigation provided by each pixel |
| watershed_results_flood_risk.shp | Download | Per-watershed summary of retention and runoff volumes |
| watershed_results_flood_risk.csv | Table | Tabular watershed results |
| structures_at_risk.shp | Download | Infrastructure within the highest-runoff zone (if infrastructure input provided) |
| structures_at_risk.csv | Table | Damage estimates per structure |

### Domain knowledge — understanding Urban Flood outputs

**SCS Curve Number method**:
- The model uses the USDA SCS Curve Number (CN) approach to estimate runoff from a design storm
- CN ranges from 0 (perfect infiltration) to 100 (total runoff — impervious)
- CN depends on both land cover (how much is paved/vegetated) and soil type (how permeable)
- Impervious urban areas on poorly drained soils (CN ~90–98) produce far more runoff than forested areas on sandy soils (CN ~30–55)

**Q_mm.tif**:
- Modeled runoff depth per pixel for the specified rainfall_depth event
- High values = high flood generation; these pixels contribute most to downstream flooding
- Urban pixels (parking lots, rooftops) on C/D soils dominate runoff production

**Runoff_retention.tif**:
- Volume of stormwater retained (absorbed, infiltrated, or held) per pixel — the ecosystem service
- High retention = green infrastructure performing well (parks, permeable pavement, wetlands)
- Comparing retention between a current and alternative LULC scenario shows the benefit of green infrastructure investment

**Flood risk mitigation service**:
- flood_risk_service.tif shows which landscape elements contribute most to reducing downstream flood risk
- High values in permeable areas that are hydrologically connected to downstream infrastructure
- Prioritize retention investments in high-service areas near critical infrastructure

**Design storm selection**:
- A 10-year return period storm is standard for urban drainage design (~50–100mm depending on climate)
- A 100-year storm is used for critical infrastructure risk assessment
- The model runs a single storm — run multiple times with different rainfall_depth values for risk curve analysis

**Damage valuation**:
- structures_at_risk.csv estimates economic damage to buildings and infrastructure
- Useful for cost-benefit analysis of green infrastructure vs. grey stormwater solutions

### Suggested next steps
- Download Q_mm.tif to identify the highest runoff-generating areas in the watershed
- Download Runoff_retention.tif to find where green infrastructure is most effective
- Review watershed_results_flood_risk.csv for watershed-level retention performance
- Run with different rainfall_depth values to build a risk curve
- Combine with Urban Stormwater (run_urban_stormwater) for complementary stormwater quality analysis
