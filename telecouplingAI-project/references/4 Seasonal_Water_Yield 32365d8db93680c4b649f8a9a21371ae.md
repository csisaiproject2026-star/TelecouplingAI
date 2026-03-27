# 4. Seasonal_Water_Yield

[seasonal_water_yield.html](seasonal_water_yield.html)

---

## Description

### Meaning

This function executes the **Seasonal Water Yield (SWY) Main Model** from the InVEST suite. It quantifies how different land use and land cover types contribute to **quickflow** (surface runoff during or shortly after rain events) and **baseflow** (slow release of water to streams during dry seasons) across a landscape. The model is particularly valuable in highly seasonal climates where baseflow sustains water availability during dry periods, and where land management decisions — such as reforestation or urban expansion — may significantly affect water timing and volume.

The model operates at a **monthly time step** using precipitation and evapotranspiration data, and aggregates results to annual and watershed-level outputs.

### Inputs

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `workspace_dir` | directory path | ✅ | Folder where all output files will be written. Created automatically if it does not exist |
| `aoi_path` | vector (polygon) | ✅ | Area of interest shapefile — defines the watersheds over which results are aggregated and summarized |
| `lulc_raster_path` | raster | ✅ | Map of land use/land cover codes. All values must have corresponding entries in the biophysical table |
| `dem_raster_path` | raster (m) | ✅ | Digital elevation model — used to derive flow direction and stream network |
| `soil_group_path` | raster | ✅ (conditionally) | Map of soil hydrologic groups (values 1–4, corresponding to groups A–D). Required if `user_defined_local_recharge` is `False` |
| `biophysical_table_path` | CSV file path | ✅ | Table mapping each LULC code to curve number values (`cn_A/B/C/D`) and monthly crop coefficients (`kc_1` to `kc_12`) |
| `precip_dir` | CSV file path | ✅ (conditionally) | Table mapping month index (1–12) to monthly precipitation raster paths (mm/month). Required if `user_defined_local_recharge` is `False` |
| `et0_dir` | CSV file path | ✅ (conditionally) | Table mapping month index (1–12) to reference evapotranspiration raster paths (mm/month). Required if `user_defined_local_recharge` is `False` |
| `rain_events_table_path` | CSV file path | ✅ (conditionally) | Table of number of rain events per month (`month`, `events` columns). Required if neither `user_defined_local_recharge` nor `user_defined_climate_zones` is selected |
| `threshold_flow_accumulation` | numeric | ✅ | Number of upslope pixels required before a pixel is classified as a stream |
| `alpha_m` | numeric | ✅ (conditionally) | Proportion of upslope annual available local recharge available in each month. Required if `monthly_alpha` is `False` |
| `beta_i` | ratio | ✅ | Proportion of the upgradient subsidy available for downgradient evapotranspiration |
| `gamma` | ratio | ✅ | Proportion of pixel local recharge available to downgradient pixels |
| `results_suffix` | string | ⬜ | Optional suffix appended to all output file names. Defaults to `''` (empty) |
| `user_defined_climate_zones` | boolean | ⬜ | If `True`, uses spatially variable climate zone data instead of a single rain events table |
| `climate_zone_raster_path` | raster | ⬜ (conditionally) | Map of climate zones. Required if `user_defined_climate_zones` is `True` |
| `climate_zone_table_path` | CSV file path | ⬜ (conditionally) | Table of monthly rain events per climate zone (`cz_id`, `jan`–`dec` columns). Required if `user_defined_climate_zones` is `True` |
| `user_defined_local_recharge` | boolean | ⬜ | If `True`, skips local recharge calculation and uses a user-supplied recharge raster instead |
| `l_path` | raster (mm) | ⬜ (conditionally) | User-supplied local recharge raster. Required if `user_defined_local_recharge` is `True` |
| `monthly_alpha` | boolean | ⬜ | If `True`, uses a month-by-month alpha table instead of a single `alpha_m` value |
| `monthly_alpha_path` | CSV file path | ⬜ (conditionally) | Table of alpha values per month (`month`, `alpha` columns). Required if `monthly_alpha` is `True` |

