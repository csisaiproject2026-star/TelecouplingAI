telecoupling-project/             # 项目根目录
├── .env                          # 【安全】存放所有密钥 (API_KEY, DB_URL等)
├── .gitignore                    # 【Git】忽略 __pycache__、.env、.db 等
├── docker-compose.yml            # 【编排】核心：一键启动全栈服务
│
├── frontend/                     # 前端模块
│   └── (目前建议直接使用 NextChat 官方 Docker 镜像，无需本地代码)
│
├── backend/                      # 【核心】FastAPI 后端
│   ├── Dockerfile                # 后端镜像构建说明
│   ├── requirements.txt          # 依赖清单 (LangGraph, FastAPI, etc.)
│   ├── main.py                   # 程序入口：路由分发、CORS 开启
│   ├── config.py                 # 配置中心：Pydantic 读取 .env 校验
│   │
│   ├── app/                      # 应用业务逻辑
│   │   ├── __init__.py
│   │   ├── api.py                # 具体的 API 接口逻辑 (v1/chat/...)
│   │   └── dependencies.py       # 注入项 (如 Auth 校验)
│   │
│   ├── agents/                   # 【大脑】LangGraph 工作流
│   │   ├── __init__.py
│   │   ├── graph.py              # 构建 Agent 状态机 (Reasoning Loop)
│   │   └── state.py              # 定义 Agent 内存状态 (TypedDict)
│   │
│   ├── tools/                    # 【外挂】能力扩展
│   │   ├── __init__.py
│   │   ├── mcp_client.py         # 重点：MCP Server 连接器逻辑
│   │   └── custom_tools.py       # 你自己编写的 Python 工具
│   │
│   └── database/                 # 【持久化】存储
│       ├── __init__.py
│       ├── session.py            # DB 连接池管理
│       └── checkpoint.py         # LangGraph 对话记录持久化逻辑
│
├── data/                         # 【挂载】Docker 磁盘映射 (持久化数据)
│   ├── db_files/                 # 存放 Sqlite 或 Postgres 数据文件
│   └── logs/                     # 存放运行日志
│
└── nginx/                        # 【网关】生产环境必备 (本地开发可选)
    ├── nginx.conf                # 负责 HTTPS 和 80 端口转发
    └── certs/                    # 存放 SSL 证书