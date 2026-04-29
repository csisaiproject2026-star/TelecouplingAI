# CSIS Platform — Demo 输入文件 & Prompt 对照表

> 文件路径均相对于 `datainput_for_demo\`

---

## Tool 1 — Network Analysis（网络社区分析）

**上传文件：**

```
datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\nodes.csv
datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\links.csv
datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\World_countries_2002.shp
datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\World_countries_2002.dbf
datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\World_countries_2002.shx
datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\World_countries_2002.prj
```

**Prompt：**

```
Please run the network community analysis using the uploaded files.
Node ID column: CODE
Sender column: sender
Receiver column: receiver
Link weight column: larrivals
Shapefile join column: ISO_3_CODE
Clustering algorithm: walktrap
```

---

## Tool 2 — Coastal Blue Carbon Preprocessor（海岸蓝碳预处理）

**上传文件：**

```
datainput_for_demo\CoastalBLueCarbonPreprocessor_input\snapshots.csv
datainput_for_demo\CoastalBLueCarbonPreprocessor_input\lulc_lookup.csv
datainput_for_demo\CoastalBLueCarbonPreprocessor_input\GBJC_2010_mean_Resample.tif
datainput_for_demo\CoastalBLueCarbonPreprocessor_input\GBJC_2030_mean_Resample.tif
datainput_for_demo\CoastalBLueCarbonPreprocessor_input\GBJC_2050_mean_Resample.tif
```

**Prompt：**

```
Please run the Coastal Blue Carbon Preprocessor using the uploaded files.
Land cover snapshots file: snapshots.csv
LULC lookup table: lulc_lookup.csv
```

---

## Tool 3 — Coastal Blue Carbon Main（海岸蓝碳主模型）

**上传文件：**

```
datainput_for_demo\CoastalBlueCarbon_input\snapshots.csv
datainput_for_demo\CoastalBlueCarbon_input\outputs_preprocessor\transitions_sample.csv
datainput_for_demo\CoastalBlueCarbon_input\outputs_preprocessor\biophysical_table_sample.csv
datainput_for_demo\CoastalBlueCarbon_input\GBJC_2010_mean_Resample.tif
datainput_for_demo\CoastalBlueCarbon_input\GBJC_2030_mean_Resample.tif
datainput_for_demo\CoastalBlueCarbon_input\GBJC_2050_mean_Resample.tif
```

**Prompt：**

```
Please run the Coastal Blue Carbon main model using the uploaded files.
Land cover snapshots file: snapshots.csv
Transitions table: transitions_sample.csv
Biophysical table: biophysical_table_sample.csv
```

---

## Tool 4 — Seasonal Water Yield（季节性水量）

**上传文件（共 33 个）：**

```
datainput_for_demo\SeasonalWaterYield_input\watershed_gura.shp
datainput_for_demo\SeasonalWaterYield_input\watershed_gura.dbf
datainput_for_demo\SeasonalWaterYield_input\watershed_gura.shx
datainput_for_demo\SeasonalWaterYield_input\watershed_gura.prj
datainput_for_demo\SeasonalWaterYield_input\land_use_gura.tif
datainput_for_demo\SeasonalWaterYield_input\DEM_gura.tif
datainput_for_demo\SeasonalWaterYield_input\soil_group_gura.tif
datainput_for_demo\SeasonalWaterYield_input\biophysical_table_gura_SWY.csv
datainput_for_demo\SeasonalWaterYield_input\rain_events_gura.csv
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_1.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_2.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_3.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_4.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_5.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_6.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_7.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_8.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_9.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_10.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_11.tif
datainput_for_demo\SeasonalWaterYield_input\Precipitation_monthly\precip_gura_12.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_1.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_2.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_3.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_4.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_5.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_6.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_7.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_8.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_9.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_10.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_11.tif
datainput_for_demo\SeasonalWaterYield_input\ET0_monthly\ET0_gura_12.tif
```

**Prompt：**

```
Please run the Seasonal Water Yield model using all the uploaded files.
AOI watershed shapefile: watershed_gura.shp
Land use raster: land_use_gura.tif
DEM raster: DEM_gura.tif
Soil group raster: soil_group_gura.tif
Biophysical table: biophysical_table_gura_SWY.csv
Rain events table: rain_events_gura.csv
Monthly precipitation files: precip_gura_1.tif through precip_gura_12.tif
Monthly ET0 files: ET0_gura_1.tif through ET0_gura_12.tif
Threshold flow accumulation: 1000
```

---

## Tool 5 — Crop Production Percentile（作物产量百分位）

**上传文件：**

```
datainput_for_demo\CropProductionPercentile_input\sample_user_data\landcover.tif
datainput_for_demo\CropProductionPercentile_input\sample_user_data\landcover_to_crop_table.csv
datainput_for_demo\CropProductionPercentile_input\sample_user_data\aggregate_shape.shp
datainput_for_demo\CropProductionPercentile_input\sample_user_data\aggregate_shape.dbf
datainput_for_demo\CropProductionPercentile_input\sample_user_data\aggregate_shape.prj
datainput_for_demo\CropProductionPercentile_input\sample_user_data\aggregate_shape.shx
```

> `model_data_path` 为服务器端固定路径（`/data/model_data`），无需用户上传。
> `aggregate_shape` 为可选聚合多边形，用于按区域汇总产量结果。

**Prompt：**

```
Please run the Crop Production Percentile analysis using the uploaded files.
Land cover raster: landcover.tif
Crop mapping table: landcover_to_crop_table.csv
Aggregate polygon shapefile: aggregate_shape.shp
```

---

## Tool 6 — Crop Production Regression（作物产量回归）

**上传文件：**

```
datainput_for_demo\CropProductionRegression_input\sample_user_data\landcover.tif
datainput_for_demo\CropProductionRegression_input\sample_user_data\landcover_to_crop_table.csv
datainput_for_demo\CropProductionRegression_input\sample_user_data\crop_fertilization_rates.csv
datainput_for_demo\CropProductionRegression_input\sample_user_data\aggregate_shape.shp
datainput_for_demo\CropProductionRegression_input\sample_user_data\aggregate_shape.dbf
datainput_for_demo\CropProductionRegression_input\sample_user_data\aggregate_shape.prj
datainput_for_demo\CropProductionRegression_input\sample_user_data\aggregate_shape.shx
```

> `model_data_path` 为服务器端固定路径（`/data/model_data`），无需用户上传。
> `aggregate_shape` 为可选聚合多边形，用于按区域汇总产量结果。

**Prompt：**

```
Please run the Crop Production Regression analysis using the uploaded files.
Land cover raster: landcover.tif
Crop mapping table: landcover_to_crop_table.csv
Fertilization rates table: crop_fertilization_rates.csv
Aggregate polygon shapefile: aggregate_shape.shp
```
