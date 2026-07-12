# CSIS Ecosystem Intelligence Platform
# Complete Project Specification for Claude Code
# Version 4.4 — Skeleton-First Strategy（含已有代码分析 + Docker/Linux 部署 + 工程规范）

---

## ⚡ 给 Claude Code 的阅读指南

**你的工作分两个阶段：**

- **阶段 A（骨架生成）：** 读完整个文档，基于已有代码创建缺失文件的骨架，每个函数只写签名 + 类型注解 + `raise NotImplementedError`。目标是让完整项目能启动、能 import、docker-compose up 不报错。同时创建 `.claude/skills/` 下的 6 个 SKILL.md 文件（见 Section 16）。

- **阶段 B（逐文件填充）：** 每次对话只实现一个文件。用户会告诉你当前要填充哪个文件，你只修改那一个文件，不动其他任何文件。

**token 节省规则：**
- 阶段 B 每次对话只需携带：当前文件骨架 + 本文档对应 Section
- 不需要每次都带整个文档
- 每个文件实现完立即运行对应测试验证

**⚠️ 实现工具 1-6（步骤 15-20）前，必须先读参考文档索引：**
`references/REFERENCE_INDEX.md` — 包含每个工具对应的 Notion 文档路径、`invest_args` 键名速查、关键注意事项

---

## 🐍 Conda 环境规格

> **⚠️ 关键：后端所有 Python 代码必须在 conda 环境 `TeleCouplingAI` 中运行。**

### 激活方式

```bash
conda activate TeleCouplingAI
```

### 已安装的包（conda-forge）

```
gdal=3.10.3, geos=3.14.1, proj=9.7.1, geopandas=1.1.2, rasterio=1.4.4, shapely=2.1.2
numpy=2.4.1, pandas=2.3.3, scikit-learn=1.8.0, matplotlib=3.10.8, networkx=3.6.1
fastapi=0.128.0, uvicorn=0.40.0, pydantic=2.10.6
```

### 已安装的包（pip）

```
natcap.invest==3.14.3  ← 工具 2-6 核心依赖 ✅
pygeoprocessing==2.4.10, python-multipart==0.0.21, aiofiles==3.13.3
```

### 还需要 pip install

```bash
conda activate TeleCouplingAI
pip install anthropic celery redis aiohttp pydantic-settings
```

### 本地开发运行方式

```bash
# 后端
conda activate TeleCouplingAI
cd C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend
python main.py

# Celery worker（单独终端）
conda activate TeleCouplingAI
cd C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend
celery -A workers.task_queue worker --concurrency=2 --loglevel=info

# 验证 natcap.invest
conda activate TeleCouplingAI
python -c "import natcap.invest; print('invest OK:', natcap.invest.__version__)"
# 期望：invest OK: 3.14.3
```

---

## ✅ 已有代码现状分析

> **重要：** 项目已有可运行代码，位于：
> `C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\`
>
> **Claude Code 必须先读懂已有代码，再决定哪些需要新建、哪些需要改造。**

### 已完成、可直接复用 ✅

**前端（React + Vite，`frontend/`）：**
- `src/App.jsx` — 完整聊天界面：渐变 "Hi, CSIS" 标题、侧边栏、消息气泡、输入栏、Settings 弹窗 ✅
- `package.json` — React 18 + Vite + Tailwind + lucide-react ✅
- `Dockerfile` — 两阶段构建（Node build → Nginx）✅

**后端（FastAPI，`backend/`）：**
- `main.py` — FastAPI 基础结构、CORS ✅（Gemini API，需改为 Claude）
- `config.py` — pydantic-settings 模式 ✅（需加 ANTHROPIC_API_KEY）
- `Dockerfile` — condaforge/miniforge3，已安装 natcap.invest ✅（需追加新包）

### 需要改造 ⚠️

- `frontend/src/App.jsx`：换 Claude 模型、改为 SSE、扩展 6 张卡片、新消息类型、**API 路径从 `/chat` 改为 `/api/chat`**
- `backend/main.py`：移除 Gemini，改用 anthropic SDK，加 SSE/upload/health 端点
- `backend/config.py`：移除 `GOOGLE_API_KEY`，加入 Claude 相关配置
- `backend/requirements.txt`：**已重写（移除了 langchain-google-genai/langgraph 等 Gemini 依赖）** ✅
- `backend/Dockerfile`：追加 `anthropic celery redis aiohttp pydantic-settings`，**修复 CMD（当前被注释掉了）**

### 需要清理/忽略 🗑️

> **以下是旧版本的残留空目录和文件，不属于新架构，阶段 A 中应忽略它们：**
- `backend/agents/` — 空目录，旧版本残留，新的 agent 逻辑在 `backend/agent.py`
- `backend/app/` — 空目录，旧版本残留
- `backend/database/` — 空目录，旧版本 LangGraph SQLite 残留，不再使用
- `backend/test_gemini.py` — Gemini 测试脚本，不再需要

### 需要全新创建 🆕

后端新增模块（tools、renderers、workers、shared）、nginx SSE 配置、Redis 服务、`.claude/skills/` 下的 6 个 Agent Skills。

---

## 目录

- [1. 项目概览](#1-项目概览)
- [2. 完整目录结构](#2-完整目录结构)
- [3. 本地环境信息](#3-本地环境信息)
- [4. 骨架生成清单](#4-骨架生成清单)
- [5. 填充顺序与依赖图](#5-填充顺序与依赖图)
- [6. 前端改造规格](#6-前端改造规格)
- [7. 后端 API 规格](#7-后端-api-规格)
- [8. Agent 系统提示词](#8-agent-系统提示词)
  - [8.5 Claude Tool Use JSON Schema](#85-claude-tool-use-json-schema)
  - [8.6 Agent 主循环逻辑](#86-agent-主循环逻辑)
- [9. 6 个工具实现规格](#9-6-个工具实现规格)
- [10. QGIS 渲染规格](#10-qgis-渲染规格)
- [11. Celery SSE 回传规格](#11-celery-sse-回传规格)
- [12. 共享工具函数规格](#12-共享工具函数规格)
  - [12.2 session_manager.py](#122-sharedsession_managerpy)
  - [12.3 csv_analyzer.py](#123-renderercsv_analyzerpy)
- [13. 输出路由规格](#13-输出路由规格)
- [14. Docker 与部署规格](#14-docker-与部署规格)
- [15. 测试脚本规格](#15-测试脚本规格)
- [16. Agent Skills 规格](#16-agent-skills-规格)
- [17. 工程规范补充](#17-工程规范补充)

---

## 1. 项目概览

**产品：** CSIS Ecosystem Intelligence Platform
**项目根目录（所有文件均在此目录下）：**
`C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\`

**技术栈：**
- 前端：React 18 + Vite + Tailwind CSS（已有，改造）
- 后端：Python FastAPI + Celery + Redis，运行在 **conda 环境 TeleCouplingAI**
- AI：Claude claude-sonnet-4-20250514 via Anthropic SDK
- 空间渲染：QGIS 3.40.14 Python subprocess（已验证）
- 生态建模：natcap.invest 3.14.3（已安装）
- 网络分析：R + igraph（subprocess）

---

## 2. 完整目录结构

```
telecouplingAI-project/
│
├── .claude/                      ← 🆕 Agent Skills（阶段 A 创建）
│   └── skills/
│       ├── run-network-analysis/SKILL.md
│       ├── run-cbc-preprocessor/SKILL.md
│       ├── run-coastal-blue-carbon/SKILL.md
│       ├── run-seasonal-water-yield/SKILL.md
│       ├── run-crop-percentile/SKILL.md
│       └── run-crop-regression/SKILL.md
│
├── frontend/                     ← 已有，部分改造
│   ├── src/
│   │   ├── App.jsx               ← 已有，需改造
│   │   ├── index.css             ← 不动
│   │   ├── main.jsx              ← 不动
│   │   ├── components/           ← 🆕
│   │   │   ├── ToolStatusCard.jsx
│   │   │   ├── CsvRenderer.jsx
│   │   │   ├── ChartRenderer.jsx
│   │   │   ├── ImageRenderer.jsx
│   │   │   ├── WarningCard.jsx
│   │   │   └── ResultFiles.jsx
│   │   └── lib/                  ← 🆕
│   │       ├── streaming.js
│   │       └── session.js
│   ├── index.html                ← 不动
│   ├── package.json              ← 微调
│   ├── tailwind.config.js        ← 不动
│   └── Dockerfile                ← 不动
│
├── backend/
│   ├── main.py                   ← 已有，需大幅改造
│   ├── agent.py                  ← 🆕
│   ├── config.py                 ← 已有，需扩展
│   ├── Dockerfile                ← 已有，需追加新包
│   ├── tools/                    ← 🆕 全部新建
│   ├── renderers/                ← 🆕 全部新建
│   ├── r_scripts/                ← 🆕
│   ├── shared/                   ← 🆕 全部新建
│   ├── workers/                  ← 🆕 全部新建
│   └── tests/                    ← 🆕 每个步骤完成后同步创建测试文件
│       ├── test_utils.py
│       ├── test_tools.py
│       ├── test_renderers.py
│       └── test_api.py
│
├── nginx/                        ← 🆕
├── datainput_for_demo/           ← 已移入，测试数据（只读）
├── references/                   ← 已移入，参考文档（只读）
├── outputs/                      ← 已创建
├── uploads/                      ← 已创建
├── test_outputs/                 ← 已创建
├── .gitignore                    ← 🆕 阶段 A 必须创建
├── docker-compose.yml            ← 已有，需扩充
└── .env.example                  ← 🆕
```

---

## 3. 本地环境信息

### 3.1 QGIS（已验证）

```
版本：3.40.14
Python 解释器：C:\Program Files\QGIS 3.40.14\bin\python-qgis-ltr.bat
验证结果：OK ✅  渲染 PNG 正常 ✅
```

### 3.2 测试数据路径（已移入项目目录，100% 确认存在）

```
DATA_ROOT = C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo

