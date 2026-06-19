# CSIS Platform — Roadmap

> 长期/跨周的工程计划写在这里。**本周的执行细节、决策记录走 `DEV_LOG.md`**。
> 这份文档只列"在做/将做/已完成"的大项，不记录每天进度。

---

## In progress

### Tier 1 + Tier 2 lite：SSE 心跳 + 客户端静默 retry（**完成于 2026-06-16**）
- [x] 后端引入 `sse-starlette`，`/api/chat` 改用 `EventSourceResponse(ping=15)` 自动心跳
- [x] 后端给每条 SSE 事件加 `id: <seq>`（为 Tier 3 续传打基础）
- [x] 前端引入 `@microsoft/fetch-event-source`，替换裸 fetch
- [x] 前端 onerror 静默 retry（在收到第一个真实事件之前），不向 UI 透出"重连中"字样
- [x] 修复 MSU `.env.docker`：删手写的 `FILE_SERVER_URL`，改用 `SERVER_BASE_URL=https://ai.telecoupling.msu.edu`，让 `config.py` 派生公网下载链

**解决的问题**：MSU WAF 因 SSE 空窗期（agent 思考 / Celery 跑工具时无字节）切断连接，浏览器报 `Failed to fetch`；以及下载链接写死 `35.9.219.33` 公网用户访问不到。

---

## Next up — Tier 3：任务 ID 解耦 + 服务端事件 buffer + Last-Event-ID 续传

**目标**：让连接断了之后能从断点续传、用户关浏览器再回来仍能拿到结果、后端容器部署时进行中的对话不中断。

**为什么 Tier 1/2 不够**：
- 心跳只能保活"还活着的连接"——用户主动关浏览器、跨设备、后端部署重启等场景，连接是真的没了，没法保活
- Tier 2 lite 的 retry 在我们目前的实现里只在"还没收到事件"的窗口期重连；一旦 agent 已经开始输出，retry 会重跑整个 agent → 工具被重复触发 → 副作用
- Tier 3 在服务端按 `(session_id, request_id)` 把所有事件 buffer 到 Redis；客户端断了重连时带 `Last-Event-ID` header，服务端从那个 id 之后续传 → 用户**完全感知不到**连接断过

### 设计草案

**API 拆分**：
```
POST /api/chat/start    → { request_id }            异步启动任务，立即返回
GET  /api/chat/stream/{request_id}  (SSE)           连流；支持 Last-Event-ID 续传
GET  /api/chat/result/{request_id}                  拿完整结果（用于关浏览器再回来）
```

兼容旧前端：`POST /api/chat` 保留，内部等价于 start + stream 一气呵成；前端逐步迁移。

**Redis schema**：
```
csis:events:{request_id}        → list of JSON events (RPUSH, LRANGE)
csis:events:{request_id}:meta   → hash {status: pending/streaming/done/error, started_at, ended_at, last_event_id}
csis:events:{request_id}        TTL = 24h
csis:user:{session_id}:requests → sorted set of request_ids (for "show my recent tasks")
```

**事件写入时机**：
- 每条 event 原子性：`MULTI / RPUSH events / HSET meta last_event_id / EXEC`
- 流结束（正常 / 异常）都写 `:done` 标记 event

**前端状态机**：
- 提交 → 拿 `request_id` → 存 `localStorage` → 连 stream
- 断了 → 自动用 `Last-Event-ID` header 重连同一 `request_id`
- 刷新页面 → 读 localStorage 里"未完成"的 request_id → 自动重连
- 跨设备：UI 加"我的进行中任务"列表，按 session 维度展示

### 工作量估算
| 模块 | 估时 | 关键风险 |
|------|------|---------|
| Redis schema + 原子写入 | 0.5 天 | 顺序保证、错误情况下不漏写 `:done` |
| 后端 `/api/chat/start` + `/stream/{id}` | 1 天 | 兼容旧 `/api/chat` 不破坏现有 frontend |
| Last-Event-ID 重放逻辑 | 0.5 天 | 边界：last_id 不存在、流已结束、过期 |
| 前端状态机改造 + localStorage 持久化 | 1 天 | 多 tab 同 session 的并发处理 |
| "进行中任务"列表 UI | 0.5 天 | UX 设计、删除/重试操作 |
| 端到端测试矩阵 | 0.5 天 | 人为切连接、重启容器、多 tab |
| **合计** | **3.5–4 天**（含测试与联调） | |

### 排期建议
- **下周（2026-06-22 那一周）**：单独开 PR、独立测试，不与其他功能混
- **不影响 Tier 1**：Tier 3 上线后心跳依然保留（防 idle、不让 WAF 误杀活连接）

