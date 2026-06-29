#!/usr/bin/env python3
"""
Windows 环境变量管理工具
查看、编辑、添加、删除用户与系统环境变量
"""

from __future__ import annotations

import os
import sys
import winreg
import ctypes
import argparse
from pathlib import Path
from dataclasses import dataclass

# ---------- 终端颜色（Windows VT100） ----------

def _enable_vt():
    if sys.platform == "win32":
        try:
            import ctypes as _ct
            _ct.windll.kernel32.SetConsoleMode(_ct.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

_enable_vt()

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


# ---------- i18n ----------

_lang = "zh"

_UI: dict[str, dict[str, str]] = {
    "zh": {
        "title":            "Windows 环境变量管理",
        "scan_phase":       "正在读取环境变量...",
        "scan_done":        "读取完成，共 {n} 个变量",
        "menu_header":      "选择变量  (数字键切换 / e 编辑 / d 删除 / a 添加 / f 切换范围 / < > 翻页 / p 预览 / l 语言 / q 退出)",
        "filter_all":       "全部",
        "filter_user":      "用户",
        "filter_sys":       "系统",
        "filter_label":     "范围",
        "page_info":        "第 {cur}/{total} 页",
        "menu_total":       "已选",
        "at_least_one":     "请至少选择一项",
        "at_most_one_edit": "编辑时请只选择一项",
        "press_any_key":    "按任意键返回菜单...",
        "col_name":         "变量名",
        "col_value":        "值（截断）",
        "col_scope":        "范围",
        "col_desc":         "说明",
        "scope_user":       "用户",
        "scope_sys":        "系统",
        # 编辑
        "edit_title":       "编辑环境变量",
        "edit_name":        "变量名",
        "edit_cur_val":     "当前值",
        "edit_prompt":      "新值（直接回车保留原值，Ctrl+C 取消）: ",
        "edit_new_val":     "新值",
        "edit_confirm":     "确认修改 {name}？[y/N] ",
        "edit_done":        "已更新: {name}",
        "edit_no_change":   "值未变化，无需保存",
        "edit_cancel":      "已取消。",
        # 添加
        "add_title":        "添加新环境变量",
        "add_name_prompt":  "变量名: ",
        "add_val_prompt":   "变量值: ",
        "add_scope_prompt": "作用范围 [u=用户  s=系统]: ",
        "add_scope_invalid":"请输入 u 或 s",
        "add_confirm":      "确认添加 [{scope}] {name}？[y/N] ",
        "add_done":         "已添加: {name}",
        "add_cancel":       "已取消。",
        "add_name_empty":   "变量名不能为空",
        # 删除
        "del_confirm":      "即将删除 {n} 个变量，确认？[y/N] ",
        "del_done":         "已删除 {n} 个变量",
        "del_cancel":       "已取消。",
        # PATH 编辑器
        "path_title":       "PATH 条目编辑器",
        "path_header":      "数字键标记删除 / a 添加条目 / < > 翻页 / Enter 保存 / q 取消",
        "path_mark_del":    "标记删除",
        "path_keep":        "保留",
        "path_exists":      "✓ 存在",
        "path_missing":     "✗ 不存在",
        "path_add_prompt":  "新增路径: ",
        "path_confirm":     "删除 {n_del} 条、保留 {n_keep} 条，确认保存？[y/N] ",
        "path_saved":       "PATH 已更新",
        "path_cancel":      "已取消。",
        # 通用
        "op_fail":          "操作失败（权限不足）",
        "warn_admin":       "提示：修改系统变量需要管理员权限，请以管理员身份重新运行",
        "broadcast_ok":     "已通知系统环境变量变更（新开的进程将自动读取新值）",
        "no_items":         "当前范围内未发现环境变量",
        # 来源说明
        "legend_user":      "用户变量 = 仅当前用户生效  (HKCU\\Environment)",
        "legend_sys":       "系统变量 = 所有用户生效，修改需管理员权限  (HKLM\\...\\Environment)",
        "tip_unknown":      "提示：未显示说明的变量作者也不清楚其用途，请自行斟酌",
        # 欢迎
        "welcome_desc":     "管理 Windows 用户与系统环境变量：查看、编辑、添加、删除",
        "welcome_scan":     "开始管理",
        "welcome_quit":     "退出",
        # 语言
        "lang_title":       "选择语言 / Select Language / 言語選択",
        "lang_hint":        "数字键选择 / q 返回",
        "lang_invalid":     "无效选项，请重新输入",
    },
    "en": {
        "title":            "Windows Environment Variables Manager",
        "scan_phase":       "Reading environment variables...",
        "scan_done":        "Done — {n} variables found",
        "menu_header":      "Select variable  (number toggle / e edit / d delete / a add / f filter / < > page / p preview / l lang / q quit)",
        "filter_all":       "All",
        "filter_user":      "User",
        "filter_sys":       "System",
        "filter_label":     "Scope",
        "page_info":        "Page {cur}/{total}",
        "menu_total":       "Selected",
        "at_least_one":     "Please select at least one variable",
        "at_most_one_edit": "Please select only one variable to edit",
        "press_any_key":    "Press any key to return...",
        "col_name":         "Name",
        "col_value":        "Value (truncated)",
        "col_scope":        "Scope",
        "col_desc":         "Description",
        "scope_user":       "User",
        "scope_sys":        "System",
        "edit_title":       "Edit Environment Variable",
        "edit_name":        "Name",
        "edit_cur_val":     "Current value",
        "edit_prompt":      "New value (Enter to keep, Ctrl+C to cancel): ",
        "edit_new_val":     "New value",
        "edit_confirm":     "Confirm change to {name}? [y/N] ",
        "edit_done":        "Updated: {name}",
        "edit_no_change":   "Value unchanged — nothing to save",
        "edit_cancel":      "Cancelled.",
        "add_title":        "Add New Environment Variable",
        "add_name_prompt":  "Variable name: ",
        "add_val_prompt":   "Variable value: ",
        "add_scope_prompt": "Scope [u=User  s=System]: ",
        "add_scope_invalid":"Please enter u or s",
        "add_confirm":      "Add [{scope}] {name}? [y/N] ",
        "add_done":         "Added: {name}",
        "add_cancel":       "Cancelled.",
        "add_name_empty":   "Variable name cannot be empty",
        "del_confirm":      "About to delete {n} variables. Continue? [y/N] ",
        "del_done":         "Deleted {n} variables",
        "del_cancel":       "Cancelled.",
        "path_title":       "PATH Entry Editor",
        "path_header":      "number to mark delete / a add entry / < > page / Enter save / q cancel",
        "path_mark_del":    "marked for deletion",
        "path_keep":        "keep",
        "path_exists":      "✓ exists",
        "path_missing":     "✗ not found",
        "path_add_prompt":  "New path: ",
        "path_confirm":     "Delete {n_del} entries, keep {n_keep}. Save? [y/N] ",
        "path_saved":       "PATH updated",
        "path_cancel":      "Cancelled.",
        "op_fail":          "Operation failed (permission denied)",
        "warn_admin":       "Note: Modifying system variables requires administrator privileges",
        "broadcast_ok":     "System notified of environment change (new processes will use new values)",
        "no_items":         "No variables found in the current scope",
        "legend_user":      "User vars = current user only  (HKCU\\Environment)",
        "legend_sys":       "System vars = all users, admin required to modify  (HKLM\\...\\Environment)",
        "tip_unknown":      "Tip: variables with no description are unknown to the author — proceed with caution",
        "welcome_desc":     "Manage Windows environment variables: view, edit, add, delete",
        "welcome_scan":     "Start",
        "welcome_quit":     "Quit",
        "lang_title":       "言語選択 / Select Language / 选择语言",
        "lang_hint":        "number to select / q back",
        "lang_invalid":     "Invalid option",
    },
    "ja": {
        "title":            "Windows 環境変数マネージャー",
        "scan_phase":       "環境変数を読み込み中...",
        "scan_done":        "完了 — {n} 件の変数",
        "menu_header":      "変数選択  (数字 / e 編集 / d 削除 / a 追加 / f フィルター / < > ページ / p プレビュー / l 言語 / q 終了)",
        "filter_all":       "全て",
        "filter_user":      "ユーザー",
        "filter_sys":       "システム",
        "filter_label":     "スコープ",
        "page_info":        "{cur}/{total} ページ",
        "menu_total":       "選択中",
        "at_least_one":     "少なくとも1つ選択してください",
        "at_most_one_edit": "編集は1つのみ選択してください",
        "press_any_key":    "何かキーを押して戻る...",
        "col_name":         "変数名",
        "col_value":        "値（省略）",
        "col_scope":        "スコープ",
        "col_desc":         "説明",
        "scope_user":       "ユーザー",
        "scope_sys":        "システム",
        "edit_title":       "環境変数の編集",
        "edit_name":        "変数名",
        "edit_cur_val":     "現在の値",
        "edit_prompt":      "新しい値（Enter で保持、Ctrl+C でキャンセル）: ",
        "edit_new_val":     "新しい値",
        "edit_confirm":     "{name} を変更しますか？[y/N] ",
        "edit_done":        "更新しました: {name}",
        "edit_no_change":   "値に変更なし",
        "edit_cancel":      "キャンセルしました。",
        "add_title":        "環境変数の追加",
        "add_name_prompt":  "変数名: ",
        "add_val_prompt":   "変数値: ",
        "add_scope_prompt": "スコープ [u=ユーザー  s=システム]: ",
        "add_scope_invalid":"u または s を入力してください",
        "add_confirm":      "[{scope}] {name} を追加しますか？[y/N] ",
        "add_done":         "追加しました: {name}",
        "add_cancel":       "キャンセルしました。",
        "add_name_empty":   "変数名は空にできません",
        "del_confirm":      "{n} 件の変数を削除します。続行しますか？[y/N] ",
        "del_done":         "{n} 件を削除しました",
        "del_cancel":       "キャンセルしました。",
        "path_title":       "PATH エントリエディター",
        "path_header":      "数字で削除マーク / a 追加 / < > ページ / Enter 保存 / q キャンセル",
        "path_mark_del":    "削除マーク",
        "path_keep":        "保持",
        "path_exists":      "✓ 存在",
        "path_missing":     "✗ 存在しない",
        "path_add_prompt":  "新しいパス: ",
        "path_confirm":     "{n_del} 件削除、{n_keep} 件保持。保存しますか？[y/N] ",
        "path_saved":       "PATH を更新しました",
        "path_cancel":      "キャンセルしました。",
        "op_fail":          "操作失敗（権限不足）",
        "warn_admin":       "注意：システム変数の変更には管理者権限が必要です",
        "broadcast_ok":     "システムに変更を通知しました（新しいプロセスで反映されます）",
        "no_items":         "現在のスコープに変数が見つかりません",
        "legend_user":      "ユーザー変数 = 現在のユーザーのみ  (HKCU\\Environment)",
        "legend_sys":       "システム変数 = 全ユーザー、変更には管理者権限が必要  (HKLM\\...\\Environment)",
        "tip_unknown":      "ヒント：説明のない変数は作者も用途不明です。慎重にご判断ください",
        "welcome_desc":     "Windows 環境変数管理：表示・編集・追加・削除",
        "welcome_scan":     "開始",
        "welcome_quit":     "終了",
        "lang_title":       "言語選択 / Select Language / 选择语言",
        "lang_hint":        "数字で選択 / q 戻る",
        "lang_invalid":     "無効な選択です",
    },
}

_LANGUAGES = [("zh", "中文"), ("en", "English"), ("ja", "日本語")]


def s(key: str, **kw) -> str:
    return _UI[_lang][key].format(**kw)


# ---------- UI 工具 ----------

def _dw(text: str) -> int:
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _dw(text))


