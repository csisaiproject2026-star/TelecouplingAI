"""
01_direct_tool_test / test_tools_direct.py
Direct tool execution tests for all 42 CSIS tools.

Strategy:
  - Send EXPLICIT parameter prompts (all params spelled out) → minimises LLM ambiguity
  - InVEST tools: reference files already mounted at /data/datainput/ in the container
  - TeleBox tools (28-42): generate minimal synthetic CSV inline and upload
  - Tools without GCP data: SKIP with clear note

Run (standalone, saves JSON report):
    cd Systematic_tests/AI_GCP_test
    CSIS_BASE_URL=http://localhost python 01_direct_tool_test/test_tools_direct.py

Run (pytest subset):
    python -m pytest 01_direct_tool_test/test_tools_direct.py -v -s -k "t07 or t08"
"""
import json
import os
import sys
import time
from typing import Optional

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _utils import (
    BASE_URL, DEMO, SD, new_sid,
    upload_bytes, stream_chat,
    events_success, events_output_files, events_error_msg,
    ToolTestResult, print_results_table, save_results_json,
)

RESULTS: list = []
REPORT_PATH = os.path.join(os.path.dirname(__file__), "results_direct.json")


# ── Synthetic CSV data for TeleBox tools ──────────────────────────────────────

OLS_CSV = b"""id,gdp_bn,pop_mil,forest_pct,co2_mt
1,14000,1400,22.3,10000
2,21000,330,33.8,5000
3,4000,83,31.7,700
4,3000,67,29.2,400
5,5000,126,68.5,1200
6,2000,45,15.2,300
7,1500,33,12.8,200
8,800,20,45.6,100
9,600,18,62.1,80
10,400,10,78.3,50
"""

FAMD_CSV = b"""country,gdp,education,health,region,income_group
China,14000,0.78,0.82,Asia,High-Middle
USA,21000,0.92,0.90,Americas,High
Germany,4000,0.93,0.88,Europe,High
France,3000,0.89,0.87,Europe,High
Japan,5000,0.90,0.89,Asia,High
Brazil,1800,0.76,0.75,Americas,Upper-Middle
India,3000,0.63,0.65,Asia,Lower-Middle
Nigeria,400,0.54,0.52,Africa,Lower-Middle
Egypt,300,0.70,0.68,Africa,Lower-Middle
Mexico,1200,0.78,0.73,Americas,Upper-Middle
"""

CO2_TRANSPORT_CSV = b"""route_id,animal_count,length_km
route_001,50,120.5
route_002,30,85.2
route_003,75,200.0
route_004,20,45.8
route_005,60,310.7
"""

CBA_MAIN_CSV = b"""region_id,region_name,area_km2,landcover_type
R01,Yangtze Delta,45000,Wetland
R02,Tibetan Plateau,2000000,Grassland
R03,Pearl River Delta,55000,Urban
R04,Northeast Plain,350000,Cropland
R05,Loess Plateau,62000,Shrubland
"""

CBA_ECON_CSV = b"""region_id,COSTS,REVENUES
R01,250000,480000
R02,80000,150000
R03,600000,950000
R04,320000,520000
R05,120000,180000
"""

POP_CSV = b"""region,area_km2,population_2000,population_2010,population_2020
Shanghai,6341,16407734,23019148,24870895
Beijing,16410,13820000,19612368,21540000
Guangzhou,7434,10000000,13000000,18670000
Shenzhen,1997,7000000,10358381,17560000
Chengdu,14335,10000000,14000000,16330000
Tianjin,11760,9000000,12938224,13866009
"""

RADIAL_FLOWS_CSV = b"""flow_id,from_x,from_y,to_x,to_y,value_usd_mil,commodity
1,116.4,39.9,-87.6,41.8,500,Electronics
2,116.4,39.9,13.4,52.5,200,Machinery
3,-87.6,41.8,116.4,39.9,300,Agricultural
4,-87.6,41.8,2.3,48.9,400,Services
5,2.3,48.9,116.4,39.9,250,Automotive
6,-51.9,-14.2,116.4,39.9,180,Soybeans
"""

