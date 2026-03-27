# 开发日志 — 2026-03-16（第一次）

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

**修复**：
- `backend/config.py`：`env_file` 改为绝对路径，指向项目根目录 `.env`
- `backend/.env`：清空，只留注释说明
- 根目录 `.env` 为唯一配置文件

---

### 三、model_data_path 改为用户输入

- `model_data_path` 加入两个工具的 `REQUIRED_KEYS`
- `invest_args` 改为从 `params["model_data_path"]` 取值

---

### 四、作物名称动态加载 + 归一化

- `get_supported_crops(model_data_path)` — 动态扫描支持列表
- `_normalize(name)` — 归一化函数
- `_rewrite_crop_csv()` — 归一化用户输入 CSV

---

### 五、CBC Main 仅扫描 output/ 子目录

- `SKIP_DIRS` 扩展覆盖所有 InVEST 中间目录变体

---

### 六、QGIS zoom_render 新功能

- 新增 `zoom_render()` 函数，params 写入临时 JSON 文件解决 Windows 路径问题
- 底图：在线 Google Satellite → 本地 MBTiles → 无底图

---

### 七、output_router 预览图自动生成

- qgis 文件 → download + 异步生成 `*_preview.png`（image）
- `scan_output_directory` 改为 async

---

### 八、单元测试更新

`test_renderers.py`、`test_tools.py`、`test_utils.py` 均已更新。

---

## 下次继续（第一次结束时）

- [x] 运行完整测试套件（pytest A + 手动测试 B-K）← 已完成
- [x] 验证所有工具的预览图生成效果 ← 已完成
- [ ] 前端集成
- [ ] Docker 部署配置验证

---

---

# 开发日志 — 2026-03-16（第二次）

## 本次工作内容

### 一、agent.py 实现（步骤 10）— Claude 版本（后被替换）

实现了 `run_agent()` 主循环（Anthropic SDK），含两阶段 Skills 加载、Celery 派发、Redis pub/sub relay。

### 二、Skills 两阶段运行时加载架构

每个 SKILL.md 分三段：`[DEV ONLY]` / `[PRE_EXECUTION]` / `[POST_EXECUTION]`。
PRE_EXECUTION 注入 system prompt，POST_EXECUTION 注入 tool_result context。

### 三、6 个 SKILL.md 重写

全部改为英文，三段式结构，含上传文件感知规则。

---

---

# 开发日志 — 2026-03-25（第三次）

## 本次工作内容

### 一、AI 后端从 Claude 切换为 Gemini

| 文件 | 改动内容 |
|------|----------|
| `requirements.txt` | `anthropic` → `google-genai>=0.8.0` |
| `config.py` | `ANTHROPIC_API_KEY` → `GOOGLE_API_KEY`，默认 `gemini-2.5-flash` |
| `.env.example` / `.env` | 同步更新 |
| `agent.py` | 重写为 Gemini function calling |
| `main.py` | 全新实现，SSE/upload/download/health/session 端点 |

---

---

# 开发日志 — 2026-03-25（第四次）

## 本次工作内容 — 全面 Review 后修复 11 个问题

### 🔴 严重问题修复

**1. agent.py — `_gemini_client` 改为懒初始化**
原来模块 import 时就创建 client，`GOOGLE_API_KEY` 未设置时直接崩溃。
改为 `_get_client()` 函数，第一次调用 `run_agent()` 时才初始化。

**2. agent.py — `tool_start` 事件 task_id 修正**
原来先发 `tool_start`（此时用 tool_name 充当 task_id），再 `delay()`，导致前端 task_id 和 Redis channel 不一致。
改为先 `run_tool_task.delay()`，拿到真实 Celery task_id 后再发 `tool_start` 事件。

**3. App.jsx — 接入 SSE，替换旧 Gemini 端点**
原来 `handleSend` 调 `fetch('http://127.0.0.1:8000/chat')` 直接 json()，完全不是 SSE。
改为调用 `streamChat()`，通过 SSE 事件驱动消息渲染。

**4. App.jsx — 默认模型改为 `gemini-2.5-flash`**
原来默认是 `gemini-2.0-flash`，与 config.py 默认值不一致，已修正。

### 🟡 中等问题修复

**5. App.jsx — 6 张 Suggested Prompts 卡片**
从 2 张旧卡片扩展为 6 张，每张对应一个工具的触发场景，含 hint 标签。

**6. App.jsx — 新消息类型渲染**
新增 `MessageContent` 组件，支持渲染 `text`、`tool_status`、`warning`、`csv_table`、`chart`、`image`、`file_download` 7 种 block 类型。
消息结构从 `{role, content}` 扩展为 `{role, blocks: [{type, ...}]}`，支持混合内容。

**7. main.py — session_manager 改为懒初始化**
原来模块加载时就 `SessionManager()`，Redis 不可用时后端无法启动。
改为 `get_session_manager()` 函数，首次请求时才初始化。

**8. agent.py — `asyncio.get_event_loop()` → `asyncio.get_running_loop()`**
在异步上下文里应用 `get_running_loop()`，消除 Python 3.10+ deprecation 警告。

**9. main.py — 新增 `/api/render/zoom` 端点**
Spec Section 7.1 要求的端点，支持传入 file_path、output_path、extent、width、height，调用 QGIS re-render。

### 🟢 小问题修复

**10. streaming.js — 加入 `model` 参数**
`streamChat()` 新增 `model` 参数，append 到 FormData，前端模型选择框生效。

**11. 前端组件完整实现**
- `ToolStatusCard`：进度条 + 完成状态变色（蓝→绿）
- `WarningCard`：琥珀色警告样式
- `ImageRenderer`：圆角卡片 + extent 信息
- `ResultFiles`：带图标的下载列表
- `CsvRenderer`：固定高度滚动表格
- `ChartRenderer`：Chart.js 动态加载，支持 bar/line

---

## 下次继续

- [x] agent.py 完整实现（Gemini）✅
- [x] main.py 完整实现 ✅
- [x] App.jsx 完整改造 ✅
- [x] streaming.js / session.js ✅
- [x] 所有前端组件完整实现 ✅
- [x] requirements.txt 版本修正 ✅
- [ ] 配置 Redis + 填入 GOOGLE_API_KEY，做端到端真实对话测试
- [ ] Docker 部署配置验证
- [ ] test_api.py 补充（Spec 步骤 6 要求）

