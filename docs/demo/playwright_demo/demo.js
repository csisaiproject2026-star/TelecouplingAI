// CSIS Platform — Complete Automated Demo Script
// All tools tested with LOCAL file uploads (simulating a real user)
// Usage: node demo.js [IP]

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SERVER_IP = process.argv[2] || '34.42.83.50';
const BASE_URL   = `http://${SERVER_IP}`;
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'demo_screenshots');

// Local demo data root (user's local machine files)
const LOCAL = path.resolve(
  __dirname,
  '../../telecouplingAI-project/datainput_for_demo'
);

// All local file paths by tool
const FILES = {
  net: [
    `${LOCAL}/NetworkAnalysisGrouping_input/Network Analysis Grouping/nodes.csv`,
    `${LOCAL}/NetworkAnalysisGrouping_input/Network Analysis Grouping/links.csv`,
    `${LOCAL}/NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.shp`,
    `${LOCAL}/NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.dbf`,
    `${LOCAL}/NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.shx`,
    `${LOCAL}/NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.prj`,
  ],
  cbcPre: [
    `${LOCAL}/CoastalBLueCarbonPreprocessor_input/snapshots.csv`,
    `${LOCAL}/CoastalBLueCarbonPreprocessor_input/lulc_lookup.csv`,
    `${LOCAL}/CoastalBLueCarbonPreprocessor_input/GBJC_2010_mean_Resample.tif`,
    `${LOCAL}/CoastalBLueCarbonPreprocessor_input/GBJC_2030_mean_Resample.tif`,
    `${LOCAL}/CoastalBLueCarbonPreprocessor_input/GBJC_2050_mean_Resample.tif`,
  ],
  cbcMain: [
    `${LOCAL}/CoastalBlueCarbon_input/snapshots.csv`,
    `${LOCAL}/CoastalBlueCarbon_input/outputs_preprocessor/transitions_sample.csv`,
    `${LOCAL}/CoastalBlueCarbon_input/outputs_preprocessor/biophysical_table_sample.csv`,
    `${LOCAL}/CoastalBlueCarbon_input/GBJC_2010_mean_Resample.tif`,
    `${LOCAL}/CoastalBlueCarbon_input/GBJC_2030_mean_Resample.tif`,
    `${LOCAL}/CoastalBlueCarbon_input/GBJC_2050_mean_Resample.tif`,
  ],
  swy: [
    // AOI watershed shapefile
    `${LOCAL}/SeasonalWaterYield_input/watershed_gura.shp`,
    `${LOCAL}/SeasonalWaterYield_input/watershed_gura.dbf`,
    `${LOCAL}/SeasonalWaterYield_input/watershed_gura.shx`,
    `${LOCAL}/SeasonalWaterYield_input/watershed_gura.prj`,
    // Core rasters
    `${LOCAL}/SeasonalWaterYield_input/land_use_gura.tif`,
    `${LOCAL}/SeasonalWaterYield_input/DEM_gura.tif`,
    `${LOCAL}/SeasonalWaterYield_input/soil_group_gura.tif`,
    // Tables
    `${LOCAL}/SeasonalWaterYield_input/biophysical_table_gura_SWY.csv`,
    `${LOCAL}/SeasonalWaterYield_input/rain_events_gura.csv`,
    // 12 monthly precipitation
    ...Array.from({length:12}, (_,i) =>
      `${LOCAL}/SeasonalWaterYield_input/Precipitation_monthly/precip_gura_${i+1}.tif`),
    // 12 monthly ET0
    ...Array.from({length:12}, (_,i) =>
      `${LOCAL}/SeasonalWaterYield_input/ET0_monthly/ET0_gura_${i+1}.tif`),
  ],
  cropPct: [
    `${LOCAL}/CropProductionPercentile_input/sample_user_data/landcover.tif`,
    `${LOCAL}/CropProductionPercentile_input/sample_user_data/landcover_to_crop_table.csv`,
  ],
  cropReg: [
    `${LOCAL}/CropProductionRegression_input/sample_user_data/landcover.tif`,
    `${LOCAL}/CropProductionRegression_input/sample_user_data/landcover_to_crop_table.csv`,
    `${LOCAL}/CropProductionRegression_input/sample_user_data/crop_fertilization_rates.csv`,
  ],
};

