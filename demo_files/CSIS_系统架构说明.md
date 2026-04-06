# CSIS Telecoupling AI Platform — 系统架构与代码说明

> 文档生成日期：2026-04-05  
> 服务器：GCP csis-server（us-central1-a）  
> 外网IP：35.184.212.119  
> SSH 用户：csisaiproject2026  

---

## 一、GCP 服务器文件结构

```
GCP 服务器 (Ubuntu 22.04)
│
├── /home/csisaiproject2026/
│   └── csis-platform/                  ← 项目根目录（docker compose 在这里运行）
│       ├── docker-compose.yml           ← 定义所有 Docker 容器和服务
│       ├── .env                         ← 宿主机路径变量（HOST_* 路径）
│       ├── .env.docker                  ← 容器内部环境变量（API Key、Redis URL 等）
│       ├── nginx/
│       │   ├── nginx.conf               ← 主反向代理配置（端口 80）
│       │   └── file-server.conf         ← 静态文件服务配置（端口 8001）
│       └── datainput_for_demo/          ← 演示用输入数据（只读，173MB）
│           ├── network_analysis/        ← 工具1 测试数据
│           ├── cbc_preprocessor/        ← 工具2 测试数据
│           ├── coastal_blue_carbon/     ← 工具3 测试数据
│           ├── seasonal_water_yield/    ← 工具4 测试数据
│           ├── crop_percentile/         ← 工具5 测试数据
│           └── crop_regression/         ← 工具6 测试数据
│
├── /data/                               ← 持久化数据目录
│   ├── outputs/                         ← 所有工具运行结果（按 session_id 分目录）
│   │   └── csis_{uuid}/
│   │       └── {时间戳}_{工具名}/       ← 每次运行一个子目录
│   ├── uploads/                         ← 用户上传的输入文件（按 session_id 分目录）
│   │   └── csis_{uuid}/
│   └── model_data/                      ← InVEST 参考数据（只读，约 10GB）
│       ├── climate_percentile_yield_tables/  ← 172种作物气候产量数据
│       └── ...
│
└── /var/lib/docker/                     ← Docker 镜像存储（系统管理，勿动）
```

---

## 二、Docker 容器架构

系统由 **12 个 Docker 容器**组成，通过 `docker-compose.yml` 统一编排：

```
外部网络（Internet）
        │
        ▼ 端口 80（HTTP）
┌───────────────┐
│  tele-nginx   │  ← 反向代理（nginx:alpine）
│  (nginx.conf) │    路由所有流量到内部服务
└───────┬───────┘
        │
        ├─── / (前端页面) ──────────────► tele-frontend:80
        │                                  React SPA (csic_frontend 镜像)
        │
        ├─── /api/chat ─────────────────► tele-backend:8000
        ├─── /api/upload ───────────────► tele-backend:8000
        ├─── /api/ (其他) ──────────────► tele-backend:8000
        └─── /download/ ────────────────► tele-backend:8000
                                          FastAPI (csic_backend 镜像)
                                                  │
                                                  │ 派发 Celery 任务
                                                  ▼
                                        ┌─────────────────┐
                                        │   tele-redis    │  ← 消息队列 + 进度发布
                                        │  (redis:alpine) │    redis://redis:6379/0
                                        └────────┬────────┘
                                                 │
                      ┌──────────────────────────┼──────────────────────────┐
                      │ 按工具路由到专属队列      │                          │
                      ▼                          ▼                          ▼
            ┌─────────────────┐       ┌──────────────────┐      ┌──────────────────┐
            │ celery-net      │       │ celery-cbc-pre   │      │ celery-cbc-main  │
            │ q_net, 并发=1   │       │ q_cbc_pre, 并发=1│      │ q_cbc_main,并发=1│
            │ 内存上限: 2GB   │       │ 内存上限: 2GB    │      │ 内存上限: 3GB    │
            └─────────────────┘       └──────────────────┘      └──────────────────┘
            ┌─────────────────┐       ┌──────────────────┐      ┌──────────────────┐
            │ celery-swy      │       │ celery-crop-pct  │      │ celery-crop-reg  │
            │ q_swy, 并发=1   │       │ q_crop_pct,并发=1│      │ q_crop_reg,并发=1│
            │ 内存上限: 4GB   │       │ 内存上限: 2GB    │      │ 内存上限: 2GB    │
            └─────────────────┘       └──────────────────┘      └──────────────────┘
            ┌─────────────────┐
            │ celery-render   │  ← QGIS 空间文件渲染
            │ q_render,并发=2 │
            │ 内存上限: 2GB   │
            └─────────────────┘

端口 8001（文件下载）
┌───────────────┐
│ tele-filesvr  │  ← 静态文件服务（nginx:alpine）
│               │    直接访问 /data/outputs 目录
└───────────────┘
```