TRADE_CSV = b"""exporter,importer,commodity,value_usd_mil,year
CHN,USA,Electronics,150,2020
USA,CHN,Soybeans,80,2020
DEU,CHN,Machinery,90,2020
JPN,USA,Vehicles,120,2020
BRA,CHN,Iron Ore,200,2020
"""

AGENTS_CSV = b"""name,latitude,longitude,agent_type,population
Beijing,39.9042,116.4074,Sending,21540000
Shanghai,31.2304,121.4737,Sending,24870895
Los Angeles,34.0522,-118.2437,Receiving,10039107
New York,40.7128,-74.0059,Receiving,8336817
London,51.5074,-0.1278,Receiving,8982000
Sydney,-33.8688,151.2093,Receiving,5312000
"""

CAUSES_CSV = b"""cause_name,cause_type,longitude,latitude,description
Economic Growth,Socioeconomic,104.1,30.7,Trade expansion drives resource extraction
Climate Change,Environmental,90.0,25.0,Temperature rise affects agriculture
Population Growth,Demographic,77.2,28.6,Urban expansion increases land demand
Technology Diffusion,Technological,-87.6,41.8,E-commerce enables global trade flows
Policy Change,Political,-0.1,51.5,International trade agreements
"""

SYSTEMS_CSV = b"""system_name,system_type,longitude,latitude,size_km2
Yangtze River Basin,Sending,107.0,30.0,1800000
Mekong Delta,Sending,106.0,10.0,40000
Western Midwest USA,Receiving,-95.0,42.0,500000
EU Agricultural Zone,Receiving,10.0,48.0,800000
Amazon Basin,Sending,-60.0,-5.0,7000000
"""

FOOD_FAO_CSV = b"""Area,Year,Item,Value
China,2019,Undernourishment,2.5
India,2019,Undernourishment,14.0
Nigeria,2019,Undernourishment,14.8
Brazil,2019,Undernourishment,6.5
China,2020,Undernourishment,2.5
India,2020,Undernourishment,15.3
Nigeria,2020,Undernourishment,18.0
Brazil,2020,Undernourishment,7.0
China,2021,Undernourishment,2.5
India,2021,Undernourishment,16.4
Nigeria,2021,Undernourishment,19.5
Brazil,2021,Undernourishment,7.3
"""

NUTRITION_POP_CSV = b"""age_group,sex,population
0-3,male,50000000
0-3,female,48000000
3-10,male,120000000
3-10,female,115000000
10-18,male,140000000
10-18,female,135000000
18-30,male,180000000
18-30,female,175000000
30-60,male,230000000
30-60,female,240000000
60+,male,90000000
60+,female,110000000
"""

MEDIA_HTML = b"""<html><body>
<p>Telecoupling between China and the United States: A soybean trade analysis.
China's soybean imports from the USA have grown dramatically over the past two decades,
driven by increasing demand for animal feed and cooking oil. This flow connects agricultural
systems in the US Midwest with consumption systems in Chinese cities. Germany and Brazil
also play important roles in global commodity flows. Japan, India, and Australia are
increasingly involved in these international trade networks.</p>
</body></html>"""

COUNTRY_REF_CSV = b"""country,lon,lat
China,104.2,35.9
USA,-98.6,39.8
Germany,10.5,51.2
Brazil,-51.9,-14.2
Japan,138.3,36.2
India,79.0,20.6
Australia,133.8,-25.3
France,2.2,46.2
UK,-3.4,55.4
Canada,-96.8,60.1
"""


# ── Tool runner helper ─────────────────────────────────────────────────────────

