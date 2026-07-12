# CSIS Telecoupling AI Platform — 用户演示流程（检查清单）

> 文档生成日期：2026-04-05  
> 访问地址：http://35.184.212.119  
> 注意：使用前请先在 GCP Console 启动 csis-server 实例  

---

## 前置准备

- [ ] GCP Console → Compute Engine → csis-server → 点击"启动"
- [ ] 等待约 30 秒，打开 Chrome 浏览器
- [ ] 地址栏输入：**http://35.184.212.119**
- [ ] 确认页面正常加载（非空白，非 502 错误）
- [ ] 演示数据已在服务器 `~/csis-platform/datainput_for_demo/` 目录下，**无需上传**

---

## 场景 1：页面基础功能检查

### 1.1 首页加载
- [ ] 页面正常显示聊天界面，左侧有侧边栏
- [ ] 右侧主区域显示欢迎界面，含 6 个工具快捷提示按钮
- [ ] 左上角或顶部有"新建对话"按钮

### 1.2 新建对话
- [ ] 点击"新建对话"（或 New Chat）
- [ ] 右侧聊天区域清空，显示空白输入框

### 1.3 模型选择
- [ ] 找到模型选择下拉框（一般在顶部或设置面板）
- [ ] 可以选择：gemini-2.5-flash / gemini-1.5-flash / gemini-2.0-flash / gemini-1.5-pro
- [ ] 保持默认 gemini-2.5-flash

### 1.4 聊天记录侧边栏
- [ ] 左侧侧边栏可以折叠/展开
- [ ] 历史对话记录显示在侧边栏
- [ ] 可以点击切换到历史对话

---

## 场景 2：普通对话测试（无工具调用）

### 2.1 发送普通问题
- [ ] 在底部输入框输入：`你好，这个平台支持哪些分析工具？`
- [ ] 点击发送按钮（或按 Enter）
- [ ] 确认 AI 流式回复（文字逐字出现，非一次性加载）
- [ ] 回复内容提到 6 个 InVEST 工具名称

### 2.2 多轮对话
- [ ] 继续输入：`工具1网络分析需要什么输入文件？`
- [ ] AI 给出关于网络分析所需文件的详细说明
- [ ] 确认 AI 记住了上下文（知道在讨论工具1）

---

## 场景 3：工具 1 — 网络社区分析（Network Analysis）

### 3.1 输入数据说明
演示数据路径（服务器内）：
```
/home/csisaiproject2026/csis-platform/datainput_for_demo/network_analysis/
```

### 3.2 发送工具调用请求
- [ ] 新建对话
- [ ] 在输入框输入以下内容并发送：

```
请帮我运行网络社区分析。
节点文件：/home/csisaiproject2026/csis-platform/datainput_for_demo/network_analysis/nodes.csv
链接文件：/home/csisaiproject2026/csis-platform/datainput_for_demo/network_analysis/links.csv
地理文件：/home/csisaiproject2026/csis-platform/datainput_for_demo/network_analysis/regions.shp
聚类算法：walktrap
```

### 3.3 检查执行过程
- [ ] 出现工具状态卡片（⚙️ 运行中...）
- [ ] 进度条数字实时更新（如 10% → 50% → 100%）
- [ ] 工具完成后卡片变为 ✅ 完成

### 3.4 检查输出结果
- [ ] 出现文件下载列表，包含：
  - [ ] `output_*.shp`（聚类后的 Shapefile）及相关 .dbf/.prj 等附属文件
  - [ ] 网络统计 CSV 文件
  - [ ] PDF 可视化报告
- [ ] 点击任意文件，确认可以正常下载
- [ ] AI 给出对分析结果的文字解释

---

## 场景 4：工具 2 — 蓝碳预处理（CBC Preprocessor）

### 4.1 发送工具调用请求
- [ ] 新建对话，输入：

