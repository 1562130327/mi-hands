"""
视觉引擎 — 结合 MiMo 视觉能力的增强版桌面控制

核心思路：
1. UIA 控件树 + 截图结合
2. 用 MiMo 视觉模型分析屏幕
3. 智能路径规划
"""

import base64
import json
from typing import Optional
from openai import OpenAI
from .uia_engine import UIAEngine


class VisionEngine:
    """视觉增强引擎"""

    def __init__(self, api_key: str = "", model: str = "mimo-v2.5"):
        self.api_key = api_key
        self.model = model
        self.engine = UIAEngine()
        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.xiaomimimo.com/v1"
            )
        else:
            self.client = None

    def analyze_screen(self, task: str = "") -> dict:
        """
        分析当前屏幕状态

        返回：
        {
            "uia_tree": str,           # UIA 控件树
            "screenshot_base64": str,  # 截图 base64
            "analysis": str,           # MiMo 分析结果
            "suggested_actions": list, # 建议的操作
        }
        """
        # 1. 获取 UIA 树
        uia_tree = self.engine.get_snapshot()

        # 2. 获取截图
        screenshot = self.engine.take_screenshot()
        screenshot_base64 = screenshot.base64_data if screenshot else ""

        # 3. 用 MiMo 分析（如果配置了 API）
        analysis = ""
        suggested_actions = []

        if self.client and screenshot_base64:
            analysis, suggested_actions = self._analyze_with_mimo(
                screenshot_base64, uia_tree, task
            )

        return {
            "uia_tree": uia_tree,
            "screenshot_base64": screenshot_base64[:100] + "..." if screenshot_base64 else "",
            "analysis": analysis,
            "suggested_actions": suggested_actions,
        }

    def _analyze_with_mimo(self, screenshot_base64: str, uia_tree: str, task: str) -> tuple:
        """用 MiMo 视觉模型分析屏幕"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """你是 MI Hands 视觉分析助手。分析屏幕截图和 UIA 树，给出操作建议。

返回 JSON 格式：
{
    "analysis": "屏幕状态描述",
    "actions": [
        {"type": "click", "x": 100, "y": 200, "description": "点击某个按钮"},
        {"type": "type_text", "text": "hello", "description": "输入文字"},
        {"type": "draw_path", "points": [[100,100], [150,120]], "description": "绘制路径"}
    ]
}
"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"任务: {task}\n\nUIA 树:\n{uia_tree}\n\n请分析屏幕并给出操作建议。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}"
                            }
                        }
                    ]
                }
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,
                temperature=0.3,
            )

            content = response.choices[0].message.content

            # 尝试解析 JSON
            try:
                # 提取 JSON 部分
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0]
                else:
                    json_str = content

                result = json.loads(json_str)
                return result.get("analysis", ""), result.get("actions", [])
            except json.JSONDecodeError:
                return content, []

        except Exception as e:
            return f"分析失败: {e}", []

    def generate_drawing_path(self, description: str, canvas_bounds: tuple = (400, 100, 1500, 800)) -> list:
        """
        根据描述生成绘制路径

        参数：
            description: 描述要画什么，比如"小鸡啄米图"
            canvas_bounds: 画布边界 (x1, y1, x2, y2)

        返回：
            路径点列表 [(x,y), ...]
        """
        if not self.client:
            # 降级：返回简单的默认路径
            return self._generate_simple_path(description, canvas_bounds)

        try:
            # 计算画布中心和大小
            cx = (canvas_bounds[0] + canvas_bounds[2]) // 2
            cy = (canvas_bounds[1] + canvas_bounds[3]) // 2
            width = canvas_bounds[2] - canvas_bounds[0]
            height = canvas_bounds[3] - canvas_bounds[1]

            messages = [
                {
                    "role": "system",
                    "content": f"""你是路径生成助手。根据描述生成绘制路径。

画布区域: {canvas_bounds}
画布中心: ({cx}, {cy})
画布大小: {width} x {height}

返回 JSON 格式的路径点列表：
{{
    "paths": [
        {{
            "name": "路径名称",
            "points": [[x1,y1], [x2,y2], ...],
            "color": "black",
            "description": "这条路径画什么"
        }}
    ]
}}

注意：
- 坐标必须在画布区域内
- 路径应该是连续的点
- 点之间距离不要太远（5-20像素）
"""
                },
                {
                    "role": "user",
                    "content": f"请生成'{description}'的绘制路径"
                }
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=3000,
                temperature=0.5,
            )

            content = response.choices[0].message.content

            # 解析 JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            result = json.loads(json_str)
            return result.get("paths", [])

        except Exception as e:
            print(f"路径生成失败: {e}")
            return self._generate_simple_path(description, canvas_bounds)

    def _generate_simple_path(self, description: str, canvas_bounds: tuple) -> list:
        """降级方案：生成简单的默认路径"""
        cx = (canvas_bounds[0] + canvas_bounds[2]) // 2
        cy = (canvas_bounds[1] + canvas_bounds[3]) // 2

        # 简单的小鸡啄米图路径
        paths = [
            {
                "name": "小鸡身体",
                "points": self._circle_points(cx, cy, 50),
                "color": "orange",
                "description": "小鸡的身体"
            },
            {
                "name": "小鸡嘴巴",
                "points": [
                    [cx + 50, cy],
                    [cx + 80, cy - 10],
                    [cx + 50, cy + 10],
                    [cx + 50, cy],
                ],
                "color": "red",
                "description": "小鸡的嘴巴"
            },
            {
                "name": "小鸡眼睛",
                "points": [[cx + 20, cy - 15], [cx + 22, cy - 15]],
                "color": "black",
                "description": "小鸡的眼睛"
            },
        ]

        return paths

    def _circle_points(self, cx: int, cy: int, radius: int, segments: int = 36) -> list:
        """生成圆形路径点"""
        import math
        points = []
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            x = int(cx + radius * math.cos(angle))
            y = int(cy + radius * math.sin(angle))
            points.append([x, y])
        return points