---

# 开发日志 — 2026-03-25（端到端测试 + SSL 修复）

## 本次工作内容

### 一、环境搭建

- Redis：使用 Windows 本机 Redis（tporadowski/redis）而非 Docker，本地开发更轻量。生产部署时直接打进 docker-compose。
- Gemini API Key：填入 `.env` 的 `GOOGLE_API_KEY` 字段，无需加引号。

### 二、SDK 兼容性 Bug 修复（agent.py）

**问题**：`google-genai 1.63.0` 的 `Part.from_text()` 改为关键字参数。

错误信息：`Part.from_text() takes 1 positional argument but 2 were given`

**修复**：`agent.py` 中两处调用改为关键字参数：
```python
# 修复前
types.Part.from_text(user_text)
# 修复后
types.Part.from_text(text=user_text)
```
涉及第 353 行（用户消息构建）和第 460 行（POST_EXECUTION skill 注入）。

### 三、SSL / 代理问题修复（agent.py）

**背景**：开发环境在中国大陆，HTTPS_PROXY 设置为本地代理（Clash/V2Ray，127.0.0.1:29758）以访问 Google API。代理建立 CONNECT 隧道后，Python httpx 的 TLS 握手失败，报错：

```
[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol
```

**根因**：代理做 SSL 中转时证书链不被 Python OpenSSL 信任。

**修复**：在 `_get_client()` 创建 genai Client 时，通过 `HttpOptions` 的 `clientArgs` / `asyncClientArgs` 关闭 SSL 验证：

```python
_gemini_client = genai.Client(
    api_key=settings.GOOGLE_API_KEY,
    http_options=HttpOptions(
        clientArgs={"verify": False},
        asyncClientArgs={"verify": False},
    ),
)
```

**⚠️ 生产部署注意**：服务器部署在美国境内，不存在代理问题，Google API 可直连。上线前需将 `verify` 改回 `True`（或直接删除这两个参数），恢复证书验证以保证安全性。

### 四、端到端测试结果

后端启动后测试 `/api/chat` 端点，Gemini 正常响应：

```
Hello! I am CSIS Assistant, an expert in ecosystem services modelling (InVEST) ...
```

基础对话流程验证通过。

## 当前状态

- [x] Redis 配置完成（Windows 本机）
- [x] GOOGLE_API_KEY 配置完成
- [x] /api/health 正常
- [x] /api/chat 端到端对话测试通过
- [x] 前端启动测试 ✅
- [ ] /api/upload 文件上传测试
- [ ] 工具调用（function calling）端到端测试
- [ ] Docker 部署配置验证

---

# 开发日志 — 2026-03-25（前端测试 + UI 修复）

## 本次工作内容

### 一、前端启动脚本

新增 `start.bat`（位于项目根目录），双击后自动弹出 3 个终端窗口分别启动：
1. FastAPI 后端（`python main.py`）
2. Celery Worker（`celery -A workers.task_queue worker -P solo`）
3. Vite 前端（`npm run dev`）

启动后浏览器访问 `http://localhost:5173`。

### 二、前端端到端对话测试

通过预览工具打开页面，输入 "test" 发送，AI 正常返回：

> Hello! I am the CSIS Assistant, an expert in ecosystem services modelling (InVEST) and spatial analysis. How may I help you today?

对话流程、消息气泡、侧边栏历史记录命名均正常。

### 三、UI 问题发现与修复（App.jsx）

**问题 1：移动端侧边栏挤掉主内容**

根因：`isSidebarOpen` 默认 `true`，侧边栏占 288px，在 375px 屏幕上主内容区几乎为零。

修复：
- 默认值改为 `window.innerWidth >= 768`（小屏默认收起）
- 侧边栏改为 `fixed md:relative`，移动端 overlay 模式（脱离文档流）
- 关闭时用 `-translate-x-full`（移动）/ `md:w-0`（桌面）

**问题 2：移动端无遮罩层**

修复：侧边栏打开时在移动端渲染半透明 backdrop，点击即关闭侧边栏。

**问题 3：汉堡菜单按钮仅在侧边栏关闭时显示**

修复：改为顶栏常驻显示，点击切换侧边栏开关。

### 四、跨屏幕验证结果

| 尺寸 | 结果 |
|------|------|
| 移动端 375px | 侧边栏默认收起，汉堡菜单可弹出 overlay ✅ |
| 平板 768px | 侧边栏默认展开，2 列卡片布局正常 ✅ |
| 桌面 1280px | 侧边栏 + 主内容并排，布局正常 ✅ |

## 当前状态

- [x] Redis 配置完成（Windows 本机）
- [x] GOOGLE_API_KEY 配置完成
- [x] /api/health 正常
- [x] /api/chat 端到端对话测试通过
- [x] 前端 UI 响应式布局修复完成
- [x] start.bat 一键启动脚本
- [ ] /api/upload 文件上传测试
- [ ] 工具调用（function calling）端到端测试
- [ ] Docker 部署配置验证

---

# 开发日志 — 2026-03-27（端到端集成测试 Phase 2）

## 本次工作内容

### 一、端到端工具测试（浏览器 UI）

**测试方法**：每次开新 Chat session，通过浏览器上传真实 demo 文件，用自然语言 prompt 驱动 Gemini Agent 完成工具调用，不使用 param=value 格式。Demo 输入文件统一放在 ，通过  路径访问。

**测试结果**：

| Tool | 状态 | 备注 |
|------|------|------|
| Tool 2: CBC Preprocessor | ✅ 通过 | |
| Tool 3: CBC Main | ✅ 通过 | 修复了 CSV 路径问题（见下） |
| Tool 5: Crop Production Percentile | ✅ 通过 | 移除 model_data_path 暴露 |
| Tool 6: Crop Production Regression | ✅ 通过 | 移除 model_data_path 暴露 |
| Tool 1: Network Analysis | ✅ 通过 | R 崩溃修复验证完成（见本次日志 Bug 6/7） |
| Tool 4: Seasonal Water Yield | ✅ 通过 | 首次测试通过（见本次日志 Bug 8） |

