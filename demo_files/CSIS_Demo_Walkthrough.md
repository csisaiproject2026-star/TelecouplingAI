# CSIS Telecoupling AI Platform — User Demo Walkthrough

> Generated: 2026-04-05  
> Server: http://34.172.147.13  
> Note: Start the GCP instance `csis-server` in GCP Console before opening the URL.

---

## Prerequisites

- [ ] GCP Console → Compute Engine → csis-server → click **Start**
- [ ] Wait ~30 seconds, open **Chrome**
- [ ] Navigate to: **http://34.172.147.13**
- [ ] Confirm page loads (not blank, not 502 error)
- [ ] Demo data is already on the server at `/data/datainput/` — no upload needed

---

## Scene 1: Basic Page Check

### 1.1 Homepage Load
- [ ] Page displays the chat interface with a left sidebar
- [ ] Main area shows welcome screen with **6 tool shortcut cards**:
  - Network Analysis, CBC Preprocessor, Coastal Blue Carbon
  - Seasonal Water Yield, Crop Percentile, Crop Regression
- [ ] **+ New Chat** button visible in top-left

### 1.2 New Chat
- [ ] Click **+ New Chat**
- [ ] Right panel clears to blank input

### 1.3 Model Selector
- [ ] Find the model dropdown (top bar)
- [ ] Options available: `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`
- [ ] Default: `gemini-2.5-flash`

### 1.4 Sidebar History
- [ ] Sidebar can be collapsed/expanded
- [ ] Previous conversations appear in sidebar list
- [ ] Clicking a history item switches to that chat

---

## Scene 2: General Conversation (No Tool Call)

### 2.1 Ask about platform capabilities
- [ ] Type in the input box: `Hello! What analysis tools does this platform support?`
- [ ] Press **Enter** or click send
- [ ] Confirm AI replies with **streaming text** (characters appear progressively)
- [ ] Response mentions all 6 InVEST tool names

### 2.2 Multi-turn conversation
- [ ] Follow up: `What input files are required for the Network Analysis tool?`
- [ ] AI gives a detailed explanation of required files
- [ ] AI remembers context from previous message

---

## Scene 3: Tool 1 — Network Analysis Grouping

### 3.1 Input data
Demo data path (inside container):
```
/data/datainput/NetworkAnalysisGrouping_input/Network Analysis Grouping/
  ├── nodes.csv          (columns: CODE, larrivals.sender, larrivals.receiver)
  ├── links.csv          (columns: sender, receiver, larrivals)
  └── World_countries_2002.shp  (join column: ISO_3_CODE)
```

### 3.2 Send tool request
- [ ] Click **+ New Chat**
- [ ] Paste and send the following:

```
Please run the network community analysis.
Nodes file: /data/datainput/NetworkAnalysisGrouping_input/Network Analysis Grouping/nodes.csv
Links file: /data/datainput/NetworkAnalysisGrouping_input/Network Analysis Grouping/links.csv
Shapefile: /data/datainput/NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.shp
Node ID column: CODE
Sender column: sender
Receiver column: receiver
Link weight column: larrivals
Shapefile join column: ISO_3_CODE
Clustering algorithm: walktrap
```

### 3.3 Check execution
- [ ] Blue **ToolStatusCard** appears (⚙️ running...)
- [ ] Progress percentage updates in real time (e.g. 20% → 100%)
- [ ] Card turns green ✅ when complete

### 3.4 Check outputs
- [ ] Output file list appears, including:
  - [ ] `output_*.shp` (clustered Shapefile + `.dbf`, `.prj`, `.shx`)
  - [ ] `network_stats_*.csv` (network statistics)
  - [ ] `network_plot_*.pdf` (visualization)
- [ ] Click any file — download works correctly
- [ ] AI provides written interpretation of the clustering results

---

## Scene 4: Tool 2 — Coastal Blue Carbon Preprocessor

### 4.1 Send tool request
- [ ] Click **+ New Chat**, send:

```
Please run the Coastal Blue Carbon Preprocessor.
Land cover snapshots file: /data/datainput/CoastalBLueCarbonPreprocessor_input/snapshots.csv
LULC lookup table: /data/datainput/CoastalBLueCarbonPreprocessor_input/lulc_lookup.csv
```

### 4.2 Check outputs
- [ ] Tool completes successfully
- [ ] Output files include:
  - [ ] `carbon_pool_transition_template.csv` (transitions table — needs manual editing)
  - [ ] `aligned_lulc_*.tif` files
