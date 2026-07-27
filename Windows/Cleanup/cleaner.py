#!/usr/bin/env python3
"""
Windows 用户目录垃圾清理工具
清理 C:\\Users\\<USERNAME> 下的缓存、安装包和空文件夹
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from typing import Callable, Generator

# ---------- 终端颜色（Windows VT100） ----------

def _enable_vt():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7
            )
        except Exception:
            pass
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

_enable_vt()


def _exit_and_close() -> None:
    os.system('cls')
    sys.exit(0)


RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
BOLD    = "\033[1m"
RESET   = "\033[0m"

_RAINBOW  = [RED, YELLOW, GREEN, CYAN, MAGENTA, BLUE]
_VERSION  = "1.02"


def _rainbow_words(text: str) -> str:
    words = text.split(" ")
    return " ".join(f"{_RAINBOW[i % len(_RAINBOW)]}{w}{RESET}" for i, w in enumerate(words))


# ---------- 国際化 / i18n ----------

_lang = "en"

_UI: dict[str, dict[str, str]] = {
    "zh": {
        "title":          "Windows 用户目录清理工具",
        "mode_dry":       "预览模式",
        "mode_exec":      "执行模式",
        "target_dir":     "目标目录",
        "scan_phase":     "扫描{name}...",
        "exec_phase":     "删除{name}...",
        "found":          "发现 {size}，{deleted} 项可清理，{skipped} 项无权限",
        "verb_scan":      "已发现",
        "verb_exec":      "已释放",
        "menu_header":    "选择要清理的分类  (数字键切换 / a 全选↔全不选 / 回车删除 / l 语言 / q 退出)",
        "menu_total":     "合计 (已选)",
        "items_del":      "项可删",
        "items_skip":     "项跳过",
        "at_least_one":   "请至少选择一项",
        "press_any_key":  "按任意键返回菜单...",
        "confirm":        "即将执行删除操作，确认继续？[y/N] ",
        "cancelled":      "已取消。",
        "done":           "清理完成！",
        "err_no_dir":     "错误：用户目录不存在: {path}",
        "col_category":   "分类",
        "col_freed":      "释放空间",
        "col_deleted":    "删除数",
        "col_skipped":    "跳过数",
        "col_total":      "合计",
        "cat_cache":      "缓存文件",
        "cat_installers": "安装包文件",
        "cat_empty_dirs": "空文件夹",
        "lang_title":     "选择语言 / Select Language / 言語選択",
        "lang_hint":      "数字键选择 / q 返回菜单",
        "lang_invalid":   "无效选项，请重新输入",
        "cat_gpu_cache":  "GPU着色器缓存",
        "cat_logs":       "日志与崩溃转储",
        "welcome_desc":   "清理 Windows 用户目录下的缓存、日志、GPU 着色器缓存与空文件夹",
        "welcome_lang":   "切换语言",
        "welcome_scan":   "开始扫描",
        "welcome_quit":   "退出",
        "post_success":   "本次共释放 {size}，删除 {deleted} 项",
        "post_nothing":   "未能清理任何文件（可能权限不足）",
        "post_skipped":   "另有 {skipped} 项因权限不足被跳过",
        "post_back":      "返回主菜单",
        "post_exit":      "退出并关闭窗口",
        "post_header":    "清理结束  (1 返回主菜单 / q 退出)",
    },
    "en": {
        "title":          "Windows User Directory Cleaner",
        "mode_dry":       "Preview Mode",
        "mode_exec":      "Execute Mode",
        "target_dir":     "Target directory",
        "scan_phase":     "Scanning {name}...",
        "exec_phase":     "Deleting {name}...",
        "found":          "Found {size},  {deleted} items to clean,  {skipped} skipped",
        "verb_scan":      "Found",
        "verb_exec":      "Freed",
        "menu_header":    "Select categories  (number toggle / a all↔none / Enter delete / l language / q quit)",
        "menu_total":     "Total (selected)",
        "items_del":      "to delete",
        "items_skip":     "skipped",
        "at_least_one":   "Please select at least one category",
        "press_any_key":  "Press any key to return to menu...",
        "confirm":        "About to delete files. Continue? [y/N] ",
        "cancelled":      "Cancelled.",
        "done":           "Cleanup complete!",
        "err_no_dir":     "Error: User directory not found: {path}",
        "col_category":   "Category",
        "col_freed":      "Freed",
        "col_deleted":    "Deleted",
        "col_skipped":    "Skipped",
        "col_total":      "Total",
        "cat_cache":      "Cache Files",
        "cat_installers": "Installers",
        "cat_empty_dirs": "Empty Dirs",
        "lang_title":     "選択言語 / Select Language / 选择语言",
        "lang_hint":      "number to select / q back to menu",
        "lang_invalid":   "Invalid option, please try again",
        "cat_gpu_cache":  "GPU Shader Cache",
        "cat_logs":       "Logs & Crash Dumps",
        "welcome_desc":   "Cleans cache, logs, GPU shader cache & empty folders in AppData",
        "welcome_lang":   "Change Language",
        "welcome_scan":   "Start Scan",
        "welcome_quit":   "Quit",
        "post_success":   "Freed {size}, deleted {deleted} items",
        "post_nothing":   "Nothing could be cleaned (possibly insufficient permissions)",
        "post_skipped":   "{skipped} items skipped due to insufficient permissions",
        "post_back":      "Back to main menu",
        "post_exit":      "Exit and close window",
        "post_header":    "Done  (1 back / q exit)",
    },
    "ja": {
        "title":          "Windowsユーザーディレクトリ クリーナー",
        "mode_dry":       "プレビューモード",
        "mode_exec":      "実行モード",
        "target_dir":     "対象ディレクトリ",
        "scan_phase":     "{name}をスキャン中...",
        "exec_phase":     "{name}を削除中...",
        "found":          "{size} 発見、{deleted} 件削除可能、{skipped} 件スキップ",
        "verb_scan":      "発見",
        "verb_exec":      "解放",
        "menu_header":    "カテゴリ選択  (数字トグル / a 全選択↔全解除 / Enter 削除 / l 言語 / q 終了)",
        "menu_total":     "合計（選択中）",
        "items_del":      "件削除可",
        "items_skip":     "件スキップ",
        "at_least_one":   "少なくとも1つ選択してください",
        "press_any_key":  "何かキーを押してメニューへ戻る...",
        "confirm":        "削除を実行しますか？[y/N] ",
        "cancelled":      "キャンセルしました。",
        "done":           "クリーニング完了！",
        "err_no_dir":     "エラー：ユーザーディレクトリが見つかりません: {path}",
        "col_category":   "カテゴリ",
        "col_freed":      "解放容量",
        "col_deleted":    "削除数",
        "col_skipped":    "スキップ",
        "col_total":      "合計",
        "cat_cache":      "キャッシュ",
        "cat_installers": "インストーラー",
        "cat_empty_dirs": "空フォルダ",
        "lang_title":     "言語選択 / Select Language / 选择语言",
        "lang_hint":      "数字で選択 / q メニューへ戻る",
        "lang_invalid":   "無効な選択です。再入力してください",
        "cat_gpu_cache":  "GPUシェーダーキャッシュ",
        "cat_logs":       "ログ・クラッシュダンプ",
        "welcome_desc":   "AppData 内のキャッシュ・ログ・GPUシェーダー・空フォルダを削除",
        "welcome_lang":   "言語変更",
        "welcome_scan":   "スキャン開始",
        "welcome_quit":   "終了",
        "post_success":   "{size} 解放、{deleted} 件削除しました",
        "post_nothing":   "クリーニングできたファイルはありませんでした（権限不足の可能性）",
        "post_skipped":   "{skipped} 件は権限不足でスキップされました",
        "post_back":      "メインメニューへ戻る",
        "post_exit":      "終了してウィンドウを閉じる",
        "post_header":    "完了  (1 戻る / q 終了)",
    },
}

_LANGUAGES = [("zh", "中文"), ("en", "English"), ("ja", "日本語")]


def s(key: str, **kw) -> str:
    return _UI[_lang][key].format(**kw)


# ---------- 工具函数 ----------

def fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def path_size(p: Path) -> int:
    """递归统计路径大小，出错跳过。"""
    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for child in p.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


# ---------- 清理结果容器 ----------

class Result:
    def __init__(self, name: str, key: str = ""):
        self.name = name
        self.key  = key
        self.freed = 0
        self.deleted = 0
        self.skipped = 0

    def display_name(self) -> str:
        return s(self.key) if self.key else self.name

    def merge(self, freed: int, deleted: int, skipped: int):
        self.freed += freed
        self.deleted += deleted
        self.skipped += skipped


# ---------- 底层删除原语 ----------

def _delete_item(p: Path, dry: bool, verbose: bool) -> tuple[int, int]:
    """删除单个文件或目录，返回 (freed, skipped)。"""
    size = path_size(p)
    if dry:
        if verbose:
            tag = "DIR " if p.is_dir() else "FILE"
            print(f"    {YELLOW}[DRY]{RESET} {tag} {p}  ({fmt_size(size)})")
        return size, 0
    try:
        if p.is_dir():
            shutil.rmtree(str(p))
        else:
            p.unlink(missing_ok=True)
        if verbose:
            tag = "DIR " if p.is_dir() else "FILE"
            print(f"    {RED}[DEL]{RESET} {tag} {p}  ({fmt_size(size)})")
        return size, 0
    except PermissionError:
        if verbose:
            print(f"    {YELLOW}[SKIP]{RESET} {p}  (权限不足)")
        return 0, 1
    except OSError as e:
        if verbose:
            print(f"    {YELLOW}[ERR]{RESET}  {p}  ({e})")
        return 0, 1


def delete_dir_contents(directory: Path, dry: bool, verbose: bool) -> tuple[int, int, int]:
    """清空目录内容（保留目录本身），返回 (freed, deleted, skipped)。"""
    if not directory.exists():
        return 0, 0, 0
    freed = deleted = skipped = 0
    try:
        for child in list(directory.iterdir()):
            f, sk = _delete_item(child, dry, verbose)
            if sk:
                skipped += 1
            else:
                freed += f
                deleted += 1
    except PermissionError:
        pass
    return freed, deleted, skipped


def delete_glob_contents(base: Path, glob_pattern: str, dry: bool, verbose: bool) -> tuple[int, int, int]:
    """删除 base/glob_pattern 匹配到的每个路径的内容。"""
    if not base.exists():
        return 0, 0, 0
    freed = deleted = skipped = 0
    for match in base.glob(glob_pattern):
        if match.is_dir():
            f, d, sk = delete_dir_contents(match, dry, verbose)
            freed += f; deleted += d; skipped += sk
    return freed, deleted, skipped


def delete_glob_files(base: Path, pattern: str, dry: bool, verbose: bool) -> tuple[int, int, int]:
    """删除匹配 glob 的文件。"""
    if not base.exists():
        return 0, 0, 0
    freed = deleted = skipped = 0
    for match in base.glob(pattern):
        if match.is_file():
            f, sk = _delete_item(match, dry, verbose)
            if sk:
                skipped += 1
            else:
                freed += f; deleted += 1
    return freed, deleted, skipped


# ---------- UI 辅助函数 ----------

def _dw(text: str) -> int:
    """Terminal display width: CJK full-width chars count as 2."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def _pad(text: str, width: int) -> str:
    """Right-pad text to display-width using spaces."""
    return text + " " * max(0, width - _dw(text))