# 工具 1 — Network Analysis
TOOL1_NODES     = ...\NetworkAnalysisGrouping_input\Network Analysis Grouping\nodes.csv
TOOL1_LINKS     = ...\NetworkAnalysisGrouping_input\Network Analysis Grouping\links.csv
TOOL1_SHAPEFILE = ...\NetworkAnalysisGrouping_input\Network Analysis Grouping\World_countries_2002.shp
# ⚠️ 目录名含空格，路径须加引号

# 工具 2 — CBC Preprocessor
TOOL2_SNAPSHOTS   = ...\CoastalBLueCarbonPreprocessor_input\snapshots.csv
TOOL2_LULC_LOOKUP = ...\CoastalBLueCarbonPreprocessor_input\lulc_lookup.csv
TOOL2_TIF_2010    = ...\CoastalBLueCarbonPreprocessor_input\GBJC_2010_mean_Resample.tif
TOOL2_TIF_2030    = ...\CoastalBLueCarbonPreprocessor_input\GBJC_2030_mean_Resample.tif
TOOL2_TIF_2050    = ...\CoastalBLueCarbonPreprocessor_input\GBJC_2050_mean_Resample.tif
# ⚠️ 目录名 CoastalBLueCarbonPreprocessor_input（L 大写）

# 工具 3 — CBC Main
TOOL3_SNAPSHOTS    = ...\CoastalBlueCarbon_input\snapshots.csv
TOOL3_TRANSITIONS  = ...\CoastalBlueCarbon_input\outputs_preprocessor\transitions_sample.csv
TOOL3_BIOPHYSICAL  = ...\CoastalBlueCarbon_input\outputs_preprocessor\biophysical_table_sample.csv
TOOL3_PRICE_SCC2_5 = ...\CoastalBlueCarbon_input\Price_table_SCC2_5.csv
TOOL3_PRICE_SCC3   = ...\CoastalBlueCarbon_input\Price_table_SCC3.csv
TOOL3_PRICE_SCC5   = ...\CoastalBlueCarbon_input\Price_table_SCC_5.csv

# 工具 4 — Seasonal Water Yield
TOOL4_AOI         = ...\SeasonalWaterYield_input\watershed_gura.shp
TOOL4_LULC        = ...\SeasonalWaterYield_input\land_use_gura.tif
TOOL4_DEM         = ...\SeasonalWaterYield_input\DEM_gura.tif
TOOL4_SOIL        = ...\SeasonalWaterYield_input\soil_group_gura.tif
TOOL4_BIOPHYS     = ...\SeasonalWaterYield_input\biophysical_table_gura_SWY.csv
TOOL4_RAIN_EVENTS = ...\SeasonalWaterYield_input\rain_events_gura.csv
TOOL4_PRECIP_DIR  = ...\SeasonalWaterYield_input\Precipitation_monthly\
# ⚠️ 文件命名 precip_gura_1.tif...12.tif → 需 glob+symlink 重命名为 precip_m1.tif...precip_m12.tif
TOOL4_ET0_DIR     = ...\SeasonalWaterYield_input\ET0_monthly\
# ⚠️ 文件命名 ET0_gura_1.tif...12.tif → 需 glob+symlink 重命名为 et0_m1.tif...et0_m12.tif
TOOL4_SUBWATERSHEDS = ...\SeasonalWaterYield_input\subwatersheds_gura.shp

# 工具 5 — Crop Percentile
TOOL5_LANDCOVER   = ...\CropProductionPercentile_input\sample_user_data\landcover.tif
TOOL5_CROP_TABLE  = ...\CropProductionPercentile_input\sample_user_data\landcover_to_crop_table.csv
TOOL5_MODEL_DATA  = ...\CropProductionPercentile_input\model_data
TOOL5_AGGREGATE   = ...\CropProductionPercentile_input\sample_user_data\aggregate_shape.shp

# 工具 6 — Crop Regression
TOOL6_LANDCOVER   = ...\CropProductionRegression_input\sample_user_data\landcover.tif
TOOL6_CROP_TABLE  = ...\CropProductionRegression_input\sample_user_data\landcover_to_crop_table.csv
TOOL6_FERT_TABLE  = ...\CropProductionRegression_input\sample_user_data\crop_fertilization_rates.csv
TOOL6_MODEL_DATA  = ...\CropProductionPercentile_input\model_data  ← 与工具5共用
TOOL6_AGGREGATE   = ...\CropProductionRegression_input\sample_user_data\aggregate_shape.shp
```

### 3.3 输出目录（在项目目录内，已创建）

```
生产输出：...\telecouplingAI-project\outputs\
上传目录：...\telecouplingAI-project\uploads\
测试输出：...\telecouplingAI-project\test_outputs\
```

---

## 4. 骨架生成清单

**阶段 A：只创建缺失文件骨架，不覆盖已有文件。**

```bash
conda activate TeleCouplingAI
cd C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend
python -c "import main, agent, tools.network_analysis, renderers.qgis_renderer, workers.task_queue; print('All imports OK')"
```

### 4.1 已有文件（不动或阶段 B 改造）

```
frontend/src/App.jsx           ← 阶段 B 步骤 1 改造
frontend/src/index.css         ← 不动
frontend/src/main.jsx          ← 不动
frontend/index.html            ← 不动
frontend/package.json          ← 阶段 B 步骤 1 微调
frontend/tailwind.config.js    ← 不动
frontend/Dockerfile            ← 不动
backend/config.py              ← 阶段 B 步骤 2 扩展
backend/Dockerfile             ← 阶段 B 步骤 2 追加新包
```

### 4.2 🆕 需要骨架生成

```
# Agent Skills（按 Section 16 逐字创建）
.claude/skills/run-network-analysis/SKILL.md
.claude/skills/run-cbc-preprocessor/SKILL.md
.claude/skills/run-coastal-blue-carbon/SKILL.md
.claude/skills/run-seasonal-water-yield/SKILL.md
.claude/skills/run-crop-percentile/SKILL.md
.claude/skills/run-crop-regression/SKILL.md

# 版本控制与安全（阶段 A 第一步必须创建）
.gitignore

# 后端
backend/main.py                ← 改造骨架（保留 FastAPI/CORS，清空 Gemini）
backend/agent.py
backend/shared/__init__.py, utils.py, session_manager.py
backend/workers/__init__.py, task_queue.py
backend/tools/__init__.py, network_analysis.py, cbc_preprocessor.py,
        cbc_main.py, seasonal_water_yield.py, crop_percentile.py, crop_regression.py
backend/renderers/__init__.py, qgis_renderer.py, _qgis_render_worker.py,
        csv_analyzer.py, output_router.py
backend/r_scripts/network_analysis.R
backend/tests/__init__.py      ← 空文件，测试目录

# 前端新文件
frontend/src/components/ToolStatusCard.jsx, CsvRenderer.jsx, ChartRenderer.jsx,
        ImageRenderer.jsx, WarningCard.jsx, ResultFiles.jsx
