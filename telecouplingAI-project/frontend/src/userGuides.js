const GUIDE_FOLDERS = [
  '01_network_analysis_User_Guide',
  '02_coastal_blue_carbon_preprocessor_User_Guide',
  '03_coastal_blue_carbon_User_Guide',
  '04_seasonal_water_yield_User_Guide',
  '05_crop_production_percentile_User_Guide',
  '06_crop_production_regression_User_Guide',
  '07_carbon_storage_User_Guide',
  '08_habitat_quality_User_Guide',
  '09_annual_water_yield_User_Guide',
  '10_forest_carbon_edge_effect_User_Guide',
  '11_crop_pollination_User_Guide',
  '12_delineateit_User_Guide',
  '13_routedem_User_Guide',
  '14_sdr_User_Guide',
  '15_ndr_User_Guide',
  '16_urban_cooling_User_Guide',
  '17_urban_flood_User_Guide',
  '18_urban_stormwater_User_Guide',
  '19_urban_nature_access_User_Guide',
  '20_urban_mental_health_User_Guide',
  '21_scenic_quality_User_Guide',
  '22_hra_User_Guide',
  '23_wave_energy_User_Guide',
  '24_coastal_vulnerability_User_Guide',
  '25_wind_energy_User_Guide',
  '27_scenario_gen_proximity_User_Guide',
  '28_ols_User_Guide',
  '29_famd_User_Guide',
  '30_co2_emissions_User_Guide',
  '31_cost_benefit_analysis_User_Guide',
  '32_population_density_User_Guide',
  '33_radial_flows_User_Guide',
  '34_commodity_trade_User_Guide',
  '35_add_agents_User_Guide',
  '36_draw_agents_table_User_Guide',
  '37_add_causes_User_Guide',
  '38_add_systems_User_Guide',
  '39_draw_systems_table_User_Guide',
  '40_add_media_flows_User_Guide',
  '41_food_security_User_Guide',
  '42_nutrition_metrics_User_Guide',
  '43_spatial_moran_User_Guide',
  '44_geodetector_User_Guide',
  'Workflow_01_soybean_telecoupling_User_Guide',
  'Workflow_02_tourism_telecoupling_User_Guide',
];

const TITLE_OVERRIDES = {
  '12_delineateit_User_Guide': 'DelineateIt',
  '13_routedem_User_Guide': 'RouteDEM',
  '14_sdr_User_Guide': 'Sediment Delivery Ratio (SDR)',
  '15_ndr_User_Guide': 'Nutrient Delivery Ratio (NDR)',
  '22_hra_User_Guide': 'Habitat Risk Assessment (HRA)',
  '27_scenario_gen_proximity_User_Guide': 'Scenario Generator - Proximity-Based',
  '28_ols_User_Guide': 'Model Selection OLS',
  '29_famd_User_Guide': 'Factor Analysis Mixed Data (FAMD)',
  '30_co2_emissions_User_Guide': 'CO2 Emissions',
  '31_cost_benefit_analysis_User_Guide': 'Cost-Benefit Analysis',
  '35_add_agents_User_Guide': 'Add Agents',
  '36_draw_agents_table_User_Guide': 'Draw Agents from Table',
  '37_add_causes_User_Guide': 'Add Causes',
  '38_add_systems_User_Guide': 'Add Systems',
  '39_draw_systems_table_User_Guide': 'Draw Systems from Table',
  '40_add_media_flows_User_Guide': 'Add Media Flows',
  '43_spatial_moran_User_Guide': 'Spatial Autocorrelation Moran',
  '44_geodetector_User_Guide': 'Geographical Detector',
  'Workflow_01_soybean_telecoupling_User_Guide': 'Soybean Telecoupling Workflow',
  'Workflow_02_tourism_telecoupling_User_Guide': 'Tourism Telecoupling Workflow',
};