def run_tool(tool_id: int, tool_name: str, prompt: str, timeout: int = 300,
             pre_upload: Optional[list] = None) -> ToolTestResult:
    """Run one tool test and return result."""
    sid = new_sid(f"t{tool_id:02d}")
    t0 = time.time()
    print(f"\n  [{tool_id:02d}] {tool_name}")
    try:
        uploaded = {}
        if pre_upload:
            uploaded = upload_bytes(sid, pre_upload)
        # Substitute uploaded paths into prompt placeholders
        resolved_prompt = prompt.format(**{k.replace(".", "_"): v
                                           for k, v in uploaded.items()})
        events = stream_chat(sid, resolved_prompt, timeout=timeout)
        duration = time.time() - t0
        if events_success(events):
            files = events_output_files(events)
            print(f"      ✓ PASS  {duration:.1f}s  {len(files)} files")
            return ToolTestResult(tool_id, tool_name, "PASS", duration, files)
        else:
            err = events_error_msg(events) or "no tool_result event"
            print(f"      ✗ FAIL  {duration:.1f}s  {err[:80]}")
            return ToolTestResult(tool_id, tool_name, "FAIL", duration, error=err)
    except Exception as e:
        duration = time.time() - t0
        print(f"      ✕ ERROR  {duration:.1f}s  {e}")
        return ToolTestResult(tool_id, tool_name, "ERROR", duration, error=str(e))


def skip_tool(tool_id: int, tool_name: str, reason: str) -> ToolTestResult:
    print(f"\n  [{tool_id:02d}] {tool_name}  ⊘ SKIP: {reason}")
    return ToolTestResult(tool_id, tool_name, "SKIP", note=reason)


# ── Tool definitions ──────────────────────────────────────────────────────────
# Each function returns a ToolTestResult.

def t01_network_analysis():
    NA = f"{DEMO}/NetworkAnalysisGrouping_input/Network Analysis Grouping"
    return run_tool(1, "Network Analysis", (
        f"Call run_network_analysis with: "
        f"nodes_table={NA}/nodes.csv, "
        f"links_table={NA}/links.csv, "
        f"shapefile_path={NA}/World_countries_2002.shp, "
        f"nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, "
        f"clustering_algorithm=walktrap. Run immediately."
    ), timeout=300)


def t02_cbc_preprocessor():
    CBC = f"{DEMO}/CoastalBLueCarbonPreprocessor_input"
    return run_tool(2, "CBC Preprocessor", (
        f"Call run_coastal_blue_carbon_preprocessor with: "
        f"landcover_snapshot_csv={CBC}/snapshots.csv, "
        f"landcover_lookup_table={CBC}/lulc_lookup.csv, "
        f"lulc_snapshot_list=[{CBC}/GBJC_2010_mean_Resample.tif,"
        f"{CBC}/GBJC_2030_mean_Resample.tif,"
        f"{CBC}/GBJC_2050_mean_Resample.tif]. Run immediately."
    ), timeout=300)


def t03_cbc_main():
    CBC = f"{DEMO}/CoastalBlueCarbon_input"
    PRE = f"{CBC}/outputs_preprocessor"
    return run_tool(3, "CBC Main", (
        f"Call run_coastal_blue_carbon with: "
        f"landcover_snapshot_csv={CBC}/snapshots.csv, "
        f"landcover_transitions_table={PRE}/transitions_sample.csv, "
        f"biophysical_table_path={PRE}/biophysical_table_sample.csv. "
        f"No economic analysis. Run immediately."
    ), timeout=600)


def t04_seasonal_water_yield():
    SWY = f"{DEMO}/SeasonalWaterYield_input"
    return run_tool(4, "Seasonal Water Yield", (
        f"Call run_seasonal_water_yield with: "
        f"aoi_path={SWY}/watershed_gura.shp, "
        f"lulc_raster_path={SWY}/land_use_gura.tif, "
        f"dem_raster_path={SWY}/DEM_gura.tif, "
        f"soil_group_path={SWY}/soil_group_gura.tif, "
        f"biophysical_table_path={SWY}/biophysical_table_gura_SWY.csv, "
        f"precip_dir={SWY}/Precipitation_monthly, "
        f"et0_dir={SWY}/ET0_monthly, "
        f"rain_events_table_path={SWY}/rain_events_gura.csv, "
        f"threshold_flow_accumulation=1000. Run immediately."
    ), timeout=600)


