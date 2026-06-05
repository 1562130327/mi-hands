"""操作指南数据模型测试"""

import pytest
from plugins.guide_manager.models import AppGuide, Operation, OperationStep


def test_create_app_guide():
    """测试创建操作指南"""
    guide = AppGuide(
        name="测试应用",
        version="1.0.0",
        process_name="test.exe"
    )

    assert guide.name == "测试应用"
    assert guide.version == "1.0.0"
    assert guide.process_name == "test.exe"


def test_create_operation():
    """测试创建操作"""
    operation = Operation(
        name="send_message",
        description="发送消息",
        steps=[
            OperationStep(action="click", target="输入框"),
            OperationStep(action="type_text", text="hello"),
            OperationStep(action="press_key", key="enter")
        ]
    )

    assert operation.name == "send_message"
    assert len(operation.steps) == 3


def test_guide_to_yaml():
    """测试转换为 YAML"""
    guide = AppGuide(
        name="测试应用",
        version="1.0.0",
        process_name="test.exe"
    )

    yaml_str = guide.to_yaml()
    assert "测试应用" in yaml_str
    assert "test.exe" in yaml_str


def test_guide_from_yaml():
    """测试从 YAML 创建"""
    yaml_str = """
metadata:
  name: 测试应用
  version: "1.0.0"
identity:
  process_name: test.exe
"""
    guide = AppGuide.from_yaml(yaml_str)
    assert guide.name == "测试应用"
    assert guide.process_name == "test.exe"
