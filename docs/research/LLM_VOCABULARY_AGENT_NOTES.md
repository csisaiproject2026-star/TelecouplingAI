# LLM 词表问题在 Agent 系统中的应用讨论

> 背景：在 CSIS 平台开发中，发现 Gemini 2.5 Flash 对 `run_sdr`（泥沙输移比）和 `run_crop_pollination`（授粉服务）这两个 InVEST 工具，在 temperature=0 下持续返回 `candidate.content = None`，而参数结构相近的其他工具（如 `run_ndr`）完全正常。由此引出对 LLM 词表局限性的讨论。

---

## 一、两种不同的"词表"问题

### 1.1 Tokenizer 词表（硬限制）

LLM 使用固定的 tokenizer 将文本切分为 token。Gemini 使用 SentencePiece，词表约 256,000 个 token。

**问题：** 专业领域的低频词汇会被拆分成多个子词 token，导致语义信息碎片化。

```
高频词（完整 token）：
  "Python"  → [Python]         # 1 个 token，语义完整
  "API"     → [API]            # 1 个 token
  "river"   → [river]          # 1 个 token

低频专业词（被拆分）：
  "erodibility"  → [er, od, ib, ility]     # 4 个 token，语义分散
  "biophysical"  → [bio, physical]          # 2 个 token
  "run_sdr"      → [run, _s, dr] 或类似     # 拆分方式不可预测
```

**影响：** 被拆分的词在注意力机制中的表示更弱，模型对它们的"理解"依赖于子词的组合，而不是整词的语义。

**无法通过 prompt 解决**，只能通过微调或换模型。

---

### 1.2 语义关联（可部分影响）

模型权重里编码了训练数据中词汇的共现模式。某个词和什么场景关联，直接决定了模型看到它时的"第一反应"。

**CSIS 平台具体案例：**

| 词汇 | 训练数据中的强关联 | 在我们场景中的含义 | 结果 |
|------|-------------------|------------------|------|
| `SDR` | Software Defined Radio（软件无线电）、Special Drawing Rights（特别提款权） | Sediment Delivery Ratio（InVEST 工具） | 模型犹豫，倾向于解释而非调用 |
| `pollination` | 生物学概念、蜜蜂、花粉、授粉过程描述 | InVEST 授粉服务计算工具 | 模型倾向于解释生物概念 |
| `NDR` | 几乎只有 Nutrient Delivery Ratio（环境科学专用） | 同上 | 模型直接调用，无歧义 |

**可以通过 prompt 部分改善**，但无法覆盖模型权重中的深层关联。

---

## 二、为什么这在 Function Calling 场景中特别明显

普通对话中，模型即使对某个词理解有偏差，也能用其他词来"绕"。但 Function Calling 是一个**二元决策**：

```
输入 → 模型决策 → ① 输出 FunctionCall JSON（调用工具）
                 → ② 输出自然语言文字（解释/对话）
```

在 temperature=0（贪婪解码）下，这个决策是确定性的。当两个选项的 logit 分数极度接近时，模型进入临界状态，结果是**输出 0 个 token**（既不调用，也不回复）。

这是 Function Calling 特有的失效模式——在普通对话中不存在，在传统 API 调用中也不存在，只在 LLM 驱动的 agent 工具调用中才会出现。

---

## 三、词汇表注入（Glossary Injection）方案

### 3.1 基本思路

在 system_instruction 里加入领域词汇表，提供推理时的语义锚点：

```markdown
## Domain Glossary
The following are InVEST ecosystem modeling tools. When the user asks to run any of these,
you MUST call the corresponding function — do not describe or explain the concept:

- SDR / Sediment Delivery Ratio → call `run_Sediment_Delivery_Ratio_SDR`
- NDR / Nutrient Delivery Ratio → call `run_ndr`
- SWY / Seasonal Water Yield   → call `run_seasonal_water_yield`
- Pollination / bee services   → call `run_crop_pollination`
- HRA / Habitat Risk           → call `run_habitat_risk_assessment`
```

### 3.2 有效范围

