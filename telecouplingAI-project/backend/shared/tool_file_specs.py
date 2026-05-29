"""Per-tool file input specs for the type-aware pre-flight check (Step 2).

Each entry maps a tool function name -> list of (param_key, required, kind),
where kind is 'raster' | 'vector' | 'table'. agent.py looks this up before
dispatching and calls shared.utils.validate_input_files(), so a wrong file type
(e.g. a CSV dropped into a raster slot) is caught with a friendly message
instead of a crash deep inside the model.

Only file params are listed. Directory params (e.g. precip_dir, et0_dir,
model_data_path) and scalar params are intentionally omitted.
Coverage is incremental — tools not listed here still get the generic
existence check (validate_file_params_exist) + validate_required.
"""

R, V, T, H = "raster", "vector", "table", "html"

TOOL_FILE_SPECS: dict[str, list[tuple]] = {
    "run_habitat_quality": [
        ("lulc_cur_path", True, R),
        ("threats_table_path", True, T),
        ("sensitivity_table_path", True, T),
        ("lulc_fut_path", False, R),
        ("lulc_bas_path", False, R),
        ("access_vector_path", False, V),
    ],
    "run_carbon_storage": [
        ("lulc_cur_path", True, R),
        ("carbon_pools_path", True, T),
        ("lulc_fut_path", False, R),
        ("lulc_redd_path", False, R),
    ],
    "run_annual_water_yield": [
        ("lulc_path", True, R),
        ("depth_to_root_rest_layer_path", True, R),
        ("precipitation_path", True, R),
        ("pawc_path", True, R),
        ("eto_path", True, R),
        ("watersheds_path", True, V),
        ("biophysical_table_path", True, T),
        ("sub_watersheds_path", False, V),
        ("demand_table_path", False, T),
        ("valuation_table_path", False, T),
    ],
    "run_Sediment_Delivery_Ratio_SDR": [
        ("dem_path", True, R),
        ("erosivity_path", True, R),
        ("erodibility_path", True, R),
        ("lulc_path", True, R),
        ("watersheds_path", True, V),
        ("biophysical_table_path", True, T),
        ("drainage_path", False, R),
    ],
    "run_ndr": [
        ("dem_path", True, R),
        ("lulc_path", True, R),
        ("runoff_proxy_path", True, R),
        ("watersheds_path", True, V),
        ("biophysical_table_path", True, T),
    ],
    "run_seasonal_water_yield": [
        ("aoi_path", True, V),
        ("lulc_raster_path", True, R),
        ("dem_raster_path", True, R),
        ("soil_group_path", True, R),
        ("biophysical_table_path", True, T),
        ("rain_events_table_path", True, T),
    ],
    "run_forest_carbon_edge_effect": [
        ("lulc_raster_path", True, R),
        ("biophysical_table_path", True, T),
        ("tropical_forest_edge_carbon_model_vector_path", True, V),
        ("aoi_vector_path", False, V),
    ],
    "run_crop_pollination": [
        ("landcover_raster_path", True, R),
        ("guild_table_path", True, T),
        ("landcover_biophysical_table_path", True, T),
        ("farm_vector_path", False, V),
    ],
    "run_urban_cooling": [
        ("lulc_raster_path", True, R),
        ("ref_eto_raster_path", True, R),
        ("aoi_vector_path", True, V),
        ("biophysical_table_path", True, T),
        ("building_vector_path", False, V),
        ("energy_consumption_table_path", False, T),
    ],
    "run_urban_flood_risk_mitigation": [
        ("aoi_watersheds_path", True, V),
        ("lulc_path", True, R),
        ("soils_hydrological_group_raster_path", True, R),
        ("curve_number_table_path", True, T),
        ("built_infrastructure_vector_path", False, V),
        ("infrastructure_damage_loss_table_path", False, T),
    ],
    "run_urban_nature_access": [
        ("lulc_raster_path", True, R),
        ("lulc_attribute_table", True, T),
        ("population_raster_path", True, R),
        ("admin_boundaries_vector_path", True, V),
        ("population_group_radii_table", False, T),
    ],
    "run_crop_production_percentile": [
        ("landcover_raster_path", True, R),
        ("landcover_to_crop_table_path", True, T),
        ("aggregate_polygon_path", False, V),
    ],
    "run_network_analysis_grouping": [
        ("nodes_table", True, T),
        ("links_table", True, T),
        ("shapefile_path", True, V),
    ],
    "run_crop_production_regression": [
        ("landcover_raster_path", True, R),
        ("landcover_to_crop_table_path", True, T),
        ("fertilization_rate_table_path", True, T),
        ("aggregate_polygon_path", False, V),
    ],
    "run_delineateit": [
        ("dem_path", True, R),
        ("outlet_vector_path", False, V),
    ],
    "run_routedem": [
        ("dem_path", True, R),
    ],
    "run_urban_stormwater_retention": [
        ("lulc_path", True, R),
        ("soil_group_path", True, R),
        ("precipitation_path", True, R),
        ("biophysical_table", True, T),
        ("aggregate_areas_path", False, V),
        ("road_centerlines_path", False, V),
    ],
    "run_urban_mental_health": [
        ("lulc_raster_path", True, R),
        ("lulc_attribute_table", True, T),
        ("population_raster_path", True, R),
        ("admin_boundaries_vector_path", True, V),
        ("population_group_radii_table", False, T),
    ],
    "run_scenario_gen_proximity": [
        ("base_lulc_path", True, R),
        ("aoi_path", False, V),
    ],
    "run_scenic_quality": [
        ("aoi_vector_path", True, V),
        ("structure_vector_path", True, V),
        ("dem_path", True, R),
    ],
    "run_coastal_vulnerability": [
        ("aoi_vector_path", True, V),
        ("bathymetry_raster_path", True, R),
        ("dem_path", True, R),
        ("geomorphology_vector_path", True, V),
        ("landmass_vector_path", True, V),
        ("wwiii_vector_path", True, V),
        ("habitat_table_path", False, T),
        ("shelf_contour_vector_path", False, V),
        ("slr_vector_path", False, V),
        ("population_raster_path", False, R),
    ],
    "run_coastal_blue_carbon_preprocessor": [
        ("landcover_snapshot_csv", True, T),
        ("landcover_lookup_table", True, T),
    ],
    "run_coastal_blue_carbon": [
        ("landcover_snapshot_csv", True, T),
        ("landcover_transitions_table", True, T),
        ("biophysical_table_path", True, T),
        ("price_table_path", False, T),
    ],
    "run_habitat_risk_assessment": [
        ("info_table_path", True, T),
        ("criteria_table_path", True, T),
        ("aoi_vector_path", True, V),
    ],
    "run_wave_energy_production": [
        ("machine_perf_path", True, T),
        ("machine_param_path", True, T),
    ],
    "run_offshore_wind_energy": [
        ("aoi_vector_path", True, V),
        ("global_wind_parameters_path", True, T),
        ("turbine_parameters_path", True, T),
        ("wind_data_path", True, T),
    ],

    # --- CSV / table-based analytical & telecoupling tools ---
    "run_model_selection_ols": [
        ("input_csv", True, T),
    ],
    "run_co2_emissions": [
        ("input_csv", True, T),
    ],
    "run_cost_benefit_analysis": [
        ("input_csv", True, T),
        ("economic_data_csv", True, T),
    ],
    "run_food_security": [
        ("fao_csv", True, T),
    ],
    "run_factor_analysis_mixed_data": [
        ("input_csv", True, T),
    ],
    "run_commodity_trade": [
        ("trade_csv", True, T),
        ("centroids_csv", False, T),
    ],
    "run_nutrition_metrics": [
        ("population_csv", True, T),
    ],
    "run_population_count_density": [
        ("input_csv", True, T),
        ("second_period_csv", False, T),
    ],
    "run_draw_radial_flows": [
        ("input_csv", True, T),
    ],
    "run_add_agents_interactively": [
        ("input_csv", True, T),
    ],
    "run_draw_agents_from_table": [
        ("input_csv", True, T),
    ],
    "run_add_causes_interactively": [
        ("input_csv", True, T),
    ],
    "run_add_systems_interactively": [
        ("input_csv", True, T),
    ],
    "run_draw_systems_from_table": [
        ("input_csv", True, T),
    ],
    "run_add_media_flows": [
        ("html_file", True, H),
        ("country_reference_csv", True, T),
    ],
}
