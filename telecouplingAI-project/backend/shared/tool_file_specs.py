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

R, V, T = "raster", "vector", "table"

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
}
