"""手动测试：测试 B — 13 个模块 import 验证"""
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

import shared.utils, shared.session_manager
import tools.network_analysis, tools.cbc_preprocessor, tools.cbc_main
import tools.seasonal_water_yield, tools.crop_percentile, tools.crop_regression
import renderers.qgis_renderer, renderers.csv_analyzer, renderers.output_router
import workers.task_queue

print("All 13 modules imported OK")
