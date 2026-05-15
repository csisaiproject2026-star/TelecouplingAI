# New Tools — Local Test Timing Report

Run: `conda run -n TeleCouplingAI pytest backend/tests/test_new_tools.py -v --durations=0`
Result: **17/17 PASSED** | Total: 4.48s

Bugs fixed during this run:
- `ols.py`: White's robust SE matrix broadcast bug (`u2 * x` → `u2[:, np.newaxis] * x`)
- `food_security.py`: `pd.read_csv()` invalid `errors=` kwarg removed
- Test params: CO2 wrong field names (`animals_field` → `animal_count_field`, `distance_field` → `length_km_field`)
- Test data: CBA `input_csv` had overlapping column `cost_usd` — replaced with `projects.csv`

---

## Timing by Tool

| # | Tool | Test Function | Time (s) | Status |
|---|------|---------------|----------|--------|
| 28 | OLS Model Selection | test_ols_basic_run | 1.51 | ✅ |
| 28 | OLS Model Selection | test_ols_model_selection | 0.02 | ✅ |
| 29 | FAMD | test_famd_mixed_run | 1.46 | ✅ |
| 30 | CO2 Emissions | test_co2_basic_run | 0.01 | ✅ |
| 31 | Cost-Benefit Analysis | test_cba_basic_run | 0.01 | ✅ |
| 32 | Population Density | test_population_density_run | 0.01 | ✅ |
| 32 | Population Density | test_population_growth_run | 0.01 | ✅ |
| 33 | Radial Flows | test_radial_flows_run | 0.18 | ✅ |
| 34 | Commodity Trade | test_commodity_trade_run | 0.02 | ✅ |
| 35 | Add Agents | test_add_agents_run | 0.02 | ✅ |
| 36 | Draw Agents Table | test_draw_agents_table_run | 0.02 | ✅ |
| 37 | Add Causes | test_add_causes_run | 0.02 | ✅ |
| 38 | Add Systems | test_add_systems_run | 0.02 | ✅ |
| 39 | Draw Systems Table | test_draw_systems_table_run | 0.02 | ✅ |
| 40 | Add Media Flows | test_media_flows_run | 0.17 | ✅ |
| 41 | Food Security | test_food_security_run | 0.74 | ✅ |
| 42 | Nutrition Metrics | test_nutrition_metrics_run | 0.16 | ✅ |

## Notes

- FAMD (1.46s): R subprocess startup cost; actual computation is negligible
- OLS basic (1.51s): first import of numpy/scipy has cold-start overhead
- Radial Flows / Media Flows (~0.18s): geopandas + shapefile I/O
- Food Security (0.74s): matplotlib chart rendering
- All others < 0.05s