frontend/src/lib/streaming.js, session.js

# 配置
nginx/nginx.conf, file-server.conf
.env.example
```

---

## 5. 填充顺序与依赖图

```
步骤 1:  frontend/src/App.jsx 改造（换 Claude 模型 + SSE + 6 张卡片 + 新消息类型）
步骤 2:  backend/config.py 扩展
步骤 3:  backend/shared/utils.py  → 同步创建 tests/test_utils.py
步骤 4:  backend/shared/session_manager.py
步骤 5:  backend/workers/task_queue.py
步骤 6:  backend/main.py 改造（换 Claude，加 SSE/upload/health 端点）
         → 同步创建 tests/test_api.py
步骤 7:  frontend/src/lib/session.js
步骤 8:  frontend/src/lib/streaming.js
步骤 9:  frontend 新组件（各自独立）
步骤 10: backend/agent.py
步骤 11: backend/renderers/output_router.py
步骤 12: backend/renderers/csv_analyzer.py
步骤 13: backend/renderers/_qgis_render_worker.py
步骤 14: backend/renderers/qgis_renderer.py → 同步创建 tests/test_renderers.py
步骤 15: backend/tools/network_analysis.py + r_scripts/network_analysis.R
         ⚠️ 先读：references/3 Network_Analysis_Grouping*.md
         → 同步创建 tests/test_tools.py（test_network_analysis）
步骤 16: backend/tools/cbc_preprocessor.py
         ⚠️ 先读：references/1 Coastal_Blue_Carbon_preprocessor*.md
步骤 17: backend/tools/cbc_main.py
         ⚠️ 先读：references/2 Coastal_Blue_Carbon*.md
步骤 18: backend/tools/seasonal_water_yield.py
         ⚠️ 先读：references/4 Seasonal_Water_Yield*.md
步骤 19: backend/tools/crop_percentile.py
         ⚠️ 先读：references/5 Crop_Production_Percentile*.md
步骤 20: backend/tools/crop_regression.py
         ⚠️ 先读：references/6 Crop_Production_Regression*.md
