# Tourism Telecoupling — Workflow 研究与工具映射

> 把 `SampleData_TourismTelecoupling/`（卧龙生态旅游案例的原版数据）映射到 CSIS 平台现有工具，
> 形成一个可端到端运行的 use-case 级工作流。参考论文：Tonini & Liu 2017, *Ecology and Society* 22(4):11。
> 本目录是该工作流的工作区；`prepare_data.py` 负责把需要转换的数据准备好。

---

## 1. 案例一句话

游客从中国各省（及全球各国）流向**卧龙保护区**（Wolong = 唯一 Receiving 系统）。围绕这条 telecoupling，
用平台工具刻画 **Systems / Flows / Causes / Effects** 四个组件并量化效应。

## 2. 数据咬合性（已验证，是一套真工作流数据，不是玩具数据）

- Systems 57 行（Wolong=Receiving + 56 个 Sending），Flows 49 行全部 "省 → Wolong"。
- **Flows 起点 46/49 精确等于 Systems 名**（另 3 个 NewZealand/CostaRica/SouthKorea 仅空格差异）。
- CO2 用的就是同一份 Flows；FAMD 的 56 行 = 56 个 Sending 系统。→ 同一批实体贯穿 Systems→Flows→CO2→FAMD。

## 3. 五步工作流映射表（核心）

| # | 组件 | 工具 (call name) | 输入文件 | 关键参数 / 字段映射 | 期望输出 | 论文对照 |
|---|------|------------------|----------|---------------------|----------|----------|
| 1 | Systems | `run_draw_systems_from_table` (38/39) | `SampleData/Systems-UploadSystems/tourism_Systems.csv` | `x_field=LON`, `y_field=LAT` | systems 点图层 (shp/geojson) | Fig 10（systems） |
| 2 | Systems(网络) | `run_network_analysis_grouping` (01) | `SampleData/Systems-NetworkGrouping/{nodes.csv, links.csv, World_countries_2002.shp}` | `nodes_join_attri=CODE`, `layer_join_attri=ISO_3_CODE`, `clustering_algorithm=walktrap` | 国家按到访客流的社群分组图 + stats | （全球客流网络分组） |
| 3 | Flows | `run_draw_radial_flows` (33) | `SampleData/Flows/tourism_Flows.csv` | `from_x_field=FROM_X`, `from_y_field=FROM_Y`, `to_x_field=TO_X`, `to_y_field=TO_Y` | 测地线流图层 | Fig 10（flows） |
| 4 | Effect-CO2 | `run_co2_emissions` (30) | **`flows_with_distance.csv`**（本目录，预处理产物） | `animal_count_field=Quantity`, `length_km_field=length_km`, `capacity_per_trip=1`, `co2_per_km_per_trip=29` | 每条流 CO2 + 汇总 | Fig 8 同法（29 kg/km Boeing777） |
| 5 | Cause-FAMD | `run_factor_analysis_mixed_data` (29) | **`famd_input.csv`**（本目录，预处理产物） | `quantitative_variables="affin,gdplog,dist"` | 因子分析图 + 特征值表 | Fig 7 / Table 2-3 |

> Cause 文件夹里的 `Wolong_NatReserve.shp`（保护区边界）是空间上下文/栖息地分析底图；论文 tourism 的环境
> 效应原本用 Habitat Quality（LULC 2001/2007 + 1998/2009 分区），但**本 SampleData 未带 LULC 栅格**，
> 故栖息地退化这步暂缺数据，先不纳入工作流（见 §6）。

## 4. 需要的数据预处理（`prepare_data.py`）

5 步里有 3 步可直接吃原版 CSV（工具用可配置字段参数，无需改数据）。只有 2 步需要预处理：

- **CO2**：原版 `tourism_Flows.csv` 有 FROM/TO 坐标和 `Quantity`，但**没有距离列**；而 `co2_emissions`
  工具不自己算距离、要求一个 `length_km` 列。→ 脚本按 haversine 算测地距离，产出 `flows_with_distance.csv`。
- **FAMD**：调查变量在 shapefile 的 .dbf 里（`Systems_withSimulatedTourism`），不是 CSV。→ 脚本导出
  `famd_input.csv`，保留 `affin`(文化亲和) / `gdplog`(log GDP) / `dist`(到卧龙距离) 三个数值变量。

跑一次：`python prepare_data.py`（需 geopandas，用项目 conda 环境 `TeleCouplingAI`）。

**预处理自检**：49 条流，距离 54–18,817 km；按 29 kg/km、cap=1 的演示总 CO2 ≈ **5.88M kg**
（论文熊猫案例是 5.2M kg，量级一致，佐证算法对）。

## 5. 怎么运行（下一步 spike）

工具是 Celery 任务、依赖完整 conda+R 环境，最稳的实跑场所是 **GCP dev 环境**（已部署最新代码）。
建议先手动按上表逐步跑通（Systems → Flows → CO2 →（Network/FAMD）），每步把输出喂下一步 /
存档，并和论文 Fig 对照。这一步验证：① 我们的工具吃不吃这套原版数据；② 出图是否合理。

## 6. 已知风险 / 待确认

- **CO2 参数语义**：`Quantity` 在原版里=1（每条流一个单位）。capacity/co2 因子取论文的 Boeing-777
  值（29 kg/km, cap=1）做演示；真实游客量级需要的话另配。
- **栖息地退化缺数据**：本 SampleData 无 LULC 栅格 + 分区，论文 tourism 的 Habitat Quality 这步跑不了；
  要补这步需另找卧龙 2001/2007 LULC + 1998/2009 zoning。
- **Network 输出语义**：nodes/links 已是 R 脚本期望格式（`graph_from_data_frame` 取 links 前两列
  sender/receiver，nodes 第一列 CODE，且脚本会用 `larrivals.sender` 节点属性）——格式对，但实跑产物
  需肉眼核对分组是否合理。
- **本目录数据未提交 git**（与其它 SampleData 一样属测试数据，按"只推代码"惯例排除）。
