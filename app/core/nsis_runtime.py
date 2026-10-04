"""NSIS 运行时定位与释放。

优先使用内嵌(随 exe 打包)的 NSIS 发行版；找不到时回落到系统安装。
程序完全独立运行，不依赖用户机器上安装 NSIS。
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_BUNDLED_DIRNAME = "NSIS"

_SYSTEM_CANDIDATES = (
    r"C:\Program Files (x86)\NSIS\makensis.exe",
    r"C:\Program Files\NSIS\makensis.exe",
)


class NsisNotFoundError(RuntimeError):
    """找不到可用的 makensis.exe。"""


@dataclass(frozen=True)
class NsisRuntime:
    """一条可用的 NSIS 运行时。"""

    makensis: Path
    root: Path
    bundled: bool

    def describe(self) -> str:
        tag = "内置" if self.bundled else "系统"
        return f"{tag} NSIS · {self.makensis}"


def _frozen_base():
    """打包形态下的资源根目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if "__compiled__" in globals():
        return Path(sys.executable).resolve().parent
    return None


def _candidate_roots():
    """按优先级返回 (可能含 NSIS 的根目录, 是否内置)。"""
    out = []

    base = _frozen_base()
    if base is not None:
        out.append((base, True))
        out.append((base / "vendor", True))

    here = Path(__file__).resolve()
    for parent in here.parents:
        vendor = parent / "vendor"
        if vendor.is_dir():
            out.append((vendor, True))
            break
        if (parent / _BUNDLED_DIRNAME / "makensis.exe").is_file():
            out.append((parent, True))
            break

    out.append((Path(tempfile.gettempdir()) / "NisiPackRuntime", True))
    return out


def _find_in(root, bundled):
    """在 root 下定位 NSIS，支持 root 本身即 NSIS 目录。"""
    direct = root / "makensis.exe"
    if direct.is_file():
        return NsisRuntime(makensis=direct, root=root, bundled=bundled)

    nested = root / _BUNDLED_DIRNAME
    nested_exe = nested / "makensis.exe"
    if nested_exe.is_file():
        return NsisRuntime(makensis=nested_exe, root=nested, bundled=bundled)
    return None


def find_nsis():
    """定位 NSIS：优先内置，其次系统安装。"""
    for root, bundled in _candidate_roots():
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue
        found = _find_in(root, bundled)
        if found is not None:
            return found

    for raw in _SYSTEM_CANDIDATES:
        path = Path(raw)
        if path.is_file():
            return NsisRuntime(makensis=path, root=path.parent, bundled=False)

    raise NsisNotFoundError("未找到 NSIS 运行时（内置资源缺失，系统也未安装 NSIS）。")


def ensure_runtime(progress=None):
    """确保 NSIS 可用并返回其位置。"""
    runtime = find_nsis()
    if progress is not None:
        progress(f"已就绪：{runtime.describe()}")
    return runtime


def check_plugins(runtime):
    """检查常用插件是否存在，供自检展示。"""
    plugins_root = runtime.root / "Plugins"
    # 这几个是标准 NSIS 发行版自带的常用插件
    wanted = ("nsExec", "System", "nsDialogs", "Math", "UserInfo")
    result = {}
    for name in wanted:
        hit = False
        if plugins_root.is_dir():
            for arch in plugins_root.iterdir():
                if not arch.is_dir():
                    continue
                if (arch / f"{name}.dll").is_file() or (arch / name).is_dir():
                    hit = True
                    break
        result[name] = hit
    return result


def human_size(num):
    """人类可读的体积字符串。"""
    value = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def free_space_ok(target, need_bytes):
    """粗略检查输出盘剩余空间。"""
    probe = Path(target)
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        usage = shutil.disk_usage(probe)
    except OSError as exc:
        return True, f"无法检测磁盘空间：{exc}"
    if usage.free < need_bytes:
        return False, (
            f"磁盘空间可能不足：需约 {human_size(need_bytes)}，"
            f"可用 {human_size(usage.free)}"
        )
    return True, "磁盘空间充足"
