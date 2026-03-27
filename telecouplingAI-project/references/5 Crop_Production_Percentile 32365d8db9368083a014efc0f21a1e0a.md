# 5. Crop_Production_Percentile

[crop_production.html](crop_production.html)

## Description

### Meaning

This function executes the **Crop Production Percentile Model** from the InVEST suite. It estimates **crop yield and nutritional value** for up to 172 crops across a user-defined landscape, based on observed global yield data from the Monfreda et al. (2008) FAO dataset. Rather than modelling yield from first principles, it reports **percentile-based yield estimates** (25th, 50th, 75th, and 95th percentiles) derived from observed yields in each crop's climate bin — allowing users to explore a range of intensification scenarios, from current average performance to near-optimal yields.

This model is particularly useful for exploring questions such as: how would changing crop types or arrangements affect total production, nutritional output, or the trade-offs between food production and other ecosystem services?

---

### Inputs

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `workspace_dir` | directory path | ✅ | Folder where all output files will be written. Created automatically if it does not exist |
| `landcover_raster_path` | raster | ✅ | Map of land use/land cover codes. Each LULC code must have a corresponding entry in the `landcover_to_crop_table_path` |
| `landcover_to_crop_table_path` | CSV file path | ✅ | Table mapping each LULC code (`lucode`) to one of the 172 canonical crop names (`crop_name`). Only one LULC class can be associated with each unique crop type |
| `model_data_path` | directory path | ✅ | Path to the InVEST Monfreda sample data directory containing global climate bin maps, percentile yield tables, observed yield rasters, and crop nutrient data. Must be downloaded separately from the InVEST sample data package |
| `aggregate_polygon_path` | vector (polygon) | ⬜ | Optional area of interest shapefile — if provided, results are additionally summarized per polygon area |
| `results_suffix` | string | ⬜ | Optional suffix appended to all output file names. Defaults to `''` (empty) |

### About `model_data_path` contents

The `model_data` directory must contain the following (pre-provided in InVEST sample data, no user editing required):

| File/Folder | Used By | Description |
| --- | --- | --- |
| `climate_percentile_yield_tables/` | Percentile model | Per-crop CSV of 25th/50th/75th/95th percentile yields per climate bin |
| `extended_climate_bin_maps/` | Both models | Per-crop global raster of climate bins |
| `observed_yield/` | Both models | Per-crop global raster of actual observed yield circa year 2000 |
| `crop_nutrient.csv` | Both models | Nutritional values (33 macro and micronutrients) for each crop |
| `crop_to_climate_bin.csv` | Both models | Maps each crop name to its climate bin raster |
| `crop_to_observed_yield.csv` | Both models | Maps each crop name to its observed yield raster |
| `crop_to_percentile_yield.csv` | Percentile model | Maps each crop name to its percentile yield table |

---

### Outputs

All main output files are located in **`workspace_dir/`**. Intermediate files are in **`workspace_dir/intermediate_outputs/`**.

| Output File | Type | Description |
| --- | --- | --- |
| `result_table_[Suffix].csv` | CSV | Primary output — lists all crops modelled with area covered, percentile production (25th/50th/75th/95th), observed production, and nutritional information per crop |
| `<crop>_yield_<percentile>_production_[Suffix].tif` | Raster (Mt/ha/yr) | Per-crop production raster at each percentile (25th, 50th, 75th, 95th), masked to areas where that crop is grown |
| `<crop>_observed_production_[Suffix].tif` | Raster (Mt/ha/yr) | Per-crop observed production raster circa year 2000, masked to areas where that crop is grown |
| `aggregate_results_[Suffix].csv` | CSV | (Only if `aggregate_polygon_path` provided) Summarizes total observed/percentile production and nutrient information within each polygon |
| `intermediate_outputs/clipped_<crop>_climate_bin_map.tif` | Raster (intermediate) | Climate bin map clipped to the extent of the LULC raster |
| `intermediate_outputs/<crop>_yield_<percentile>_coarse_yield.tif` | Raster (intermediate) | Reclassified climate map at coarse resolution (1/12 degree) showing percentile yields |
| `intermediate_outputs/<crop>_yield_<percentile>_interpolated_yield.tif` | Raster (intermediate) | Percentile yield raster interpolated to match LULC raster resolution |
| `intermediate_outputs/<crop>_clipped_observed_yield.tif` | Raster (intermediate) | Observed yield clipped to LULC extent |
| `intermediate_outputs/<crop>_interpolated_observed_yield.tif` | Raster (intermediate) | Observed yield interpolated to LULC raster resolution |
| `intermediate_outputs/aggregate_vector.shp` | Shapefile (intermediate) | Spatial join of results to aggregate polygons (if provided) |

