"""用 Nuitka 把 NisiPack 编译为独立的单文件 exe。

产物不依赖用户机器上的 Python、PySide6 或 NSIS：
NSIS 运行时已随包附带，首次运行会释放到临时目录。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "NisiPack"
ENTRY = ROOT / "main.py"
VENDOR = ROOT / "vendor" / "NSIS"
DIST = ROOT / "dist"


def check_prereqs() -> list[str]:
    problems: list[str] = []
    if not ENTRY.is_file():
        problems.append(f"找不到入口文件：{ENTRY}")
    if not (VENDOR / "makensis.exe").is_file():
        problems.append(f"缺少内置 NSIS：{VENDOR}")
    try:
        import PySide6  # noqa: F401
    except ImportError:
        problems.append("未安装 PySide6，请先执行 pip install PySide6")
    return problems


def build_command() -> list[str]:
    """组装 Nuitka 命令。"""
    sep = ";" if sys.platform == "win32" else ":"
    return [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        # 名称与版本信息
        "--company-name=NisiPack",
        f"--product-name={APP_NAME}",
        f"--file-version=1.0.0.0",
        f"--product-version=1.0.0",
        f"--file-description=NisiPack 安装包制作工具",
        # 把整个 NSIS 运行时塞进发布目录。
        # 注意：--include-data-dir 默认会跳过可执行文件，
        # 而 makensis.exe 正是核心，必须显式用 --include-data-files 补上。
        f"--include-data-dir={VENDOR}=vendor/NSIS",
        # 可执行文件、DLL 都要单独声明，data-dir 会跳过它们
        f"--include-data-files={VENDOR}/*.exe=vendor/NSIS/",
        f"--include-data-files={VENDOR}/Bin/*.exe=vendor/NSIS/Bin/",
        f"--include-data-files={VENDOR}/Bin/*.dll=vendor/NSIS/Bin/",
        f"--include-data-files={VENDOR}/Plugins/x86-unicode/*.dll=vendor/NSIS/Plugins/x86-unicode/",
        f"--include-data-files={VENDOR}/Plugins/x86-ansi/*.dll=vendor/NSIS/Plugins/x86-ansi/",
        # 排除明显用不到的大块依赖，减小体积
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=pydoc",
        "--nofollow-import-to=PySide6.QtWebEngineCore",
        "--nofollow-import-to=PySide6.QtWebEngineWidgets",
        "--nofollow-import-to=PySide6.Qt3DCore",
        "--nofollow-import-to=PySide6.QtMultimedia",
        "--nofollow-import-to=PySide6.QtQuick",
        "--nofollow-import-to=PySide6.QtQml",
        "--nofollow-import-to=PySide6.QtCharts",
        "--nofollow-import-to=PySide6.QtDataVisualization",
        "--nofollow-import-to=PySide6.QtNetworkAuth",
        "--nofollow-import-to=PySide6.QtPdf",
        "--nofollow-import-to=PySide6.QtSql",
        "--nofollow-import-to=PySide6.QtTest",
        f"--output-dir={DIST}",
        f"--output-filename={APP_NAME}.exe",
        # 文件夹模式：不打包成一个 exe，启动快、便于替换资源
        *icon_args(),
        str(ENTRY),
    ]


def icon_args() -> list[str]:
    """有图标才传 --windows-icon-from-ico，否则 Nuitka 会因文件不存在报错。"""
    ico = ROOT / "app" / "assets" / "app.ico"
    return [f"--windows-icon-from-ico={ico}"] if ico.is_file() else []


def main() -> int:
    problems = check_prereqs()
    if problems:
        print("构建前检查未通过：")
        for p in problems:
            print("  ✗", p)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    cmd = build_command()
    print("执行 Nuitka 构建（首次编译较慢，请耐心等待）…")
    print(" ".join(cmd[:8]), "…")
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        print(f"Nuitka 返回码 {rc}，构建失败")
        return rc

    # 文件夹模式下 Nuitka 产物位于 dist/<名字>.dist/
    # Nuitka 4.x 用入口文件名命名产物目录，所以可能是 main.dist
    candidates = [
        DIST / f"{APP_NAME}.dist" / f"{APP_NAME}.exe",
        DIST / "main.dist" / f"{APP_NAME}.exe",
        DIST / "main.dist" / "main.exe",
        DIST / f"{APP_NAME}.exe",
    ]
    exe = next((c for c in candidates if c.is_file()), None)
    if exe is None:
        print("构建结束但未找到产物，请检查上面的输出")
        return 1

    folder = exe.parent
    total = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
    print(f"\n构建成功")
    print(f"  可执行文件：{exe}")
    print(f"  整个目录  ：{folder}")
    print(f"  文件数    ：{sum(1 for f in folder.rglob('*') if f.is_file())}")
    print(f"  总体积    ：{total / 1024 / 1024:.1f} MB")
    print(f"\n分发时请整体拷贝 {folder.name} 文件夹，运行其中的 {exe.name}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
