# Input-Validation Pre-Flight — Comprehensive Test Report

**Feature under test:** the new pre-flight input validation added this session
- **Step 1** `validate_file_params_exist` — existence check (forgot to upload / wrong path) for every tool
- **Step 2** `validate_input_files` + `TOOL_FILE_SPECS` — file-type check (raster / vector / table / html) for **all 41 file-taking tools**
- Plus the **Wave Energy routing fix** (optional param no longer wrongly demanded)

**Servers tested:** GCP `34.42.83.50` **and** MSU `35.9.219.33` (both, baked into the running images)
**Date:** 2026-05-29

---

## Bottom line

| Server | Tools | Test cases | Pass | Fail |
|---|---|---|---|---|
| **GCP** | 41 | **359** | **359** | **0** |
| **MSU** | 41 | **359** | **359** | **0** |

**Every tool, every case, on both servers: PASS.** The validation correctly
**allows** valid inputs and **blocks** all three error conditions with a clear,
user-facing message.

---

## 1. Method — what each tool was tested against

The test drives the exact two functions `agent.py` runs before dispatching a
tool, for **every tool** and **every required file parameter**:

| Case | Input | Expected |
|---|---|---|
| **correct** | all params point at valid files of the right type | **ALLOW** (no error) |
| **missing** | a required file param omitted | **BLOCK** — "required … is missing" |
| **wrong-path** | a required param → a path that does not exist | **BLOCK** — "file not found / not uploaded" |
| **wrong-type** | a required param → a real file of the WRONG type (e.g. a CSV in a raster slot) | **BLOCK** — "expected a raster file …" |

Validation checks existence + extension only, so empty placeholder files of each
type exercise the full logic deterministically (no model runs, no Gemini).
Total = 41 correct-cases + 106 required file-params × 3 error-cases = **359 cases**.

---

## 2. Per-tool results (identical on GCP and MSU)

Each tool's cases = 1 (correct) + 3 × (number of required file params). GCP and MSU produced identical results.

| # | Tool (function) | Req. file params | Cases | Verdict |
|---|---|---|---|---|
| 1 | run_habitat_quality | 3 | 10 | ✅ ALL PASS |
| 2 | run_carbon_storage | 2 | 7 | ✅ ALL PASS |
| 3 | run_annual_water_yield | 7 | 22 | ✅ ALL PASS |
| 4 | run_Sediment_Delivery_Ratio_SDR | 6 | 19 | ✅ ALL PASS |
| 5 | run_ndr | 5 | 16 | ✅ ALL PASS |
| 6 | run_seasonal_water_yield | 6 | 19 | ✅ ALL PASS |
| 7 | run_forest_carbon_edge_effect | 3 | 10 | ✅ ALL PASS |
| 8 | run_crop_pollination | 3 | 10 | ✅ ALL PASS |
| 9 | run_urban_cooling | 4 | 13 | ✅ ALL PASS |
| 10 | run_urban_flood_risk_mitigation | 4 | 13 | ✅ ALL PASS |
| 11 | run_urban_nature_access | 4 | 13 | ✅ ALL PASS |
| 12 | run_crop_production_percentile | 2 | 7 | ✅ ALL PASS |
| 13 | run_network_analysis_grouping | 3 | 10 | ✅ ALL PASS |
| 14 | run_crop_production_regression | 3 | 10 | ✅ ALL PASS |
| 15 | run_delineateit | 1 | 4 | ✅ ALL PASS |
| 16 | run_routedem | 1 | 4 | ✅ ALL PASS |
| 17 | run_urban_stormwater_retention | 4 | 13 | ✅ ALL PASS |
| 18 | run_urban_mental_health | 4 | 13 | ✅ ALL PASS |
| 19 | run_scenario_gen_proximity | 1 | 4 | ✅ ALL PASS |
| 20 | run_scenic_quality | 3 | 10 | ✅ ALL PASS |
| 21 | run_coastal_vulnerability | 6 | 19 | ✅ ALL PASS |
| 22 | run_coastal_blue_carbon_preprocessor | 2 | 7 | ✅ ALL PASS |
| 23 | run_coastal_blue_carbon | 3 | 10 | ✅ ALL PASS |
| 24 | run_habitat_risk_assessment | 3 | 10 | ✅ ALL PASS |
| 25 | run_wave_energy_production | 2 | 7 | ✅ ALL PASS |
| 26 | run_offshore_wind_energy | 4 | 13 | ✅ ALL PASS |
| 27 | run_model_selection_ols | 1 | 4 | ✅ ALL PASS |
| 28 | run_co2_emissions | 1 | 4 | ✅ ALL PASS |
| 29 | run_cost_benefit_analysis | 2 | 7 | ✅ ALL PASS |
| 30 | run_food_security | 1 | 4 | ✅ ALL PASS |
| 31 | run_factor_analysis_mixed_data | 1 | 4 | ✅ ALL PASS |
| 32 | run_commodity_trade | 1 | 4 | ✅ ALL PASS |
| 33 | run_nutrition_metrics | 1 | 4 | ✅ ALL PASS |
| 34 | run_population_count_density | 1 | 4 | ✅ ALL PASS |
| 35 | run_draw_radial_flows | 1 | 4 | ✅ ALL PASS |
| 36 | run_add_agents_interactively | 1 | 4 | ✅ ALL PASS |
| 37 | run_draw_agents_from_table | 1 | 4 | ✅ ALL PASS |
| 38 | run_add_causes_interactively | 1 | 4 | ✅ ALL PASS |
| 39 | run_add_systems_interactively | 1 | 4 | ✅ ALL PASS |
| 40 | run_draw_systems_from_table | 1 | 4 | ✅ ALL PASS |
| 41 | run_add_media_flows | 2 (html_file + country_reference_csv) | 7 | ✅ ALL PASS |
|  | **Total** | **106** | **359** | **✅ 359/359** |

