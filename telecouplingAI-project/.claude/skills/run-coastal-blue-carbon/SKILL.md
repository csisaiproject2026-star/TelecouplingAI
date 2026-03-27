# Skill: run-coastal-blue-carbon

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/cbc_main.py
Import: natcap.invest.coastal_blue_carbon.coastal_blue_carbon as cbc
Reference: references/2 Coastal_Blue_Carbon*.md

invest_args keys:
- landcover_snapshot_csv, landcover_transitions_table, biophysical_table_path
- analysis_year, do_economic_analysis, discount_rate, inflation_rate
- price, use_price_table, price_table_path
- workspace_dir, results_suffix

⚠️ CBC Main outputs are written to workspace_dir/output/ subdirectory — scan only this subdir.
Test data: datainput_for_demo\CoastalBlueCarbon_input\

---

## [PRE_EXECUTION]

**Uploaded files**: If snapshot CSV, transitions CSV, or biophysical table have been uploaded, extract their paths directly — do not ask for them again. Only ask for genuinely missing inputs.

**Parameters to collect**:
- landcover_snapshot_csv: path to snapshots CSV (same file used in Tool 2)
- landcover_transitions_table: path to the **manually edited** transitions CSV (output of Tool 2, edited by user)
- biophysical_table_path: path to biophysical parameters table CSV
- analysis_year: final year of analysis (optional)
- do_economic_analysis: true/false — default false; if true, also collect:
  - discount_rate, inflation_rate
  - price (single carbon price) OR price_table_path (if use_price_table=true)

**Key notes**:
- Before calling this tool, **explicitly confirm** the user has finished manually editing the transitions CSV — if not, stop and remind them to complete editing first
- Economic analysis parameters are only needed when do_economic_analysis=true

---

## [POST_EXECUTION]

### Output file reference

| File | Type | Description |
|------|------|-------------|
| carbon-stock-at-*_preview.png | Preview image | Carbon stock spatial distribution at each time point |
| carbon-stock-at-*.tif | Download | Carbon stock raster; unit: Mg C/pixel |
| carbon-accumulation-*_preview.png | Preview image | Carbon accumulation (positive = sink, negative = source) |
| carbon-emissions-*_preview.png | Preview image | Carbon emissions spatial distribution |
| total-net-carbon-sequestration*_preview.png | Preview image | Total net carbon sequestration over the study period |
| net-present-value*_preview.png | Preview image | Net present value of carbon (only when economic analysis is enabled) |

### Result interpretation
- High carbon stock areas are critical sinks — prioritize for conservation
- Emission areas typically correspond to land use change (e.g. mangroves → aquaculture)
- NPV map can be used directly for policy and investment decisions

### Suggested next steps
- Download TIF files for GIS overlay with administrative boundaries
- Modify the transitions CSV to simulate alternative conservation scenarios and re-run
- Combine with Tool 4 (Seasonal Water Yield) for a comprehensive ecosystem services assessment