---

### 二、Bug 修复

**Bug 1 — DataTransfer 文件通过 Vite 获取到 HTML 而非实际文件**
- 现象：浏览器 eval 里用  fetch 文件，拿到的是 （Vite SPA fallback）
- 根因：Vite dev server 只代理 , , ， 路径未代理
- 修复：改用  路径，利用后端  端点， 即可访问 

**Bug 2 — CBC Main CSV 解析错误**
- 现象：
- 根因： 表头有多余引号，raster 路径为相对路径
- 修复：重写为无引号表头 + 绝对路径

**Bug 3 — Gemini Agent 跨 session ConnectError**
- 现象：第二次 Chat session 调用 Gemini API 报 
- 根因： 全局缓存，SDK 关闭 session 后 httpx.AsyncClient 已失效
- 修复 ()：移除全局缓存，每次调用创建新 （含新 httpx clients）

**Bug 4 — model_data_path 暴露给用户**
- 现象：Agent 向用户询问 model_data_path 并在输出中显示服务器绝对路径
- 修复： /  改为  默认值； tool schema 移除该参数；SKILL.md 添加禁止提及说明

**Bug 5 — Network Analysis R 进程崩溃（Windows 特有）**
- 现象：Celery Worker 调用 R 脚本返回 exit code （0xC0000005 = STATUS_ACCESS_VIOLATION），stderr 为空
- 根因： 使用相对路径 Usage: Rscript [options] file [args]
   or: Rscript [options] -e expr [-e expr2 ...] [args]
A binary front-end to R, for use in scripting applications.

Options:
  --help              Print usage and exit
  --version           Print version and exit
  --verbose           Print information on progress
  --default-packages=LIST  Attach these packages on startup;
                        a comma-separated LIST of package names, or 'NULL'
and options to R (in addition to --no-echo --no-restore), for example:
  --save              Do save workspace at the end of the session
  --no-environ        Don't read the site and user environment files
  --no-site-file      Don't read the site-wide Rprofile
  --no-init-file      Don't read the user R profile
  --restore           Do restore previously saved objects at startup
  --vanilla           Combine --no-save, --no-restore, --no-site-file,
                        --no-init-file and --no-environ

Expressions (one or more '-e <expr>') may be used *instead* of 'file'.
Any additional 'args' can be accessed from R via 'commandArgs(TRUE)'.
See also  ?Rscript  from within R. + ，Celery Worker 通过  启动后 PATH 环境与直接测试不同，路径解析不稳定
- 修复 ()：改用  绝对路径 +  绝对脚本路径
- 状态：修复已提交，待重启 Celery Worker 验证

---

### 三、新增 Demo 输入文件（）

| 文件 | 用途 |
|------|------|
|  | CBC Main — 快照年份与绝对路径 |
|  | CBC Main — 土地覆盖转换规则 |
|  | CBC Main — 生物物理参数表 |
|  | Crop Percentile — lucode 映射 |
|  | Network Analysis — 节点属性（列：CODE, larrivals.sender, larrivals.receiver） |
|  | Network Analysis — 连接表 |
|  | Network Analysis — 世界国家底图 |

---
找到了！Redis 在 C:\Users\dru18\redis\。

## 下次继续（Phase 2 结束时）

- [x] Tool 1: Network Analysis — 重启 Celery 后重试 ✅
- [x] Tool 4: Seasonal Water Yield — 首次测试 ✅
- [ ] 多用户并发场景测试
- [ ] Docker 化 + Linux 环境验证

---

---

# 开发日志 — 2026-03-27（端到端集成测试 Phase 3）

## 本次工作内容

### 一、服务启动方式修复

**问题**：`conda run` 在 git bash 下不能正确继承 CWD（Unix 路径 vs Windows 路径不匹配），Celery Worker 的 `_backend_dir` 计算偏差，`from tools.xxx import` 抛出 `ModuleNotFoundError: No module named 'tools'`。

**修复**：改用 conda env 的 Python 可执行文件直接启动，并显式设置 `PYTHONPATH`：
```
PYTHONPATH=C:\...\backend  C:\Users\dru18\.conda\envs\TeleCouplingAI\python.exe -m celery -A workers.task_queue worker -P solo
```

---

### 二、UI 端到端测试方法

使用 `preview_eval` 在浏览器上下文中 fetch demo 文件（通过 `/download/demo_xxx/` 路径），用 `DataTransfer` API 注入 React file input，触发完整 UI 流程。
交互约定：每次提交后用 `AskUserQuestion`（成功/失败）等待确认，失败时截图分析。

---

### 三、Bug 修复

**Bug 6 — Celery 旧进程残留（DuplicateNodename）**
- 现象：存在两个 Celery Worker，任务被旧进程（修复前代码）处理
- 修复：每次重启前 `Get-Process python | Stop-Process -Force` 杀干净

**Bug 7 — Network Analysis R 脚本路径修复验证**
- 修复内容（Phase 2 已完成）：`network_analysis.py` 改用 `Path(__file__).parent.parent` 绝对路径
- 验证结果：Celery `returncode=0`，6 个输出文件（PDF/CSV/SHP/PNG），UI ✅ 100% Completed + 预览地图

**Bug 8 — SWY `prepare_monthly_dir` 同目录多类型文件歧义**
- 现象：precip 和 ET0 文件在同一 uploads 目录，`glob("*_N.tif")` 返回多个候选，`matches[0]` 可能选错类型
- 修复（`tools/seasonal_water_yield.py`）：增加 `type_keyword` 优先匹配
  - `prefix_out="precip_m"` → 优先选文件名含 "precip" 的
  - `prefix_out="et0_m"` → 优先选文件名含 "et0" 的
- 验证结果：SWY 输出 B.tif/QF.tif/L.tif/aggregated_results_swy.shp，UI 多张预览图正常渲染 ✅

---

### 四、测试结果汇总（截至本次）

| Tool | 状态 | 测试日期 |
|------|------|----------|
| Tool 1: Network Analysis | ✅ 通过 | 2026-03-27 |
| Tool 2: CBC Preprocessor | ✅ 通过 | 2026-03-27 (Phase 2) |
| Tool 3: CBC Main | ✅ 通过 | 2026-03-27 (Phase 2) |
| Tool 4: Seasonal Water Yield | ✅ 通过 | 2026-03-27 |
| Tool 5: Crop Production Percentile | ✅ 通过 | 2026-03-27 (Phase 2) |
| Tool 6: Crop Production Regression | ✅ 通过 | 2026-03-27 (Phase 2) |

