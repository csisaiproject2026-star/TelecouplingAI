# 开发日志 — 2026-03-16

## 本次工作内容

### 一、测试文件分析与修复

**问题：mock 目标错误**
所有手动测试脚本（`test_network.py`、`test_cbc_pre.py` 等）用 `import shared.utils as _u; _u.generate_output_dir = _mock_gen` 来 mock 输出目录，但各工具用 `from shared.utils import generate_output_dir` 方式导入，导致 mock 不生效，文件跑到 `/data/outputs/` 而非预期的测试目录。

**修复**：改为 mock 各自 tool 模块内的引用：
```python
import tools.network_analysis as _na
_na.generate_output_dir = _mock_gen
```

**新增测试脚本**：
- `test_cbc_main.py` — Tool 3 CBC Main 集成测试
- `test_qgis_zoom.py` — zoom_render 叠加渲染测试
- `test_swy_monthly.py` — SWY 月度文件重命名预检
- `test_imports.py` — 13 模块 import 验证
- `test_crop_reg_validation.py` — 不支持作物拒绝验证
- `test_csv_analyzer.py` — CSV 分析器验证
- `test_output_router.py` — Output Router 文件分类验证
- `test_task_queue.py` — task_queue 分发验证

所有 `python -c "..."` 内联命令已提取为独立 `.py` 文件。

---

### 二、环境配置整合

**问题**：`backend/.env` 和根目录 `.env` 内容重复，`config.py` 只读 `backend/` 下的 `.env`（相对路径）。

**修复**：
- `backend/config.py`：`env_file` 改为绝对路径，指向项目根目录 `.env`
  ```python
  _ENV_FILE = str(Path(__file__).parent.parent / ".env")
  ```
- `backend/.env`：清空，只留注释说明
- 根目录 `.env` 为唯一配置文件（已在 `.gitignore` 中）

---

### 三、model_data_path 改为用户输入

**背景**：`crop_percentile` 和 `crop_regression` 原来从 `settings.MODEL_DATA_PATH`（环境变量）读取 model_data 路径，不符合实际使用场景。

**修改**：
- `model_data_path` 加入两个工具的 `REQUIRED_KEYS`
- `invest_args` 改为从 `params["model_data_path"]` 取值
- 测试脚本 `params` 里补充 `model_data_path`

---

### 四、作物名称动态加载 + 归一化

**问题**：`SUPPORTED_CROPS` 手写列表，与 InVEST model_data 文件名不一致（`oil palm` vs `oilpalm`）。

**修复**（crop_percentile 和 crop_regression 均适用）：
- `get_supported_crops(model_data_path)` — 动态扫描 `climate_*_yield_tables/` 目录，从文件名前缀生成支持列表
- `_normalize(name)` — 归一化函数（小写、去空格和连字符）
- `_rewrite_crop_csv()` — 归一化用户输入的 CSV，原文件不动，写临时文件传给 InVEST
- crop_regression 验证顺序：先校验 `fertilization_rate_table_path`，再做作物校验，最后全量参数校验

---

### 五、CBC Main 仅扫描 output/ 子目录

**问题**：InVEST CBC Main 的目录结构为 `output/`、`intermediate/`、`taskgraph_cache/`，原来扫描整个 workspace 会把几百个中间文件全部渲染。

**修复**：
- `cbc_main.py`：`scan_output_directory` 改为只扫描 `workspace_dir/output/`
- `output_router.py`：`SKIP_DIRS` 扩展覆盖所有 InVEST 中间目录变体：
  ```python
  SKIP_DIRS = {"intermediate_outputs", "intermediate_output", "intermediate", "taskgraph_cache"}
  ```

---

### 六、QGIS zoom_render 新功能

**新增文件**：
- `renderers/qgis_renderer.py`：新增 `zoom_render()` 函数，原有函数不变
- `renderers/_qgis_zoom_render_worker.py`：新 worker，实现叠加渲染

**底图策略**（优先级顺序）：
1. 在线 Google Satellite XYZ 瓦片（有网络时高清）
2. 本地 MBTiles fallback（`data/basemap/world_satellite.mbtiles`，zoom 0-6，35MB）
3. 无底图（两者都失败时只渲染用户图层）

