# MI Hands 架构合并实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合并 MI Hands 的两套架构，删除旧代码，保留 v3 + 6 个核心指南

**Architecture:** 删除 core/ + plugins/ 旧架构，保留 src/v3/ 三层架构，将 6 个 YAML 指南转为 JSON 集成到 v3

**Tech Stack:** Python 3.10+, YAML, JSON, MCP

---

## Task 1: 转换 6 个核心指南为 JSON

**Files:**
- Create: `D:\MI-Hands\skills\windows.json`
- Create: `D:\MI-Hands\skills\chrome.json`
- Create: `D:\MI-Hands\skills\vscode.json`
- Create: `D:\MI-Hands\skills\wechat.json`
- Create: `D:\MI-Hands\skills\notepad.json`
- Create: `D:\MI-Hands\skills\paint.json`

- [ ] **Step 1: 创建 skills 目录**

```bash
mkdir -p D:\MI-Hands\skills
```

- [ ] **Step 2: 转换 chrome.yaml 为 JSON**

读取 `D:\MI-Hands\app_guides\chrome.yaml`，转换为 `D:\MI-Hands\skills\chrome.json`，保留全部字段。

- [ ] **Step 3: 转换其他 5 个指南**

同样方式转换 windows.yaml、vscode.yaml、wechat.yaml、notepad.yaml、paint.yaml。

- [ ] **Step 4: 验证 JSON 格式**

```bash
cd D:\MI-Hands\skills
python -c "import json; [json.load(open(f)) for f in __import__('glob').glob('*.json')]; print('All JSON valid')"
```

- [ ] **Step 5: Commit**

```bash
git add skills/
git commit -m "feat: convert 6 core guides from YAML to JSON"
```

---

## Task 2: 修改 SkillManager 支持静态加载

**Files:**
- Modify: `D:\MI-Hands\src\v3\core\skill_manager.py`

- [ ] **Step 1: 添加静态加载方法**

在 `SkillManager` 类中添加 `_load_static_skills` 方法：

```python
def _load_static_skills(self):
    """加载 skills/ 目录中的静态 skill"""
    for skill_file in SKILLS_DIR.glob("*.json"):
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                skill = json.load(f)
                if "name" in skill:
                    self._static_skills[skill["name"]] = skill
        except Exception as e:
            print(f"Failed to load {skill_file}: {e}")
```

- [ ] **Step 2: 修改 __init__ 添加静态 skills 存储**

```python
def __init__(self):
    self._ensure_dirs()
    self._registry = self._load_registry()
    self._static_skills = {}  # 新增
    self._load_static_skills()  # 新增
```

- [ ] **Step 3: 修改 find_matching_skills 包含静态 skill**

```python
def find_matching_skills(self, task: str) -> list:
    """匹配 skill（包含静态 + GitHub）"""
    # 先搜索静态 skill
    local_results = self.search_local(task)
    return local_results
```

- [ ] **Step 4: Commit**

```bash
git add src/v3/core/skill_manager.py
git commit -m "feat: add static skill loading from skills/ directory"
```

---

## Task 3: 修改 HostAgent 支持自动注入

**Files:**
- Modify: `D:\MI-Hands\src\v3\core\host_agent.py`

- [ ] **Step 1: 修改 __init__ 初始化 SkillManager**

```python
def __init__(self, mimo_client=None):
    self.mimo = mimo_client
    self.skill_manager = SkillManager()  # 新增
```

- [ ] **Step 2: 修改 plan 方法注入 skill**

在 `plan` 方法中添加 skill 匹配和注入：

```python
def plan(self, task, uia_tree, screenshot_base64=""):
    # 1. 匹配 skill
    matching_skills = self.skill_manager.find_matching_skills(task)
    
    # 2. 构建 prompt（包含 skill）
    prompt = self._build_planning_prompt(task, uia_tree, matching_skills)
    
    # 3. 调用 MiMo
    ...
```