### Outputs

All main output files are located in **`workspace_dir/`**. Intermediate files are in **`workspace_dir/intermediate_outputs/`**.

| Output File | Type | Units | Description |
| --- | --- | --- | --- |
| `QF_[Suffix].tif` | Raster | mm | Annual quickflow — surface runoff generated per pixel |
| `B_[Suffix].tif` | Raster | mm (relative) | Baseflow contribution of each pixel to slow-release streamflow |
| `B_sum_[Suffix].tif` | Raster | mm (relative) | Total flow through a pixel from all upslope contributions that reaches the stream without being evapotranspired |
| `L_[Suffix].tif` | Raster | mm (relative) | Local recharge — precipitation minus quickflow minus actual evapotranspiration |
| `L_avail_[Suffix].tif` | Raster | mm (relative) | Available local recharge (fraction `gamma` of local recharge) |
| `L_sum_[Suffix].tif` | Raster | mm (relative) | Total upslope flow available for evapotranspiration to downslope pixels |
| `L_sum_avail_[Suffix].tif` | Raster | mm (relative) | Available water to a pixel contributed by all upslope pixels |
| `Vri_[Suffix].tif` | Raster | mm | Value of recharge index — each pixel's contribution (positive or negative) to total watershed recharge |
| `CN_[Suffix].tif` | Raster | unitless | Map of curve number values derived from LULC and soil group inputs |
| `stream_[Suffix].tif` | Raster | — | Stream network derived from DEM and threshold flow accumulation. 1 = stream, 0 = non-stream |
| `P_[Suffix].tif` | Raster | mm/year | Total annual precipitation per pixel |
| `aggregated_results_swy_[Suffix].shp` | Shapefile | — | Watershed-level aggregated results including `qb` (mean local recharge, mm) and `vri_sum` (total recharge contribution, mm) |
| `aet_[Suffix].tif` | Raster (intermediate) | mm | Actual evapotranspiration per pixel |
| `Si_[Suffix].tif` | Raster (intermediate) | inches | Maximum potential retention used in quickflow calculation |

### Internal Logic

1. **Load spatial inputs** — Reads DEM, LULC, soil hydrologic group, and AOI vector.
2. **Derive stream network** — Uses DEM and `threshold_flow_accumulation` to identify stream pixels via flow accumulation.
3. **Calculate curve numbers** — Combines LULC class and soil hydrologic group to derive CN values per pixel from the biophysical table.
4. **Calculate monthly quickflow (QF)** — Uses the NRCS Curve Number method combined with an exponential distribution of monthly rainfall depths and rain event counts. Annual QF is the sum of monthly QF values.
5. **Calculate actual evapotranspiration (AET)** — For each month, AET is limited by either PET (potential evapotranspiration, derived from ET₀ × Kc) or available water (precipitation − QF + upslope subsidy scaled by `alpha_m` and `beta_i`).
6. **Calculate local recharge (L)** — L = Precipitation − QF − AET. Negative values indicate the pixel consumes more water than it receives from precipitation alone.
7. **Calculate available recharge (L_avail)** — `L_avail = min(gamma × L, L)`, controlling how much local recharge is passed downslope.
8. **Calculate baseflow (B and B_sum)** — Accumulates upslope recharge contributions along the flow path. Pixels with negative local recharge do not contribute to baseflow.
9. **Calculate recharge index (Vri)** — Normalizes each pixel's contribution to total watershed recharge.
10. **Aggregate to watersheds** — Summarizes `qb` (mean baseflow index) and `vri_sum` per watershed polygon and writes to shapefile.
11. **Write all outputs** — All rasters and the aggregated shapefile are written to `workspace_dir`.

