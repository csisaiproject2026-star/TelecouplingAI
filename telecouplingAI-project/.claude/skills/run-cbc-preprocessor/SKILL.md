# Skill: run-cbc-preprocessor

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/cbc_preprocessor.py
Import: natcap.invest.coastal_blue_carbon.preprocessor as cbc_pre
Reference: references/1 Coastal_Blue_Carbon_preprocessor*.md

invest_args keys:
- landcover_snapshot_csv (columns: snapshot_year int, raster_path str)
- lulc_lookup_table_path (columns: lucode int, lulc-class str, is_coastal_blue_carbon_habitat bool)
- results_suffix: ''
- workspace_dir

⚠️ Outputs are written to workspace_dir/outputs_preprocessor/ — NOT the root workspace dir.
Test data: datainput_for_demo\CoastalBLueCarbonPreprocessor_input\ (note capital L)

---

## [PRE_EXECUTION]

**Uploaded files**: If snapshot CSV or LULC lookup table have been uploaded, extract their paths directly — do not ask for them again. Only ask for genuinely missing inputs.

**Parameters to collect**:
- landcover_snapshot_csv: path to snapshot CSV with two columns — snapshot_year (integer year) and raster_path (path to the LULC raster for that year)
- landcover_lookup_table: path to LULC lookup CSV with columns — lucode (integer), lulc-class (name), is_coastal_blue_carbon_habitat (true/false)

**Key notes**:
- If the user already has a manually edited transitions CSV from a previous run, skip this tool and proceed directly to Tool 3

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| transitions_*.csv | Table | LULC transition matrix — **requires manual editing before use in Tool 3** |
| carbon_pool_transient_template_*.csv | Table | Carbon pool template for entering carbon stock parameters per land class |
| aligned_lulc_*_preview.png | Preview image | Aligned land use raster overlaid on satellite basemap |
| aligned_lulc_*.tif | Download | Aligned LULC raster file |

### ⚠️ Critical warning — must tell the user
**transitions_*.csv requires manual editing before it can be used in Tool 3.**

The user must open the file and change transition type values from `disturb` to one of:
- `low-impact-disturb`
- `med-impact-disturb`
- `high-impact-disturb`

### Suggested next steps
1. Download and manually edit transitions_*.csv as described above
2. Fill in carbon stock values in carbon_pool_transient_template_*.csv
3. Run Tool 3 (Coastal Blue Carbon) once editing is complete