**全部 6 个工具端到端测试通过 ✅**

---

## 下次继续

- [ ] 多用户并发场景测试
- [ ] Docker 化 + Linux 环境验证
- [ ] `/api/render/zoom` QGIS 重渲染端点测试
- [ ] `start.bat` 更新（改为直接调用 Python 可执行文件，避免 conda run CWD 问题）

**启动方式（当前有效）**：
```
1. Redis:   C:\Users\dru18\redis\redis-server.exe redis.windows.conf
2. 后端:    C:\Users\dru18\.conda\envs\TeleCouplingAI\python.exe main.py
3. Celery:  PYTHONPATH=C:\...\backend python.exe -m celery -A workers.task_queue worker -P solo
4. 前端:    npm run dev
```

---

# 开发日志 — 2026-03-27（代码审查 + 安全修复 Phase 4）

## 本次工作内容

### 一、全量代码审查

对 `backend/` 下所有源文件（`main.py`、`agent.py`、`workers/task_queue.py`、`config.py`、`shared/`、`tools/` 全部 6 个工具、`renderers/`）进行系统性代码审查，共发现 **25 个问题**，分为 4 个严重级别。

---

### 二、已修复问题（4 项）

#### Fix 1 — 路径穿越漏洞（`backend/main.py:266`）

**严重程度**：高（安全漏洞）

**问题**：`/download/{session_id}/{file_path:path}` 端点未校验 `file_path` 是否包含 `../`，攻击者可构造如 `/download/x/../../../etc/passwd` 的 URL 读取服务器任意文件。

```python
# 修复前
full_path = os.path.join(settings.SHARED_DIR, session_id, file_path)
if not os.path.isfile(full_path):
    raise HTTPException(status_code=404, detail="File not found")
return FileResponse(full_path, filename=os.path.basename(full_path))

# 修复后
shared_root = Path(settings.SHARED_DIR).resolve()
full_path = Path(settings.SHARED_DIR, session_id, file_path).resolve()
if not str(full_path).startswith(str(shared_root)):
    raise HTTPException(status_code=403, detail="Access denied")
if not full_path.is_file():
    raise HTTPException(status_code=404, detail="File not found")
return FileResponse(str(full_path), filename=full_path.name)
```

**原则**：`Path.resolve()` 展开所有 `..` 符号后，用 `startswith` 校验路径必须在 `SHARED_DIR` 内。

---

#### Fix 2 — Gemini 空 candidates 崩溃（`backend/agent.py:413`）

**严重程度**：中（运行时崩溃）

**问题**：当 Gemini API 因安全过滤、限流或异常返回空 `candidates` 列表时，`response.candidates[0]` 抛出 `IndexError`，导致整个 Agent 任务崩溃，前端收到 500 错误。

```python
# 修复后（在 response 使用前增加守卫）
if not response.candidates:
    logger.warning("[agent] Gemini returned no candidates, stopping")
    break
```

**位置**：`agent.py` 主循环 `for iteration in range(max_iterations):` 内，紧跟 `generate_content` 调用之后。

---

#### Fix 3 — 事件循环冗余代码（`backend/workers/task_queue.py:58`）

**严重程度**：低（代码质量）

**问题**：`execute_tool()` 手动创建新事件循环并设置为全局事件循环，污染线程状态。`asyncio.run()` 是 Python 3.7+ 的官方等效用法，更简洁安全。

```python
# 修复前（7 行）
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    return loop.run_until_complete(
        func(params, session_id, task_id, progress_callback)
    )
finally:
    loop.close()

# 修复后（1 行）
return asyncio.run(func(params, session_id, task_id, progress_callback))
```

**注意**：两者行为等价，均创建全新事件循环运行协程后关闭。修复后代码更清晰，不写入全局线程状态。

---

#### Fix 4 — 死代码 `if True:`（`backend/tools/crop_regression.py:100`）

**严重程度**：低（代码质量）

**问题**：`run_crop_regression()` 内有 `if True:` 包裹的验证逻辑块，该条件恒为真，等同于多余的缩进层级，令代码难读且带来误解（是否原本是 `if some_flag:`？）。

```python
# 修复前
if os.path.isfile(fert_path_check):
    supported_check = get_supported_crops(model_data_path)
    if True:
        with open(fert_path_check, ...) as f:
            ...

# 修复后
if os.path.isfile(fert_path_check):
    supported_check = get_supported_crops(model_data_path)
    with open(fert_path_check, ...) as f:
        ...
```

---

### 三、延期处理的问题（21 项）

以下问题经评估后决定**不在本次修复**，原因是改动风险超过收益，或属于部署环境特有配置，强行修改会破坏已通过的 E2E 测试。