def show_progress_bar(sublabel: str, freed: int, step: int, width: int = 79) -> None:
    """Asterisk-style progress bar, updated in-place on the current line."""
    bar_width = 30
    pos = min(step, bar_width)
    bar = "[" + "*" * pos + " " * (bar_width - pos) + "]"
    size_str = fmt_size(freed)
    right = f"  {size_str}"
    available = max(0, width - len(bar) - len(right) - 2)
    if len(sublabel) > available:
        label = sublabel[:max(0, available - 1)] + ("…" if available > 0 else "")
    else:
        label = sublabel
    line = f"{bar}  {label:<{available}}{right}"
    print(f"\r{line[:width]}", end="", flush=True)


def render_menu(results: list[Result], selected: list[bool], status: str = "") -> str:
    header   = s('menu_header')
    name_col = max(14, max((_dw(r.display_name()) for r in results), default=14))
    del_w    = max((len(str(r.deleted))  for r in results), default=1)
    skip_w   = max((len(str(r.skipped)) for r in results), default=1)
    sep_w    = max(_dw(header) + 4, name_col + 36)
    SEP  = "=" * sep_w
    SEP2 = "-" * sep_w
    lines = [
        SEP,
        f"  {header}",
        SEP,
    ]
    for i, (r, sel) in enumerate(zip(results, selected), 1):
        check = "✓" if sel else " "
        lines.append(
            f"  [{i}] {check}  {_pad(r.display_name(), name_col)}  {fmt_size(r.freed):>10}"
            f"   {r.deleted:>{del_w}} {s('items_del')}  {r.skipped:>{skip_w}} {s('items_skip')}"
        )
    lines.append(SEP2)
    total = sum(r.freed for r, sel in zip(results, selected) if sel)
    lines.append(f"  {s('menu_total')}: {fmt_size(total)}")
    if status:
        lines.append(f"  {YELLOW}{status}{RESET}")
    lines.append("> ")
    return "\n".join(lines)


