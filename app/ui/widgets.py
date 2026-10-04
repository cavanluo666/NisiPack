"""可复用的界面组件。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme


class Card(QFrame):
    """带标题的圆角卡片容器。"""

    def __init__(self, title: str = "", hint: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(16, 14, 16, 16)
        self._outer.setSpacing(10)

        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        if title:
            lbl = QLabel(title)
            lbl.setObjectName("CardTitle")
            self.header.addWidget(lbl)
            self.title_label = lbl
        else:
            self.title_label = None
        if hint:
            self.hint_label = QLabel(hint)
            self.hint_label.setObjectName("CardHint")
            self.header.addWidget(self.hint_label)
        else:
            self.hint_label = None
        self.header.addStretch(1)
        self._outer.addLayout(self.header)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self._outer.addLayout(self.body)

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)

    def add_header_widget(self, widget: QWidget) -> QWidget:
        """把控件放到卡片标题行右侧。"""
        self.header.addWidget(widget)
        return widget


class PathPicker(QWidget):
    """一行式路径选择器：输入框 + 浏览按钮。"""

    changed = Signal(str)

    def __init__(
        self,
        mode: str = "dir",              # dir | file | save
        placeholder: str = "",
        file_filter: str = "所有文件 (*.*)",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.mode = mode
        self.file_filter = file_filter

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(True)
        self.edit.textChanged.connect(self.changed.emit)
        lay.addWidget(self.edit, 1)

        self.button = QPushButton("浏览…")
        self.button.setObjectName("Ghost")
        self.button.setFixedWidth(78)
        self.button.clicked.connect(self._browse)
        lay.addWidget(self.button)

    def _browse(self) -> None:
        current = self.edit.text().strip()
        start = str(Path(current).parent if current and Path(current).is_file() else current)

        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(self, "选择文件夹", start)
        elif self.mode == "save":
            path, _ = QFileDialog.getSaveFileName(
                self, "保存为", current or start, self.file_filter
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择文件", start, self.file_filter
            )
        if path:
            self.edit.setText(path)

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, text: str) -> None:
        self.edit.setText(text or "")


class DropLineEdit(QLineEdit):
    """支持把文件/文件夹拖进来的输入框。"""

    dropped = Signal(str)

    def __init__(self, mode: str = "dir", parent: QWidget | None = None):
        super().__init__(parent)
        self.mode = mode
        self.setAcceptDrops(True)
        self._normal_style = ""
        self._active_style = (
            f"border: 1px dashed {theme.ACCENT};"
            f"background: {theme.ACCENT_SOFT};"
            "border-radius: 8px;"
        )

    def _first_path(self, event) -> str | None:
        if not event.mimeData().hasUrls():
            return None
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if not local:
                continue
            if self.mode == "dir" and Path(local).is_dir():
                return local
            if self.mode == "file" and Path(local).is_file():
                return local
            if self.mode == "any":
                return local
        return None

    def dragEnterEvent(self, event) -> None:
        if self._first_path(event):
            event.acceptProposedAction()
            self.setStyleSheet(self._active_style)
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self._normal_style)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self.setStyleSheet(self._normal_style)
        path = self._first_path(event)
        if path:
            self.setText(path)
            self.dropped.emit(path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class DropPathPicker(PathPicker):
    """PathPicker 的拖拽增强版。"""

    def __init__(self, mode: str = "dir", placeholder: str = "",
                 file_filter: str = "所有文件 (*.*)", parent: QWidget | None = None):
        super().__init__(mode, placeholder, file_filter, parent)
        # 用支持拖拽的输入框替换默认输入框
        drop = DropLineEdit("dir" if mode == "dir" else "file")
        drop.setPlaceholderText(placeholder)
        drop.setClearButtonEnabled(True)
        drop.textChanged.connect(self.changed.emit)
        lay = self.layout()
        lay.replaceWidget(self.edit, drop)
        self.edit.deleteLater()
        self.edit = drop
        self.edit.dropped.connect(self.changed.emit)


class LogView(QPlainTextEdit):
    """带级别配色的日志输出面板。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Log")
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMaximumBlockCount(5000)
        self._formats = {
            "info": self._make_format("#c8d0e0"),
            "muted": self._make_format(theme.FG_MUTE),
            "ok": self._make_format(theme.OK),
            "warning": self._make_format(theme.WARN),
            "error": self._make_format(theme.ERR),
            "accent": self._make_format(theme.ACCENT_HI),
        }

    @staticmethod
    def _make_format(color: str) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        return fmt

    def append(self, text: str, level: str = "info") -> None:
        fmt = self._formats.get(level, self._formats["info"])
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text + "\n", fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def clear_log(self) -> None:
        self.clear()


class StepIndicator(QWidget):
    """顶部步骤指示条。"""

    def __init__(self, steps: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.steps = steps
        self.current = 0
        self.setFixedHeight(34)

    def set_current(self, index: int) -> None:
        self.current = max(0, min(index, len(self.steps) - 1))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme.BG))

        n = len(self.steps)
        if n == 0:
            return

        pad = 4
        seg_w = (self.width() - 2 * pad) / n
        y = self.height() // 2
        r = 11

        font = QFont(self.font())
        font.setPointSizeF(9.0)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        for i, name in enumerate(self.steps):
            x = pad + i * seg_w
            done = i < self.current
            active = i == self.current

            cx = x + r / 2 + 2

            # 先画到下一段的连接线，避免盖住文字
            if i < n - 1:
                line_y = y
                painter.setPen(QColor(theme.OK if done else theme.BORDER))
                next_cx = pad + (i + 1) * seg_w + r / 2 + 2
                painter.drawLine(int(cx + r), int(line_y),
                                 int(next_cx - r), int(line_y))

            # 圆点
            painter.setPen(Qt.PenStyle.NoPen)
            if active:
                painter.setBrush(QColor(theme.ACCENT))
            elif done:
                painter.setBrush(QColor(theme.OK))
            else:
                painter.setBrush(QColor(theme.BORDER_HI))
            painter.drawEllipse(cx - r / 2, y - r / 2, r, r)

            # 圆点里的序号
            painter.setPen(QColor("#ffffff") if (active or done) else QColor(theme.FG_MUTE))
            painter.drawText(int(cx - r / 2), int(y - r / 2), int(r), int(r),
                             Qt.AlignmentFlag.AlignCenter, str(i + 1))

            # 文字放在圆点右侧，可用宽度受限于本段
            painter.setPen(QColor(theme.FG) if (active or done) else QColor(theme.FG_MUTE))
            text_x = cx + r / 2 + 8
            avail = seg_w - r - 12
            elided = metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(avail))
            painter.drawText(int(text_x), 0, int(avail), self.height(),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             elided)
        painter.end()


class LabeledRow(QWidget):
    """左标签 + 右控件的一行布局。"""

    def __init__(self, label: str, widget: QWidget, label_width: int = 92,
                 parent: QWidget | None = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lbl = QLabel(label)
        lbl.setObjectName("SectionLabel")
        lbl.setFixedWidth(label_width)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(lbl)
        lay.addWidget(widget, 1)
        self.label = lbl
        self.widget = widget