# vscode-cpp-init

一键生成 Windows + MinGW-w64 的 VS Code C++ 工作区配置。

同一份配置在不同电脑上路径往往不一样（`E:\Code\mingw64`、`D:\mingw64`……），手动改 json 很烦。
这个脚本从 PATH 定位你的 MinGW，探测编译器架构和标准库路径，把 4 个配置json 里的路径一次性填对。

## 环境要求

- Windows
- Python 3.8+
- 已安装 MinGW-w64，且其 `bin` 目录在系统 `PATH` 里（`g++ --version` 能在任意终端跑通即可）
- VS Code 装了 C/C++ 扩展（`ms-vscode.cpptools`）

## 快速开始

```bat
python setup_vscode.py
```

跑完当前目录下会多出 `.vscode/`，包含 4 个 json。用 VS Code 打开这个目录（或把 `.vscode` 拷进你的项目）就能编译调试。

想直接给别的项目生成：

```bat
python setup_vscode.py --dir D:\work\myproject
```

## 生成之后能干什么

| 操作 | 说明 |
| --- | --- |
| `Ctrl+Shift+B` | 编译当前文件并在终端运行，可以正常输入数据 |
| `F5` | 调试当前文件（gdb，走 integratedTerminal，中文输出不乱码） |
| 命令面板 → Tasks: Run Task | 选「cpp: 清理 build 产物」可清掉 `build/` 里的 exe 和 o，不动源码 |

`build/` 目录会在编译前自动创建（隐藏的辅助任务），产物统一进 `build/`，不污染源码目录；
`build/` 已在配置里从搜索和文件监听中排除。

生成的文件：

| 文件 | 作用 |
| --- | --- |
| `c_cpp_properties.json` | 智能提示：编译器路径、IntelliSense 模式、标准库头文件位置 |
| `tasks.json` | 编译 / 运行 / 清理任务 |
| `launch.json` | gdb 调试入口 |
| `settings.json` | 编码、排除 `build/`、给内置终端追加 MinGW `bin` |

## 参数

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--root` | 手动指定 MinGW 目录，跳过 PATH 查找。根目录、`bin` 子目录、带引号的路径都认 | 无 |
| `--dir` | 目标项目目录（在其中创建 `.vscode`） | 脚本所在目录 |
| `--std` | C++ 标准，同时写进编译参数和智能提示配置 | `c++17` |
| `--cstd` | C 标准 | `c17` |
| `--no-check` | 跳过编译自检 | 自检开启 |

## 它是怎么找 MinGW 的

只看 `PATH`：依次试 `g++.exe` / `g++` / `gcc.exe` / `gcc`，从命中的可执行文件反推出根目录（`...\bin\g++.exe` → `...`）。
不扫盘。找不到就退出并提示你加 PATH 或用 `--root`。

拿到根目录后还会跑 `g++ -dumpmachine` 探测目标三元组，据此决定 `intelliSenseMode`
（`x86_64` → `windows-gcc-x64`，`i686` → `windows-gcc-x86`，ARM64 也覆盖）和标准库 browse 路径。

最后做一次**自检**：在临时目录编译并运行一个几行的小程序，确认这套工具链真能产出可运行的 exe，
临时文件自动删除，不碰你的项目。

## 常见问题

**`[X] PATH 里没找到 g++/gcc`**
MinGW 的 `bin` 没进 PATH。加进系统 PATH 后重开终端，或者临时用 `--root D:\mingw64`。

**`[!] 没找到 gdb.exe`**
说明装的是精简版 MinGW（例如只带编译器的 bundle）。编译运行不受影响，但 `F5` 调试会失败，
换完整的 MinGW-w64 / MSYS2 发行版。

**`[!] VS Code 里没装 C/C++ 扩展`**
智能提示和调试都依赖它，扩展面板搜 `cpptools` 安装。

**输出中文乱码**
脚本本身是 UTF-8 输出；如果你用的是 PowerShell 5 且管道重定向了输出，加 `python -X utf8 setup_vscode.py`。

**会覆盖已有配置吗**
会。目标目录下已存在的 `.vscode/*.json` 会被直接覆盖，需要的话先备份。

## 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 全部正常 |
| `1` | 没找到 MinGW，未生成任何文件 |
| `2` | 配置已生成，但存在隐患（缺 gdb / 缺 C/C++ 扩展 / 自检未通过） |
