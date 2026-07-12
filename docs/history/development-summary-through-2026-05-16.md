# CSIS 平台历史开发摘要（截至 2026-05-16）

> **归档文件，不再追加。** 项目唯一权威开发日志是仓库根目录
> `DEV_LOG.md`。本文件是该日志截至 2026-05-16 的**整理重写版**：
> 通读全部历史后按时间倒序（新 → 旧）重排，
> 合并重复记录、去除冗长代码块与噪音，保留所有关键技术事实（根因、测试结果、commit）。
> 覆盖范围 2026-03-16 ~ 2026-05-16，共 5 个开发阶段、42 次工作记录。

## 开发阶段概览

| 阶段 | 时间 | 主线 |
|------|------|------|
| 一、POC 基础搭建 | 2026-03 | 6 个工具的后端 + agent + Skills 架构，Claude→Gemini，Docker 化 |
| 二、上云与并发加固 | 2026-04 | GCP 部署，并发竞态根治（队列隔离 + SSE 修复），平台功能完善 |
| 三、InVEST 工具大扩展 | 2026-05-04 ~ 08 | 工具从 6 个扩展到 26 个，LLM 路径调通 |
| 四、TeleBox 工具 + 系统化测试 | 2026-05-14 ~ 15 | 新增 15 个非 InVEST 工具（共 41/42），测试体系重组 |
| 五、全量验证与上线 | 2026-05-16 | GCP 四层测试全通过，Recreation 下架，仓库整理 |

## 目录（新 → 旧）

- 2026-05-16 — 提交 2026-05-16 测试批次 + 仓库清理
- 2026-05-16 — 修复 "list all tools" 输出格式
- 2026-05-16 — Recreation & Tourism 工具下架（Tool 26）
- 2026-05-16 — Manual_ClientToGCP_test 测试指南生成（42 工具）
- 2026-05-16 — Smoke / 并发压力测试通过
- 2026-05-16 — 浏览器自动化测试全量通过
- 2026-05-16 — GCP LLM 路径测试全量通过
- 2026-05-15 — GCP 直接工具测试全量通过
- 2026-05-15 — GCP 四级测试套件全量执行
- 2026-05-15 — GCP 完整部署（42 工具上线）
- 2026-05-15 — GCP 部署前代码审查 + 测试套件扩展
- 2026-05-15 — 测试文件重命名 + 本地运行器扩展到 42 工具
- 2026-05-15 — 全平台测试统一（108 tests）
- 2026-05-15 — 新工具 pytest + 本地运行器 + bug 修复
- 2026-05-15 — 测试体系重组（Systematic_tests/）
- 2026-05-14 — 15 个 TeleBox 工具全量实现
- 2026-05-14 — 15 个新工具 SKILL.md
- 2026-05-08 — 跨轮文件注入 + 多轮参数补全 + GCP Redis 修复
- 2026-05-06 — 对话记忆 + 前端拖拽上传 + 空消息修复
- 2026-05-06 — SDR 函数名重命名实验 + agent.py 重试优化
- 2026-05-06 — LLM 路径英文 prompt 10/10 全通过
- 2026-05-05 — LLM 路径测试 8/10 → 10/10
- 2026-05-05 — Gemini LLM 路径端到端测试 + FunctionDeclaration 补全
- 2026-05-04 — 完整集成测试 26/26 + GCP 部署
- 2026-05-04 — 新增 Recreation & Tourism（第 26 工具）
- 2026-05-04 — 新增 Coastal Vulnerability + Offshore Wind Energy
- 2026-05-04 — InVEST 工具扩展（14 个新工具，6→20）
- 2026-04-29 — 禁用自动渲染 + HTTP 422 修复 + 完整部署
- 2026-04-06 — 平台全面升级（下载 / QGIS / Markdown / 域知识）
- 2026-04-04 — 前端 crypto.randomUUID HTTP 兼容修复
- 2026-04-04 — P1 队列隔离 + SSE 并发修复（深夜）
- 2026-04-04 — 仿真测试 v2 + 50 人压力测试（晚）
- 2026-04-04 — GCP E2E 测试 + 并发问题暴露（下午）
- 2026-04-04 — GCP Docker 部署
- 2026-04-04 — GCP 服务器创建 + SSH 配置
- 2026-03-27 — Docker 部署 + 全栈验证
- 2026-03-27 — 端到端集成测试（6 工具）
- 2026-03-25 — 环境验证 + 依赖修复
- 2026-03-25 — 全面 Review 修复 11 个问题
- 2026-03-25 — AI 后端从 Claude 切换为 Gemini
- 2026-03-16 — agent.py + Skills 两阶段加载架构
- 2026-03-16 — 测试脚本修复 + 环境配置 + QGIS 渲染