---

## 三、后端代码结构（csic_backend 镜像内，位于 /app/）

```
/app/
├── main.py                   ← FastAPI 入口，定义所有 HTTP 接口
├── agent.py                  ← Gemini AI 智能体核心（函数调用循环）
├── config.py                 ← 从 .env 加载配置
│
├── tools/                    ← 6 个 InVEST 工具实现
│   ├── network_analysis.py   ← 工具1：网络社区分析
│   ├── cbc_preprocessor.py   ← 工具2：蓝碳预处理
│   ├── cbc_main.py           ← 工具3：蓝碳主模型
│   ├── seasonal_water_yield.py ← 工具4：季节性水量
│   ├── crop_percentile.py    ← 工具5：作物产量（百分位）
│   └── crop_regression.py    ← 工具6：作物产量（回归）
│
├── renderers/                ← 输出文件处理
│   ├── output_router.py      ← 根据文件类型路由渲染方式
│   ├── qgis_renderer.py      ← QGIS 无头渲染 → PNG 预览图
│   └── csv_analyzer.py       ← CSV 数据分析与表格提取
│
├── workers/
│   └── task_queue.py         ← Celery 任务定义，连接 Redis broker
│
├── shared/
│   ├── session_manager.py    ← Redis 会话管理（文件路径、历史记录）
│   └── utils.py              ← 文件扫描、分类、路径处理等工具函数
│
└── r_scripts/                ← R 脚本（工具1 网络分析专用）
    └── network_community.R   ← igraph 社区发现算法
```

---

## 四、前端代码结构（csic_frontend 镜像内，构建产物在 /usr/share/nginx/html/）

```
前端源码（开发时位于 telecouplingAI-project/frontend/src/）

src/
├── App.jsx                   ← 主界面：聊天框、侧边栏、消息流
├── lib/
│   ├── streaming.js          ← SSE 客户端（监听 /api/chat 流式响应）
│   └── session.js            ← 生成/获取 Session ID（持久化到 sessionStorage）
│
└── components/
    ├── ToolStatusCard.jsx     ← 工具运行进度卡片（⚙️ 运行中 / ✅ 完成）
    ├── ResultFiles.jsx        ← 输出文件下载列表
    ├── ImageRenderer.jsx      ← 空间图层预览（PNG 图片 + 支持缩放）
    ├── CsvRenderer.jsx        ← CSV 表格内联展示
    ├── ChartRenderer.jsx      ← 图表展示（Recharts）
    └── WarningCard.jsx        ← 警告提示（如"请先编辑转换表再运行工具3"）
```

---

## 五、API 接口说明

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| POST | `/api/chat` | **主要接口**：AI 对话 + 工具调用 | 支持流式 SSE，Header 需带 `X-Session-ID` |
| POST | `/api/upload` | 独立文件上传 | 上传文件到 session，之后聊天可引用 |
| POST | `/api/render/zoom` | 空间文件缩放重渲染 | QGIS 重新生成指定范围的 PNG 预览 |
| GET  | `/download/{session_id}/{path}` | 下载输出文件 | 返回文件附件 |
| DELETE | `/api/sessions/{session_id}` | 删除会话 | 清理 Redis + 输出文件 |
| GET  | `/health` | 健康检查 | 返回 `{"status":"ok"}` |

---

## 六、完整请求处理流程（SSE 流程）

