"""手动测试：测试 I — CSV 分析器"""
import os
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from renderers.csv_analyzer import analyze_csv

CSV_PATH = r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\datainput_for_demo\NetworkAnalysisGrouping_input\Network Analysis Grouping\nodes.csv"


def main():
    result = analyze_csv(CSV_PATH)
    print(f"Filename:     {result['filename']}")
    print(f"Columns:      {result['columns']}")
    print(f"Total rows:   {result['total_rows']}")
    print(f"Preview rows: {len(result['rows'])}")
    print(f"Chart config: {result['chart_config']}")
    print("\n✓ CSV Analyzer OK")


if __name__ == "__main__":
    main()
