# 1. Coastal_Blue_Carbon_preprocessor

[coastal_blue_carbon.html](coastal_blue_carbon.html)

## Description

## Meaning

This function executes the **Coastal Blue Carbon** from the InVEST (Integrated Valuation of Ecosystem Services and Tradeoffs) model suite via an MCP server interface. It is designed to prepare input data for full coastal blue carbon analysis by identifying all **Land Use / Land Cover (LULC) transitions** across snapshot years, and generating a **transition matrix** and a **carbon pool template table** that describe how coastal habitats (e.g. mangroves, salt marshes, seagrasses) change over time. These outputs are essential prerequisites before running the main Coastal Blue Carbon model.

The function also handles robust parameter parsing, dynamic file downloading from remote URLs, and structured result delivery — making it suitable for automated pipeline environments such as **Dify** or other AI-agent orchestration platforms.

---

### Inputs

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `landcover_file` | URL string | ✅ | Remote URL to the **LULC snapshots table** CSV — a table mapping snapshot years to corresponding LULC raster paths (`snapshot_year`, `raster_path` columns required) |
| `lulc_file` | URL string | ✅ | Remote URL to the **LULC lookup table** CSV — maps LULC codes to class names and whether each class is a coastal blue carbon habitat (`lucode`, `lulc-class`, `is_coastal_blue_carbon_habitat` columns required) |
| `GBJC_*_Resample` | URL string(s) | ✅ | Remote URLs to **LULC raster files** (`.tif`) for each snapshot year. Keys must follow the pattern `GBJC_<identifier>_Resample`. Multiple rasters can be provided, one per snapshot year |
| `workspace_dir` | string | ✅ (auto-generated) | Output directory auto-created using a timestamp-based folder name under the shared directory |
| `results_suffix` | string | ⬜ | Optional suffix appended to all output file names. Defaults to `''` (empty) |

> **Note:** `input_data` is the top-level parameter received by the MCP tool. It must be a **dictionary** (or a string parseable as a dictionary/JSON) containing the above keys. The function includes robust parsing logic to handle both string and dict formats.
> 

---

### Outputs

All output files are located in **`Workspace/outputs_preprocessor/`** and are served via downloadable URLs.

| Output File | Type | Description |
| --- | --- | --- |
| `transitions_[Suffix].csv` | CSV | Transition matrix identifying all LULC class transitions across snapshot years. Left column = source LULC class; top row = destination LULC class. Values indicate transition type: `accumulation`, `disturb`, `NCC` (no carbon change), or blank |
| `carbon_pool_transient_template_[Suffix].csv` | CSV | Template table for transient carbon pool data — pre-filled based on detected transitions. Must be further edited by the user before use in the main model |
| `aligned_lulc_[year]_[Suffix].tif` | Raster (TIF) | Aligned and resampled LULC raster for each snapshot year, used as intermediate processing output |
| MCP return value | JSON | `{"status": "success", "data": [{"file": "<filename>", "url": "<download_url>"}]}` for each output file, or `{"status": "error", "message": "<reason>"}` on failure |

---

### Internal Logic

1. **Parse input parameters** — Checks if `input_data` is a string; if so, attempts to parse it via `ast.literal_eval()` then `json.loads()`. Returns an error immediately if parsing fails or if the result is an empty/non-dict object.
2. **Create timestamped output directory** — Generates a folder named `YYYYMMDD_HHMMSS_blue_carbon_results` under the shared directory.
3. **Download required files** — Downloads `landcover_file` (LULC snapshots table) and `lulc_file` (LULC lookup table) from their remote URLs to local paths.
4. **Download raster files** — Iterates over all keys in `input_data` matching the pattern `GBJC_*_Resample`, downloading each raster `.tif` file to local storage.
5. **Execute InVEST preprocessor** — Calls `natcap.invest.coastal_blue_carbon.preprocessor.execute()` with the constructed `invest_args` dict, which includes `landcover_snapshot_csv`, `lulc_lookup_table_path`, `results_suffix`, and `workspace_dir`.
6. **Collect output files** — Scans the `outputs_preprocessor` subdirectory using `glob`, collects all output files, and constructs download URLs using the file server base URL.
7. **Return results** — Returns a structured JSON response with status and a list of output file names and their download URLs.

---

### Key Components Used