def t05_crop_percentile():
    CP = f"{DEMO}/CropProductionPercentile_input/sample_user_data"
    return run_tool(5, "Crop Production Percentile", (
        f"Call run_crop_production_percentile with: "
        f"landcover_raster_path={CP}/landcover.tif, "
        f"landcover_to_crop_table_path={CP}/landcover_to_crop_table.csv. "
        f"Model data path already configured. Run immediately."
    ), timeout=360)


def t06_crop_regression():
    CR = f"{DEMO}/CropProductionRegression_input/sample_user_data"
    return run_tool(6, "Crop Production Regression", (
        f"Call run_crop_production_regression with: "
        f"landcover_raster_path={CR}/landcover.tif, "
        f"landcover_to_crop_table_path={CR}/landcover_to_crop_table.csv, "
        f"fertilization_rate_table_path={CR}/crop_fertilization_rates.csv. "
        f"Model data path already configured. Run immediately."
    ), timeout=360)


def t07_carbon():
    C = f"{SD}/Carbon"
    return run_tool(7, "Carbon Storage", (
        f"Call run_carbon_storage with: "
        f"lulc_cur_path={C}/lulc_current_willamette.tif, "
        f"carbon_pools_path={C}/carbon_pools_willamette.csv. Run immediately."
    ), timeout=180)


def t08_habitat_quality():
    HQ = f"{SD}/HabitatQuality"
    return run_tool(8, "Habitat Quality", (
        f"Call run_habitat_quality with: "
        f"lulc_cur_path={HQ}/lulc_current_willamette.tif, "
        f"access_vector_path={HQ}/accessibility_willamette.shp, "
        f"sensitivity_table_path={HQ}/sensitivity_willamette.csv, "
        f"threats_table_path={HQ}/threats_willamette.csv, "
        f"half_saturation_constant=0.05. Run immediately."
    ), timeout=300)


def t09_annual_water_yield():
    AWY = f"{SD}/Annual_Water_Yield"
    return run_tool(9, "Annual Water Yield", (
        f"Call run_annual_water_yield with: "
        f"lulc_path={AWY}/land_use_gura.tif, "
        f"eto_path={AWY}/reference_ET_gura.tif, "
        f"precipitation_path={AWY}/precipitation_gura.tif, "
        f"depth_to_root_rest_layer_path={AWY}/depth_to_root_restricting_layer_gura.tif, "
        f"pawc_path={AWY}/plant_available_water_fraction_gura.tif, "
        f"biophysical_table_path={AWY}/biophysical_table_gura.csv, "
        f"watersheds_path={AWY}/watershed_gura.shp, "
        f"sub_watersheds_path={AWY}/subwatersheds_gura.shp, "
        f"seasonality_constant=15. Run immediately."
    ), timeout=300)


def t10_pollination():
    P = f"{SD}/pollination"
    return run_tool(10, "Pollination", (
        f"Call run_crop_pollination with: "
        f"landcover_raster_path={P}/landcover.tif, "
        f"landcover_biophysical_table_path={P}/landcover_biophysical_table.csv, "
        f"guild_table_path={P}/guild_table.csv, "
        f"farm_vector_path={P}/farms.shp. Run immediately."
    ), timeout=300)


def t11_delineateit():
    DI = f"{SD}/DelineateIt"
    return run_tool(11, "DelineateIt", (
        f"Call run_delineateit with: "
        f"dem_path={DI}/DEM_gura.tif, "
        f"outlet_vector_path={DI}/outlet_points.shp, "
        f"snap_points=true, flow_threshold=1000, snap_distance=50. Run immediately."
    ), timeout=300)


def t12_routedem():
    DI = f"{SD}/DelineateIt"
    return run_tool(12, "RouteDEM", (
        f"Call run_routedem with: "
        f"dem_path={DI}/DEM_gura.tif, "
        f"algorithm=D8, "
        f"calculate_flow_accumulation=true, "
        f"calculate_slope=true. Run immediately."
    ), timeout=300)


