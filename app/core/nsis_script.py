"""根据配置生成 NSIS 脚本（.nsi）。

生成器只负责产出脚本文本，不负责调用编译器；
这样可以先把脚本落盘给用户检查，再决定是否编译。
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import (
    SCOPE_ALL_USERS,
    UI_CLASSIC,
    UI_MODERN,
    UI_SILENT,
    InstallerConfig,
)

# 形如 ${MACRO} 或 $VAR：NSIS 宏 / 变量引用，必须原样保留
_RE_NSIS_REF = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*")


def _esc_literal(text: str) -> str:
    """转义“纯字面文本”。

    用户填写的应用名、版本号等内容属于字面量，
    其中的 $ 必须写成 $$ 才不会被 NSIS 误当成变量，引号同理。
    """
    out = str(text or "")
    out = out.replace("$", "$$")
    out = out.replace('"', "$\\" + '"')
    return out


def _esc(text: str) -> str:
    """转义可能混有 NSIS 变量引用的字符串。

    已经写好的 ${APP_NAME}、$INSTDIR 会被完整保留，
    只有其余字面量中的 $ 与引号才转义。
    """
    src = str(text or "")
    parts: list[str] = []
    pos = 0
    for m in _RE_NSIS_REF.finditer(src):
        parts.append(_esc_literal(src[pos:m.start()]))
        parts.append(m.group(0))
        pos = m.end()
    parts.append(_esc_literal(src[pos:]))
    return "".join(parts)


def _q(text: str) -> str:
    """带引号的 NSIS 字符串，保留其中的宏与变量引用。"""
    return '"' + _esc(text) + '"'


def _lit(text: str) -> str:
    """带引号的纯字面量字符串，其中的 $ 一律转义。"""
    return '"' + _esc_literal(text) + '"'



class ScriptBuilder:
    """增量式构建 .nsi 脚本。"""

    def __init__(self) -> None:
        self._lines: list[str] = []

    def raw(self, line: str = "") -> "ScriptBuilder":
        self._lines.append(line)
        return self

    def cmd(self, command: str, *args: str) -> "ScriptBuilder":
        parts = [command] + [str(a) for a in args]
        self._lines.append(" ".join(parts))
        return self

    def section(self, name: str, flags: str = "") -> "ScriptBuilder":
        head = f'Section {flags} {_q(name)}'.replace("  ", " ")
        self._lines.append(head)
        return self

    def section_end(self) -> "ScriptBuilder":
        self._lines.append("SectionEnd")
        return self

    def function(self, name: str) -> "ScriptBuilder":
        self._lines.append(f"Function {name}")
        return self

    def function_end(self) -> "ScriptBuilder":
        self._lines.append("FunctionEnd")
        return self

    def var(self, name: str) -> "ScriptBuilder":
        self._lines.append(f"Var {name}")
        return self

    def comment(self, text: str) -> "ScriptBuilder":
        self._lines.append(f"; {text}")
        return self

    def blank(self) -> "ScriptBuilder":
        self._lines.append("")
        return self

    def text(self) -> str:
        return "\r\n".join(self._lines) + "\r\n"


def _icon_line(keyword: str, path: str) -> str | None:
    if path and Path(path).is_file():
        return f'{keyword} {_q(path)}'
    return None


def build_script(cfg: InstallerConfig, nsi_path: Path, script_path: Path) -> str:
    """生成完整 .nsi 脚本内容。

    nsi_path   —— 输入文件树，打包时使用
    script_path—— 本脚本自身将保存的位置，用于 OutFile 相对路径
    """
    b = ScriptBuilder()
    src = Path(cfg.source_dir)
    out_file = Path(cfg.output_dir) / f"{cfg.safe_output_name()}.exe"

    b.comment("=" * 60)
    b.comment(f" 由 NisiPack 安装包制作工具生成")
    b.comment(f" 应用：{cfg.app_name}  {cfg.app_version}")
    b.comment("=" * 60)
    b.blank()

    # —— 宏定义必须放在最前面，后面的 InstallDir 等会引用它们 ——
    predefine_macros(b, cfg)
    b.blank()

    # —— 基本属性 ——
    b.cmd("Unicode", "true")
    b.cmd("Name", _lit(cfg.app_name))
    b.cmd("OutFile", _lit(str(out_file)))
    b.cmd("InstallDir", _q(cfg.default_install_dir))
    b.blank()

    if cfg.request_execution_level and cfg.scope == SCOPE_ALL_USERS:
        b.cmd("RequestExecutionLevel", "admin")
    else:
        b.cmd("RequestExecutionLevel", "user")
    b.blank()

    # —— 压缩 ——
    b.raw(_compressor_line(cfg.compress))
    b.blank()

    # —— 图标 ——
    if cfg.icon_path and Path(cfg.icon_path).is_file():
        b.cmd("Icon", _lit(cfg.icon_path))
    if cfg.uninstall_icon and Path(cfg.uninstall_icon).is_file():
        b.cmd("UninstallIcon", _lit(cfg.uninstall_icon))
    b.blank()

    # —— 版本信息（决定文件属性里的详细信息） ——
    b.cmd("VIProductVersion", _lit(_vi_version(cfg.app_version)))
    # /FileVersion 需最先声明。
    # 注：同时启用中英双语时，NSIS 会对未补齐的语言给出 warning 9100，
    #     这是外观性提示，不影响安装包功能。
    b.cmd("VIAddVersionKey", "//FileVersion", _lit(cfg.app_version))
    b.cmd("VIAddVersionKey", "//ProductVersion", _lit(cfg.app_version))
    b.cmd("VIAddVersionKey", "//ProductName", _lit(cfg.app_name))
    b.cmd("VIAddVersionKey", "//FileDescription", _lit(cfg.description or cfg.app_name))
    b.cmd("VIAddVersionKey", "//CompanyName", _lit(cfg.publisher or cfg.app_name))
    b.cmd("VIAddVersionKey", "//LegalCopyright", _lit(cfg.publisher or cfg.app_name))

    # —— Modern UI 外观 ——
    include_ui(b, cfg)
    define_paths(b, cfg)
    define_macros(b, cfg)

    # —— 变量与页面 ——
    b.var("StartMenuFolder")
    b.blank()
    pages(b, cfg)

    # 卸载向导页必须紧跟在安装页之后、MUI_LANGUAGE 之前插入
    if cfg.create_uninstaller:
        uninstall_callbacks(b, cfg)
    b.blank()

    b.comment("—— 语言 ——")
    b.cmd("!insertmacro", "MUI_LANGUAGE", _lit("SimpChinese"))
    b.cmd("!insertmacro", "MUI_LANGUAGE", _lit("English"))
    b.blank()

    # —— 安装段 ——
    install_section(b, cfg, src)
    b.blank()
    if cfg.create_uninstaller:
        uninstall_section(b, cfg)
        b.blank()
        define_uninstaller_writer(b, cfg)
    b.blank()

    # 清理与结束回调
    cleanup_callbacks(b, cfg)

    return b.text()


def _compressor_line(choice: str) -> str:
    """把界面选项翻译成合法的 SetCompressor 指令。

    NSIS 语法为 SetCompressor [/FINAL] [/SOLID] (zlib|bzip2|lzma)，
    其中 /SOLID 只是修饰符，必须与算法一起给出。
    """
    mapping = {
        "lzma": "SetCompressor /FINAL lzma",
        "solid": "SetCompressor /SOLID lzma",
        "bzip2": "SetCompressor /FINAL bzip2",
        "zlib": "SetCompressor /FINAL zlib",
    }
    return mapping.get(choice, "SetCompressor /FINAL lzma")


def _vi_version(version: str) -> str:
    """把 1.2.3 转成 VIProductVersion 需要的 1.2.3.0 四段格式。"""
    parts = [p for p in str(version).replace("-", ".").split(".") if p.strip()]
    nums: list[str] = []
    for p in parts[:4]:
        digits = "".join(ch for ch in p if ch.isdigit())
        nums.append(digits or "0")
    while len(nums) < 4:
        nums.append("0")
    return ".".join(nums[:4])


def predefine_macros(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """定义全局宏。

    必须最先输出：InstallDir、快捷方式、注册表等都用 ${...} 引用它们，
    NSIS 是顺序解析的，宏定义晚于使用就会变成字面量。
    """
    b.comment("—— 全局宏（务必最先定义） ——")
    b.cmd("!define", "APP_NAME", _lit(cfg.app_name))
    b.cmd("!define", "APP_VERSION", _lit(cfg.app_version))
    b.cmd("!define", "APP_PUBLISHER", _lit(cfg.publisher or cfg.app_name))
    b.cmd("!define", "APP_ID", _lit(cfg.safe_output_name()))
    b.cmd("!define", "APP_EXE", _lit(cfg.exe_file_name()))


def include_ui(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """按风格引入界面宏。"""
    if cfg.ui_style == UI_CLASSIC:
        b.comment("经典风格：使用传统 UI")
        return
    b.comment("现代界面（Modern UI 2）")
    b.cmd("!include", _q("MUI2.nsh"))
    b.blank()


def define_paths(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """定义可复用路径常量。"""
    b.comment("—— 卸载信息注册表位置 ——")
    # 依赖前面已定义的 ${APP_ID}，因此不能再重复定义 APP_* 系列宏
    uninst_key = (
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
    )
    b.cmd("!define", "UNINST_KEY", _q(uninst_key))
    b.blank()


def define_macros(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """定义界面文案宏。"""
    b.comment("—— 界面文案 ——")
    b.cmd("!define", "MUI_ABORTWARNING")
    if cfg.ui_style == UI_MODERN:
        header = _icon_line("!define MUI_HEADERIMAGE_BITMAP", cfg.header_image)
        if header:
            b.raw(header)
            b.cmd("!define", "MUI_HEADERIMAGE")
        welcome = _icon_line("!define MUI_WELCOMEFINISHPAGE_BITMAP", cfg.welcome_image)
        if welcome:
            b.raw(welcome)
        if cfg.icon_path and Path(cfg.icon_path).is_file():
            b.cmd("!define", "MUI_ICON", _q(cfg.icon_path))
        if cfg.uninstall_icon and Path(cfg.uninstall_icon).is_file():
            b.cmd("!define", "MUI_UNICON", _q(cfg.uninstall_icon))

        b.cmd("!define", "MUI_WELCOMEPAGE_TITLE", _lit(f"欢迎安装 {cfg.app_name}"))
        desc = cfg.description or f"即将在你的电脑上安装 {cfg.app_name}。"
        b.cmd("!define", "MUI_WELCOMEPAGE_TEXT", _lit(desc))
        # 只有确实有主程序时才提供"立即运行"
        if cfg.exe_file_name():
            b.cmd("!define", "MUI_FINISHPAGE_RUN", _lit(r"$INSTDIR\${APP_EXE}"))
            b.cmd("!define", "MUI_FINISHPAGE_RUN_TEXT", _lit(f"运行 {cfg.app_name}"))
        # 这两个宏必须成对出现，只定义其一会导致 NSIS 报 unknown variable
        if cfg.app_url:
            b.cmd("!define", "MUI_FINISHPAGE_LINK", _lit(f"访问官网"))
            b.cmd("!define", "MUI_FINISHPAGE_LINK_LOCATION", _lit(cfg.app_url))
        b.blank()


def pages(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """插入安装向导页面。"""
    b.comment("—— 安装向导页面 ——")
    if cfg.ui_style == UI_SILENT:
        b.cmd("!insertmacro", "MUI_PAGE_DIRECTORY")
        b.cmd("!insertmacro", "MUI_PAGE_INSTFILES")
        return

    if cfg.ui_style == UI_CLASSIC:
        b.cmd("Page", "directory")
        b.cmd("Page", "instfiles")
        return

    b.cmd("!insertmacro", "MUI_PAGE_WELCOME")
    if cfg.license_file and Path(cfg.license_file).is_file():
        b.cmd("!insertmacro", "MUI_PAGE_LICENSE", _lit(cfg.license_file))
    if cfg.allow_change_dir:
        b.cmd("!insertmacro", "MUI_PAGE_DIRECTORY")
    b.cmd("!insertmacro", "MUI_PAGE_INSTFILES")
    b.cmd("!insertmacro", "MUI_PAGE_FINISH")


def install_section(b: ScriptBuilder, cfg: InstallerConfig, src: Path) -> None:
    """主安装段：解压文件 + 写注册表 + 建快捷方式。"""
    b.comment("=" * 60)
    b.comment(" 安装")
    b.comment("=" * 60)
    b.section("${APP_NAME}", "")

    b.comment("先确定 Shell 变量上下文，决定快捷方式写到哪个用户")
    if cfg.scope == SCOPE_ALL_USERS:
        b.raw("SetShellVarContext all")
    else:
        b.raw("SetShellVarContext current")
    b.blank()

    b.comment("设置安装目录到用户选择的路径")
    b.cmd("SetOutPath", _q("$INSTDIR"))
    b.blank()

    # 结束占用文件的进程。
    # 这里用 NSIS 自带的 nsExec 调 taskkill，避免依赖第三方 nsProcess 插件。
    if cfg.kill_processes.strip():
        names = [n.strip() for n in cfg.kill_processes.split(",") if n.strip()]
        if names:
            b.comment("结束可能占用文件的进程")
            for name in names:
                safe = _esc_literal(name)
                cmd = 'nsExec::ExecToLog \'"$SYSDIR\\taskkill.exe" /F /IM "' + safe + '\"\''
                b.raw(cmd)
                b.raw("Pop $R0")
            b.raw("Sleep 600")
            b.blank()

    b.comment("复制程序文件（递归打包整个文件夹）")
    b.cmd("File", "/r", _q(str(src / "*.*")))
    b.blank()

    # 卸载程序
    if cfg.create_uninstaller:
        b.comment("生成卸载程序")
        b.raw('WriteUninstaller "$INSTDIR\\Uninstall.exe"')
        b.blank()

    # 快捷方式
    if cfg.shortcuts.start_menu:
        b.comment("开始菜单快捷方式")
        # 必须先给运行时变量赋值，否则 $StartMenuFolder 为空，快捷方式会落到开始菜单根目录
        b.raw(f'StrCpy $StartMenuFolder "{_esc_literal(cfg.start_menu_folder())}"')
        b.raw(
            'CreateDirectory "$SMPROGRAMS\\$StartMenuFolder"'
        )
        b.raw(
            'CreateShortCut "$SMPROGRAMS\\$StartMenuFolder\\${APP_NAME}.lnk" '
            '"$INSTDIR\\${APP_EXE}"'
        )
        if cfg.create_uninstaller:
            b.raw(
                'CreateShortCut "$SMPROGRAMS\\$StartMenuFolder\\卸载 ${APP_NAME}.lnk" '
                '"$INSTDIR\\Uninstall.exe"'
            )
        b.blank()

    if cfg.shortcuts.desktop:
        b.comment("桌面快捷方式")
        b.raw(
            'CreateShortCut "$DESKTOP\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXE}"'
        )
        b.blank()

    if cfg.shortcuts.quick_launch:
        b.comment("快速启动栏快捷方式")
        b.raw(
            'CreateShortCut "$QUICKLAUNCH\\${APP_NAME}.lnk" "$INSTDIR\\${APP_EXE}"'
        )
        b.blank()

    # 注册表
    if cfg.registry_uninstall:
        b.comment("写入“添加或删除程序”所需信息")
        root = "HKLM" if cfg.scope == SCOPE_ALL_USERS else "HKCU"
        b.raw(f'WriteRegStr {root} "${{UNINST_KEY}}" "DisplayName" "${{APP_NAME}}"')
        b.raw(
            f'WriteRegStr {root} "${{UNINST_KEY}}" "DisplayVersion" '
            f'"{_esc(cfg.app_version)}"'
        )
        b.raw(
            f'WriteRegStr {root} "${{UNINST_KEY}}" "UninstallString" '
            '"$\\"$INSTDIR\\Uninstall.exe$\\""'
        )
        b.raw(
            f'WriteRegStr {root} "${{UNINST_KEY}}" "InstallLocation" "$INSTDIR"'
        )
        b.raw(
            f'WriteRegStr {root} "${{UNINST_KEY}}" "DisplayIcon" '
            '"$INSTDIR\\Uninstall.exe"'
        )
        b.raw(f'WriteRegDWORD {root} "${{UNINST_KEY}}" "NoModify" 1')
        b.raw(f'WriteRegDWORD {root} "${{UNINST_KEY}}" "NoRepair" 1')
        if cfg.publisher:
            b.raw(
                f'WriteRegStr {root} "${{UNINST_KEY}}" "Publisher" '
                f'"{_esc(cfg.publisher)}"'
            )
        if cfg.app_url:
            b.raw(
                f'WriteRegStr {root} "${{UNINST_KEY}}" "URLInfoAbout" '
                f'"{_esc(cfg.app_url)}"'
            )
        size = _dir_size_kb(src)
        b.raw(f'WriteRegDWORD {root} "${{UNINST_KEY}}" "EstimatedSize" {size}')

        b.comment("登记应用路径，便于其它程序定位")
        b.raw(
            f'WriteRegStr {root} "Software\\${{APP_ID}}" "InstallPath" "$INSTDIR"'
        )
        b.raw(
            f'WriteRegStr {root} "Software\\${{APP_ID}}" "Version" '
            f'"{_esc(cfg.app_version)}"'
        )
        b.blank()

    b.section_end()


def _dir_size_kb(src: Path) -> int:
    """估算源目录大小（KB），用于控制面板显示。"""
    total = 0
    try:
        for f in src.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        return 0
    return max(1, total // 1024)


def uninstall_section(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """卸载段。"""
    b.comment("=" * 60)
    b.comment(" 卸载")
    b.comment("=" * 60)
    b.raw('Section "Uninstall"')
    b.raw("  SetShellVarContext all" if cfg.scope == SCOPE_ALL_USERS else "  SetShellVarContext current")
    b.blank()

    if cfg.kill_processes.strip():
        names = [n.strip() for n in cfg.kill_processes.split(",") if n.strip()]
        for name in names:
            safe = _esc_literal(name)
            cmd = 'nsExec::ExecToLog \'"$SYSDIR\\taskkill.exe" /F /IM "' + safe + '\"\''
            b.raw(cmd)
            b.raw("  Pop $R0")
        if names:
            b.raw("  Sleep 600")
        b.blank()

    b.comment("删除安装目录下的全部文件")
    b.raw('  RMDir /r "$INSTDIR"')
    b.blank()

    if cfg.shortcuts.start_menu:
        b.comment("删除开始菜单文件夹（递归，避免残留空目录）")
        b.raw('  Delete "$SMPROGRAMS\\$StartMenuFolder\\${APP_NAME}.lnk"')
        b.raw('  Delete "$SMPROGRAMS\\$StartMenuFolder\\卸载 ${APP_NAME}.lnk"')
        b.raw('  RMDir /r "$SMPROGRAMS\\$StartMenuFolder"')
    if cfg.shortcuts.desktop:
        b.raw('  Delete "$DESKTOP\\${APP_NAME}.lnk"')
    if cfg.shortcuts.quick_launch:
        b.raw('  Delete "$QUICKLAUNCH\\${APP_NAME}.lnk"')
    b.blank()

    if cfg.registry_uninstall:
        b.comment("清理注册表")
        root = "HKLM" if cfg.scope == SCOPE_ALL_USERS else "HKCU"
        b.raw(f'  DeleteRegKey {root} "${{UNINST_KEY}}"')
        b.raw(f'  DeleteRegKey {root} "Software\\${{APP_ID}}"')
        b.blank()

    b.raw("SectionEnd")


def uninstall_callbacks(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """卸载界面回调。"""
    b.comment("—— 卸载向导页面（必须早于 MUI_LANGUAGE） ——")
    if cfg.ui_style == UI_MODERN:
        b.raw("!insertmacro MUI_UNPAGE_CONFIRM")
        b.raw("!insertmacro MUI_UNPAGE_INSTFILES")


def define_uninstaller_writer(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """定义卸载时清理临时文件的宏占位，便于后续扩展。"""
    b.comment("—— 卸载程序数据 ——")
    b.cmd("!define", "UNINSTALL_APP_NAME", _lit(cfg.app_name))


def cleanup_callbacks(b: ScriptBuilder, cfg: InstallerConfig) -> None:
    """安装前后回调（预留）。"""
    b.blank()
    b.comment("=" * 60)
    b.comment(" 结束")
    b.comment("=" * 60)

def write_script_file(script: str, path: Path) -> Path:
    """把脚本写盘。

    NSIS 只有在文件带 UTF-8 BOM 时才会正确识别其中的中文；
    无 BOM 的中文（哪怕只是注释）会触发 "Bad text encoding" 而编译失败。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" 防止 Python 把 \n 再转义一次，脚本内部已使用 \r\n
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write(script)
    return path
