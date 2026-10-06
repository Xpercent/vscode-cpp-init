#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键生成 VS Code C++ (MinGW-w64) 工作区配置。

只从 PATH 定位 MinGW（不扫盘）；找不到就用 --root 指定。

用法:
    python setup_vscode.py                 # 从 PATH 找 MinGW，写入本脚本目录下的 .vscode/
    python setup_vscode.py --root D:\\mingw64
    python setup_vscode.py --dir D:\\proj  # 写到别的项目里
    python setup_vscode.py --std c++20
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- #
# 定位 MinGW（只看 PATH，不扫盘）
# --------------------------------------------------------------------------- #
def to_root(p: Path) -> Path:
    """把 g++.exe / bin 目录 / MinGW 根目录统一归成根目录。"""
    if p.name.lower() in ("g++.exe", "gcc.exe", "g++", "gcc"):
        p = p.parent
    return p.parent if p.name.lower() == "bin" else p


def is_root(d: Path) -> bool:
    return d.is_dir() and (d / "bin" / "g++.exe").is_file()


def find_in_path() -> Path | None:
    for name in ("g++.exe", "g++", "gcc.exe", "gcc"):
        found = shutil.which(name)
        if found:
            return to_root(Path(found))
    return None


def detect(cli_root: str | None) -> Path:
    if cli_root:
        p = to_root(Path(cli_root.strip().strip('"')))
        if not is_root(p):
            sys.exit(f"[X] --root 指向的目录里没有 bin/g++.exe：{p}")
        log(f"[i] 使用命令行指定的 MinGW：{p}")
        return p

    log("[.] 在 PATH 中查找 g++ ...")
    hit = find_in_path()
    if hit and is_root(hit):
        log(f"[✓] 在 PATH 中找到：{hit}")
        return hit

    sys.exit(
        "[X] PATH 里没找到 g++/gcc，无法定位 MinGW。\n"
        "    请先把 MinGW 的 bin 目录加入系统 PATH，或用 --root 指定：\n"
        "        python setup_vscode.py --root D:\\mingw64"
    )


