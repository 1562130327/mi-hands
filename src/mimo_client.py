"""
MiMo Function Calling 客户端 — 调度 MiMo 模型执行桌面操作

核心流程：
1. 发送任务 + UIA 树给 MiMo
2. MiMo 返回 tool_calls（结构化的函数调用）
3. 执行工具，把结果喂回去
4. 重复直到 MiMo 调用 done
"""

import json
import time
from typing import Optional, Callable

from openai import OpenAI

from .uia_engine import UIAEngine
from .tools import get_tool_definitions, get_system_prompt, route_tool_call
from .optimizer import TokenOptimizer


class MiMoClient:
    """MiMo Function Calling 客户端"""

    def __init__(
        self,
        api_key: str,
        model: str = "mimo-v2.5-pro",
        base_url: str = "https://api.xiaomimimo.com/v1",
        max_turns: int = 20,
        on_action: Optional[Callable[[str, str], None]] = None,
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_turns = max_turns
        self.engine = UIAEngine()
        self.optimizer = TokenOptimizer()
        self.on_action = on_action  # 回调：(tool_name, result_text) -> None

    def run_task(self, task: str, window_handle: Optional[int] = None) -> dict:
        """
        执行一个桌面操作任务

        返回：
        {
            "success": bool,
            "summary": str,
            "turns": int,
            "actions": list[str],
            "token_stats": dict,
        }
        """
        self.optimizer.reset()
        actions = []
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": f"任务: {task}"},
        ]

        tools = get_tool_definitions()

        for turn in range(self.max_turns):
            # 先获取当前屏幕状态作为上下文
            if turn == 0:
                uia_text = self.engine.get_snapshot(window_handle)
                messages.append({
                    "role": "user",
                    "content": f"当前屏幕状态:\n{uia_text}"
                })

            # 调用 MiMo
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=1.0,
                    top_p=0.95,
                    max_tokens=4096,
                )
            except Exception as e:
                return {
                    "success": False,
                    "summary": f"API 调用失败: {e}",
                    "turns": turn + 1,
                    "actions": actions,
                    "token_stats": self.optimizer.get_stats(),
                }

            message = response.choices[0].message

            # 如果没有 tool_calls，MiMo 直接回复了文本
            if not message.tool_calls:
                # MiMo 可能认为任务完成了
                content = message.content or ""
                actions.append(f"[文本回复] {content[:100]}")
                return {
                    "success": True,
                    "summary": content,
                    "turns": turn + 1,
                    "actions": actions,
                    "token_stats": self.optimizer.get_stats(),
                }

            # 处理 tool_calls
            messages.append(message)  # 把 assistant 的回复加到对话中

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # 执行工具
                result = route_tool_call(self.engine, name, arguments)

                # 记录
                action_desc = f"[{turn+1}] {name}({json.dumps(arguments, ensure_ascii=False)[:80]}) → {result[:80]}"
                actions.append(action_desc)

                if self.on_action:
                    self.on_action(name, result)

                # 把工具结果喂回去
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

                # 如果是 done，结束
                if name == "done":
                    return {
                        "success": True,
                        "summary": arguments.get("summary", result),
                        "turns": turn + 1,
                        "actions": actions,
                        "token_stats": self.optimizer.get_stats(),
                    }

            # 操作后获取新的屏幕状态
            uia_text = self.engine.get_diff(window_handle)
            messages.append({
                "role": "user",
                "content": f"操作后的屏幕状态:\n{uia_text}"
            })

        # 超过最大轮次
        return {
            "success": False,
            "summary": f"超过最大轮次 ({self.max_turns})",
            "turns": self.max_turns,
            "actions": actions,
            "token_stats": self.optimizer.get_stats(),
        }

    def run_interactive(self, window_handle: Optional[int] = None):
        """交互式模式：用户输入任务，AI 执行"""
        print("=" * 60)
        print("MI Hands — 交互模式")
        print("输入任务描述，AI 会控制桌面完成。输入 q 退出。")
        print("=" * 60)

        while True:
            task = input("\n🎯 任务: ").strip()
            if not task or task.lower() == "q":
                break

            def on_action(name, result):
                print(f"  ⚡ {name}: {result[:100]}")

            self.on_action = on_action
            print(f"\n🔄 执行中...\n")

            result = self.run_task(task, window_handle)

            print(f"\n{'✅' if result['success'] else '❌'} {result['summary']}")
            print(f"  轮次: {result['turns']}")
            print(f"  Token 节省: ~{result['token_stats']['estimated_saved_tokens']}")

            if result["actions"]:
                print(f"\n  操作记录:")
                for a in result["actions"]:
                    print(f"    {a}")