---

# 阶段五 — 全量验证与上线（2026-05-16）

## 2026-05-16 — 提交 2026-05-16 测试批次 + 仓库清理

- 将 2026-05-16 全部未提交工作提交到 `feature/invest-expansion`（commit `1648a27`，57 文件 / 5718 行新增），并 push 到 GitHub（领先远程 32 个提交一次性同步）。
- 删除误重定向产生的 0 字节垃圾文件 `total=%.1fs`。
- 删除废弃的内层仓库 `telecouplingAI-project/.git`（HEAD 停在 2026-05-04），开发统一用外层 `fulldev` 仓库，避免子目录误操作 git。
- `references/Telecoupling+Toolbox_ArcGISProV3.3/`（8.5 MB ArcGIS 工具箱资料）按决定保持不跟踪。

## 2026-05-16 — 修复 "list all tools" 输出格式

- **问题 1**：`list all tools` 返回 `Tool Name: run_xxx`（函数名而非描述）。根因：`agent.py` 的 `_BASE_SYSTEM_INSTRUCTION` 中 "Available Tools Overview" 只列了 8 个工具且用函数名。修复：替换为完整 41 工具 markdown 列表（`- **名称**: 描述`，分 InVEST / TeleBox / Utility 三组）。
- **问题 2**：每次回复前自动加 "I am an expert in Telecoupling toolbox..." 前缀。根因：Greeting Behaviour 指令让 LLM 把该句当成所有回复的 opener。修复：删除整个 `## Greeting Behaviour` 节。
- 关键变更：`backend/agent.py`。GCP 验证通过。

## 2026-05-16 — Recreation & Tourism 工具下架（Tool 26）

- 原因：该工具依赖外部 NatCap recmodel server（`34.44.144.58:54321`），无访问权限。
- `agent.py`：移除 `run_recreation_tourism` 的 FunctionDeclaration 及 `_SINGLE_TOOL_KEYWORDS` / `_TOOL_QUEUES` 条目 —— LLM 不再看到、调用或在 "list all tools" 中列出该工具。
- `workers/task_queue.py`：import 替换为内联 stub，万一触发返回友好错误 `temporarily unavailable`。
- 工具文件本身（`tools/recreation.py`、SKILL.md）保留，仅从调用链断开。

## 2026-05-16 — Manual_ClientToGCP_test 测试指南生成（42 工具）

- 编写自包含脚本 `Systematic_tests/Manual_ClientToGCP_test/_generate_guides.py`，运行后生成 42 个工具子目录、各含 `how_to_test.md`，外加顶层 `README.md`（InVEST 27 + TeleBox 15 索引表）。
- 覆盖特殊情况：需 patch 的工具（02/03/05/06/08/15）标注 patch 路径；大文件服务器预装工具（23 Wave / 25 Wind）注明传服务器路径勿上传；Tool 26 标 SKIP；SWY 提示上传 24 个月度栅格。

## 2026-05-16 — Smoke / 并发压力测试通过

- 新建 `AI_GCP_smoke_test/run_AI_GCP_smoke_test.py`：在 GCP 宿主机经 nginx（localhost:80）做快速冒烟 + 轻量并发压力。
- 4 个代表工具：07 Carbon Storage / 09 Annual Water Yield / 28 OLS / 30 CO2。
- **Phase 1**（单用户顺序）：4/4 PASS，12.8s。**Phase 2**（3 并发用户、0–8s 错峰、随机顺序）：12/12 PASS，壁钟 19.4s；CPU peak 27%，内存 peak 9.1 GB / 32 GB。

## 2026-05-16 — 浏览器自动化测试全量通过