def t13_sdr():
    SDR = f"{SD}/SDR"
    return run_tool(13, "SDR", (
        f"Call run_Sediment_Delivery_Ratio_SDR with: "
        f"dem_path={SDR}/DEM_gura.tif, "
        f"erosivity_path={SDR}/erosivity_gura.tif, "
        f"erodibility_path={SDR}/erodibility_gura.tif, "
        f"lulc_path={SDR}/land_use_gura.tif, "
        f"watersheds_path={SDR}/watershed_gura.shp, "
        f"biophysical_table_path={SDR}/biophysical_table_Gura.csv, "
        f"threshold_flow_accumulation=1000, k_param=2, ic_0_param=0.5, sdr_max=0.8. Run immediately."
    ), timeout=360)


def t14_ndr():
    NDR = f"{SD}/NDR"
    return run_tool(14, "NDR", (
        f"Call run_NDR_Nutrient_Delivery_Ratio with: "
        f"dem_path={NDR}/DEM_gura.tif, "
        f"lulc_path={NDR}/land_use_gura.tif, "
        f"runoff_proxy_path={NDR}/precipitation_gura.tif, "
        f"watersheds_path={NDR}/watershed_gura.shp, "
        f"biophysical_table_path={NDR}/biophysical_table_gura.csv, "
        f"calc_p=true, calc_n=true, "
        f"threshold_flow_accumulation=1000, k_param=2, "
        f"subsurface_critical_length_n=200, subsurface_eff_n=0.8. Run immediately."
    ), timeout=360)


def t15_urban_cooling():
    return skip_tool(15, "Urban Cooling", "no urban LULC/temp data on GCP")


def t16_urban_flood():
    return skip_tool(16, "Urban Flood Risk", "no urban data on GCP")


def t17_urban_stormwater():
    return skip_tool(17, "Urban Stormwater", "no urban data on GCP")


def t18_urban_nature():
    return skip_tool(18, "Urban Nature Access", "no urban data on GCP")


def t19_urban_mental_health():
    return skip_tool(19, "Urban Mental Health", "no urban data on GCP")


def t20_scenic_quality():
    return skip_tool(20, "Scenic Quality", "no viewshed/DEM data configured on GCP")


def t21_hra():
    return skip_tool(21, "HRA", "no coastal habitat data on GCP")


def t22_wave_energy():
    return skip_tool(22, "Wave Energy", "no wave/bathymetry data on GCP")


def t23_scenario_generator():
    return skip_tool(23, "Scenario Generator", "no LULC transition data on GCP")


def t24_recreation():
    return skip_tool(24, "Recreation", "requires outbound TCP 54321 to NatCap server")


def t25_coastal_vulnerability():
    return skip_tool(25, "Coastal Vulnerability", "no coastal geospatial data on GCP")


def t26_wind_energy():
    return skip_tool(26, "Wind Energy", "no wind/grid data on GCP")


def t27_forest_carbon():
    return skip_tool(27, "Forest Carbon Edge Effects", "no forest edge data on GCP")


def t28_ols():
    sid = new_sid("t28")
    uploaded = upload_bytes(sid, [("ols_data.csv", OLS_CSV, "text/csv")])
    return run_tool(28, "OLS Regression", (
        f"Call run_ols with: "
        f"input_csv={uploaded['ols_data.csv']}, "
        f"dependent_variable=co2_mt, "
        f"independent_variables=gdp_bn,pop_mil,forest_pct. Run immediately."
    ), timeout=120)


def t29_famd():
    sid = new_sid("t29")
    uploaded = upload_bytes(sid, [("famd_data.csv", FAMD_CSV, "text/csv")])
    return run_tool(29, "FAMD", (
        f"Call run_factor_analysis_mixed_data with: "
        f"input_csv={uploaded['famd_data.csv']}, "
        f"quantitative_variables=gdp,education,health, "
        f"qualitative_variables=region,income_group, "
        f"n_components=3. Run immediately."
    ), timeout=180)


