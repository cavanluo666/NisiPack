"""NisiPack 核心引擎。"""
from .models import InstallerConfig, ShortcutOptions, UI_CHOICES
from .nsis_runtime import NsisRuntime, NsisNotFoundError, find_nsis
from .nsis_script import build_script
from .compiler import compile_script, CompileResult, probe_version