步骤 21: 压测脚本 tests/locustfile.py（见 Section 17）
```

---

## 6. 前端改造规格

### 6.1 App.jsx 改造要点（在现有结构上修改，不推倒重写）

```jsx
// ① 模型列表换成 Claude
const AVAILABLE_MODELS = [
  { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4.5', desc: 'Smart, efficient.' },
  { id: 'claude-opus-4-5-20251101', name: 'Claude Opus 4.5', desc: 'Most capable.' },
];

// ② 提示词从 2 张扩展为 6 张
const SUGGESTED_PROMPTS = [
  "Analyze a flow network and detect community clusters",
  "Run coastal blue carbon preprocessing",
  "Calculate coastal carbon stock and sequestration",
  "Estimate seasonal water yield and baseflow",
  "Estimate crop yield by percentile across 172 crops",
  "Model crop yield from fertilizer rates (NPK)",
];

// ③ handleSend 改为调用 streamChat（见 streaming.js）
// ④ 消息渲染增加 type 判断（见 6.2）
```

### 6.2 新消息类型渲染

```jsx
{msg.type === 'tool_status'   && <ToolStatusCard tool={msg.tool} message={msg.message} progress={msg.progress} />}
{msg.type === 'csv_table'     && <CsvRenderer filename={msg.filename} rows={msg.rows} columns={msg.columns} />}
{msg.type === 'chart'         && <ChartRenderer config={msg.config} />}
{msg.type === 'qgis_image'    && <ImageRenderer url={msg.url} filename={msg.filename} extent={msg.extent} />}
{msg.type === 'warning'       && <WarningCard message={msg.message} />}
{msg.type === 'file_download' && <ResultFiles files={msg.files} />}
```

### 6.3 SSE 流解析器（lib/streaming.js）

```javascript
export async function streamChat(message, uploadedFiles, sessionId, onEvent) {
  const formData = new FormData();
  formData.append('message', message);
  if (uploadedFiles) uploadedFiles.forEach(f => formData.append('files', f));
  // ❗ 使用相对路径，不要硬编码 localhost（Docker 部署时由 nginx 反向代理）
  const response = await fetch('/api/chat', {
    method: 'POST', headers: { 'X-Session-ID': sessionId }, body: formData,
  });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { onEvent(JSON.parse(line.slice(6))); }
        catch (e) { console.warn('SSE parse error:', e); }
      }
    }
  }
}
```

### 6.4 会话 ID（lib/session.js）

```javascript
export function getOrCreateSessionId() {
  const key = 'csis_session_id';
  let id = sessionStorage.getItem(key);
  if (!id) { id = `csis_${crypto.randomUUID()}`; sessionStorage.setItem(key, id); }
  return id;
}
```

---

## 7. 后端 API 规格

### 7.1 端点

```
POST   /api/chat        → SSE 流式响应，Header: X-Session-ID
POST   /api/upload      → 文件上传
POST   /api/render/zoom → QGIS zoom/pan
GET    /download/{session_id}/{subfolder}/{filename}
GET    /health          → {"status": "ok"}
DELETE /api/sessions/{session_id}
```

### 7.2 SSE 事件格式

```
data: {"type": "text_chunk",    "content": "..."}
data: {"type": "tool_start",    "tool": "...", "message": "...", "task_id": "..."}
data: {"type": "tool_progress", "progress": 45, "message": "..."}
data: {"type": "tool_result",   "files": [{"file":"...","url":"...","render_type":"qgis"}]}
data: {"type": "csv_data",      "filename":"...","rows":[...],"columns":[...]}
data: {"type": "image_url",     "filename":"...","url":"...","source_file":"...","extent":[...]}
data: {"type": "chart_config",  "config": {...}}
data: {"type": "warning",       "message": "..."}
data: {"type": "error",         "message": "...", "error_code": "TOOL_FAILED|INVALID_PARAMS|QGIS_TIMEOUT|..."}
data: {"type": "done"}
```

### 7.3 config.py 扩展

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- AI ---
    ANTHROPIC_API_KEY: str
    DEFAULT_MODEL: str = "claude-sonnet-4-20250514"

    # --- Storage (Docker container paths) ---
    SHARED_DIR: str = "/data/outputs"
    UPLOADS_DIR: str = "/data/uploads"
    FILE_SERVER_URL: str = "http://file-server/download/"

    # --- QGIS (Linux, inside Docker) ---
    QGIS_PYTHON_PATH: str = "/usr/bin/python3"
    QGIS_MAX_CONCURRENT: int = 3

    # --- InVEST model data ---
    MODEL_DATA_PATH: str = "/data/model_data"

    # --- R scripts ---
    R_SCRIPT_DIR: str = "./r_scripts"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Session ---
    SESSION_TTL_HOURS: int = 24
    MAX_SESSIONS: int = 50
    AUTH_REQUIRED: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

> **❗ 注意：** 已移除 `GOOGLE_API_KEY` 和 `DB_PATH`（Gemini/LangGraph 残留）。
> 所有路径默认值是 Docker 容器内的 Linux 路径，通过 `.env` 文件覆盖。

---

## 8. Agent 系统提示词

```python
SYSTEM_PROMPT = """
You are CSIS Assistant, an expert in ecosystem services modelling (InVEST) and spatial analysis.
Always respond in the same language as the user.

## Tool 1: run_network_analysis_grouping
Triggers: "network analysis", "flow network", "community detection", "node clustering"
Required: nodes_table(str), links_table(str), shapefile_path(str), nodes_join_attri(str), layer_join_attri(str), clustering_algorithm(str: "walktrap"|"spin_glass")
Optional: weight_within_clusters(int=10), weight_between_clusters(int=2), color_set(str="Set3"), node_size(float=0.05), edge_width(float=0.833333), label_size(float=0.8)
Outputs: network_plot_*.pdf→QGIS PNG, network_stats_*.csv→table, output_*.shp→QGIS PNG

## Tool 2: run_coastal_blue_carbon_preprocessor
Triggers: "blue carbon preprocess", "LULC transition", "coastal carbon prep"
Required: landcover_snapshot_csv(str), landcover_lookup_table(str)
Outputs: transitions_*.csv ⚠️REQUIRES MANUAL EDIT, carbon_pool_*.csv, aligned_lulc_*.tif→QGIS
⚠️ ALWAYS send warning: "transitions_.csv requires manual editing before running Tool 3"

## Tool 3: run_coastal_blue_carbon
Triggers: "carbon stock", "carbon sequestration", "coastal carbon", "net present value"
Required: landcover_snapshot_csv(str), landcover_transitions_table(str MANUALLY EDITED), biophysical_table_path(str)
Optional: analysis_year(int), do_economic_analysis(bool=False), discount_rate(float), inflation_rate(float), price(float), use_price_table(bool=False), price_table_path(str)
⚠️ PREREQUISITE: Confirm manual edit of transitions CSV.
Outputs: all *.tif → QGIS PNG with zoom

## Tool 4: run_seasonal_water_yield
Triggers: "seasonal water yield", "baseflow", "quickflow", "SWY"
Required: aoi_path, lulc_raster_path, dem_raster_path, soil_group_path, biophysical_table_path, precip_dir, et0_dir, rain_events_table_path, threshold_flow_accumulation(int)
⚠️ precip/et0 files may have non-standard names — use glob+symlinks in implementation
Optional: alpha_m(float=0.083333), beta_i(float=1.0), gamma(float=1.0), climate zone params, recharge params
Outputs: *.tif→QGIS, aggregated_results_swy_*.shp→QGIS+table

## Tool 5: run_crop_production_percentile
Triggers: "crop yield percentile", "172 crops", "food production"
Required: landcover_raster_path(str), landcover_to_crop_table_path(str), model_data_path(str SERVER-LOCAL → use MODEL_DATA_PATH env)
Optional: aggregate_polygon_path(str)
Outputs: result_table_*.csv→table+chart, *_yield_*percentile_*.tif→QGIS

## Tool 6: run_crop_production_regression
Triggers: "crop regression", "fertilizer", "NPK"
Required: landcover_raster_path(str), landcover_to_crop_table_path(str, supported crops: barley/maize/oil palm/potato/rice/soybean/sugar beet/sugar cane/sunflower/wheat), fertilization_rate_table_path(str, cols: crop_name,nitrogen_rate,phosphorus_rate,potassium_rate float kg/ha), model_data_path(str SERVER-LOCAL)
Optional: aggregate_polygon_path(str)
Outputs: result_table_*.csv→table+chart, *_regression_production_*.tif→QGIS

## Rules
- Same language as user
- Collect ALL required params before calling any tool
- Never assume model_data_path — use MODEL_DATA_PATH env var
"""
```

### 8.5 Claude Tool Use JSON Schema（agent.py 必须实现）

> **❗ 关键：** agent.py 使用 Anthropic SDK 的原生 function calling（tool_use）能力。
> 必须将以下 `tools` 列表传入 `client.messages.create(tools=TOOLS, ...)`。
> Claude 会自动返回 `tool_use` content block，agent 层解析后调用对应工具函数。

```python
# backend/agent.py 中定义
TOOLS = [
    {
        "name": "run_network_analysis_grouping",
        "description": "Run Network Analysis Grouping using R + igraph to detect community clusters in flow networks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nodes_table": {"type": "string", "description": "Path to nodes CSV file"},
                "links_table": {"type": "string", "description": "Path to links/edges CSV file"},
                "shapefile_path": {"type": "string", "description": "Path to input shapefile (.shp)"},
                "nodes_join_attri": {"type": "string", "description": "Column name in nodes CSV used for joining (e.g. 'CODE')"},
                "layer_join_attri": {"type": "string", "description": "Column name in shapefile for joining (e.g. 'ISO_3_CODE')"},
                "clustering_algorithm": {"type": "string", "enum": ["walktrap", "spin_glass"], "description": "Graph clustering method"},
                "weight_within_clusters": {"type": "integer", "default": 10, "description": "Edge weight within same cluster (0-100)"},
                "weight_between_clusters": {"type": "integer", "default": 2, "description": "Edge weight between clusters (0-100)"},
                "color_set": {"type": "string", "default": "Set3", "description": "RColorBrewer palette name"},
                "node_size": {"type": "number", "default": 0.05, "description": "Node size scaling (0-1)"},
                "edge_width": {"type": "number", "default": 0.833333, "description": "Edge width scaling (0-1)"},
                "label_size": {"type": "number", "default": 0.8, "description": "Label font size scaling (0-1)"}
            },
            "required": ["nodes_table", "links_table", "shapefile_path", "nodes_join_attri", "layer_join_attri", "clustering_algorithm"]
        }
    },
    {
        "name": "run_coastal_blue_carbon_preprocessor",
        "description": "Run InVEST Coastal Blue Carbon Preprocessor to identify LULC transitions between time periods.",
        "input_schema": {
            "type": "object",
            "properties": {
                "landcover_snapshot_csv": {"type": "string", "description": "Path to CSV with columns: snapshot_year(int), raster_path(str)"},
                "landcover_lookup_table": {"type": "string", "description": "Path to LULC lookup CSV with columns: lucode, lulc-class, is_coastal_blue_carbon_habitat"}
            },
            "required": ["landcover_snapshot_csv", "landcover_lookup_table"]
        }
    },
    {
        "name": "run_coastal_blue_carbon",
        "description": "Run InVEST Coastal Blue Carbon main model for carbon stock, sequestration, and economic NPV.",
        "input_schema": {
            "type": "object",
            "properties": {
                "landcover_snapshot_csv": {"type": "string", "description": "Path to snapshots CSV"},
                "landcover_transitions_table": {"type": "string", "description": "Path to MANUALLY EDITED transitions CSV from preprocessor"},
                "biophysical_table_path": {"type": "string", "description": "Path to biophysical table CSV"},
                "analysis_year": {"type": "integer", "description": "Final analysis year"},
                "do_economic_analysis": {"type": "boolean", "default": false, "description": "Enable NPV calculation"},
                "discount_rate": {"type": "number", "description": "Economic discount rate (required if do_economic_analysis=true)"},
                "inflation_rate": {"type": "number", "description": "Inflation rate"},
                "price": {"type": "number", "description": "Carbon price per ton"},
                "use_price_table": {"type": "boolean", "default": false, "description": "Use price schedule CSV instead of single price"},
                "price_table_path": {"type": "string", "description": "Path to price schedule CSV (if use_price_table=true)"}
            },
            "required": ["landcover_snapshot_csv", "landcover_transitions_table", "biophysical_table_path"]
        }
    },
    {
        "name": "run_seasonal_water_yield",
        "description": "Run InVEST Seasonal Water Yield model to estimate quickflow, baseflow, and local recharge.",
        "input_schema": {
            "type": "object",
            "properties": {
                "aoi_path": {"type": "string", "description": "Path to watershed AOI shapefile"},
                "lulc_raster_path": {"type": "string", "description": "Path to land use/land cover raster"},
                "dem_raster_path": {"type": "string", "description": "Path to DEM raster"},
                "soil_group_path": {"type": "string", "description": "Path to hydrologic soil group raster"},
                "biophysical_table_path": {"type": "string", "description": "Path to biophysical table CSV"},
                "precip_dir": {"type": "string", "description": "Directory of monthly precipitation rasters"},
                "et0_dir": {"type": "string", "description": "Directory of monthly ET0 rasters"},
                "rain_events_table_path": {"type": "string", "description": "Path to rain events CSV (columns: month, events)"},
                "threshold_flow_accumulation": {"type": "integer", "default": 1000, "description": "Flow accumulation threshold for stream delineation"},
                "alpha_m": {"type": "number", "default": 0.083333},
                "beta_i": {"type": "number", "default": 1.0},
                "gamma": {"type": "number", "default": 1.0}
            },
            "required": ["aoi_path", "lulc_raster_path", "dem_raster_path", "soil_group_path", "biophysical_table_path", "precip_dir", "et0_dir", "rain_events_table_path", "threshold_flow_accumulation"]
        }
    },
    {
        "name": "run_crop_production_percentile",
        "description": "Run InVEST Crop Production Percentile model for up to 172 crops based on climate percentiles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "landcover_raster_path": {"type": "string", "description": "Path to land cover raster"},
                "landcover_to_crop_table_path": {"type": "string", "description": "Path to CSV mapping lucode to crop_name"},
                "aggregate_polygon_path": {"type": "string", "description": "Optional path to polygon shapefile for aggregation"}
            },
            "required": ["landcover_raster_path", "landcover_to_crop_table_path"]
        }
    },
    {
        "name": "run_crop_production_regression",
        "description": "Run InVEST Crop Production Regression model based on fertilizer NPK rates. Supports 10 crops: barley, maize, oil palm, potato, rice, soybean, sugar beet, sugar cane, sunflower, wheat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "landcover_raster_path": {"type": "string", "description": "Path to land cover raster"},
                "landcover_to_crop_table_path": {"type": "string", "description": "Path to CSV mapping lucode to crop_name"},
                "fertilization_rate_table_path": {"type": "string", "description": "Path to CSV with columns: crop_name, nitrogen_rate, phosphorus_rate, potassium_rate (kg/ha)"},
                "aggregate_polygon_path": {"type": "string", "description": "Optional path to polygon shapefile for aggregation"}
            },
            "required": ["landcover_raster_path", "landcover_to_crop_table_path", "fertilization_rate_table_path"]
        }
    }
]
```

### 8.6 Agent 主循环逻辑（agent.py 核心流程）

```python
import anthropic
from config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