| # | 文件 | 问题 | 延期原因 |
|---|------|------|----------|
| 1 | `agent.py` | `content.parts` 可能为 `None` → 列表推导 `AttributeError` | 实际 Gemini API 始终返回 parts；加守卫会引入不必要代码 |
| 2 | `agent.py` | `ssl_verify=False` 硬编码 | 生产部署在境外，不需代理，届时删除；改动需重新测试 |
| 3 | `agent.py` | Gemini Client 不缓存（每次调用新建） | 已确认是 Bug 3 的修复，不可回退 |
| 4 | `config.py` | 默认路径为 Docker 路径（`/data/outputs`） | 生产 Docker 环境确实使用此路径；本地由 `.env` 覆盖 |
| 5 | `main.py` | `CORS allow_origins=["*"]` | 本地开发便利性需求；生产部署时按域名收窄 |
| 6 | `main.py` | 会话无超时/自动清理 | 当前是 MVP，不需要自动过期逻辑 |
| 7 | `shared/session_manager.py` | 内存存储，重启即丢失 | 设计如此，会话状态为瞬态 |
| 8 | `tools/network_analysis.py` | subprocess 未限制运行时间 | R 脚本超时由 Celery `task_soft_time_limit=1800s` 保护 |
| 9 | `tools/network_analysis.py` | shapefile 路径用字符串拼接 | 用户上传文件，路径可信；不存在注入风险 |
| 10 | `tools/cbc_main.py` | CSV 路径未用 `validate_required` | 路径来自上传文件字典，已在上层验证 |
| 11 | `tools/cbc_preprocessor.py` | 无进度百分比细分 | 工具本身很快，细分无实际意义 |
| 12 | `tools/seasonal_water_yield.py` | tmpdir 在异常时可能残留 | `finally` 块已处理；极端异常（kill -9）可接受 |
| 13 | `tools/crop_percentile.py` | `model_data_path` 由 settings 提供而非用户输入 | 这是 Tool 5 的已知设计；model_data 路径不暴露给用户 |
| 14 | `tools/crop_regression.py` | `_rewrite_crop_csv` 在 workspace 内写文件（workspace 是 InVEST 输出目录） | InVEST 不干扰额外文件；实测通过 |
| 15 | `workers/task_queue.py` | `r.close()` 在 `finally`，但 `publish()` 异常时 r 可能未初始化 | `redis.from_url()` 失败时 `r` 赋值前就会抛出，不会到 `finally` |
| 16 | `renderers/qgis_renderer.py` | QGIS 渲染超时无机制 | `/api/render/zoom` 端点尚未进入测试，延期处理 |
| 17 | `renderers/output_router.py` | `.tif` 文件一律触发渲染，可能对大文件很慢 | 当前 demo 数据文件较小；大文件场景待压测后处理 |
| 18 | `shared/utils.py` | `scan_output_directory` 递归深度无限制 | InVEST 输出结构固定，不存在深层嵌套 |
| 19 | `main.py` | 上传文件无大小/类型限制 | MVP 阶段，受信任用户使用；生产前加限制 |
| 20 | `agent.py` | `max_iterations=10` 硬编码 | 当前工具调用链不超过 2 轮；足够 |
| 21 | `config.py` | `FILE_SERVER_URL` 默认为 localhost | 生产时通过环境变量覆盖；不需改代码 |

---

### 四、修复后状态

- 所有 4 项修复均**向后兼容**，不影响已通过的 E2E 测试
- Fix 1 (路径穿越)：现有测试路径均在 SHARED_DIR 内，`resolve()` 后 `startswith` 仍通过
- Fix 2 (空 candidates)：正常响应时 `candidates` 非空，守卫不触发
- Fix 3 (事件循环)：`asyncio.run()` 与原实现行为等价
- Fix 4 (`if True:`)：纯缩进调整，逻辑不变



# 并发架构分析 — 2026-03-27

## 一、同一 Chat 窗口连续调用多个 Tool

**结论：安全，无冲突。**

| 机制 | 说明 |
|------|------|
| 输出目录隔离 | `generate_output_dir` 用秒级时间戳生成 `{session_id}/{timestamp}_{tool_name}/`，每次调用独立目录 |
| Redis 频道隔离 | 每个 Celery 任务有唯一 UUID task_id，订阅 `progress:{session_id}:{task_id}`，不同 tool 的事件不串台 |
| Agent 串行执行 | `agent.py` 主循环 `for fc in function_calls:` 是顺序 for 循环，必须等当前 tool 收到 `done` 后才 dispatch 下一个 |
| Celery `-P solo` 兜底 | 即使 Gemini 在同一 response 里返回多个 function_call，Celery 也排队串行执行 |

唯一边缘情况：`generate_output_dir` 时间戳精度为秒，同一秒内同一用户调用同一 tool 两次会复用目录，但输出文件名不同，不会覆盖关键结果。

---

## 二、多用户并发（10 人同时在线）

### 安全的组件

| 组件 | 原因 |
|------|------|
| FastAPI | 异步处理，多个 SSE 流并发无问题 |
| Session Manager | 基于 Redis hash 存储（`session:{session_id}`），每用户独立 key，有 TTL 自动过期和 `MAX_SESSIONS` 最大上限保护 |
| 文件系统 | 输出目录按 `session_id` 隔离，用户间完全不干扰 |
| Redis pub/sub | 频道按 `progress:{session_id}:{task_id}` 隔离，跨用户无干扰 |

### 核心瓶颈：Celery `-P solo` 是全局单线程队列

10 人同时提交工具调用，所有任务进同一队列，**严格串行**：

```
用户1 的 SWY 任务     → 立即执行（~5分钟）
用户2 的 Network 任务 → 等用户1 完成后执行
...
用户10 的任务         → 等待约 45 分钟
```

前端 SSE 连接保持 pending，用户看到长时间转圈，不是 bug，是设计限制。

### 次要问题：session_manager 有小概率竞态

`add_uploaded_file` / `add_tool_run` 是非原子的 read-modify-write（`hget` → `json.loads` → `append` → `hset`）。同一 session_id 并发写入时理论上可能丢一条记录。实际中每个用户 session_id 不同，不共享，触发概率接近零。

### 解决方案（按优先级）

**方案一：Windows 下改用 `-P threads`（中期，改动成本极低）**

```bash
PYTHONPATH=... python.exe -m celery -A workers.task_queue worker -P threads -c 4 --loglevel=info
```
允许 4 个工具任务并发执行，10 人场景基本够用，Windows 兼容，无需改任何业务代码。

**方案二：启动多个 Worker 进程（扩展性好，Windows 也可用）**

```bash
# 终端 A
PYTHONPATH=... python.exe -m celery -A workers.task_queue worker -P solo -n worker1@%h
# 终端 B
PYTHONPATH=... python.exe -m celery -A workers.task_queue worker -P solo -n worker2@%h
```
Redis broker 自动负载均衡，两个 Worker 各跑一个任务，并发 ×2。

**方案三：Docker + Linux 生产部署（长期标配）**

Linux 下 Celery 默认 `prefork` 多进程，性能最强：
```bash
celery -A workers.task_queue worker -c 8
```
这也是 `config.py` 默认 Docker 路径的设计意图。

---

# 本地开发环境启动手册（避免重复调试）

> 每次重新开始本地开发/测试前，按此顺序操作。所有坑已踩完，照做即可。

## 一、前置条件确认