# --------------------------------------------------------------------------- #
# 探测编译器细节
# --------------------------------------------------------------------------- #
def probe(root: Path) -> dict:
    info = {"triple": "x86_64-w64-mingw32", "mode": "windows-gcc-x64"}
    try:
        out = subprocess.run(
            [str(root / "bin" / "g++.exe"), "-dumpmachine"],
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace",
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    if out:
        info["triple"] = out
        arch = out.split("-")[0].lower()
        info["mode"] = {
            "x86_64": "windows-gcc-x64",
            "i686": "windows-gcc-x86",
            "aarch64": "windows-gcc-arm64",
            "arm": "windows-gcc-arm",
        }.get(arch, "windows-gcc-x64")
    return info


def browse_paths(root: Path, triple: str) -> list[str]:
    fwd = root.as_posix()
    paths = [f"{fwd}/include"]
    for cand in (f"{fwd}/lib/gcc/{triple}", f"{fwd}/lib/gcc"):
        if Path(cand).is_dir():
            paths.append(cand)
            break  # 优先用架构专属目录，避免 browse 路径重复
    return paths


def slashes(root: Path) -> tuple[str, str]:
    """返回 (正斜杠形式, 反斜杠形式)，与 VS Code 各配置文件的写法保持一致。"""
    fwd = root.as_posix()
    return fwd, fwd.replace("/", "\\")


# --------------------------------------------------------------------------- #
# 配置模板：路径由探测结果填充
# --------------------------------------------------------------------------- #
def build_configs(root: Path, std: str, cstd: str, info: dict) -> dict[str, dict]:
    fwd, back = slashes(root)
    binp = f"{back}\\bin"

    c_cpp_properties = {
        "configurations": [
            {
                "name": "Win32",
                "includePath": ["${workspaceFolder}/**"],
                "defines": ["_DEBUG", "UNICODE", "_UNICODE"],
                "compilerPath": f"{fwd}/bin/g++.exe",
                "cStandard": cstd,
                "cppStandard": std,
                "intelliSenseMode": info["mode"],
                "compilerArgs": [f"-std={std}"],
                "browse": {
                    "path": ["${workspaceFolder}"] + browse_paths(root, info["triple"]),
                    "limitSymbolsToIncludedHeaders": True,
                },
            }
        ],
        "version": 4,
    }

    build_exe = "${workspaceFolder}\\build\\${fileBasenameNoExtension}.exe"
    shell_opts = {
        "cwd": "${workspaceFolder}",
        "shell": {"executable": "cmd.exe", "args": ["/d", "/c"]},
    }

    tasks = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "cpp: 准备 build 目录",
                "detail": "build 文件夹不存在时自动创建，由编译任务自动调用",
                "type": "shell",
                "command": 'if not exist "${workspaceFolder}\\build" mkdir "${workspaceFolder}\\build"',
                "options": shell_opts,
                "presentation": {"hidden": True},
                "problemMatcher": [],
            },
            {
                "label": "cpp: 编译当前文件",
                "detail": "只编译，产物 -> build\\<文件名>.exe。F5 调试用的就是它",
                "type": "shell",
                "command": f"{binp}\\g++.exe",
                "args": [
                    f"-std={std}", "-O0", "-g", "-Wall", "-static",
                    "${file}", "-o", build_exe,
                ],
                "options": shell_opts,
                "dependsOn": "cpp: 准备 build 目录",
                "group": "build",
                "presentation": {"reveal": "silent", "panel": "shared"},
                "problemMatcher": ["$gcc"],
            },
            {
                "label": "cpp: 编译并运行当前文件",
                "detail": "默认任务：Ctrl+Shift+B 走这个（先编译再在终端运行，可输入数据）",
                "type": "shell",
                "command": f'chcp 65001 >nul && "{build_exe}"',
                "options": shell_opts,
                "dependsOn": "cpp: 编译当前文件",
                "dependsOrder": "sequence",
                "group": {"kind": "build", "isDefault": True},
                "presentation": {"reveal": "always", "focus": True, "panel": "dedicated"},
                "problemMatcher": [],
            },
            {
                "label": "cpp: 清理 build 产物",
                "detail": "删除 build 里的 .exe 和 .o，不动源码",
                "type": "shell",
                "command": 'if exist "${workspaceFolder}\\build" del /q '
                           '"${workspaceFolder}\\build\\*.exe" "${workspaceFolder}\\build\\*.o"',
                "options": shell_opts,
                "problemMatcher": [],
            },
        ],
    }

    launch = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "C++ 调试当前文件 (MinGW)",
                "type": "cppdbg",
                "request": "launch",
                "program": build_exe,
                "args": [],
                "stopAtEntry": False,
                "cwd": "${workspaceFolder}",
                "environment": [],
                "console": "integratedTerminal",
                "MIMode": "gdb",
                "miDebuggerPath": f"{binp}\\gdb.exe",
                "preLaunchTask": "cpp: 编译当前文件",
                "setupCommands": [
                    {
                        "description": "为 gdb 启用整齐打印（pretty-printing）",
                        "text": "-enable-pretty-printing",
                        "ignoreFailures": True,
                    },
                    {
                        "description": "关闭地址随机化，便于复现",
                        "text": "set disable-randomization on",
                        "ignoreFailures": True,
                    },
                ],
            }
        ],
    }

    settings = {
        "C_Cpp.default.compilerPath": f"{fwd}/bin/g++.exe",
        "C_Cpp.default.intelliSenseMode": info["mode"],
        "C_Cpp.default.cppStandard": std,
        "C_Cpp.default.cStandard": cstd,
        "C_Cpp.files.exclude": {"**/build": True},
        "files.encoding": "utf8",
        "files.watcherExclude": {"**/build/**": True},
        "search.exclude": {"**/build": True},
        "terminal.integrated.env.windows": {"Path": f"{binp};${{env:Path}}"},
        "cmake.ignoreCMakeListsMissing": True,
    }

    return {
        "c_cpp_properties.json": c_cpp_properties,
        "tasks.json": tasks,
        "launch.json": launch,
        "settings.json": settings,
    }