def t30_co2():
    sid = new_sid("t30")
    uploaded = upload_bytes(sid, [("co2_transport.csv", CO2_TRANSPORT_CSV, "text/csv")])
    return run_tool(30, "CO2 Emissions", (
        f"Call run_co2_emissions with: "
        f"input_csv={uploaded['co2_transport.csv']}, "
        f"capacity_per_trip=10, co2_per_km_per_trip=0.8, "
        f"animal_count_field=animal_count, length_km_field=length_km. Run immediately."
    ), timeout=120)


def t31_cba():
    sid = new_sid("t31")
    uploaded = upload_bytes(sid, [
        ("cba_main.csv", CBA_MAIN_CSV, "text/csv"),
        ("cba_econ.csv", CBA_ECON_CSV, "text/csv"),
    ])
    return run_tool(31, "Cost-Benefit Analysis", (
        f"Call run_cost_benefit_analysis with: "
        f"input_csv={uploaded['cba_main.csv']}, "
        f"economic_data_csv={uploaded['cba_econ.csv']}, "
        f"key_field=region_id. Run immediately."
    ), timeout=120)


def t32_population_density():
    sid = new_sid("t32")
    uploaded = upload_bytes(sid, [("pop_data.csv", POP_CSV, "text/csv")])
    return run_tool(32, "Population Density", (
        f"Call run_population_count_density with: "
        f"input_csv={uploaded['pop_data.csv']}, "
        f"population_field=population_2020, "
        f"area_km2_field=area_km2, "
        f"unit_id_field=region. Run immediately."
    ), timeout=120)


def t33_radial_flows():
    sid = new_sid("t33")
    uploaded = upload_bytes(sid, [("radial_flows.csv", RADIAL_FLOWS_CSV, "text/csv")])
    return run_tool(33, "Radial Flows", (
        f"Call run_draw_radial_flows with: "
        f"input_csv={uploaded['radial_flows.csv']}, "
        f"from_x_field=from_x, from_y_field=from_y, "
        f"to_x_field=to_x, to_y_field=to_y. Run immediately."
    ), timeout=120)


def t34_commodity_trade():
    sid = new_sid("t34")
    uploaded = upload_bytes(sid, [("trade.csv", TRADE_CSV, "text/csv")])
    return run_tool(34, "Commodity Trade", (
        f"Call run_commodity_trade with: "
        f"trade_csv={uploaded['trade.csv']}, "
        f"from_country_field=exporter, to_country_field=importer, "
        f"value_field=value_usd_mil. Run immediately."
    ), timeout=120)


def t35_add_agents():
    sid = new_sid("t35")
    uploaded = upload_bytes(sid, [("agents.csv", AGENTS_CSV, "text/csv")])
    return run_tool(35, "Add Agents", (
        f"Call run_add_agents_interactively with: "
        f"input_csv={uploaded['agents.csv']}, "
        f"x_field=longitude, y_field=latitude, name_field=name. Run immediately."
    ), timeout=120)


def t36_draw_agents():
    return skip_tool(36, "Draw Agents", "requires GeoJSON from Add Agents output")


def t37_add_causes():
    sid = new_sid("t37")
    uploaded = upload_bytes(sid, [("causes.csv", CAUSES_CSV, "text/csv")])
    return run_tool(37, "Add Causes", (
        f"Call run_add_causes_interactively with: "
        f"input_csv={uploaded['causes.csv']}, "
        f"x_field=longitude, y_field=latitude, description_field=description. Run immediately."
    ), timeout=120)


def t38_add_systems():
    sid = new_sid("t38")
    uploaded = upload_bytes(sid, [("systems.csv", SYSTEMS_CSV, "text/csv")])
    return run_tool(38, "Add Systems", (
        f"Call run_add_systems_interactively with: "
        f"input_csv={uploaded['systems.csv']}, "
        f"x_field=longitude, y_field=latitude, name_field=system_name. Run immediately."
    ), timeout=120)


def t39_draw_systems():
    return skip_tool(39, "Draw Systems", "requires GeoJSON from Add Systems output")