def _trunc(text: str, max_w: int) -> str:
    if _dw(text) <= max_w:
        return text
    import unicodedata
    out, w = "", 0
    for c in text:
        cw = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
        if w + cw > max_w - 1:
            return out + "…"
        out += c; w += cw
    return out


def _wait_key() -> None:
    import msvcrt
    while msvcrt.kbhit():
        msvcrt.getch()
    msvcrt.getch()


# ---------- 变量说明数据库 ----------
# 键为变量名（大写），值为 (中文, 英文, 日文)

_KNOWN: dict[str, tuple[str, str, str]] = {
    # 核心路径
    "PATH":           ("可执行文件搜索路径，系统按顺序在此列表各目录中查找命令",     "Executable search path; directories searched in order for commands",     "実行ファイルの検索パス（;区切り）"),
    "PATHEXT":        ("CMD 可直接执行的文件扩展名列表",                           "File extensions treated as executables by CMD",                          "CMDが実行可能なファイル拡張子リスト"),
    "TEMP":           ("临时文件存放目录，程序写入临时数据的默认位置",               "Temporary files directory used by most programs",                        "一時ファイルの保存先"),
    "TMP":            ("临时文件目录（TEMP 的别名，通常两者相同）",                 "Temp directory alias, usually identical to TEMP",                        "一時ファイルディレクトリ（TEMPの別名）"),
    "COMSPEC":        ("默认命令行解释器路径（通常为 cmd.exe）",                    "Default command interpreter (usually cmd.exe)",                          "デフォルトコマンドインタープリター（通常 cmd.exe）"),
    # Windows 系统目录
    "WINDIR":         ("Windows 系统目录（通常 C:\\Windows）",                    "Windows system directory (usually C:\\Windows)",                         "Windowsシステムディレクトリ"),
    "SYSTEMROOT":     ("Windows 系统根目录，与 WINDIR 相同",                      "Windows system root, same as WINDIR",                                    "Windowsシステムルート（WINDIRと同じ）"),
    "SYSTEMDRIVE":    ("系统盘盘符（通常 C:）",                                   "System drive letter (usually C:)",                                       "システムドライブ文字（通常 C:）"),
    "PROGRAMFILES":   ("64 位程序的默认安装目录",                                  "Default installation directory for 64-bit programs",                     "64ビットプログラムのデフォルトインストール先"),
    "PROGRAMFILES(X86)": ("32 位程序在 64 位系统上的安装目录",                    "Installation directory for 32-bit programs on 64-bit Windows",           "64ビットWindowsでの32ビットプログラムインストール先"),
    "PROGRAMW6432":   ("同 PROGRAMFILES（兼容性别名）",                           "Same as PROGRAMFILES (compatibility alias)",                             "PROGRAMFILESと同じ（互換性エイリアス）"),
    "PROGRAMDATA":    ("所有用户共享的应用程序数据目录",                            "Shared application data directory for all users",                       "全ユーザー共有のアプリケーションデータ"),
    "COMMONPROGRAMFILES":    ("多应用共享的公共程序文件目录",                       "Common program files shared by multiple applications",                   "共通プログラムファイルディレクトリ"),
    "COMMONPROGRAMFILES(X86)": ("32 位公共程序文件目录",                           "32-bit common program files directory",                                 "32ビット共通プログラムファイル"),
    # 用户目录
    "USERPROFILE":    ("当前用户的主目录（如 C:\\Users\\Username）",               "Current user's home directory",                                          "現在のユーザーのホームディレクトリ"),
    "APPDATA":        ("用户漫游应用数据目录，域账户会同步此目录",                   "Roaming application data, synced with domain accounts",                 "ローミングアプリデータ（ドメインアカウントで同期）"),
    "LOCALAPPDATA":   ("用户本地应用数据目录，不进行同步",                          "Local application data, not synced across machines",                    "ローカルアプリデータ（同期なし）"),
    "HOMEPATH":       ("用户主目录相对路径，不含盘符（旧版变量）",                   "User home path without drive letter (legacy variable)",                 "ユーザーホームパス（ドライブレター除く）"),
    "HOMEDRIVE":      ("用户主目录所在盘符（与 HOMEPATH 配合使用）",                "Drive letter of user home directory",                                   "ホームディレクトリのドライブ文字"),
    "ONEDRIVE":       ("OneDrive 个人账户同步目录",                                "OneDrive personal sync folder",                                         "OneDrive個人同期フォルダー"),
    "ONEDRIVECONSUMER": ("OneDrive 消费者版同步目录",                              "OneDrive consumer sync folder",                                         "OneDriveコンシューマー同期フォルダー"),
    "ONEDRIVECOMMERCIAL": ("OneDrive 商业版同步目录",                              "OneDrive for Business sync folder",                                     "OneDrive Business同期フォルダー"),
    # 系统信息
    "COMPUTERNAME":   ("计算机名称",                                               "Computer / hostname",                                                   "コンピューター名"),
    "USERNAME":       ("当前登录用户的用户名",                                      "Currently logged-in username",                                          "現在のログインユーザー名"),
    "USERDOMAIN":     ("用户所在 Windows 域名（本地账户则为计算机名）",              "User's domain (or computer name for local accounts)",                   "ユーザーのWindowsドメイン"),
    "OS":             ("操作系统名称（固定为 Windows_NT）",                         "OS identifier (always Windows_NT)",                                     "OS識別子（常にWindows_NT）"),
    "PROCESSOR_ARCHITECTURE": ("CPU 架构：AMD64 / x86 / ARM64",                  "CPU architecture: AMD64 / x86 / ARM64",                                 "CPUアーキテクチャ"),
    "NUMBER_OF_PROCESSORS": ("逻辑处理器数量（核心 × 线程）",                     "Number of logical processors",                                          "論理プロセッサ数"),
    "PROCESSOR_IDENTIFIER": ("CPU 型号标识字符串",                                 "CPU model identifier string",                                           "CPU識別子文字列"),
    # PowerShell
    "PSMODULEPATH":   ("PowerShell 模块搜索路径",                                  "PowerShell module search path",                                         "PowerShellモジュール検索パス"),
    # Java
    "JAVA_HOME":      ("Java JDK 安装根目录，Java 相关工具链必须设置此变量",         "Java JDK root; required by most Java toolchain tools",                  "Java JDKインストールルート（必須）"),
    "JRE_HOME":       ("Java 运行时目录（部分旧工具使用）",                          "Java Runtime Environment directory (used by some legacy tools)",        "Java実行環境ディレクトリ"),
    "CLASSPATH":      ("Java 类文件额外搜索路径",                                   "Extra Java class file search path",                                     "Javaクラスファイル追加検索パス"),
    # Python
    "PYTHONPATH":     ("Python 额外模块搜索路径，追加到 sys.path",                  "Extra Python module search path, appended to sys.path",                 "Python追加モジュール検索パス"),
    "PYTHONSTARTUP":  ("Python 启动时自动执行的脚本路径",                            "Script executed automatically when Python starts",                      "Python起動時自動実行スクリプト"),
    "PYTHONHOME":     ("Python 标准库目录，通常无需手动设置",                        "Python standard library location (usually auto-detected)",              "Python標準ライブラリディレクトリ"),
    "VIRTUAL_ENV":    ("当前激活的 Python 虚拟环境路径",                            "Currently active Python virtual environment path",                      "現在アクティブなPython仮想環境"),
    "CONDA_PREFIX":   ("当前激活的 Conda 环境路径",                                 "Currently active Conda environment path",                               "現在アクティブなConda環境"),
    "PIP_CACHE_DIR":  ("pip 包缓存目录，可改到空间充足的分区",                       "pip package cache directory",                                           "pipパッケージキャッシュディレクトリ"),
    # Node.js
    "NODE_PATH":      ("Node.js 模块额外搜索路径",                                  "Extra Node.js module search path",                                      "Node.js追加モジュール検索パス"),
    "NVM_HOME":       ("nvm（Node 版本管理器）安装目录",                            "nvm (Node Version Manager) installation directory",                     "nvm インストールディレクトリ"),
    "NVM_SYMLINK":    ("nvm 当前 Node.js 版本的符号链接目录",                       "nvm symlink directory for active Node.js version",                     "nvmアクティブNode.jsシンボリックリンク"),
    # Go
    "GOPATH":         ("Go 工作区目录，存放依赖包和编译产物",                        "Go workspace for dependencies and build output",                        "Goワークスペースディレクトリ"),
    "GOROOT":         ("Go 安装目录，标准库所在位置",                               "Go installation directory containing the standard library",             "Goインストールディレクトリ"),
    "GOBIN":          ("go install 编译产物的输出目录",                             "Output directory for go install binaries",                              "go installバイナリ出力ディレクトリ"),
    "GOMODCACHE":     ("Go 模块缓存目录",                                           "Go module cache directory",                                             "Goモジュールキャッシュ"),
    "GOPROXY":        ("Go 模块代理服务器地址",                                      "Go module proxy URL",                                                   "Goモジュールプロキシ"),
    # Rust
    "CARGO_HOME":     ("Rust Cargo 包管理器主目录，存放工具链和已安装包",            "Rust Cargo home; stores toolchains and installed packages",             "Rust Cargoホームディレクトリ"),
    "RUSTUP_HOME":    ("rustup 工具链管理器目录",                                   "rustup toolchain manager directory",                                    "rustupツールチェーンディレクトリ"),
    # JVM 构建工具
    "GRADLE_HOME":    ("Gradle 构建工具安装目录",                                   "Gradle build tool installation directory",                              "Gradleインストールディレクトリ"),
    "GRADLE_USER_HOME": ("Gradle 缓存与配置目录（默认 ~/.gradle）",                "Gradle cache and config directory (default: ~/.gradle)",                "Gradleキャッシュと設定ディレクトリ"),
    "MAVEN_HOME":     ("Apache Maven 安装目录",                                    "Apache Maven installation directory",                                   "Apache Mavenインストールディレクトリ"),
    "M2_HOME":        ("Maven 主目录（同 MAVEN_HOME）",                            "Maven home, same as MAVEN_HOME",                                        "Mavenホーム（MAVEN_HOMEと同じ）"),
    # Android
    "ANDROID_HOME":   ("Android SDK 根目录（推荐使用此变量名）",                    "Android SDK root directory (recommended variable name)",                "Android SDKルートディレクトリ（推奨）"),
    "ANDROID_SDK_ROOT": ("Android SDK 根目录（旧版变量名）",                        "Android SDK root (legacy variable name)",                               "Android SDKルート（旧変数名）"),
    "ANDROID_NDK_HOME": ("Android NDK 原生开发套件目录",                            "Android NDK (native development kit) directory",                        "Android NDKディレクトリ"),
    # C/C++
    "CMAKE_HOME":     ("CMake 构建系统安装目录",                                    "CMake build system installation directory",                             "CMakeインストールディレクトリ"),
    "VCPKG_ROOT":     ("vcpkg C++ 包管理器根目录",                                  "vcpkg C++ package manager root directory",                              "vcpkg C++パッケージマネージャールート"),
    "INCLUDE":        ("MSVC 额外头文件搜索路径",                                   "Additional include file search paths for MSVC",                         "MSVCインクルードファイル追加パス"),
    "LIB":            ("MSVC 额外库文件搜索路径",                                   "Additional library search paths for MSVC",                              "MSVCライブラリ追加検索パス"),
    # GPU / AI
    "CUDA_PATH":      ("NVIDIA CUDA 工具包安装路径",                                "NVIDIA CUDA toolkit installation path",                                 "NVIDIA CUDAツールキットパス"),
    "CUDA_HOME":      ("CUDA 主目录（部分工具使用，通常同 CUDA_PATH）",              "CUDA home directory (used by some tools, usually same as CUDA_PATH)",  "CUDAホームディレクトリ"),
    "HF_HOME":        ("HuggingFace Hub 主目录，用于缓存模型和数据集",              "HuggingFace Hub home for caching models and datasets",                  "HuggingFace Hubホームディレクトリ"),
    "HUGGINGFACE_HUB_CACHE": ("HuggingFace 模型缓存目录",                          "HuggingFace model cache directory",                                     "HuggingFaceモデルキャッシュ"),
    "TRANSFORMERS_CACHE": ("Transformers 缓存目录（已被 HF_HOME 替代）",            "Transformers cache (superseded by HF_HOME)",                            "Transformersキャッシュ（HF_HOMEに移行）"),
    "TORCH_HOME":     ("PyTorch 预训练模型缓存目录",                                "PyTorch pretrained model cache directory",                              "PyTorchモデルキャッシュ"),
    "OLLAMA_MODELS":  ("Ollama 本地大模型存储目录",                                 "Ollama local LLM model storage directory",                              "Ollama LLMモデル保存ディレクトリ"),
    # 代理
    "HTTP_PROXY":     ("HTTP 代理地址，影响 curl/wget/pip 等命令行工具",            "HTTP proxy; affects curl, wget, pip and other CLI tools",               "HTTPプロキシアドレス"),
    "HTTPS_PROXY":    ("HTTPS 代理地址",                                            "HTTPS proxy address",                                                   "HTTPSプロキシアドレス"),
    "ALL_PROXY":      ("全局代理地址，HTTP 和 HTTPS 均使用",                        "Global proxy for both HTTP and HTTPS",                                  "グローバルプロキシアドレス"),
    "NO_PROXY":       ("不经过代理的地址列表，逗号分隔",                             "Comma-separated addresses to bypass proxy",                             "プロキシをバイパスするアドレスリスト"),
    # 开发工具
    "GIT_HOME":       ("Git 安装目录",                                              "Git installation directory",                                            "Gitインストールディレクトリ"),
    "EDITOR":         ("默认文本编辑器，部分 CLI 工具（如 git commit）会调用",       "Default text editor, used by git commit and other CLI tools",           "デフォルトテキストエディター"),
    "VISUAL":         ("默认可视化编辑器，部分工具优先于 EDITOR",                    "Default visual editor, some tools prefer this over EDITOR",             "デフォルトビジュアルエディター"),
    "DOCKER_HOST":    ("Docker 守护进程连接地址",                                   "Docker daemon connection address",                                      "Dockerデーモン接続アドレス"),
    "DOCKER_BUILDKIT": ("启用 Docker BuildKit，设为 1 开启",                        "Enable Docker BuildKit (set to 1)",                                     "Docker BuildKit有効化（1で有効）"),
    "KUBECONFIG":     ("kubectl 配置文件路径（Kubernetes）",                        "kubectl config file path (Kubernetes)",                                 "kubectl設定ファイルパス"),
    "XDG_CACHE_HOME": ("XDG 缓存目录，部分 Linux 移植工具遵循此约定",               "XDG cache dir; used by some Linux-ported tools on Windows",             "XDGキャッシュディレクトリ"),
    "XDG_CONFIG_HOME": ("XDG 配置目录",                                             "XDG config directory",                                                  "XDG設定ディレクトリ"),
    "XDG_DATA_HOME":  ("XDG 数据目录",                                              "XDG data directory",                                                    "XDGデータディレクトリ"),
    # 云 / API
    "AWS_PROFILE":    ("AWS CLI 默认配置文件名",                                    "AWS CLI default profile name",                                          "AWS CLIデフォルトプロファイル名"),
    "AWS_DEFAULT_REGION": ("AWS 默认服务区域",                                      "AWS default service region",                                            "AWSデフォルトリージョン"),
    "GOOGLE_APPLICATION_CREDENTIALS": ("Google Cloud 服务账号密钥 JSON 文件路径",  "Google Cloud service account key file path",                            "Google Cloudサービスアカウントキーファイル"),
    "OPENAI_API_KEY": ("OpenAI API 密钥",                                           "OpenAI API key",                                                        "OpenAI APIキー"),
    "ANTHROPIC_API_KEY": ("Anthropic Claude API 密钥",                             "Anthropic Claude API key",                                              "Anthropic Claude APIキー"),
}