- 新建 `AI_GCP_browser_test/run_AI_GCP_browser_test.py`：Playwright（headless Chromium）模拟真实用户 —— 把文件真正拖入上传控件，输入 prompt，等待蓝/绿 ToolStatusCard。`_expand_uploads()` 自动展开 `.shp` → 全 sidecar、目录 → 目录内全部文件。每工具独立浏览器上下文。
- 修复 4 处初始失败：
  - **Tool 17 Urban Flood**：SKILL.md 补 GeoPackage 格式说明 + 多 CSV 时 `curve_number_table` 消歧。
  - **Tool 23 Wave Energy**：上传 WaveData/（811 MB）触发 HTTP 413；改为只传用户侧文件，prompt 中传服务器路径。
  - **Tool 32 Population Density**：prompt 用了不存在的参数，改为 SKILL.md 中的正确参数。
  - **Tool 40 Add Media Flows**：`.html` 被文件白名单拒绝；`backend/main.py` 的 `supported_extensions` 加入 `.html`/`.htm`，重建镜像。
- 结果：**41 PASS / 0 FAIL / 1 SKIP**（Recreation）。

## 2026-05-16 — GCP LLM 路径测试全量通过

- 新建 `AI_GCP_llm_test/run_AI_GCP_llm_test.py`：经 `/api/chat` SSE 接口对全部工具做 LLM 路径测试（stdlib `urllib`，解析 `tool_start`/`tool_result`/`error` 事件）。
- 修复 Docker 网络错误：上次误用根目录 compose 导致 `tele-backend` 进错网络与 Redis 不通；从内层 compose 重启恢复。
- 新增 `.claude` 卷挂载：让 SKILL.md 对容器内 `agent.py` 可见（原镜像中 `/.claude/skills/` 不存在），并支持热更新。
- SKILL.md 修复：`run-urban-nature-access`（补 `dichotomy` 合法值 + 可选参数说明）、`run-coastal-vulnerability`（注明 `slr_*` 可选）。
- prompt 修复：Wave Energy `analysis_area` 用全名、Food Security `indicator_field` 用真实指标名。
- 结果：**41 PASS / 0 FAIL / 1 SKIP**。

---

## 2026-05-15 — GCP 直接工具测试全量通过

- 重写 `AI_GCP_direct_test/run_AI_GCP_direct_test.py`，完整对标本地运行器：Section A（01-27）直接调 `natcap.invest.X.execute()`，Section B（28-42）直接调 backend async 函数。包含全部 CSV patch（`lucode→code`/`lucode→lulc`/strip `load_type_*`/`crop_name→crop`）与参数修正。
- `docker-compose.yml` 新增 `Systematic_tests` 挂载，测试输出直接落宿主机；DATA 路径从旧 `/data/datainput` 改为 `Test_data`。
- 结果：**42 PASS / 0 FAIL**（Tool 26 SKIP）。

## 2026-05-15 — GCP 四级测试套件全量执行

- 测试套件重构为 4 个子目录：`01_direct_tool_test` / `02_llm_tool_test` / `03_smoke_stress_test` / `04_browser_test`。
- 修复 11 个 TeleBox 工具的提示词（参数名、函数名、测试数据格式）。
- 结果：直接测试 27 PASS / 15 SKIP（缺地理数据）/ 0 FAIL；LLM 测试 10/10；冒烟 5 并发 20/20；压力 20 用户 39/40（1 次 OLS 120s 边界超时）。并发下 CPU peak 47%、RAM peak 8.2 GB。

## 2026-05-15 — GCP 完整部署（42 工具上线）

- 环境修复：`.env` 的 `HOST_*` 改回 Linux 路径（上次 tar 传文件覆盖成 Windows 路径）；`.env.docker` 写入真实 API key 与 GCP IP。
- 镜像 `csis-backend:latest`（7.71 GB，含 r-factominer + beautifulsoup4）重打标签为 `csic_backend:latest`。
- `docker compose up -d --force-recreate`：39 个容器全部启动（含 6 个新 TeleBox worker）；nginx restart 刷新 upstream。
- 验证：`/health` ok，前端 200，文件服务器 200。访问地址 http://34.42.83.50/。

## 2026-05-15 — GCP 部署前代码审查 + 测试套件扩展

- `Dockerfile` 补依赖：`r-factominer`（FAMD 必需）、`beautifulsoup4`（Add Media Flows HTML 解析）。
- pytest 套件扩展到 **208 tests，207 PASS / 1 SKIP / 0 FAIL**：`test_tools.py` 64→94、`test_renderers.py` +20、`test_api.py` 修复 fake_agent mock 漏 `chat_history`。
- 本地运行器补入 Tool 01 Network Analysis，42 工具全覆盖。

