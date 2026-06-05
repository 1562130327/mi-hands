"""操作指南数据模型"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import yaml


@dataclass
class OperationStep:
    """操作步骤"""
    action: str
    target: Optional[str] = None
    text: Optional[str] = None
    key: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    timeout: int = 10


@dataclass
class Operation:
    """操作"""
    name: str
    description: str
    steps: List[OperationStep] = field(default_factory=list)
    variables: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AppGuide:
    """应用操作指南"""
    name: str
    version: str
    process_name: str
    install_paths: List[str] = field(default_factory=list)
    window_title_pattern: Optional[str] = None
    class_name: Optional[str] = None
    login_required: bool = False
    login_method: Optional[str] = None
    login_steps: List[OperationStep] = field(default_factory=list)
    features: List[Dict[str, str]] = field(default_factory=list)
    operations: Dict[str, Operation] = field(default_factory=dict)
    uia_tree: Dict[str, Any] = field(default_factory=dict)
    fallback: Dict[str, Any] = field(default_factory=dict)

    def to_yaml(self) -> str:
        """转换为 YAML 格式"""
        data = {
            "metadata": {
                "name": self.name,
                "version": self.version
            },
            "identity": {
                "process_name": self.process_name,
                "install_paths": self.install_paths
            }
        }
        return yaml.dump(data, allow_unicode=True, default_flow_style=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "AppGuide":
        """从 YAML 创建"""
        data = yaml.safe_load(yaml_str)
        metadata = data.get("metadata", {})
        identity = data.get("identity", {})
        operations_data = data.get("operations", {})

        # 解析操作
        operations = {}
        for op_name, op_data in operations_data.items():
            steps = []
            for step_data in op_data.get("steps", []):
                step = OperationStep(
                    action=step_data.get("action", ""),
                    target=step_data.get("target"),
                    text=step_data.get("text"),
                    key=step_data.get("key"),
                    x=step_data.get("x"),
                    y=step_data.get("y"),
                    timeout=step_data.get("timeout", 10)
                )
                steps.append(step)

            operation = Operation(
                name=op_name,
                description=op_data.get("description", ""),
                steps=steps,
                variables=op_data.get("variables", [])
            )
            operations[op_name] = operation

        return cls(
            name=metadata.get("name", ""),
            version=metadata.get("version", ""),
            process_name=identity.get("process_name", ""),
            install_paths=identity.get("install_paths", []),
            operations=operations
        )