| 问题类型 | 词汇表能解决吗 |
|---------|-------------|
| 多义词歧义（SDR 是无线电还是泥沙？） | ✅ 有帮助，提供明确映射 |
| 低频词被错误 tokenize | ❌ 无效，tokenizer 在词汇表加载前已完成切分 |
| temperature=0 的临界状态 | ⚠️ 有限帮助，改变输入概率分布，但不能保证突破临界 |
| 模型对生物概念的"解释冲动" | ⚠️ 有限帮助，明确指令可以压制，但不能彻底消除 |

### 3.3 与改函数名方案的对比

```
词汇表方案：影响 INPUT 侧（模型对输入的理解）
改函数名方案：影响 OUTPUT 侧（模型生成的 token 序列）
```

问题出在 OUTPUT 阶段（模型决定输出什么），因此改函数名比加词汇表更直接。但两者可以叠加使用。

---

## 四、潜在的深入应用方向

### 4.1 细粒度领域词汇表

不只是函数名映射，而是建立完整的领域语义网络注入上下文：

```
LULC = Land Use / Land Cover（土地利用/土地覆盖）
DEM  = Digital Elevation Model（数字高程模型）
AOI  = Area of Interest（感兴趣区域）
ETO  = Reference Evapotranspiration（参考蒸散发）
PAWC = Plant Available Water Content（植物有效水分含量）
```

当用户说"我有一个 DEM 文件"，模型能正确理解这是地形数据，而不是其他含义。

### 4.2 函数名设计原则（针对 LLM Agent）

基于本项目经验，给 LLM agent 设计函数名时的建议：

- ❌ 避免：有多义缩写（SDR、HRA、CBC）
- ❌ 避免：与常见自然语言概念重名（pollination、flood、cooling）
- ✅ 推荐：使用完整词汇（`run_Sediment_Delivery_Ratio_SDR`）
- ✅ 推荐：加领域前缀（`invest_sdr_run`、`natcap_pollination_run`）
- ✅ 推荐：函数名中包含动词（`run_`, `compute_`, `calculate_`）使函数调用意图更明显

### 4.3 混合路由策略

对于高歧义工具，可以考虑两阶段架构：

```
阶段 1（轻量分类器，非 LLM）：
  规则 / 正则 / 关键词匹配 → 判断工具类别

阶段 2（LLM 参数解析）：
  只传入已确定类别的 1 个 FunctionDeclaration
  → LLM 专注于参数抽取，不需要做工具选择决策
```

这正是 CSIS 平台目前的 `_detect_tool_from_message` + 单工具模式的设计思路。

### 4.4 Temperature 与 Function Calling 的关系

| Temperature | 行为 | 适用场景 |
|-------------|------|---------|
| 0 | 确定性，但临界状态导致空输出 | 高频确定性工具 |
| 0.3–0.7 | 有适度随机性，可打破临界状态 | 语义歧义工具 |
| 0.9–1.0 | 强随机性，几乎肯定打破临界 | 最难工具的兜底策略 |

经验规律：**对于 LLM Agent 的 Function Calling，temperature=0 并不是最优选择**。适度的温度（0.3–0.5）在保持参数解析准确性的同时，也能避免空输出临界状态。

### 4.5 Fine-tuning 作为根本解法

如果平台工具数量增加到 50+ 个，且有持续出现的空输出问题，可以考虑对 Gemini 进行领域微调：

- 用真实的用户请求 + 正确函数调用对作为训练数据
- 让模型"记住" InVEST 工具名称与调用场景的关联
- 成本：需要数百到数千条高质量训练样本

---

## 五、CSIS 平台当前处理方案总结

| 问题 | 解决方案 | 效果 |
|------|---------|------|
| SDR 空输出 | 函数名改为 `run_Sediment_Delivery_Ratio_SDR` + 重试机制 | 待测试 |
| Pollination 空输出 | base_temperature=0.9，重试不低于 0.9 | 稳定通过 |
| 所有工具 | 单工具模式（iteration=0 只传 1 个 FunctionDeclaration） | 减少歧义 |
| 重试收敛 | 温度从 base 递增到 1.0，最多 10 次 | 兜底保障 |

---

*文件创建：2026-05-06*  
*关联功能：CSIS 平台 LLM 路径稳定性优化*
