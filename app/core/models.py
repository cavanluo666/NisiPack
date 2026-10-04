"""安装包配置数据模型。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

# 安装包界面风格
UI_MODERN = "modern"      # Modern UI 2：标准向导，最通用
UI_SILENT = "silent"      # 极简：只有进度条
UI_CLASSIC = "classic"    # 经典 NSIS 风格

UI_CHOICES = (
    (UI_MODERN, "现代向导（推荐）", "标准的欢迎/目录/进度/完成多页向导"),
    (UI_SILENT, "极简静默", "只显示一个安装进度条，适合快速安装"),
    (UI_CLASSIC, "经典风格", "NSIS 传统外观，兼容老系统"),
)

# 安装范围
SCOPE_ALL_USERS = "all"       # 所有用户，需要管理员权限
SCOPE_CURRENT_USER = "user"   # 仅当前用户，无需提权
SCOPE_CHOICES = (
    (SCOPE_ALL_USERS, "所有用户（需要管理员权限）"),
    (SCOPE_CURRENT_USER, "仅当前用户（无需提权）"),
)

# 压缩算法
# NSIS 的 SetCompressor 只接受 zlib / bzip2 / lzma 三种算法
COMPRESS_CHOICES = (
    ("lzma", "LZMA（体积最小，推荐）"),
    ("solid", "Solid LZMA（多文件时更小，兼容性略差）"),
    ("bzip2", "bzip2（压缩比与速度折中）"),
    ("zlib", "zlib（编译最快，体积最大）"),
)


def _sanitize_name(text: str, fallback: str = "App") -> str:
    """清理成安全的文件名/标识符。"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text or "").strip()
    cleaned = cleaned.replace(" ", "")
    return cleaned or fallback


@dataclass
class ShortcutOptions:
    """快捷方式选项。"""

    desktop: bool = True
    start_menu: bool = True
    quick_launch: bool = False
    start_menu_folder: str = ""


@dataclass
class InstallerConfig:
    """一份完整的安装包配置。"""

    # —— 基本信息 ——
    app_name: str = "我的应用"
    app_version: str = "1.0.0"
    publisher: str = ""
    app_url: str = ""
    description: str = ""

    # —— 文件来源 ——
    source_dir: str = ""
    main_exe: str = ""            # 相对 source_dir 的主程序，用于生成快捷方式
    output_dir: str = ""
    output_name: str = ""         # 留空则按 app_name + version 生成

    # —— 安装行为 ——
    default_install_dir: str = r"$PROGRAMFILES64\${APP_NAME}"
    scope: str = SCOPE_ALL_USERS
    ui_style: str = UI_MODERN
    compress: str = "lzma"
    allow_change_dir: bool = True
    create_uninstaller: bool = True
    run_after_install: bool = True
    request_execution_level: bool = True

    # —— 外观 ——
    icon_path: str = ""
    header_image: str = ""
    welcome_image: str = ""
    uninstall_icon: str = ""
    license_file: str = ""

    # —— 附加 ——
    shortcuts: ShortcutOptions = field(default_factory=ShortcutOptions)
    registry_uninstall: bool = True
    kill_processes: str = ""      # 逗号分隔的进程名，安装前结束

    # —— 产物 ——
    def safe_output_name(self) -> str:
        """确定最终的安装包文件名（不含扩展名）。"""
        if self.output_name.strip():
            base = _sanitize_name(self.output_name)
        else:
            app = _sanitize_name(self.app_name)
            ver = _sanitize_name(self.app_version, "")
            base = f"{app}-{ver}-Setup" if ver else f"{app}-Setup"
        return base

    def exe_file_name(self) -> str:
        """主程序文件名。"""
        if self.main_exe.strip():
            return Path(self.main_exe).name
        return ""

    def install_dir_name(self) -> str:
        """默认安装目录中的子目录名。"""
        return _sanitize_name(self.app_name)

    def start_menu_folder(self) -> str:
        return self.shortcuts.start_menu_folder.strip() or self.app_name

    def to_dict(self) -> dict:
        data = asdict(self)
        data["shortcuts"] = asdict(self.shortcuts)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "InstallerConfig":
        payload = dict(data or {})
        sc = payload.pop("shortcuts", None)
        cfg = cls(**{k: v for k, v in payload.items() if k in cls.__dataclass_fields__})
        if isinstance(sc, dict):
            cfg.shortcuts = ShortcutOptions(
                **{k: v for k, v in sc.items() if k in ShortcutOptions.__dataclass_fields__}
            )
        return cfg

    def validate(self) -> list[str]:
        """返回问题列表，空列表代表可以编译。"""
        problems: list[str] = []
        if not self.app_name.strip():
            problems.append("应用名称不能为空")

        src = Path(self.source_dir) if self.source_dir.strip() else None
        if src is None:
            problems.append("尚未选择要打包的文件夹")
        elif not src.is_dir():
            problems.append(f"源文件夹不存在：{src}")
        elif not any(src.iterdir()):
            problems.append("源文件夹是空的，打包出来会没有内容")

        if self.exclude_empty_source(src):
            pass

        if self.main_exe.strip() and src is not None and src.is_dir():
            target = src / self.main_exe
            if not target.is_file():
                problems.append(f"主程序不存在：{self.main_exe}")

        if not self.output_dir.strip():
            problems.append("尚未选择安装包输出位置")

        for label, path in (
            ("安装包图标", self.icon_path),
            ("向导头图", self.header_image),
            ("欢迎页图", self.welcome_image),
            ("卸载图标", self.uninstall_icon),
            ("许可协议", self.license_file),
        ):
            if path.strip() and not Path(path).is_file():
                problems.append(f"{label}文件不存在：{path}")

        if self.license_file.strip().lower().endswith(".txt"):
            problems.append("许可协议需为 RTF 格式（NSIS 只支持 .rtf）")

        return problems

    @staticmethod
    def exclude_empty_source(src) -> bool:
        return False