```
请运行蓝碳预处理工具。
土地覆盖快照文件：/home/csisaiproject2026/csis-platform/datainput_for_demo/cbc_preprocessor/landcover_snapshots.csv
LULC查找表：/home/csisaiproject2026/csis-platform/datainput_for_demo/cbc_preprocessor/lulc_lookup.csv
```

### 4.2 检查执行过程
- [ ] 工具状态卡片正常显示和更新

### 4.3 检查输出结果
- [ ] 出现输出文件，包含：
  - [ ] `transitions_*.csv`（土地覆盖转换表）
  - [ ] 对齐后的 LULC TIF 文件
- [ ] **关键检查**：AI 是否给出警告提示，说明需要手动编辑 transitions 文件后才能运行工具3
- [ ] 出现 ⚠️ WarningCard 或 AI 文字提醒

---

## 场景 5：工具 3 — 蓝碳主模型（Coastal Blue Carbon）

### 5.1 发送工具调用请求
- [ ] 继续在场景4的对话中，或新建对话，输入：

```
请运行蓝碳主模型。
土地覆盖快照：/home/csisaiproject2026/csis-platform/datainput_for_demo/coastal_blue_carbon/landcover_snapshots.csv
转换表：/home/csisaiproject2026/csis-platform/datainput_for_demo/coastal_blue_carbon/transitions.csv
生物物理参数表：/home/csisaiproject2026/csis-platform/datainput_for_demo/coastal_blue_carbon/biophysical_table.csv
```

### 5.2 检查输出结果
- [ ] 输出文件包含多个 TIF 文件（碳储量、固碳量等）
- [ ] 出现空间预览图（PNG 图片直接在聊天界面显示）
- [ ] 图片可以正常加载（非破损图标）
- [ ] AI 对碳储量结果给出解读说明

---

## 场景 6：工具 4 — 季节性水量（Seasonal Water Yield）

### 6.1 发送工具调用请求
- [ ] 新建对话，输入：

```
请运行季节性水量模型。
研究区：/home/csisaiproject2026/csis-platform/datainput_for_demo/seasonal_water_yield/watershed.shp
LULC栅格：/home/csisaiproject2026/csis-platform/datainput_for_demo/seasonal_water_yield/lulc.tif
DEM：/home/csisaiproject2026/csis-platform/datainput_for_demo/seasonal_water_yield/dem.tif
土壤组：/home/csisaiproject2026/csis-platform/datainput_for_demo/seasonal_water_yield/soil_group.tif
生物物理表：/home/csisaiproject2026/csis-platform/datainput_for_demo/seasonal_water_yield/biophysical_table.csv
降雨事件表：/home/csisaiproject2026/csis-platform/datainput_for_demo/seasonal_water_yield/rain_events_table.csv
月度降水文件（1-12月）：/home/csisaiproject2026/csis-platform/datainput_for_demo/seasonal_water_yield/precip/
月度蒸散文件（1-12月）：/home/csisaiproject2026/csis-platform/datainput_for_demo/seasonal_water_yield/et0/
```

### 6.2 检查输出结果
- [ ] 工具运行时间较长（约 2-5 分钟），进度条正常更新
- [ ] 输出包含 QF/B/L 栅格文件
- [ ] 出现聚合结果 Shapefile
- [ ] 空间预览图正常显示

---

## 场景 7：工具 5 — 作物产量百分位（Crop Production Percentile）

### 7.1 发送工具调用请求
- [ ] 新建对话，输入：

```
请运行作物产量百分位分析。
土地覆盖栅格：/home/csisaiproject2026/csis-platform/datainput_for_demo/crop_percentile/lulc.tif
作物映射表：/home/csisaiproject2026/csis-platform/datainput_for_demo/crop_percentile/crop_mapping.csv
```

### 7.2 检查输出结果
- [ ] 输出包含每种作物的产量 TIF
- [ ] 出现汇总 CSV 表格
- [ ] **关键检查**：CSV 表格在聊天界面内联显示（非仅下载链接）
- [ ] 表格有列标题，数据可滚动查看

