telecoupling-project/             # Project root
├── .env                          # [Security] Stores all secrets (API_KEY, DB_URL, etc.)
├── .gitignore                    # [Git] Ignores __pycache__, .env, .db, etc.
├── docker-compose.yml            # [Orchestration] Core: launch the full stack in one command
│
├── frontend/                     # Frontend module
│   └── (For now, use the official NextChat Docker image directly — no local code needed)
│
├── backend/                      # [Core] FastAPI backend
│   ├── Dockerfile                # Backend image build instructions
│   ├── requirements.txt          # Dependency list (LangGraph, FastAPI, etc.)
│   ├── main.py                   # Entry point: route dispatch, CORS enabled
│   ├── config.py                 # Config hub: Pydantic reads & validates .env
│   │
│   ├── app/                      # Application business logic
│   │   ├── __init__.py
│   │   ├── api.py                # Concrete API endpoint logic (v1/chat/...)
│   │   └── dependencies.py       # Injected dependencies (e.g., auth checks)
│   │
│   ├── agents/                   # [Brain] LangGraph workflow
│   │   ├── __init__.py
│   │   ├── graph.py              # Build the agent state machine (reasoning loop)
│   │   └── state.py              # Define agent in-memory state (TypedDict)
│   │
│   ├── tools/                    # [Add-ons] Capability extensions
│   │   ├── __init__.py
│   │   ├── mcp_client.py         # Key: MCP Server connector logic
│   │   └── custom_tools.py       # Your own custom Python tools
│   │
│   └── database/                 # [Persistence] Storage
│       ├── __init__.py
│       ├── session.py            # DB connection pool management
│       └── checkpoint.py         # LangGraph conversation checkpoint persistence
│
├── data/                         # [Mount] Docker volume mapping (persistent data)
│   ├── db_files/                 # Stores SQLite or Postgres data files
│   └── logs/                     # Stores runtime logs
│
└── nginx/                        # [Gateway] Required in production (optional for local dev)
    ├── nginx.conf                # Handles HTTPS and port-80 forwarding
    └── certs/                    # Stores SSL certificates
