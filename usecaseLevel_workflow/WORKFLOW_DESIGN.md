# Use-Case Level Workflow — 设计草案 (v0.1)

> 目标：让用户给一个**分析目标**（一个 telecoupling case），AI 自动把它拆成多步、调多个现有工具、
> 串起来完成，最后给结果 + 解读。基于 Tonini & Liu 2017 的五组件框架（Systems / Agents / Flows /
> Causes / Effects）。第一个落地案例：卧龙生态旅游（数据见 `TourismTelecoupling_Workflow/`）。
>
> 状态：设计草案，待评审后进入 MVP。本文件是总设计；具体案例的工具映射见各 `*_Workflow/WORKFLOW.md`。

---

## 1. 目标与范围

**要做的**
- 用户用一句话描述分析目标 → AI 规划 → 引导用户给数据 → 确认 → 自动执行多工具链 → 出结果 + 解读。
- 复用现有 43 个工具，不重写工具本身。

**明确不做的（至少 MVP 不做）**
- 不做"任意自然语言 case 都能规划"——MVP 先把已知案例（tourism）做扎实，论文那套五组件当 few-shot。
- 不做并行 DAG（先线性/简单依赖链）。
- 不解决 LLM 本身的生成质量、工具自身的 bug。

## 2. 交互模型（已敲定）

**"对话式向导"**：用户说目标 → AI 拆步骤给计划 → **A) 计划里一次性列出完整数据清单（manifest）**，用户可批量传或逐个喂 → **B) 真跑到某步发现还缺，再补问（兜底）** → 用户确认 → 执行 → 结果 + 解读。

```
用户：我要做卧龙生态旅游的 telecoupling 分析
AI  ：拆成 5 步：①系统 ②全球客流网络分组 ③游客流 ④CO2 ⑤成因(FAMD)。
      需要这些数据【清单 A】：系统坐标表 / 客流起止表 / nodes+links+世界国界图层 / ...
      你可以现在一起传，也可以我们一步步来。
用户：（上传若干）
AI  ：计划如下【可读 DAG】，确认就开跑。
用户：确认
AI  ：（编排器逐步执行，实时进度）→ 出图/表/下载 + 一段解读
       （若中途缺第④步的文件 → 兜底 B：临时问用户补传）
```

## 3. 架构：四阶段（LLM 与确定性代码的分工）

| 阶段 | 谁干 | 干什么 |
|------|------|--------|
| **① Plan 规划** | LLM | 读"目标 + 能力目录 + 已上传清单" → 经 `propose_workflow_plan` 工具产出**结构化计划**（数据，非隐式链） |
| **② Confirm + Intake 确认与收数据** | 后端 + 人 | 校验计划（工具存在/输入有着落/类型对，复用 `tool_file_specs.py`）→ 渲染可读 DAG + 数据清单 → 用户传文件、点确认 |
| **③ Execute 执行** | **确定性编排器**（非 LLM） | 按依赖顺序逐步跑：解析每步输入（上传文件 / 上游步骤输出）→ 现有 Celery 队列 → 把输出登记进运行上下文 |
| **④ Synthesize 解读** | LLM | 拿全部输出（CSV/图）写叙述分析（对应论文 Results） |

**核心原则**：会抖动的 LLM 只在两端（规划 + 解读）出现，且规划结果由用户确认；中间 N 步执行是机械、可复现、可重试的。

## 4. 数据模型

### WorkflowPlan（LLM 产出，后端校验）
```jsonc
{
  "case_name": "tourism_telecoupling",
  "description": "游客流向卧龙的 telecoupling 分析",
  "required_inputs": [                      // 清单 A（manifest）
    { "id": "systems_table", "label": "系统坐标表", "file_kind": "table",
      "description": "含系统名/角色/经纬度", "satisfied_by": null }   // 用户传后填 upload ref
    // ...
  ],
  "steps": [
    {
      "id": "s1", "component": "systems",
      "tool": "run_draw_systems_from_table",
      "inputs": {
        "input_csv": { "source": "input", "ref": "systems_table" },
        "x_field":   { "source": "literal", "value": "LON" },
        "y_field":   { "source": "literal", "value": "LAT" }
      },
      "depends_on": [],
      "produces": ["systems_from_table.shp"],
      "rationale": "把系统坐标表渲染成点图层"
    },
    {
      "id": "s4", "component": "effects",
      "tool": "run_co2_emissions",
      "inputs": {
        "input_csv": { "source": "input", "ref": "flows_with_distance" },
        "animal_count_field": { "source": "literal", "value": "Quantity" },
        "length_km_field":    { "source": "literal", "value": "length_km" },
        "capacity_per_trip":  { "source": "literal", "value": 1 },
        "co2_per_km_per_trip":{ "source": "literal", "value": 29 }
      },
      "depends_on": ["s3"],
      "produces": ["co2_emissions_results.csv"]
    }
  ]
}
```

