"""Textual TUI 前端，复用 cleaner.py 的清理逻辑。

字体依赖终端本身（默认 Windows Terminal 字体即可，emoji 用普通 Unicode，
不依赖 Nerd Font 图标集）。
"""
from __future__ import annotations

import os
from pathlib import Path

from rich.table import Table
from rich.text import Text

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Checkbox, Footer, ProgressBar, RichLog, Static, Tab, Tabs

import cleaner as clr

CATEGORIES: list[tuple[str, clr.Callable]] = [
    ("cat_cache", clr.clean_cache),
    ("cat_installers", clr.clean_installers),
    ("cat_gpu_cache", clr.clean_gpu_cache),
    ("cat_logs", clr.clean_logs),
    ("cat_empty_dirs", clr.clean_empty_dirs),
    ("cat_system", clr.clean_system),
]

# Nord 官方 accent 色系，浅色底下把偏白的 primary/warning 换成对比度更够的
# nord10/nord12，其余沿用 nord 原色，保持深浅两套主题视觉同源。
NORD_CREAM = Theme(
    name="nord-cream",
    primary="#5E81AC",
    secondary="#81A1C1",
    warning="#D08770",
    error="#BF616A",
    success="#4C7A63",
    accent="#B48EAD",
    foreground="#2E3440",
    background="#FBF1D3",
    surface="#F5E9C6",
    panel="#EEDFAF",
    dark=False,
)

RAINBOW_HEX = ["#BF616A", "#D08770", "#A3BE8C", "#88C0D0", "#5E81AC", "#B48EAD"]

_TUI_STR = {
    "zh": {"execute": "执行删除", "lang": "切换语言 (中/EN/日)", "select_one": "请至少勾选一个分类"},
    "en": {"execute": "Execute", "lang": "Language (中/EN/日)", "select_one": "Select at least one category"},
    "ja": {"execute": "削除実行", "lang": "言語 (中/EN/日)", "select_one": "少なくとも1つ選択してください"},
}


def t(key: str) -> str:
    return _TUI_STR[clr._lang][key]