- **`natcap.invest.coastal_blue_carbon.preprocessor`** — The InVEST model module that performs LULC transition analysis and generates the transition matrix and carbon pool template
- **`ast.literal_eval` / `json.loads`** — Dual-layer string parsing for robust handling of parameter inputs from AI-agent pipelines
- **`glob`** — Used to collect all files generated in the `outputs_preprocessor` output directory
- **`datetime`** — Used to generate unique timestamped output folder names per execution

---

This function is ideal for **automated ecological modeling pipelines** where coastal habitat change data needs to be preprocessed before full carbon stock and sequestration analysis. It is particularly suited to environments like Dify or other LLM-agent orchestration tools that pass parameters as strings or loosely structured dictionaries.

## Current Code

```python
import natcap.invest.coastal_blue_carbon.preprocessor

def run_coastal_blue_carbon(input_data):
    """
    执行沿海蓝碳预处理计算。
    参数 input_data 必须包含文件路径字典或其字符串形式。
    """
    # 1. 立即打印，确认数据到底进没进来
    logger.info(f"--- MCP 接收到原始数据: {input_data} (类型: {type(input_data)}) ---")

    # 2. 健壮的解析逻辑
    if isinstance(input_data, str):
        try:
            logger.info("尝试解析字符串格式参数...")
            import ast
            input_data = ast.literal_eval(input_data)
        except Exception as e:
            try:
                import json
                input_data = json.loads(input_data)
            except:
                logger.error(f"字符串解析彻底失败: {e}")
                return {"status": "error", "message": "无法解析传入的字符串参数"}

    # 3. 核心拦截：如果是空字典，直接返回错误，不要往下走
    if not isinstance(input_data, dict) or not input_data:
        logger.error("收到的数据为空或非字典格式，停止执行")
        return {"status": "error", "message": "MCP收到的input_data为空，请检查Dify参数绑定"}

    """执行沿海蓝碳预处理计算"""
    time_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder_name = f"{time_stamp}_blue_carbon_results"
    output_dir = os.path.join(SHARED_DIR, folder_name)
    os.makedirs(output_dir, exist_ok=True)
    
    downloaded_files = {}
    try:
        # 下载必需文件
        logger.info("开始下载文件...")
        logger.info(f"Input data: {input_data}")
        
        downloaded_files['landcover'] = download_file(
            input_data['landcover_file'], 'landcover_snapshot.csv'
        )
        downloaded_files['lulc'] = download_file(
            input_data['lulc_file'], 'lulc_lookup.csv'
        )
        
        # 下载栅格文件
        raster_files = []
        for key, url in input_data.items():
            if key.startswith('GBJC_') and key.endswith('_Resample'):
                raster_path = download_file(url, f"{key}.tif")
                raster_files.append(raster_path)
                downloaded_files[key] = raster_path
        
        #logger.info(f"成功下载 {len(raster_files)} 个栅格文件")
        
        # 执行 InVEST
        invest_args = {
            'landcover_snapshot_csv': downloaded_files['landcover'],
            'lulc_lookup_table_path': downloaded_files['lulc'],
            'results_suffix': '',
            'workspace_dir': output_dir,
        }
        natcap.invest.coastal_blue_carbon.preprocessor.execute(invest_args)
        
        # 构造结果链接
        # 假设结果在 outputs_preprocessor 子目录下
        search_path = os.path.join(output_dir, "outputs_preprocessor", "*")
        result_files = glob.glob(search_path)
        
        results = []
        for f in result_files:
            if os.path.isfile(f):
                fname = os.path.basename(f)
                # 拼接 URL: http://IP:8002/download/目录/子目录/文件
                url = f"{FILE_SERVER_URL}{folder_name}/outputs_preprocessor/{fname}"
                results.append({"file": fname, "url": url})
    
        return {"status": "success", "data": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

import logging
import sys

import natcap.invest.coastal_blue_carbon.preprocessor
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
    'landcover_snapshot_csv': knio.flow_variables['landcover_snapshot_csv'],
    'lulc_lookup_table_path': knio.flow_variables['lulc_lookup_table_path'],
    'results_suffix': '',
    'workspace_dir': knio.flow_variables['workspace_dir'],
}
natcap.invest.coastal_blue_carbon.preprocessor.execute(args)

knio.output_tables[0] = knio.input_tables[0]
```