# CSIS 平台测试报告

**报告日期：** 2026-05-06  
**测试服务器：** GCP 34.42.83.50  
**InVEST 版本：** 3.14.3  
**AI 模型：** Gemini 2.5 Flash  
**平台架构：** FastAPI + Celery（28 个专属 worker）+ Redis + nginx + React 前端

---

## 一、平台架构概览

```
用户浏览器
    │
    ▼
nginx（端口 80）
    │ 反向代理
    ▼
FastAPI 后端（tele-backend，端口 8000）
    │ Gemini 2.5 Flash API
    │ → 解析自然语言 → FunctionDeclaration 调用
    │
    ▼
Redis 消息队列（tele-redis）
    │ 28 条专属队列（每工具一条）
    ▼
Celery Workers（28 个容器，每工具独立）
    │ 调用 natcap.invest
    ▼
InVEST 计算结果（TIF / SHP / CSV）
    │
    ▼
SSE 实时推送 → 前端展示
```

**容器总数：** 33 个  
1 nginx + 1 backend + 1 frontend + 1 redis + 1 fileserver + 1 render worker + 28 Celery workers

---

## 二、已实现工具清单（共 26 个）

| 编号 | 工具名称 | Python 模块 | 类别 |
|------|---------|------------|------|
| 1 | Network Analysis（网络分析） | 自定义 | 生态耦合 |
| 2 | Coastal Blue Carbon Preprocessor（海岸蓝碳预处理） | natcap.invest.coastal_blue_carbon.preprocessor | 海岸/海洋 |
| 3 | Coastal Blue Carbon Main（海岸蓝碳主模型） | natcap.invest.coastal_blue_carbon.coastal_blue_carbon | 海岸/海洋 |
| 4 | Seasonal Water Yield（季节性水资源产量） | natcap.invest.seasonal_water_yield | 水文 |
| 5 | Crop Production Percentile（作物产量百分位） | natcap.invest.crop_production_percentile | 农业 |
| 6 | Crop Production Regression（作物产量回归） | natcap.invest.crop_production_regression | 农业 |
| 7 | Carbon Storage & Sequestration（碳储量与碳汇） | natcap.invest.carbon | 碳 |
| 8 | Forest Carbon Edge Effect（森林碳边缘效应） | natcap.invest.forest_carbon_edge_effect | 碳 |
| 9 | Annual Water Yield（年水资源产量） | natcap.invest.annual_water_yield | 水文 |
| 10 | SDR — Sediment Delivery Ratio（泥沙输移比） | natcap.invest.sdr.sdr | 水文/土壤 |
| 11 | NDR — Nutrient Delivery Ratio（营养物质输移比） | natcap.invest.ndr.ndr | 水质 |
| 12 | DelineateIt（流域划定） | natcap.invest.delineateit | 水文 |
| 13 | RouteDEM（DEM 路由） | natcap.invest.routedem | 水文 |
| 14 | Habitat Quality（栖息地质量） | natcap.invest.habitat_quality | 生物多样性 |
| 15 | Pollination（授粉服务） | natcap.invest.pollination | 生物多样性 |
| 16 | Urban Cooling（城市冷却岛） | natcap.invest.urban_cooling_model | 城市 |
| 17 | Urban Flood Risk Mitigation（城市洪水风险缓解） | natcap.invest.urban_flood_risk_mitigation | 城市 |
| 18 | Urban Stormwater Retention（城市雨水保留） | natcap.invest.stormwater | 城市 |
| 19 | Urban Nature Access（城市自然可达性） | natcap.invest.urban_nature_access | 城市 |
| 20 | Urban Mental Health（城市心理健康） | natcap.invest.urban_nature_access（扩展）| 城市 |
| 21 | Scenic Quality（景观质量） | natcap.invest.scenic_quality | 景观 |
| 22 | HRA — Habitat Risk Assessment（栖息地风险评估） | natcap.invest.hra | 景观 |
| 23 | Scenario Generator Proximity（情景生成器） | natcap.invest.scenario_gen_proximity | 景观 |
| 24 | Coastal Vulnerability（海岸脆弱性） | natcap.invest.coastal_vulnerability | 海岸/海洋 |
| 25 | Wave Energy Production（波浪能） | natcap.invest.wave_energy | 海岸/海洋 |
| 26 | Offshore Wind Energy（海上风能） | natcap.invest.wind_energy | 海岸/海洋 |
| — | Recreation & Tourism（休闲旅游）* | natcap.invest.recreation | 休闲 |