def t40_add_media_flows():
    sid = new_sid("t40")
    uploaded = upload_bytes(sid, [
        ("media.html", MEDIA_HTML, "text/html"),
        ("country_ref.csv", COUNTRY_REF_CSV, "text/csv"),
    ])
    return run_tool(40, "Add Media Flows", (
        f"Call run_add_media_flows with: "
        f"html_file={uploaded['media.html']}, "
        f"source_lon=104.2, source_lat=35.9, "
        f"country_reference_csv={uploaded['country_ref.csv']}, "
        f"source_name=China. Run immediately."
    ), timeout=180)


def t41_food_security():
    sid = new_sid("t41")
    uploaded = upload_bytes(sid, [("food_fao.csv", FOOD_FAO_CSV, "text/csv")])
    return run_tool(41, "Food Security", (
        f"Call run_food_security with: "
        f"fao_csv={uploaded['food_fao.csv']}, "
        f"countries=China,India,Nigeria,Brazil, "
        f"indicator_field=Undernourishment, "
        f"country_field=Area, year_field=Year, value_field=Value. Run immediately."
    ), timeout=120)


def t42_nutrition_metrics():
    sid = new_sid("t42")
    uploaded = upload_bytes(sid, [("population.csv", NUTRITION_POP_CSV, "text/csv")])
    return run_tool(42, "Nutrition Metrics", (
        f"Call run_nutrition_metrics with: "
        f"population_csv={uploaded['population.csv']}, "
        f"age_group_field=age_group, sex_field=sex, population_count_field=population. "
        f"Run immediately."
    ), timeout=120)


# ── All tool functions in order ───────────────────────────────────────────────

ALL_TOOLS = [
    t01_network_analysis, t02_cbc_preprocessor, t03_cbc_main,
    t04_seasonal_water_yield, t05_crop_percentile, t06_crop_regression,
    t07_carbon, t08_habitat_quality, t09_annual_water_yield,
    t10_pollination, t11_delineateit, t12_routedem, t13_sdr, t14_ndr,
    t15_urban_cooling, t16_urban_flood, t17_urban_stormwater,
    t18_urban_nature, t19_urban_mental_health, t20_scenic_quality,
    t21_hra, t22_wave_energy, t23_scenario_generator, t24_recreation,
    t25_coastal_vulnerability, t26_wind_energy, t27_forest_carbon,
    t28_ols, t29_famd, t30_co2, t31_cba, t32_population_density,
    t33_radial_flows, t34_commodity_trade, t35_add_agents, t36_draw_agents,
    t37_add_causes, t38_add_systems, t39_draw_systems, t40_add_media_flows,
    t41_food_security, t42_nutrition_metrics,
]


# ── pytest wrappers ───────────────────────────────────────────────────────────

import pytest

@pytest.mark.parametrize("fn", ALL_TOOLS, ids=[f.__name__ for f in ALL_TOOLS])
def test_tool(fn):
    result = fn()
    if result.status == "SKIP":
        pytest.skip(result.note)
    assert result.status == "PASS", f"Tool failed: {result.error}"


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools", nargs="*", type=int,
                        help="Tool IDs to run (e.g. --tools 1 7 28). Default: all")
    parser.add_argument("--skip-slow", action="store_true",
                        help="Skip tools expected to take >5 min (03 SWY, 03 CBC-Main)")
    args = parser.parse_args()

    print(f"\n{'=' * 78}")
    print(f"  Direct Tool Tests  →  {BASE_URL}")
    print(f"  {len(ALL_TOOLS)} tools total")
    print(f"{'=' * 78}")

    slow_tools = {3, 4}

    results = []
    for fn in ALL_TOOLS:
        tool_id = int(fn.__name__[1:3])
        if args.tools and tool_id not in args.tools:
            continue
        if args.skip_slow and tool_id in slow_tools:
            results.append(skip_tool(tool_id, fn.__name__, "skipped via --skip-slow"))
            continue
        results.append(fn())

    print_results_table(results, "Direct Tool Test Results")
    save_results_json(results, REPORT_PATH)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    sys.exit(0 if failed == 0 else 1)