---

### Key Algorithms Used

- **NRCS Curve Number (CN) method** — Estimates quickflow based on land cover, soil type, and rainfall distribution
- **Exponential rainfall depth distribution** — Models the distribution of daily precipitation depths within a month given rain event counts
- **Water balance model** — Monthly budget of precipitation, quickflow, AET, and local recharge per pixel
- **Flow accumulation routing** — D8 or MFD algorithm used to route recharge downslope and accumulate baseflow contributions

This function is ideal for **watershed management, land use planning, and seasonal water security analysis**, enabling quantification of how landscape changes affect the timing and volume of both surface runoff and dry-season baseflow across a catchment.

---

## Current Code

```python
# Example input (KNIME flow variables):
# workspace_dir: output\seasonal_water_yield_results
# aoi_path: ..data\Seasonal Water Yield\watersheds.shp
# lulc_raster_path: ..data\Seasonal Water Yield\lulc.tif
# dem_raster_path: ..data\Seasonal Water Yield\dem.tif
# soil_group_path: ..data\Seasonal Water Yield\soil_groups.tif
# biophysical_table_path: ..data\Seasonal Water Yield\biophysical_table.csv
# precip_dir: ..data\Seasonal Water Yield\precip_table.csv
# et0_dir: ..data\Seasonal Water Yield\et0_table.csv
# rain_events_table_path: ..data\Seasonal Water Yield\rain_events.csv
# threshold_flow_accumulation: 1000
# alpha_m: 0.083333  (i.e. 1/12, uniform monthly distribution)
# beta_i: 1.0
# gamma: 1.0
# monthly_alpha: False
# monthly_alpha_path: (empty if monthly_alpha is False)
# user_defined_climate_zones: False
# climate_zone_raster_path: (empty if user_defined_climate_zones is False)
# climate_zone_table_path: (empty if user_defined_climate_zones is False)
# user_defined_local_recharge: False
# l_path: (empty if user_defined_local_recharge is False)
# results_suffix: (empty)

import knime.scripting.io as knio

import logging
import sys
import os
os.environ['PROJ_LIB'] = "C:\\Anaconda3\\envs\\geopy39\\Library\\share\\proj"

import natcap.invest.seasonal_water_yield.seasonal_water_yield
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
    'alpha_m': knio.flow_variables['alpha_m'],
    'aoi_path': knio.flow_variables['aoi_path'],
    'beta_i': knio.flow_variables['beta_i'],
    'biophysical_table_path': knio.flow_variables['biophysical_table_path'],
    'climate_zone_raster_path': knio.flow_variables['climate_zone_raster_path'],
    'climate_zone_table_path': knio.flow_variables['climate_zone_table_path'],
    'dem_raster_path': knio.flow_variables['dem_raster_path'],
    'et0_dir': knio.flow_variables['et0_dir'],
    'gamma': knio.flow_variables['gamma'],
    'l_path': knio.flow_variables['l_path'],
    'lulc_raster_path': knio.flow_variables['lulc_raster_path'],
    'monthly_alpha': knio.flow_variables['monthly_alpha'],
    'monthly_alpha_path': knio.flow_variables['monthly_alpha_path'],
    'precip_dir': knio.flow_variables['precip_dir'],
    'rain_events_table_path': knio.flow_variables['rain_events_table_path'],
    'results_suffix': '',
    'soil_group_path': knio.flow_variables['soil_group_path'],
    'threshold_flow_accumulation': knio.flow_variables['threshold_flow_accumulation'],
    'user_defined_climate_zones': knio.flow_variables['user_defined_climate_zones'],
    'user_defined_local_recharge': knio.flow_variables['user_defined_local_recharge'],
    'workspace_dir': knio.flow_variables['workspace_dir'],
}

natcap.invest.seasonal_water_yield.seasonal_water_yield.execute(args)

knio.output_tables[0] = knio.input_tables[0]
```