**生成 MBTiles**：
- 在 QGIS 中用 ArcGIS Satellite 底图，Generate XYZ Tiles (MBTiles)
- 参数：全球范围、zoom 0-6、JPG 格式、96 DPI
- 保存至 `data/basemap/world_satellite.mbtiles`（已在 .gitignore 中）

**参数传递方式**：从命令行 JSON 字符串改为临时文件，解决 Windows 路径空格引号问题。

**渲染逻辑**：
- CRS 统一为 EPSG:3857（与 XYZ/MBTiles 一致）
- Extent 取用户图层范围 + padding，自动重投影
- `setLayers([user_layer, basemap_layer])` — 用户层在上，底图在下

---

### 七、output_router 预览图自动生成

**新逻辑**：
- `render_type=qgis` 的文件（SHP/TIF）→ 原文件改为 `download` + 异步生成 `*_preview.png`（`image`）
- 前端同时收到原始文件（下载用）和预览图（展示用）

**异步架构修改**：
- `output_router.py`：新增 `route_outputs_async()`，`route_outputs()` 作为同步 wrapper
- `shared/utils.py`：`scan_output_directory` 改为 `async`
- 6 个工具：`scan_output_directory` 调用全部加 `await`，新增 "Generating previews..." 进度步骤

**解决 event loop 嵌套问题**：
- 工具函数本身是 async，不能用 `loop.run_until_complete()` 嵌套
- 改为直接 `await route_outputs_async()`

---

### 八、QGIS Windows 路径修复

**问题历程**：
1. `FileNotFoundError` — `QGIS_PYTHON_PATH` 默认是 Linux 路径，需要 `.env` 配置
2. `'C:\Program' is not recognized` — `cmd /c` + 列表方式，路径有空格被截断
3. `filename syntax is incorrect` — 手动加引号又被当成路径一部分
4. `QGIS render failed: (empty)` — JSON 参数通过命令行传递，特殊字符被截断

**最终方案**：params 写入临时 JSON 文件，命令行只传文件路径，彻底绕开引号问题。

---

### 九、单元测试更新

**`test_renderers.py`**：
- `TestRouteOutputs` 新增 4 个测试，mock `_generate_preview` 避免 QGIS 调用
- 更新断言：`qgis` → `download`，新增 `image` 类型验证

**`test_tools.py`**：
- 新增 `TestCBCMain`（3 个测试）
- `TestCropPercentile/Regression`：改为测试 `get_supported_crops()` 动态加载

**`test_utils.py`**：
- `build_result_urls` 测试更新为新的 `download`/`image` 类型

---

## 下次继续

- [ ] 运行完整测试套件（pytest A + 手动测试 B-K）确认所有修改正常工作
- [ ] 验证各工具预览图生成效果（特别是 SWY、CBC Main、Crop）
- [ ] 前端集成：如何展示 `image` 类型 vs `download` 类型
- [ ] Docker 部署配置验证

---

## AI 协作教训（2026-03-16）

**来自 Project 对话里犯的错误，下次务必遵守：**

1. **写 DEV_LOG 前必须先读原文件**，直接覆盖会丢失历史记录。
   正确做法：`read_text_file` → 追加内容 → `write_file`

2. **删改任何文件前先说明意图，确认后再执行**，不能想当然动手。

3. **读 DEV_LOG 要认真读完**，特别是"下次继续"的待办项，不能走马观花就乱说测试状态。

4. **有疑问先把相关文档读完再开口**，不能自相矛盾来回绕圈。

**每次新对话开始时的固定流程**：
1. 先读 DEV_LOG 恢复完整上下文
2. 读 manual_test_guide.md 了解当前测试状态
3. 确认待办项后再开始工作
4. 任何删改操作先说明意图，确认后执行
5. 重大改动结束后先读原 DEV_LOG，再追加新内容

---

## 工作流总结

**Claude Code 负责搭骨架** → **Claude Chat 打磨细节** → **人工确认**

Code 阶段产出功能完整但未经真实环境验证的初版；Chat 阶段结合实际运行结果修复细节问题（平台差异、命名不一致、异步陷阱等）。这是目前 AI 辅助开发的最佳实践模式。