---

## 场景 8：工具 6 — 作物产量回归（Crop Production Regression）

### 8.1 发送工具调用请求
- [ ] 新建对话，输入：

```
请运行作物产量回归分析。
土地覆盖栅格：/home/csisaiproject2026/csis-platform/datainput_for_demo/crop_regression/lulc.tif
作物映射表：/home/csisaiproject2026/csis-platform/datainput_for_demo/crop_regression/crop_mapping.csv
施肥量表：/home/csisaiproject2026/csis-platform/datainput_for_demo/crop_regression/fertilization_rates.csv
```

### 8.2 检查输出结果
- [ ] 输出包含每种作物的产量 TIF
- [ ] 出现聚合结果 CSV
- [ ] AI 对施肥量与产量关系给出解读

---

## 场景 9：文件上传功能测试

### 9.1 通过聊天界面上传文件
- [ ] 新建对话
- [ ] 找到文件上传按钮（通常是回形针图标 📎 或"上传"按钮）
- [ ] 点击上传，选择本地的一个 CSV 文件
- [ ] 文件名出现在输入框旁边
- [ ] 发送消息：`这个文件里有什么内容？`
- [ ] AI 能读取文件内容并回答

### 9.2 多文件上传
- [ ] 同时选择 2-3 个文件上传
- [ ] 所有文件名都显示在界面上
- [ ] AI 能识别所有文件

---

## 场景 10：输出文件下载与预览

### 10.1 下载文件
- [ ] 在任意工具完成后，找到输出文件列表
- [ ] 点击 CSV 文件 → 浏览器下载正常
- [ ] 点击 TIF 文件 → 浏览器下载正常
- [ ] 点击 SHP 文件 → 浏览器下载正常（或下载整个压缩包）

### 10.2 空间文件预览
- [ ] TIF / SHP 文件旁边显示地图预览缩略图
- [ ] 预览图片可以正常加载（非空白）
- [ ] 确认图片展示了合理的地理空间内容

### 10.3 CSV 内联预览
- [ ] CSV 文件在聊天界面直接以表格形式展示
- [ ] 表格有列标题
- [ ] 数据行正常显示

---

## 场景 11：并发功能测试（可选）

### 11.1 两个浏览器标签同时运行
- [ ] 打开两个 Chrome 标签，都访问 http://35.184.212.119
- [ ] **注意**：两个标签会有不同的 Session ID（因为每次打开新标签是新会话）
- [ ] 标签1 发起工具5（作物百分位），标签2 发起工具6（作物回归）
- [ ] 两个任务同时运行，互不干扰
- [ ] 两个标签的结果都正常返回

---

## 场景 12：错误处理测试

### 12.1 发送无关请求
- [ ] 输入：`帮我写一首诗`
- [ ] AI 礼貌回复，说明这是生态系统分析工具，无法处理此类请求（或正常回复，视系统提示词设定）

### 12.2 文件路径错误
- [ ] 输入：`请运行网络分析，节点文件是 /不存在的路径/test.csv`
- [ ] AI 或工具返回明确的错误提示
- [ ] 界面不崩溃，可以继续使用

### 12.3 刷新页面
- [ ] 在有对话记录的情况下刷新页面（F5）
- [ ] 聊天记录保留（从 localStorage 恢复）
- [ ] Session ID 不变（从 sessionStorage 恢复）

---

## 快速检查清单（演示前10分钟速查）

```
□ 1. 页面正常打开，无空白/502错误
□ 2. 普通对话能收到 AI 回复（流式）
□ 3. 工具1 运行成功，文件可下载
□ 4. 工具2 运行成功，有 WarningCard 提示
□ 5. 工具5 运行成功，CSV 内联预览正常
□ 6. TIF 文件有空间预览图
□ 7. 文件上传后 AI 可以读取内容
□ 8. 刷新页面，聊天记录保留
□ 9. 侧边栏可以切换历史对话
□ 10. 模型选择下拉可以切换
```

