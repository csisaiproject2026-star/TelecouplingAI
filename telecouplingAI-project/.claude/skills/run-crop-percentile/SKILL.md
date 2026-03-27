# Skill: run-crop-percentile

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/crop_percentile.py
Import: natcap.invest.crop_production_percentile as cpp
Reference: references/5 Crop_Production_Percentile*.md

invest_args keys:
- aggregate_polygon_path (optional; empty string if not used)
- landcover_raster_path
- landcover_to_crop_table_path (columns: lucode int, crop_name str)
- model_data_path (user-provided, required)
- results_suffix: ''
- workspace_dir

Crop name normalization: _normalize() handles case and whitespace variants
Supported crops: 172 crops loaded dynamically via get_supported_crops(model_data_path)
Test data: datainput_for_demo\CropProductionPercentile_input\

---

## [PRE_EXECUTION]

**Uploaded files**: If landcover raster, crop table, or aggregate shapefile have been uploaded, extract their paths directly — do not ask for them again. Only ask for genuinely missing inputs.

**Parameters to collect**:
- landcover_raster_path: land cover raster path (pixel values = land class codes)
- landcover_to_crop_table_path: CSV mapping land class codes to crop names (columns: lucode, crop_name)
- aggregate_polygon_path: optional shapefile for aggregating yield statistics by polygon

**Key notes**:
- model_data_path is handled server-side — do NOT mention it to the user, do NOT ask for it, do NOT include it in any response
- Supports 172 crops; if unsure whether a specific crop is supported, it will be validated at runtime
- Difference from Tool 6: this tool uses climate percentile estimates, no fertilizer data needed, suitable for broad multi-crop surveys; Tool 6 uses fertilizer regression but only supports 10 crops

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| result_table_*.csv | Table + chart | Total area and production per crop across the study area |
| aggregate_results_*.csv | Table | Production aggregated by polygon boundaries (only if aggregate_polygon_path provided) |
| *_yield_*percentile_*_preview.png | Preview image | Spatial yield distribution per crop at each climate percentile |
| *_yield_*percentile_*.tif | Download | Yield raster; unit: t/ha/year |

### Result interpretation
- Higher percentile = more favorable climate conditions = higher yield estimate
- total_production in result_table is the estimated total production within the study area
- Spatial maps reveal geographic patterns of high-yield and low-yield zones

### Suggested next steps
- Download result_table_*.csv to compare yields across crop types
- To analyze fertilizer effects on yield (10 major crops only), use Tool 6 (Crop Regression)
- Combine with Tool 4 (Seasonal Water Yield) to analyze agricultural water pressure