const DESCRIPTION_OVERRIDES = {
  '01_network_analysis_User_Guide': 'Detect network communities and calculate centrality metrics from node and link tables.',
  '02_coastal_blue_carbon_preprocessor_User_Guide': 'Prepare land-cover transition tables for coastal blue carbon modeling.',
  '03_coastal_blue_carbon_User_Guide': 'Estimate blue carbon stock, sequestration, emissions, and valuation over time.',
  '04_seasonal_water_yield_User_Guide': 'Model quickflow, baseflow, and local recharge for seasonal water planning.',
  '05_crop_production_percentile_User_Guide': 'Estimate crop production using global climate percentile yield tables.',
  '06_crop_production_regression_User_Guide': 'Model crop yield response from fertilizer inputs using regression-based production curves.',
  '07_carbon_storage_User_Guide': 'Estimate carbon storage and sequestration from land-use and carbon-pool tables.',
  '08_habitat_quality_User_Guide': 'Map habitat degradation and quality based on land cover, threats, and sensitivity tables.',
  '09_annual_water_yield_User_Guide': 'Estimate annual water yield from precipitation, evapotranspiration, soils, and watersheds.',
  '10_forest_carbon_edge_effect_User_Guide': 'Estimate forest carbon while accounting for edge effects near forest boundaries.',
  '11_crop_pollination_User_Guide': 'Assess wild pollinator supply and farm pollination service across landscapes.',
  '12_delineateit_User_Guide': 'Delineate watersheds and outlet-based drainage areas from a digital elevation model.',
  '13_routedem_User_Guide': 'Generate flow direction, flow accumulation, streams, and slope products from DEM data.',
  '14_sdr_User_Guide': 'Estimate soil erosion, sediment retention, and sediment export using the SDR model.',
  '15_ndr_User_Guide': 'Estimate nitrogen and phosphorus export and retention across watersheds.',
  '16_urban_cooling_User_Guide': 'Estimate urban heat mitigation provided by shade, evapotranspiration, and green space.',
  '17_urban_flood_User_Guide': 'Estimate runoff retention and flood-risk mitigation from urban land cover.',
  '18_urban_stormwater_User_Guide': 'Calculate stormwater retention, runoff, and recharge benefits in urban areas.',
  '19_urban_nature_access_User_Guide': 'Measure population access to urban nature and green spaces.',
  '20_urban_mental_health_User_Guide': 'Estimate mental health benefits associated with urban nature accessibility.',
  '21_scenic_quality_User_Guide': 'Map viewshed visibility and visual impact from infrastructure or scenic features.',
  '22_hra_User_Guide': 'Assess cumulative habitat risk from stressors, exposure, and consequence criteria.',
  '23_wave_energy_User_Guide': 'Estimate wave energy potential and related coastal energy production metrics.',
  '24_coastal_vulnerability_User_Guide': 'Map coastal exposure and vulnerability using shoreline, habitat, wind, and wave data.',
  '25_wind_energy_User_Guide': 'Estimate offshore wind energy potential and economic indicators.',
  '27_scenario_gen_proximity_User_Guide': 'Generate land-cover change scenarios based on proximity to focal features.',
  '28_ols_User_Guide': 'Run OLS model selection and compare candidate explanatory variables.',
  '29_famd_User_Guide': 'Reduce mixed numeric and categorical data dimensions using PCA, MCA, or FAMD.',
  '30_co2_emissions_User_Guide': 'Calculate transport-related CO2 emissions from routes, distance, and shipment attributes.',
  '31_cost_benefit_analysis_User_Guide': 'Join benefit and cost data to calculate net returns and summarize tradeoffs.',
  '32_population_density_User_Guide': 'Calculate population density and population-change indicators from spatial tables.',
  '33_radial_flows_User_Guide': 'Create radial origin-destination flow lines from coordinate and magnitude tables.',
  '34_commodity_trade_User_Guide': 'Map bilateral commodity trade flows between countries using tabular trade data.',
  '35_add_agents_User_Guide': 'Create telecoupling agent point features from a structured agent table.',
  '36_draw_agents_table_User_Guide': 'Render uploaded agent coordinates as mapped telecoupling agent features.',
  '37_add_causes_User_Guide': 'Create telecoupling cause point features from a structured cause table.',
  '38_add_systems_User_Guide': 'Create sending, receiving, and spillover system points from a systems table.',
  '39_draw_systems_table_User_Guide': 'Render uploaded system coordinates with sending, receiving, and spillover symbology.',
  '40_add_media_flows_User_Guide': 'Extract country mentions from media HTML and convert them into media flow lines.',
  '41_food_security_User_Guide': 'Analyze food security indicators and generate trends for selected countries or regions.',
  '42_nutrition_metrics_User_Guide': 'Calculate nutrition and energy-requirement indicators by age group and sex.',
  '43_spatial_moran_User_Guide': 'Calculate global and local Moran statistics to detect spatial autocorrelation.',
  '44_geodetector_User_Guide': 'Use geographical detector methods to measure factor, interaction, risk, and ecological effects.',
  'Workflow_01_soybean_telecoupling_User_Guide': 'Run a complete soybean telecoupling workflow from trade flows to ecosystem-service interpretation.',
  'Workflow_02_tourism_telecoupling_User_Guide': 'Run a complete tourism telecoupling workflow connecting flows, agents, systems, and spatial outputs.',
};