- [ ] **⚠️ Key check**: A **WarningCard** appears advising user to manually edit the transitions CSV before running Tool 3
- [ ] AI also mentions this requirement in its explanation

---

## Scene 5: Tool 3 — Coastal Blue Carbon (Main Model)

### 5.1 Send tool request
- [ ] New Chat, send:

```
Please run the Coastal Blue Carbon main model.
Land cover snapshots: /data/datainput/CoastalBlueCarbon_input/GBJC_2010_mean_Resample.tif
Transitions table: /data/datainput/CoastalBlueCarbon_input/outputs_preprocessor/biophysical_table_sample.csv
Biophysical table: /data/datainput/CoastalBlueCarbon_input/outputs_preprocessor/biophysical_table_template.csv
```

### 5.2 Check outputs
- [ ] Output includes carbon stock / accumulation / emissions TIF files
- [ ] Spatial preview PNG displayed inline in chat
- [ ] AI interprets the carbon stock results

---

## Scene 6: Tool 5 — Crop Production Percentile

### 6.1 Send tool request
- [ ] New Chat, send:

```
Please run the Crop Production Percentile analysis.
Land cover raster: /data/datainput/CropProductionPercentile_input/sample_user_data/landcover.tif
Crop mapping table: /data/datainput/CropProductionPercentile_input/sample_user_data/landcover_to_crop_table.csv
```

### 6.2 Check outputs
- [ ] Output includes per-crop yield TIF files (wheat, barley, soybean, etc.)
- [ ] `result_table.csv` listed as output
- [ ] **Key check**: CSV file displayed as an **inline table** in the chat (not just a download link)
- [ ] AI explains yield estimates

---

## Scene 7: Tool 6 — Crop Production Regression

### 7.1 Send tool request
- [ ] New Chat, send:

```
Please run the Crop Production Regression analysis.
Land cover raster: /data/datainput/CropProductionRegression_input/sample_user_data/landcover.tif
Crop mapping table: /data/datainput/CropProductionRegression_input/sample_user_data/landcover_to_crop_table.csv
Fertilization rates table: /data/datainput/CropProductionRegression_input/sample_user_data/crop_fertilization_rates.csv
```

### 7.2 Check outputs
- [ ] Output includes per-crop regression production TIF files
- [ ] Aggregate results CSV listed
- [ ] AI explains the relationship between fertilizer rates and estimated yields

---

## Scene 8: File Download & Preview

### 8.1 Download files
- [ ] After any tool completes, find the output file list
- [ ] Click a **CSV file** → browser downloads correctly
- [ ] Click a **TIF file** → browser downloads correctly
- [ ] Click a **SHP file** → browser downloads correctly

### 8.2 Spatial file preview
- [ ] TIF / SHP files show a **map preview thumbnail** in chat
- [ ] Preview image loads correctly (not broken icon)
- [ ] Image shows recognizable geographic content

### 8.3 CSV inline preview
- [ ] CSV files display as an **inline table** in the chat
- [ ] Table has column headers
- [ ] Data rows visible and scrollable

---

## Scene 9: Error Handling

### 9.1 Non-existent file path
- [ ] New Chat, send:

```
Please run network analysis. Nodes file: /nonexistent/path/test.csv, links file: /fake/links.csv, shapefile: /fake/regions.shp
```
- [ ] System returns a clear error message (file not found)
- [ ] UI does not crash — can continue using the platform

### 9.2 Unrelated request
- [ ] Send: `Write me a poem about the ocean`
- [ ] AI responds politely, stays in context of ecosystem analysis

---

## Scene 10: Page Refresh — Chat History Preserved

- [ ] While chats exist in sidebar, press **F5** to refresh
- [ ] After reload, chat history **still visible** in sidebar (restored from localStorage)
- [ ] Session ID unchanged (restored from sessionStorage)
- [ ] Can click previous chats to view them

---

## Quick 10-Minute Checklist

```
□ 1. Page loads without blank screen or 502 error
□ 2. General chat receives streaming AI response
□ 3. Tool 1 (Network Analysis) runs successfully — files downloadable
□ 4. Tool 2 (CBC Preprocessor) runs — WarningCard displayed
□ 5. Tool 5 (Crop Percentile) runs — CSV inline table visible
□ 6. Tool 6 (Crop Regression) runs — AI yield explanation provided
□ 7. TIF files show spatial preview image
□ 8. File upload works — AI reads uploaded content
□ 9. Page refresh preserves chat history
□ 10. Model dropdown switches between Gemini versions
```