class ConfirmScreen(ModalScreen[bool]):
    # 半透明背景在 on_mount 里用代码设置（CSS 里写会被 App 级的
    # `Screen { background: ... }` 通配规则盖掉，见 on_mount 注释）
    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    ConfirmScreen > Vertical {
        width: 60;
        height: auto;
        border: solid $primary;
        background: $panel;
        padding: 1 2;
    }
    ConfirmScreen #buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    ConfirmScreen Button {
        width: 8;
        height: 3;
        margin: 0 1;
    }
    """
    BINDINGS = [
        ("y", "confirm_yes", "Yes"),
        ("n,escape", "confirm_no", "No"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def on_mount(self) -> None:
        # App 级 CSS 里的 `Screen { background: $background; }` 通配规则会
        # 匹配到所有 Screen 子类（含本类），跟层叠顺序打架把这里 CSS 里写的
        # 半透明背景盖掉；直接用代码设置样式不受层叠顺序影响，稳妥
        self.styles.background = "black 60%"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._message)
            with Horizontal(id="buttons"):
                yield Button("Y", id="yes", variant="error")
                yield Button("N", id="no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_confirm_yes(self) -> None:
        self.dismiss(True)

    def action_confirm_no(self) -> None:
        self.dismiss(False)


class CleanerApp(App):
    TITLE = "Cleaner"
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: $background;
        padding: 1;
    }
    /* 细滚动条：轨道贴近背景、滑块常态也接近透明，只在悬停/拖动时才明显 */
    VerticalScroll, RichLog {
        scrollbar-size-vertical: 1;
        scrollbar-background: $background;
        scrollbar-color: $primary 20%;
        scrollbar-color-hover: $primary 60%;
        scrollbar-color-active: $primary;
    }
    #root {
        layout: horizontal;
        height: 1fr;
    }
    #dock {
        width: 3fr;
        border: solid $primary;
        margin: 0 1 0 0;
        padding: 1;
    }
    #right {
        width: 7fr;
        layout: vertical;
        height: 1fr;
    }
    #col1 {
        height: 2fr;
        border: solid $primary;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    #col1-content {
        width: 100%;
    }
    #col2 {
        height: 8fr;
        border: solid $primary;
        padding: 1;
        layout: vertical;
    }
    Tabs {
        height: 3;
        width: 100%;
        margin-bottom: 0;
    }
    Tabs > Tab {
        border: solid $primary;
        padding: 0 2;
        width: 1fr;
        content-align: center middle;
    }
    Tabs > Tab.-active {
        background: $primary;
        color: $background;
        text-style: bold;
    }
    Underline {
        display: none;
    }
    /* dock 内所有选项框（复选框/按钮）统一实线边框、无填充、等宽对齐；
       margin-bottom: 0 让相邻方框的边框直接贴在一起，间距更紧凑 */
    #dock Checkbox {
        border: solid $primary;
        background: transparent;
        width: 100%;
        height: auto;
        min-height: 3;
        padding: 0 1;
        margin-bottom: 0;
        content-align: left middle;
    }
    Button {
        background: transparent;
        border: solid $primary;
        color: $primary;
        content-align: center middle;
        text-style: none;
    }
    /* width:100% 只用于 dock 里纵向堆叠的按钮；不能写成全局规则，
       否则确认弹窗里横排的 Y/N 按钮也会被撑成100%宽度，互相挤没 */
    #dock Button {
        width: 100%;
        height: 3;
        margin-bottom: 0;
    }
    Button:hover {
        background: $panel 50%;
    }
    Button:disabled {
        border: solid $panel;
        color: $panel;
        background: transparent;
    }
    Button.-warning {
        border: solid $warning;
        color: $warning;
    }
    Button.-error {
        border: solid $error;
        color: $error;
    }
    #progress {
        height: 1;
        margin-bottom: 1;
    }
    #progress.hidden {
        display: none;
    }
    #log {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("pagedown", "dock_scroll_down", "Dock ▼"),
        ("pageup", "dock_scroll_up", "Dock ▲"),
    ]

    def __init__(self, user_dir: Path | None = None) -> None:
        super().__init__()
        self.user_dir = user_dir or Path(os.environ.get("USERPROFILE", str(Path.home())))
        self._busy = False
        self._has_scanned = False

    def on_mount(self) -> None:
        self.register_theme(NORD_CREAM)
        self.theme = "nord-cream"
        self._refresh_col1()
        self._show_intro()
        self.query_one("#btn-exec", Button).disabled = True

    def compose(self) -> ComposeResult:
        with Horizontal(id="root"):
            with VerticalScroll(id="dock"):
                yield Tabs(
                    Tab("☀ Light", id="theme-light"),
                    Tab("🌙 Dark", id="theme-dark"),
                )
                for key, _ in CATEGORIES:
                    yield Checkbox(clr.s(key), value=True, id=f"chk-{key}")
                yield Button(clr.s("welcome_scan"), id="btn-scan", variant="primary")
                yield Button(t("execute"), id="btn-exec", variant="warning")
                yield Button(t("lang"), id="btn-lang")
                yield Button(clr.s("welcome_quit"), id="btn-quit", variant="error")
            with Vertical(id="right"):
                with VerticalScroll(id="col1"):
                    yield Static(id="col1-content")
                with Vertical(id="col2"):
                    yield ProgressBar(id="progress", classes="hidden", show_eta=False)
                    yield RichLog(id="log", wrap=True, highlight=False, markup=False)
        yield Footer()

    # ---------- 主题切换 ----------

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if event.tab is None:
            return
        if event.tab.id == "theme-dark":
            self.theme = "nord"
        else:
            self.theme = "nord-cream"

    # ---------- 语言切换 ----------

    def action_quit(self) -> None:
        self.exit()

    def action_dock_scroll_down(self) -> None:
        self.query_one("#dock", VerticalScroll).scroll_down(animate=False)

    def action_dock_scroll_up(self) -> None:
        self.query_one("#dock", VerticalScroll).scroll_up(animate=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-quit":
            self.exit()
        elif bid == "btn-lang":
            self._cycle_language()
        elif bid == "btn-scan":
            self._start_run(execute=False)
        elif bid == "btn-exec":
            self._confirm_execute()

    def _cycle_language(self) -> None:
        codes = [code for code, _ in clr._LANGUAGES]
        idx = (codes.index(clr._lang) + 1) % len(codes)
        clr._lang = codes[idx]
        for key, _ in CATEGORIES:
            self.query_one(f"#chk-{key}", Checkbox).label = clr.s(key)
        self.query_one("#btn-scan", Button).label = clr.s("welcome_scan")
        self.query_one("#btn-exec", Button).label = t("execute")
        self.query_one("#btn-lang", Button).label = t("lang")
        self.query_one("#btn-quit", Button).label = clr.s("welcome_quit")
        self._refresh_col1()
        if not self._has_scanned:
            self._show_intro()

    # ---------- 柱1：彩虹标题 ----------

    def _refresh_col1(self) -> None:
        # 终端字符格是固定大小，没有真正的"字号"——加粗 + 字间距拉开是终端里
        # 让标题显得比正文明显更大的惯用手法，同时保持单行不会撑爆柱1的高度
        title = Text()
        words = clr.s("title").split(" ")
        for i, word in enumerate(words):
            spaced = " ".join(word)
            title.append(spaced, style=f"bold {RAINBOW_HEX[i % len(RAINBOW_HEX)]}")
            if i < len(words) - 1:
                title.append("   ")
        content = Text()
        content.append_text(title)
        content.append("\n")
        content.append(clr.s("welcome_desc"), style="italic")
        content.append("\n")
        content.append(f"v{clr._VERSION}  ·  K4GAM1/Toolbox", style="dim")
        self.query_one("#col1-content", Static).update(content)

    # ---------- 柱2：扫描前的简介 ----------

    def _show_intro(self) -> None:
        log = self.query_one("#log", RichLog)
        log.clear()
        log.write(clr.s("welcome_desc"))
        log.write("")
        for key, _ in CATEGORIES:
            log.write(f"  • {clr.s(key)}")
        log.write("")
        log.write(f"v{clr._VERSION}  ·  K4GAM1/Toolbox")

    # ---------- 柱2：扫描 / 执行 ----------

    def _selected_categories(self) -> list[tuple[str, clr.Callable]]:
        selected = []
        for key, fn in CATEGORIES:
            if self.query_one(f"#chk-{key}", Checkbox).value:
                selected.append((key, fn))
        return selected

    def _confirm_execute(self) -> None:
        if self._busy:
            return
        selected = self._selected_categories()
        if not selected:
            self.query_one("#log", RichLog).write(t("select_one"))
            return

        def handle(confirmed: bool | None) -> None:
            if confirmed:
                self._start_run(execute=True)

        self.push_screen(ConfirmScreen(clr.s("confirm")), handle)

    def _start_run(self, execute: bool) -> None:
        if self._busy:
            return
        selected = self._selected_categories()
        log = self.query_one("#log", RichLog)
        if not selected:
            log.write(t("select_one"))
            return
        log.clear()
        self._busy = True
        self.query_one("#btn-scan", Button).disabled = True
        self.query_one("#btn-exec", Button).disabled = True
        progress = self.query_one("#progress", ProgressBar)
        progress.remove_class("hidden")
        progress.update(total=None)
        self._run_categories(selected, execute)

    @work(thread=True, exclusive=True)
    def _run_categories(self, selected: list[tuple[str, clr.Callable]], execute: bool) -> None:
        log = self.query_one("#log", RichLog)
        results: list[clr.Result] = []
        total = len(selected)
        for i, (key, fn) in enumerate(selected, 1):
            name = clr.s(key)
            phase = clr.s("exec_phase", name=name) if execute else clr.s("scan_phase", name=name)
            self.call_from_thread(log.write, f"[{i}/{total}] {phase}")

            def cb(label: str, freed: int) -> None:
                self.call_from_thread(log.write, f"    → {label}  {clr.fmt_size(freed)}")

            r = fn(self.user_dir, dry=not execute, verbose=False, progress_cb=cb)
            results.append(r)
            self.call_from_thread(
                log.write,
                "  " + clr.s("found", size=clr.fmt_size(r.freed), deleted=r.deleted, skipped=r.skipped),
            )

        self.call_from_thread(self._finish_run, results, execute)

    def _finish_run(self, results: list[clr.Result], execute: bool) -> None:
        log = self.query_one("#log", RichLog)
        table = Table(title=clr.s("mode_exec") if execute else clr.s("mode_dry"))
        table.add_column(clr.s("col_category"))
        table.add_column(clr.s("col_freed"), justify="right")
        table.add_column(clr.s("col_deleted"), justify="right")
        table.add_column(clr.s("col_skipped"), justify="right")
        for r in results:
            table.add_row(r.display_name(), clr.fmt_size(r.freed), str(r.deleted), str(r.skipped))
        total_freed = sum(r.freed for r in results)
        total_deleted = sum(r.deleted for r in results)
        total_skipped = sum(r.skipped for r in results)
        table.add_row(
            clr.s("col_total"), clr.fmt_size(total_freed), str(total_deleted), str(total_skipped),
            style="bold",
        )
        log.write(table)
        self.query_one("#progress", ProgressBar).add_class("hidden")
        self._busy = False
        self._has_scanned = True
        self.query_one("#btn-scan", Button).disabled = False
        self.query_one("#btn-exec", Button).disabled = not self._has_scanned


def run_tui(user_dir_override: Path | None = None) -> None:
    CleanerApp(user_dir=user_dir_override).run()


if __name__ == "__main__":
    run_tui()