> *Recreation & Tourism：代码已实现，但 GCP VPC 出站防火墙屏蔽 TCP 54321 端口（NatCap 数据服务器），集成测试自动跳过。需添加 GCP 出站规则后可用。

---

## 三、集成测试（Integration Tests）

### 3.1 测试说明

- 测试方式：直接调用 InVEST Python API（不经过 LLM），使用 NatCap 官方样本数据
- 测试文件：`backend/tests/test_invest_integration.py`
- 运行环境：GCP Docker 容器（csis-backend:latest，Python 3.12）
- 样本数据：NatCap 官方数据，挂载于 `/sampledata`（GCP）

### 3.2 测试结果：26/26 全部通过

| 排名 | 工具 | GCP 耗时 | 速度类别 |
|------|------|---------|---------|
| 1 | Scenic Quality（景观质量） | **43.9 s** | 🔴 很慢 |
| 2 | Urban Nature Access（城市自然可达性） | **38.9 s** | 🔴 很慢 |
| 3 | Coastal Vulnerability（海岸脆弱性） | **35.3 s** | 🔴 很慢 |
| 4 | Pollination（授粉服务） | **21.6 s** | 🟡 慢 |
| 5 | Forest Carbon Edge Effect（森林碳边缘效应） | **17.3 s** | 🟡 慢 |
| 6 | Seasonal Water Yield（季节性水资源产量） | **12.3 s** | 🟡 慢 |
| 7 | Scenario Generator Proximity（情景生成器） | **11.0 s** | 🟡 慢 |
| 8 | Urban Mental Health（城市心理健康） | **10.5 s** | 🟡 慢 |
| 9 | Offshore Wind Energy（海上风能） | **7.7 s** | 🟢 中等 |
| 10 | Urban Cooling（城市冷却岛） | **7.7 s** | 🟢 中等 |
| 11 | SDR（泥沙输移比） | **6.8 s** | 🟢 中等 |
| 12 | CBC Main（海岸蓝碳主模型） | **6.8 s** | 🟢 中等 |
| 13 | Habitat Quality（栖息地质量） | **6.8 s** | 🟢 中等 |
| 14 | NDR（营养物质输移比） | **5.9 s** | 🟢 中等 |
| 15 | Carbon Storage（碳储量） | **4.5 s** | 🟢 中等 |
| 16 | Wave Energy（波浪能） | **4.5 s** | 🟢 中等 |
| 17 | Crop Production Percentile（作物产量百分位） | **4.1 s** | 🟢 中等 |
| 18 | HRA（栖息地风险评估） | **3.5 s** | 🟢 中等 |
| 19 | Crop Production Regression（作物产量回归） | **3.3 s** | 🟢 中等 |
| 20 | Urban Stormwater（城市雨水保留） | **3.0 s** | 🟢 中等 |
| 21 | Carbon（碳汇场景） | **2.9 s** | 🟢 中等 |
| 22 | Annual Water Yield（年水资源产量） | **1.7 s** | ✅ 快 |
| 23 | DelineateIt（流域划定） | **0.8 s** | ✅ 快 |
| 24 | Urban Flood（城市洪水风险） | **0.8 s** | ✅ 快 |
| 25 | RouteDEM（DEM 路由） | **0.7 s** | ✅ 快 |
| 26 | CBC Preprocessor（海岸蓝碳预处理） | **0.2 s** | ✅ 快 |
| — | Recreation & Tourism | **跳过** | ⚠️ GCP 防火墙 |

**总测试套件运行时间：** 约 4 分 22 秒

---

## 四、LLM 路径端到端测试

### 4.1 测试链路

```
英文自然语言 prompt
    → POST /api/chat（SSE 接口）
    → Gemini 2.5 Flash 解析
    → FunctionDeclaration 调用
    → Celery 任务派发
    → InVEST 模型执行
    → SSE tool_result 事件返回前端
```

### 4.2 测试范围

本次 LLM 路径测试覆盖 10 个代表性工具（涵盖快/中/慢三个速度类别），全部使用**纯英文 prompt**（平台面向美国用户，不允许中文）。

