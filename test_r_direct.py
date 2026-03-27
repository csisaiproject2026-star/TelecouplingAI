import json, subprocess, shutil, os, sys

config = {
    "nodes_table": r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\nodes.csv",
    "links_table":  r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\links.csv",
    "shapefile_path": r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\World_countries_2002.shp",
    "nodes_join_attri": "CODE",
    "layer_join_attri": "ISO_3_CODE",
    "clustering_algorithm": "walktrap",
    "weight_within": 10,
    "weight_between": 2,
    "color_set": "Set3",
    "node_size": 0.05,
    "edge_width": 0.833333,
    "label_size": 0.8,
    "out_pdf": r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\test_outputs\test_network_plot.pdf",
    "out_csv": r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\test_outputs\test_network_stats.csv",
    "out_shp": r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\test_outputs\test_network_output.shp",
}

script = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend\r_scripts\network_analysis.R"
rscript = shutil.which("Rscript")
print(f"Rscript path: {rscript}")
print(f"Script exists: {os.path.isfile(script)}")

proc = subprocess.run(
    [rscript, script, json.dumps(config)],
    capture_output=True, text=True, timeout=300,
)
print(f"returncode: {proc.returncode}")
print(f"--- stdout ---\n{proc.stdout[-1000:]}")
print(f"--- stderr ---\n{proc.stderr[-500:]}")
sys.exit(proc.returncode)
