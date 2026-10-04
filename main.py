"""NisiPack 启动入口。"""
from __future__ import annotations

import sys
from pathlib import Path

# 源码运行时确保项目根目录在 sys.path 上
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.ui import theme
from app.ui.main_window import MainWindow


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("NisiPack")
    app.setApplicationDisplayName("NisiPack 安装包制作工具")
    app.setStyle("Fusion")
    app.setStyleSheet(theme.stylesheet())

    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