### Tier 3 不解决的（明确划界）
- 流式 token 延迟 / 卡顿（属于 LLM 服务质量，不在这里）
- 工具自身 bug（Celery 任务失败仍然失败；Tier 3 只保证"失败也不悄悄丢失"）
- 业务逻辑错误

---

## Next up — Use-Case Level Workflow（用户给目标，AI 规划+串多工具完成）

- 设计草案：`usecaseLevel_workflow/WORKFLOW_DESIGN.md`（v0.1）。
- 交互模型已敲定：**用户说目标 → AI 给计划 + 列数据清单(A) → 用户传文件/确认 → 确定性编排器执行 → 结果 + 解读**；缺数据时边跑边补问(B 兜底)。架构 = Plan → Confirm → Execute → Synthesize（LLM 只管规划+解读，执行交确定性编排器）。
- 第一个案例：卧龙生态旅游，数据 + 工具映射见 `usecaseLevel_workflow/TourismTelecoupling_Workflow/WORKFLOW.md`（5 步：Systems→Network→Flows→CO2→FAMD，3 步零改数据、2 步已预处理好）。
- 依赖：长任务执行底座建在 **Tier 3** 上（建议合建或 Tier 3 先行）。
- MVP 验收：tourism 在 GCP dev 端到端跑通、出图对照论文 Fig。落地步骤见设计草案 §10（先零开发 spike）。

---

## Backlog（未排期）

来自 Run 1 用户系统测试反馈（详见 `Systematic_tests/UserSystematicTest_Run1_20260610/FeedbackResults/`）：

- **BUG 2 — 渲染图 "Preview expired"**：render 出来的 PNG 链接 TTL 太短，或新一次渲染让旧链接作废。需查 `render_spatial_file` 链接生成 + nginx 缓存策略。
- **BUG 3 — AI 把 `report.html` 喂给 `read_file_content`**：在 carbon-storage SKILL.md / system prompt 里约束：不要尝试用 `read_file_content` 读 .html，改提示用户下载或描述 InVEST summary。
- **BUG 4 — Markdown base64 图片爆屏**：渲染输出的 `data:image/png;base64,...` 被前端 markdown 当文本渲染。要么后端不传 base64 入聊天文本，要么前端 markdown 检测 inline image 不展示长字符串。
- **BUG 5 — 渲染图缺 legend / color bar**：`render_spatial_file` 默认输出灰度无 legend，NoData 黑色和低值难分。给默认 legend + color bar + NoData 透明。
- **BUG 6 — 「假渲染」：AI 谎称出图但无图（2026-06-18 自测中复现）**：
  - 症状：首次「please show xxx.shp」→ AI 回「Here is the rendered map: systems_render.png … You can download this image」**但前端无图**；原样重发第二次才正常出图。
  - 根因（代码已核实）：前端只有收到 `render_spatial_file` 真正执行后发出的 `tool_result`(`render_type='image'`)/`image_url` 事件才显示图（`App.jsx` 311–316）。无图=**LLM 根本没调用渲染工具，只是用文字"演"了成功**。两个叠加原因：① `_TOOL_KEYWORDS` 里没有 render/show/可视化 → 渲染调用 100% 靠 LLM 非确定性自觉，无兜底；② 系统提示词第 317 行 *"若之前已渲染过则不要重生成，只按文件名说'已显示在上面'"* —— 会话里已存在早先的 `systems_render.png` 时，模型误判"已渲染"并照此句剧本谎报。
  - 修法：①收紧提示词——用户明确 show/render/display 某文件时必须对该文件调用 `render_spatial_file`；删/收窄"已显示在上面"逃生口（仅限上一轮刚渲染同一文件）；严禁未真正调用就声称出图。②可选加兜底：检测 "show/render/可视化"+`.shp`/`.tif` 文件名时偏向/强制走渲染工具。
  - 时机：待 Run 2 工具自测（37→44）跑完再改 `agent.py` + 重新部署 MSU，避免扰动在测流程。
  - ✅ **已修（GCP dev，2026-06-18）**：`agent.py` 系统提示词——删掉宽口径"已渲染过就说已显示在上面"逃生口（收窄为"仅上一轮我自己刚渲染过同一文件"才可免调）；新增硬规则"未真正调用 `render_spatial_file` 就声称/暗示已出图 = hard error，会给用户留下无图"；用户 show/render/display/可视化 某 .tif/.shp 时必须调渲染工具。已部署 GCP，39/39 healthy。**行为侧需真人聊天验证**（不在此自动测 LLM）。**MSU 暂未同步**。可选的"关键词强制兜底"留作后续。
