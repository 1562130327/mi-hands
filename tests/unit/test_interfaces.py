"""接口测试"""

import pytest
from core.interfaces import PluginInterface, GuidePluginInterface


def test_plugin_interface_is_abstract():
    """测试 PluginInterface 是抽象类"""
    with pytest.raises(TypeError):
        PluginInterface()


def test_guide_interface_is_abstract():
    """测试 GuidePluginInterface 是抽象类"""
    with pytest.raises(TypeError):
        GuidePluginInterface()