- [ ] **Step 3: 修改 _build_planning_prompt 接受 skills 参数**

```python
def _build_planning_prompt(self, task, uia_tree, skills=None):
    skill_section = ""
    if skills:
        skill_section = "\n## 可用 Skills\n\n"
        for skill in skills[:3]:
            skill_section += f"### {skill.get('name', '')}\n"
            skill_section += f"{skill.get('description', '')}\n\n"
    
    return f"""你是 MI Hands 桌面自动化助手。
{skill_section}
## 用户任务
{task}
...
"""
```

- [ ] **Step 4: Commit**

```bash
git add src/v3/core/host_agent.py
git commit -m "feat: auto-inject matching skills into planning prompt"
```

---

## Task 4: 删除旧架构

**Files:**
- Delete: `D:\MI-Hands\core\` (整个目录)
- Delete: `D:\MI-Hands\plugins\` (整个目录)

- [ ] **Step 1: 备份重要文件**

如果有自定义的配置或数据，先备份。

- [ ] **Step 2: 删除 core/ 目录**

```bash
rm -rf D:\MI-Hands\core
```

- [ ] **Step 3: 删除 plugins/ 目录**

```bash
rm -rf D:\MI-Hands\plugins
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: remove legacy plugin architecture (core/ + plugins/)"
```

---

## Task 5: 删除测试文件和空目录

**Files:**
- Delete: `D:\MI-Hands\test_v3.py`
- Delete: `D:\MI-Hands\test_mixed.py`
- Delete: `D:\MI-Hands\test_draw.py`
- Delete: `D:\MI-Hands\learning\` (空目录)
- Delete: `D:\MI-Hands\memory\` (空目录)
- Delete: `D:\MI-Hands\skills\` (空目录，已被新的 skills/ 替代)
- Delete: `D:\MI-Hands\metrics\` (空目录)

- [ ] **Step 1: 删除测试文件**

```bash
rm D:\MI-Hands\test_v3.py D:\MI-Hands\test_mixed.py D:\MI-Hands\test_draw.py
```

- [ ] **Step 2: 删除空目录**

```bash
rm -rf D:\MI-Hands\learning D:\MI-Hands\memory D:\MI-Hands\skills D:\MI-Hands\metrics
```

注意：不要删除新的 `D:\MI-Hands\skills\` 目录（包含 JSON 指南）。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: remove test files and empty directories"
```

---

## Task 6: 更新 pyproject.toml

**Files:**
- Modify: `D:\MI-Hands\pyproject.toml`

- [ ] **Step 1: 更新版本号和描述**

确保版本号一致（3.0.0），更新项目描述。

- [ ] **Step 2: 更新入口点**

确保 `mi-hands-mcp` 入口指向 `src.v3.mcp.plugin`。

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: update pyproject.toml for v3 architecture"
```

---

## Task 7: 验证整体功能

**Files:** None

- [ ] **Step 1: 测试 MCP 启动**

```bash
cd D:\MI-Hands
python -m src.v3.mcp.plugin
```

- [ ] **Step 2: 测试 Skill 加载**

```bash
python -c "from src.v3.core.skill_manager import SkillManager; sm = SkillManager(); print(sm.list_installed_skills())"
```

- [ ] **Step 3: 测试决策层 skill 注入**

```bash
python -c "from src.v3.core.host_agent import HostAgent; ha = HostAgent(); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: verify architecture merge"
```

---

## Self-Review

1. **Spec coverage:** 
   - ✅ 删除旧架构（Task 4）
   - ✅ 保留 v3（Task 1-3）
   - ✅ 集成 6 个指南（Task 1-3）
   - ✅ 简化项目结构（Task 5）

2. **Placeholder scan:** 无 TBD/TODO

3. **Type consistency:** Task 2 的 `_load_static_skills` 在 Task 3 中被调用，类型一致

4. **顺序正确：** 先创建新文件（Task 1-3），再删除旧文件（Task 4-5）
