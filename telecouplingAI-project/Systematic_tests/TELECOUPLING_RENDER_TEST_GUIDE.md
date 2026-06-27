# Telecoupling 渲染测试指南（手动逐项）

> 目标：在网站上逐个验证 8 个 telecoupling 工具产出的图层能按角色正确渲染
> （flows=弯弧分级线、systems=正/倒三角+橙圆、agents=小人、causes=红星），
> 单独上传文件能用 `render_as` 指定，合成图能叠成一张。

## 0. 测试环境

- 地址：**http://34.42.83.50/**（建议用**无痕窗口**，避免旧缓存）
- 测试数据（本地，上传时浏览到这里）：
  `telecouplingAI-project/Systematic_tests/Test_data/<NN>_<tool>/`
- 额外 demo 数据（为看清三角区分）：
  `telecouplingAI-project/Systematic_tests/render_demo_data/`

## 1. 通用流程（每个工具都一样）

1. **上传** 对应的 CSV（媒体流还要传 HTML）。
2. 发一条 **prompt 跑工具** → 生成带 `tc_role` 标记的 shp。
3. 发一条 **prompt 渲染** → 自动按角色出样式（图是 JPEG，应秒加载）。
4. 如果是**流**（flows/媒体/贸易），渲染时 AI 会**先问你用哪一列做数量** → 回一个列名即可。

> 关键点①：**渲染必须真出图**。如果 AI 只回 "Here is the map" 却没有图，就是假渲染 bug——已修，若复现告诉我。
> 关键点②：每次都是**新生成**的文件才带标记；旧文件没有 `tc_role` 会走通用渲染。

---

## 2. 逐工具测试

### ① Radial Flows（弯弧流）— 33
- **上传**：`Test_data/33_radial_flows/flows.csv`
- **跑工具**：
  `Draw radial flows from this table. from_x_field=from_lon, from_y_field=from_lat, to_x_field=to_lon, to_y_field=to_lat`
- **渲染**：`Render the radial_flows result as a map`
  → AI 问数量列 → 回 **`flow_value`**
- **预期**：弯曲弧线，按 flow_value 颜色（粉→品红）+ 线宽分级，起讫点有小圆点，右侧色带图例。

### ② Commodity Trade（贸易流）— 34
- **上传**：`Test_data/34_commodity_trade/trade.csv`
- **跑工具**：
  `Map commodity trade flows. from_country_field=exporter_iso3, to_country_field=importer_iso3, value_field=trade_usd`
- **渲染**：`Render the commodity trade flows` → 数量列回 **`trade_usd`**
- **预期**：国家间弯弧贸易流，按 trade_usd 分级。

### ③ Media Information Flows（媒体流）— 40
- **上传**：`Test_data/40_add_media_flows/article.html` **和** `country_centroids.csv`（两个一起传）
- **跑工具**：
  `Add media information flows. html_file=article.html, country_reference_csv=country_centroids.csv, source_lon=116.4, source_lat=39.9, source_name=Beijing`
- **渲染**：`Render the media flows` → 数量列回 **`mentions`**
- **预期**：从北京出发的弯弧媒体流，按 mentions 分级。

### ④ Add Agents Interactively（主体·交互版）— 35
- **上传**：`Test_data/35_add_agents/agents.csv`
- **跑工具**：`Add agents interactively. x_field=longitude, y_field=latitude`
- **渲染**：`Render the agents` （文件名为 agents.shp）
- **预期**：**小人图标**（不是圆点）。

### ⑤ Draw Agents from Table（主体·表格版）— 36
- **上传**：`Test_data/36_draw_agents_table/agents_table.csv`
- **跑工具**：`Draw agents from table. x_field=longitude, y_field=latitude`
- **渲染**：`Render the agents from table result`
- **预期**：**小人图标**。

### ⑥ Add Systems Interactively（系统·交互版）— 38
- **上传（推荐用 demo 看三角区分）**：`render_demo_data/systems_SRS.csv`
  （它的 type 列是 Sending/Receiving/Spillover；用 `Test_data/38_add_systems/systems.csv` 也能跑，但 type 是 Watershed 等→会全是正三角）
- **跑工具**：`Add systems interactively. x_field=longitude, y_field=latitude`
- **渲染**：`Render the systems`
- **预期**：Sending=**正实心绿三角**、Receiving=**倒实心绿三角**、Spillover=**橙圆**，带类型图例。

### ⑦ Draw Systems from Table（系统·表格版）— 39
- **上传**：`render_demo_data/systems_SRS.csv`（同上，想看区分就用这个）
- **跑工具**：`Draw systems from table. x_field=longitude, y_field=latitude`
- **渲染**：`Render the systems from table result`
- **预期**：同⑥。

### ⑧ Add Causes Interactively（驱动）— 37
- **上传**：`Test_data/37_add_causes/causes.csv`
- **跑工具**：`Add causes interactively. x_field=longitude, y_field=latitude`
- **渲染**：`Render the causes`
- **预期**：**红色★星形**标记 + 星形图例。

---

## 3. 合成图（Phase B：一张 Fig.10）

先把上面几类各跑出一个（至少 flows + systems + agents，causes 可选），然后：

`Combine the flows, systems, agents and causes into one telecoupling map`（如含流，数量列回对应列名）

- **预期**：一张图里同时有 弯弧分级流 + 正/倒三角 + 橙圆 + 小人 + 红星 + 右上组合图例 + 右侧流色带。

---

## 4. 单独上传文件 + `render_as`（不靠 tc_role）

如果你**自己上传一个普通点/线 shp**（没有 tc_role），要按 telecoupling 样式渲染，必须在 prompt 里**说清楚类型**：

- `Render this shapefile as agents`（→ 小人）
- `Render this as a system map`（→ 三角）
- `Render this as flows, using <列名> as the magnitude`（→ 弯弧流）
- `Render this as causes`（→ 红星）

不说类型、文件又没 tc_role → 走**通用渲染**（默认点/线，无 telecoupling 样式）。这是有意为之，保证不误伤其他工具的文件。

---

## 5. 检查清单（每项打勾）

- [ ] ① radial flows → 弯弧分级 + 起讫点
- [ ] ② commodity trade → 贸易弧线分级
- [ ] ③ media flows → 北京出发的弧线分级
- [ ] ④ add agents → 小人
- [ ] ⑤ draw agents table → 小人
- [ ] ⑥ add systems → 正/倒三角 + 橙圆（用 demo CSV）
- [ ] ⑦ draw systems table → 正/倒三角 + 橙圆（用 demo CSV）
- [ ] ⑧ add causes → 红星
- [ ] 合成图 → 全部叠一张
- [ ] render_as → 单独上传文件按指定类型渲染
- [ ] 通用兜底 → 无标记/未指定 → 默认渲染（无 telecoupling 样式）
- [ ] 每次渲染都**真出图**（无"假渲染"）、图**秒加载**（JPEG，无 preview expired）

---

## 6. 已知注意

- **旧文件无 tc_role**：你之前已经生成的 shp 不带标记，渲染会走通用；**重新跑一遍工具**即带标记。
- **数量列**：流类渲染时 AI 会先问你选哪列——这是设计如此（人工指定），回列名即可。
- 当前部署是**热补丁未 baked**：容器若被重建会回退；测通过后我再 commit + rebuild 持久化。