const TOOL_TIMEOUT_MS = 12 * 60 * 1000;  // 12 min (SWY can be slow)
const STABLE_WAIT_MS  = 3000;

let screenshotIndex = 0;
let browser, page;
const results = [];

// ─────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────

function ensureDir(d) { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); }

async function shot(name, description) {
  screenshotIndex++;
  const filename = `${String(screenshotIndex).padStart(2, '0')}_${name}.png`;
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, filename), fullPage: false });
  console.log(`  📸 [${screenshotIndex}] ${description}`);
  results.push({ filename, description });
}

// Upload local files via the hidden file input
async function uploadFiles(filePaths) {
  const existing = filePaths.filter(f => fs.existsSync(f));
  if (existing.length === 0) { console.log('  ⚠️  No files found to upload'); return; }
  await page.setInputFiles('input[type="file"]', existing);
  await page.waitForTimeout(800);
  console.log(`  📂 Uploaded ${existing.length} file(s)`);
}

async function sendMessage(text) {
  const input = await page.waitForSelector('input[placeholder="Enter a prompt here"]', { timeout: 10000 });
  await input.click();
  await input.fill(text);
  await page.waitForTimeout(300);
  await input.press('Enter');
  await page.waitForTimeout(800);
}

async function waitForToolDone(ms = TOOL_TIMEOUT_MS) {
  console.log(`  ⏳ Waiting for tool (up to ${ms/60000} min)...`);
  const start = Date.now();
  while (Date.now() - start < ms) {
    if (await page.$('.bg-green-50')) {
      console.log(`  ✅ Done (${Math.round((Date.now()-start)/1000)}s)`);
      return true;
    }
    process.stdout.write('.');
    await page.waitForTimeout(3000);
  }
  console.log('\n  ⚠️  Timeout');
  return false;
}

async function waitForStable(maxMs = 90000) {
  console.log('  ⏳ Waiting for stable response...');
  let last = '', same = 0;
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    await page.waitForTimeout(STABLE_WAIT_MS);
    const cur = await page.evaluate(() => document.body.innerText);
    if (cur === last) { if (++same >= 2) break; } else { same = 0; last = cur; }
  }
  console.log('  ✅ Stable');
}

async function newChat() {
  const btn = await page.waitForSelector('button:has-text("New Chat")', { timeout: 10000 });
  await btn.click();
  await page.waitForTimeout(1000);
  console.log('  🆕 New chat');
}

// ─────────────────────────────────────────
// Main Demo
// ─────────────────────────────────────────