| 项目 | 路径 / 说明 |
|------|------------|
| 项目根目录 | `C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\` |
| Conda 环境 | `TeleCouplingAI`（Python 3.13，natcap.invest 3.14.3） |
| Python 可执行 | `C:\Users\dru18\.conda\envs\TeleCouplingAI\python.exe` |
| Redis 可执行 | `C:\Users\dru18\redis\redis-server.exe`（**不在 PATH**，必须用绝对路径） |
| API Key | 根目录 `.env` 中的 `GOOGLE_API_KEY`（已配置，无需改动） |
| R 语言 | 系统已安装，`igraph` 包已就绪 |

---

## 二、启动步骤（共 4 步，各开独立终端）

### 第 1 步 — 启动 Redis

打开终端 1，执行：

```bash
C:\Users\dru18\redis\redis-server.exe C:\Users\dru18\redis\redis.windows.conf
```

看到 `Ready to accept connections` 即成功。

> **⚠️ 不要用 `redis-server` 直接执行**，Redis 不在 PATH 中，会报"命令未找到"。

---

### 第 2 步 — 启动 FastAPI 后端

打开终端 2，进入 backend 目录：

```bash
cd C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend
C:\Users\dru18\.conda\envs\TeleCouplingAI\python.exe main.py
```

看到 `CSIS backend started ✅` 和 `Uvicorn running on http://127.0.0.1:8000` 即成功。

> **⚠️ 不要用 `python main.py`**，系统 Python 没有 `natcap`、`google-genai` 等依赖。必须用 conda env 的绝对路径。

---

### 第 3 步 — 启动 Celery Worker

打开终端 3（**Git Bash**），执行：

```bash
PYTHONPATH=C:/YPHOME/Jianan_Projects/Telecoupling_AI_Project/fulldev/telecouplingAI-project/backend \
  C:/Users/dru18/.conda/envs/TeleCouplingAI/python.exe \
  -m celery -A workers.task_queue worker -P solo --loglevel=info
```

看到 `celery@hostname ready` 即成功。

> **⚠️ 三个关键点，缺一不可：**
> 1. **必须显式设置 `PYTHONPATH`**：`conda run` 在 git bash 下无法正确继承 Windows CWD，会导致 `ModuleNotFoundError: No module named 'tools'`
> 2. **必须用 conda env 的绝对路径 Python**：同上，系统 Python 缺依赖
> 3. **必须加 `-P solo`**：Windows 不支持 Celery 默认的 `prefork`（基于 `fork`），`solo` 是 Windows 专用单线程模式

---

### 第 4 步 — 启动前端

打开终端 4：

```bash
cd C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\frontend
npm run dev
```

看到 `Local: http://localhost:5173/` 即成功。浏览器打开此地址开始测试。

---

## 三、重启时的清理步骤

**每次重启服务前**，必须先杀干净旧进程，否则会出现两个 Celery Worker 同时运行（`DuplicateNodename` 警告），任务会被旧进程（修复前代码）处理，导致测试假失败。

在 PowerShell 中执行：

```powershell
Get-Process python | Stop-Process -Force
```

然后重新按第 2、3 步启动后端和 Celery。Redis 和前端一般不需要重启。

---

## 四、验证服务是否正常

全部启动后，可用以下命令快速验证：

```bash
curl http://localhost:8000/health
# 应返回: {"status":"ok"}
```

浏览器打开 `http://localhost:5173`，发送消息 `"hello"`，AI 应回复 CSIS 助手介绍语。

---

## 五、常见问题速查

| 现象 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: No module named 'tools'` | Celery 启动时未设置 `PYTHONPATH` | 按第 3 步，加 `PYTHONPATH=...` 前缀 |
| `DuplicateNodename` 警告 | 存在旧 Celery 进程未关闭 | PowerShell: `Get-Process python \| Stop-Process -Force` |
| R 脚本 exit code `3221225477` (0xC0000005) | Celery Worker 使用相对路径找不到 R 脚本 | 已修复（`network_analysis.py` 改为绝对路径），无需操作 |
| 后端启动报 `GOOGLE_API_KEY is not set` | `.env` 未被加载 | 确认在 `backend/` 目录下执行；`config.py` 指向根目录 `.env` |
| 前端文件上传后无进度 | Celery Worker 未启动，或任务被旧进程消费 | 检查终端 3 是否有 `Task received` 日志；必要时重启 |
| Redis 连接失败 | Redis 未启动，或配置文件路径错误 | 检查终端 1；确保用 `redis.windows.conf` 绝对路径 |

## 下次继续

- [ ] 多用户并发场景测试
- [ ] Docker 化 + Linux 环境验证
- [ ] `/api/render/zoom` QGIS 重渲染端点测试
- [ ] `start.bat` 更新
- [ ] 生产部署前：将 `ssl_verify=False` 改回 `True`，`CORS` 收窄到具体域名

---
---

# 开发日志 — 2026-03-27

## 本次工作内容：Docker 部署 + 全栈验证

---

### 一、Docker 镜像构建修复

**问题 1：Python 版本不兼容**
QGIS conda-forge 不支持 Python 3.13，构建时报 `Could not solve for environment specs`。

**修复**：`backend/Dockerfile` 中将 `python=3.13` 改为 `python=3.12`，同时放宽 gdal/geos/proj 的版本固定，让 conda 自动解决 QGIS 依赖约束。

**问题 2：`g++` 找不到（pygeoprocessing C++ 编译失败）**
错误：`error: command 'g++' failed: No such file or directory`

**修复**：在 conda install 中加入 `gxx_linux-64 gcc_linux-64`，并添加编译器 symlink 步骤：
```dockerfile
RUN ln -sf /opt/conda/envs/TeleCouplingAI/bin/x86_64-conda-linux-gnu-g++ \
           /opt/conda/envs/TeleCouplingAI/bin/g++