_LANG_IDX = {"zh": 0, "en": 1, "ja": 2}

# 这些变量的值是分号分隔的路径列表，使用专属 PATH 编辑器
_PATH_LIKE = {"PATH", "PATHEXT", "PSMODULEPATH", "CLASSPATH", "NODE_PATH",
              "INCLUDE", "LIB", "PYTHONPATH"}


def _get_desc(name: str) -> str:
    idx = _LANG_IDX.get(_lang, 1)
    return _KNOWN.get(name.upper(), ("", "", ""))[idx]


def _is_path_like(name: str) -> bool:
    n = name.upper()
    return n in _PATH_LIKE or n.endswith("PATH") or n.endswith("PATHS")


# ---------- 数据结构 ----------

@dataclass
class EnvVar:
    name:  str
    value: str
    scope: str   # "User" | "System"

    @property
    def desc(self) -> str:
        return _get_desc(self.name)

    @property
    def is_path_like(self) -> bool:
        return _is_path_like(self.name)

    @property
    def scope_label(self) -> str:
        return s("scope_user") if self.scope == "User" else s("scope_sys")

    def key(self) -> tuple[str, str]:
        return (self.name, self.scope)


# ---------- 注册表读写 ----------

_REG_USER = r"Environment"
_REG_SYS  = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"


