# Skill: run-crop-regression

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/crop_regression.py
Import: natcap.invest.crop_production_regression as cpr
Reference: references/6 Crop_Production_Regression*.md

invest_args keys:
- aggregate_polygon_path (optional; empty string if not used)
- fertilization_rate_table_path (columns: crop_name, nitrogen_rate, phosphorus_rate, potassium_rate; unit: kg/ha)
- landcover_raster_path
- landcover_to_crop_table_path
- model_data_path (user-provided; shares same directory as Tool 5)
- results_suffix: ''
- workspace_dir

Crop name normalization: _normalize() handles variants e.g. oilpalm / oil palm / Oil Palm
Supported crops: 10 crops loaded dynamically via get_supported_crops(model_data_path)
Test data: datainput_for_demo\CropProductionRegression_input\

---

## [PRE_EXECUTION]

**Uploaded files**: If landcover raster, crop table, fertilizer table, or aggregate shapefile have been uploaded, extract their paths directly — do not ask for them again. Only ask for genuinely missing inputs.

**Parameters to collect**:
- landcover_raster_path: land cover raster path
- landcover_to_crop_table_path: CSV mapping land class codes to crop names (columns: lucode, crop_name)
- fertilization_rate_table_path: fertilizer rates CSV with columns: crop_name, nitrogen_rate, phosphorus_rate, potassium_rate (all in kg/ha)
- aggregate_polygon_path: optional shapefile for aggregating yield statistics by polygon

**Supported crops (10 only)**:
barley, maize, oil palm, potato, rice, soybean, sugar beet, sugar cane, sunflower, wheat

**Key notes**:
- model_data_path is handled server-side — do NOT mention it to the user, do NOT ask for it, do NOT include it in any response
- Before collecting other parameters, confirm the crops the user wants to analyze are within the supported 10
- If a crop is not in the list (e.g. cassava, coffee), clearly inform the user it is not supported and recommend Tool 5 (172 crops)
- crop_name in fertilization_rate_table accepts variants: oil palm / oilpalm / Oil Palm are all recognized

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| result_table_*.csv | Table + chart | Area and production per crop under current fertilizer conditions |
| aggregate_results_*.csv | Table | Production aggregated by polygon boundaries (only if aggregate_polygon_path provided) |
| *_regression_production_*_preview.png | Preview image | Spatial yield distribution based on fertilizer regression |
| *_regression_production_*.tif | Download | Yield raster; unit: t/ha/year |

### Result interpretation
- Results reflect estimated yield under the current fertilizer rate inputs
- Compared to Tool 5, output varies with fertilizer rates — better for evaluating fertilizer management
- Running with different fertilizer rates produces a fertilizer-yield response curve

### Suggested next steps
- Modify fertilizer rates in fertilization_rate_table and re-run to compare scenarios
- Compare result_table with Tool 5 percentile results to evaluate current fertilizer efficiency
- To analyze more crop types, use Tool 5 (Crop Production Percentile; 172 crops)