---

### Internal Logic

1. **Load LULC map** — Reads the landcover raster and maps each LULC code to a crop name using `landcover_to_crop_table_path`.
2. **For each crop identified in the LULC map:**
    - **Clip climate bin map** — Clips the global climate bin raster from `model_data/extended_climate_bin_maps/` to the extent of the LULC map.
    - **For each percentile (25th, 50th, 75th, 95th):**
        - Reclassify the clipped climate map using `model_data/climate_percentile_yield_tables/` to produce a coarse-resolution yield map.
        - Interpolate the coarse yield map to match the LULC raster resolution.
        - Mask out pixels not growing that crop according to the LULC map → produces the percentile production raster.
    - **Process observed yield** — Clips, zero-fills nodata, and interpolates the global observed yield raster, then masks to crop areas.
3. **Tabulate results** — Sums yield values and calculates nutritional content (using `crop_nutrient.csv`) across all modelled crops → writes `result_table.csv`.
4. **Aggregate to polygons (optional)** — If `aggregate_polygon_path` is provided, spatially aggregates all production and nutrient results within each polygon → writes `aggregate_results.csv`.
5. **Write all outputs** — All rasters and tables are written to `workspace_dir`.

---

### Key Concepts

- **Percentile yields** — The 25th percentile represents low-intensity farming; the 50th is roughly "average" yield; the 95th represents near-optimal yield achievable by improving farming practices. These are derived from observed global data within each climate bin, not modelled from fertilizer or management inputs.
- **Climate bins** — Each crop has a unique set of climate bins (based on temperature and precipitation zones). Yield distributions are computed separately within each bin to account for climate variability.
- **Observed yield** — Based on FAO and sub-national datasets circa year 2000 (Monfreda et al. 2008). Used as a quality control baseline alongside percentile estimates.
- **172 crops** — The Percentile model covers 172 crops globally. The companion Regression model covers only 10 staple crops but additionally accounts for fertilizer application rates.

---

This function is ideal for **food security analysis, land use planning, and agricultural policy assessment**, enabling comparison of current crop production against potential yields under different intensification scenarios, while also providing nutritional output data for 33 macro and micronutrients.

---

## Current Code

```python
# Example input (KNIME flow variables):
# workspace_dir: output\crop_production_results
# landcover_raster_path: ..data\Crop Production\lulc.tif
# landcover_to_crop_table_path: ..data\Crop Production\landcover_to_crop_table.csv
#   (columns: lucode, crop_name — e.g. 1, wheat / 2, maize / 3, rice)
# model_data_path: ..data\Crop Production\model_data
#   (must contain: climate_percentile_yield_tables/, extended_climate_bin_maps/,
#    observed_yield/, crop_nutrient.csv, crop_to_climate_bin.csv,
#    crop_to_observed_yield.csv, crop_to_percentile_yield.csv)
# aggregate_polygon_path: ..data\Crop Production\aoi.shp  (optional)
# results_suffix: (empty)

import knime.scripting.io as knio

import logging
import sys
import os
os.environ['PROJ_LIB'] = "C:\\Anaconda3\\envs\\geopy39\\Library\\share\\proj"

import natcap.invest.crop_production_percentile
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
    'landcover_raster_path': knio.flow_variables['landcover_raster_path'],
    'landcover_to_crop_table_path': knio.flow_variables['landcover_to_crop_table_path'],
    'model_data_path': knio.flow_variables['model_data_path'],
    'results_suffix': '',
    'workspace_dir': knio.flow_variables['workspace_dir'],
}

natcap.invest.crop_production_percentile.execute(args)

knio.output_tables[0] = knio.input_tables[0]
```