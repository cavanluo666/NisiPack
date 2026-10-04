"""用 NisiPack 自己给 NisiPack 做一个安装包（自举打包）。

前提：已经运行过 build.py，产物位于 dist/NisiPack.dist/。
生成的安装包会落在 release/ 目录。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DIST = ROOT / "dist" / "NisiPack.dist"
RELEASE = ROOT / "release"
ICON = ROOT / "app" / "assets" / "app.ico"
LICENSE = ROOT / "LICENSE.rtf"


def find_dist() -> Path:
    """定位 Nuitka 文件夹模式的产物目录。"""
    candidates = [
        DIST,
        ROOT / "dist" / "NisiPack.dist",
        ROOT / "dist" / "main.dist",
    ]
    for c in candidates:
        if (c / "NisiPack.exe").is_file() or (c / "main.exe").is_file():
            return c
    # 兜底：扫 dist 下所有 .dist 目录
    dist_root = ROOT / "dist"
    if dist_root.is_dir():
        for d in dist_root.iterdir():
            if d.is_dir() and any(d.glob("*.exe")):
                return d
    raise FileNotFoundError(
        "找不到编译产物，请先运行：python build.py"
    )


def main() -> int:
    _utf8_console()

    try:
        dist = find_dist()
    except FileNotFoundError as exc:
        print(f"[✗] {exc}")
        return 1

    exe = next((p for p in (dist / "NisiPack.exe", dist / "main.exe") if p.is_file()), None)
    if exe is None:
        print("[✗] 未在产物目录里找到主程序 exe")
        return 1

    RELEASE.mkdir(parents=True, exist_ok=True)

    from app.core import InstallerConfig, build_script, compile_script, find_nsis
    from app.core import nsis_runtime
    from app.core.nsis_script import write_script_file

    cfg = InstallerConfig(
        app_name="NisiPack",
        app_version="1.0.0",
        publisher="NisiPack",
        app_url="",
        description="图形化 Windows 安装包制作工具，内置 NSIS 运行时。",
        source_dir=str(dist),
        main_exe=exe.name,
        output_dir=str(RELEASE),
        output_name="NisiPack-1.0.0-Setup",
        scope="all",                 # 装到 Program Files，需要管理员权限
        ui_style="modern",
        compress="lzma",
        default_install_dir=r"$PROGRAMFILES64\${APP_NAME}",
        icon_path=str(ICON) if ICON.is_file() else "",
        uninstall_icon=str(ICON) if ICON.is_file() else "",
        license_file=str(LICENSE) if LICENSE.is_file() else "",
        kill_processes="NisiPack.exe",   # 覆盖安装前先关掉正在运行的本程序
    )

    problems = cfg.validate()
    if problems:
        print("[✗] 配置校验未通过：")
        for p in problems:
            print("   ·", p)
        return 1

    rt = find_nsis()
    print(f"[·] 编译环境：{rt.describe()}")

    script_path = RELEASE / f"{cfg.safe_output_name()}.nsi"
    output_file = RELEASE / f"{cfg.safe_output_name()}.exe"

    # 统计打包体积
    total = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    count = sum(1 for f in dist.rglob("*") if f.is_file())
    print(f"[·] 待打包：{count} 个文件，{nsis_runtime.human_size(total)}")
    print(f"[·] 源目录：{dist}")

    script = build_script(cfg, script_path, script_path)
    write_script_file(script, script_path)

    print("[·] 正在编译安装包…")
    res = compile_script(
        rt, script_path, output_file=output_file,
        log_callback=lambda line: None,   # 只关心结果，细节不必刷屏
        verbosity=2,
    )

    if not res.success:
        print("[✗] 生成失败：")
        for e in res.errors:
            print("   ", e)
        return 1

    size = nsis_runtime.human_size(res.output_size())
    print()
    print("=" * 60)
    print(f"  安装包已生成")
    print(f"  文件：{output_file}")
    print(f"  体积：{size}")
    print(f"  耗时：{res.duration:.1f} 秒")
    if res.warnings:
        print(f"  警告：{len(res.warnings)} 条（外观性提示，不影响功能）")
    print("=" * 60)
    return 0


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


if __name__ == "__main__":
    raise SystemExit(main())
