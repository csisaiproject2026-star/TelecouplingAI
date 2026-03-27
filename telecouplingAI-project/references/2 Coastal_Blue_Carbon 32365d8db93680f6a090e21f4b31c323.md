# 2. Coastal_Blue_Carbon

[coastal_blue_carbon.html](coastal_blue_carbon%201.html)

## Description

### Meaning

This function executes the **Coastal Blue Carbon Main Model** from the InVEST (Integrated Valuation of Ecosystem Services and Tradeoffs) suite. It performs a full temporal analysis of carbon storage, accumulation, and emissions across coastal habitats — such as mangroves, salt marshes, and seagrasses — based on LULC transitions across multiple snapshot years. Optionally, it also calculates the **monetary net present value** of carbon sequestration if economic analysis is enabled.

This function is the **second and core step** of the Coastal Blue Carbon workflow. It requires the `transitions_.csv` (produced by the Preprocessor and **manually edited** by the user) and a biophysical parameter table as key inputs before it can be executed.

---

### Inputs

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `landcover_snapshot_csv` | CSV file path | ✅ | Table mapping snapshot years to corresponding LULC raster paths (`snapshot_year`, `raster_path` columns required) |
| `landcover_transitions_table` | CSV file path | ✅ | Transition matrix CSV — produced by Preprocessor and **manually edited** by user to define carbon impact type (`accumulation`, `disturb`, `NCC`) for each LULC transition |
| `biophysical_table_path` | CSV file path | ✅ | Table of biophysical carbon properties per LULC class, including initial carbon stocks (`biomass-initial`, `soil-initial`, `litter-initial`), half-lives, disturbance proportions, and yearly accumulation rates |
| `workspace_dir` | directory path | ✅ | Folder where all output files will be written. Created automatically if it does not exist |
| `results_suffix` | string | ⬜ | Optional suffix appended to all output file names. Defaults to `''` (empty) |
| `analysis_year` | integer | ⬜ | Optional year beyond the final snapshot year for extended analysis |
| `do_economic_analysis` | boolean | ⬜ | Set to `True` to enable monetary valuation of carbon sequestration |
| `discount_rate` | numeric | ⬜ | Annual discount rate (%) used in net present value calculation. Required if `do_economic_analysis` is `True` |
| `inflation_rate` | numeric | ⬜ | Annual inflation rate (%) applied to carbon price over time. Required if `do_economic_analysis` is `True` |
| `price` | numeric | ⬜ | Price per Megatonne of CO₂e. Required if `do_economic_analysis` is `True` and `use_price_table` is `False` |
| `use_price_table` | boolean | ⬜ | If `True`, uses a year-by-year price table instead of a single fixed price |
| `price_table_path` | CSV file path | ⬜ | Path to year-by-year carbon price table. Required if `use_price_table` is `True` |

---

### Outputs

All output files are located in **`workspace_dir/`**.

| Output File | Type | Description |
| --- | --- | --- |
| `carbon-stock-at-[year][Suffix].tif` | Raster (TIF) | Carbon stock at each snapshot year. For baseline year: sum of 3 initial carbon pools. For subsequent years: previous stock + accumulation − emissions. Units: Megatonnes CO₂e per Hectare |
| `carbon-accumulation-between-[year]-and-[year][Suffix].tif` | Raster (TIF) | Amount of carbon accumulated between two snapshot years |
| `carbon-emissions-between-[year]-and-[year][Suffix].tif` | Raster (TIF) | Amount of carbon emitted between two snapshot years due to LULC disturbance |
| `total-net-carbon-sequestration-between-[year]-and-[year][Suffix].tif` | Raster (TIF) | Total net carbon sequestration between two snapshot years |
| `total-net-carbon-sequestration[Suffix].tif` | Raster (TIF) | Total net carbon sequestration across the entire analysis period |
| `net-present-value[Suffix].tif` | Raster (TIF) | Monetary value of carbon sequestration (only produced if `do_economic_analysis` is `True`) |