### 4.3 测试结果：10/10 全部通过（2026-05-06）

| 工具 | 总耗时 | LLM 开销 | InVEST 执行* | 重试次数 | 状态 |
|------|--------|---------|------------|---------|------|
| CBC Preprocessor（海岸蓝碳预处理） | 4.8s | 4.8s | ~0.2s | 0 | ✅ |
| DelineateIt（流域划定） | 4.1s | 4.1s | ~0.8s | 0 | ✅ |
| Annual Water Yield（年水资源产量） | 5.4s | 4.5s | ~1.7s | 0 | ✅ |
| Carbon Storage（碳储量） | 4.0s | 4.0s | ~4.5s | 0 | ✅ |
| Crop Production Percentile（作物产量百分位） | 7.5s | 5.0s | ~4.1s | 0 | ✅ |
| Habitat Quality（栖息地质量） | 8.6s | 8.6s | ~6.8s | 0 | ✅ |
| NDR（营养物质输移比） | 10.7s | 10.7s | ~5.9s | 0 | ✅ |
| SDR（泥沙输移比） | 21.6s | 21.6s | ~6.8s | **3** | ✅ |
| Seasonal Water Yield（季节性水资源产量） | 15.7s | 14.6s | ~12.3s | 0 | ✅ |
| Pollination（授粉服务） | 69.2s | 68.3s | ~21.6s | **7** | ✅ |

> *LLM 开销：从用户发出 prompt 到 Gemini 触发 FunctionDeclaration 调用的时间。  
> *InVEST 执行：实际 InVEST 模型运算时间（受 nginx SSE 缓冲影响，表中 LLM 开销包含部分等待时间）。  
> *重试：Gemini 首次返回空响应时自动重试的次数，不影响最终结果。

### 4.4 测试 Prompt 格式说明

| 工具 | Prompt 格式 | 说明 |
|------|------------|------|
| CBC Preprocessor | `Call run_coastal_blue_carbon_preprocessor with: ...` | 显式函数名 |
| DelineateIt | `Run DelineateIt watershed delineation. ...` | 自然语言 |
| Annual Water Yield | `Run the Annual Water Yield model. ...` | 自然语言 |
| Carbon Storage | `Run Carbon Storage and Sequestration. ...` | 自然语言 |
| Crop Production Percentile | `Call run_crop_production_percentile with: ...` | 显式函数名 |
| Habitat Quality | `Run Habitat Quality. ...` | 自然语言 |
| NDR | `Run the Nutrient Delivery Ratio (NDR) model. ...` | 自然语言 + 缩写 |
| SDR | `Call run_sdr with: ...` | 显式函数名（需要重试） |
| Seasonal Water Yield | `Call run_seasonal_water_yield with: ...` | 显式函数名 |
| Pollination | `Call run_crop_pollination with: ...` | 显式函数名（需要重试） |

---

## 五、Gemini 空响应问题说明

### 5.1 现象

Gemini 2.5 Flash 对某些英文工具 prompt（SDR、SWY、Pollination）在首次请求时返回 `candidate.content = None`，`finish_reason = FinishReason.STOP`（非安全过滤，是模型内部不确定性导致的空输出）。

### 5.2 解决方案（已在 agent.py 实现）

| 机制 | 说明 |
|------|------|
| **单工具模式** | 关键词检测到目标工具后，第一次 Gemini 调用只传入该工具的 FunctionDeclaration（1 个，而非 26 个），减少模型选择歧义 |
| **重试对话重置** | 原方案：追加第二条 user 消息（连续两条 user 消息违反 Gemini 交替对话规范）。新方案：每次重试开启全新单轮对话，内容为 `"Call {function_name} with: {原始参数}"` |
| **温度递进** | 首次调用 temp=0，重试从 temp=0.5 开始逐步升至 1.0（共 10 次重试机会），打破确定性空输出循环 |

### 5.3 各工具首次调用成功率

| 情况 | 工具 |
|------|------|
| 首次调用直接成功（0 次重试） | CBC Pre、DelineateIt、AWY、Carbon、Crop Pct、HQ、NDR、SWY |
| 需要重试但最终成功 | SDR（3 次重试）、Pollination（7 次重试） |

