# Run-2 反馈处理对照表（2026-07-02）

**测试环境：GCP dev → http://34.42.83.50/**
- 所有改动目前只在 **GCP dev**（热补丁生效），**MSU 仍是旧版**，请勿在 MSU 上验收本表。
- Run-2 反馈是基于 **MSU 旧版**测的；GCP 更新，**部分问题在 GCP 上早已修好**（表中标 `✓ GCP 已修`），无需再改。
- 渲染类测试统一流程：上传输入 → 让 AI 跑对应工具 → 对 AI 说 **"render the result map"** → 看结果图。
- 截图对照见同目录 `../Run2_improvements_20260702_screenshots/`（含 README 逐图说明）。

| # | 反馈指出的问题（来源） | 我做了什么改动 | 现在怎么测 |
|---|----------------------|--------------|-----------|
| 1 | **地图图例太小、看不清，没有标题/单位**（Cori：AWY/NDR/SDR/SWY/RouteDEM/Habitat；Nick：crop）| InVEST 栅格图例放大到 **2x + 粗体黑字**；放进地图**右侧白 gutter**，不再压住数据；栅格自动加**文件名标题**，并对高置信输出加**单位**（如 `Wyield (mm)`、NDR `... (kg/yr)`）；右边距按最宽数字动态算，科学计数也不裁 | 跑任一出 `.tif` 的 InVEST 工具（Annual Water Yield / Carbon / NDR）→ "render the result map" → 看色带在右侧白条、字大加粗、有标题+单位、数字不被切 |
| 2 | **telecoupling 点要素 marker 太小太淡、宽 extent 下难分辨**（Xin：37 causes / 38 systems / 39 systems）| 放大点 marker：systems 三角 7.5→11、agents 人形 9→13、causes 星 7.5→11、flow 端点 2.4→3.2，并加粗黑/白描边提对比 | 跑 Add/Draw Systems、Add Agents、Add Causes → "render the result map" → 点明显更大更醒目 |
| 3 | **causes 用了连续色带，但数据是离散的**（Xin 37）| `✓ GCP 已修`：GCP 上 causes 本就渲成**红星 + categorical 图例**（MSU 旧版才是连续色带）| 跑 Add Causes → render → 红色五角星 + "Causes / Cause" 分类图例（非渐变色带）|
| 4 | **同类渲染图例不一致：systems/causes 图例没 2x、不 bold；agent/flow 根本没图例；图例还盖在地图上**（用户 07-02）| 去掉 telecoupling 图例的"冻结"：**所有图例统一 2x + 粗体**，并和栅格一样放**右侧 gutter 不遮挡地图**；给 **agents**（人形图例）和**无量级 flows**（线图例）补上图例；agent 图例小人改用**真正的 `agent_person.svg` 渲染**，和地图 marker 完全一致 | 分别 render systems / agents / causes / flows → 四类图例都在**右侧白 gutter**、字大加粗；agent 图例里的小人和地图上的人形图标一模一样 |
| 5 | **AI 回复里罗列全部 28 个工具，又长又慢**（Nan 05 / Nick 05）| agent system prompt 加护栏：**未被明确要求就不罗列工具**，直接选对的工具跑；仅当用户明说"列出所有工具"才给清单 | （LLM 冒烟）新开对话跑 Crop Percentile → AI 应直接跑，不再先把所有工具列一遍 |
| 6 | **AI 宣称了并未真正产出的文件**（Run-2 综合）| agent prompt 加规则：**只描述工具实际返回列表里存在的文件**，不虚构 report/tif/图表；缺哪个预期产出就如实说 | （LLM 冒烟）跑任一工具 → AI 描述的输出文件应与实际返回的文件完全对应 |
| 7 | **add_media_flows 强制列名 `lon/lat`，无字段映射**（Xin 40）| `✓ GCP 已修`：GCP 上已接受 `longitude/latitude`（及 `x/y`）| 跑 Add Media Flows，参考 CSV 用 `longitude/latitude` 列名 → 直接运行，不再要求改列名 |
| 8 | **Coastal Vulnerability 报 `habitat_table_path`**（Nan 24）| `— 非 bug`：该参数可选，含 habitat 图层时 InVEST 需要一张关联"保护等级"的 CSV；SKILL 已详细说明，AI 其实是在**正确地**索要该表 | 用 habitat 数据时，提供一张把各 habitat 图层链接到 protection rank 的 CSV → 正常运行 |
| 9 | **CBC transitions CSV 需手动编辑才能进 Tool 3**（Nan / CSIS 02）| `— 非 bug`：这是 InVEST 固有流程；CBC Preprocessor 的 SKILL 已明确"运行 Tool 3 前需手动编辑"并解释各扰动强度；⚠️ 提示正常工作 | 跑 CBC Preprocessor → 看到 transitions 需手改的 ⚠️ 提示 → 编辑后再跑 CBC Main |
| 10 | **crop 输出里一堆带长 uuid 的无意义 CSV**（Nick 06）| 把归一化的中间输入表改写到隐藏子目录 `_csis_intermediate/`（加入扫描跳过表）→ 不再当结果列给用户 | 跑 Crop Percentile / Regression → 输出文件列表里**不再出现** `*_normalized_<uuid>.csv`，只剩 `result_table.csv` / `aggregate_results.csv` / 各 `.tif` |
| 11 | **DelineateIt 渲染 `flow_direction.tif` 报 file not found 却又出图**（Nan 12a）| `— 非 bug`：DelineateIt 产出的是 `watersheds.gpkg`，本就不产 `flow_direction.tif`（那是 RouteDEM 的）；报错是对的。根因是 AI 建议了不存在的文件 → 已被 #6 规则约束 | 跑 DelineateIt → render **`watersheds.gpkg`**（真实输出）；AI 不应再建议渲染 `flow_direction.tif` |
| 12 | **上传慢 / 开站慢 / 进度条一直闪**（多位）| `— 已诊断，非服务器 bug`：上传慢=GCP 在美国机房、国际链路慢；进度条闪=已知取舍（用户 07-01 决定不动）| — |
| 13 | **Network Analysis 对比 Nan 参考：closeness 缺失、betweenness 尺度差 ~17000 倍（归一化 vs 原始）**（截图 `Screenshot 2026-07-01 ...png`）| `✓ GCP 已修`：GCP 的 `network_analysis.R` 早已输出 **degree + closeness(normalized) + betweenness(原始计数)**；截图测的是 MSU 旧版。用真实数据核实与 Nan **精确吻合**：USA betweenness=**1167.86**（与 Nan 完全一致）、closeness=0.41、Top 节点 USA/CAN/BEL/AUS 一致 | 跑 Network Analysis → 开 `network_stats_*.csv` → `betweenness` 为原始计数（USA 1167.86，非 0.0x）、`closeness` 在 0.28–0.41 |
| 14 | **PageRank 和 communities 不在 CSV 里**（用户 07-02：PageRank 未计算；community 只在输出 SHP 的 `cluster_N`，不在 stats CSV）| ★ 改 `network_analysis.R`：CSV **新增 `pagerank` 列**（`page_rank()$vector`）和 **`community` 列**（`membership()`，与 SHP 的 cluster 一致）。现 CSV 五列：degree/closeness/betweenness/pagerank/community。commit `49fca06`（R 每次新进程，热补丁即时生效）| 跑 Network Analysis → 开 `network_stats_*.csv` → 表头含 **pagerank** 与 **community**。已用真实数据核实：USA=deg237/clo0.41/betw1167.86/pr0.0189/community5，walktrap 共 6 组 |

---

## 部署状态与后续
- **本表 #1/#2/#4/#5/#6/#10 = 本次改代码**，共 6 个 commit 在 `gcp-head` 分支；均已**热补丁**在 GCP dev 生效。
- **#3/#7 = GCP 早已修好**；**#8/#9/#11 = 非 bug（已有引导 / 被 #6 约束）**；**#12 = 不改**。
- ⏳ **待固化**：整套改动目前是热补丁，容器 recreate 会回退。需在场做一次镜像 bake（`csic_backend:latest`）+ recreate 固化。
- ⏳ **待回灌 MSU**：需校园网/VPN；MSU 打通后按 tar 工作流同步，届时真实测试者才能在 MSU 上看到这些改进。
- **#5/#6 需真人 LLM 冒烟**（prompt 改动无法确定性单测），其余渲染/输出类改动均已在 GCP dev 真机自测（见截图）。