def write(out_dir: Path, configs: dict[str, dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for fname, data in configs.items():
        (out_dir / fname).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        log(f"  + {out_dir / fname}")


# --------------------------------------------------------------------------- #
# 自检：真的编译跑一次
# --------------------------------------------------------------------------- #
def verify(root: Path, std: str) -> bool:
    src = (
        "#include <iostream>\n#include <vector>\n#include <string>\n"
        "int main(){std::vector<std::string> v{\"ok\",\"mingw\"};"
        "for(auto&s:v)std::cout<<s<<' ';std::cout<<std::endl;return 0;}\n"
    )
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        cpp = d / "probe.cpp"
        exe = d / "probe.exe"
        cpp.write_text(src, encoding="utf-8")
        gxx = str(root / "bin" / "g++.exe")
        r = subprocess.run(
            [gxx, f"-std={std}", "-static", str(cpp), "-o", str(exe)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            log(f"[X] 自检编译失败：\n{(r.stderr or '').strip()}")
            return False
        run = subprocess.run(
            [str(exe)], capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if run.returncode != 0 or "ok" not in (run.stdout or ""):
            log(f"[X] 自检运行失败：{run.stdout!r} {run.stderr!r}")
            return False
    log("[✓] 自检通过：编译 + 运行均正常")
    return True


# --------------------------------------------------------------------------- #
def cpptools_installed():
    """查 VS Code 的 C/C++ 扩展装没装；查不到证据时返回 None（不影响生成）。"""
    d = Path.home() / ".vscode" / "extensions"
    if not d.is_dir():
        d = Path.home() / ".vscode-server" / "extensions"
    if not d.is_dir():
        return None
    return any("cpptools" in p.name.lower() for p in d.iterdir() if p.is_dir())


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(
        description="一键生成 VS Code C++ (MinGW) 配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--root", help="手动指定 MinGW 目录（根目录或 bin 均可），跳过 PATH 查找")
    ap.add_argument("--dir", help="目标项目目录（在其中创建 .vscode）；默认为本脚本所在目录的 .vscode")
    ap.add_argument("--std", default="c++17", help="C++ 标准，默认 c++17")
    ap.add_argument("--cstd", default="c17", help="C 标准，默认 c17")
    ap.add_argument("--no-check", action="store_true", help="跳过编译自检")
    args = ap.parse_args()

    if os.name != "nt":
        sys.exit("[X] 本脚本面向 Windows + MinGW 环境。")

    try:  # 管道重定向时避免中文输出炸编码
        sys.stdout.reconfigure(errors="replace")
    except (OSError, ValueError):
        pass

    log("=" * 58)
    log(" VS Code C++ 环境一键配置")
    log("=" * 58)

    root = detect(args.root)

    out_dir = Path(args.dir).resolve() / ".vscode" if args.dir else Path(__file__).resolve().parent / ".vscode"
    log(f"\n[.] 写入配置 -> {out_dir}")
    info = probe(root)
    write(out_dir, build_configs(root, args.std, args.cstd, info))

    ok = True
    if not args.no_check:
        ok = verify(root, args.std)

    gdb_ok = (root / "bin" / "gdb.exe").is_file()
    make_ok = (root / "bin" / "mingw32-make.exe").is_file()
    ext = cpptools_installed()
    log("\n" + "-" * 58)
    log(f"  MinGW     : {root}")
    log(f"  架构/模式 : {info['triple']}  ({info['mode']})")
    log(f"  C++ 标准  : {args.std}")
    log(f"  gdb       : {'找到' if gdb_ok else '缺失'}")
    log(f"  make      : {'找到' if make_ok else '未找到（只影响 make 构建）'}")
    log(f"  C/C++扩展 : {None if ext is None else ('已安装' if ext else '未安装')}")
    log("-" * 58)
    if out_dir.parent != Path(__file__).resolve().parent:
        log(f"[i] 用 VS Code 打开 {out_dir.parent} 即可生效。")
    else:
        log("[i] 这套配置是模板；把 .vscode 文件夹拷进任意 C++ 项目即可使用。")

    problems = []
    if not gdb_ok:
        problems.append("没找到 gdb.exe：F5 调试会失败（编译运行不受影响），建议换完整的 MinGW-w64 发行版")
    if ext is False:
        problems.append("VS Code 里没装 C/C++ 扩展（ms-vscode.cpptools）：智能提示和调试都用不了，"
                        "在扩展面板搜 cpptools 安装")
    if not ok:
        problems.append("自检编译没有通过，请检查上面输出")
    for p in problems:
        log("[!] " + p)
    if problems:
        sys.exit(2)
    log("[✓] 全部完成")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n[X] 已取消")