```
用户在前端输入消息 + 上传文件
        │
        ▼
前端 POST /api/chat (multipart/form-data)
  - message: 用户文本
  - files: 附带文件（可选）
  - Header: X-Session-ID: csis_{uuid}
        │
        ▼
nginx 接收，转发到 tele-backend:8000
  - SSE 接口：关闭缓冲，超时 1800s
        │
        ▼
FastAPI main.py
  1. 保存上传文件到 /data/uploads/{session_id}/
  2. 从 Redis 读取本 session 历史上传文件（合并，去重）
  3. 创建 asyncio 队列，启动 agent 后台任务
  4. 返回 StreamingResponse (text/event-stream)
        │
        ▼
agent.py — Gemini 函数调用循环
  第1步：组装系统指令（含工具知识 PRE_EXECUTION）
  第2步：调用 Gemini API（gemini-2.5-flash）
  第3步：如果 Gemini 决定调用工具：
    - 向前端推送 tool_start 事件
    - 通过 apply_async() 派发 Celery 任务到专属队列
    - 订阅 Redis pub/sub 频道：progress:{session_id}:{task_id}
    - 实时转发进度事件到前端（tool_progress）
    - 收到 done 事件后，组装工具结果
    - 注入 POST_EXECUTION 上下文，继续 Gemini 对话
  第4步：Gemini 生成最终文字回复
  第5步：推送 text_chunk 事件流到前端
        │
        ▼
前端 SSE 事件处理器
  - text_chunk → 流式追加 AI 回复文字
  - tool_start → 显示 ToolStatusCard（进度条）
  - tool_progress → 更新进度百分比
  - tool_result → 渲染下载文件 + 图片预览 + CSV 表格
  - warning → 显示 WarningCard 警告
  - error → 显示错误信息
```

---

## 七、6 个 InVEST 工具详细说明

### 工具 1：Network Analysis Grouping（网络社区分析）

| 项目 | 说明 |
|------|------|
| **功能** | 对流向/贸易网络进行社区发现，识别节点分组 |
| **算法** | R + igraph（walktrap 或 spin_glass 社区检测） |
| **必需输入** | 节点 CSV、链接 CSV、地理 Shapefile、聚类算法选择 |
| **输出文件** | 聚类后的 Shapefile（含分组属性）、网络统计 CSV、可视化 PDF |
| **Celery 队列** | q_net，并发=1，内存上限 2GB |

---

### 工具 2：Coastal Blue Carbon Preprocessor（蓝碳预处理）

| 项目 | 说明 |
|------|------|
| **功能** | 分析不同时期土地覆盖变化，生成碳变化转换表 |
| **必需输入** | 土地覆盖快照 CSV（含多个年份的 LULC TIF 路径）、LULC 查找表 |
| **输出文件** | 土地覆盖转换 CSV（**需要用户手动编辑后才能用于工具3**）、对齐后的 LULC TIF |
| **⚠️ 注意** | 输出的 transitions_*.csv 需要用户填写碳变化数值，再传给工具3 |
| **Celery 队列** | q_cbc_pre，并发=1，内存上限 2GB |

---

### 工具 3：Coastal Blue Carbon（蓝碳主模型）

| 项目 | 说明 |
|------|------|
| **功能** | 计算蓝碳生态系统的碳储量、固碳量、排放量，可选经济估值 |
| **必需输入** | 土地覆盖快照 CSV、**已编辑的**转换表 CSV、生物物理参数表 |
| **可选输入** | 经济参数（贴现率、碳价格）→ 输出净现值 NPV |
| **输出文件** | 碳储量/碳积累/碳排放/固碳量 TIF、汇总报告、可选 NPV TIF |
| **Celery 队列** | q_cbc_main，并发=1，内存上限 3GB |

---

### 工具 4：Seasonal Water Yield（季节性水量）

