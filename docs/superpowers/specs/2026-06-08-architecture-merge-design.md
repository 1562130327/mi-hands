# MI Hands 架构合并设计

## 概述

合并 MI Hands 的两套架构（旧插件体系 + v3 三层架构），只保留核心内容，简化项目结构。

## 目标

1. 删除旧架构（core/ + plugins/）
2. 保留 v3 三层架构
3. 集成 6 个核心操作指南到 v3
4. 简化项目结构，减少维护成本

## 保留内容

### 核心代码

| 模块 | 路径 | 说明 |
|------|------|------|
| 三层架构 | `src/v3/core/` | 决策层+执行层+验证层 |
| MCP 插件 | `src/v3/mcp/` | MCP 工具注册 |
| UIA 引擎 | `src/uia_engine.py` | UIA 控件树 |

### 核心指南（6 个）

| 指南 | 来源 | 用途 |
|------|------|------|
| windows.json | app_guides/windows.yaml | Windows 系统操作 |
| chrome.json | app_guides/chrome.yaml | Chrome 浏览器 |
| vscode.json | app_guides/vscode.yaml | VSCode 编辑器 |
| wechat.json | app_guides/wechat.yaml | 微信 |
| notepad.json | app_guides/notepad.yaml | 记事本 |
| paint.json | app_guides/paint.yaml | 画图 |

## 删除内容

### 旧架构

| 目录 | 说明 |
|------|------|
| core/ | 旧插件框架 |
| plugins/ | 9 个旧插件 |
| app_guides/ | 141 个指南（只保留 6 个） |

### 测试文件

| 文件 | 说明 |
|------|------|
| test_v3.py | 测试脚本 |
| test_mixed.py | 测试脚本 |
| test_draw.py | 测试脚本 |

## 目录结构

```
MI Hands/
├── src/
│   ├── v3/
│   │   ├── core/           # 三层架构
│   │   │   ├── host_agent.py
│   │   │   ├── app_agent.py
│   │   │   ├── verify.py
│   │   │   ├── action_models.py
│   │   │   ├── security.py
│   │   │   ├── memory.py
│   │   │   ├── reflection.py
│   │   │   ├── script_executor.py
│   │   │   ├── file_ops.py
│   │   │   ├── metrics.py
│   │   │   ├── skill_manager.py
│   │   │   ├── continuous_awareness.py
│   │   │   ├── entity_operations.py
│   │   │   ├── physical_hid.py
│   │   │   └── execution_engines.py
│   │   └── mcp/
│   │       └── plugin.py
│   └── uia_engine.py
├── skills/                 # 核心指南
│   ├── windows.json
│   ├── chrome.json
│   ├── vscode.json
│   ├── wechat.json
│   ├── notepad.json
│   └── paint.json
├── pyproject.toml
└── start-mcp-v3.bat
```

## 集成方式

### 静态加载

```python
# skill_manager.py 启动时扫描
skills_dir = Path("skills/")
for skill_file in skills_dir.glob("*.json"):
    with open(skill_file) as f:
        skill = json.load(f)
        self.skills[skill["name"]] = skill
```

### 自动注入

```python
# host_agent.py 规划时
def plan(self, task, uia_tree, screenshot):
    # 1. 匹配 skill
    matching_skills = self.skill_manager.find_matching(task)

    # 2. 注入 skill prompt
    skill_prompt = self._build_skill_prompt(matching_skills)

    # 3. 调用 MiMo
    response = self._call_mimo(prompt + skill_prompt, screenshot)
```

## 实施步骤

1. 创建 `skills/` 目录
2. 转换 6 个 YAML 指南为 JSON
3. 修改 `skill_manager.py` 支持静态加载
4. 修改 `host_agent.py` 支持自动注入
5. 删除旧架构（core/、plugins/）
6. 删除测试文件
7. 更新 pyproject.toml

## 验证标准

1. 6 个指南正确转换
2. 决策层能自动匹配 skill
3. 旧架构完全删除
4. 项目结构清晰