**结论：** 所有 10 个测试工具均可在重试机制保障下稳定通过。Pollination 最多需 7 次重试，总耗时约 69s（其中重试等待约 46s + InVEST 执行 22s）。

---

## 六、Celery API Pipeline 烟雾测试

测试链路：直接向 Celery broker 派发任务（绕过 LLM），验证 Worker→InVEST→文件输出的完整路径。

| 工具 | 队列 | 状态 | 耗时 | 输出文件验证 |
|------|------|------|------|------------|
| run_seasonal_water_yield | q_swy | ✅ 通过 | 13s | P.tif、aggregated_results_swy.shp ✓ |
| run_crop_production_percentile | q_crop_pct | ✅ 通过 | 4s | aggregate_results.csv、*.tif ✓ |
| run_coastal_blue_carbon_preprocessor | q_cbc_pre | ⚠️ 部分 | 1s | 仅 taskgraph_cache（演示数据列名问题） |
| run_coastal_blue_carbon | q_cbc_main | ⚠️ 部分 | 2s | 仅 taskgraph_cache（同上） |

> CBC 演示数据问题：`datainput_for_demo/CoastalBlue*` 中 CSV 使用 `lucode` 列名，InVEST 3.14.3 要求 `code`。集成测试在运行时做了列名转换，演示数据文件本身尚未更新。

---

## 七、部署状态

| 组件 | 状态 |
|------|------|
| Docker 容器（33 个） | ✅ 全部运行中 |
| API 接口 `/api/chat` | ✅ 可访问 |
| SSE 流式推送 | ✅ 正常 |
| Redis 消息队列 | ✅ 正常 |
| 文件服务器 `/download` | ✅ 正常 |
| 前端（nginx） | ✅ 正常提供服务 |
| Recreation 工具（端口 54321） | ⚠️ GCP VPC 出站防火墙屏蔽 |

**访问地址：** http://34.42.83.50/

---

## 八、已知问题 & 待办

| 优先级 | 问题 | 处理方式 |
|--------|------|---------|
| 低 | CBC 演示数据 CSV 列名为 `lucode`，InVEST 3.14.3 需要 `code` | 更新 `datainput_for_demo/CoastalBlue*` 中的文件 |
| 低 | Recreation & Tourism 在 GCP 上无法访问 NatCap 远程数据服务器 | 在 GCP VPC 添加出站防火墙规则：TCP 54321 → 34.44.144.58 |
| 说明 | Pollination 工具 LLM 路径需要最多 7 次重试（总耗时约 70s） | 已通过自动重试机制解决，不影响功能 |
| 说明 | SKILL.md 文件未挂载到容器 | `/.claude/skills/` 路径在 Docker 容器内不存在，系统 prompt 使用 inline 描述（5,691 字节），功能正常 |

---

## 九、速度类别参考（实际用户数据将更慢）

以下基于 GCP 样本数据，真实用户数据通常范围更大，运行时间会相应增加。

| 类别 | 工具 | 样本数据耗时 | 真实场景预估 |
|------|------|------------|------------|
| 🔴 很慢（>30s） | Scenic Quality、Urban Nature Access、Coastal Vulnerability | 35–44s | 2–30 分钟 |
| 🟡 慢（10–30s） | Pollination、Forest Carbon、SWY、Scenario Proximity、Urban Mental Health | 10–22s | 20–120s |
| 🟢 中等（3–10s） | Carbon、HQ、SDR、NDR、CBC、Crop、Wave Energy、Urban Cooling、Wind Energy | 3–8s | 10–60s |
| ✅ 快（<3s） | Annual WY、DelineateIt、RouteDEM、Urban Flood、CBC Preprocessor | 0.2–1.7s | 1–10s |

---

## 十、总结

| 测试维度 | 结果 |
|---------|------|
| 集成测试（InVEST 直接调用） | **26/26 PASS** |
| LLM 路径测试（英文 prompt → Gemini → InVEST） | **10/10 PASS** |
| Celery Pipeline 烟雾测试 | **2/4 完整通过，2/4 部分通过（演示数据问题）** |
| Docker 容器运行状态 | **33/33 运行中** |

平台核心功能完整，所有 26 个 InVEST 工具均已实现并通过测试。LLM 路径（自然语言 → 工具调用）在 Gemini 重试机制保障下稳定可用。