**input source 三种**：`input`（清单里某个上传文件）/ `literal`（字段名、数值参数）/ `step`（上游步骤的输出文件，按 `produces` 接线）。

### RunContext（执行期，存 Redis）
```jsonc
{
  "request_id": "...", "plan": { /* 上面的 plan */ },
  "step_status": { "s1": "done", "s2": "running", ... },     // pending/running/done/error/skipped
  "step_outputs": { "s1": [ {filename, path, render_type}, ... ] },
  "warnings": [], "started_at": ..., "ended_at": ...
}
```
编排器解析 `inputs[*].source`：`input`→清单映射的上传路径；`literal`→直接取值；`step`→上游 `step_outputs` 里的文件路径。

## 5. 后端组件

**新增**
1. **能力目录 (capability catalog)** — 一份喂给 LLM 的知识：43 工具各属哪个组件、I/O 签名、何时用 + tourism 等已知案例当 few-shot。可由 `tool_file_specs.py` + SKILL.md 自动生成。
2. **`propose_workflow_plan` 工具** — Gemini function-call，参数 schema 约束成上面的 WorkflowPlan 结构，让规划以数据回来。
3. **计划校验器 (plan validator)** — 工具是否存在、required_inputs 是否都被某上传/上游满足、文件类型是否匹配（复用 `tool_file_specs.py` 预检）、依赖是否成环。
4. **编排器 (orchestrator)** — 拓扑序执行；每步解析输入→入 Celery 队列→等完成→登记输出；失败可重试/中止/跳过。
5. **运行上下文存储** — Redis（与 Tier 3 共用底座）。

**复用**
- 43 个 Celery 工具、`tool_file_specs.py` 校验、session 工作区做文件交接、`output_router` 分类、agent.py 已有的"多轮收集缺失参数/文件"机制（直接支撑兜底 B）。

## 6. API / 事件（与 Tier 3 的关系）

- 一个 workflow run = 一个长任务（多步、好几分钟）→ **正好建在 Tier 3 的任务 ID 解耦 + Redis 事件 buffer + 断点续传之上**。Tier 3 是它的执行底座，建议合建或 Tier 3 先行。
- 事件流新增类型（在现有 SSE 上扩展）：`plan_proposed`（带可读 DAG + manifest）、`input_needed`（兜底 B 要文件）、`step_started/step_progress/step_done/step_error`、`workflow_done`、`synthesis`（解读文本）。

## 7. 前端

- **计划卡**：渲染 DAG（步骤 + 每步要什么 + 产出什么）+ **数据清单 checklist**（每项显示"待上传/已上传 ✓"）+ 「确认执行」按钮。
- 上传复用现有上传 + **文件夹上传**（shapefile 是 .shp/.shx/.dbf/.prj 一组，文件夹上传正好用上）。
- 末尾：结果文件区（下载/按需渲染）+ 解读文本。
- **位置**：建议融进现有聊天（触发规则见 §11），保留对话感；与单工具调用共存。

### 7.1 过程展示（可展开/折叠，两层）

两层都建在现有 SSE 流上（Tier 1/2 已流式推文字，只是加事件类型），且都是**可折叠**组件：

1. **执行过程「行动叙述」（主，可靠）** — 把计划 + 每步进展显示成结构化条目（"🧠 拆成 5 步 → ✅ 标系统(57) → ⏳ 画游客流 → ✅ 用流算 CO2…"）。来源是我们自己产生的事件（`plan_proposed`/`step_started`/`step_done`…，见 §6），**准确、可控、不依赖模型**。
   - **默认状态**：执行中**展开**、实时可见；**完成后自动收成一行摘要**（"✅ 完成 N 步 · 展开看详情"），可再点开。