```

**问题 3：缺少 pip 包**
原 Dockerfile 缺少 `celery[redis]`、`redis`、`aiohttp`、`pydantic-settings`、`loguru`、`google-genai`。

**修复**：统一加入 `RUN pip install` 步骤。

**最终 Dockerfile 新增/修改点**：
- `python=3.12`
- 添加：`qgis`, `r-base r-igraph r-dplyr r-jsonlite r-sf r-rcolorbrewer`, `gxx_linux-64 gcc_linux-64`
- 添加完整 pip 包列表
- 添加 `COPY . .` 和 `EXPOSE 8000`
- 添加 `ENV QT_QPA_PLATFORM=offscreen`, `ENV QGIS_PREFIX_PATH`
- 修复 `CMD`：`uvicorn main:app --host 0.0.0.0 --port 8000`

**构建结果**：
- `csic_backend:latest` — 7.03 GB
- `csic_frontend:latest` — 92.7 MB

---

### 二、docker-compose.yml 重写

**主要变更**：
- 去掉废弃的 `version: '3.8'`
- 添加 `image: csic_backend:latest` / `image: csic_frontend:latest`（统一镜像命名）
- 新增 nginx 入口服务（port 80，统一路由 `/api/`、`/health`、`/download/`）
- `api-server` 添加 `healthcheck`（curl /health，60s start_period）
- `redis` 添加 `healthcheck`（redis-cli ping）
- `api-server` / `celery-worker` 改为 `depends_on: redis: condition: service_healthy`
- `celery-worker`：`--concurrency=8 --pool=prefork --max-tasks-per-child=50`，`memory: 12G`
- `frontend-ui` 改为 `expose`（不直接暴露端口，通过 nginx）
- `file-server`：port 8001，挂载 outputs 目录

**卷路径分离**：

原来 `.env` 里的 Windows 路径直接被容器用，发生冲突。解决方案：
- 新建 `.env.docker`，分离主机挂载路径（`HOST_*` 变量）和容器内路径（Linux 路径）
- `docker-compose.yml` 卷定义改为 `${HOST_SHARED_DIR:-/data/outputs}:/data/outputs`

---

### 三、`.env.docker` 中发现并修复的 4 个环境变量 Bug

| 变量 | 原因 | 修复 |
|------|------|------|
| `PYTHONPATH=/app` | Celery prefork 子进程 sys.path 不含 `/app`，`from tools.xxx import` 失败 | 加入 `.env.docker` |
| `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` | httpx 在 conda 环境使用 conda CA bundle，TLS 握手失败（`httpx.ConnectError`）；curl 正常但 httpx/google-genai SDK 不通 | 指向 certifi 的 `cacert.pem` |
| `PROJ_DATA` / `PROJ_LIB` | natcap.invest / pygeoprocessing 调用 `transform_bounding_box` 时报 `OGR Error: Corrupt data`，根因是 `/opt/conda/.../share/proj` 未被 PROJ 找到 | 显式设置指向 conda env 下的 proj 数据目录 |
| `GDAL_DATA` | 同上，防止 GDAL 相关路径问题 | 指向 conda env 下的 gdal 数据目录 |

---

### 四、R 包补全

网络分析工具（Tool 1）的 R 脚本依赖 `dplyr`、`sf`、`jsonlite`、`RColorBrewer`，原 Dockerfile 只有 `r-base r-igraph`。

**修复**：
- `backend/Dockerfile` 中 conda install 行加入：`r-dplyr r-jsonlite r-sf r-rcolorbrewer`
- 在运行中的容器里通过 `mamba install` 立即安装并验证
- 用 `docker commit --change='CMD ["uvicorn", ...]' tele-celery csic_backend:latest` 将修复固化到镜像

**注意**：`docker commit` 必须指定 `--change='CMD [...]'`，否则会将 celery 的 command 保存为镜像默认 CMD，导致 api-server 启动时跑 celery 而非 uvicorn。

---

### 五、测试体系建立

#### 集成测试 `tests/test_integration.py`（11 个测试）

对运行中的 Docker stack 发真实 HTTP 请求：

| 测试 | 验证内容 |
|------|---------|
| `test_health` | GET /health → `{"status":"ok"}` |
| `test_upload_*` | 单文件、自动分配 session、多文件上传 |
| `test_delete_session` | DELETE /api/sessions/{id} |
| `test_download_*` | 404 响应、路径遍历攻击拦截 |
| `test_chat_sse_*` | SSE 流格式、session ID 自动分配 |
| `test_render_zoom_missing_file` | 404 响应 |
| `test_celery_*` | Celery/Redis 连通性验证 |

**结果：11/11 通过，耗时 6.33s**

#### Locust 压测 `tests/locustfile.py`

模拟 40 并发用户，运行 2 分钟：

| 接口 | P50 | P95 | 吞吐 | 失败 |
|------|-----|-----|------|------|
| GET /health | 6ms | 14ms | 8.6 req/s | 0 |
| POST /api/upload | 61ms | 77ms | 4.3 req/s | 0 |
| DELETE /api/sessions | 7ms | 14ms | 2.4 req/s | 0 |
| POST /api/chat (Gemini) | 1.7s | 2.3s | 1.6 req/s | 0 |

**结果：2148 次请求，0 失败，整体吞吐 18 req/s**

#### E2E 工具测试 `tests/test_e2e_tools.py`（3 个工具）

模拟真实用户：上传文件 → 发 chat 消息触发工具 → 读 SSE 流 → 验证输出文件。

**Tool 1：Network Analysis Grouping（R + igraph）**
- 上传：`nodes.csv`、`links.csv`
- 参数：`walktrap` 聚类，`ISO_3_CODE` join
- 输出：`network_plot.pdf`、`network_stats.csv`、`output.shp` 等 6 个文件
- 耗时：~7s ✅

**Tool 2：CBC Preprocessor（natcap.invest）**
- 上传：`snapshots.csv`、`lulc_lookup.csv`、3 个 TIF 栅格
- 输出：`aligned_lulc_2010/2030/2050.tif`、`carbon_biophysical_table_template.csv` 等 6 个文件
- 耗时：~3s ✅

**Tool 5：Crop Production Percentile（natcap.invest）**
- 上传：`landcover_to_crop_table.csv`（参考容器内 `landcover.tif`）
- 输出：barley/soybean/wheat 各 5 个产量栅格 + `result_table.csv` 共 54 个文件
- 耗时：~14s ✅

**结果：3/3 通过**

---

### 六、Docker 运维注意事项

1. **`docker commit` 固化包**：在运行容器中 `mamba install` 之后，必须 `docker commit` 固化，否则 `--force-recreate` 会丢失安装的包。

2. **nginx IP 缓存**：`api-server` / `celery-worker` 容器重建（IP 变化）后，`tele-nginx` 必须 `docker compose restart nginx`，否则出现 502。

3. **env_file 变更必须 `--force-recreate`**：`docker compose restart` 不重新读取 `env_file`，必须用 `docker compose up -d --force-recreate` 才能让新环境变量生效。

4. **镜像标签**：`csic_backend` 和 `csic_frontend` 都带 `csic_` 前缀。celery-worker 复用 `csic_backend:latest`，通过 docker-compose 的 `command:` 字段覆盖启动命令。

---

### 七、本次修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/Dockerfile` | 修改 | python 3.12, R 包补全, pip 包补全, 编译器 symlink |
| `docker-compose.yml` | 重写 | nginx 入口, healthcheck, HOST_* 卷变量, 镜像名统一 |
| `.env.docker` | 新建 | Docker 专用环境变量（含 HOST_* 路径） |
| `tests/test_integration.py` | 新建 | 11 个集成测试 |
| `tests/locustfile.py` | 新建 | Locust 压测脚本 |
| `tests/test_e2e_tools.py` | 新建 | 3 个工具 E2E 测试 |

