"""界面主题：配色、字体与 QSS 样式表。

设计取向：深色 + 低饱和蓝紫强调色，卡片式分组，圆角与细边框，
避免 Qt 默认控件的"90 年代"观感。
"""
from __future__ import annotations

# —— 配色 ——
BG = "#14161c"           # 窗口底色
BG_ELEV = "#1b1e27"      # 卡片/输入框底色
BG_ELEV2 = "#232733"     # 悬浮态
BORDER = "#2c313f"       # 常规边框
BORDER_HI = "#3d445a"    # 聚焦边框

FG = "#e6e9f0"           # 主文字
FG_DIM = "#98a0b3"       # 次要文字
FG_MUTE = "#6b7385"      # 更弱的提示

ACCENT = "#5b8cff"       # 主强调色
ACCENT_HI = "#7aa2ff"    # 悬浮
ACCENT_DIM = "#3f6bd9"   # 按下
ACCENT_SOFT = "#1e2a45"  # 强调色的浅背景

OK = "#3ecf8e"
WARN = "#f5b544"
ERR = "#ff6b6b"
LOG_BG = "#101319"


def stylesheet() -> str:
    """返回全局 QSS。"""
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    outline: none;
}}

QWidget {{
    background: {BG};
    color: {FG};
}}

QMainWindow, QDialog {{
    background: {BG};
}}

/* ---------- 卡片 ---------- */
QFrame#Card {{
    background: {BG_ELEV};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QLabel#CardTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {FG};
}}

QLabel#CardHint {{
    color: {FG_MUTE};
    font-size: 12px;
}}

QLabel#SectionLabel {{
    color: {FG_DIM};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#Title {{
    font-size: 20px;
    font-weight: 700;
    color: {FG};
}}

QLabel#Subtitle {{
    color: {FG_DIM};
    font-size: 13px;
}}

/* ---------- 输入控件 ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
    background: {BG_ELEV2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    color: {FG};
    selection-background-color: {ACCENT_DIM};
    selection-color: #ffffff;
}}

QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
    border-color: {BORDER_HI};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
    background: {BG_ELEV2};
}}

QLineEdit:disabled, QComboBox:disabled {{
    color: {FG_MUTE};
    background: {BG_ELEV};
}}

QLineEdit[readOnly="true"] {{
    color: {FG_DIM};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {FG_DIM};
    margin-right: 6px;
}}

QComboBox::down-arrow:hover {{
    border-top-color: {FG};
}}

QComboBox QAbstractItemView {{
    background: {BG_ELEV2};
    border: 1px solid {BORDER_HI};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {FG};
    outline: none;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {BG_ELEV2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    color: {FG};
    font-weight: 500;
}}

QPushButton:hover {{
    background: {BORDER};
    border-color: {BORDER_HI};
}}

QPushButton:pressed {{
    background: {BG_ELEV};
}}

QPushButton:disabled {{
    color: {FG_MUTE};
    background: {BG_ELEV};
    border-color: {BORDER};
}}

QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #ffffff;
    font-weight: 600;
    padding: 10px 22px;
}}

QPushButton#Primary:hover {{
    background: {ACCENT_HI};
    border-color: {ACCENT_HI};
}}

QPushButton#Primary:pressed {{
    background: {ACCENT_DIM};
}}

QPushButton#Primary:disabled {{
    background: {BORDER};
    border-color: {BORDER};
    color: {FG_MUTE};
}}

QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {FG_DIM};
}}

QPushButton#Ghost:hover {{
    color: {FG};
    border-color: {BORDER_HI};
    background: {BG_ELEV2};
}}

QPushButton#Danger {{
    background: transparent;
    border: 1px solid {ERR};
    color: {ERR};
}}

QPushButton#Danger:hover {{
    background: rgba(255, 107, 107, 0.12);
}}

/* ---------- 复选框 ---------- */
QCheckBox, QRadioButton {{
    spacing: 8px;
    color: {FG};
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border: 1px solid {BORDER_HI};
    background: {BG_ELEV2};
}}

QCheckBox::indicator {{
    border-radius: 5px;
}}

QRadioButton::indicator {{
    border-radius: 9px;
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {ACCENT};
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {BG_ELEV};
    border-color: {BORDER};
}}

/* ---------- 分组框 ---------- */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    color: {FG_DIM};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {FG_DIM};
    font-weight: 600;
}}

/* ---------- 日志区 ---------- */
QPlainTextEdit#Log {{
    background: {LOG_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px;
    font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
    font-size: 12px;
    color: #c8d0e0;
}}

/* ---------- 进度条 ---------- */
QProgressBar {{
    background: {BG_ELEV2};
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 6px;
}}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_HI};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {FG_MUTE};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_HI};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* ---------- 其他 ---------- */
QToolTip {{
    background: {BG_ELEV2};
    color: {FG};
    border: 1px solid {BORDER_HI};
    border-radius: 6px;
    padding: 6px 8px;
}}

QSplitter::handle {{
    background: {BORDER};
}}

QSplitter::handle:hover {{
    background: {ACCENT};
}}

QStatusBar {{
    background: {BG_ELEV};
    color: {FG_DIM};
    border-top: 1px solid {BORDER};
}}

QStatusBar::item {{
    border: none;
}}

QMenu {{
    background: {BG_ELEV2};
    border: 1px solid {BORDER_HI};
    border-radius: 8px;
    padding: 5px;
}}

QMenu::item {{
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
}}

QMenu::item:selected {{
    background: {ACCENT_SOFT};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: {FG_DIM};
    padding: 8px 18px;
    margin-right: 4px;
    border-radius: 8px;
    font-weight: 500;
}}

QTabBar::tab:hover {{
    color: {FG};
    background: {BG_ELEV2};
}}

QTabBar::tab:selected {{
    color: {FG};
    background: {ACCENT_SOFT};
}}
"""