# CSIS Platform — Unified Tool Test Directory

This directory contains one subfolder per tool (42 tools total).

## Structure

```
tool_tests/
├── 01_network_analysis/
│   ├── testdata/        ← input files (CSV or README pointing to datainput_for_demo/)
│   ├── output/          ← run outputs land here (.gitkeep keeps folder in git)
│   └── how_to_test.bat  ← step-by-step test guide (open in editor to read)
├── 02_coastal_blue_carbon_preprocessor/
│   └── ...
...
```

## Quick Guide

### InVEST Tools (01–27)
Demo data lives in `../datainput_for_demo/`. The `testdata/README.md` in each folder
shows which files to upload and what prompt to send.

### New Non-InVEST Tools (28–42)
Actual sample CSV (and HTML) files are in `testdata/`. Upload via the web UI or
run directly with Python using the command shown in `how_to_test.bat`.

## Tool Index

| # | Folder | Tool Call Name |
|---|--------|---------------|
| 01 | network_analysis | run_network_analysis_grouping |
| 02 | coastal_blue_carbon_preprocessor | run_coastal_blue_carbon_preprocessor |
| 03 | coastal_blue_carbon | run_coastal_blue_carbon |
| 04 | seasonal_water_yield | run_seasonal_water_yield |
| 05 | crop_production_percentile | run_crop_production_percentile |
| 06 | crop_production_regression | run_crop_production_regression |
| 07 | carbon_storage | run_carbon_storage |
| 08 | habitat_quality | run_habitat_quality |
| 09 | annual_water_yield | run_annual_water_yield |
| 10 | forest_carbon_edge_effect | run_forest_carbon_edge_effect |
| 11 | crop_pollination | run_crop_pollination |
| 12 | delineateit | run_delineateit |
| 13 | routedem | run_routedem |
| 14 | sdr | run_Sediment_Delivery_Ratio_SDR |
| 15 | ndr | run_ndr |
| 16 | urban_cooling | run_urban_cooling |
| 17 | urban_flood | run_urban_flood_risk_mitigation |
| 18 | urban_stormwater | run_urban_stormwater_retention |
| 19 | urban_nature_access | run_urban_nature_access |
| 20 | urban_mental_health | run_urban_mental_health |
| 21 | scenic_quality | run_scenic_quality |
| 22 | hra | run_habitat_risk_assessment |
| 23 | wave_energy | run_wave_energy_production |
| 24 | coastal_vulnerability | run_coastal_vulnerability |
| 25 | wind_energy | run_offshore_wind_energy |
| 26 | recreation | run_recreation_tourism |
| 27 | scenario_gen_proximity | run_scenario_gen_proximity |
| 28 | ols | run_model_selection_ols |
| 29 | famd | run_factor_analysis_mixed_data |
| 30 | co2_emissions | run_co2_emissions |
| 31 | cost_benefit_analysis | run_cost_benefit_analysis |
| 32 | population_density | run_population_count_density |
| 33 | radial_flows | run_draw_radial_flows |
| 34 | commodity_trade | run_commodity_trade |
| 35 | add_agents | run_add_agents_interactively |
| 36 | draw_agents_table | run_draw_agents_from_table |
| 37 | add_causes | run_add_causes_interactively |
| 38 | add_systems | run_add_systems_interactively |
| 39 | draw_systems_table | run_draw_systems_from_table |
| 40 | add_media_flows | run_add_media_flows |
| 41 | food_security | run_food_security |
| 42 | nutrition_metrics | run_nutrition_metrics |
