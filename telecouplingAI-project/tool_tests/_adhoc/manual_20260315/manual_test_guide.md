# CSIS 后端手动测试指南

**日期：** 2026-03-15
**测试范围：** 6 个工具实现 + 渲染器 + 共享工具 + Celery 任务队列
**前置条件：** conda 环境 `TeleCouplingAI` 已配置

---

## 准备工作

### 1. 打开终端，激活 conda 环境

```bash
conda activate TeleCouplingAI
cd C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend
```

### 2. 创建测试输出目录

```bash
mkdir -p C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs
```

后续统一用 `TEST_OUT` 表示此目录：
```
set TEST_OUT=C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\adhoc_test\manual_test_20260315\outputs
```

---

## 测试 A：自动化 pytest（约 4 秒）

最简单的验证，确认代码可以 import 且基本逻辑正确。

```bash
cd C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend
python -m pytest tests/ -v
```

**期望结果：** all passed, 0 failed（可能有 1 个 FutureWarning 关于 gdal.UseExceptions，可忽略）

---

## 测试 B：逐模块 import 验证

```bash
python ..\adhoc_test\manual_test_20260315\test_imports.py
```

**期望结果：** `All 13 modules imported OK`

---

## 测试 C：工具 1 — Network Analysis（R 脚本）

> ⚠️ 需要已安装 R 和 igraph 等 R 包。如果没装 R，跳过此测试。

### C.1 验证 R 可用

```bash
Rscript --version
```

如果报错 "Rscript not found"，需要先安装 R 并确保在 PATH 中。

### C.2 运行网络分析工具

```bash
python ..\adhoc_test\manual_test_20260315\test_network.py
```

