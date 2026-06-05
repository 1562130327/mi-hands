"""本地文件扫描器测试"""

import pytest
import tempfile
import os
from plugins.guide_manager.local_scanner import LocalScanner


@pytest.fixture
def scanner():
    return LocalScanner()


def test_scan_install_directory(scanner):
    """测试扫描安装目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        with open(os.path.join(tmpdir, "README.txt"), "w") as f:
            f.write("This is a test application")

        with open(os.path.join(tmpdir, "config.ini"), "w") as f:
            f.write("[app]\nname=TestApp")

        result = scanner.scan_directory(tmpdir)

        assert "readme_files" in result
        assert "config_files" in result
        assert len(result["readme_files"]) == 1
        assert len(result["config_files"]) == 1


def test_extract_app_info(scanner):
    """测试提取应用信息"""
    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.txt")
        with open(readme_path, "w") as f:
            f.write("TestApp v1.0.0\nA test application for testing")

        info = scanner.extract_info(readme_path)

        assert "name" in info
        assert "version" in info
