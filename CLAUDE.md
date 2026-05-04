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

| 项目 | 值 |
|------|----|
| GCP 服务器 IP | **34.42.83.50**（唯一正确的 IP，不要用其他 IP） |
| 访问地址 | http://34.42.83.50/ |
| 服务器路径 | `~/csis-platform/` |
| Docker Dockerfile | `~/csis-platform/backend/Dockerfile`（build 必须在 backend/ 目录下执行） |

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

## 已实现工具（6 个）

| 工具 | Python 模块 | 状态 |
|------|-------------|------|
| Seasonal Water Yield | `natcap.invest.seasonal_water_yield` | ✅ |
| Coastal Blue Carbon Preprocessor | `natcap.invest.coastal_blue_carbon.preprocessor` | ✅ |
| Coastal Blue Carbon (Main) | `natcap.invest.coastal_blue_carbon.coastal_blue_carbon` | ✅ |
| Crop Production Percentile | `natcap.invest.crop_production_percentile` | ✅ |
| Crop Production Regression | `natcap.invest.crop_production_regression` | ✅ |
| Network Analysis | 自定义 | ✅ |

---

## 核心设计原则

- **TIF/SHP 文件只提供下载链接**，不自动生成预览。预览仅在用户明确请求时通过 `render_spatial_file` 工具触发
- 每个新 InVEST 工具需要：Celery 任务文件、docker-compose worker、output_router 规则、SKILL.md
- 测试用数据在 `datainput_for_demo/` 目录下