**期望结果：**
- 输出 "Network Analysis completed successfully"
- 在 `%TEST_OUT%\network\` 下生成：
  - `network_plot_manual_test.pdf` — 网络图 PDF（供下载）
  - `network_stats_manual_test.csv` — 度/接近性/中介性统计（表格展示）
  - `output_manual_test.shp` — 带 cluster_N 列的 shapefile（供下载）
  - `output_manual_test_preview.png` — shp 叠加卫星底图的预览图（前端展示）
- 用 Excel 打开 `network_stats_manual_test.csv` 检查有 degree/closeness/betweenness 三列

---

## 测试 D：工具 2 — CBC Preprocessor

```bash
python ..\adhoc_test\manual_test_20260315\test_cbc_pre.py
```

**期望结果：**
- 输出 "CBC Preprocessor completed successfully"
- 输出包含 warning 消息："transitions CSV requires manual editing"
- 在输出目录下生成：
  - `transitions_*.csv` — 过渡矩阵（表格展示）
  - `carbon_pool_transient_template_*.csv` — 碳池模板（表格展示）
  - `aligned_lulc_*.tif` — 对齐后的土地利用栅格（供下载）
  - `aligned_lulc_*_preview.png` — tif 叠加卫星底图的预览图（前端展示）

---

## 测试 D2：工具 3 — CBC Main

```bash
python ..\adhoc_test\manual_test_20260315\test_cbc_main.py
```

**期望结果：**
- 输出 "CBC Main completed successfully"
- 在 `%TEST_OUT%\cbc_main\` 下生成：
  - `carbon_stock_at_*.tif` — 各年份碳储量栅格（供下载）
  - `carbon_stock_at_*_preview.png` — 对应预览图（前端展示）
  - `carbon-accumulation-*.tif` 等其他栅格文件及对应预览图

---

## 测试 E：工具 4 — Seasonal Water Yield

### E.1 验证月度文件重命名逻辑

```bash
python ..\adhoc_test\manual_test_20260315\test_swy_monthly.py
```

**期望结果：** 12 个月都显示 OK，最后输出 "All 12 months verified successfully"

### E.2 运行完整 SWY 模型

```bash
python ..\adhoc_test\manual_test_20260315\test_swy.py
```

**期望结果：**
- 输出 "SWY completed successfully"
- 在输出目录下生成：
  - `QF_*.tif`, `B_*.tif`, `L_*.tif` 等栅格文件（供下载）
  - 各栅格对应的 `*_preview.png` 预览图（前端展示）
  - `aggregated_results_swy_*.shp` — 汇总结果 shapefile（供下载）
  - `aggregated_results_swy_*_preview.png` — shp 预览图

> ⚠️ SWY 模型运行较慢（可能需要 1-5 分钟），请耐心等待。

---

## 测试 F：工具 5 — Crop Production Percentile

```bash
python ..\adhoc_test\manual_test_20260315\test_crop_pct.py
```

**期望结果：**
- 输出 "Crop Percentile completed successfully"
- 在输出目录下生成：
  - `result_table_*.csv` — 汇总表（表格展示）
  - `*_yield_*percentile_*.tif` — 产量栅格（供下载）
  - `*_yield_*percentile_*_preview.png` — 栅格预览图（前端展示）

---

## 测试 G：工具 6 — Crop Regression + SUPPORTED_CROPS 验证

### G.1 验证不支持的作物被拒绝

```bash
python ..\adhoc_test\manual_test_20260315\test_crop_reg_validation.py
```

**期望结果：** 输出 "Correctly rejected" 和 "SUPPORTED_CROPS validation works!"

### G.2 运行完整 Crop Regression

```bash
python ..\adhoc_test\manual_test_20260315\test_crop_reg.py
```

**期望结果：**
- 输出 "Crop Regression completed successfully"
- 在输出目录下生成：
  - `result_table_*.csv` — 汇总表（表格展示）
  - `*_regression_production_*.tif` — 产量栅格（供下载）
  - `*_regression_production_*_preview.png` — 栅格预览图（前端展示）

---

## 测试 H：QGIS 渲染器

> ⚠️ 需要 QGIS 3.40.14 已安装在 `C:\Program Files\QGIS 3.40.14\`

### H.1 基础渲染（render_file）

```bash
python ..\adhoc_test\manual_test_20260315\test_qgis.py
```

**期望结果：**
- 输出 "QGIS render OK"
- 在 `%TEST_OUT%\qgis\` 下生成 `dem_render.png`

### H.2 世界底图叠加渲染（zoom_render）

```bash
python ..\adhoc_test\manual_test_20260315\test_qgis_zoom.py
```

**期望结果：**
- 输出 "zoom_render completed successfully"
- 在 `%TEST_OUT%\qgis\` 下生成：
  - `zoom_render_shp.png` — 流域 shapefile 叠加卫星底图，zoom 到非洲区域
  - `zoom_render_tif.png` — DEM 栅格叠加卫星底图
- 有网络时底图为 Google Satellite 高清卫星图；无网络时自动切换到本地 MBTiles（`data/basemap/world_satellite.mbtiles`）

---

## 测试 I：CSV 分析器

```bash
python ..\adhoc_test\manual_test_20260315\test_csv_analyzer.py
```

**期望结果：** 显示 columns = ['CODE', 'larrivals.sender', 'larrivals.receiver']，chart_config 不为 None

---

## 测试 J：Output Router 分类

```bash
python ..\adhoc_test\manual_test_20260315\test_output_router.py
```

**期望结果：** 8 个全部 OK

---

## 测试 K：task_queue — task_id 传递验证

```bash
python ..\adhoc_test\manual_test_20260315\test_task_queue.py
```

**期望结果：** 两条消息都正常输出，最后显示 "task_queue dispatch OK"

---

## 结果检查清单

完成上述测试后，在下表中记录结果：

| 测试 | 描述 | 结果 |
|------|------|------|
| A | pytest all tests | ☐ 通过 / ☐ 失败 |
| B | 13 模块 import | ☐ 通过 / ☐ 失败 |
| C | Network Analysis (R) | ☐ 通过 / ☐ 跳过(无R) / ☐ 失败 |
| D | CBC Preprocessor | ☐ 通过 / ☐ 失败 |
| D2 | CBC Main | ☐ 通过 / ☐ 失败 |
| E.1 | SWY 月度文件重命名 | ☐ 通过 / ☐ 失败 |
| E.2 | SWY 完整运行 | ☐ 通过 / ☐ 失败 |
| F | Crop Percentile | ☐ 通过 / ☐ 失败 |
| G.1 | Crop Regression 作物验证 | ☐ 通过 / ☐ 失败 |
| G.2 | Crop Regression 完整运行 | ☐ 通过 / ☐ 失败 |
| H.1 | QGIS 基础渲染 | ☐ 通过 / ☐ 跳过(无QGIS) / ☐ 失败 |
| H.2 | QGIS zoom_render 叠加渲染 | ☐ 通过 / ☐ 跳过(无QGIS) / ☐ 失败 |
| I | CSV 分析器 | ☐ 通过 / ☐ 失败 |
| J | Output Router 分类 | ☐ 通过 / ☐ 失败 |
| K | task_queue 分发 | ☐ 通过 / ☐ 失败 |

---

## 文件输出规则说明

每个工具输出的 SHP/TIF 文件会有两个版本：

| 文件类型 | render_type | 用途 |
|---|---|---|
| 原始 `.shp` / `.tif` | `download` | 供用户下载，用于 GIS 分析 |
| `*_preview.png` | `image` | 前端直接展示，叠加卫星底图 |

原始文件和预览图共存于同一输出目录，互不影响。

---

## 常见问题

**Q: `ModuleNotFoundError: No module named 'natcap'`**
A: 确认 conda 环境已激活：`conda activate TeleCouplingAI`

**Q: `Rscript not found`**
A: 安装 R 并添加到 PATH，或跳过测试 C

**Q: QGIS 渲染超时或报错**
A: 检查根目录 `.env` 中 `QGIS_PYTHON_PATH` 是否指向正确的 `python-qgis-ltr.bat`

**Q: zoom_render 底图模糊或无底图**
A: 检查网络连接。有网络时自动使用 Google Satellite 高清底图；无网络时使用本地 `data/basemap/world_satellite.mbtiles`（zoom 0-6，全球低精度）。

**Q: Crop Percentile/Regression 报 model_data_path 错误**
A: 在 params 中传入正确的 model_data 路径，例如：
`datainput_for_demo/CropProductionPercentile_input/model_data`