## 2026-05-15 — 测试文件重命名 + 本地运行器扩展到 42 工具

- `git mv test_new_tools.py → test_telebox_tools.py`（区分 InVEST / TeleBox）。
- `run_all_local_tests.py` 重写：Section A InVEST 02-27、Section B TeleBox 28-42，CLI `--invest`/`--telebox`，Recreation 自动 SKIP，数据路径统一到 `Test_data/`。
- 验证：TeleBox 16/16 PASS、InVEST 25 PASS / 1 SKIP。

## 2026-05-15 — 全平台测试统一（108 tests）

- 重写 `test_invest_integration.py`：数据路径改用 `Test_data/`，统一 `td("NN_folder")` helper；修复 CBC 路径、补 Coastal Vulnerability 缺失 habitat 文件。
- `test_tools.py`：task_queue 工具数从 24 扩到 42。
- 结果：**106 PASS / 1 SKIP / 0 FAIL**（~370s）。新增 `all_tools_test_timing.md` 计时报告。

## 2026-05-15 — 新工具 pytest + 本地运行器 + bug 修复

- 新增 `test_new_tools.py`（工具 28-42 共 17 测试，17/17 PASS）与 `run_all_local_tests.py`。
- 修复 `ols.py`：White 稳健标准误广播 bug（`u2 * x` → `u2[:, np.newaxis] * x`）。
- 修复 `food_security.py`：移除 `pd.read_csv()` 不支持的 `errors=` 参数。
- `.gitignore` 排除 `AI_local_test/*/output/*`；删除旧 `tool_tests/` 目录。

## 2026-05-15 — 测试体系重组（Systematic_tests/）

- 将分散各处的测试文件与数据整合进 `Systematic_tests/` 统一目录，建 5 个语义子目录；42 个工具测试数据集中到 `Test_data/`（`.gitignore` 排除大型二进制）。
- 删除冗余目录：`datainput_for_demo/`、`test_outputs/`、`outputs/`（490 MB 运行产物）、`adhoc_test/`、`tests/`。
- 同次先创建过 `tool_tests/`（84 目录 + 128 文件，含 15 个新工具的最小测试数据），后重命名为 `Systematic_tests/`。

---

# 阶段四 — TeleBox 工具扩展（2026-05-14）

## 2026-05-14 — 15 个 TeleBox 工具全量实现

- 分析 ArcGIS Pro Telecoupling Toolbox v3.3 的 28 个工具，确认 InVEST 部分已全实现；新增 15 个非 InVEST 工具，全部去除 arcpy 依赖，改用 pandas / numpy / scipy / geopandas / shapely / matplotlib / R subprocess。
- 工具列表：OLS Model Selection、FAMD、CO2 Emissions、Cost-Benefit Analysis、Population Density、Radial Flows、Commodity Trade、Add Agents、Draw Agents Table、Add Causes、Add Systems、Draw Systems Table、Add Media Flows、Food Security、Nutrition Metrics。
- 每个工具完整实现：Celery 任务文件 + `task_queue.py` 注册 + `output_router.py` PATTERNS + `agent.py` FunctionDeclaration；`docker-compose.yml` 新增 6 个 Celery worker。

## 2026-05-14 — 15 个新工具 SKILL.md

- 为 15 个新工具各建 `.claude/skills/run-{tool}/SKILL.md`，沿用三段式结构（DEV ONLY / PRE_EXECUTION / POST_EXECUTION），含上传文件感知规则。

---

# 阶段三 — InVEST 工具大扩展与 LLM 调通（2026-05-04 ~ 08）

## 2026-05-08 — 跨轮文件注入 + 多轮参数补全 + GCP Redis 修复

- **跨轮文件注入**（`agent.py`）：原 `context_lines` 只注入本轮上传文件；改为每轮从 Redis session 取 `get_uploaded_files()`，把历史上传文件以 `Previously uploaded file: ...` 追加进上下文。
- **多轮参数补全**：`_BASE_SYSTEM_INSTRUCTION` 新增章节 —— 缺参数时先列清单等待补充、不得提前调用工具、历史已给参数不得再问。
- **GCP Redis URL 修复**：`tele-backend` 因上 session 手动 `docker run` 启动，`REDIS_URL` 错为 `localhost`，导致 `/api/chat` 全 500；改用 `docker compose --env-file` 重启修复。
- GCP 多轮对话验证 PASS。

