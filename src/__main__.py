"""
MI Hands 入口 — python -m mi_hands

用法：
  python -m mi_hands                       # 交互模式
  python -m mi_hands "打开记事本"           # 执行任务
  python -m mi_hands --test-uia            # 测试 UIA 引擎
  python -m mi_hands --api                 # 启动 OpenAI API 服务
  python -m mi_hands --mcp                 # 启动 MCP Server
  python -m mi_hands --all                 # 同时启动 API + MCP
"""

import sys
import os
from pathlib import Path

# 确保 src 目录在 path 中
src_dir = Path(__file__).parent
if str(src_dir.parent) not in sys.path:
    sys.path.insert(0, str(src_dir.parent))


def load_config() -> dict:
    """加载配置"""
    import yaml
    config_path = Path(__file__).parent.parent / "config" / "mimo_config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def main():
    args = sys.argv[1:]

    # 测试 UIA
    if "--test-uia" in args:
        from src.uia_engine import test_uia
        test_uia()
        return

    # 启动 API 服务
    if "--api" in args:
        from src.server import start_api_server
        host = "0.0.0.0"
        port = 8765
        for i, a in enumerate(args):
            if a == "--port" and i + 1 < len(args):
                port = int(args[i + 1])
        start_api_server(host, port)
        return

    # 启动 MCP Server
    if "--mcp" in args:
        from src.server import start_mcp_server
        start_mcp_server()
        return

    # 同时启动 API + MCP
    if "--all" in args:
        from src.server import start_all
        start_all()
        return

    # 加载配置
    config = load_config()
    api_key = config.get("api_key") or os.getenv("MIMO_API_KEY", "")
    model = config.get("model", "mimo-v2.5-pro")

    if not api_key:
        print("❌ 未设置 API Key")
        print("   方法 1: 设置环境变量 MIMO_API_KEY")
        print("   方法 2: 编辑 config/mimo_config.yaml")
        print("   获取: https://platform.xiaomimimo.com")
        sys.exit(1)

    from src.mimo_client import MiMoClient
    client = MiMoClient(api_key=api_key, model=model)

    # 任务模式：python -m mi_hands "任务描述"
    task_args = [a for a in args if not a.startswith("--")]
    if task_args:
        task = " ".join(task_args)
        print(f"🎯 任务: {task}")
        print("🔄 执行中...\n")

        def on_action(name, result):
            print(f"  ⚡ {name}: {result[:120]}")

        client.on_action = on_action
        result = client.run_task(task)

        print(f"\n{'✅' if result['success'] else '❌'} {result['summary']}")
        print(f"  轮次: {result['turns']}")
        stats = result["token_stats"]
        if stats["estimated_saved_tokens"] > 0:
            print(f"  Token 节省: ~{stats['estimated_saved_tokens']}")
        return

    # 交互模式
    client.run_interactive()


if __name__ == "__main__":
    main()
