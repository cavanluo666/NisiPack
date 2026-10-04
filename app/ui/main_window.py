"""主窗口。"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import compiler, models, nsis_runtime
from ..core.models import COMPRESS_CHOICES, SCOPE_CHOICES, UI_CHOICES, InstallerConfig
from . import theme
from .widgets import Card, DropPathPicker, LabeledRow, LogView, PathPicker, StepIndicator


class CompileWorker(QThread):
    """在后台线程里编译，避免界面卡死。"""

    line = Signal(str, str)      # (级别, 文本)
    finished_ok = Signal(object)  # CompileResult

    def __init__(self, runtime, script_path: Path, output_file: Path, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.script_path = script_path
        self.output_file = output_file
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        result = compiler.compile_script(
            self.runtime,
            self.script_path,
            output_file=self.output_file,
            log_callback=lambda text: self.line.emit(compiler.classify(text), text),
            cancel_event=self._cancel,
        )
        self.finished_ok.emit(result)


class MainWindow(QMainWindow):
    """NisiPack 主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("NisiPack · 安装包制作工具")
        self.resize(1280, 800)
        self.setMinimumSize(980, 660)

        self.cfg = InstallerConfig()
        self.runtime = None
        self.worker: CompileWorker | None = None
        self._last_output: Path | None = None
        self._result = None

        self._build_ui()
        self._wire()
        self._detect_runtime()
        self._update_preview()

    # ------------------------------------------------------------------ 构建
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(12)

        root.addLayout(self._build_header())

        self.steps = StepIndicator(["填写信息", "打包选项", "生成脚本", "编译安装包"])
        root.addWidget(self.steps)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setFrameShape(QFrame.Shape.NoFrame)
        left.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_host = QWidget()
        left_lay = QVBoxLayout(left_host)
        left_lay.setContentsMargins(0, 0, 8, 0)
        left_lay.setSpacing(12)

        left_lay.addWidget(self._card_basic())
        left_lay.addWidget(self._card_source())
        left_lay.addWidget(self._card_install())
        left_lay.addWidget(self._card_appearance())
        left_lay.addWidget(self._card_extra())
        left_lay.addStretch(1)
        left.setWidget(left_host)

        split.addWidget(left)
        split.addWidget(self._build_right())
        split.setStretchFactor(0, 52)
        split.setStretchFactor(1, 48)
        split.setSizes([600, 560])
        root.addWidget(split, 1)

        self.setStatusBar(QStatusBar())
        self._build_menu()

    def _build_header(self) -> QHBoxLayout:
        lay = QHBoxLayout()
        lay.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("安装包制作工具")
        title.setObjectName("Title")
        sub = QLabel("选择文件夹 → 填写信息 → 一键生成 Windows 安装包")
        sub.setObjectName("Subtitle")
        left.addWidget(title)
        left.addWidget(sub)
        lay.addLayout(left)
        lay.addStretch(1)

        self.runtime_badge = QLabel("正在检测编译环境…")
        self.runtime_badge.setObjectName("CardHint")
        self.runtime_badge.setStyleSheet(
            f"background: {theme.BG_ELEV}; border: 1px solid {theme.BORDER};"
            "border-radius: 8px; padding: 7px 12px;"
        )
        lay.addWidget(self.runtime_badge)

        self.btn_compile = QPushButton("开始生成安装包")
        self.btn_compile.setObjectName("Primary")
        self.btn_compile.setMinimumWidth(170)
        lay.addWidget(self.btn_compile)
        return lay

    def _card_basic(self) -> Card:
        card = Card("应用信息", "显示在安装向导和「应用和功能」中")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.in_name = QLineEdit()
        self.in_name.setPlaceholderText("必填，例如：我的工具箱")
        self.in_version = QLineEdit("1.0.0")
        self.in_publisher = QLineEdit()
        self.in_publisher.setPlaceholderText("选填，例如：某某工作室")
        self.in_url = QLineEdit()
        self.in_url.setPlaceholderText("选填，https://…")
        self.in_desc = QLineEdit()
        self.in_desc.setPlaceholderText("选填，一句话介绍")

        for row, (text, widget) in enumerate((
            ("应用名称", self.in_name),
            ("版本号", self.in_version),
            ("开发者", self.in_publisher),
            ("官网", self.in_url),
            ("简介", self.in_desc),
        )):
            lbl = QLabel(text)
            lbl.setObjectName("SectionLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lbl, row // 2, (row % 2) * 2)
            grid.addWidget(widget, row // 2, (row % 2) * 2 + 1)

        card.add_layout(grid)
        return card

    def _card_source(self) -> Card:
        card = Card("要打包的内容", "把文件夹或 exe 直接拖进输入框也可以")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.pick_source = DropPathPicker("dir", "拖入文件夹，或点右侧浏览…")
        self.pick_mainexe = QComboBox()
        self.pick_mainexe.setEditable(True)
        self.pick_mainexe.setMinimumWidth(200)
        self.pick_outdir = PathPicker("dir", "安装包输出到哪里")
        self.in_outname = QLineEdit()
        self.in_outname.setPlaceholderText("留空自动生成，例如：我的工具箱-1.0.0-Setup")

        rows = (
            ("源文件夹", self.pick_source),
            ("主程序", self.pick_mainexe),
            ("输出目录", self.pick_outdir),
            ("文件名", self.in_outname),
        )
        for r, (text, widget) in enumerate(rows):
            lbl = QLabel(text)
            lbl.setObjectName("SectionLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setFixedWidth(64)
            grid.addWidget(lbl, r, 0)
            grid.addWidget(widget, r, 1)

        card.add_layout(grid)

        self.source_summary = QLabel("尚未选择内容")
        self.source_summary.setObjectName("CardHint")
        card.add(self.source_summary)
        return card

    def _card_install(self) -> Card:
        card = Card("安装选项")

        self.cmb_ui = QComboBox()
        for key, label, tip in UI_CHOICES:
            self.cmb_ui.addItem(label, key)
            self.cmb_ui.setItemData(self.cmb_ui.count() - 1, tip, Qt.ItemDataRole.ToolTipRole)

        self.cmb_scope = QComboBox()
        for key, label in SCOPE_CHOICES:
            self.cmb_scope.addItem(label, key)

        self.cmb_compress = QComboBox()
        for key, label in COMPRESS_CHOICES:
            self.cmb_compress.addItem(label, key)

        self.in_installdir = QLineEdit(InstallerConfig.default_install_dir)
        self.in_kill = QLineEdit()
        self.in_kill.setPlaceholderText("选填，如：MyApp.exe，多个用逗号分隔")

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        for r, (text, widget) in enumerate((
            ("向导风格", self.cmb_ui),
            ("安装范围", self.cmb_scope),
            ("压缩方式", self.cmb_compress),
            ("默认目录", self.in_installdir),
            ("安装前关闭", self.in_kill),
        )):
            lbl = QLabel(text)
            lbl.setObjectName("SectionLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setFixedWidth(70)
            grid.addWidget(lbl, r, 0)
            grid.addWidget(widget, r, 1)
        card.add_layout(grid)

        self.chk_desktop = QCheckBox("创建桌面快捷方式")
        self.chk_desktop.setChecked(True)
        self.chk_startmenu = QCheckBox("创建开始菜单项")
        self.chk_startmenu.setChecked(True)
        self.chk_uninstaller = QCheckBox("生成卸载程序")
        self.chk_uninstaller.setChecked(True)
        self.chk_registry = QCheckBox("在「应用和功能」中登记")
        self.chk_registry.setChecked(True)
        self.chk_changedir = QCheckBox("允许用户修改安装目录")
        self.chk_changedir.setChecked(True)

        checks = QGridLayout()
        checks.setHorizontalSpacing(18)
        checks.setVerticalSpacing(6)
        for i, chk in enumerate((self.chk_desktop, self.chk_startmenu,
                                 self.chk_uninstaller, self.chk_registry,
                                 self.chk_changedir)):
            checks.addWidget(chk, i // 2, i % 2)
        card.add_layout(checks)
        return card

    def _card_appearance(self) -> Card:
        card = Card("外观素材", "全部选填；不填就用默认样式")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.pick_icon = PathPicker("file", "安装包图标（.ico）", "图标 (*.ico)")
        self.pick_header = PathPicker("file", "向导右上角小图（.bmp）", "位图 (*.bmp)")
        self.pick_welcome = PathPicker("file", "欢迎页左侧图（.bmp）", "位图 (*.bmp)")
        self.pick_license = PathPicker("file", "许可协议（.rtf）", "RTF (*.rtf)")

        for r, (text, widget) in enumerate((
            ("安装包图标", self.pick_icon),
            ("向导头图", self.pick_header),
            ("欢迎页图", self.pick_welcome),
            ("许可协议", self.pick_license),
        )):
            lbl = QLabel(text)
            lbl.setObjectName("SectionLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setFixedWidth(70)
            grid.addWidget(lbl, r, 0)
            grid.addWidget(widget, r, 1)
        card.add_layout(grid)
        return card

    def _card_extra(self) -> Card:
        card = Card("其它")
        self.chk_run_after = QCheckBox("安装完成后提供「立即运行」选项")
        self.chk_run_after.setChecked(True)
        card.add(self.chk_run_after)

        row = QHBoxLayout()
        self.btn_save_cfg = QPushButton("导出配置")
        self.btn_save_cfg.setObjectName("Ghost")
        self.btn_load_cfg = QPushButton("导入配置")
        self.btn_load_cfg.setObjectName("Ghost")
        self.btn_reset = QPushButton("重置")
        self.btn_reset.setObjectName("Ghost")
        row.addWidget(self.btn_save_cfg)
        row.addWidget(self.btn_load_cfg)
        row.addWidget(self.btn_reset)
        row.addStretch(1)
        card.add_layout(row)
        return card

    def _build_right(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.tabs = QTabWidget()

        # 日志页
        log_page = QWidget()
        log_lay = QVBoxLayout(log_page)
        log_lay.setContentsMargins(10, 10, 10, 10)
        log_lay.setSpacing(8)

        bar = QHBoxLayout()
        self.lbl_status = QLabel("等待开始")
        self.lbl_status.setObjectName("CardTitle")
        bar.addWidget(self.lbl_status)
        bar.addStretch(1)
        self.btn_clear_log = QPushButton("清空")
        self.btn_clear_log.setObjectName("Ghost")
        self.btn_clear_log.setFixedWidth(64)
        bar.addWidget(self.btn_clear_log)
        log_lay.addLayout(bar)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        log_lay.addWidget(self.progress)

        self.log = LogView()
        log_lay.addWidget(self.log, 1)

        self.tabs.addTab(log_page, "编译日志")

        # 脚本预览页
        script_page = QWidget()
        sp = QVBoxLayout(script_page)
        sp.setContentsMargins(10, 10, 10, 10)
        sp.setSpacing(8)
        tip = QLabel("下面是即将交给 NSIS 的脚本，可自行核对")
        tip.setObjectName("CardHint")
        sp.addWidget(tip)
        self.script_view = QPlainTextEdit()
        self.script_view.setObjectName("Log")
        self.script_view.setReadOnly(True)
        self.script_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        sp.addWidget(self.script_view, 1)

        self.tabs.addTab(script_page, "脚本预览")

        # 检查页
        check_page = QWidget()
        cp = QVBoxLayout(check_page)
        cp.setContentsMargins(10, 10, 10, 10)
        cp.setSpacing(8)
        self.check_view = QPlainTextEdit()
        self.check_view.setObjectName("Log")
        self.check_view.setReadOnly(True)
        cp.addWidget(self.check_view, 1)
        self.tabs.addTab(check_page, "配置检查")

        lay.addWidget(self.tabs, 1)

        row = QHBoxLayout()
        self.btn_open_out = QPushButton("打开输出目录")
        self.btn_open_out.setObjectName("Ghost")
        self.btn_run_exe = QPushButton("试运行安装包")
        self.btn_run_exe.setObjectName("Ghost")
        row.addWidget(self.btn_open_out)
        row.addWidget(self.btn_run_exe)
        row.addStretch(1)
        lay.addLayout(row)
        return panel

    def _build_menu(self) -> None:
        bar = self.menuBar()

        m_file = bar.addMenu("文件")
        act_out = QAction("打开输出目录", self)
        act_out.setShortcut(QKeySequence("Ctrl+O"))
        act_out.triggered.connect(self._open_output)
        m_file.addAction(act_out)
        m_file.addSeparator()
        act_quit = QAction("退出", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_help = bar.addMenu("帮助")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    # ------------------------------------------------------------------ 绑定
    def _wire(self) -> None:
        self.in_name.textChanged.connect(self._on_change)
        self.in_version.textChanged.connect(self._on_change)
        self.in_publisher.textChanged.connect(self._on_change)
        self.in_url.textChanged.connect(self._on_change)
        self.in_desc.textChanged.connect(self._on_change)

        self.pick_source.changed.connect(self._on_source_changed)
        self.pick_mainexe.currentTextChanged.connect(self._on_change)
        self.pick_outdir.changed.connect(self._on_change)
        self.in_outname.textChanged.connect(self._on_change)

        self.cmb_ui.currentIndexChanged.connect(self._on_change)
        self.cmb_scope.currentIndexChanged.connect(self._on_change)
        self.cmb_compress.currentIndexChanged.connect(self._on_change)
        self.in_installdir.textChanged.connect(self._on_change)
        self.in_kill.textChanged.connect(self._on_change)

        for chk in (self.chk_desktop, self.chk_startmenu, self.chk_uninstaller,
                    self.chk_registry, self.chk_changedir, self.chk_run_after):
            chk.toggled.connect(self._on_change)

        for picker in (self.pick_icon, self.pick_header,
                       self.pick_welcome, self.pick_license):
            picker.changed.connect(self._on_change)

        self.btn_compile.clicked.connect(self._start_compile)
        self.btn_clear_log.clicked.connect(self.log.clear_log)
        self.btn_open_out.clicked.connect(self._open_output)
        self.btn_run_exe.clicked.connect(self._run_installer)
        self.btn_save_cfg.clicked.connect(self._save_config)
        self.btn_load_cfg.clicked.connect(self._load_config)
        self.btn_reset.clicked.connect(self._reset)

    # ------------------------------------------------------------- 配置同步
    def _collect(self) -> InstallerConfig:
        cfg = self.cfg
        cfg.app_name = self.in_name.text().strip()
        cfg.app_version = self.in_version.text().strip()
        cfg.publisher = self.in_publisher.text().strip()
        cfg.app_url = self.in_url.text().strip()
        cfg.description = self.in_desc.text().strip()

        cfg.source_dir = self.pick_source.value()
        cfg.main_exe = self.pick_mainexe.currentText().strip()
        cfg.output_dir = self.pick_outdir.value()
        cfg.output_name = self.in_outname.text().strip()

        cfg.ui_style = self.cmb_ui.currentData()
        cfg.scope = self.cmb_scope.currentData()
        cfg.compress = self.cmb_compress.currentData()
        cfg.default_install_dir = self.in_installdir.text().strip()
        cfg.kill_processes = self.in_kill.text().strip()

        cfg.shortcuts.desktop = self.chk_desktop.isChecked()
        cfg.shortcuts.start_menu = self.chk_startmenu.isChecked()
        cfg.create_uninstaller = self.chk_uninstaller.isChecked()
        cfg.registry_uninstall = self.chk_registry.isChecked()
        cfg.allow_change_dir = self.chk_changedir.isChecked()
        cfg.run_after_install = self.chk_run_after.isChecked()

        cfg.icon_path = self.pick_icon.value()
        cfg.header_image = self.pick_header.value()
        cfg.welcome_image = self.pick_welcome.value()
        cfg.license_file = self.pick_license.value()
        return cfg

    def _on_change(self) -> None:
        self._update_preview()

    def _on_source_changed(self, path: str) -> None:
        self._scan_source(path)
        self._update_preview()

    def _scan_source(self, path: str) -> None:
        """扫描源目录，填充主程序候选并提示体积。"""
        self.pick_mainexe.blockSignals(True)
        current = self.pick_mainexe.currentText()
        self.pick_mainexe.clear()

        folder = Path(path) if path else None
        if folder is None or not folder.is_dir():
            self.pick_mainexe.blockSignals(False)
            self.source_summary.setText("尚未选择内容")
            return

        try:
            entries = list(folder.iterdir())
        except OSError as exc:
            self.source_summary.setText(f"无法读取目录：{exc}")
            self.pick_mainexe.blockSignals(False)
            return

        exes = sorted(p.name for p in entries if p.is_file() and p.suffix.lower() == ".exe")
        self.pick_mainexe.addItems(exes)
        if current and current in exes:
            self.pick_mainexe.setCurrentText(current)
        elif exes:
            self.pick_mainexe.setCurrentIndex(0)
        self.pick_mainexe.blockSignals(False)

        total = 0
        count = 0
        for p in folder.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
                    count += 1
            except OSError:
                continue

        dirs = sum(1 for p in entries if p.is_dir())
        self.source_summary.setText(
            f"共 {count} 个文件（{nsis_runtime.human_size(total)}），"
            f"{dirs} 个子文件夹，{len(exes)} 个可执行文件"
        )

    # ------------------------------------------------------------- 预览刷新
    def _update_preview(self) -> None:
        cfg = self._collect()
        problems = cfg.validate()

        # 步骤指示
        if not cfg.source_dir:
            self.steps.set_current(0)
        elif problems:
            self.steps.set_current(1)
        elif self._last_output and self._last_output.is_file():
            self.steps.set_current(3)
        else:
            self.steps.set_current(2)

        # 脚本预览
        try:
            nsi = Path(cfg.output_dir or ".") / "_preview.nsi"
            self.script_view.setPlainText(models_module_build(cfg, nsi))
        except Exception as exc:  # 预览失败不影响主流程
            self.script_view.setPlainText(f"（预览生成失败：{exc}）")

        # 检查页
        lines = []
        lines.append("【配置检查】")
        if problems:
            for p in problems:
                lines.append(f"  ✗ {p}")
        else:
            lines.append("  ✓ 所有必填项已就绪")

        lines.append("")
        lines.append("【编译环境】")
        if self.runtime is not None:
            lines.append(f"  ✓ {self.runtime.describe()}")
            for name, ok in nsis_runtime.check_plugins(self.runtime).items():
                lines.append(f"  {'✓' if ok else '·'} 插件 {name}")
        else:
            lines.append("  ✗ 未找到可用的 NSIS")

        lines.append("")
        lines.append("【预生成文件名】")
        lines.append(f"  {cfg.safe_output_name()}.exe")

        lines.append("")
        lines.append("【安装目录】")
        lines.append(f"  {cfg.default_install_dir}")

        self.check_view.setPlainText("\n".join(lines))

        can_build = not problems and self.runtime is not None
        self.btn_compile.setEnabled(can_build and self.worker is None)

    # ------------------------------------------------------------- 环境检测
    def _detect_runtime(self) -> None:
        try:
            self.runtime = nsis_runtime.ensure_runtime(
                progress=lambda m: self.log.append(m, "muted")
            )
            ver = compiler.probe_version(self.runtime)
            tag = "内置" if self.runtime.bundled else "系统"
            self.runtime_badge.setText(f"NSIS v{ver} · {tag}")
            self.runtime_badge.setStyleSheet(
                f"background: rgba(62,207,142,0.12); border: 1px solid {theme.OK};"
                f"color: {theme.OK}; border-radius: 8px; padding: 7px 12px;"
            )
            self.log.append(f"编译环境就绪：NSIS v{ver}（{tag}）", "ok")
        except nsis_runtime.NsisNotFoundError as exc:
            self.runtime = None
            self.runtime_badge.setText("编译环境缺失")
            self.runtime_badge.setStyleSheet(
                f"background: rgba(255,107,107,0.12); border: 1px solid {theme.ERR};"
                f"color: {theme.ERR}; border-radius: 8px; padding: 7px 12px;"
            )
            self.log.append(str(exc), "error")
        self._update_preview()

    # --------------------------------------------------------------- 编译
    def _start_compile(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            self.lbl_status.setText("正在中止…")
            return

        cfg = self._collect()
        problems = cfg.validate()
        if problems:
            QMessageBox.warning(self, "还不能开始", "\n".join(f"· {p}" for p in problems))
            return
        if self.runtime is None:
            QMessageBox.critical(self, "缺少编译环境", "未找到 NSIS，无法生成安装包。")
            return

        out_dir = Path(cfg.output_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "输出目录不可用", str(exc))
            return

        ok, msg = nsis_runtime.free_space_ok(out_dir, 200 * 1024 * 1024)
        if not ok:
            QMessageBox.warning(self, "空间提示", msg)

        script_path = out_dir / f"{cfg.safe_output_name()}.nsi"
        output_file = out_dir / f"{cfg.safe_output_name()}.exe"
        script = models_module_build(cfg, script_path)
        from ..core.nsis_script import write_script_file

        write_script_file(script, script_path)
        self.log.clear_log()
        self.log.append(f"脚本已写入 {script_path}", "muted")
        self.tabs.setCurrentIndex(0)

        self.progress.setVisible(True)
        self.lbl_status.setText("正在编译…")
        self.btn_compile.setText("中止")
        self.btn_compile.setObjectName("Danger")
        self._restyle(self.btn_compile)

        self.worker = CompileWorker(self.runtime, script_path, output_file, self)
        self.worker.line.connect(self._on_log_line)
        self.worker.finished_ok.connect(self._on_compiled)
        self.worker.start()
        self._update_preview()

    def _restyle(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _on_log_line(self, level: str, text: str) -> None:
        self.log.append(text, level)

    def _on_compiled(self, result) -> None:
        self.progress.setVisible(False)
        self.btn_compile.setText("开始生成安装包")
        self.btn_compile.setObjectName("Primary")
        self._restyle(self.btn_compile)
        self.worker = None
        self._result = result

        if result.cancelled:
            self.lbl_status.setText("已中止")
            self.log.append("编译已被用户中止", "warning")
        elif result.success:
            self._last_output = result.output_file
            size = nsis_runtime.human_size(result.output_size())
            self.lbl_status.setText(f"完成 · {size}")
            self.log.append(f"安装包已生成：{result.output_file}", "ok")
            self.steps.set_current(3)
        else:
            self.lbl_status.setText("生成失败")
            self.log.append("生成失败，请查看上面的错误信息", "error")

        self._update_preview()

    # --------------------------------------------------------------- 动作
    def _open_output(self) -> None:
        cfg = self._collect()
        target = Path(cfg.output_dir) if cfg.output_dir else Path.home()
        if self._last_output and self._last_output.is_file():
            target = self._last_output.parent
        if not target.exists():
            QMessageBox.information(self, "目录不存在", f"{target} 还不存在。")
            return
        try:
            if os.name == "nt":
                os.startfile(str(target))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except OSError as exc:
            QMessageBox.warning(self, "无法打开", str(exc))

    def _run_installer(self) -> None:
        if not (self._last_output and self._last_output.is_file()):
            QMessageBox.information(self, "还没有安装包", "请先生成安装包。")
            return
        try:
            os.startfile(str(self._last_output))  # noqa: S606
        except OSError as exc:
            QMessageBox.warning(self, "无法运行", str(exc))

    def _save_config(self) -> None:
        cfg = self._collect()
        path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", f"{cfg.safe_output_name()}.nisipack.json",
            "配置文件 (*.json)"
        )
        if not path:
            return
        import json

        try:
            Path(path).write_text(
                json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.log.append(f"配置已导出：{path}", "ok")
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def _load_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "配置文件 (*.json)"
        )
        if not path:
            return
        import json

        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            cfg = InstallerConfig.from_dict(data)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "导入失败", f"配置文件无法解析：{exc}")
            return

        self.cfg = cfg
        self.in_name.setText(cfg.app_name)
        self.in_version.setText(cfg.app_version)
        self.in_publisher.setText(cfg.publisher)
        self.in_url.setText(cfg.app_url)
        self.in_desc.setText(cfg.description)

        self.pick_source.set_value(cfg.source_dir)
        self.pick_outdir.set_value(cfg.output_dir)
        self.in_outname.setText(cfg.output_name)
        self._scan_source(cfg.source_dir)
        if cfg.main_exe:
            self.pick_mainexe.setCurrentText(cfg.main_exe)

        self._select_data(self.cmb_ui, cfg.ui_style)
        self._select_data(self.cmb_scope, cfg.scope)
        self._select_data(self.cmb_compress, cfg.compress)
        self.in_installdir.setText(cfg.default_install_dir)
        self.in_kill.setText(cfg.kill_processes)

        self.chk_desktop.setChecked(cfg.shortcuts.desktop)
        self.chk_startmenu.setChecked(cfg.shortcuts.start_menu)
        self.chk_uninstaller.setChecked(cfg.create_uninstaller)
        self.chk_registry.setChecked(cfg.registry_uninstall)
        self.chk_changedir.setChecked(cfg.allow_change_dir)
        self.chk_run_after.setChecked(cfg.run_after_install)

        self.pick_icon.set_value(cfg.icon_path)
        self.pick_header.set_value(cfg.header_image)
        self.pick_welcome.set_value(cfg.welcome_image)
        self.pick_license.set_value(cfg.license_file)

        self.log.append(f"配置已导入：{path}", "ok")
        self._update_preview()

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _reset(self) -> None:
        if QMessageBox.question(self, "确认重置", "将清空所有已填内容，继续吗？") \
                != QMessageBox.StandardButton.Yes:
            return
        self.cfg = InstallerConfig()
        self.in_name.clear()
        self.in_version.setText("1.0.0")
        self.in_publisher.clear()
        self.in_url.clear()
        self.in_desc.clear()
        self.pick_source.set_value("")
        self.pick_mainexe.clear()
        self.pick_outdir.set_value("")
        self.in_outname.clear()
        self.in_installdir.setText(InstallerConfig.default_install_dir)
        self.in_kill.clear()
        self.pick_icon.set_value("")
        self.pick_header.set_value("")
        self.pick_welcome.set_value("")
        self.pick_license.set_value("")
        self.source_summary.setText("尚未选择内容")
        self.log.clear_log()
        self.log.append("已重置", "muted")
        self._update_preview()

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "关于 NisiPack",
            "<h3>NisiPack</h3>"
            "<p>Windows 安装包制作工具，基于 NSIS。</p>"
            "<p>内置 NSIS 运行时，无需额外安装任何环境。</p>"
            "<p style='color:#98a0b3'>用 PySide6 构建界面，Nuitka 编译发布。</p>",
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None:
            self.worker.cancel()
            self.worker.wait(3000)
        super().closeEvent(event)


def models_module_build(cfg: InstallerConfig, script_path: Path) -> str:
    """薄封装，避免在界面里直接依赖脚本生成模块的细节。"""
    from ..core.nsis_script import build_script

    return build_script(cfg, script_path, script_path)