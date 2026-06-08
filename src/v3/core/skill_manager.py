"""
SkillManager - 技能管理器

职责：
1. 搜索 GitHub 上的 skill
2. 下载并安装到本地
3. 根据任务匹配 skill
4. 注入 skill prompt 到决策层
5. 支持社区共享

安全策略：
- 下载 skill 时验证格式和内容
- 禁止包含危险操作的 skill
- 限制 skill prompt 长度
"""

import json
import os
import re
from typing import Optional, Set
from pathlib import Path


# Skill 安全限制
MAX_SKILL_PROMPT_LENGTH = 5000  # 最大 prompt 长度
BLOCKED_SKILL_PATTERNS = [
    # 危险操作
    r'os\.system',
    r'subprocess\.call',
    r'subprocess\.run',
    r'exec\s*\(',
    r'eval\s*\(',
    # 文件操作
    r'open\s*\(\s*[\'\"]\/',
    r'os\.remove',
    r'shutil\.rmtree',
    # 系统操作
    r'ctypes\.windll',
    r'win32api',
    r'win32gui',
]


# Skill 存储目录（可通过环境变量覆盖）
SKILLS_DIR = Path(os.environ.get("MI_HANDS_SKILLS_DIR", Path(__file__).parent.parent.parent.parent / "skills"))
REGISTRY_FILE = SKILLS_DIR / "registry.json"