- **BUG 7 — Nutrition Metrics 对 sex 取值不健壮：不匹配就静默出空图（2026-06-18 自测中发现）**：
  - 症状：工具 42 输出 `nutrition_ller_chart.png` 全空（无 bar 无线）。
  - 根因（源码核实）：`nutrition_metrics.py` 的 `_BMR_EQUATIONS`/`_DEFAULT_WEIGHTS` 用 `male`/`female` 做 key；样本 CSV `sex` 列是 `M`/`F`，`.lower()` 后是 `m`/`f`，匹配不上 → `_ller_per_person()` 每行返回 0.0 → 全部 LLER=0 → 柱状图全 0 高 → 空图。**且全程无报错/无警告**。
  - 已临时修复（仅测试数据）：把 `42_nutrition_metrics/input_data/nutrition_data.csv` 的 sex 改成 `male`/`female`。
  - 产品侧待修（需改 `nutrition_metrics.py` + 重部署）：① 归一化 sex 取值（`m`/`male`/`Male`/`男`→male，`f`/`female`/`Female`/`女`→female）；② 当某行 age_group 或 sex 匹配不到公式时，至少记一条 warning 事件，避免"静默 0"；③ 同理 age_group 也应容错。
  - 时机：与 BUG 6 一起，待 Run 2 跑完再改后端重部署。
  - ✅ **已修（GCP dev，2026-06-18）**：`nutrition_metrics.py`——加 `_normalize_sex()`（`m/male/man/boy/男→male`，`f/female/woman/girl/女→female`，不认的归 None）+ `_normalize_age_group()`（统一 en/em dash、去空格）；统计未匹配的 sex/age 值；**全零结果直接抛 `CSISError`（绝不静默出空图）**，部分未匹配则在返回里带 `warnings`；图表配色对 ≠2 类做防御。GCP 容器内实测：`M/F` 输入产出 33KB 真图、总 LLER=7,088,367 kcal/day（修复前=0）；乱码 sex 输入抛清晰错误。**MSU 暂未同步**。
- **UX — 上传页面预先说明文件类型**（zyt / 郭玉婷）
- ✅ **UX — 一键打包下载结果（ZIP）**（zyt；**2026-06-18 已实现并部署 MSU**）
  - **范围=单张结果卡（一次工具运行）**，不是整会话（用户反馈初版把整会话都打包了，已修正）。
  - 后端 `POST /api/download_zip/{session_id}`（`main.py`，sync def→threadpool）：body `{paths:[内部路径]}`，逐路径校验 `relative_to(session_root)` 必在该会话目录下才收（防越权/穿越），过期文件跳过；临时 zip + `FileResponse` + `BackgroundTask(os.unlink)`；无文件→404。
  - 前端 `ResultFiles.jsx`：「Download all (.zip)」按钮 POST 本卡 `files.map(f=>f.path)` → 收 blob 触发下载（带 zipping 态 + 过期 alert）。`App.jsx` 把 `sessionId` 透传 `MessageContent`→`ResultFiles`。
  - 仍待观察：大包走 MSU WAF 的下载超时（线上实测）。
- ✅ **UX — 支持整文件夹上传**（用户 2026-06-18 提出，**当日已实现，本地 build 通过，待部署**）
  - 前端：`App.jsx` 输入栏加「文件夹」按钮 + 隐藏 `<input webkitdirectory>`；选中的 File 自带 `webkitRelativePath`，chip 显示相对路径。`streaming.js` 上传时并行 `formData.append('paths', f.webkitRelativePath||f.name)`。
  - 后端：`/api/upload` 增 `paths: list[str]=Form([])`，按 `_safe_relpath()`（剥离 `..`/绝对/盘符，纯保留相对段）重建子目录写盘；外加 `resolve()` 必须在 upload_root 下的二次防穿越校验。已用 8 个用例验证（`../../etc/passwd`→`etc/passwd` 不外逃等）。
  - **与 HRA 拍平问题直接相关**：文件夹上传保留相对路径后，CSV 用 `habitat_layers/eelgrass.tif` 这类子目录引用可原生解析，理论上不必再手工拍平+改 CSV（部署后用 HRA 原始包实测验证）。
  - 注意点：大文件夹走 MSU WAF 的体积/超时待部署后实测。
- **UX — 地图交互化**（Logan，workshop 用户期望）
- **UX — 渲染输出的手动 UI 控制兜底**（Xin：AI 改不动 legend 时用户能自己调）