const GUIDE_FILE_OVERRIDES = {
  'Workflow_01_soybean_telecoupling_User_Guide': 'Soybean_Telecoupling_AI_Driven_User_Guide.pdf',
  'Workflow_02_tourism_telecoupling_User_Guide': 'Tourism_Telecoupling_User_Guide.pdf',
};

function encodedDownloadPath(folder, filename) {
  return `/download/user-guides/${encodeURIComponent(folder)}/${encodeURIComponent(filename)}`;
}

function safeDownloadFilename(name) {
  return name.replace(/[<>:"/\\|?*]+/g, '-');
}

function titleFromFolder(folder) {
  if (TITLE_OVERRIDES[folder]) return TITLE_OVERRIDES[folder];
  const acronyms = new Set(['co2', 'sdr', 'ndr', 'hra', 'ols', 'famd']);
  return folder
    .replace(/^\d+_/, '')
    .replace(/_User_Guide$/, '')
    .split('_')
    .map(word => acronyms.has(word.toLowerCase()) ? word.toUpperCase() : word[0].toUpperCase() + word.slice(1))
    .join(' ');
}

function typeFromFolder(folder) {
  if (folder.startsWith('Workflow_')) return 'Workflow';
  const number = Number(folder.slice(0, 2));
  return number >= 27 ? 'Telecoupling Tool' : 'InVEST Model';
}

function descriptionFor(type) {
  if (type === 'Workflow') {
    return 'Follow a complete workflow using the matching guide, prompts, sample data, and expected outputs.';
  }
  if (type === 'Telecoupling Tool') {
    return 'Use the guide and sample data to run this telecoupling toolbox item in CSIS.';
  }
  return 'Use the guide and sample data to run this InVEST model in CSIS.';
}

export const USER_GUIDES = GUIDE_FOLDERS.map(folder => {
  const type = typeFromFolder(folder);
  const title = titleFromFolder(folder);
  const sampleDataFilename = safeDownloadFilename(`${title} sample data.zip`);
  return {
    id: folder,
    folder,
    type,
    title,
    description: DESCRIPTION_OVERRIDES[folder] || descriptionFor(type),
    guideUrl: encodedDownloadPath(folder, GUIDE_FILE_OVERRIDES[folder] || 'user guide.pdf'),
    sampleDataFilename,
    sampleDataUrl: encodedDownloadPath(folder, sampleDataFilename),
  };
});