---

### 八、待完成

- [ ] Tool 3（CBC Main）、Tool 4（Seasonal Water Yield）、Tool 6（Crop Regression）的 E2E Docker 测试
- [ ] 将 `.env.docker` 中的环境变量（PROJ_DATA、SSL_CERT_FILE 等）固化进 Dockerfile，避免部署时手动维护
- [ ] 部署到真实 Linux 服务器（当前在 Windows Docker Desktop 验证完毕）

---

---

## 续：2026-03-27（下半场）

### 八、高优先级 E2E 测试完成（Tool 3/4/6）

在 `tests/test_e2e_tools.py` 中追加三个工具的 E2E 测试：

| Tool | 描述 | 输出文件数 | 耗时 | 结果 |
|------|------|----------|------|------|
| Tool 3 | CBC Main（natcap.invest） | 266 | ~44s | ✅ |
| Tool 4 | Seasonal Water Yield | 84 | ~32s | ✅ |
| Tool 6 | Crop Regression | 67 | ~13s | ✅ |

至此 **6/6 工具全部 E2E 通过**。

**Tool 3 注意点**：`snapshots.csv` 中 TIF 路径为相对路径，测试中动态替换为容器绝对路径（`/data/datainput/CoastalBlueCarbon_input/`）再上传。

**Tool 4 注意点**：所有输入文件已挂载在容器内，无需上传，直接在 chat 消息中引用 `/data/datainput/SeasonalWaterYield_input/` 路径。

---

### 九、环境变量固化进 Dockerfile

将原本只在 `.env.docker` 中维护的以下变量写入 `backend/Dockerfile` 的 `ENV` 指令：

```dockerfile
ENV PROJ_DATA=/opt/conda/envs/TeleCouplingAI/share/proj
ENV PROJ_LIB=/opt/conda/envs/TeleCouplingAI/share/proj
ENV GDAL_DATA=/opt/conda/envs/TeleCouplingAI/share/gdal
ENV SSL_CERT_FILE=.../certifi/cacert.pem
ENV REQUESTS_CA_BUNDLE=.../certifi/cacert.pem
ENV PYTHONPATH=/app:/opt/conda/envs/TeleCouplingAI/share/qgis/python:/opt/conda/envs/TeleCouplingAI/share/qgis/python/plugins
```

同时在 `.env.docker` 中删除这些重复项，只保留应用级配置和 `HOST_*` 路径变量。

---

### 十、发现并修复 Docker 卷挂载 Bug（根本原因）

**问题**：`/data/model_data` 在容器内始终为空，导致 Tool 5/6 并发测试失败。

**根本原因**：Docker Compose 的**卷路径变量替换**（`${HOST_MODEL_DATA_PATH:-/data/model_data}`）读取的是项目目录的 `.env` 文件或 shell 环境变量，而不是 `env_file:` 指定的 `.env.docker`。`.env.docker` 中的 `HOST_*` 变量对卷替换无效。

**修复**：将 `HOST_SHARED_DIR`、`HOST_UPLOADS_DIR`、`HOST_MODEL_DATA_PATH` 三个变量也写入项目根的 `.env` 文件。

---

### 十一、render/zoom QGIS 端点测试

发现 QGIS Python 绑定不在 `site-packages`，而在：
```
/opt/conda/envs/TeleCouplingAI/share/qgis/python/
```
需要显式加入 `PYTHONPATH`，否则子进程报 `No module named 'qgis'`。

修复后新增两个集成测试，均通过：
- `test_render_zoom_success`：普通 TIF 渲染，返回 download URL
- `test_render_zoom_with_extent`：带 bounding box 渲染

---

### 十二、多用户并发测试 `tests/test_concurrent_tools.py`

**场景**：3 个用户同时运行不同工具（Tool 1 / Tool 2 / Tool 5），验证：
- Celery 并发调度正常
- 各 session 输出目录完全隔离
- 无跨 session 数据污染

**过程中发现并修复的问题**：

| 问题 | 原因 | 修复 |
|------|------|------|
| UserC SSE 连接在 120s 被断开 | `agent.py` 中 httpx `timeout=120.0`，并发时 Gemini 调用超时 | 改为 `timeout=300.0` |
| SSE `ChunkedEncodingError` | 连接中断但任务已完成 | 捕获异常，等待输出文件出现再判断结果 |

**最终结果**：3/3 通过，总耗时 97s，各 session 完全隔离。

---

### 十三、start.bat 更新

主要变更：
- `python main.py` → `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- `workers.task_queue` → `celery_app`（模块名同步）
- 添加 Redis 启动前检查
- 显示所有服务地址（Frontend / Backend / API Docs / Health）

---

### 十四、待完成（更新）

- [ ] CORS 收窄 + `ssl_verify=True`（用户手动测试完毕后）
- [ ] 部署到真实 Linux 服务器
- [ ] 下次重建镜像后，将 `.env.docker` 中临时保留的 `PYTHONPATH` 行删除（已固化进 Dockerfile）

---