def _reg_hive_path(scope: str) -> tuple[int, str]:
    if scope == "User":
        return winreg.HKEY_CURRENT_USER, _REG_USER
    return winreg.HKEY_LOCAL_MACHINE, _REG_SYS


def scan_all() -> list[EnvVar]:
    result: list[EnvVar] = []
    for scope, hive, path in [("User", winreg.HKEY_CURRENT_USER, _REG_USER),
                               ("System", winreg.HKEY_LOCAL_MACHINE, _REG_SYS)]:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
        except OSError:
            continue
        i = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, i)
                result.append(EnvVar(name=name, value=str(value), scope=scope))
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    result.sort(key=lambda e: (e.scope, e.name.upper()))
    return result


def _write_var(name: str, value: str, scope: str) -> bool:
    hive, path = _reg_hive_path(scope)
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_WRITE)
        reg_type = (winreg.REG_EXPAND_SZ
                    if "%" in value or _is_path_like(name)
                    else winreg.REG_SZ)
        winreg.SetValueEx(key, name, 0, reg_type, value)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def _delete_var(name: str, scope: str) -> bool:
    hive, path = _reg_hive_path(scope)
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_WRITE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def _broadcast() -> None:
    try:
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None
        )
    except Exception:
        pass


# ---------- 欢迎 / 语言界面 ----------