| 项目 | 说明 |
|------|------|
| **功能** | 模拟流域快速径流、基流、局部补给量的月度分布 |
| **必需输入** | 研究区 Shapefile、LULC 栅格、DEM、土壤组、生物物理表、12个月降水+蒸散 TIF、降雨事件表 |
| **自动处理** | 月度文件自动重命名为 InVEST 格式（precip_m1.tif～m12，et0_m1.tif～m12） |
| **输出文件** | QF（快速径流）/B（基流）/L（局部补给）TIF、聚合结果 Shapefile |
| **Celery 队列** | q_swy，并发=1，内存上限 4GB（最耗内存的工具） |

---

### 工具 5：Crop Production Percentile（作物产量-百分位法）

| 项目 | 说明 |
|------|------|
| **功能** | 基于气候百分位估算指定区域的作物产量 |
| **支持作物** | 172 种（动态从 /data/model_data/climate_percentile_yield_tables/ 读取） |
| **必需输入** | 土地覆盖栅格、作物-LULC 映射 CSV |
| **可选输入** | 聚合多边形（按行政区汇总产量） |
| **输出文件** | 每种作物的产量 TIF、汇总结果 CSV 表格 |
| **Celery 队列** | q_crop_pct，并发=1，内存上限 2GB |

---

### 工具 6：Crop Production Regression（作物产量-回归法）

| 项目 | 说明 |
|------|------|
| **功能** | 基于施肥量（N/P/K）通过回归模型估算作物产量 |
| **支持作物** | 10 种：大麦、玉米、油棕、马铃薯、水稻、大豆、甜菜、甘蔗、向日葵、小麦 |
| **必需输入** | 土地覆盖栅格、作物-LULC 映射 CSV、施肥量表（N/P/K，单位 kg/ha） |
| **输出文件** | 每种作物的产量 TIF、聚合结果 CSV |
| **Celery 队列** | q_crop_reg，并发=1，内存上限 2GB |

---

## 八、数据目录说明（/data/）

| 目录 | 用途 | 生命周期 |
|------|------|---------|
| `/data/outputs/{session_id}/` | 工具运行产生的所有输出文件 | 24小时 TTL（Redis 会话到期后不自动删除磁盘文件，需手动清理） |
| `/data/uploads/{session_id}/` | 用户上传的输入文件 | 同上 |
| `/data/model_data/` | InVEST 参考数据（只读挂载） | 永久保留 |
| `~/csis-platform/datainput_for_demo/` | 演示输入数据（只读挂载） | 永久保留 |

---

## 九、关键配置参数（.env.docker）

| 变量 | 值 | 说明 |
|------|-----|------|
| `GOOGLE_API_KEY` | sk-... | Gemini API 密钥 |
| `DEFAULT_MODEL` | gemini-2.5-flash | 默认 AI 模型 |
| `REDIS_URL` | redis://redis:6379/0 | Redis 连接（Docker 内网） |
| `SHARED_DIR` | /data/outputs | 输出文件根目录（容器内路径） |
| `UPLOADS_DIR` | /data/uploads | 上传文件根目录（容器内路径） |
| `MODEL_DATA_PATH` | /data/model_data | InVEST 参考数据（容器内路径） |
| `FILE_SERVER_URL` | http://file-server/download/ | 文件下载服务 URL |
| `SESSION_TTL_HOURS` | 24 | 会话过期时间（小时） |
| `MAX_SESSIONS` | 50 | 最大并发会话数 |

---

## 十、并发架构设计说明

**问题背景**：InVEST 工具底层使用 GDAL，多个进程同时运行同一工具时会产生临时文件冲突，导致计算错误或崩溃。

**解决方案（P1 工具级队列隔离）**：
- 每个 InVEST 工具分配一个独立的 Celery 队列
- 每个队列对应一个专属 Worker，`concurrency=1`
- 同一工具的多个请求在 Redis 队列中排队，串行执行
- 不同工具之间完全并行（6 个工具可同时运行）

**测试验证结果**：
- 5 用户并发：100% 通过率
- 50 用户压测：98% 通过率（2% 为 InVEST 内部偶发错误）
- 系统吞吐量：37.7 次工具运行/分钟
- 服务器资源：CPU 峰值 54.8%，内存峰值 4GB / 32GB（资源充裕）