def print_table(results: list[Result], dry: bool) -> None:
    COL_NAMES = [s("col_category"), s("col_freed"), s("col_deleted"), s("col_skipped")]

    data_rows = [
        [r.display_name(), fmt_size(r.freed), str(r.deleted), str(r.skipped)]
        for r in results
    ]
    total_freed   = sum(r.freed   for r in results)
    total_deleted = sum(r.deleted for r in results)
    total_skipped = sum(r.skipped for r in results)
    total_row = [s("col_total"), fmt_size(total_freed), str(total_deleted), str(total_skipped)]

    all_rows = data_rows + [total_row]
    widths = [
        max(_dw(COL_NAMES[i]), max(_dw(row[i]) for row in all_rows))
        for i in range(4)
    ]

    def _cell(text: str, idx: int) -> str:
        return f" {_pad(text, widths[idx])} "

    def _row(cells: list[str]) -> str:
        return "║" + "║".join(_cell(c, i) for i, c in enumerate(cells)) + "║"

    def _div(l: str, m: str, r: str, fill: str = "═") -> str:
        return l + m.join(fill * (w + 2) for w in widths) + r

    print(_div("╔", "╦", "╗"))
    print(_row(COL_NAMES))
    print(_div("╠", "╬", "╣"))
    for row in data_rows:
        print(_row(row))
    print(_div("╠", "╬", "╣"))
    print(_row(total_row))
    print(_div("╚", "╩", "╝"))



def _render_lang_menu(status: str = "") -> str:
    SEP  = "=" * 60
    SEP2 = "-" * 60
    lines = [
        SEP,
        f"  {s('lang_title')}",
        f"  ({s('lang_hint')})",
        SEP,
    ]
    for i, (code, label) in enumerate(_LANGUAGES, 1):
        marker = "●" if code == _lang else " "
        lines.append(f"  [{i}] {marker}  {label}")
    lines.append(SEP2)
    if status:
        lines.append(f"  {YELLOW}{status}{RESET}")
    lines.append("> ")
    return "\n".join(lines)


def select_language() -> None:
    """Interactive language selection menu. q always returns to caller."""
    global _lang
    import msvcrt

    while msvcrt.kbhit():
        msvcrt.getch()

    status = ""
    menu_text = _render_lang_menu(status)
    print(menu_text, end="", flush=True)

    while True:
        key = msvcrt.getch()
        if key in (b"\x00", b"\xe0"):
            msvcrt.getch()
            continue
        try:
            ch = key.decode("utf-8").lower()
        except (UnicodeDecodeError, AttributeError):
            continue

        if ch == "\x03":
            print(); sys.exit(0)
        elif ch == "q":
            print()
            return
        elif ch in "123":
            idx = int(ch) - 1
            if idx < len(_LANGUAGES):
                _lang = _LANGUAGES[idx][0]
                print()
                return
            else:
                status = s("lang_invalid")
        else:
            status = s("lang_invalid")

        n_up = menu_text.count("\n")
        print(f"\033[{n_up}A\r\033[J", end="", flush=True)
        menu_text = _render_lang_menu(status)
        print(menu_text.replace("\n", "\033[K\n") + "\033[K", end="", flush=True)


