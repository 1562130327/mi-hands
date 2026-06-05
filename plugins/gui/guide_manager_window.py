"""操作指南管理窗口"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget,
    QTextEdit, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class GuideManagerWindow(QDialog):
    """操作指南管理窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("操作指南管理")
        self.setMinimumSize(600, 400)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("操作指南管理")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 主布局
        main_layout = QHBoxLayout()

        # 左侧列表
        left_layout = QVBoxLayout()

        self.guide_list = QListWidget()
        self.guide_list.currentItemChanged.connect(self._on_guide_selected)
        left_layout.addWidget(self.guide_list)

        # 列表按钮
        list_button_layout = QHBoxLayout()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_guides)
        list_button_layout.addWidget(refresh_btn)

        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self._import_guide)
        list_button_layout.addWidget(import_btn)

        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_guide)
        list_button_layout.addWidget(export_btn)

        left_layout.addLayout(list_button_layout)

        main_layout.addLayout(left_layout)

        # 右侧详情
        right_layout = QVBoxLayout()

        self.detail_label = QLabel("操作指南详情")
        self.detail_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        right_layout.addWidget(self.detail_label)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        right_layout.addWidget(self.detail_text)

        # 详情按钮
        detail_button_layout = QHBoxLayout()

        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(self._edit_guide)
        detail_button_layout.addWidget(edit_btn)

        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self._delete_guide)
        detail_button_layout.addWidget(delete_btn)

        right_layout.addLayout(detail_button_layout)

        main_layout.addLayout(right_layout)

        layout.addLayout(main_layout)

        # 底部按钮
        bottom_layout = QHBoxLayout()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _refresh_guides(self):
        """刷新操作指南列表"""
        self.guide_list.clear()
        # TODO: 从 guide_manager 获取指南列表
        self.guide_list.addItem("微信")
        self.guide_list.addItem("Chrome")
        self.guide_list.addItem("VS Code")
        self.guide_list.addItem("记事本")
        self.guide_list.addItem("计算器")

    def _on_guide_selected(self, current, previous):
        """操作指南选中"""
        if current:
            self.detail_label.setText(f"操作指南: {current.text()}")
            # TODO: 从 guide_manager 获取指南详情
            self.detail_text.setText(f"这是 {current.text()} 的操作指南详情...")

    def _import_guide(self):
        """导入操作指南"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入操作指南",
            "",
            "YAML 文件 (*.yaml);;所有文件 (*)"
        )
        if file_path:
            QMessageBox.information(self, "导入", f"导入: {file_path}")

    def _export_guide(self):
        """导出操作指南"""
        current_item = self.guide_list.currentItem()
        if current_item:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出操作指南",
                f"{current_item.text()}.yaml",
                "YAML 文件 (*.yaml);;所有文件 (*)"
            )
            if file_path:
                QMessageBox.information(self, "导出", f"导出到: {file_path}")
        else:
            QMessageBox.warning(self, "提示", "请先选择一个操作指南")

    def _edit_guide(self):
        """编辑操作指南"""
        current_item = self.guide_list.currentItem()
        if current_item:
            QMessageBox.information(self, "编辑", f"编辑 {current_item.text()}")
        else:
            QMessageBox.warning(self, "提示", "请先选择一个操作指南")

    def _delete_guide(self):
        """删除操作指南"""
        current_item = self.guide_list.currentItem()
        if current_item:
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除 {current_item.text()} 吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.guide_list.takeItem(self.guide_list.row(current_item))
        else:
            QMessageBox.warning(self, "提示", "请先选择一个操作指南")