## 2026-05-06 — 对话记忆 + 前端拖拽上传 + 空消息修复

- **多轮对话记忆**：原 `agent.py` 每轮只传一条消息、丢弃历史。`session_manager.py` 新增 `add_chat_turn` / `get_chat_history`，对话历史存 Redis（保留最近 20 轮）；`main.py` 取存历史；`agent.py` 新增 `chat_history` 参数拼接多轮 Content。
- **前端拖拽上传**（`App.jsx`）：聊天区支持拖入文件，蓝色虚线蒙层提示。Bug：拖回桌面 overlay 不消失 —— 改用 `currentTarget.contains(relatedTarget)` 判断真正离开。
- **空消息修复**（`main.py`）：有文件无文字时自动补默认 prompt。
- 部署踩坑记录：`docker stop/start` 不切换镜像（须 `rm` 后重建）；backend `.env` 在 `telecouplingAI-project/`；nginx upstream 名须为 `frontend-ui`；SSH 用户 `csisaiproject2026`。
- LLM 路径 10/10 全部 0 重试。Commit `c251abf`（23 文件 / 3238 行）。

## 2026-05-06 — SDR 函数名重命名实验 + agent.py 重试优化

- **假设**：`SDR` 缩写多义（Software Defined Radio 等），Gemini 二元决策时进入临界态、需多次重试；而 `NDR`（环境科学专用）一直稳定。
- 验证：`run_sdr` → `run_Sediment_Delivery_Ratio_SDR` 后，首测 0 重试 6.9s 直接成功（21.6s/3 重试 → 10.4s/0 重试）。
- 重试逻辑改进：`_HIGH_TEMP_TOOLS = {run_crop_pollination}`，base temperature 0.9，retry 温度不低于 base —— Pollination 从 69.2s/7 重试 → 26.3s/0 重试。
- **函数名设计原则**：避免多义缩写、避免与常见自然语言概念重名；推荐完整词汇 + 领域前缀 + 含动词。
- 笔记记入 `LLM_VOCABULARY_AGENT_NOTES.md`。

## 2026-05-06 — LLM 路径英文 prompt 10/10 全通过

- 需求：测试 prompt 全部改英文（平台面向美国用户）。
- 根因：Gemini 2.5 Flash 对特定英文 prompt 持续返回 `candidate.content = None`（finish_reason=STOP）。
- 修复（`agent.py`）：① 单工具模式 —— keyword 命中时只传该工具 1 个 FunctionDeclaration（而非 26 个）减少歧义；② 重试对话重置 —— 每次 retry 用全新单轮 `Call fn_name with: {...}` 替换（原来连续追加两条 user 消息违反交替格式）；③ 起始温度 0.3→0.5、重试 8→10 次。
- 结果：英文 prompt **10/10 PASS**。

## 2026-05-05 — LLM 路径测试 8/10 → 10/10

- 诊断：CBC Pre / Crop Pct / SDR / Pollination 在英文 prompt 下失败 —— Gemini 对特定关键词触发安全过滤，返回空 candidate。
- 修复：`agent.py` 对 `candidate.content is None` 加最多 3 次指数退避重试；`test_llm_path.py` 4 个问题工具暂改中文 prompt、AWY `seasonality_constant=15`、间隔 12s。
- 结果：**10/10 全通过**。

## 2026-05-05 — Gemini LLM 路径端到端测试 + FunctionDeclaration 补全

- 为 `agent.py` 补全全部 26 个 InVEST 工具的 FunctionDeclaration（原仅 6 个，其余 20 个 Gemini 无法调用）；`TOOL_TO_SKILL` 从 6 扩到 27。
- 新建 LLM 路径测试 `test_llm_path.py`（自然语言 → Gemini → FunctionCall → Celery → InVEST → SSE）。
- 修复 4 个基础问题：`.env.docker` 真实 API key、NDR 删字符串列、HQ `lucode→lulc`、AWY `seasonality_constant=15`。
- 结果：**8/10 PASS**（Crop Pct、Pollination 失败 —— Gemini 拒绝调用函数）。