# ---------- 欢迎界面 ----------

_WELCOME_ART = r"""  ____  _     _____    _    _   _   _   _ ____
 / ___|| |   | ____|  / \  | \ | | | | | |  _ \
| |    | |   |  _|   / _ \ |  \| | | | | | |_) |
| |___ | |___| |___ / ___ \| |\  | | |_| |  __/
 \____||_____|_____/_/   \_\_| \_|  \___/ |_|    """


def _render_welcome() -> str:
    SEP  = "=" * 62
    SEP2 = "-" * 62
    lines = [SEP, ""]
    for i, art_line in enumerate(_WELCOME_ART.split("\n")):
        color = _RAINBOW[i % len(_RAINBOW)]
        lines.append(f"  {color}{art_line}{RESET}")
    lines += [
        "",
        f"  {_rainbow_words(s('welcome_desc'))}",
        f"  {CYAN}v{_VERSION}{RESET}",
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
    """Show welcome screen. Returns when user selects Start Scan. Exits on quit."""
    import msvcrt

    while True:
        os.system('cls')
        print(_render_welcome(), end="", flush=True)

        while msvcrt.kbhit():
            msvcrt.getch()

        while True:
            key = msvcrt.getch()
            if key in (b"\x00", b"\xe0"):
                msvcrt.getch()
                continue
            try:
                ch = key.decode("utf-8").lower()
            except (UnicodeDecodeError, AttributeError):
                continue

            if ch == "\x03":
                print()
                sys.exit(0)
            elif ch == "1":
                print()
                os.system('cls')
                select_language()
                break  # re-render welcome with (possibly new) language
            elif ch == "2":
                print()
                return
            elif ch == "q":
                print()
                _exit_and_close()


def select_menu(results: list[Result],
                initial: list[bool] | None = None) -> list[bool]:
    """Interactive category menu. Returns selected list ready for execution."""
    import msvcrt

    while msvcrt.kbhit():
        msvcrt.getch()

    selected = list(initial) if initial is not None else [r.freed > 0 or r.deleted > 0 for r in results]
    status = ""
    menu_text = render_menu(results, selected, status)
    print(menu_text, end="", flush=True)

    while True:
        try:
            key = msvcrt.getch()
        except KeyboardInterrupt:
            print()
            sys.exit(0)

        if key in (b"\x00", b"\xe0"):
            msvcrt.getch()
            continue

        try:
            ch = key.decode("utf-8").lower()
        except (UnicodeDecodeError, AttributeError):
            continue

        redraw = False

        if ch == "\x03":
            print()
            sys.exit(0)
        elif ch in "123456789":
            idx = int(ch) - 1
            if idx < len(results):
                selected[idx] = not selected[idx]
                status = ""
                redraw = True
        elif ch == "a":
            if all(selected):
                selected = [False] * len(results)
            else:
                selected = [True] * len(results)
            status = ""
            redraw = True
        elif ch in ("\r", "\n"):
            if not any(selected):
                status = s("at_least_one")
                redraw = True
            else:
                print()
                return selected
        elif ch == "l":
            os.system('cls')
            select_language()
            os.system('cls')
            status = ""
            menu_text = render_menu(results, selected, status)
            print(menu_text, end="", flush=True)
        elif ch == "q":
            print()
            _exit_and_close()

        if redraw:
            n_up = menu_text.count("\n")
            print(f"\033[{n_up}A\r\033[J", end="", flush=True)
            menu_text = render_menu(results, selected, status)
            print(menu_text.replace("\n", "\033[K\n") + "\033[K", end="", flush=True)


# ---------- 三大清理模块 ----------

def clean_cache(user: Path, dry: bool, verbose: bool,
                progress_cb: Callable[[str, int], None] | None = None) -> Result:
    r = Result("缓存文件", key="cat_cache")
    loc = user / "AppData" / "Local"
    roam = user / "AppData" / "Roaming"

    tasks = [
        ("Windows Temp",            delete_dir_contents,  loc / "Temp"),
        ("INetCache",               delete_dir_contents,  loc / "Microsoft/Windows/INetCache"),
        ("WebCache",                delete_dir_contents,  loc / "Microsoft/Windows/WebCache"),
        ("最近使用的文件快捷方式",    delete_glob_files,    roam / "Microsoft/Windows/Recent", "*.lnk"),
        ("缩略图缓存",               delete_glob_files,    loc / "Microsoft/Windows/Explorer", "thumbcache_*.db"),
        ("Chrome Cache",            delete_glob_contents, loc / "Google/Chrome/User Data", "*/Cache"),
        ("Chrome Code Cache",       delete_glob_contents, loc / "Google/Chrome/User Data", "*/Code Cache"),
        ("Edge Cache",              delete_glob_contents, loc / "Microsoft/Edge/User Data", "*/Cache"),
        ("Edge Code Cache",         delete_glob_contents, loc / "Microsoft/Edge/User Data", "*/Code Cache"),
        ("Firefox Cache",           delete_glob_contents, loc / "Mozilla/Firefox/Profiles", "*/cache2"),
        ("Teams Cache",             delete_dir_contents,  roam / "Microsoft/Teams/Cache"),
        ("Teams blob_storage",      delete_dir_contents,  roam / "Microsoft/Teams/blob_storage"),
        ("Teams GPUCache",          delete_dir_contents,  roam / "Microsoft/Teams/GPUCache"),
        ("Discord Cache",           delete_dir_contents,  roam / "discord/Cache"),
        ("Discord Code Cache",      delete_dir_contents,  roam / "discord/Code Cache"),
        ("Spotify Cache",           delete_dir_contents,  loc / "Spotify/Storage"),
        ("pip Cache",               delete_dir_contents,  loc / "pip/cache"),
        ("npm Cache",               delete_dir_contents,  loc / "npm-cache"),
        ("Yarn Cache",              delete_dir_contents,  loc / "Yarn/Cache"),
        ("VS Code CachedData",      delete_dir_contents,  roam / "Code/CachedData"),
        ("Cursor CachedData",       delete_dir_contents,  roam / "Cursor/CachedData"),
        # ── 游戏平台 ──────────────────────────────────────────────
        ("Steam htmlcache",         delete_dir_contents,  loc / "Steam/htmlcache"),
        ("Battle.net htmlcache",    delete_glob_contents, loc / "Battle.net", "*/Cache"),
        ("EA Desktop Cache",        delete_glob_contents, loc / "EADesktop", "*/webcache"),
        # ── 国产/其他应用 ───────────────────────────────────────
        ("Quark Cache",             delete_glob_contents, loc / "Quark/User Data", "*/Cache"),
        ("Quark Code Cache",        delete_glob_contents, loc / "Quark/User Data", "*/Code Cache"),
        ("Zoom WebCache",           delete_dir_contents,  roam / "Zoom/data/WebviewCacheX64"),
        # ── Windows 错误报告 ──────────────────────────────────────
        ("WER ReportArchive",       delete_dir_contents,  loc / "Microsoft/Windows/WER/ReportArchive"),
        ("WER ReportQueue",         delete_dir_contents,  loc / "Microsoft/Windows/WER/ReportQueue"),
    ]

    for label, fn, *args in tasks:
        if not verbose and progress_cb:
            progress_cb(label, r.freed)
        if verbose:
            print(f"  {CYAN}→ {label}{RESET}")
        f, d, sk = fn(*args, dry, verbose)
        r.merge(f, d, sk)

    return r


def clean_installers(user: Path, dry: bool, verbose: bool,
                     progress_cb: Callable[[str, int], None] | None = None) -> Result:
    r = Result("安装包文件", key="cat_installers")
    loc = user / "AppData" / "Local"

    temp = loc / "Temp"
    installer_exts = ["*.exe", "*.msi", "*.msp", "*.cab", "*.pkg", "*.msix"]

    if not verbose and progress_cb:
        progress_cb("Temp 目录安装包", r.freed)
    if verbose:
        print(f"  {CYAN}→ Temp 目录安装包{RESET}")
    for pat in installer_exts:
        f, d, sk = delete_glob_files(temp, pat, dry, verbose)
        r.merge(f, d, sk)

    if not verbose and progress_cb:
        progress_cb("WinGet 临时下载", r.freed)
    if verbose:
        print(f"  {CYAN}→ WinGet 临时下载{RESET}")
    for winget_tmp in [temp / "WinGet", loc / "Temp" / "winget"]:
        f, d, sk = delete_dir_contents(winget_tmp, dry, verbose)
        r.merge(f, d, sk)

    if not verbose and progress_cb:
        progress_cb("Teams 旧版本文件", r.freed)
    if verbose:
        print(f"  {CYAN}→ Teams 旧版本文件{RESET}")
    for old in (loc / "Microsoft" / "Teams").glob("previous") if (loc / "Microsoft" / "Teams").exists() else []:
        freed_v, sk = _delete_item(old, dry, verbose)
        r.merge(freed_v, 0 if sk else 1, sk)

    if not verbose and progress_cb:
        progress_cb("UWP TempState", r.freed)
    if verbose:
        print(f"  {CYAN}→ UWP TempState{RESET}")
    f, d, sk = delete_glob_contents(loc / "Packages", "*/TempState", dry, verbose)
    r.merge(f, d, sk)

    squirrel_roots = [
        loc / "Discord",
        loc / "slack",
        loc / "GitHubDesktop",
    ]
    for root in squirrel_roots:
        if root.exists():
            if not verbose and progress_cb:
                progress_cb(f"Squirrel 旧包: {root.name}", r.freed)
            if verbose:
                print(f"  {CYAN}→ Squirrel 旧包: {root.name}{RESET}")
            for nupkg in root.rglob("*.nupkg"):
                if nupkg.parent.name in ("packages", "nupkg"):
                    freed_v, sk = _delete_item(nupkg, dry, verbose)
                    r.merge(freed_v, 0 if sk else 1, sk)

    return r


def clean_gpu_cache(user: Path, dry: bool, verbose: bool,
                    progress_cb: Callable[[str, int], None] | None = None) -> Result:
    """清理 GPU 着色器编译缓存（NVIDIA DXCache / GLCache / D3DSCache）。
    这些缓存可达数 GB，删除后显卡驱动会在运行游戏时自动重建，安全可反复清理。"""
    r = Result("GPU着色器缓存", key="cat_gpu_cache")
    loc = user / "AppData" / "Local"

    tasks = [
        ("NVIDIA DXCache",          delete_dir_contents, loc / "NVIDIA/DXCache"),
        ("NVIDIA GLCache",          delete_dir_contents, loc / "NVIDIA/GLCache"),
        ("D3DSCache",               delete_dir_contents, loc / "D3DSCache"),
        ("NVIDIA App Cache",        delete_glob_contents, loc / "NVIDIA Corporation/NVIDIA App", "*/cache"),
        ("NVIDIA Overlay Cache",    delete_glob_contents, loc / "NVIDIA Corporation/NVIDIA Overlay", "*/cache"),
    ]

    for label, fn, *args in tasks:
        if not verbose and progress_cb:
            progress_cb(label, r.freed)
        if verbose:
            print(f"  {CYAN}→ {label}{RESET}")
        f, d, sk = fn(*args, dry, verbose)
        r.merge(f, d, sk)

    return r


def clean_logs(user: Path, dry: bool, verbose: bool,
               progress_cb: Callable[[str, int], None] | None = None) -> Result:
    """清理日志文件与崩溃转储（.log / .dmp / WER 报告）。"""
    r = Result("日志与崩溃转储", key="cat_logs")
    loc  = user / "AppData" / "Local"
    roam = user / "AppData" / "Roaming"

    # ── 崩溃转储 ─────────────────────────────────────────────────
    dump_dirs = [
        loc / "CrashDumps",
        loc / "Microsoft/Windows/WER/Temp",
        loc / "Temp",
        loc / "Activision",                              # CoD crash_reports
        loc / "Google/Chrome/User Data/Crashpad/reports",
        loc / "Microsoft/Edge/User Data/Crashpad/reports",
    ]
    dump_patterns = ["*.dmp", "*.mdmp", "*.hdmp", "*.rpt"]

    for d in dump_dirs:
        label = f"崩溃转储 {d.name}"
        if not verbose and progress_cb:
            progress_cb(label, r.freed)
        if verbose:
            print(f"  {CYAN}→ {label}{RESET}")
        for pat in dump_patterns:
            # Activision 的 crash_reports 在子目录中
            glob_fn = d.rglob if d.name == "Activision" else d.glob
            if d.exists():
                freed = deleted = skipped = 0
                for match in glob_fn(pat) if d.name == "Activision" else [*d.glob(pat)]:
                    if match.is_file():
                        fv, sk = _delete_item(match, dry, verbose)
                        if sk:
                            skipped += 1
                        else:
                            freed += fv
                            deleted += 1
                r.merge(freed, deleted, skipped)

    # ── 应用日志文件 ──────────────────────────────────────────────
    log_tasks: list[tuple[str, Path, str]] = [
        # ── Windows / 系统组件 ────────────────────────────────────
        ("Temp *.log",              loc / "Temp",                                                                          "*.log"),
        ("PowerToys 日志",          loc / "Microsoft/PowerToys",                                                           "**/*.log"),
        ("OneDrive 日志",           loc / "Microsoft/OneDrive/logs",                                                       "**/*.log"),
        ("OneDrive 安装日志",       loc / "Microsoft/OneDrive/setup/logs",                                                 "**/*.log"),
        ("MSIPC 日志",              loc / "Microsoft/MSIPC/Logs",                                                          "*.log"),
        ("新版 Outlook 日志",       loc / "Microsoft/Olk/logs",                                                            "*.log"),
        ("Xbox Gaming 日志",        loc / "Packages/Microsoft.GamingApp_8wekyb3d8bbwe/LocalState/Logs",                   "*.log"),
        ("Xbox Services 日志",      loc / "Packages/Microsoft.GamingServices_8wekyb3d8bbwe/LocalState/Logs",              "*.log"),
        # ── 游戏平台 ─────────────────────────────────────────────
        ("Steam 日志",              loc / "Steam",                                                                         "*.log"),
        ("Battle.net 日志",         loc / "Battle.net",                                                                    "*.log"),
        ("EA Desktop 日志",         loc / "Electronic Arts",                                                               "**/*.log"),
        ("鸣潮 日志",               loc / "PioneerGame/Saved/Logs",                                                        "*.log"),
        # ── 通讯 / 社交 ──────────────────────────────────────────
        ("Discord 日志",            roam / "discord/logs",                                                                 "*.log"),
        ("QQ 日志",                 roam / "QQ/log",                                                                       "**/*.log"),
        ("QQ Crashpad 日志",        roam / "QQ/Crashpad",                                                                  "**/*.log"),
        ("QQEX 日志",               roam / "QQEX",                                                                         "**/*.log"),
        ("Tencent 日志",            roam / "Tencent",                                                                      "**/*.log"),
        ("Teams 日志",              loc / "Packages/MSTeams_8wekyb3d8bbwe/LocalCache/Microsoft/MSTeams/Logs",             "**/*.log"),
        ("Zoom 日志",               roam / "Zoom/logs",                                                                    "*.log"),
        # ── 浏览器 ───────────────────────────────────────────────
        ("Quark ulog",              loc / "Quark/User Data/ulog",                                                          "**/*.log"),
        # ── 开发工具 ─────────────────────────────────────────────
        ("VS Code 日志",            roam / "Code/logs",                                                                    "**/*.log"),
        ("Cursor 日志",             roam / "Cursor/logs",                                                                  "**/*.log"),
        # ── 其他应用 ─────────────────────────────────────────────
        ("NVIDIA 日志",             loc / "NVIDIA Corporation",                                                            "**/*.log"),
        ("qBittorrent 日志",        loc / "qBittorrent",                                                                   "*.log"),
        ("Spotify Launcher 日志",   loc / "Packages/SpotifyAB.SpotifyMusic_zpdnekdrzrea0/LocalCache/Spotify/Launcher/Logs", "*.log"),
        ("leigod 日志",             roam / "leigod",                                                                       "*.log"),
        ("百度网盘 日志",           roam / "baidu",                                                                        "**/*.log"),
        ("百度云管家 日志",         roam / "BaiduYunGuanjia/logs",                                                         "*.log"),
        ("clash_win 日志",          roam / "clash_win/logs",                                                               "*.log"),
        ("HMCL 日志",               roam / ".hmcl/logs",                                                                   "*.log"),
        ("Minecraft Bedrock 日志",  roam / "Minecraft Bedrock/logs",                                                       "*.log"),
    ]

    for label, base, pattern in log_tasks:
        if not verbose and progress_cb:
            progress_cb(label, r.freed)
        if verbose:
            print(f"  {CYAN}→ {label}{RESET}")
        # rglob 版本支持 ** 通配
        if "**" in pattern:
            if base.exists():
                freed = deleted = skipped = 0
                for match in base.rglob(pattern.replace("**/", "")):
                    if match.is_file():
                        f, sk = _delete_item(match, dry, verbose)
                        if sk:
                            skipped += 1
                        else:
                            freed += f
                            deleted += 1
                r.merge(freed, deleted, skipped)
        else:
            f, d2, sk = delete_glob_files(base, pattern, dry, verbose)
            r.merge(f, d2, sk)

    # ── Squirrel 安装日志 ─────────────────────────────────────────
    squirrel_roots = [loc / "Discord", loc / "slack", loc / "GitHubDesktop"]
    for root in squirrel_roots:
        if root.exists():
            label = f"Squirrel 安装日志: {root.name}"
            if not verbose and progress_cb:
                progress_cb(label, r.freed)
            if verbose:
                print(f"  {CYAN}→ {label}{RESET}")
            f, d2, sk = delete_glob_files(root, "*.log", dry, verbose)
            r.merge(f, d2, sk)

    return r


def clean_empty_dirs(user: Path, dry: bool, verbose: bool,
                     progress_cb: Callable[[str, int], None] | None = None) -> Result:
    """删除 AppData 三个子目录的直接空子目录（非递归，不深入扫描）。"""
    r = Result("空文件夹", key="cat_empty_dirs")

    scan_roots = [
        user / "AppData" / "Local",
        user / "AppData" / "Roaming",
        user / "AppData" / "LocalLow",
    ]

    for root in scan_roots:
        if not root.exists():
            continue
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for d in children:
            if not d.is_dir():
                continue
            if not verbose and progress_cb:
                progress_cb(str(d), r.freed)
            try:
                if not any(d.iterdir()):
                    if verbose:
                        print(f"  {CYAN}→ 空目录: {d}{RESET}")
                    freed_v, sk = _delete_item(d, dry, verbose)
                    if sk:
                        r.skipped += 1
                    else:
                        r.freed += freed_v
                        r.deleted += 1
            except OSError:
                pass

    return r


# ---------- 清理结果菜单 ----------

def show_post_menu(total_freed: int, total_deleted: int, total_skipped: int) -> str:
    """Show post-cleanup result and options. Returns 'back' or 'exit'."""
    import msvcrt

    SEP  = "=" * 62
    SEP2 = "-" * 62

    if total_deleted > 0:
        result_color = GREEN
        result_msg = s("post_success", size=fmt_size(total_freed), deleted=total_deleted)
    else:
        result_color = YELLOW
        result_msg = s("post_nothing")

    lines = ["", SEP, f"  {result_color}{BOLD}{result_msg}{RESET}"]
    if total_skipped > 0:
        lines.append(f"  {YELLOW}{s('post_skipped', skipped=total_skipped)}{RESET}")
    lines += [
        SEP2,
        f"  [1]  {s('post_back')}",
        f"  [q]  {s('post_exit')}",
        SEP,
        "> ",
    ]
    menu_text = "\n".join(lines)
    print(menu_text, end="", flush=True)

    while msvcrt.kbhit():
        msvcrt.getch()

    while True:
        key = msvcrt.getch()
        if key in (b"\x00", b"\xe0"):
            msvcrt.getch()
            continue
        try:
            ch = key.decode("utf-8").lower()
        except (UnicodeDecodeError, AttributeError):
            continue
        if ch == "\x03":
            print()
            sys.exit(0)
        elif ch == "1":
            print()
            return "back"
        elif ch == "q":
            print()
            return "exit"


# ---------- 主流程 ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="cleaner",
        description="Windows 用户目录垃圾清理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cleaner.py                  # 预览模式，显示将清理的内容
  python cleaner.py -x               # 执行清理（所有分类）
  python cleaner.py --cache -x       # 只清理缓存并执行
  python cleaner.py --gpu-cache -x   # 只清理 GPU 着色器缓存并执行
  python cleaner.py --logs -x        # 只清理日志与崩溃转储并执行
  python cleaner.py --empty-dirs -x  # 只删除空文件夹并执行
  python cleaner.py -x -v            # 执行并显示每个被删文件
        """,
    )
    p.add_argument("--cache",        action="store_true", help="清理缓存目录")
    p.add_argument("--installers",   action="store_true", help="清理安装包文件")
    p.add_argument("--gpu-cache",    action="store_true", help="清理 GPU 着色器缓存（NVIDIA DXCache / D3DSCache）")
    p.add_argument("--logs",         action="store_true", help="清理日志文件与崩溃转储（*.log / *.dmp）")
    p.add_argument("--empty-dirs",   action="store_true", help="删除空文件夹")
    p.add_argument("--user",         metavar="PATH",      help="指定用户目录（默认当前用户）")
    p.add_argument("-x", "--execute",action="store_true", help="实际执行删除（默认为预览模式）")
    p.add_argument("-v", "--verbose", action="store_true", help="显示每个被处理的文件/目录")
    p.add_argument("-y", "--yes",     action="store_true", help="跳过执行前的确认提示")
    return p.parse_args()


def main():
    args = parse_args()
    explicit = args.cache or args.installers or args.gpu_cache or args.logs or args.empty_dirs

    while True:
        if not explicit:
            show_welcome()
            os.system('cls')

        dry = not args.execute

        if args.user:
            user_dir = Path(args.user)
        else:
            user_dir = Path(os.environ.get("USERPROFILE", Path.home()))

        if not user_dir.exists():
            print(f"{RED}{s('err_no_dir', path=user_dir)}{RESET}")
            sys.exit(1)

        categories: list[tuple[str, Callable]] = []
        if args.cache or not explicit:
            categories.append(("cat_cache", clean_cache))
        if args.installers or not explicit:
            categories.append(("cat_installers", clean_installers))
        if args.gpu_cache or not explicit:
            categories.append(("cat_gpu_cache", clean_gpu_cache))
        if args.logs or not explicit:
            categories.append(("cat_logs", clean_logs))
        if args.empty_dirs or not explicit:
            categories.append(("cat_empty_dirs", clean_empty_dirs))

        mode_label = f"{YELLOW}{s('mode_dry')}{RESET}" if dry else f"{RED}{s('mode_exec')}{RESET}"
        print(f"\n{BOLD}{s('title')}{RESET}  [{mode_label}]")
        print(f"{s('target_dir')}: {CYAN}{user_dir}{RESET}\n")

        # ── Phase 1: dry scan ──────────────────────────────────────
        total_cats = len(categories)
        scan_results: list[Result] = []

        for i, (cat_key, fn) in enumerate(categories, 1):
            name = s(cat_key)
            prefix = f"[{i}/{total_cats}] {s('scan_phase', name=name)}"
            print(f"{BOLD}{prefix}{RESET}")

            def make_scan_cb(pfx: str) -> Callable[[str, int], None]:
                step = [0]
                def cb(label: str, freed: int) -> None:
                    if not args.verbose:
                        step[0] += 1
                        show_progress_bar(label, freed, step[0])
                return cb

            r = fn(user_dir, dry=True, verbose=args.verbose,
                   progress_cb=make_scan_cb(prefix))
            if not args.verbose:
                print()
            print(f"  {s('found', size=fmt_size(r.freed), deleted=r.deleted, skipped=r.skipped)}\n")
            scan_results.append(r)

        # ── Phase 2: category selection ────────────────────────────
        if explicit:
            selected = [True] * len(categories)
            active = [
                (cat_key, fn, r)
                for (cat_key, fn), sel, r in zip(categories, selected, scan_results)
                if sel
            ]
            if dry:
                print_table([r for _, _, r in active], dry=True)
                sys.exit(0)
        else:
            last_selected: list[bool] | None = None
            os.system('cls')
            while True:
                selected = select_menu(scan_results, initial=last_selected)
                dry = False
                active = [
                    (cat_key, fn, r)
                    for (cat_key, fn), sel, r in zip(categories, selected, scan_results)
                    if sel
                ]
                if args.yes:
                    break
                print()
                answer = input(f"{YELLOW}{s('confirm')}{RESET}").strip().lower()
                if answer == "y":
                    break
                last_selected = selected
                os.system('cls')

        # ── Phase 3: execute ───────────────────────────────────────
        print()
        exec_total = len(active)
        exec_results: list[Result] = []

        for i, (cat_key, fn, _) in enumerate(active, 1):
            name = s(cat_key)
            prefix = f"[{i}/{exec_total}] {s('exec_phase', name=name)}"
            print(f"{BOLD}{prefix}{RESET}")

            def make_exec_cb(pfx: str) -> Callable[[str, int], None]:
                step = [0]
                def cb(label: str, freed: int) -> None:
                    if not args.verbose:
                        step[0] += 1
                        show_progress_bar(label, freed, step[0])
                return cb

            r = fn(user_dir, dry=False, verbose=args.verbose,
                   progress_cb=make_exec_cb(prefix))
            if not args.verbose:
                print()
            exec_results.append(r)

        os.system('cls')
        print_table(exec_results, dry=False)

        if explicit:
            sys.exit(0)

        total_freed   = sum(r.freed   for r in exec_results)
        total_deleted = sum(r.deleted for r in exec_results)
        total_skipped = sum(r.skipped for r in exec_results)

        action = show_post_menu(total_freed, total_deleted, total_skipped)
        if action == "exit":
            _exit_and_close()
        os.system('cls')


if __name__ == "__main__":
    main()