---

## Common Issues & Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| Blank page | GCP instance not running | GCP Console → Start `csis-server` |
| 502 Bad Gateway | Docker containers not started | SSH in, `cd ~/csis-platform && docker compose up -d` |
| AI not responding | Invalid API key or Gemini rate limit | Check `GOOGLE_API_KEY` in `.env.docker` |
| Tool never completes | Celery worker error | `docker compose restart tele-celery-<toolname>` |
| File download fails | File server container down | `docker compose restart tele-fileserver` |
| Preview image missing | QGIS render worker down | `docker compose restart tele-celery-render` |

---

## SSH Login (if needed)

```powershell
# Connect to GCP server
ssh -i $env:USERPROFILE\.ssh\id_ed25519_csis csisaiproject2026@34.172.147.13

# Check all container status
docker compose -f ~/csis-platform/docker-compose.yml ps

# Restart all services
cd ~/csis-platform && docker compose restart

# View backend logs
docker logs tele-backend --tail 50
```

---

## Demo Screenshots

> Captured: 4/6/2026, 6:33:25 PM  
> Server: http://34.42.83.50  
> All 6 tools + render tested with **local file uploads**

**Homepage — Hi CSIS welcome screen with 6 tool shortcuts**

![Homepage — Hi CSIS welcome screen with 6 tool shortcuts](demo_screenshots/01_01_homepage.png)

---

**AI lists all 6 supported InVEST tools**

![AI lists all 6 supported InVEST tools](demo_screenshots/02_02_chat_tools.png)

---

**Multi-turn: AI explains SWY input requirements**

![Multi-turn: AI explains SWY input requirements](demo_screenshots/03_03_chat_swy_info.png)

---

**Tool 1 — local files attached (nodes.csv, links.csv, shapefile)**

![Tool 1 — local files attached (nodes.csv, links.csv, shapefile)](demo_screenshots/04_04_tool1_files_uploaded.png)

---

**Tool 1 — blue progress card, Running R network analysis...**

![Tool 1 — blue progress card, Running R network analysis...](demo_screenshots/05_05_tool1_running.png)

---

**Tool 1 complete — SHP, CSV and PDF output files**

![Tool 1 complete — SHP, CSV and PDF output files](demo_screenshots/06_06_tool1_complete.png)

---

**Tool 1 — AI interprets community detection results**

![Tool 1 — AI interprets community detection results](demo_screenshots/07_07_tool1_ai_result.png)

---

**Follow-up: AI renders clustered SHP as spatial map preview**

![Follow-up: AI renders clustered SHP as spatial map preview](demo_screenshots/08_07b_tool1_render.png)

---

**Follow-up: community cluster map displayed inline**

![Follow-up: community cluster map displayed inline](demo_screenshots/09_07c_tool1_render_done.png)

---

**Tool 2 — snapshots.csv, lulc_lookup.csv and 3 LULC TIFs attached**

![Tool 2 — snapshots.csv, lulc_lookup.csv and 3 LULC TIFs attached](demo_screenshots/10_08_tool2_files_uploaded.png)

---

**Tool 2 — CBC Preprocessor running**

![Tool 2 — CBC Preprocessor running](demo_screenshots/11_09_tool2_running.png)

---

**Tool 2 complete — transitions CSV + aligned TIFs + WarningCard**

![Tool 2 complete — transitions CSV + aligned TIFs + WarningCard](demo_screenshots/12_10_tool2_complete.png)

---

**Tool 3 — snapshots, transitions_sample, biophysical_table + TIFs attached**

![Tool 3 — snapshots, transitions_sample, biophysical_table + TIFs attached](demo_screenshots/13_11_tool3_files_uploaded.png)

---

**Tool 3 — Coastal Blue Carbon model running**

![Tool 3 — Coastal Blue Carbon model running](demo_screenshots/14_12_tool3_running.png)

---

**Tool 3 complete — carbon stock, sequestration TIF outputs**

![Tool 3 complete — carbon stock, sequestration TIF outputs](demo_screenshots/15_13_tool3_complete.png)

---

**Tool 3 — AI explains carbon stock and sequestration results**

![Tool 3 — AI explains carbon stock and sequestration results](demo_screenshots/16_14_tool3_ai_result.png)

---

**Tool 4 — 30 files uploaded (watershed SHP, LULC, DEM, soil, biophysical, 12x precip, 12x ET0)**