async def run_agent(message: str, session_id: str, files: list, event_callback):
    """
    1. 调用 client.messages.create(model=..., system=SYSTEM_PROMPT, tools=TOOLS, messages=...)
    2. 检查返回的 content blocks:
       - 如果是 text block → 通过 event_callback 发送 text_chunk SSE
       - 如果是 tool_use block → 提取 tool name + input
         → 发送 tool_start SSE
         → 调用对应工具函数（通过 Celery 或直接调用）
         → 将工具结果作为 tool_result 回传给 Claude
         → Claude 生成最终回复
    3. 支持多轮 tool_use（如果 Claude 返回 stop_reason='tool_use'，继续循环）
    """
    pass  # 步骤 10 填充
```

---

## 9. 6 个工具实现规格

### 9.1 通用模式

```python
async def run_tool(params, session_id, task_id, progress_callback) -> dict:
    # 1. validate_required(params, REQUIRED_KEYS)
    # 2. workspace_dir = generate_output_dir(tool_name, session_id)
    # 3. progress_callback(10, "Preparing...")
    # 4. 执行 invest 或 R（键名参考 REFERENCE_INDEX.md 速查表）
    # 5. files = scan_output_directory(workspace_dir, tool_name)
    # 6. return {"success": True, "files": files}
```

### 9.2 工具 1（R subprocess）

```python
REQUIRED_KEYS = ['nodes_table','links_table','shapefile_path','nodes_join_attri','layer_join_attri','clustering_algorithm']
# 先读：references/3 Network_Analysis_Grouping*.md（含完整 R 脚本）
# 关键：使用变量 in_telecoupling_layer_join，不能硬编码 "ISO_3_code"
# 关键：brewer.pal(min(max(n_communities, 3), 12), color_set)
```

### 9.3 工具 2-6（natcap.invest，键名见 REFERENCE_INDEX.md）

```python
# 工具 2：import natcap.invest.coastal_blue_carbon.preprocessor as cbc_pre
# 工具 3：import natcap.invest.coastal_blue_carbon.coastal_blue_carbon as cbc
# 工具 4：import natcap.invest.seasonal_water_yield.seasonal_water_yield as swy
#          ⚠️ precip/et0 需临时目录 glob+symlink 重命名
# 工具 5：import natcap.invest.crop_production_percentile as cpp
# 工具 6：import natcap.invest.crop_production_regression as cpr
```

---

## 10. QGIS 渲染规格

### 10.1 QGIS 环境

> **Docker 部署时：** QGIS 通过 `apt-get install qgis python3-qgis` 安装在后端容器中。
> `QGIS_PYTHON_PATH` 默认为 `/usr/bin/python3`，`QGIS_PREFIX_PATH` 默认为 `/usr`。
> 本地 Windows 开发时通过 `.env` 覆盖为 Windows QGIS 路径。

### 10.2 qgis_renderer.py

```python
import asyncio, json, os
from pathlib import Path
from config import settings

QGIS_PYTHON = settings.QGIS_PYTHON_PATH  # 从配置读取，不硬编码
_semaphore = asyncio.Semaphore(int(os.environ.get('QGIS_MAX_CONCURRENT', '3')))
WORKER_SCRIPT = str(Path(__file__).parent / '_qgis_render_worker.py')

async def render_file(file_path, output_path, width=1920, height=1080):
    async with _semaphore:
        return await _run({'file_path': file_path, 'output_path': output_path,
                           'width': width, 'height': height})

async def render_with_extent(file_path, output_path, extent, width=1920, height=1080):
    async with _semaphore:
        return await _run({'file_path': file_path, 'output_path': output_path,
                           'width': width, 'height': height, 'extent': extent})