## 2026-05-04 — 完整集成测试 26/26 + GCP 部署

- 补全 16 个缺失集成测试（11→27，覆盖全部 26 个 InVEST 工具）。
- 修复 8 处 InVEST 3.14.3 与旧版本的 API 参数名差异（CBC `lucode→code`、SWY `et0_dir`、Scenic `aoi_path`/`refraction`、Wave `dem_path`/`valuation_container` 等），并修复 `scenic_quality.py`、`wave_energy.py`。
- 本地 26/26、GCP 26/26 通过（GCP 33 容器，总耗时 4 分 22 秒）。生成 `TOOL_TIMING_REPORT.md`。
- 计时：最慢 Scenic Quality 43.9s，最快 CBC Preprocessor 0.2s。

## 2026-05-04 — 新增 Recreation & Tourism（第 26 工具）

- 实现 `tools/recreation.py`（`natcap.invest.recreation.recmodel_client`），无需 API key、直连 NatCap 服务器（`34.44.144.58:54321`，Pyro4 RPC）。
- 调研发现：NatCap 服务器活跃且无需认证；本地 Windows 因 HTTPS 代理挡住 Pyro4 TCP，GCP 直连无障碍。
- 集成测试本地自动 skip（TCP 探针）、GCP 自动运行。工具总数达 26。Commit `eba653f`。

## 2026-05-04 — 新增 Coastal Vulnerability + Offshore Wind Energy

- 实现 `tools/coastal_vulnerability.py` 与 `tools/wind_energy.py`，更新 task_queue / agent / output_router / docker-compose（新增 2 个 worker）。
- 新增集成测试（Grand Bahama + New England 样例数据），编写两个 SKILL.md。
- 全部 124 tests passed。工具总数达 22。Commit `4430259`。

## 2026-05-04 — InVEST 工具扩展（14 个新工具，6→20）

- POC 验证成功后，将 InVEST 可行模型批量集成。新建 `feature/invest-expansion` 分支（master 保持 POC 基准）。
- 新增 14 个工具：Carbon Storage、Habitat Quality、Annual Water Yield、Forest Carbon Edge Effect、Crop Pollination、DelineateIt、RouteDEM、SDR、NDR、Urban Cooling、Urban Flood、Urban Stormwater、Urban Nature Access、Scenario Gen Proximity。
- 版本兼容修复（natcap.invest 3.14.3 vs 样本数据 3.17.x）：HQ `lucode/lulc`、AWY `seasonality_constant` 必填、NDR `load_type_*` 列、Pollination `landcover_raster_path`、SDR/NDR 硬编码文件名。
- 测试 62 passed。Commits `e3718a0`、`7a6131b`，SKILL.md `fff0a04`。

---

# 阶段二 — 上云与并发加固（2026-04）

## 2026-04-29 — 禁用自动渲染 + HTTP 422 修复 + 完整部署

- **HTTP 422 修复**（`main.py`）：`message` 改为可选 `Form("")`；空 prompt 返回友好提示；实现文件扩展名白名单，不支持类型跳过并警告。
- **禁用地理文件自动预览**（`output_router.py`）：移除 `_generate_preview()` —— TIF/SHP 工具完成后只返回下载链接，预览改为用户经 `render_spatial_file` 按需触发，减少服务器 I/O。
- 部署到 GCP，12 容器启动验证。Commit `1762791` 推送 GitHub master。

## 2026-04-06 — 平台全面升级（下载 / QGIS / Markdown / 域知识）

- **下载修复**：`nginx.conf` 新增 `/download/` location 同域代理，解决跨域 `download` 属性失效与重复 Content-Disposition header；`/api/chat` 加 `client_max_body_size 500M` 解决 shp 上传 413。
- **QGIS 渲染修复**：Celery prefork worker CWD 非 `/app` 导致 `No module named 'tools'`；`qgis_renderer.py` 固定 PYTHONPATH 把 `/app` 置前。
- **外部 IP 统一**：`config.py` 新增 `SERVER_BASE_URL`，迁服务器只改一处。
- 新增 `read_file.py`（CSV/TXT/JSON 读取工具）；`App.jsx` 引入 `react-markdown` 修复 `**bold**` 显示为原文。
- 域知识注入：`_BASE_SYSTEM_INSTRUCTION` 加 Domain Knowledge 章节 + 6 个 SKILL.md 的 POST_EXECUTION 扩充。
- SSH 密钥清理：统一用 `id_ed25519_csis` + `csisaiproject2026`。