---

## 常见问题 & 处理方法

| 问题 | 原因 | 处理方法 |
|------|------|---------|
| 页面空白 | GCP 实例未启动 | GCP Console 启动 csis-server |
| 502 Bad Gateway | Docker 容器未运行 | SSH 登录，`cd ~/csis-platform && docker compose up -d` |
| AI 无响应 | API Key 无效或 Gemini 限流 | 检查 .env.docker 中 GOOGLE_API_KEY |
| 工具一直不完成 | Celery Worker 异常 | `docker compose restart celery-worker-xxx` |
| 文件下载失败 | file-server 未运行 | `docker compose restart tele-fileserver` |
| 预览图不显示 | QGIS render worker 异常 | `docker compose restart celery-worker-render` |

---

## SSH 登录命令（需要时）

```powershell
# Windows PowerShell 登录 GCP 服务器
ssh -i $env:USERPROFILE\.ssh\id_ed25519_csis csisaiproject2026@35.184.212.119

# 查看所有容器状态
docker compose -f ~/csis-platform/docker-compose.yml ps

# 重启所有服务
cd ~/csis-platform && docker compose restart

# 查看后端日志
docker logs tele-backend --tail 50
```

---

## 演示截图记录

> 截图时间：2026/4/5 19:38:55  
> 服务器：http://34.172.147.13

### 场景 1：首页加载

**首页正常加载 — 显示 6 个工具快捷提示**

![首页正常加载 — 显示 6 个工具快捷提示](demo_screenshots/01_homepage.png)

### 场景 2：普通对话

**问题已发送，等待 AI 回复**

![问题已发送，等待 AI 回复](demo_screenshots/02_chat_sent.png)

**AI 流式回复 — 列出支持的工具**

![AI 流式回复 — 列出支持的工具](demo_screenshots/03_chat_response.png)

**多轮对话 — AI 说明工具1输入要求**

![多轮对话 — AI 说明工具1输入要求](demo_screenshots/04_chat_followup.png)

### 场景 3：工具1 网络社区分析

**工具1 执行中 — 进度卡片（蓝色）**

![工具1 执行中 — 进度卡片（蓝色）](demo_screenshots/05_tool1_progress.png)

**工具1 完成 — 绿色卡片 + 输出文件列表**

![工具1 完成 — 绿色卡片 + 输出文件列表](demo_screenshots/06_tool1_complete.png)

**工具1 AI 结果解读**

![工具1 AI 结果解读](demo_screenshots/07_tool1_ai_explain.png)

### 场景 4：工具2 蓝碳预处理

**工具2 蓝碳预处理执行中**

![工具2 蓝碳预处理执行中](demo_screenshots/08_tool2_progress.png)

**工具2 完成 — 含 WarningCard 提示（需编辑转换表）**

![工具2 完成 — 含 WarningCard 提示（需编辑转换表）](demo_screenshots/09_tool2_complete.png)

### 场景 5：工具5 作物产量百分位

**工具5 作物产量百分位执行中**

![工具5 作物产量百分位执行中](demo_screenshots/10_tool5_progress.png)

**工具5 完成 — CSV 表格内联显示 + 预览图**

![工具5 完成 — CSV 表格内联显示 + 预览图](demo_screenshots/11_tool5_complete.png)

### 场景 6：工具6 作物产量回归

**工具6 作物产量回归执行中**

![工具6 作物产量回归执行中](demo_screenshots/12_tool6_progress.png)

**工具6 完成 — 产量结果文件**

![工具6 完成 — 产量结果文件](demo_screenshots/13_tool6_complete.png)

### 场景 7：错误处理

**错误处理 — 路径不存在时的提示**

![错误处理 — 路径不存在时的提示](demo_screenshots/14_error_handling.png)

### 场景 8：刷新后记录保留

**刷新后聊天记录仍保留在侧边栏**

![刷新后聊天记录仍保留在侧边栏](demo_screenshots/15_after_refresh.png)