> **All 41 active tools are covered** — including the add_*/draw_* tools, which
> (despite the "interactively" name) actually read an uploaded CSV. The only tools
> without a file spec are `render_spatial_file` / `read_file_content` (they act on
> already-produced output files) and Recreation (disabled). Every tool also still
> runs `validate_required` + the generic existence check.

---

## 3. Sample of the actual user-facing messages (verified)

**Missing required file (forgot to upload):**
```
The model cannot run because of a problem with the input files:
- 'lulc_cur_path': required raster file is missing — please upload it.
```

**Wrong path (typo / not uploaded):**
```
The tool cannot run because some input files are missing:
- 'lulc_cur_path': file not found (NOT_UPLOADED.tif) — it may not have been uploaded, or the path is wrong.
```

**Wrong file type (e.g. a CSV dropped into a raster slot):**
```
The model cannot run because of a problem with the input files:
- 'lulc_cur_path': expected a raster file (.tif/.tiff/.img/.vrt/.bil/.hgt), but got 'dummy.csv'.
```

All errors carry `error_code = VALIDATION_ERROR`, are path-sanitized (no internal
server paths leak), and flow to the user **and** back to Gemini (which explains
them) via the existing error channel.

---

## 4. Correct-case (happy path) end-to-end coverage

Beyond the 41 "correct → allow" validation cases above, real tool execution on
valid data was verified separately this session:
- Full 41-tool LLM-path regression on GCP: **40 PASS / 1 SKIP** before the Wave
  Energy fix; with that fix it is now **41 PASS / 1 SKIP** (#26 Recreation is a
  designed skip).
- Direct InVEST runs on MSU after the image rebuild: Carbon, Habitat (2 files),
  SDR (11 files), NDR (4 files), CBC Preprocessor — all PASS, producing outputs.

So valid inputs run the models; invalid inputs are blocked with a clear message.

---

## 5. Honest limits

- **Semantic** wrong files (correct format but wrong region/year, e.g. a valid
  raster of the wrong study area) cannot be auto-detected — only structural
  errors (missing / wrong-path / wrong-type / wrong CSV column-by-extension) are.
- Directory params (precip_dir, et0_dir, wave_base_data_path) and params with
  built-in server defaults (wave/wind bathymetry & land polygon) are intentionally
  not type-checked, to avoid false positives.
- The 359-case suite tests the validation **logic** directly (the exact deployed
  functions). The agent→user glue was verified separately (habitat broken-input
  surfaced the message end-to-end).

---

## 6. Conclusion

The new input-validation feature is **fully verified on both GCP and MSU**:
- ✅ 41 tools, 359 cases, **359/359 PASS on each server**
- ✅ valid inputs allowed; missing / wrong-path / wrong-type all blocked with clear messages
- ✅ baked into both production images (survives container recreate)