_WELCOME_ART = r"""  ___ _  _ __   __ __  __  ___ ___
 | __| \| |\ \ / / |  \/  |/ __| _ \
 | _|| .` | \ V /  | |\/| | (_ |   /
 |___|_|\_|  \_/   |_|  |_|\___|_|_\
"""


def _render_lang_menu(status: str = "") -> str:
    SEP  = "=" * 60
    SEP2 = "-" * 60
    lines = [SEP, f"  {s('lang_title')}", f"  ({s('lang_hint')})", SEP]
    for i, (code, label) in enumerate(_LANGUAGES, 1):
        marker = "●" if code == _lang else " "
        lines.append(f"  [{i}] {marker}  {label}")
    lines.append(SEP2)
    if status:
        lines.append(f"  {YELLOW}{status}{RESET}")
    lines.append("> ")
    return "\n".join(lines)


def select_language() -> None:
    global _lang
    import msvcrt
    while msvcrt.kbhit():
        msvcrt.getch()
    status = ""
    menu_text = _render_lang_menu()
    print(menu_text, end="", flush=True)
    while True:
        key = msvcrt.getch()
        if key in (b"\x00", b"\xe0"):
            msvcrt.getch(); continue
        try:
            ch = key.decode("utf-8").lower()
        except (UnicodeDecodeError, AttributeError):
            continue
        if ch == "\x03":
            print(); sys.exit(0)
        elif ch == "q":
            print(); return
        elif ch in "123":
            idx = int(ch) - 1
            if idx < len(_LANGUAGES):
                _lang = _LANGUAGES[idx][0]; print(); return
            status = s("lang_invalid")
        else:
            status = s("lang_invalid")
        n_up = menu_text.count("\n")
        print(f"\033[{n_up}A\r\033[J", end="", flush=True)
        menu_text = _render_lang_menu(status)
        print(menu_text.replace("\n", "\033[K\n") + "\033[K", end="", flush=True)


def _render_welcome() -> str:
    SEP  = "=" * 62
    SEP2 = "-" * 62
    lines = [SEP, ""]
    for line in _WELCOME_ART.split("\n"):
        lines.append(f"  {line}")
    lines += [
        "",
        f"  {s('welcome_desc')}",
        "",
        SEP2,
        f"  [1]  Change Language / 切换语言 / 言語変更",
        f"  [2]  {s('welcome_scan')}",
        f"  [q]  {s('welcome_quit')}",
        SEP,
        "> ",
    ]
    return "\n".join(lines)