## 2026-04-04 — 前端 crypto.randomUUID HTTP 兼容修复

- 问题：经 `http://`（非 HTTPS）访问页面空白，`crypto.randomUUID is not a function`（Secure Context API 在非 HTTPS/非 localhost 不暴露）。
- 修复：`frontend/src/lib/session.js` 加 fallback —— HTTP 下用 `Math.random` 实现 UUID v4。重建前端镜像热更新，HTTP/HTTPS 均可访问。

## 2026-04-04 — P1 队列隔离 + SSE 并发修复（深夜）

- **P1 工具级队列隔离**：每种 InVEST 工具分配独立 Celery 队列、`concurrency=1`，从根本消除 GDAL 多进程竞态。`agent.py` 新增 `_TOOL_QUEUES` 路由（`.delay()` → `.apply_async(queue=...)`）；`docker-compose.yml` 单体 worker 拆为 7 个独立 worker。
- **SSE 并发 Bug 修复**（`main.py`）：`event_stream()` 未在生成器清理时取消后台 agent task，客户端断开产生 zombie task 干扰其他连接 —— 加 `finally` 中 `agent_task.cancel()`。
- 结果：E2E Phase 2（5 并发）从 66% → **30/30 (100%)**；50 人压力测试从 40% → **98/100**，吞吐 15.7 → 37.7 次/分。

## 2026-04-04 — 仿真测试 v2 + 50 人压力测试（晚）

- 测试脚本升级：随机错峰到达（0–8s）、每用户随机工具顺序、`tool_invoked=False` 自动重试一次、系统指标采集；新增 `test_stress_50.py`。
- 结果（修复前）：E2E Phase 2 17/30 (56%)；50 人压力 40/100 (40%)。
- **根因分析**：失败工具 1–4s 内结束、无输出无报错 —— Celery 多 worker 并发执行 InVEST 时底层 GDAL 临时文件/全局缓存冲突。单用户 100%、多用户失败，证实是并发竞态而非数据问题。硬件非瓶颈（CPU peak 55%）。
- 待修复项排序：P0 独立 `GDAL_TMPDIR`、P0 失败正确回传 error 事件、P1 工具级队列 `concurrency=1`。

## 2026-04-04 — GCP E2E 测试 + 并发问题暴露（下午）

- **Bug 修复**：E2E 脚本先 `/api/upload` 再单独 `/api/chat`，agent 收不到文件 —— `session_manager.py` 新增 `get_uploaded_files()`，`main.py` 调 `run_agent()` 前注入历史上传文件（浏览器前端把文件与消息一起发，绕过了此 bug 所以一直没发现）。
- Gemini 并发限流：30 并发调用频繁触发 429/503 —— `agent.py` 加 `asyncio.Semaphore(3)` + 指数退避重试。
- Celery worker `concurrency` 2→4。
- E2E 结果：Phase 1 6/6，Phase 2 22/30（残余失败为 LLM 高并发下偶尔要求确认而非调用工具）。

## 2026-04-04 — GCP Docker 部署

- 服务器装 Docker CE（29.3.1）；创建 `/data/{outputs,uploads,model_data}`；传输 compose / `.env` / nginx 配置 / 镜像（`docker save | ssh docker load` 管道直传）。
- `ssl_verify` 服务器端经 `docker exec + commit` 改为 True（本地保留 False 供代理调试）。**坑**：`docker commit` 须显式 `--change='CMD [...]'`，否则继承 `sleep` 命令。
- 6 容器全部 healthy，`/health` ok。
- **Bug 修复**：`/api/upload` 文件未注入 agent 上下文（同下午条目根因），服务器热补丁 + 本地代码同步。

## 2026-04-04 — GCP 服务器创建 + SSH 配置

- 选 GCP（Gemini API 同属 Google，走内网延迟低，未来可升 Vertex AI）。
- 实例：`csis-server`，us-central1-a，e2-standard-4（4 vCPU / 16 GB，实际 32 GB），Ubuntu 22.04，外网 IP `35.184.212.119`（注：当前 IP 已变更为 34.42.83.50）。
- SSH：Ed25519 密钥 `id_ed25519_csis`；项目专用账号 `csisaiproject2026`（有 sudo），删除自动创建的 `dru1889`。
- 注意事项：生产前 CORS 收窄、`ssl_verify=True`；Redis 6379 仅 Docker 内网。

