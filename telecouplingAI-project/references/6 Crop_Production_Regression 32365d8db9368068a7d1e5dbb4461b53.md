# 6. Crop_Production_Regression

---

[seasonal_water_yield.html](seasonal_water_yield%201.html)

## Description

### Meaning

This function executes the **Crop Production Regression Model** from the InVEST suite. Unlike the Percentile model which reports observed yield distributions, this model **estimates crop yield based on fertilizer application rates** — specifically nitrogen, phosphorus, and potassium inputs (kg/ha). It is designed for exploring how changes in fertilizer management affect crop production and nutritional output for **10 globally modelled staple crops**: barley, maize, oil palm, potato, rice, soybean, sugar beet, sugar cane, sunflower, and wheat.

This model is particularly useful for questions such as: what is the trade-off between fertilizer intensification and ecosystem service impacts, and how much yield improvement is achievable through optimized nutrient management?

### Inputs

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `workspace_dir` | directory path | ✅ | Folder where all output files will be written. Created automatically if it does not exist |
| `landcover_raster_path` | raster | ✅ | Map of land use/land cover codes. Each LULC code must have a corresponding entry in `landcover_to_crop_table_path` |
| `landcover_to_crop_table_path` | CSV file path | ✅ | Table mapping each LULC code (`lucode`) to one of the 10 supported crop names (`crop_name`). Only one LULC class can be associated with each unique crop type |
| `fertilization_rate_table_path` | CSV file path | ✅ | Table mapping each crop to its fertilizer application rates. Required columns: `crop_name`, `nitrogen_rate` (kg/ha), `phosphorus_rate` (kg/ha), `potassium_rate` (kg/ha) |
| `model_data_path` | directory path | ✅ | Path to the InVEST Monfreda sample data directory containing global climate bin maps, regression yield tables, observed yield rasters, and crop nutrient data. Must be downloaded separately from the InVEST sample data package |
| `aggregate_polygon_path` | vector (polygon) | ⬜ | Optional area of interest shapefile — if provided, results are additionally summarized per polygon area |
| `results_suffix` | string | ⬜ | Optional suffix appended to all output file names. Defaults to `''` (empty) |

### Supported Crops (Regression Model Only)

Barley, Maize, Oil Palm, Potato, Rice, Soybean, Sugar Beet, Sugar Cane, Sunflower, Wheat

### About `model_data_path` contents

The `model_data` directory must contain the following (pre-provided in InVEST sample data, no user editing required):

| File/Folder | Description |
| --- | --- |
| `climate_regression_yield_tables/` | Per-crop CSV of regression parameters for each climate bin |
| `extended_climate_bin_maps/` | Per-crop global raster of climate bins |
| `observed_yield/` | Per-crop global raster of actual observed yield circa year 2000 |
| `crop_nutrient.csv` | Nutritional values (33 macro and micronutrients) for each crop |
| `crop_to_climate_bin.csv` | Maps each crop name to its climate bin raster |
| `crop_to_observed_yield.csv` | Maps each crop name to its observed yield raster |
| `crop_to_regression_yield.csv` | Maps each crop name to its regression yield table |

### Outputs

All main output files are located in **`workspace_dir/`**. Intermediate files are in **`workspace_dir/intermediate_outputs/`**.

| Output File | Type | Description |
| --- | --- | --- |
| `result_table_[Suffix].csv` | CSV | Primary output — lists all crops modelled with area covered, regression-modelled production, observed production, and nutritional information per crop |
| `<crop>_regression_production_[Suffix].tif` | Raster (Mt/ha/yr) | Per-crop regression-modelled production raster, based on fertilizer inputs and climate bin regression parameters, masked to areas where that crop is grown |
| `<crop>_observed_production_[Suffix].tif` | Raster (Mt/ha/yr) | Per-crop observed production raster circa year 2000, masked to areas where that crop is grown |
| `aggregate_results_[Suffix].csv` | CSV | (Only if `aggregate_polygon_path` provided) Summarizes total regression-modelled and observed production and nutrient information within each polygon |
| `intermediate_outputs/clipped_<crop>_climate_bin_map.tif` | Raster (intermediate) | Climate bin map clipped to the extent of the LULC raster |
| `intermediate_outputs/<crop>_<parameter>_coarse_regression_parameter.tif` | Raster (intermediate) | Coarse-resolution regression parameter raster per crop and nutrient element |
| `intermediate_outputs/<crop>_<parameter>_interpolated_regression_parameter.tif` | Raster (intermediate) | Regression parameter raster interpolated to match LULC raster resolution |
| `intermediate_outputs/<crop>_<element>_yield.tif` | Raster (intermediate) | Per-element (N/P/K) yield raster before pixel-wise minimum is applied |
| `intermediate_outputs/<crop>_clipped_observed_yield.tif` | Raster (intermediate) | Observed yield clipped to LULC extent |
| `intermediate_outputs/<crop>_interpolated_observed_yield.tif` | Raster (intermediate) | Observed yield interpolated to LULC raster resolution |
| `intermediate_outputs/aggregate_vector.shp` | Shapefile (intermediate) | Spatial join of results to aggregate polygons (if provided) |