def show_welcome() -> None:
    import msvcrt
    while True:
        os.system("cls")
        print(_render_welcome(), end="", flush=True)
        while msvcrt.kbhit():
            msvcrt.getch()
        while True:
            key = msvcrt.getch()
            if key in (b"\x00", b"\xe0"):
                msvcrt.getch(); continue
            try:
                ch = key.decode("utf-8").lower()
            except (UnicodeDecodeError, AttributeError):
                continue
            if ch == "\x03":
                print(); sys.exit(0)
            elif ch == "1":
                print(); os.system("cls"); select_language(); break
            elif ch == "2":
                print(); return
            elif ch == "q":
                print(); sys.exit(0)


# ---------- 主菜单 ----------

_PAGE_SIZE = 8
_FILTERS   = ("all", "user", "sys")


def _filtered(entries: list[EnvVar], filt: str) -> list[EnvVar]:
    if filt == "user":   return [e for e in entries if e.scope == "User"]
    if filt == "sys":    return [e for e in entries if e.scope == "System"]
    return entries


def render_menu(all_entries: list[EnvVar], sel_keys: set[tuple[str, str]],
                page: int, filt: str, status: str = "") -> str:
    view = _filtered(all_entries, filt)
    total_pages = max(1, (len(view) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page_ents   = view[page * _PAGE_SIZE: (page + 1) * _PAGE_SIZE]

    fl = {"all": s("filter_all"), "user": s("filter_user"), "sys": s("filter_sys")}
    filt_str = " / ".join(
        f"{BOLD}{fl[f]}{RESET}" if f == filt else fl[f] for f in _FILTERS
    )

    SEP  = "=" * 76
    SEP2 = "-" * 76
    lines = [
        SEP,
        f"  {s('menu_header')}",
        f"  {CYAN}{s('page_info', cur=page+1, total=total_pages)}{RESET}"
        f"  |  {s('filter_label')}: {filt_str}",
        SEP,
    ]

    NAME_W = 22
    VAL_W  = 24
    SC_W   = 6
    DESC_W = 18

    for i, entry in enumerate(page_ents, 1):
        check  = "✓" if entry.key() in sel_keys else " "
        name_s = _trunc(entry.name,  NAME_W)
        val_s  = _trunc(entry.value, VAL_W)
        sc_c   = CYAN if entry.scope == "User" else YELLOW
        desc_s = _trunc(entry.desc, DESC_W)
        lines.append(
            f"  [{i}] {check}  {_pad(name_s, NAME_W)}  "
            f"{sc_c}{_pad(entry.scope_label, SC_W)}{RESET}  "
            f"{DIM}{_pad(val_s, VAL_W)}{RESET}  "
            f"{desc_s}"
        )

    lines.append(SEP2)
    lines.append(f"  {s('menu_total')}: {len(sel_keys)}")
    lines.append(SEP2)
    lines.append(f"  {DIM}{s('legend_user')}{RESET}")
    lines.append(f"  {DIM}{s('legend_sys')}{RESET}")
    lines.append(f"  {YELLOW}{s('tip_unknown')}{RESET}")
    if status:
        lines.append(f"  {YELLOW}{status}{RESET}")
    lines.append("> ")
    return "\n".join(lines)


def select_menu(all_entries: list[EnvVar]) -> tuple[str, list[EnvVar]] | None:
    import msvcrt
    while msvcrt.kbhit():
        msvcrt.getch()

    sel_keys: set[tuple[str, str]] = set()
    page   = 0
    filt   = "all"
    status = ""

    def view():
        return _filtered(all_entries, filt)

    def total_pages():
        return max(1, (len(view()) + _PAGE_SIZE - 1) // _PAGE_SIZE)

    menu_text = render_menu(all_entries, sel_keys, page, filt, status)
    print(menu_text, end="", flush=True)

    def _redraw():
        nonlocal menu_text
        n_up = menu_text.count("\n")
        print(f"\033[{n_up}A\r\033[J", end="", flush=True)
        menu_text = render_menu(all_entries, sel_keys, page, filt, status)
        print(menu_text.replace("\n", "\033[K\n") + "\033[K", end="", flush=True)

    while True:
        try:
            key = msvcrt.getch()
        except KeyboardInterrupt:
            print(); sys.exit(0)

        if key in (b"\x00", b"\xe0"):
            arrow = msvcrt.getch()
            if arrow == b"K":
                page = max(0, page - 1); status = ""; _redraw()
            elif arrow == b"M":
                page = min(total_pages() - 1, page + 1); status = ""; _redraw()
            continue

        try:
            ch = key.decode("utf-8").lower()
        except (UnicodeDecodeError, AttributeError):
            continue

        if ch == "\x03":
            print(); sys.exit(0)

        elif ch in "12345678":
            v = view()
            idx = page * _PAGE_SIZE + int(ch) - 1
            if idx < len(v):
                k = v[idx].key()
                if k in sel_keys:
                    sel_keys.discard(k)
                else:
                    sel_keys.add(k)
                status = ""; _redraw()

        elif ch == "a":
            print(); return "add", []

        elif ch in ("e", "\r", "\n"):
            if not sel_keys:
                status = s("at_least_one"); _redraw()
            elif len(sel_keys) > 1:
                status = s("at_most_one_edit"); _redraw()
            else:
                k = next(iter(sel_keys))
                entry = next((e for e in all_entries if e.key() == k), None)
                if entry:
                    print(); return "edit", [entry]

        elif ch == "d":
            if not sel_keys:
                status = s("at_least_one"); _redraw()
            else:
                selected = [e for e in all_entries if e.key() in sel_keys]
                print(); return "delete", selected

        elif ch == "f":
            filt = _FILTERS[(_FILTERS.index(filt) + 1) % len(_FILTERS)]
            page = 0; sel_keys.clear(); status = ""; _redraw()

        elif ch == "n":
            sel_keys.clear(); status = ""; _redraw()

        elif ch == "<":
            page = max(0, page - 1); status = ""; _redraw()

        elif ch == ">":
            page = min(total_pages() - 1, page + 1); status = ""; _redraw()

        elif ch == "p":
            if not sel_keys:
                status = s("at_least_one"); _redraw()
            else:
                os.system("cls")
                for k in sel_keys:
                    entry = next((e for e in all_entries if e.key() == k), None)
                    if not entry:
                        continue
                    sc_c = CYAN if entry.scope == "User" else YELLOW
                    print(f"\n  {BOLD}{entry.name}{RESET}  {sc_c}[{entry.scope_label}]{RESET}")
                    if entry.is_path_like:
                        for part in entry.value.split(";"):
                            if part.strip():
                                tag = (f"{GREEN}{s('path_exists')}{RESET}"
                                       if Path(part.strip()).exists()
                                       else f"{YELLOW}{s('path_missing')}{RESET}")
                                print(f"    {tag}  {part.strip()}")
                    else:
                        print(f"    {CYAN}{entry.value}{RESET}")
                print(f"\n{YELLOW}{s('press_any_key')}{RESET}", end="", flush=True)
                _wait_key()
                os.system("cls")
                menu_text = render_menu(all_entries, sel_keys, page, filt, "")
                print(menu_text, end="", flush=True)

        elif ch == "l":
            os.system("cls"); select_language(); os.system("cls")
            menu_text = render_menu(all_entries, sel_keys, page, filt, "")
            print(menu_text, end="", flush=True)

        elif ch == "q":
            print(); return None


# ---------- PATH 编辑器 ----------

_PATH_PAGE = 9


def path_editor(entry: EnvVar) -> str | None:
    import msvcrt

    parts   = [p.strip() for p in entry.value.split(";") if p.strip()]
    marked: set[int] = set()
    page    = 0
    status  = ""

    def total_pages():
        return max(1, (len(parts) + _PATH_PAGE - 1) // _PATH_PAGE)

    def _render() -> str:
        tp = total_pages()
        start = page * _PATH_PAGE
        page_parts = parts[start: start + _PATH_PAGE]
        sc_c = CYAN if entry.scope == "User" else YELLOW
        SEP  = "=" * 72
        SEP2 = "-" * 72
        lines = [
            SEP,
            f"  {s('path_title')}  {sc_c}[{entry.scope_label}]  {entry.name}{RESET}",
            f"  {s('path_header')}",
            f"  {CYAN}{start+1}–{min(start+_PATH_PAGE, len(parts))}/{len(parts)}{RESET}"
            f"  |  {CYAN}{page+1}/{tp}{RESET}",
            SEP,
        ]
        for i, part in enumerate(page_parts, 1):
            real = start + i - 1
            del_mark = real in marked
            exist = Path(part).exists()
            exist_s = (f"{GREEN}{s('path_exists')}{RESET}"
                       if exist else f"{YELLOW}{s('path_missing')}{RESET}")
            mark_s  = f"{RED}✗{RESET}" if del_mark else " "
            name_c  = RED if del_mark else ""
            reset_c = RESET if del_mark else ""
            lines.append(
                f"  [{i}] {mark_s}  {name_c}{_trunc(part, 52)}{reset_c}  {exist_s}"
            )
        lines.append(SEP2)
        n_del  = len(marked)
        n_keep = len(parts) - n_del
        lines.append(
            f"  {RED}{s('path_mark_del')}: {n_del}{RESET}  "
            f"{GREEN}{s('path_keep')}: {n_keep}{RESET}"
        )
        if status:
            lines.append(f"  {YELLOW}{status}{RESET}")
        lines.append("> ")
        return "\n".join(lines)

    os.system("cls")
    menu_text = _render()
    print(menu_text, end="", flush=True)

    def _redraw():
        nonlocal menu_text
        n_up = menu_text.count("\n")
        print(f"\033[{n_up}A\r\033[J", end="", flush=True)
        menu_text = _render()
        print(menu_text.replace("\n", "\033[K\n") + "\033[K", end="", flush=True)

    while True:
        try:
            key = msvcrt.getch()
        except KeyboardInterrupt:
            print(); return None

        if key in (b"\x00", b"\xe0"):
            arrow = msvcrt.getch()
            if arrow == b"K":
                page = max(0, page - 1); status = ""; _redraw()
            elif arrow == b"M":
                page = min(total_pages() - 1, page + 1); status = ""; _redraw()
            continue

        try:
            ch = key.decode("utf-8").lower()
        except (UnicodeDecodeError, AttributeError):
            continue

        if ch == "\x03":
            print(); sys.exit(0)
        elif ch == "q":
            print(); return None
        elif ch == "<":
            page = max(0, page - 1); status = ""; _redraw()
        elif ch == ">":
            page = min(total_pages() - 1, page + 1); status = ""; _redraw()
        elif ch == "a":
            print()
            try:
                new_p = input(f"  {YELLOW}{s('path_add_prompt')}{RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                new_p = ""
            if new_p:
                parts.append(new_p)
                page = total_pages() - 1
            status = ""
            os.system("cls")
            menu_text = _render()
            print(menu_text, end="", flush=True)
        elif ch in ("\r", "\n"):
            n_del  = len(marked)
            n_keep = len(parts) - n_del
            print()
            try:
                ans = input(
                    f"  {YELLOW}{s('path_confirm', n_del=n_del, n_keep=n_keep)}{RESET}"
                ).strip().lower()
            except (KeyboardInterrupt, EOFError):
                ans = ""
            if ans == "y":
                return ";".join(p for i, p in enumerate(parts) if i not in marked)
            status = s("path_cancel")
            os.system("cls")
            menu_text = _render()
            print(menu_text, end="", flush=True)
        elif ch.isdigit():
            idx_page = int(ch) - 1
            real     = page * _PATH_PAGE + idx_page
            if 0 <= real < len(parts):
                if real in marked:
                    marked.discard(real)
                else:
                    marked.add(real)
                status = ""; _redraw()


# ---------- 编辑变量 ----------

def edit_var(entry: EnvVar) -> bool:
    os.system("cls")
    sc_c = CYAN if entry.scope == "User" else YELLOW

    if entry.is_path_like:
        new_val = path_editor(entry)
        os.system("cls")
        if new_val is None or new_val == entry.value:
            return False
        ok = _write_var(entry.name, new_val, entry.scope)
        if ok:
            entry.value = new_val
            _broadcast()
            print(f"\n  {GREEN}{s('path_saved')}{RESET}")
            print(f"  {DIM}{s('broadcast_ok')}{RESET}\n")
        else:
            print(f"\n  {RED}{s('op_fail')}{RESET}")
            if entry.scope == "System":
                print(f"  {YELLOW}{s('warn_admin')}{RESET}\n")
        _wait_key()
        return ok

    SEP = "─" * 60
    print(f"\n  {BOLD}{s('edit_title')}{RESET}  {sc_c}[{entry.scope_label}]{RESET}\n")
    print(f"  {s('edit_name')}:     {BOLD}{entry.name}{RESET}")
    print(f"  {s('edit_cur_val')}:")
    print(f"  {CYAN}{entry.value}{RESET}")
    print(f"  {SEP}")
    try:
        new_val = input(f"  {YELLOW}{s('edit_prompt')}{RESET}")
    except (KeyboardInterrupt, EOFError):
        print(f"\n  {s('edit_cancel')}"); _wait_key(); return False

    if not new_val:
        new_val = entry.value
    if new_val == entry.value:
        print(f"\n  {DIM}{s('edit_no_change')}{RESET}"); _wait_key(); return False

    print(f"\n  {s('edit_new_val')}:")
    print(f"  {CYAN}{new_val}{RESET}\n")
    try:
        ans = input(f"  {YELLOW}{s('edit_confirm', name=entry.name)}{RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        ans = ""

    if ans != "y":
        print(f"\n  {s('edit_cancel')}"); _wait_key(); return False

    ok = _write_var(entry.name, new_val, entry.scope)
    if ok:
        entry.value = new_val
        _broadcast()
        print(f"\n  {GREEN}{s('edit_done', name=entry.name)}{RESET}")
        print(f"  {DIM}{s('broadcast_ok')}{RESET}")
    else:
        print(f"\n  {RED}{s('op_fail')}{RESET}")
        if entry.scope == "System":
            print(f"  {YELLOW}{s('warn_admin')}{RESET}")
    _wait_key()
    return ok


# ---------- 添加变量 ----------

def add_var(all_entries: list[EnvVar]) -> EnvVar | None:
    os.system("cls")
    print(f"\n  {BOLD}{s('add_title')}{RESET}\n")

    try:
        name = input(f"  {YELLOW}{s('add_name_prompt')}{RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        return None
    if not name:
        print(f"\n  {RED}{s('add_name_empty')}{RESET}"); _wait_key(); return None

    try:
        value = input(f"  {YELLOW}{s('add_val_prompt')}{RESET}")
    except (KeyboardInterrupt, EOFError):
        return None

    scope = ""
    while scope not in ("User", "System"):
        try:
            ch = input(f"  {YELLOW}{s('add_scope_prompt')}{RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None
        if ch == "u":
            scope = "User"
        elif ch == "s":
            scope = "System"
        else:
            print(f"  {RED}{s('add_scope_invalid')}{RESET}")

    sc_c   = CYAN if scope == "User" else YELLOW
    sc_lbl = s("scope_user") if scope == "User" else s("scope_sys")
    print(f"\n  {BOLD}{name}{RESET}  {sc_c}[{sc_lbl}]{RESET}")
    print(f"  {CYAN}{value}{RESET}\n")
    try:
        ans = input(f"  {YELLOW}{s('add_confirm', scope=sc_lbl, name=name)}{RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        ans = ""

    if ans != "y":
        print(f"\n  {s('add_cancel')}"); _wait_key(); return None

    ok = _write_var(name, value, scope)
    if ok:
        _broadcast()
        print(f"\n  {GREEN}{s('add_done', name=name)}{RESET}")
        print(f"  {DIM}{s('broadcast_ok')}{RESET}")
        _wait_key()
        return EnvVar(name=name, value=value, scope=scope)
    else:
        print(f"\n  {RED}{s('op_fail')}{RESET}")
        if scope == "System":
            print(f"  {YELLOW}{s('warn_admin')}{RESET}")
        _wait_key()
        return None


# ---------- 删除变量 ----------

def delete_vars(to_del: list[EnvVar], all_entries: list[EnvVar]) -> int:
    print()
    try:
        ans = input(f"  {YELLOW}{s('del_confirm', n=len(to_del))}{RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        ans = ""
    if ans != "y":
        print(f"  {s('del_cancel')}"); _wait_key(); return 0

    n_ok = 0
    print()
    for entry in to_del:
        ok = _delete_var(entry.name, entry.scope)
        tag = f"{GREEN}OK{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  [{tag}]  {entry.name}  {DIM}[{entry.scope_label}]{RESET}")
        if ok:
            all_entries.remove(entry)
            n_ok += 1

    if n_ok:
        _broadcast()
    print(f"\n  {GREEN}{s('del_done', n=n_ok)}{RESET}")
    _wait_key()
    return n_ok


# ---------- 主流程 ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="envmgr",
        description="Windows 环境变量管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python envmgr.py             # 交互式管理界面
  python envmgr.py --list      # 列出所有变量后退出
  python envmgr.py --list --user    # 只列用户变量
  python envmgr.py --list --system  # 只列系统变量
        """,
    )
    p.add_argument("--list",   action="store_true", help="列出所有环境变量后退出")
    p.add_argument("--user",   action="store_true", help="仅显示用户变量（配合 --list）")
    p.add_argument("--system", action="store_true", help="仅显示系统变量（配合 --list）")
    return p.parse_args()


def main():
    args = parse_args()

    if not args.list:
        show_welcome()
        os.system("cls")

    print(f"\n{BOLD}{s('title')}{RESET}")
    print(f"{CYAN}{s('scan_phase')}{RESET}", end="", flush=True)
    all_entries = scan_all()
    print(f"\r{GREEN}✓{RESET}  {s('scan_done', n=len(all_entries))}\n")

    if args.list:
        show_scope = (None if not (args.user ^ args.system)
                      else ("User" if args.user else "System"))
        entries = [e for e in all_entries
                   if show_scope is None or e.scope == show_scope]
        if not entries:
            print(f"  {YELLOW}{s('no_items')}{RESET}"); return
        name_w  = max(_dw(e.name)        for e in entries)
        scope_w = max(_dw(e.scope_label) for e in entries)
        for e in entries:
            sc_c = CYAN if e.scope == "User" else YELLOW
            line = (f"  {sc_c}{_pad(e.scope_label, scope_w)}{RESET}  "
                    f"{BOLD}{_pad(e.name, name_w)}{RESET}  "
                    f"{DIM}{_trunc(e.value, 55)}{RESET}")
            if e.desc:
                line += f"  {e.desc}"
            print(line)
        return

    if not all_entries:
        print(f"  {YELLOW}{s('no_items')}{RESET}"); return

    while True:
        result = select_menu(all_entries)
        if result is None:
            break
        action, entries = result
        os.system("cls")

        if action == "add":
            new_e = add_var(all_entries)
            if new_e is not None:
                # 按作用域+字母序插入
                pos = sum(
                    1 for e in all_entries
                    if (e.scope, e.name.upper()) < (new_e.scope, new_e.name.upper())
                )
                all_entries.insert(pos, new_e)

        elif action == "edit":
            edit_var(entries[0])

        elif action == "delete":
            delete_vars(entries, all_entries)

        os.system("cls")


if __name__ == "__main__":
    main()
