"""学习状态窗口"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget,
    QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class LearningStatusWindow(QDialog):
    """学习状态窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("学习状态")
        self.setMinimumSize(500, 400)
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("学习状态")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 学习进度
        progress_label = QLabel("学习进度")
        progress_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_text = QLabel("就绪")
        layout.addWidget(self.progress_text)

        # 学习任务列表
        task_label = QLabel("学习任务")
        task_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(task_label)

        self.task_list = QListWidget()
        layout.addWidget(self.task_list)

        # 按钮布局
        button_layout = QHBoxLayout()

        start_btn = QPushButton("开始学习")
        start_btn.clicked.connect(self._start_learning)
        button_layout.addWidget(start_btn)

        stop_btn = QPushButton("停止学习")
        stop_btn.clicked.connect(self._stop_learning)
        button_layout.addWidget(stop_btn)

        clear_btn = QPushButton("清空任务")
        clear_btn.clicked.connect(self._clear_tasks)
        button_layout.addWidget(clear_btn)

        layout.addLayout(button_layout)

        # 底部按钮
        bottom_layout = QHBoxLayout()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _setup_timer(self):
        """设置定时器"""
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_progress)
        self.timer.start(1000)  # 每秒更新一次

    def _start_learning(self):
        """开始学习"""
        self.progress_text.setText("正在学习...")
        self.progress_bar.setValue(0)

        # 添加学习任务
        self.task_list.clear()
        self.task_list.addItem("扫描本地应用...")
        self.task_list.addItem("分析 UIA 树...")
        self.task_list.addItem("联网查资料...")
        self.task_list.addItem("生成操作指南...")

        # TODO: 启动实际学习任务

    def _stop_learning(self):
        """停止学习"""
        self.progress_text.setText("已停止")
        self.timer.stop()

    def _clear_tasks(self):
        """清空任务"""
        self.task_list.clear()
        self.progress_bar.setValue(0)
        self.progress_text.setText("就绪")

    def _update_progress(self):
        """更新进度"""
        current = self.progress_bar.value()
        if current < 100:
            self.progress_bar.setValue(current + 1)
        else:
            self.timer.stop()
            self.progress_text.setText("学习完成")
