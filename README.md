# NisiPack · 安装包制作工具

把任意文件夹一键打成 Windows 安装包（`.exe`）的图形化工具，底层用 NSIS 编译。

**完全独立**：程序内置 NSIS 运行时，用户电脑上不需要装 Python、PySide6 或 NSIS，
双击即可运行。

---

## 功能

| 能力 | 说明 |
|---|---|
| 可视化配置 | 应用名、版本、开发者、官网、简介 |
| 拖拽打包 | 文件夹直接拖进输入框，自动识别其中的 `.exe` 作为主程序 |
| 向导风格 | 现代向导（推荐）/ 极简静默 / 经典风格 |
| 安装范围 | 所有用户（提权，装到 Program Files）或仅当前用户（免提权） |
| 快捷方式 | 桌面、开始菜单，可自定义开始菜单分组名 |
| 卸载支持 | 自动生成 `Uninstall.exe` 并登记到「应用和功能」 |
| 外观定制 | 安装包图标、向导头图、欢迎页大图、RTF 许可协议 |
| 压缩算法 | LZMA（最小）/ Solid LZMA / bzip2 / zlib（最快） |
| 进程处理 | 安装前自动结束占用文件的进程 |
| 配置存取 | 导出 / 导入 JSON，方便重复出包 |
| 实时日志 | 编译输出按 错误/警告/信息 分级着色 |
| 脚本预览 | 编译前可查看完整的 `.nsi` 脚本 |

---

## 使用流程

1. **填写应用信息** —— 至少填「应用名称」
2. **选择要打包的内容** —— 拖入或选择文件夹，确认「主程序」下拉框选中了正确的 exe
3. **选择输出目录** —— 安装包将生成在这里
4. **调整安装选项与外观**（可选）
5. 点右上角 **开始生成安装包**

右侧可切换三个标签页：

- **编译日志** —— 实时输出，出错时看这里
- **脚本预览** —— 即将交给 NSIS 的 `.nsi` 脚本
- **配置检查** —— 必填项、编译环境、预生成文件名

生成完成后：

- **打开输出目录** —— 定位到安装包
- **试运行安装包** —— 直接跑一遍看效果

---

## 从源码运行

先把 NSIS 运行时放到 `vendor/NSIS/`（见下方「获取内置 NSIS」），然后：

```bash
pip install -r requirements.txt
python main.py
```

自检（不启动界面，验证 NSIS 与编译链路）：

```bash
python selfcheck.py
```

### 获取内置 NSIS

仓库**不包含** `vendor/NSIS/`（约 6.9 MB 的第三方二进制，避免在版本库里重复分发）。
从源码运行或自行构建前，请先下载 NSIS 3.x 并解压到该目录：

1. 打开 <https://nsis.sourceforge.io/Download> 下载 `nsis-3.x.zip`（或安装包）；
2. 把解压后的内容放到 `vendor/NSIS/`，使 `vendor/NSIS/makensis.exe` 存在：

```
vendor/NSIS/
├── makensis.exe         ← 必须是这个层级
├── Include/
├── Plugins/
└── Stubs/
```

`app/core/nsis_runtime.py` 会按「内置 → 系统安装」的顺序查找，
所以你也可以跳过这一步，改为在本机安装 NSIS 到默认位置。

---

## 打包发布

```bash
python build.py
```

用 Nuitka 编译成**文件夹模式**产物（不打包成单体 exe）：

- 可执行文件：`dist/main.dist/NisiPack.exe`（约 7.6 MB）
- 完整目录：`dist/main.dist/`（约 82 MB，含 PySide6 与 NSIS 运行时）

分发时需整体拷贝 `main.dist` 文件夹。选择文件夹模式而非单文件模式的原因：

- **启动快** —— 单文件模式每次运行都要把上百 MB 内容解压到临时目录
- **便于替换资源** —— 内置的 NSIS 可在目录里直接更新
- 只有入口 exe 会被杀软反复扫描，减少误报概率

### 给自己做安装包（自举）

```bash
python make_self_installer.py
```

把 `dist/main.dist/` 整个打成一个安装包，输出到
`release/NisiPack-1.0.0-Setup.exe`（约 25 MB）。

该安装包已验证：

- 安装到 `Program Files`，创建公共桌面与开始菜单快捷方式
- 在「应用和功能」中登记，显示名称、版本、发布者与预估大小
- 安装后程序可独立运行
- 卸载后安装目录、快捷方式、注册表**零残留**

---

## 项目结构

```
NisiPack/
├── main.py                  启动入口
├── build.py                 Nuitka 构建脚本
├── selfcheck.py             自检脚本
├── make_self_installer.py   给自己打安装包（自举）
├── LICENSE.rtf              安装向导中展示的许可协议
├── app/
│   ├── core/
│   │   ├── models.py        配置数据模型与校验
│   │   ├── nsis_script.py   生成 .nsi 脚本
│   │   ├── nsis_runtime.py  定位内置 NSIS
│   │   └── compiler.py      调用 makensis 并流式回收日志
│   └── ui/
│       ├── theme.py         配色与 QSS 样式表
│       ├── widgets.py       卡片、拖拽输入框、日志面板等
│       └── main_window.py   主窗口
└── vendor/NSIS/             内置 NSIS 运行时（随包分发）
```

---

## 实现要点

生成 NSIS 脚本时有几个容易踩的坑，本项目已处理：

- **脚本必须写为 UTF-8 with BOM**。无 BOM 时，哪怕只是中文注释，
  makensis 也会报 `Bad text encoding` 而中断。
- **`File` 指令必须用绝对路径**，否则会相对于脚本所在目录解析而找不到文件。
- **宏必须在使用前定义**。`${APP_NAME}` 这类宏若定义晚于 `InstallDir`，
  会被当成字面量。
- **`${MACRO}` 与 `$Var` 语义不同**：前者是编译期宏，后者是运行时变量，
  不可混用（如 `StartMenuFolder` 是 `Var`，必须写 `$StartMenuFolder`）。
- **`SetCompressor` 只接受** `zlib|bzip2|lzma`，`/SOLID` 只是修饰符。
- **卸载向导页必须早于 `MUI_LANGUAGE` 插入**，否则语言字符串未定义。
- makensis 在中文 Windows 上输出 **GBK**，按 UTF-8 解码会得到乱码。

### 已知提示

编译日志里可能出现以下警告，**不影响安装包功能**：

- `warning 9100: ... without standard key "FileVersion"` ——
  同时启用中英双语时，NSIS 对未补齐版本信息的语言给出的提示。
- `warning 6001: Variable "StartMenuFolder" ...` ——
  某些配置下（未勾选开始菜单快捷方式）该变量未被使用。

---

## 许可

本项目以 **GNU General Public License v3.0 or later** 发布，完整条款见 [`LICENSE`](LICENSE)。

```
Copyright (C) 2026 LCH
```

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

### 第三方组件

- **NSIS**（Nullsoft Scriptable Install System）采用
  [zlib/libpng 许可](https://nsis.sourceforge.io/License)，允许随程序一同分发。
  本仓库不分发 NSIS 二进制，需自行获取；打包分发给最终用户时请一并遵守其许可。
- **PySide6 / Qt** 采用 LGPLv3，以动态链接方式使用。若你分发本程序的构建产物，
  请自行确认对 LGPLv3 的合规义务。