2. **模型「思考」块（次，锦上添花）** — Gemini 2.5 Flash 的 thought summaries（`thinkingConfig(includeThoughts=true)`；`google-genai 2.8.0` 支持），流进一个折叠块。
   - **默认状态**：**默认折叠**成"思考"小条，点开看摘要。
   - ⚠️ 必须与"真实行动/结果"视觉严格分开：模型"思考里说要调某工具" ≠ 它真调了（BUG6 同类陷阱），不能让"想了一下"冒充"做了"。
   - 成本：有额外延迟/ token；当可选项，MVP 可后置。

## 8. MVP 范围 vs 后续

**MVP（先做，目标=tourism 端到端）**
- 能力目录（覆盖 tourism 需要的 5 个工具）+ `propose_workflow_plan` + 校验器 + **线性**编排器 + 计划卡/清单 UI + 确认 + 顺序执行 + 简单解读。
- 数据清单走 A，兜底 B 复用现有多轮收集。
- 验收：tourism 案例（Systems→Network→Flows→CO2→FAMD）在 GCP 端到端跑通，出图对照论文 Fig。

**后续**
- 完整 DAG（并行分支）、单步重试 UI、Tier 3 续传、跨设备"我的进行中任务"。
- 从"已知案例"放开到"任意 case 自由规划"。
- 把 OneDrive 里另外 3 套案例（International Transport / Qilian / Soybean）纳入。

## 9. 风险 / 待解

- **LLM 规划可靠性**：靠"计划是数据 + 用户确认"兜底；能力目录要写清楚减少乱编。
- **跨步实体一致性**：systems/flows/cba 要指同一批实体——确认环节 + 校验器尽量早暴露。
- **数据预处理**：有些步骤数据不能直接用（CO2 要算距离列、FAMD 要 shapefile→csv）。MVP 先靠预先备好的数据（见 `TourismTelecoupling_Workflow/prepare_data.py`）；后续考虑让 AI/编排器自动做轻量转换。
- **栖息地退化步缺数据**：tourism SampleData 无 LULC+分区，Habitat Quality 这步暂不纳入。
- **长任务超时**：依赖 Tier 3；MVP 阶段可先在 GCP 容忍。

## 10. 落地步骤建议

1. 先在 GCP 手动把 tourism 5 步串通（spike，验证工具吃数据 + 出图）——几乎零开发，暴露真实问题。
2. 写能力目录 + `propose_workflow_plan` schema，让 LLM 能产出/校验 tourism 的计划（先不执行）。
3. 实现线性编排器 + RunContext，打通"确认→自动跑完"。
4. 前端计划卡 + 清单 + 进度。
5. 加解读阶段。
6. 评估后再上 DAG / Tier 3 / 更多案例。

---

## 11. 触发 / 路由（单工具调用**不**进 workflow）

**原则：现有单工具链路（已测 43/43）保持原样，workflow 是叠加、不污染它。**

- 请求能落到**单个工具** → 直接调该工具，**和今天完全一样**（不弹计划、不走确认）。
- 只有当请求是一个**需要串 ≥2 个工具的分析目标** → 才进 workflow（plan → 确认 → 执行）。

**让路由不乱触发的三层防线：**
1. **提示词 + 能力目录规则**：`propose_workflow_plan` 只是 LLM 工具箱里多出来的一个工具；明确"只有多步目标才出计划，能对到单工具的请求直接调那个工具"。
2. **1 步坍缩护栏**：若 LLM 给的"计划"只有 1 步，后端降级成普通单工具调用，不走计划-确认仪式。
3. **确认闸是安全网**：即便偶尔误判进 workflow，也只是回一份计划等用户确认——不点确认什么都不跑，误触发最多多一条计划消息，不会失控。

**边界情况**：模糊请求（"分析旅游客流" 既像单工具又像多步）→ **偏向更简单的解释（单工具）**，用户想要更多再追一句即可。

**可选**：留一个显式入口（"分析/Workflow"开关/按钮）给想确保走 workflow 的用户；默认聊天框仍自动路由。