class SkillManager:
    """
    技能管理器

    流程：
    1. 搜索 GitHub 找到相关 skill
    2. 下载 skill 文件
    3. 安装到本地 skills/ 目录
    4. 根据用户任务匹配 skill
    5. 将 skill 的 prompt 注入到决策层
    """

    def __init__(self, skills_dir: str = None):
        """初始化技能管理器"""
        if skills_dir:
            global SKILLS_DIR, REGISTRY_FILE
            SKILLS_DIR = Path(skills_dir)
            REGISTRY_FILE = SKILLS_DIR / "registry.json"
        self._ensure_dirs()
        self._registry = self._load_registry()
        self._static_skills = {}
        self._load_static_skills()

    def _ensure_dirs(self):
        """确保目录存在"""
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_registry(self) -> dict:
        """加载注册表"""
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"skills": [], "version": "1.0.0"}

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

    def _save_registry(self):
        """保存注册表"""
        try:
            with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._registry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存注册表失败: {e}")

    # ============================================================
    # GitHub 搜索
    # ============================================================

    def search_github(self, query: str, limit: int = 5) -> list:
        """
        搜索 GitHub 上的 skill

        搜索关键词：mi-hands-skill, mi-hands-skill-{query}

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            搜索结果列表
        """
        try:
            import urllib.request
            import urllib.parse

            # 构建搜索查询
            search_query = f"mi-hands-skill {query}"
            encoded_query = urllib.parse.quote(search_query)

            # GitHub API
            url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=stars&order=desc&per_page={limit}"

            # 发送请求
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "MI-Hands-SkillManager"
            })

            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            # 解析结果
            results = []
            for repo in data.get("items", []):
                results.append({
                    "name": repo.get("name", ""),
                    "description": repo.get("description", ""),
                    "url": repo.get("html_url", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "topics": repo.get("topics", []),
                    "download_url": repo.get("default_branch", "main"),
                })

            return results

        except Exception as e:
            print(f"GitHub 搜索失败: {e}")
            return []

    def search_local(self, query: str) -> list:
        """
        搜索本地已安装的 skill

        Args:
            query: 搜索关键词

        Returns:
            匹配的 skill 列表
        """
        results = []
        query_lower = query.lower()
        seen_names = set()

        # 搜索注册表中的 skill
        for skill in self._registry.get("skills", []):
            # 搜索名称、描述、标签
            if (query_lower in skill.get("name", "").lower() or
                query_lower in skill.get("description", "").lower() or
                any(query_lower in tag.lower() for tag in skill.get("tags", []))):
                results.append(skill)
                seen_names.add(skill.get("name"))

        # 搜索静态 skill（去重）
        for skill_data in self._static_skills.values():
            name = skill_data.get("name", "")
            if name in seen_names:
                continue
            if (query_lower in name.lower() or
                query_lower in skill_data.get("description", "").lower() or
                any(query_lower in tag.lower() for tag in skill_data.get("tags", []))):
                results.append(skill_data)

        return results

    def search(self, query: str) -> dict:
        """
        综合搜索（本地 + GitHub）

        Args:
            query: 搜索关键词

        Returns:
            {"local": [...], "github": [...]}
        """
        return {
            "local": self.search_local(query),
            "github": self.search_github(query)
        }

    # ============================================================
    # 下载和安装
    # ============================================================

    def download_skill(self, github_url: str) -> Optional[dict]:
        """
        从 GitHub 下载 skill

        支持的 URL 格式：
        - https://github.com/user/repo
        - https://github.com/user/repo/tree/main

        Args:
            github_url: GitHub 仓库 URL

        Returns:
            下载的 skill 数据，失败返回 None
        """
        try:
            import urllib.request
            import urllib.parse

            # 解析 URL
            # https://github.com/user/repo -> API URL
            match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", github_url)
            if not match:
                print(f"无效的 GitHub URL: {github_url}")
                return None

            owner, repo = match.groups()

            # 尝试下载 skill.json
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/skill.json"
            req = urllib.request.Request(raw_url, headers={
                "User-Agent": "MI-Hands-SkillManager"
            })

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    skill_data = json.loads(response.read().decode())
                    return skill_data
            except Exception:
                # 尝试 master 分支
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/skill.json"
                req = urllib.request.Request(raw_url, headers={
                    "User-Agent": "MI-Hands-SkillManager"
                })

                with urllib.request.urlopen(req, timeout=10) as response:
                    skill_data = json.loads(response.read().decode())
                    return skill_data

        except Exception as e:
            print(f"下载 skill 失败: {e}")
            return None

    def install_skill(self, skill_data: dict) -> bool:
        """
        安装 skill 到本地

        Args:
            skill_data: skill 数据（必须包含 name 字段）

        Returns:
            是否安装成功
        """
        try:
            name = skill_data.get("name")
            if not name:
                print("skill 数据缺少 name 字段")
                return False

            # 验证 skill 格式和安全性
            validation = self._validate_skill(skill_data)
            if not validation["valid"]:
                print(f"skill 验证失败: {validation['reason']}")
                return False

            # 保存 skill 文件
            skill_file = SKILLS_DIR / f"{name}.json"
            with open(skill_file, "w", encoding="utf-8") as f:
                json.dump(skill_data, f, ensure_ascii=False, indent=2)

            # 更新注册表
            skill_entry = {
                "name": name,
                "version": skill_data.get("version", "1.0.0"),
                "description": skill_data.get("description", ""),
                "tags": skill_data.get("tags", []),
                "author": skill_data.get("author", ""),
                "file": str(skill_file),
            }

            # 移除旧版本（如果存在）
            self._registry["skills"] = [
                s for s in self._registry["skills"] if s.get("name") != name
            ]

            # 添加新版本
            self._registry["skills"].append(skill_entry)
            self._save_registry()

            print(f"OK: Skill '{name}' installed")
            return True

        except Exception as e:
            print(f"FAIL: Install skill failed: {e}")
            return False

    def _validate_skill(self, skill_data: dict) -> dict:
        """
        验证 skill 数据格式和安全性

        Returns:
            {"valid": bool, "reason": str}
        """
        # 1. 检查必填字段
        required_fields = ["name", "description"]
        for field in required_fields:
            if not skill_data.get(field):
                return {"valid": False, "reason": f"缺少必填字段: {field}"}

        # 2. 验证 name 格式（只允许英文、数字、连字符）
        name = skill_data.get("name", "")
        if not re.match(r'^[a-z0-9\-]+$', name):
            return {"valid": False, "reason": "name 只能包含小写字母、数字和连字符"}

        # 3. 验证 description 长度
        description = skill_data.get("description", "")
        if len(description) > 500:
            return {"valid": False, "reason": "description 太长 (>500 字符)"}

        # 4. 验证 prompt 安全性
        prompt = skill_data.get("prompt", "")
        if len(prompt) > MAX_SKILL_PROMPT_LENGTH:
            return {"valid": False, "reason": f"prompt 太长 (>{MAX_SKILL_PROMPT_LENGTH} 字符)"}

        # 检查危险模式
        for pattern in BLOCKED_SKILL_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                return {"valid": False, "reason": f"prompt 包含危险操作: {pattern}"}

        # 5. 验证 tags 格式
        tags = skill_data.get("tags", [])
        if not isinstance(tags, list):
            return {"valid": False, "reason": "tags 必须是列表"}
        for tag in tags:
            if not isinstance(tag, str):
                return {"valid": False, "reason": "tags 必须是字符串列表"}

        return {"valid": True, "reason": ""}

    # ============================================================
    # Skill 匹配
    # ============================================================

    def find_matching_skills(self, task: str) -> list:
        """
        根据任务匹配本地 skill

        匹配算法：
        1. 关键词匹配（名称、描述、标签）
        2. 语义匹配（prompt 中的关键词）

        Args:
            task: 用户任务描述

        Returns:
            匹配的 skill 列表（按相关度排序）
        """
        task_lower = task.lower()
        matches = []

        # 收集所有候选 skill（注册表 + 静态）
        all_skills = []
        for skill_entry in self._registry.get("skills", []):
            skill_data = self._load_skill(skill_entry.get("name"))
            if skill_data:
                all_skills.append(skill_data)
        for skill_data in self._static_skills.values():
            # 避免重复：如果已通过注册表加载则跳过
            if skill_data.get("name") not in {s.get("name") for s in all_skills}:
                all_skills.append(skill_data)

        for skill_data in all_skills:

            # 计算匹配分数
            score = 0

            # 名称匹配
            if task_lower in skill_data.get("name", "").lower():
                score += 3

            # 描述匹配
            if task_lower in skill_data.get("description", "").lower():
                score += 2

            # 标签匹配
            for tag in skill_data.get("tags", []):
                if task_lower in tag.lower() or tag.lower() in task_lower:
                    score += 1

            # prompt 关键词匹配
            prompt = skill_data.get("prompt", "")
            if prompt:
                # 提取关键词
                keywords = re.findall(r'[\w一-鿿]+', task_lower)
                for keyword in keywords:
                    if keyword in prompt.lower():
                        score += 1

            if score > 0:
                matches.append((score, skill_data))

        # 按分数排序
        matches.sort(key=lambda x: x[0], reverse=True)

        return [skill for _, skill in matches]

    def _load_skill(self, name: str) -> Optional[dict]:
        """加载 skill 数据"""
        if not name:
            return None

        skill_file = SKILLS_DIR / f"{name}.json"
        if skill_file.exists():
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def get_skill_prompt(self, task: str) -> str:
        """
        获取匹配 skill 的 prompt

        Args:
            task: 用户任务

        Returns:
            skill prompt 文本
        """
        matching_skills = self.find_matching_skills(task)

        if not matching_skills:
            return ""

        # 组合所有匹配 skill 的 prompt
        prompts = []
        for skill in matching_skills[:3]:  # 最多 3 个 skill
            skill_prompt = skill.get("prompt", "")
            if skill_prompt:
                prompts.append(f"### Skill: {skill.get('name')}\n{skill_prompt}")

        return "\n\n".join(prompts)

    # ============================================================
    # Skill 管理
    # ============================================================

    def list_installed_skills(self) -> list:
        """列出已安装的 skill"""
        return self._registry.get("skills", [])

    def uninstall_skill(self, name: str) -> bool:
        """卸载 skill"""
        try:
            # 删除文件
            skill_file = SKILLS_DIR / f"{name}.json"
            if skill_file.exists():
                skill_file.unlink()

            # 更新注册表
            self._registry["skills"] = [
                s for s in self._registry["skills"] if s.get("name") != name
            ]
            self._save_registry()

            print(f"OK: Skill '{name}' uninstalled")
            return True

        except Exception as e:
            print(f"FAIL: Uninstall skill failed: {e}")
            return False

    def get_skill_info(self, name: str) -> Optional[dict]:
        """获取 skill 详细信息"""
        return self._load_skill(name)

    # ============================================================
    # 社区共享
    # ============================================================

    def prepare_share(self, skill_name: str) -> Optional[dict]:
        """
        准备分享 skill

        生成分享所需的文件结构：
        - skill.json（skill 数据）
        - README.md（说明文档）

        Args:
            skill_name: skill 名称

        Returns:
            分享数据
        """
        skill_data = self._load_skill(skill_name)
        if not skill_data:
            print(f"Skill '{skill_name}' 不存在")
            return None

        # 生成 README
        readme = self._generate_readme(skill_data)

        return {
            "skill": skill_data,
            "readme": readme,
            "files": {
                "skill.json": json.dumps(skill_data, ensure_ascii=False, indent=2),
                "README.md": readme,
            }
        }

    def _generate_readme(self, skill_data: dict) -> str:
        """生成 skill 的 README 文档"""
        name = skill_data.get("name", "")
        description = skill_data.get("description", "")
        version = skill_data.get("version", "1.0.0")
        author = skill_data.get("author", "")
        tags = skill_data.get("tags", [])
        prompt = skill_data.get("prompt", "")
        examples = skill_data.get("examples", [])

        readme = f"# {name}\n\n"
        readme += f"{description}\n\n"
        readme += f"**Version:** {version}\n"
        if author:
            readme += f"**Author:** {author}\n"
        if tags:
            readme += f"**Tags:** {', '.join(tags)}\n"
        readme += "\n"

        if prompt:
            readme += "## Prompt\n\n"
            readme += f"```\n{prompt}\n```\n\n"

        if examples:
            readme += "## Examples\n\n"
            for ex in examples:
                readme += f"- **Task:** {ex.get('task', '')}\n"
                readme += f"  **Result:** {ex.get('result', '')}\n\n"

        readme += "## Installation\n\n"
        readme += "```bash\n"
        readme += f"# 在 MI Hands MCP 中安装\n"
        readme += f'find_skill("{name}")\n'
        readme += "```\n"

        return readme

    def create_share_repo_data(self, skill_name: str) -> Optional[dict]:
        """
        创建 GitHub 仓库所需的数据

        返回仓库名和文件内容，供用户上传到 GitHub

        Args:
            skill_name: skill 名称

        Returns:
            {"repo_name": "...", "files": {...}}
        """
        share_data = self.prepare_share(skill_name)
        if not share_data:
            return None

        return {
            "repo_name": f"mi-hands-skill-{skill_name}",
            "description": share_data["skill"].get("description", ""),
            "files": share_data["files"],
            "topics": ["mi-hands-skill", "desktop-automation"] + share_data["skill"].get("tags", []),
        }
