# CSIS Platform — Project Instructions for Codex

## 项目持久记忆

- 开始仓库审计、服务器部署或 workflow 复测前，先完整阅读根目录 `PROJECT_MEMORY.md`。
- 不要重复已经记录且仍然有效的全目录扫描、服务器结构调查或完整 workflow 复测。
- 当分支、服务器镜像、部署方法、验证结果或重要设计决策发生变化时，更新 `PROJECT_MEMORY.md`。
- `PROJECT_MEMORY.md` 记录稳定结论；逐次工作流水仍记录在 `DEV_LOG.md`。

## DEV_LOG 记录规则

**每次对话结束前，必须将本次工作追加记录到 `DEV_LOG.md`**，格式如下：

```
## YYYY-MM-DD — [简短标题]
### 完成内容
- ...
### 关键变更文件
- ...
### 测试状态
- ...
```

不需要用户提醒，完成工作后主动追加。

---

## 服务器信息

平台现有三台服务器（两台 GCP、一台 MSU，均非 git 仓库）：

| 项目 | GCP 1（现有验证环境） | GCP 2（新增） | MSU（生产） |
|------|----------------------|---------------|------------|
| 主机名 | `csis-server` | `csis-server-2` | MSU host |
| IP | **34.42.83.50** | **34.136.64.176** | **35.9.219.33** |
| SSH | `ssh csis-gcp`（user `csisaiproject2026`） | `ssh -i ~/.ssh/id_ed25519_csis csisaiproject2026@34.136.64.176` | `ssh csis-msu`（user `jianan2`，需校园网/VPN） |
| 访问地址 | http://34.42.83.50/ | https://34.136.64.176/ | http://35.9.219.33/（校园网）<br>https://ai.telecoupling.msu.edu/（公网，经 MSU WAF） |
| 服务器路径 | `~/csis-platform/` | `~/csis-platform/telecouplingAI-project/` | `~/csis-platform/telecouplingAI-project/` |

- **两台 GCP 都有效**：GCP 1 为 `34.42.83.50`，GCP 2 为 `34.136.64.176`，部署或排查时必须明确目标。
- GCP 2 于 2026-07-31 验证 SSH、HTTP/HTTPS、`/health` 和 40 个容器正常；在完成源码/环境/数据漂移审计前，不要假定它与 GCP 1 完全一致。
- **MSU 公网访问经 MSU 的 WAF 转发**：WAF 终结公网 TLS → 连源站 `:443`。源站 nginx 已配 `listen 443 ssl`（自签名证书在 `nginx/certs/`，端口 80/443 均开）。SSH(22) 不走 WAF，管理服务器仍需 VPN。
- Docker Dockerfile：`~/csis-platform/backend/Dockerfile`（build 必须在 backend/ 目录下执行）。

---

## Git 分支策略

| 分支 | 用途 |
|------|------|
| `production` | GitHub 默认和唯一长期分支；代表已确认的权威源码 |
| `feature/<topic>` | 从 `production` 创建的短期开发分支，合并后删除 |

- 不要直接在 `production` 开发；每项工作使用独立 `feature/<topic>` 分支
- 候选提交先部署到 GCP 验证，通过后合并回 `production`
- 从同一提交构建不可变镜像，再将同一镜像提升到 MSU
- GCP 是测试环境，不对应长期 Git 分支

---

## 部署工作流

**服务器不是 git 仓库**，不能用 `git pull`。正确方式：

```bash
# 1. 本地打包传输（必须排除 env 文件——每台服务器各有自己的 .env.docker，不能被本地覆盖）
tar czf - --exclude='telecouplingAI-project/.env.docker' --exclude='telecouplingAI-project/.env' \
    telecouplingAI-project/ | ssh user@34.42.83.50 "cd ~/csis-platform && tar xzf -"

# 2. 服务器上重建镜像（在 backend/ 目录）
cd ~/csis-platform/backend
docker build -t csis-backend:latest .

# 3. 重启容器
cd ~/csis-platform
docker compose up -d --force-recreate
```

> ⚠️ **env 文件是 per-server 配置，永不随 tar 部署**（否则会重演 2026-06-10 的下载全失效：本地 `localhost:8001` 覆盖掉 GCP 修好的下载地址）。
> 每台服务器的 `.env.docker` 在服务器本地维护；仓库里 `.env.docker.gcp` / `.env.docker.msu` 只是模板，首次部署时在对应服务器上 `cp .env.docker.<server> .env.docker` 并填入真实 `GOOGLE_API_KEY`。
> 换 IP / 域名时只改一个变量 `SERVER_BASE_URL`，`FILE_SERVER_URL` 由 `backend/config.py` 自动派生为 `<base>/download/`。

---

## 项目结构关键路径

```
fulldev/
├── telecouplingAI-project/
│   ├── backend/
│   │   ├── main.py               # FastAPI 主入口
│   │   ├── tools/                # 每个 InVEST 工具的 Celery 任务
│   │   ├── renderers/
│   │   │   ├── output_router.py  # 输出文件分类（qgis/csv/download）
│   │   │   └── csv_analyzer.py   # CSV 分析与图表建议
│   │   ├── shared/utils.py       # 公共工具函数
│   │   └── tests/                # pytest 测试
│   ├── docker-compose.yml        # 所有容器定义
│   └── .Codex/skills/           # 每个工具的 AI 调用指南 SKILL.md
├── DEV_LOG.md                    # 开发日志（每次必须追加）
└── INVEST_MODELS_REFERENCE.md    # InVEST 所有模型参考文档
```

---

## 已实现工具（41 个活跃工具）

平台目前有 **41 个活跃工具**（26 个 InVEST 模型 + 15 个自定义/Telecoupling 工具）。
工具数量已稳定，逐条列表容易过时——**权威清单见这三处，不要在本文件维护明细：**

- `backend/shared/tool_file_specs.py` — 41 个工具的输入文件参数与类型定义（最准的"活跃工具"集合）
- `.Codex/skills/run-*` — 每个工具一个 SKILL.md（AI 调用指南）
- `INVEST_MODELS_REFERENCE.md` — InVEST 模型参考文档

> 历史：POC 阶段只有 6 个工具（SWY / CBC 预处理 / CBC 主模型 / Crop Percentile / Crop Regression / Network Analysis）；
> 后续在 `feature/invest-expansion` 分支扩展到 41 个。
> 未纳入 file-spec 校验的两个例外：`render_spatial_file` / `read_file_content`（处理已生成的输出文件）；
> Recreation 工具已禁用。

---

## 核心设计原则

- **TIF/SHP 文件只提供下载链接**，不自动生成预览。预览仅在用户明确请求时通过 `render_spatial_file` 工具触发
- 每个新 InVEST 工具需要：Celery 任务文件、docker-compose worker、output_router 规则、SKILL.md
- 测试用数据在 `datainput_for_demo/` 目录下
