"""调用 makensis 编译脚本，并流式回传日志。"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .nsis_runtime import NsisRuntime

# 日志行 → 严重级别
# 这些模式覆盖 makensis 在中文/英文环境下的实际输出措辞
_RE_WARN = re.compile(r"(?i)(^|\s)(warning|warn)\s*[:\-]|\bwarning\b")
_RE_ERR = re.compile(
    r"(?i)error in script"
    r"|bad text encoding"
    r"|aborting creation process"
    r"|\b(fatal error|error)\s*[:\-]"
    r"|^error\b"
)


@dataclass
class CompileResult:
    """一次编译的结果。"""

    success: bool = False
    returncode: int | None = None
    output_file: Path | None = None
    log: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration: float = 0.0
    cancelled: bool = False

    def output_size(self) -> int:
        if self.output_file and self.output_file.is_file():
            return self.output_file.stat().st_size
        return 0


def classify(line: str) -> str:
    """给日志行打标签：error / warning / info。"""
    if _RE_ERR.search(line):
        return "error"
    if _RE_WARN.search(line):
        return "warning"
    return "info"


def _console_encoding() -> str:
    """makensis 控制台输出的编码。

    中文 Windows 上是 GBK(936)，直接按 UTF-8 解码会出现替换字符，
    导致中文错误信息变成乱码，用户看不懂。
    """
    if os.name != "nt":
        return "utf-8"
    try:
        import ctypes

        cp = ctypes.windll.kernel32.GetOEMCP()
        if cp:
            return f"cp{cp}"
    except Exception:
        pass
    return "mbcs"


def _no_window_kwargs() -> dict:
    """Windows 下隐藏子进程控制台窗口。"""
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }


def build_command(
    runtime: NsisRuntime,
    script: Path,
    *,
    defines: dict[str, str] | None = None,
    verbosity: int = 2,
) -> list[str]:
    """组装 makensis 命令行。"""
    cmd = [str(runtime.makensis), f"/V{verbosity}", "/NOCD"]
    # 让 NSIS 能读到随包附带的 Include / Plugins
    cmd.append(f"/X!addincludedir {runtime.root / 'Include'}")
    for arch in ("x86-unicode", "x86-ansi"):
        plugin_dir = runtime.root / "Plugins" / arch
        if plugin_dir.is_dir():
            cmd.append(f"/X!addplugindir /x86-unicode {plugin_dir}")
            break
    for key, value in (defines or {}).items():
        cmd.append(f"/D{key}={value}")
    cmd.append(str(script))
    return cmd


def compile_script(
    runtime: NsisRuntime,
    script: Path,
    *,
    output_file: Path | None = None,
    defines: dict[str, str] | None = None,
    log_callback: Callable[[str], None] | None = None,
    line_callback: Callable[[str, str], None] | None = None,
    cancel_event: threading.Event | None = None,
    verbosity: int = 2,
) -> CompileResult:
    """编译 .nsi 脚本。

    log_callback  —— 收到一行原始日志时调用（已去尾随空白）
    line_callback —— (级别, 文本)，级别为 error/warning/info
    cancel_event  —— 置位后将终止编译进程
    """
    import time

    result = CompileResult()
    started = time.monotonic()

    if not script.is_file():
        result.errors.append(f"脚本不存在：{script}")
        result.log.append(f"脚本不存在：{script}")
        return result

    cmd = build_command(runtime, script, defines=defines, verbosity=verbosity)
    workdir = script.parent

    def emit(line: str) -> None:
        line = line.rstrip()
        if not line:
            return
        level = classify(line)
        result.log.append(line)
        if level == "error":
            result.errors.append(line)
        elif level == "warning":
            result.warnings.append(line)
        if log_callback is not None:
            try:
                log_callback(line)
            except Exception:
                pass
        if line_callback is not None:
            try:
                line_callback(level, line)
            except Exception:
                pass

    emit(f"[命令] {' '.join(cmd)}")
    emit(f"[工作目录] {workdir}")

    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding=_console_encoding(),
            errors="replace",
            bufsize=1,
            **_no_window_kwargs(),
        )
    except OSError as exc:
        emit(f"[错误] 无法启动 makensis：{exc}")
        result.duration = time.monotonic() - started
        return result

    # 边读边发，保证界面实时刷新
    assert proc.stdout is not None
    try:
        for raw in proc.stdout:
            if cancel_event is not None and cancel_event.is_set():
                break
            emit(raw)
    except (OSError, ValueError):
        pass
    finally:
        if cancel_event is not None and cancel_event.is_set() and proc.poll() is None:
            proc.kill()
            result.cancelled = True
            emit("[已取消] 用户中止了编译")

    try:
        result.returncode = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        result.returncode = proc.wait()
        emit("[错误] 编译进程未正常退出，已强制终止")

    result.duration = time.monotonic() - started
    result.output_file = output_file
    result.success = (
        not result.cancelled
        and result.returncode == 0
        and output_file is not None
        and Path(output_file).is_file()
    )

    if result.success:
        size = Path(output_file).stat().st_size
        emit(f"[完成] 已生成 {output_file}（{size / 1024 / 1024:.2f} MB，"
             f"耗时 {result.duration:.1f} 秒）")
    elif not result.cancelled:
        emit(f"[失败] makensis 返回码 {result.returncode}")

    return result


def probe_version(runtime: NsisRuntime, timeout: float = 15.0) -> str:
    """读取 makensis 版本号。"""
    try:
        out = subprocess.run(
            [str(runtime.makensis), "/VERSION"],
            capture_output=True,
            text=True,
            encoding=_console_encoding(),
            errors="replace",
            timeout=timeout,
            **_no_window_kwargs(),
        )
        return (out.stdout or out.stderr or "").strip() or "未知"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"读取失败：{exc}"