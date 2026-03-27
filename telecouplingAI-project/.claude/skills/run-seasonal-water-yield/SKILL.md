# Skill: run-seasonal-water-yield

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/seasonal_water_yield.py
Import: natcap.invest.seasonal_water_yield.seasonal_water_yield as swy
Reference: references/4 Seasonal_Water_Yield*.md

Full invest_args key list:
alpha_m, aoi_path, beta_i, biophysical_table_path, climate_zone_raster_path,
climate_zone_table_path, dem_raster_path, et0_dir, gamma, l_path,
lulc_raster_path, monthly_alpha, monthly_alpha_path, precip_dir,
rain_events_table_path, results_suffix, soil_group_path,
threshold_flow_accumulation, user_defined_climate_zones,
user_defined_local_recharge, workspace_dir

⚠️ Monthly file naming: project files are precip_gura_N.tif / ET0_gura_N.tif;
InVEST expects precip_mN.tif / et0_mN.tif — handled automatically by prepare_monthly_dir().

Test data: datainput_for_demo\SeasonalWaterYield_input\

---

## [PRE_EXECUTION]

**Uploaded files**: If any spatial inputs (shapefiles, rasters, CSVs) or directories have been uploaded or their paths provided, extract them directly — do not ask again. Only ask for genuinely missing inputs.

**Parameters to collect**:
- aoi_path: watershed area of interest shapefile path
- lulc_raster_path: land use / land cover raster path
- dem_raster_path: Digital Elevation Model raster path
- soil_group_path: hydrologic soil group raster path (classes A/B/C/D)
- biophysical_table_path: biophysical parameters CSV path
- precip_dir: **directory** containing 12 monthly precipitation rasters (not a single file)
- et0_dir: **directory** containing 12 monthly ET0 rasters (not a single file)
- rain_events_table_path: rain events CSV path (columns: month, events)
- threshold_flow_accumulation: integer, default 1000 — only ask if user wants to change
- Optional (defaults provided, only ask if user wants to adjust): alpha_m=0.083333, beta_i=1.0, gamma=1.0

**Key notes**:
- precip_dir and et0_dir must be directory paths, not individual file paths

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| QF_*_preview.png | Preview image | Quickflow (surface runoff) spatial distribution |
| QF_*.tif | Download | Quickflow raster; unit: mm/year |
| B_*_preview.png | Preview image | Baseflow (groundwater recharge contribution) spatial distribution |
| B_*.tif | Download | Baseflow raster; unit: mm/year |
| L_avail_*_preview.png | Preview image | Available local recharge spatial distribution |
| L_*_preview.png | Preview image | Local recharge spatial distribution |
| P_*_preview.png | Preview image | Precipitation spatial distribution |
| aggregated_results_swy_*_preview.png | Preview image | Sub-watershed aggregated results map |
| aggregated_results_swy_*.shp | Download | Sub-watershed summary shapefile with hydrological statistics |

### Result interpretation
- High baseflow areas = important water source conservation zones; protect vegetation
- High quickflow areas = impervious or bare land; potential flood risk zones
- Sub-watershed summary is suitable for direct use in watershed management decisions

### Suggested next steps
- Download aggregated_results_swy_.shp and overlay with land use maps in GIS
- Modify the LULC raster to simulate land use change scenarios
- Combine with Tool 5 or Tool 6 (Crop Production) to analyze agricultural water trade-offs
