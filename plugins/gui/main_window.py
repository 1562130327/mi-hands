"""主窗口"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QTabWidget,
    QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MI Hands v2.0")
        self.setMinimumSize(800, 600)
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()

    def _setup_ui(self):
        """设置 UI"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        layout = QVBoxLayout(central_widget)

        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # 添加操作指南标签页
        guide_tab = self._create_guide_tab()
        tab_widget.addTab(guide_tab, "操作指南")

        # 添加学习标签页
        learning_tab = self._create_learning_tab()
        tab_widget.addTab(learning_tab, "学习")

        # 添加设置标签页
        settings_tab = self._create_settings_tab()
        tab_widget.addTab(settings_tab, "设置")

    def _create_guide_tab(self) -> QWidget:
        """创建操作指南标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 标题
        title = QLabel("操作指南库")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # 操作指南列表
        self.guide_list = QListWidget()
        layout.addWidget(self.guide_list)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_guides)
        button_layout.addWidget(refresh_btn)

        # 查看按钮
        view_btn = QPushButton("查看详情")
        view_btn.clicked.connect(self._view_guide)
        button_layout.addWidget(view_btn)

        # 学习按钮
        learn_btn = QPushButton("学习新应用")
        learn_btn.clicked.connect(self._learn_app)
        button_layout.addWidget(learn_btn)

        layout.addLayout(button_layout)

        return tab

    def _create_learning_tab(self) -> QWidget:
        """创建学习标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 标题
        title = QLabel("学习状态")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # 学习状态列表
        self.learning_list = QListWidget()
        layout.addWidget(self.learning_list)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 开始学习按钮
        start_btn = QPushButton("开始学习")
        start_btn.clicked.connect(self._start_learning)
        button_layout.addWidget(start_btn)

        # 停止学习按钮
        stop_btn = QPushButton("停止学习")
        stop_btn.clicked.connect(self._stop_learning)
        button_layout.addWidget(stop_btn)

        layout.addLayout(button_layout)

        return tab

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 标题
        title = QLabel("设置")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # GitHub 同步设置
        github_label = QLabel("GitHub 同步")
        github_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(github_label)

        # 同步按钮
        sync_layout = QHBoxLayout()

        pull_btn = QPushButton("拉取更新")
        pull_btn.clicked.connect(self._pull_updates)
        sync_layout.addWidget(pull_btn)

        push_btn = QPushButton("推送指南")
        push_btn.clicked.connect(self._push_guide)
        sync_layout.addWidget(push_btn)

        layout.addLayout(sync_layout)

        # 鼠标设置
        mouse_label = QLabel("鼠标管理")
        mouse_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(mouse_label)

        # 暂停/继续按钮
        mouse_layout = QHBoxLayout()

        pause_btn = QPushButton("暂停")
        pause_btn.clicked.connect(self._pause_mouse)
        mouse_layout.addWidget(pause_btn)

        resume_btn = QPushButton("继续")
        resume_btn.clicked.connect(self._resume_mouse)
        mouse_layout.addWidget(resume_btn)

        layout.addLayout(mouse_layout)

        return tab

    def _setup_menu(self):
        """设置菜单"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        file_menu.addAction("退出", self.close)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        help_menu.addAction("关于", self._show_about)

    def _setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _refresh_guides(self):
        """刷新操作指南列表"""
        self.status_bar.showMessage("正在刷新...")
        # TODO: 从 guide_manager 获取指南列表
        self.guide_list.clear()
        self.guide_list.addItem("微信")
        self.guide_list.addItem("Chrome")
        self.guide_list.addItem("VS Code")
        self.guide_list.addItem("记事本")
        self.guide_list.addItem("计算器")
        self.status_bar.showMessage("刷新完成")

    def _view_guide(self):
        """查看操作指南详情"""
        current_item = self.guide_list.currentItem()
        if current_item:
            QMessageBox.information(self, "操作指南", f"查看 {current_item.text()} 的详情")
        else:
            QMessageBox.warning(self, "提示", "请先选择一个操作指南")

    def _learn_app(self):
        """学习新应用"""
        QMessageBox.information(self, "学习", "请选择要学习的应用")

    def _start_learning(self):
        """开始学习"""
        self.status_bar.showMessage("开始学习...")
        # TODO: 启动学习任务

    def _stop_learning(self):
        """停止学习"""
        self.status_bar.showMessage("停止学习")
        # TODO: 停止学习任务

    def _pull_updates(self):
        """拉取更新"""
        self.status_bar.showMessage("正在拉取更新...")
        # TODO: 调用 GitHub 同步插件
        self.status_bar.showMessage("拉取完成")

    def _push_guide(self):
        """推送指南"""
        self.status_bar.showMessage("正在推送指南...")
        # TODO: 调用 GitHub 同步插件
        self.status_bar.showMessage("推送完成")

    def _pause_mouse(self):
        """暂停鼠标"""
        self.status_bar.showMessage("鼠标已暂停")
        # TODO: 调用鼠标管理插件

    def _resume_mouse(self):
        """继续鼠标"""
        self.status_bar.showMessage("鼠标已继续")
        # TODO: 调用鼠标管理插件

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 MI Hands",
            "MI Hands v2.0\n\n"
            "MiMo 桌面控制 SDK\n"
            "插件架构 + 操作指南库 + 社区协作\n\n"
            "© 2026 MI Hands Team"
        )
