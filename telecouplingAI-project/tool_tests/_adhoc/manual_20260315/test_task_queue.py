"""手动测试：测试 K — task_queue 工具分发验证"""
import sys

sys.path.insert(0, r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev\telecouplingAI-project\backend")

from workers.task_queue import execute_tool
from shared.utils import CSISError


def main():
    # 验证未知工具名抛 ValueError
    try:
        execute_tool("fake_tool", {}, "sess", "tid123", lambda p, m: None)
        print("ERROR: Should have raised ValueError!")
        sys.exit(1)
    except ValueError as e:
        print(f"Unknown tool correctly rejected: {e}")

    # 验证合法工具能被正确分发（缺参数时抛 CSISError，而不是 ValueError）
    try:
        execute_tool("run_network_analysis_grouping", {}, "sess", "my_real_task_id", lambda p, m: None)
        print("ERROR: Should have raised CSISError!")
        sys.exit(1)
    except CSISError as e:
        print(f"Tool dispatched correctly (failed at validation as expected): {e.error_code}")

    print("\n✓ task_queue dispatch OK")


if __name__ == "__main__":
    main()
