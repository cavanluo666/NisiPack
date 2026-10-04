"""不启动界面，检查核心链路是否可用。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _use_utf8_console() -> None:
    """让中文与勾叉符号在 GBK 控制台也能正常打印。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    _use_utf8_console()
    ok = True
    print("=" * 56)
    print(" NisiPack 自检")
    print("=" * 56)

    from app.core import InstallerConfig, build_script, find_nsis, probe_version
    from app.core import nsis_runtime
    from app.core.nsis_script import write_script_file

    # 1) NSIS 运行时
    try:
        rt = find_nsis()
        ver = probe_version(rt)
        print(f"[✓] NSIS 运行时：{ver}")
        print(f"    位置：{rt.makensis}")
        print(f"    来源：{'内置（随包分发）' if rt.bundled else '系统安装'}")
    except Exception as exc:
        print(f"[✗] NSIS 运行时不可用：{exc}")
        return 1

    # 2) 插件
    plugins = nsis_runtime.check_plugins(rt)
    avail = [k for k, v in plugins.items() if v]
    print(f"[✓] 可用插件：{', '.join(avail) if avail else '无（非必需）'}")

    # 3) 脚本生成
    with tempfile.TemporaryDirectory(prefix="nisipack_check_") as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        (src / "app.exe").write_bytes(b"MZ" + b"\0" * 1024)
        (src / "sub" / "data.txt").write_text("hello", encoding="utf-8")

        cfg = InstallerConfig(
            app_name="自检示例", app_version="1.0.0",
            source_dir=str(src), main_exe="app.exe",
            output_dir=str(tmp_path), output_name="SelfCheck",
            scope="user",
        )
        problems = cfg.validate()
        if problems:
            print(f"[✗] 配置校验失败：{problems}")
            ok = False
        else:
            print("[✓] 配置校验通过")

        script = build_script(cfg, tmp_path / "s.nsi", tmp_path / "s.nsi")
        nsi = write_script_file(script, tmp_path / "s.nsi")
        head = nsi.read_bytes()[:3]
        print(f"[✓] 脚本生成：{nsi.stat().st_size} 字节，UTF-8 BOM={'是' if head == b'\xef\xbb\xbf' else '否'}")

        # 4) 真实编译
        from app.core import compile_script

        res = compile_script(rt, nsi, output_file=tmp_path / "SelfCheck.exe",
                             verbosity=1)
        if res.success:
            print(f"[✓] 编译成功：{nsis_runtime.human_size(res.output_size())}，"
                  f"耗时 {res.duration:.1f} 秒")
        else:
            print(f"[✗] 编译失败：{res.errors}")
            ok = False

    # 5) 界面模块
    try:
        from app.ui import theme, widgets  # noqa: F401
        from app.ui.main_window import MainWindow  # noqa: F401
        print("[✓] 界面模块可导入")
    except Exception as exc:
        print(f"[✗] 界面模块导入失败：{exc}")
        ok = False

    print("=" * 56)
    print(" 全部通过" if ok else " 存在问题")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
