# AI_Telecoupling

**CSIS Ecosystem Intelligence Platform — Project Summary**

The CSIS Ecosystem Intelligence Platform is a full-stack AI-powered web application that enables researchers and analysts to run complex ecological models through natural language conversation. Instead of manually configuring and executing InVEST (Integrated Valuation of Ecosystem Services and Tradeoffs) tools, users simply describe what they want to analyze, and the system handles the rest.

**What it does.** The platform integrates six InVEST modeling tools — Network Analysis Grouping, Coastal Blue Carbon Preprocessor, Coastal Blue Carbon, Seasonal Water Yield, Crop Production Percentile, and Crop Production Regression — into a Gemini-style chat interface. Users interact in plain language; Claude (Sonnet 4.5) interprets the request, collects any missing parameters through conversation, triggers the appropriate model, and streams results back in real time. Spatial outputs are rendered as interactive map images via QGIS, tabular outputs appear as sortable inline tables, and all result files are available for download.

**Tech stack.** The frontend is built on React 18 + Vite + Tailwind CSS (already functional). The backend runs Python FastAPI with Celery task queues and Redis pub/sub for real-time SSE streaming, all inside the existing `TeleCouplingAI` conda environment which already has `natcap.invest 3.14.3` installed. Spatial rendering uses QGIS 3.40.14 via subprocess, and network analysis runs R + igraph. The entire project — source code, test data, and reference documentation — lives in a single directory: `telecouplingAI-project/`.

**Current status.** The frontend UI is complete and the FastAPI skeleton exists, currently wired to Gemini. The immediate next step is running Claude Code to generate the backend skeleton (Phase A), then systematically filling in each module (Phase B, 20 steps) starting with swapping Gemini for Claude and adding SSE streaming.

[0. Frontend](0%20Frontend%2032365d8db93680d98dccc251254a9f05.md)

[1. Coastal_Blue_Carbon_preprocessor](1%20Coastal_Blue_Carbon_preprocessor%2032365d8db93680af92a6d1ab8868d24e.md)

[2. Coastal_Blue_Carbon](2%20Coastal_Blue_Carbon%2032365d8db93680f6a090e21f4b31c323.md)

[3. Network_Analysis_Grouping](3%20Network_Analysis_Grouping%2032365d8db9368058bd3cf2905f49c41a.md)

[4. Seasonal_Water_Yield](4%20Seasonal_Water_Yield%2032365d8db93680c4b649f8a9a21371ae.md)

[5. Crop_Production_Percentile](5%20Crop_Production_Percentile%2032365d8db9368083a014efc0f21a1e0a.md)

[6. Crop_Production_Regression](6%20Crop_Production_Regression%2032365d8db9368068a7d1e5dbb4461b53.md)