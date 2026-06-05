"""GUI 插件实现"""

import sys
from typing import Dict, List, Any, Optional
from core.interfaces import PluginInterface


class GUIPlugin(PluginInterface):
    """GUI 插件"""

    name = "gui"
    version = "1.0.0"
    dependencies = []

    def __init__(self):
        self._app = None
        self._main_window = None
        self._initialized = False

    async def initialize(self) -> bool:
        """初始化插件"""
        try:
            # 延迟导入 PyQt
            try:
                from PyQt6.QtWidgets import QApplication
                from PyQt6.QtCore import Qt

                # 创建应用
                if not QApplication.instance():
                    self._app = QApplication(sys.argv)
                else:
                    self._app = QApplication.instance()

                self._initialized = True
                return True
            except ImportError:
                print("PyQt6 未安装，GUI 功能不可用")
                return False
        except Exception as e:
            print(f"GUI 插件初始化失败: {e}")
            return False

    async def shutdown(self):
        """关闭插件"""
        if self._app:
            self._app.quit()

    async def get_status(self) -> Dict[str, Any]:
        """获取插件状态"""
        return {
            "name": self.name,
            "version": self.version,
            "initialized": self._initialized,
            "pyqt_available": self._initialized
        }

    async def show_main_window(self):
        """显示主窗口"""
        if not self._initialized:
            print("GUI 未初始化")
            return

        try:
            from .main_window import MainWindow
            self._main_window = MainWindow()
            self._main_window.show()
            self._app.exec()
        except Exception as e:
            print(f"显示主窗口失败: {e}")

    async def show_guide_manager(self):
        """显示操作指南管理窗口"""
        if not self._initialized:
            print("GUI 未初始化")
            return

        try:
            from .guide_manager_window import GuideManagerWindow
            window = GuideManagerWindow()
            window.show()
            self._app.exec()
        except Exception as e:
            print(f"显示操作指南管理窗口失败: {e}")

    async def show_learning_status(self):
        """显示学习状态窗口"""
        if not self._initialized:
            print("GUI 未初始化")
            return

        try:
            from .learning_status_window import LearningStatusWindow
            window = LearningStatusWindow()
            window.show()
            self._app.exec()
        except Exception as e:
            print(f"显示学习状态窗口失败: {e}")