async def _run(params):
    proc = await asyncio.create_subprocess_exec(
        QGIS_PYTHON, WORKER_SCRIPT, json.dumps(params),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill(); raise RuntimeError("QGIS timeout")
    if proc.returncode != 0:
        raise RuntimeError(f"QGIS failed:\n{err.decode()}")
    return json.loads(out.decode().strip())['output_path']
```

### 10.3 _qgis_render_worker.py

```python
import sys, json, os
p = json.loads(sys.argv[1])
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.setdefault('QGIS_PREFIX_PATH', '/usr')  # Docker default; override via env
from qgis.core import (QgsApplication, QgsVectorLayer, QgsRasterLayer,
                        QgsMapSettings, QgsMapRendererParallelJob, QgsRectangle)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QImage
app = QgsApplication([], False); app.initQgis()
ext = os.path.splitext(p['file_path'])[1].lower()
layer = QgsVectorLayer(p['file_path'],'l','ogr') if ext=='.shp' else QgsRasterLayer(p['file_path'],'l')
if not layer.isValid(): print(json.dumps({"error":layer.error().message()})); sys.exit(1)
e = p.get('extent')
re = QgsRectangle(e[0],e[1],e[2],e[3]) if e else layer.extent()
s = QgsMapSettings(); s.setLayers([layer]); s.setExtent(re)
s.setOutputSize(QSize(p.get('width',1920), p.get('height',1080)))
os.makedirs(os.path.dirname(os.path.abspath(p['output_path'])), exist_ok=True)
img = QImage(QSize(p.get('width',1920),p.get('height',1080)), QImage.Format_ARGB32_Premultiplied)
img.fill(0xFFFFFFFF)
job = QgsMapRendererParallelJob(s); job.start(); job.waitForFinished()
job.renderedImage().save(p['output_path'], 'PNG')
print(json.dumps({'output_path': p['output_path'],
                  'extent': [re.xMinimum(), re.yMinimum(), re.xMaximum(), re.yMaximum()]}))
app.exitQgis()
```

---

## 11. Celery SSE 回传规格

```python
# workers/task_queue.py
import redis, json
from celery import Celery
from config import settings

app = Celery('csis', broker=settings.REDIS_URL, backend=settings.REDIS_URL)
app.conf.update(task_soft_time_limit=1800, task_time_limit=2100,
                task_acks_late=True, task_reject_on_worker_lost=True)

def publish(r, sid, tid, event):
    r.publish(f"progress:{sid}:{tid}", json.dumps(event))

@app.task(bind=True)
def run_tool_task(self, tool_name, params, session_id):
    r = redis.from_url(settings.REDIS_URL)
    tid = self.request.id
    try:
        publish(r, session_id, tid, {"type":"tool_start","tool":tool_name,"task_id":tid})
        result = execute_tool(tool_name, params, session_id,
                   progress_callback=lambda p,m: publish(r, session_id, tid,
                       {"type":"tool_progress","progress":p,"message":m}))
        publish(r, session_id, tid, {"type":"tool_result","files":result['files']})
        publish(r, session_id, tid, {"type":"done"})
    except Exception as e:
        publish(r, session_id, tid, {"type":"error","message":str(e)})
    finally:
        r.close()
```

---

## 12. 共享工具函数规格

### 12.1 shared/utils.py

```python
def parse_input_data(raw) -> dict: ...
async def download_file(url, local_name, session_id) -> str: ...
def generate_output_dir(tool_name, session_id) -> tuple[str, str]: ...
def build_result_urls(folder_name, files, subfolder='') -> list[dict]: ...
def run_r_script(script_path, config, session_id, task_id) -> dict: ...
def validate_required(params, required_keys) -> None: ...
def scan_output_directory(workspace_dir, tool_name) -> list[dict]: ...
```

### 12.2 shared/session_manager.py

> **❗ 步骤 4 必须实现此文件。负责会话生命周期、工具运行状态和 TTL 清理。**

```python
import redis, json, time
from config import settings

class SessionManager:
    """
    基于 Redis 的会话管理器。
    每个会话存储在 Redis hash 中，key = session:{session_id}
    """

    def __init__(self):
        self.r = redis.from_url(settings.REDIS_URL)
        self.ttl = settings.SESSION_TTL_HOURS * 3600

    def create_session(self, session_id: str) -> dict:
        """创建新会话，设置 TTL"""
        data = {
            "created_at": time.time(),
            "last_active": time.time(),
            "tool_runs": "[]",        # JSON array of {tool_name, task_id, status, timestamp}
            "uploaded_files": "[]",   # JSON array of file paths
        }
        self.r.hset(f"session:{session_id}", mapping=data)
        self.r.expire(f"session:{session_id}", self.ttl)
        self._enforce_max_sessions()
        return data

    def get_session(self, session_id: str) -> dict | None:
        """获取会话数据，如果不存在返回 None"""
        ...

    def touch_session(self, session_id: str):
        """更新 last_active，续期 TTL"""
        ...

    def add_tool_run(self, session_id: str, tool_name: str, task_id: str):
        """记录工具运行状态"""
        ...

    def add_uploaded_file(self, session_id: str, file_path: str):
        """记录上传文件路径"""
        ...

    def delete_session(self, session_id: str):
        """删除会话及其输出目录"""
        ...

    def _enforce_max_sessions(self):
        """如果总会话数 > MAX_SESSIONS，淘汰最久未活跃的会话"""
        ...
```

### 12.3 renderers/csv_analyzer.py

> **❗ 步骤 12 实现。负责解析 CSV 输出文件，生成前端可渲染的表格和图表配置。**

```python
import pandas as pd

MAX_PREVIEW_ROWS = 50  # 前端表格最多显示行数

def analyze_csv(csv_path: str) -> dict:
    """
    读取 CSV 文件，返回前端可渲染的数据。
    
    Returns:
        {
            "filename": "result_table.csv",
            "columns": ["crop_name", "area_ha", "production_mt", ...],
            "rows": [{"crop_name": "maize", ...}, ...],  # 前 MAX_PREVIEW_ROWS 行
            "total_rows": 150,
            "chart_config": {  # 可选，如果数据适合图表
                "type": "bar",
                "x_field": "crop_name",
                "y_field": "production_mt",
                "title": "Crop Production by Type"
            } or None
        }
    """
    ...

def suggest_chart(df: pd.DataFrame, filename: str) -> dict | None:
    """根据 CSV 内容自动推荐图表类型。返回 chart_config 或 None。"""
    ...
```

---

## 13. 输出路由规格

```python
PATTERNS = {
    'seasonal_water_yield':             {'qgis':['QF_*.tif','B_*.tif','L_avail_*.tif','L_*.tif','P_*.tif','aggregated_results_swy_*.shp'],'csv':[]},
    'coastal_blue_carbon_preprocessor': {'qgis':['aligned_lulc_*.tif'],'csv':['transitions_*.csv','carbon_pool_transient_template_*.csv']},
    'coastal_blue_carbon':              {'qgis':['carbon_stock_*.tif','net_carbon_sequestration_*.tif','total_net_carbon_sequestration_*.tif','npv_*.tif'],'csv':[]},
    'crop_production_percentile':       {'qgis':['*_yield_*percentile_*.tif'],'csv':['result_table_*.csv','aggregate_results_*.csv']},
    'crop_production_regression':       {'qgis':['*_regression_production_*.tif'],'csv':['result_table_*.csv','aggregate_results_*.csv']},
    'network_analysis':                 {'qgis':['output_*.shp'],'csv':['network_stats_*.csv'],'download':['network_plot_*.pdf']},
}
EXT_FALLBACK = {'.tif':'qgis','.tiff':'qgis','.shp':'qgis','.csv':'csv','.png':'image','.jpg':'image'}
```

---

## 14. Docker 与部署规格

### 14.1 .env.example

> **❗ 所有路径必须是 Docker 容器内的 Linux 路径，不要用 Windows 路径。**
> **已创建实际 `.env.example` 文件在项目根目录。** ✅

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here

# --- Paths (Docker container paths, do NOT use Windows paths) ---
SHARED_DIR=/data/outputs
UPLOADS_DIR=/data/uploads
FILE_SERVER_URL=http://file-server/download/

# --- QGIS (Linux, inside Docker) ---
QGIS_PYTHON_PATH=/usr/bin/python3
QGIS_MAX_CONCURRENT=3
QT_QPA_PLATFORM=offscreen
QGIS_PREFIX_PATH=/usr

# --- Redis ---
REDIS_URL=redis://redis:6379/0

# --- InVEST model data (mounted read-only in Docker) ---
MODEL_DATA_PATH=/data/model_data

# --- R scripts ---
R_SCRIPT_DIR=./r_scripts

# --- Session ---
SESSION_TTL_HOURS=24
MAX_SESSIONS=50
AUTH_REQUIRED=false

# --- Claude model ---
DEFAULT_MODEL=claude-sonnet-4-20250514
```

### 14.2 backend/Dockerfile 改造

> **❗ 当前 Dockerfile 的 CMD 被注释掉了（`tail -f /dev/null`），必须修复。**

需要的改动：
1. pip install 行追加：`anthropic celery[redis] redis aiohttp pydantic-settings loguru`
2. 安装 QGIS Python bindings：`apt-get install -y qgis python3-qgis r-base r-cran-igraph`
3. 复制后端代码：`COPY . .`
4. 暴露端口：`EXPOSE 8000`
5. 修复 CMD：

```dockerfile
CMD ["conda", "run", "--no-capture-output", "-n", "TeleCouplingAI", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 14.3 docker-compose.yml 扩充

```yaml
version: '3.8'
services:
  api-server:
    build: ./backend
    container_name: tele-backend
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./datainput_for_demo:/data/datainput:ro
      - ${SHARED_DIR}:/data/outputs
      - ${UPLOADS_DIR}:/data/uploads
      - ${MODEL_DATA_PATH}:/data/model_data:ro
    ports: ["8000:8000"]
    depends_on: [redis]
    restart: always

  celery-worker:
    build: ./backend
    command: conda run --no-capture-output -n TeleCouplingAI celery -A workers.task_queue worker --concurrency=2 --pool=prefork
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./datainput_for_demo:/data/datainput:ro
      - ${SHARED_DIR}:/data/outputs
      - ${UPLOADS_DIR}:/data/uploads
      - ${MODEL_DATA_PATH}:/data/model_data:ro
    depends_on: [redis]
    restart: always

  redis:
    image: redis:7.2-alpine
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    ports: ["6379:6379"]
    restart: always

  frontend-ui:
    build: ./frontend
    container_name: tele-frontend
    ports: ["80:80"]
    depends_on: [api-server]
    restart: always

  file-server:
    image: nginx:1.25-alpine
    ports: ["8001:80"]
    volumes:
      - ${SHARED_DIR}:/usr/share/nginx/html/download:ro
      - ./nginx/file-server.conf:/etc/nginx/nginx.conf:ro
    restart: always
```

### 14.4 nginx/nginx.conf

> **❗ 注意：** 前端 Dockerfile 内置了 Nginx 托管静态文件。
> 前端 JS 中 API 请求应使用**相对路径** `/api/chat`，通过此 nginx 反向代理到后端。
> 如果使用独立 nginx 服务作为入口，需要同时代理前端和 API。

```nginx
upstream backend  { server api-server:8000; }
upstream frontend { server frontend-ui:80; }

server {
    listen 80;

    # --- Frontend static files ---
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
    }

    # --- SSE streaming (no buffering) ---
    location /api/chat {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 1800s;
        proxy_set_header X-Session-ID $http_x_session_id;
    }

    # --- File upload ---
    location /api/upload {
        proxy_pass http://backend;
        client_max_body_size 500M;
        proxy_read_timeout 300s;
    }

    # --- Other API routes ---
    location /api/ { proxy_pass http://backend; }

    # --- Health check ---
    location /health { proxy_pass http://backend; }
}
```

---

## 15. 测试脚本规格

### 15.1 conda 环境验证

```bash
conda activate TeleCouplingAI
python -c "import natcap.invest, fastapi, uvicorn, redis, celery, anthropic; print('All OK')"
```

### 15.2 骨架验证

```bash
conda activate TeleCouplingAI
cd backend
python -c "
import main, agent, config
import shared.utils, shared.session_manager
import tools.network_analysis, tools.cbc_preprocessor, tools.cbc_main
import tools.seasonal_water_yield, tools.crop_percentile, tools.crop_regression
import renderers.qgis_renderer, renderers.csv_analyzer, renderers.output_router
import workers.task_queue
print('All imports OK')
"
```

### 15.3 步骤 6 完成验证

```bash
cd backend && python main.py
curl http://localhost:8000/health   # {"status": "ok"}
```

### 15.4 步骤 14 完成验证（QGIS）

```bash
python -c "
import asyncio, os, sys
sys.path.insert(0, r'...telecouplingAI-project\backend')
from renderers.qgis_renderer import render_file
result = asyncio.run(render_file(
    r'...\SeasonalWaterYield_input\DEM_gura.tif',
    r'...\test_outputs\qgis_test.png'
))
assert os.path.exists(result); print('QGIS OK')
"
```

### 15.5 工具 4 月度文件验证

```bash
python -c "
import glob, os
precip_dir = r'...\Precipitation_monthly'
for m in range(1, 13):
    assert glob.glob(os.path.join(precip_dir, f'*_{m}.tif')), f'Month {m} missing'
print('月度文件匹配 OK')
"
```

---

## 16. Agent Skills 规格

> **Claude Code 在阶段 A 必须按以下规格，逐字创建 6 个 SKILL.md 文件。**

### 16.1 `.claude/skills/run-network-analysis/SKILL.md`

```markdown
---
name: run-network-analysis
description: Run Network Analysis Grouping using R + igraph to detect community clusters in flow networks. Use when user asks about network analysis, flow network, community detection, node clustering, trade network, or telecoupling network.
---

## 实现文件
backend/tools/network_analysis.py → 调用 backend/r_scripts/network_analysis.R
先读：references/3 Network_Analysis_Grouping*.md（含完整 R 脚本）

## 必填参数
- nodes_table, links_table, shapefile_path
- nodes_join_attri (str): nodes CSV 中 join 列名
- layer_join_attri (str): shapefile 属性表中 join 列名
- clustering_algorithm: "walktrap" 或 "spin_glass"

## 可选参数
weight_within_clusters=10, weight_between_clusters=2, color_set="Set3"
node_size=0.05, edge_width=0.833333, label_size=0.8

## ⚠️ R 脚本关键规则
```r
# ✅ 使用变量，不要硬编码
colnames(community_df)[1] <- nodes_table_join
shp_merged <- shp_layer %>% left_join(community_df,
    by = setNames(nodes_table_join, in_telecoupling_layer_join))
# ✅ 颜色数量保护
Colors <- brewer.pal(min(max(n_communities, 3), 12), color_set)
```

## 输出
network_plot_*.pdf→PNG, network_stats_*.csv→table, output_*.shp→QGIS PNG

## 测试数据
nodes/links/shapefile: datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\
```

---

### 16.2 `.claude/skills/run-cbc-preprocessor/SKILL.md`

```markdown
---
name: run-cbc-preprocessor
description: Run InVEST Coastal Blue Carbon Preprocessor to identify LULC transitions. Use when user asks about blue carbon preprocessing, LULC transition analysis, or coastal carbon prep.
---

## 实现文件
backend/tools/cbc_preprocessor.py
import natcap.invest.coastal_blue_carbon.preprocessor as cbc_pre
先读：references/1 Coastal_Blue_Carbon_preprocessor*.md

## invest_args 键名
```python
invest_args = {
    'landcover_snapshot_csv': path,   # 列：snapshot_year(int), raster_path(str)
    'lulc_lookup_table_path': path,   # 列：lucode(int), lulc-class(str), is_coastal_blue_carbon_habitat(bool)
    'results_suffix': '',
    'workspace_dir': output_dir,
}
```

## ⚠️ 输出在子目录
workspace_dir/outputs_preprocessor/ — 不是根目录！

## ⚠️ 运行后必须发送警告 SSE 事件
{"type":"warning","message":"transitions_.csv requires manual editing before running Tool 3"}

## 测试数据
datainput_for_demo\CoastalBLueCarbonPreprocessor_input\（L大写）
```

---

### 16.3 `.claude/skills/run-coastal-blue-carbon/SKILL.md`

```markdown
---
name: run-coastal-blue-carbon
description: Run InVEST Coastal Blue Carbon main model for carbon stock, sequestration, and NPV. Use when user asks about carbon stock, carbon sequestration, coastal carbon, or NPV of carbon.
---

## 实现文件
backend/tools/cbc_main.py
import natcap.invest.coastal_blue_carbon.coastal_blue_carbon as cbc
先读：references/2 Coastal_Blue_Carbon*.md

## ⚠️ 前置条件
必须确认用户已将 transitions CSV 中的 'disturb' 改为 'low/med/high-impact-disturb'

## 必填参数
- landcover_snapshot_csv, landcover_transitions_table（已手动编辑）, biophysical_table_path

## 可选经济分析参数
do_economic_analysis(bool=False), discount_rate, inflation_rate, price
use_price_table(bool=False), price_table_path

## 输出 → 全部 QGIS PNG
carbon_stock_*.tif, net_carbon_sequestration_*.tif, total_net_carbon_sequestration_*.tif
npv_*.tif（仅经济分析时）
```

---

### 16.4 `.claude/skills/run-seasonal-water-yield/SKILL.md`

```markdown
---
name: run-seasonal-water-yield
description: Run InVEST Seasonal Water Yield model for quickflow, baseflow, and recharge. Use when user asks about seasonal water yield, baseflow, quickflow, SWY, or watershed hydrology.
---

## 实现文件
backend/tools/seasonal_water_yield.py
import natcap.invest.seasonal_water_yield.seasonal_water_yield as swy
先读：references/4 Seasonal_Water_Yield*.md

## invest_args 完整键名（直接复用）
alpha_m, aoi_path, beta_i, biophysical_table_path, climate_zone_raster_path,
climate_zone_table_path, dem_raster_path, et0_dir, gamma, l_path,
lulc_raster_path, monthly_alpha, monthly_alpha_path, precip_dir,
rain_events_table_path, results_suffix, soil_group_path,
threshold_flow_accumulation, user_defined_climate_zones,
user_defined_local_recharge, workspace_dir

## ⚠️ 月度文件命名问题（最关键）
本项目文件：precip_gura_N.tif / ET0_gura_N.tif
InVEST 要求：precip_mN.tif / et0_mN.tif
解决：
```python
import shutil

def prepare_monthly_dir(src_dir, prefix_out):
    """Rename monthly files to InVEST-expected format via symlink (Linux) or copy (Windows fallback)."""
    tmp = tempfile.mkdtemp()
    for month in range(1, 13):
        src = glob.glob(os.path.join(src_dir, f"*_{month}.tif"))[0]
        dst = os.path.join(tmp, f"{prefix_out}{month}.tif")
        try:
            os.symlink(os.path.abspath(src), dst)
        except OSError:
            shutil.copy2(src, dst)  # Windows fallback (symlink needs admin)
    return tmp
```

## 输出 → 全部 QGIS PNG
QF_*.tif, B_*.tif, L_avail_*.tif, L_*.tif, P_*.tif, aggregated_results_swy_*.shp
```

---

### 16.5 `.claude/skills/run-crop-percentile/SKILL.md`

```markdown
---
name: run-crop-percentile
description: Run InVEST Crop Production Percentile model for up to 172 crops based on climate percentiles. Use when user asks about crop yield percentile, 172 crops, food production, or crop intensification.
---

## 实现文件
backend/tools/crop_percentile.py
import natcap.invest.crop_production_percentile as cpp
先读：references/5 Crop_Production_Percentile*.md

## invest_args
```python
invest_args = {
    'aggregate_polygon_path': params.get('aggregate_polygon_path', ''),
    'landcover_raster_path': path,
    'landcover_to_crop_table_path': path,  # 列：lucode(int), crop_name(str)
    'model_data_path': os.environ.get('MODEL_DATA_PATH'),  # ⚠️ 始终用环境变量
    'results_suffix': '',
    'workspace_dir': output_dir,
}
```

## 输出
result_table_*.csv→table+chart, <crop>_yield_<percentile>percentile_*.tif→QGIS
```

---

### 16.6 `.claude/skills/run-crop-regression/SKILL.md`

```markdown
---
name: run-crop-regression
description: Run InVEST Crop Production Regression model based on fertilizer NPK rates. Use when user asks about crop regression, fertilizer NPK, nitrogen phosphorus potassium, or fertilizer-yield analysis.
---

## 实现文件
backend/tools/crop_regression.py
import natcap.invest.crop_production_regression as cpr
先读：references/6 Crop_Production_Regression*.md

## invest_args
```python
invest_args = {
    'aggregate_polygon_path': params.get('aggregate_polygon_path', ''),
    'fertilization_rate_table_path': path,  # 列：crop_name, nitrogen_rate, phosphorus_rate, potassium_rate (kg/ha)
    'landcover_raster_path': path,
    'landcover_to_crop_table_path': path,
    'model_data_path': os.environ.get('MODEL_DATA_PATH'),  # ⚠️ 与工具5共用，始终用环境变量
    'results_suffix': '',
    'workspace_dir': output_dir,
}
```

## ⚠️ 仅支持 10 种作物
barley, maize, oil palm, potato, rice, soybean, sugar beet, sugar cane, sunflower, wheat
不支持的作物请建议用户使用工具 5

## 输出
result_table_*.csv→table+chart, <crop>_regression_production_*.tif→QGIS
```

---

### 16.7 Skills 创建验证

```bash
dir .claude\skills\   # 期望看到 6 个子目录
```

---

## 17. 工程规范补充

> **以下 5 条规范是生产质量的必要条件，Claude Code 在阶段 B 实现过程中必须遵守。**

### 17.1 版本控制（Git）

**阶段 A 第一步必须完成：**

```bash
cd C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project
git init
git add .gitignore
git commit -m "init: add .gitignore"
git add CSIS_Platform_Spec_v4.md .claude/ references/
git commit -m "docs: add spec and reference docs"
```

**`.gitignore` 必须包含：**

```gitignore
# 环境变量（绝对不能提交）
.env
*.env

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/

# 输出目录（数据太大，不提交）
outputs/
uploads/
test_outputs/
data/

# Node
node_modules/
frontend/dist/

# 系统
.DS_Store
Thumbs.db
```

**阶段 B 每个步骤完成并测试通过后，立即 commit：**

```bash
git add backend/shared/utils.py backend/tests/test_utils.py
git commit -m "feat(step3): implement shared/utils.py with tests"
```

---

### 17.2 自动化测试

**每个步骤完成时，同步创建对应测试文件。测试文件位于 `backend/tests/`。**

**运行方式：**

```bash
conda activate TeleCouplingAI
cd backend
python -m pytest tests/ -v
```

**各模块测试要点：**

```python
# tests/test_utils.py — 步骤 3 完成时创建
def test_parse_input_data_dict():
    assert parse_input_data({"a": 1}) == {"a": 1}

def test_parse_input_data_json_string():
    assert parse_input_data('{"a": 1}') == {"a": 1}

def test_validate_required_missing():
    with pytest.raises(ValueError):
        validate_required({}, ["nodes_table"])

# tests/test_api.py — 步骤 6 完成时创建
from fastapi.testclient import TestClient
def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

# tests/test_renderers.py — 步骤 14 完成时创建
def test_qgis_render_tif():
    # 使用真实 DEM 测试数据验证输出 PNG 存在
    result = asyncio.run(render_file(TOOL4_DEM, OUTPUT_PATH))
    assert os.path.exists(result)

# tests/test_tools.py — 步骤 15-20 逐步补充
# 每个工具一个 test_tool_N() 函数，使用 datainput_for_demo 真实数据
```

---

### 17.3 统一错误处理与日志

**后端所有工具和端点必须使用统一的错误码和日志格式。**

**错误码定义（在 `shared/utils.py` 中定义）：**

```python
class CSISError(Exception):
    """所有 CSIS 工具错误的基类"""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

# 标准错误码
ERROR_CODES = {
    "MISSING_PARAMS":    "缺少必填参数",
    "INVALID_PARAMS":    "参数格式不正确",
    "TOOL_FAILED":       "工具执行失败",
    "QGIS_TIMEOUT":      "QGIS 渲染超时（120秒）",
    "QGIS_FAILED":       "QGIS 渲染失败",
    "FILE_NOT_FOUND":    "输入文件不存在",
    "R_FAILED":          "R 脚本执行失败",
    "OUTPUT_NOT_FOUND":  "工具未生成预期输出文件",
}
```

**日志规范：**

```python
import logging

# 每个模块顶部统一设置
logger = logging.getLogger(__name__)

# 工具执行时记录关键节点
logger.info(f"[{tool_name}] Starting, session={session_id}, params={params}")
logger.info(f"[{tool_name}] invest_args={invest_args}")
logger.info(f"[{tool_name}] Completed, outputs={[f['filename'] for f in files]}")
logger.error(f"[{tool_name}] Failed: {e}", exc_info=True)
```

**用户友好的错误消息（SSE error 事件）：**

```python
# 工具失败时发送的错误消息要对用户有意义，不要裸露技术堆栈
# ❌ 不好：{"type": "error", "message": "KeyError: 'lucode' at line 45 in..."}
# ✅ 好：  {"type": "error", "message": "biophysical_table_path 缺少必需列 'lucode'，请检查文件格式", "error_code": "INVALID_PARAMS"}
```

---

### 17.4 安全：API Key 保护

**`.env` 文件绝对不能提交到 Git。阶段 A 必须确认 `.gitignore` 包含 `.env`。**

**验证：**

```bash
# 确认 .env 不会被追踪
git check-ignore -v .env
# 期望输出：.gitignore:1:.env   .env
```

**额外保护：后端启动时验证 key 存在：**

```python
# backend/main.py 启动时检查
@app.on_event("startup")
async def startup_check():
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Check your .env file.")
    logger.info("API key validated ✅")
```

---

### 17.5 并发压测

**步骤 20（最后一个工具）完成后，执行步骤 21：创建并运行压测脚本。**

**安装：**

```bash
conda activate TeleCouplingAI
pip install locust
```

**`backend/tests/locustfile.py`：**

```python
from locust import HttpUser, task, between

class CSISUser(HttpUser):
    wait_time = between(5, 15)  # 模拟用户思考时间

    @task(3)
    def test_health(self):
        self.client.get("/health")

    @task(1)
    def test_chat_simple(self):
        """测试纯文本对话（不触发工具）"""
        self.client.post("/api/chat",
            data={"message": "What is seasonal water yield?"},
            headers={"X-Session-ID": f"csis_test_{id(self)}"},
            stream=True
        )

    @task(1)
    def test_chat_tool(self):
        """测试触发工具的对话（使用测试数据路径）"""
        self.client.post("/api/chat",
            data={"message": "Run seasonal water yield with default test data"},
            headers={"X-Session-ID": f"csis_test_{id(self)}"},
            stream=True
        )
```

**运行（目标：30 用户，观察响应时间和错误率）：**

```bash
conda activate TeleCouplingAI
cd backend
locust -f tests/locustfile.py --host=http://localhost:8000 --users=30 --spawn-rate=5
# 浏览器打开 http://localhost:8089 查看实时报告
```

**通过标准：**
- `/health` 端点：P95 响应时间 < 100ms，错误率 = 0%
- 纯文本对话：P95 < 3s，错误率 < 1%
- 工具执行：30 个并发用户下 QGIS Semaphore 不死锁，无 OOM

---

*文档结束 — v4.4*

*给 Claude Code 的最后提醒：*
*1. 后端所有 Python 运行必须在 conda 环境 TeleCouplingAI 中执行*
*2. natcap.invest 3.14.3 已安装，直接 import，不需要重新安装*
*3. 步骤 15-20 实现工具前，先读 references/REFERENCE_INDEX.md 和对应 Notion .md 文件*
*4. 阶段 A 第一步：git init + 创建 .gitignore，确保 .env 不被追踪*
*5. 阶段 B 每个步骤：实现 → 写测试 → 运行测试通过 → git commit → 再继续*
*6. 前端已有完整 UI，步骤 1 是改造（换模型+SSE+新消息类型），不是重写*
*7. **所有路径默认值必须是 Docker/Linux 路径**，不要硬编码 Windows 路径*
*8. 工具 2（CBC Preprocessor）和工具 3（CBC Main）共用部分测试数据（snapshots.csv 分别在两个目录中，内容相同；工具 3 的 outputs_preprocessor/ 是工具 2 的预运行输出）*
*9. agent.py 必须使用 Section 8.5 的 TOOLS JSON Schema 实现 Claude 原生 function calling*
*10. requirements.txt 已重写，移除了所有 Gemini/LangGraph 依赖 ✅*