### Internal Logic

1. **Load LULC map** — Reads the landcover raster and maps each LULC code to one of the 10 supported crop names using `landcover_to_crop_table_path`.
2. **Load fertilization rates** — Reads `fertilization_rate_table_path` to obtain nitrogen, phosphorus, and potassium application rates per crop.
3. **For each crop identified in the LULC map:**
    - **Clip climate bin map** — Clips the global climate bin raster from `model_data/extended_climate_bin_maps/` to the extent of the LULC map.
    - **Interpolate regression parameters** — Reclassifies the clipped climate map using regression parameters from `model_data/climate_regression_yield_tables/` for each nutrient element (N, P, K), then interpolates to LULC raster resolution.
    - **Calculate per-element yield** — For each of the three nutrient elements (nitrogen, phosphorus, potassium), calculates a separate yield raster using the regression parameters and the corresponding fertilization rate from `fertilization_rate_table_path`.
    - **Calculate final regression yield** — Takes the **pixel-wise minimum** of the three per-element yield rasters. The limiting nutrient determines final yield.
    - **Process observed yield** — Clips, zero-fills nodata, and interpolates the global observed yield raster, then masks to crop areas.
4. **Tabulate results** — Sums yield values and calculates nutritional content (using `crop_nutrient.csv`) across all modelled crops → writes `result_table.csv`.
5. **Aggregate to polygons (optional)** — If `aggregate_polygon_path` is provided, spatially aggregates all production and nutrient results within each polygon → writes `aggregate_results.csv`.
6. **Write all outputs** — All rasters and tables are written to `workspace_dir`.

### Key Differences from Percentile Model

|  | Percentile Model | Regression Model |
| --- | --- | --- |
| Number of crops | 172 | 10 staple crops only |
| Yield basis | Observed percentile distributions (25th/50th/75th/95th) | Regression from fertilizer application rates |
| Additional input required | None | `fertilization_rate_table_path` (N/P/K rates per crop) |
| Best for | Exploring intensification scenarios across many crops | Evaluating fertilizer management impacts on yield |
| Yield output type | `<crop>_yield_<percentile>_production.tif` | `<crop>_regression_production.tif` |

This function is ideal for **fertilizer management analysis, agricultural intensification studies, and nutrient-yield trade-off assessments**, enabling quantification of how varying nitrogen, phosphorus, and potassium inputs affect crop production across a landscape, alongside nutritional output data for 33 macro and micronutrients.

---

## Current Code

```python
# Example input (KNIME flow variables):
# workspace_dir: output\crop_production_regression_results
# landcover_raster_path: ..data\Crop Production\lulc.tif
# landcover_to_crop_table_path: ..data\Crop Production\landcover_to_crop_table.csv
#   (columns: lucode, crop_name — limited to 10 supported crops:
#    barley, maize, oil palm, potato, rice, soybean,
#    sugar beet, sugar cane, sunflower, wheat)
# fertilization_rate_table_path: ..data\Crop Production\fertilization_rate_table.csv
#   (columns: crop_name, nitrogen_rate, phosphorus_rate, potassium_rate — units: kg/ha)
# model_data_path: ..data\Crop Production\model_data
#   (must contain: climate_regression_yield_tables/, extended_climate_bin_maps/,
#    observed_yield/, crop_nutrient.csv, crop_to_climate_bin.csv,
#    crop_to_observed_yield.csv, crop_to_regression_yield.csv)
# aggregate_polygon_path: ..data\Crop Production\aoi.shp  (optional)
# results_suffix: (empty)

import knime.scripting.io as knio

import logging
import sys
import os
os.environ['PROJ_LIB'] = "C:\\Anaconda3\\envs\\geopy39\\Library\\share\\proj"

import natcap.invest.crop_production_regression
import natcap.invest.utils

LOGGER = logging.getLogger(__name__)
root_logger = logging.getLogger()

handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    fmt=natcap.invest.utils.LOG_FMT,
    datefmt='%m/%d/%Y %H:%M:%S ')
handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[handler])

args = {
    'aggregate_polygon_path': knio.flow_variables['aggregate_polygon_path'],
    'fertilization_rate_table_path': knio.flow_variables['fertilization_rate_table_path'],
    'landcover_raster_path': knio.flow_variables['landcover_raster_path'],
    'landcover_to_crop_table_path': knio.flow_variables['landcover_to_crop_table_path'],
    'model_data_path': knio.flow_variables['model_data_path'],
    'results_suffix': '',
    'workspace_dir': knio.flow_variables['workspace_dir'],
}

natcap.invest.crop_production_regression.execute(args)

knio.output_tables[0] = knio.input_tables[0]
```