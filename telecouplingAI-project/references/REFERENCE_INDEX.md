# 参考文档索引 — 实现每个工具前必读

## 说明

`references/` 目录下有两类文档，实现步骤 15-20 时必须先读对应文档。

---

## 类型 1：InVEST 官方文档（HTML）

模型原理、公式、数据格式要求。

| 文件 | 对应工具 |
|------|----------|
| `coastal_blue_carbon.html` | 工具 2（CBC Preprocessor）、工具 3（CBC Main）|
| `seasonal_water_yield.html` | 工具 4（SWY）|
| `crop_production.html` | 工具 5（Crop Percentile）、工具 6（Crop Regression）|

---

## 类型 2：Notion 项目文档（Markdown）⭐ 最重要，优先读这个

这是**已在 KNIME/Dify 中跑通的真实代码**，包含：
- 完整的 `invest_args` 字典，键名可直接复用
- 所有 CSV 文件的必需列名
- 内部处理逻辑（10 步）
- 工具 1 的完整 R 脚本

| 文件（文件名含 Notion ID，用 glob 找） | 对应工具 | 最关键内容 |
|---------------------------------------|----------|-----------|
| `1 Coastal_Blue_Carbon_preprocessor*.md` | **工具 2** | Python 代码，`invest_args` 键名，输出目录 `outputs_preprocessor/` |
| `2 Coastal_Blue_Carbon*.md` | **工具 3** | CBC main `invest_args`，经济分析参数 |
| `3 Network_Analysis_Grouping*.md` | **工具 1** | 完整 R 脚本，`in_telecoupling_layer_join` 变量用法 |
| `4 Seasonal_Water_Yield*.md` | **工具 4** | Python 代码，完整参数列表，`precip_dir`/`et0_dir` 说明 |
| `5 Crop_Production_Percentile*.md` | **工具 5** | Python 代码，`model_data_path` 目录结构说明 |
| `6 Crop_Production_Regression*.md` | **工具 6** | Python 代码，`fertilization_rate_table_path` 列名 |

---

## 阶段 B 工具实现步骤对照

```
步骤 15: tools/network_analysis.py + r_scripts/network_analysis.R
         → 先读：references/3 Network_Analysis_Grouping*.md
         → 重点：R 脚本中 in_telecoupling_layer_join 变量，不要硬编码 "ISO_3_code"

步骤 16: tools/cbc_preprocessor.py
         → 先读：references/1 Coastal_Blue_Carbon_preprocessor*.md
         → 重点：invest_args 键名 landcover_snapshot_csv, lulc_lookup_table_path
         → 重点：输出在 workspace_dir/outputs_preprocessor/ 子目录

步骤 17: tools/cbc_main.py
         → 先读：references/2 Coastal_Blue_Carbon*.md
         → 重点：transitions CSV 必须是用户手动编辑后的版本

步骤 18: tools/seasonal_water_yield.py
         → 先读：references/4 Seasonal_Water_Yield*.md
         → 重点：precip_dir/et0_dir 文件命名不符合 InVEST 要求，需 glob+symlink 重命名
         → 重点：precip_gura_N.tif → precip_mN.tif，ET0_gura_N.tif → et0_mN.tif

步骤 19: tools/crop_percentile.py
         → 先读：references/5 Crop_Production_Percentile*.md
         → 重点：model_data_path 始终从 os.environ["MODEL_DATA_PATH"] 读取

步骤 20: tools/crop_regression.py
         → 先读：references/6 Crop_Production_Regression*.md
         → 重点：仅支持 10 种作物，fertilization_rate_table_path 列名
```

---

## invest_args 键名速查（直接从 Notion 代码提取）

### 工具 2 — CBC Preprocessor
```python
invest_args = {
    'landcover_snapshot_csv': path,      # snapshots CSV（列：snapshot_year, raster_path）
    'lulc_lookup_table_path': path,      # lulc lookup CSV（列：lucode, lulc-class, is_coastal_blue_carbon_habitat）
    'results_suffix': '',
    'workspace_dir': output_dir,
}
# 输出在：workspace_dir/outputs_preprocessor/transitions_*.csv
```

### 工具 4 — Seasonal Water Yield
```python
invest_args = {
    'alpha_m': 0.083333,
    'aoi_path': path,
    'beta_i': 1.0,
    'biophysical_table_path': path,      # 列：lucode, CN_A/B/C/D, Kc_1~Kc_12
    'climate_zone_raster_path': '',      # 仅 user_defined_climate_zones=True 时用
    'climate_zone_table_path': '',
    'dem_raster_path': path,
    'et0_dir': tmp_et0_dir,              # ⚠️ 必须是 et0_m1.tif~et0_m12.tif 命名
    'gamma': 1.0,
    'l_path': '',
    'lulc_raster_path': path,
    'monthly_alpha': False,
    'monthly_alpha_path': '',
    'precip_dir': tmp_precip_dir,        # ⚠️ 必须是 precip_m1.tif~precip_m12.tif 命名
    'rain_events_table_path': path,      # 列：month(1-12), events(float)
    'results_suffix': '',
    'soil_group_path': path,
    'threshold_flow_accumulation': 1000,
    'user_defined_climate_zones': False,
    'user_defined_local_recharge': False,
    'workspace_dir': output_dir,
}
```

### 工具 5 — Crop Percentile
```python
invest_args = {
    'aggregate_polygon_path': '',        # 可选
    'landcover_raster_path': path,
    'landcover_to_crop_table_path': path, # 列：lucode(int), crop_name(str)
    'model_data_path': os.environ['MODEL_DATA_PATH'],
    'results_suffix': '',
    'workspace_dir': output_dir,
}
```

### 工具 6 — Crop Regression
```python
invest_args = {
    'aggregate_polygon_path': '',        # 可选
    'fertilization_rate_table_path': path, # 列：crop_name, nitrogen_rate, phosphorus_rate, potassium_rate（kg/ha）
    'landcover_raster_path': path,
    'landcover_to_crop_table_path': path,
    'model_data_path': os.environ['MODEL_DATA_PATH'],  # 与工具5共用
    'results_suffix': '',
    'workspace_dir': output_dir,
}
```