---

# 阶段一 — POC 基础搭建（2026-03）

## 2026-03-27 — Docker 部署 + 全栈验证

- Dockerfile：Python 3.12、R 包补全、编译器 symlink；`docker-compose.yml`：nginx 入口、healthcheck、`HOST_*` 卷变量；新建 `.env.docker`。
- 测试：集成测试 11/11；Locust 压测（40 并发 2 分钟）2148 请求 0 失败；E2E 6/6；3 用户并发 session 完全隔离。
- 运维注意：`docker commit` 须指定 CMD；api-server 重建后 nginx 须 restart；`HOST_*` 变量须在项目根 `.env`。

## 2026-03-27 — 端到端集成测试（6 工具）

- 浏览器 UI 端到端测试 6 个工具全部通过：Network Analysis（R 崩溃修复验证）、CBC Preprocessor、CBC Main（修 CSV 路径）、Seasonal Water Yield、Crop Production Percentile / Regression（移除 `model_data_path` 暴露）。

## 2026-03-25 — 环境验证 + 依赖修复

- Claude Code 执行环境验证：conda `TeleCouplingAI`（Python 3.13.11）、13 模块 import OK、pytest 59/59、`/health` ok、前端 build + dev server 正常。
- 修复依赖：`aiofiles==3.13.3` → `>=23.0.0`、`aiohttp` → `aiohttp[speedups]>=3.9.0`。
- 环境配置说明：代码只认 `.env` 的 `REDIS_URL`（本地 `localhost` / Docker `redis`），无自动检测；`GOOGLE_API_KEY` 须填真实值。

## 2026-03-25 — 全面 Review 修复 11 个问题

- 严重：`agent.py` `_gemini_client` 改懒初始化、`tool_start` 事件 task_id 修正；`App.jsx` 接入 SSE 替换旧 Gemini 端点、默认模型 `gemini-2.5-flash`。
- 中等：6 张 Suggested Prompts 卡片、7 种消息 block 渲染、`session_manager` 懒初始化、`asyncio.get_running_loop()`、新增 `/api/render/zoom` 端点。
- 小：`streaming.js` 加 `model` 参数、6 个前端组件完整实现。

## 2026-03-25 — AI 后端从 Claude 切换为 Gemini

- `requirements.txt`：`anthropic` → `google-genai>=0.8.0`；`config.py`：`ANTHROPIC_API_KEY` → `GOOGLE_API_KEY`，默认 `gemini-2.5-flash`。
- `agent.py` 重写为 Gemini function calling；`main.py` 全新实现 SSE / upload / download / health / session 端点。

## 2026-03-16 — agent.py + Skills 两阶段加载架构

- 实现 `run_agent()` 主循环（初版 Anthropic SDK，后被 Gemini 替换）：两阶段 Skills 加载、Celery 派发、Redis pub/sub relay。
- **Skills 两阶段运行时加载**：每个 SKILL.md 分三段 —— `[DEV ONLY]` / `[PRE_EXECUTION]`（注入 system prompt）/ `[POST_EXECUTION]`（注入 tool_result 上下文）。
- 6 个 SKILL.md 重写为英文三段式，含上传文件感知规则。

## 2026-03-16 — 测试脚本修复 + 环境配置 + QGIS 渲染

- **mock 目标修复**：手动测试脚本 mock 了 `shared.utils.generate_output_dir`，但工具用 `from ... import` 方式导入致 mock 失效、文件写错目录 —— 改为 mock 各 tool 模块内的引用。新增 8 个独立测试脚本。
- 环境配置整合：`config.py` `env_file` 改绝对路径指向项目根 `.env`（唯一配置文件）。
- `model_data_path` 改为用户输入；作物名称动态加载 + 归一化（`get_supported_crops` / `_normalize` / `_rewrite_crop_csv`）。
- 新增 QGIS `zoom_render()`（params 写临时 JSON 解决 Windows 路径问题，底图三级 fallback）。
- `output_router` 预览图自动生成（后于 2026-04-29 改为禁用）。
