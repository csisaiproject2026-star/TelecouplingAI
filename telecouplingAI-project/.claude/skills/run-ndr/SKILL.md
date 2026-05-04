# Skill: run-ndr

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/ndr.py
Import: natcap.invest.ndr.ndr
Tool name: run_ndr

invest_args keys:
- workspace_dir
- dem_path (required)
- lulc_path (required)
- runoff_proxy_path (required; precipitation or runoff raster, mm/yr)
- watersheds_path (required; polygon shapefile with 'ws_id')
- biophysical_table_path (required; columns: lucode, load_n and/or load_p, eff_n and/or eff_p, crit_len_n and/or crit_len_p)
  NOTE: must NOT have load_type_n / load_type_p columns (3.17.x format incompatible with 3.14.3)
- threshold_flow_accumulation (required int)
- k_param (float; default 2)
- calc_n (bool; default True)
- calc_p (bool; default False)
- subsurface_critical_length_n (float; default 150 m; if calc_n=True)
- subsurface_eff_n (float; default 0.8; if calc_n=True)
- subsurface_critical_length_p (float; default 150 m; if calc_p=True)
- subsurface_eff_p (float; default 0.8; if calc_p=True)

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first.

**Required parameters**:
- dem_path: digital elevation model raster (meters, projected CRS)
- lulc_path: land use / land cover raster
- runoff_proxy_path: raster representing water runoff or precipitation (mm/year) — drives nutrient transport
- watersheds_path: watershed boundary shapefile (must have 'ws_id' integer field)
- biophysical_table_path: CSV with lucode and nutrient-specific columns — ask user which nutrients they need (N, P, or both), then confirm the table has the appropriate columns (load_n, eff_n, crit_len_n for nitrogen; load_p, eff_p, crit_len_p for phosphorus)
- threshold_flow_accumulation: integer defining stream network (e.g. 1000)

**Nutrient selection** (ask the user):
- calc_n: model nitrogen delivery (default True)
- calc_p: model phosphorus delivery (default False; requires P columns in biophysical table)
- At least one must be True

**Optional subsurface parameters** (use defaults unless user has data):
- subsurface_critical_length_n/p: travel length (m) for subsurface flow attenuation (default 150)
- subsurface_eff_n/p: subsurface nutrient removal efficiency (0–1; default 0.8)

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| n_export.tif | Download | Nitrogen export to streams per pixel (kg/ha/yr); present if calc_n=True |
| p_export.tif | Download | Phosphorus export to streams per pixel (kg/ha/yr); present if calc_p=True |
| n_retention.tif | Download | Nitrogen retained on landscape (kg/ha/yr) |
| p_retention.tif | Download | Phosphorus retained on landscape (kg/ha/yr) |
| watershed_results_ndr_n.shp | Download | Per-watershed nitrogen totals |
| watershed_results_ndr_p.shp | Download | Per-watershed phosphorus totals |
| watershed_results_ndr_n.csv | Table | Tabular nitrogen results per watershed |
| watershed_results_ndr_p.csv | Table | Tabular phosphorus results per watershed |

### Domain knowledge — understanding NDR outputs

**How nutrient delivery works**:
- Each pixel generates a nutrient load (from biophysical table: load_n/load_p in kg/ha/yr)
- As nutrient moves downslope toward the stream, vegetation on each pixel removes a fraction (efficiency eff_n/p)
- The NDR (Nutrient Delivery Ratio) is the fraction of the load that actually reaches the stream
- n_export = load × NDR — accounting for both surface and subsurface flow pathways

**n_export.tif / p_export.tif**:
- High values: high-load land uses (fertilized cropland, urban) with high connectivity to streams
- Low values: forests, wetlands, or upslope positions far from streams
- Hotspots near streams are most directly controlled by riparian buffer restoration

**n_retention / p_retention**:
- Shows where the landscape naturally filters nutrients before they reach waterways
- High retention in forested riparian zones — these areas provide the greatest water quality service
- Reducing this retention (e.g. by clearing riparian forest) directly increases downstream nutrient loads

**Watershed summary (CSV)**:
- total_load: total nutrient inputs to the watershed (no retention)
- total_export: nutrient reaching the outlet after landscape filtration
- total_retention_eff: watershed-level retention efficiency (%)
- A watershed with low efficiency is dominated by poorly buffered high-load areas

**Calibration**:
- Calibrate against observed stream nutrient concentrations at gauging stations
- Adjust load_n/load_p in the biophysical table if modeled exports are systematically high or low

### Suggested next steps
- Download n_export.tif to identify nutrient pollution hotspots
- Review watershed_results_ndr_n.csv to rank watersheds by nitrogen load for targeted intervention
- Install riparian buffers in high-export areas near streams to reduce downstream loads
- Combine with Annual Water Yield (run_annual_water_yield) for integrated water quantity + quality assessment
- Combine with SDR (run_sdr) for simultaneous sediment and nutrient management planning