---

### Internal Logic

1. **Load LULC snapshots** — Reads the snapshots CSV to obtain the list of LULC raster maps and their corresponding years in chronological order.
2. **Load transition matrix** — Reads the manually edited `landcover_transitions_table` to determine the carbon impact type (accumulation / disturb / NCC) for every LULC-to-LULC transition.
3. **Load biophysical parameters** — Reads carbon pool properties per LULC class (initial stocks, half-lives, disturbance proportions, yearly accumulation rates).
4. **Calculate carbon stock** — For the baseline year, stock = sum of the 3 initial carbon pools (biomass + soil + litter). For each subsequent year, stock = previous stock + accumulation − emissions.
5. **Calculate carbon accumulation** — Derived from the yearly accumulation rate of the destination LULC class after a transition into an accumulation state.
6. **Calculate carbon emissions** — Begins in the snapshot year where a LULC transition into a disturbed state occurs. Emissions are spread over time based on the half-life defined in the biophysical table.
7. **Calculate net sequestration** — Aggregates accumulation minus emissions across all transitions and years.
8. **Economic valuation (optional)** — If `do_economic_analysis` is enabled, calculates net present value using the provided price, discount rate, and inflation rate (or price table).
9. **Write outputs** — All raster results are written to `workspace_dir`, one file per snapshot year interval and per metric.

---

### Key Algorithms Used

- **Carbon stock tracking** — Year-by-year stock accounting across three carbon pools (biomass, soil, litter) with transition-driven changes
- **Half-life decay model** — Carbon emissions after disturbance are modelled using exponential decay based on each pool's half-life
- **Net present value calculation** — Discounted cash flow model applied to carbon sequestration value over the analysis period

---

This function is ideal for **coastal ecosystem management and climate policy analysis**, enabling quantification of how LULC changes in coastal areas affect carbon storage and sequestration over time, and optionally translating those changes into monetary values for cost-benefit assessments.

---

## Current Code

```python
# Example input (KNIME flow variables):
# analysis_year: 2030
# biophysical_table_path: ..data\Coastal Blue Carbon\carbon_biophysical_table.csv
# landcover_snapshot_csv: ..data\Coastal Blue Carbon\landcover_snapshot.csv
# landcover_transitions_table: ..data\Coastal Blue Carbon\transitions.csv  ← manually edited from Preprocessor output
# discount_rate: 5
# inflation_rate: 2
# do_economic_analysis: True
# use_price_table: False
# price: 43.0
# price_table_path: (empty if use_price_table is False)
# results_suffix: (empty)
# workspace_dir: output\coastal_blue_carbon_results

import knime.scripting.io as knio

import logging
import sys
import os
os.environ['PROJ_LIB'] = "C:\\Anaconda3\\envs\\geopy39\\Library\\share\\proj"

import natcap.invest.coastal_blue_carbon.coastal_blue_carbon
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
    'analysis_year': knio.flow_variables['analysis_year'],
    'biophysical_table_path': knio.flow_variables['biophysical_table_path'],
    'discount_rate': knio.flow_variables['discount_rate'],
    'do_economic_analysis': knio.flow_variables['do_economic_analysis'],
    'inflation_rate': knio.flow_variables['inflation_rate'],
    'landcover_snapshot_csv': knio.flow_variables['landcover_snapshot_csv'],
    'landcover_transitions_table': knio.flow_variables['landcover_transitions_table'],
    'price': knio.flow_variables['price'],
    'price_table_path': knio.flow_variables['price_table_path'],
    'results_suffix': '',
    'use_price_table': knio.flow_variables['use_price_table'],
    'workspace_dir': knio.flow_variables['workspace_dir'],
}

natcap.invest.coastal_blue_carbon.coastal_blue_carbon.execute(args)

knio.output_tables[0] = knio.input_tables[0]
```

[coastal_blue_carbon.html](coastal_blue_carbon%202.html)