async function runDemo() {
  ensureDir(SCREENSHOTS_DIR);

  // Clear proxy env vars
  delete process.env.http_proxy; delete process.env.HTTP_PROXY;
  delete process.env.https_proxy; delete process.env.HTTPS_PROXY;
  process.env.no_proxy = '*'; process.env.NO_PROXY = '*';

  console.log('='.repeat(60));
  console.log(`CSIS Complete Demo  →  ${BASE_URL}`);
  console.log(`Local data: ${LOCAL}`);
  console.log('='.repeat(60));

  browser = await chromium.launch({
    headless: false,
    args: ['--start-maximized', '--no-proxy-server', '--proxy-bypass-list=*'],
  });
  page = await browser.newContext({ viewport: { width: 1440, height: 900 } })
                      .then(ctx => ctx.newPage());

  // ══════════════════════════════════════
  // SCENE 1: Homepage
  // ══════════════════════════════════════
  console.log('\n[Scene 1] Homepage');
  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1500);
  await shot('01_homepage', 'Homepage — Hi CSIS welcome screen with 6 tool shortcuts');

  // ══════════════════════════════════════
  // SCENE 2: General chat
  // ══════════════════════════════════════
  console.log('\n[Scene 2] General chat');
  await sendMessage('Hello! What analysis tools does this platform support?');
  await waitForStable();
  await shot('02_chat_tools', 'AI lists all 6 supported InVEST tools');

  await sendMessage('What input files are needed for Seasonal Water Yield?');
  await waitForStable();
  await shot('03_chat_swy_info', 'Multi-turn: AI explains SWY input requirements');

  // ══════════════════════════════════════
  // SCENE 3: Tool 1 — Network Analysis
  // ══════════════════════════════════════
  console.log('\n[Scene 3] Tool 1 — Network Analysis');
  await newChat();
  await uploadFiles(FILES.net);
  await shot('04_tool1_files_uploaded', 'Tool 1 — local files attached (nodes.csv, links.csv, shapefile)');

  await sendMessage(
    'Please run the network community analysis using the uploaded files.\n' +
    'Node ID column: CODE\n' +
    'Sender column: sender\n' +
    'Receiver column: receiver\n' +
    'Link weight column: larrivals\n' +
    'Shapefile join column: ISO_3_CODE\n' +
    'Clustering algorithm: walktrap'
  );
  await page.waitForTimeout(5000);
  await shot('05_tool1_running', 'Tool 1 — blue progress card, Running R network analysis...');

  await waitForToolDone();
  await page.waitForTimeout(2000);
  await shot('06_tool1_complete', 'Tool 1 complete — SHP, CSV and PDF output files');

  await waitForStable(60000);
  await shot('07_tool1_ai_result', 'Tool 1 — AI interprets community detection results');

  // Follow-up: render the output shapefile
  await sendMessage('Can you render the output shapefile to show the community clusters on a map?');
  await page.waitForTimeout(4000);
  await shot('07b_tool1_render', 'Follow-up: AI renders clustered SHP as spatial map preview');
  await waitForToolDone();
  await page.waitForTimeout(1500);
  await shot('07c_tool1_render_done', 'Follow-up: community cluster map displayed inline');

  // ══════════════════════════════════════
  // SCENE 4: Tool 2 — CBC Preprocessor
  // ══════════════════════════════════════
  console.log('\n[Scene 4] Tool 2 — CBC Preprocessor');
  await newChat();
  await uploadFiles(FILES.cbcPre);
  await shot('08_tool2_files_uploaded', 'Tool 2 — snapshots.csv, lulc_lookup.csv and 3 LULC TIFs attached');

  await sendMessage(
    'Please run the Coastal Blue Carbon Preprocessor using the uploaded files.\n' +
    'Land cover snapshots file: snapshots.csv\n' +
    'LULC lookup table: lulc_lookup.csv'
  );
  await page.waitForTimeout(4000);
  await shot('09_tool2_running', 'Tool 2 — CBC Preprocessor running');

  await waitForToolDone();
  await page.waitForTimeout(2000);
  await shot('10_tool2_complete', 'Tool 2 complete — transitions CSV + aligned TIFs + WarningCard');

  // ══════════════════════════════════════
  // SCENE 5: Tool 3 — CBC Main
  // ══════════════════════════════════════
  console.log('\n[Scene 5] Tool 3 — Coastal Blue Carbon Main');
  await newChat();
  await uploadFiles(FILES.cbcMain);
  await shot('11_tool3_files_uploaded', 'Tool 3 — snapshots, transitions_sample, biophysical_table + TIFs attached');

  await sendMessage(
    'Please run the Coastal Blue Carbon main model using the uploaded files.\n' +
    'Land cover snapshots file: snapshots.csv\n' +
    'Transitions table: transitions_sample.csv\n' +
    'Biophysical table: biophysical_table_sample.csv'
  );
  await page.waitForTimeout(4000);
  await shot('12_tool3_running', 'Tool 3 — Coastal Blue Carbon model running');

  await waitForToolDone();
  await page.waitForTimeout(2000);
  await shot('13_tool3_complete', 'Tool 3 complete — carbon stock, sequestration TIF outputs');

  await waitForStable(60000);
  await shot('14_tool3_ai_result', 'Tool 3 — AI explains carbon stock and sequestration results');

  // ══════════════════════════════════════
  // SCENE 6: Tool 4 — Seasonal Water Yield
  // ══════════════════════════════════════
  console.log('\n[Scene 6] Tool 4 — Seasonal Water Yield (30 files)');
  await newChat();
  await uploadFiles(FILES.swy);
  await shot('15_tool4_files_uploaded', 'Tool 4 — 30 files uploaded (watershed SHP, LULC, DEM, soil, biophysical, 12x precip, 12x ET0)');

  await sendMessage(
    'Please run the Seasonal Water Yield model using all the uploaded files.\n' +
    'AOI watershed shapefile: watershed_gura.shp\n' +
    'Land use raster: land_use_gura.tif\n' +
    'DEM raster: DEM_gura.tif\n' +
    'Soil group raster: soil_group_gura.tif\n' +
    'Biophysical table: biophysical_table_gura_SWY.csv\n' +
    'Rain events table: rain_events_gura.csv\n' +
    'Monthly precipitation files: precip_gura_1.tif through precip_gura_12.tif\n' +
    'Monthly ET0 files: ET0_gura_1.tif through ET0_gura_12.tif\n' +
    'Threshold flow accumulation: 1000'
  );
  await page.waitForTimeout(5000);
  await shot('16_tool4_running', 'Tool 4 — Seasonal Water Yield running (largest tool, ~5 min)');

  await waitForToolDone(12 * 60 * 1000);
  await page.waitForTimeout(2000);
  await shot('17_tool4_complete', 'Tool 4 complete — QF, B, L rasters + aggregated results shapefile');

  await waitForStable(60000);
  await shot('18_tool4_ai_result', 'Tool 4 — AI interprets quickflow, baseflow and recharge results');

  // Follow-up: ask about the quickflow raster
  await sendMessage('Please render the quickflow (QF) output raster so I can see the spatial distribution.');
  await page.waitForTimeout(4000);
  await shot('18b_tool4_render', 'Follow-up: render_spatial_file called for QF raster');
  await waitForToolDone();
  await page.waitForTimeout(1500);
  await shot('18c_tool4_render_done', 'Follow-up: quickflow spatial map displayed inline');

  // ══════════════════════════════════════
  // SCENE 7: Tool 5 — Crop Percentile
  // ══════════════════════════════════════
  console.log('\n[Scene 7] Tool 5 — Crop Production Percentile');
  await newChat();
  await uploadFiles(FILES.cropPct);
  await shot('19_tool5_files_uploaded', 'Tool 5 — landcover.tif and landcover_to_crop_table.csv attached');

  await sendMessage(
    'Please run the Crop Production Percentile analysis using the uploaded files.\n' +
    'Land cover raster: landcover.tif\n' +
    'Crop mapping table: landcover_to_crop_table.csv'
  );
  await page.waitForTimeout(4000);
  await shot('20_tool5_running', 'Tool 5 — Crop Percentile running');

  await waitForToolDone();
  await page.waitForTimeout(2000);
  await shot('21_tool5_complete', 'Tool 5 complete — per-crop yield TIFs + result_table.csv');

  await waitForStable(60000);
  await shot('22_tool5_ai_result', 'Tool 5 — AI explains yield estimates across 172 crops');

  // ══════════════════════════════════════
  // SCENE 8: Follow-up questions after Tool 5
  // ══════════════════════════════════════
  console.log('\n[Scene 8] Follow-up: render + interpretation questions');

  // 8a: Ask AI to render output spatially
  await sendMessage(
    'Can you render and visualize the wheat yield 25th percentile output raster from the previous analysis?'
  );
  await page.waitForTimeout(4000);
  await shot('23_render_running', 'Follow-up: render_spatial_file called — QGIS rendering wheat yield TIF');
  await waitForToolDone();
  await page.waitForTimeout(2000);
  await shot('24_render_complete', 'Follow-up: spatial map preview rendered and displayed inline in chat');

  // 8b: Ask interpretive question about results
  await sendMessage(
    'Which crop has the highest observed production in this area? And what does the 25th vs 75th percentile difference tell us?'
  );
  await waitForStable(60000);
  await shot('25_followup_interpret', 'Follow-up: AI interprets crop yield percentile differences without re-running tool');

  // 8c: Ask about next steps / recommendations
  await sendMessage(
    'Based on these crop production results, what would you recommend as the next analysis step?'
  );
  await waitForStable(60000);
  await shot('26_followup_recommend', 'Follow-up: AI recommends next analysis steps based on context');

  // ══════════════════════════════════════
  // SCENE 9: Tool 6 — Crop Regression
  // ══════════════════════════════════════
  console.log('\n[Scene 9] Tool 6 — Crop Production Regression');
  await newChat();
  await uploadFiles(FILES.cropReg);
  await shot('25_tool6_files_uploaded', 'Tool 6 — landcover.tif, crop_mapping and fertilization_rates.csv attached');

  await sendMessage(
    'Please run the Crop Production Regression analysis using the uploaded files.\n' +
    'Land cover raster: landcover.tif\n' +
    'Crop mapping table: landcover_to_crop_table.csv\n' +
    'Fertilization rates table: crop_fertilization_rates.csv'
  );
  await page.waitForTimeout(4000);
  await shot('26_tool6_running', 'Tool 6 — Crop Regression running');

  await waitForToolDone();
  await page.waitForTimeout(2000);
  await shot('27_tool6_complete', 'Tool 6 complete — regression production TIFs + result CSV');

  await waitForStable(60000);
  await shot('28_tool6_ai_result', 'Tool 6 — AI explains NPK fertilizer rate vs yield relationship');

  // ══════════════════════════════════════
  // SCENE 10: Error handling
  // ══════════════════════════════════════
  console.log('\n[Scene 10] Error handling');
  await newChat();
  await sendMessage(
    'Please run network analysis. ' +
    'Nodes file: /nonexistent/nodes.csv, links: /fake/links.csv, shapefile: /fake/regions.shp'
  );
  await waitForStable(60000);
  await shot('29_error_handling', 'Error handling — clear error when file path does not exist');

  // ══════════════════════════════════════
  // SCENE 11: Refresh — history preserved
  // ══════════════════════════════════════
  console.log('\n[Scene 11] Page refresh');
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await shot('30_after_refresh', 'Page refresh — all 9 chat sessions preserved in sidebar');

  // ══════════════════════════════════════
  // SCENE 12: Responsive layout
  // ══════════════════════════════════════
  console.log('\n[Scene 12] Responsive layout test');

  // Mobile (375×812 — iPhone SE)
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(1000);
  await shot('31_responsive_mobile', 'Responsive: mobile 375px — layout adapts to narrow screen');

  // Tablet (768×1024 — iPad)
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.waitForTimeout(1000);
  await shot('32_responsive_tablet', 'Responsive: tablet 768px — sidebar and chat panel stack correctly');

  // Desktop (1440×900)
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(1000);
  await shot('33_responsive_desktop', 'Responsive: desktop 1440px — full two-column layout restored');

  console.log('\n' + '='.repeat(60));
  console.log(`✅ Demo complete! ${screenshotIndex} screenshots captured.`);
  console.log('='.repeat(60));
  await page.waitForTimeout(3000);
  await browser.close();
}

// ─────────────────────────────────────────
// Append screenshots to markdown doc
// ─────────────────────────────────────────

function appendToDoc() {
  const docPath = path.join(__dirname, '..', 'CSIS_Demo_Walkthrough.md');
  const timestamp = new Date().toLocaleString('en-US');

  let md = `\n---\n\n## Demo Screenshots\n\n> Captured: ${timestamp}  \n> Server: ${BASE_URL}  \n> All 6 tools + render tested with **local file uploads**\n\n`;

  for (const r of results) {
    md += `**${r.description}**\n\n![${r.description}](demo_screenshots/${r.filename})\n\n---\n\n`;
  }

  let existing = fs.readFileSync(docPath, 'utf-8');
  const cut = existing.indexOf('\n---\n\n## Demo Screenshots');
  if (cut !== -1) existing = existing.slice(0, cut);
  fs.writeFileSync(docPath, existing + md, 'utf-8');
  console.log(`\n✅ Screenshots written to: CSIS_Demo_Walkthrough.md`);
}

runDemo()
  .then(() => appendToDoc())
  .catch(err => {
    console.error('\n❌ Demo failed:', err.message);
    if (results.length > 0) appendToDoc();
    if (browser) browser.close();
    process.exit(1);
  });