![Tool 4 — 30 files uploaded (watershed SHP, LULC, DEM, soil, biophysical, 12x precip, 12x ET0)](demo_screenshots/17_15_tool4_files_uploaded.png)

---

**Tool 4 — Seasonal Water Yield running (largest tool, ~5 min)**

![Tool 4 — Seasonal Water Yield running (largest tool, ~5 min)](demo_screenshots/18_16_tool4_running.png)

---

**Tool 4 complete — QF, B, L rasters + aggregated results shapefile**

![Tool 4 complete — QF, B, L rasters + aggregated results shapefile](demo_screenshots/19_17_tool4_complete.png)

---

**Tool 4 — AI interprets quickflow, baseflow and recharge results**

![Tool 4 — AI interprets quickflow, baseflow and recharge results](demo_screenshots/20_18_tool4_ai_result.png)

---

**Follow-up: render_spatial_file called for QF raster**

![Follow-up: render_spatial_file called for QF raster](demo_screenshots/21_18b_tool4_render.png)

---

**Follow-up: quickflow spatial map displayed inline**

![Follow-up: quickflow spatial map displayed inline](demo_screenshots/22_18c_tool4_render_done.png)

---

**Tool 5 — landcover.tif and landcover_to_crop_table.csv attached**

![Tool 5 — landcover.tif and landcover_to_crop_table.csv attached](demo_screenshots/23_19_tool5_files_uploaded.png)

---

**Tool 5 — Crop Percentile running**

![Tool 5 — Crop Percentile running](demo_screenshots/24_20_tool5_running.png)

---

**Tool 5 complete — per-crop yield TIFs + result_table.csv**

![Tool 5 complete — per-crop yield TIFs + result_table.csv](demo_screenshots/25_21_tool5_complete.png)

---

**Tool 5 — AI explains yield estimates across 172 crops**

![Tool 5 — AI explains yield estimates across 172 crops](demo_screenshots/26_22_tool5_ai_result.png)

---

**Follow-up: render_spatial_file called — QGIS rendering wheat yield TIF**

![Follow-up: render_spatial_file called — QGIS rendering wheat yield TIF](demo_screenshots/27_23_render_running.png)

---

**Follow-up: spatial map preview rendered and displayed inline in chat**

![Follow-up: spatial map preview rendered and displayed inline in chat](demo_screenshots/28_24_render_complete.png)

---

**Follow-up: AI interprets crop yield percentile differences without re-running tool**

![Follow-up: AI interprets crop yield percentile differences without re-running tool](demo_screenshots/29_25_followup_interpret.png)

---

**Follow-up: AI recommends next analysis steps based on context**

![Follow-up: AI recommends next analysis steps based on context](demo_screenshots/30_26_followup_recommend.png)

---

**Tool 6 — landcover.tif, crop_mapping and fertilization_rates.csv attached**

![Tool 6 — landcover.tif, crop_mapping and fertilization_rates.csv attached](demo_screenshots/31_25_tool6_files_uploaded.png)

---

**Tool 6 — Crop Regression running**

![Tool 6 — Crop Regression running](demo_screenshots/32_26_tool6_running.png)

---

**Tool 6 complete — regression production TIFs + result CSV**

![Tool 6 complete — regression production TIFs + result CSV](demo_screenshots/33_27_tool6_complete.png)

---

**Tool 6 — AI explains NPK fertilizer rate vs yield relationship**

![Tool 6 — AI explains NPK fertilizer rate vs yield relationship](demo_screenshots/34_28_tool6_ai_result.png)

---

**Error handling — clear error when file path does not exist**

![Error handling — clear error when file path does not exist](demo_screenshots/35_29_error_handling.png)

---

**Page refresh — all 9 chat sessions preserved in sidebar**

![Page refresh — all 9 chat sessions preserved in sidebar](demo_screenshots/36_30_after_refresh.png)

---

**Responsive: mobile 375px — layout adapts to narrow screen**

![Responsive: mobile 375px — layout adapts to narrow screen](demo_screenshots/37_31_responsive_mobile.png)

---

**Responsive: tablet 768px — sidebar and chat panel stack correctly**

![Responsive: tablet 768px — sidebar and chat panel stack correctly](demo_screenshots/38_32_responsive_tablet.png)

---

**Responsive: desktop 1440px — full two-column layout restored**

![Responsive: desktop 1440px — full two-column layout restored](demo_screenshots/39_33_responsive_desktop.png)

---

