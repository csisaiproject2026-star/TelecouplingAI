# CSIS Platform — Project Instructions for Claude

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

平台部署在两台服务器上（结构 1:1 一致，均非 git 仓库）：

| 项目 | GCP（源/主） | MSU（新服务器） |
|------|-------------|----------------|
| IP | **34.42.83.50** | **35.9.219.33** |
| SSH | `ssh csis-gcp`（user `csisaiproject2026`） | `ssh csis-msu`（user `jianan2`，需校园网/VPN） |
| 访问地址 | http://34.42.83.50/ | http://35.9.219.33/（校园网）<br>https://ai.telecoupling.msu.edu/（公网，经 MSU WAF） |
| 服务器路径 | `~/csis-platform/` | `~/csis-platform/telecouplingAI-project/` |

- **GCP IP 唯一正确就是 34.42.83.50，不要用其他 IP。**
- **MSU 公网访问经 MSU 的 WAF 转发**：WAF 终结公网 TLS → 连源站 `:443`。源站 nginx 已配 `listen 443 ssl`（自签名证书在 `nginx/certs/`，端口 80/443 均开）。SSH(22) 不走 WAF，管理服务器仍需 VPN。
- Docker Dockerfile：`~/csis-platform/backend/Dockerfile`（build 必须在 backend/ 目录下执行）。

---

## Git 分支策略

| 分支 | 用途 |
|------|------|
| `master` | POC 保护分支，保持稳定，不直接在此开发新功能 |
| `feature/invest-expansion` | InVEST 新工具扩展开发分支（当前主力分支） |

- 新功能统一在 feature 分支开发，本地调试通过后再推 GCP
- 稳定后合并回 master

---

## 部署工作流

**服务器不是 git 仓库**，不能用 `git pull`。正确方式：

```bash
# 1. 本地打包传输
tar czf - telecouplingAI-project/ | ssh user@34.42.83.50 "cd ~/csis-platform && tar xzf -"

# 2. 服务器上重建镜像（在 backend/ 目录）
cd ~/csis-platform/backend
docker build -t csis-backend:latest .

# 3. 重启容器
cd ~/csis-platform
docker compose up -d --force-recreate
```

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
│   └── .claude/skills/           # 每个工具的 AI 调用指南 SKILL.md
├── DEV_LOG.md                    # 开发日志（每次必须追加）
└── INVEST_MODELS_REFERENCE.md    # InVEST 所有模型参考文档
```

---

## 已实现工具（41 个活跃工具）

平台目前有 **41 个活跃工具**（26 个 InVEST 模型 + 15 个自定义/Telecoupling 工具）。
工具数量已稳定，逐条列表容易过时——**权威清单见这三处，不要在本文件维护明细：**

- `backend/shared/tool_file_specs.py` — 41 个工具的输入文件参数与类型定义（最准的"活跃工具"集合）
- `.claude/skills/run-*` — 每个工具一个 SKILL.md（AI 调用指南）
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
