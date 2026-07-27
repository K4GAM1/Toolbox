#!/usr/bin/env python3
"""
Windows 右键菜单管理工具
管理文件 / 文件夹 / 桌面右键菜单项（shell 命令项 + 扩展程序）
"""

from __future__ import annotations

import os
import sys
import ctypes
import winreg
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import dataclass, field
from typing import Optional

_VERSION = "1.05"

# 高分屏下避免界面模糊
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# ─── Privilege ────────────────────────────────────────────────────────────────

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

# ─── i18n ─────────────────────────────────────────────────────────────────────

_LANG_ORDER = ["en", "ja", "zh"]
_LANG_DISPLAY = {"en": "English", "ja": "日本語", "zh": "中文"}
_LANG_FROM_DISPLAY = {v: k for k, v in _LANG_DISPLAY.items()}
_lang: str = "en"

def _system_ui_lang() -> str:
    """系统 UI 语言（仅用于标题/logo）：中文系统→zh，日文→ja，其余→en"""
    try:
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return {0x04: "zh", 0x11: "ja"}.get(langid & 0x3FF, "en")
    except Exception:
        return "en"

_SYS_LANG = _system_ui_lang()

_UI: dict[str, dict[str, str]] = {
    "zh": {
        "title":             "Windows 右键菜单管理",
        "tab_file":          "文件右键",
        "tab_dir":           "文件夹 / 桌面",
        "tab_add":           "添加自定义",
        "col_display":       "显示名称",
        "col_type":          "类型",
        "col_status":        "状态",
        "col_name":          "键名",
        "col_path":          "注册表路径",
        "type_shell":        "命令项",
        "type_shellex":      "扩展程序",
        "status_on":         "✔ 启用",
        "status_off":        "✘ 禁用",
        "btn_enable":        "启用",
        "btn_disable":       "禁用",
        "btn_delete":        "删除",
        "btn_refresh":       "刷新",
        "btn_add":           "添加",
        "btn_browse":        "浏览...",
        "btn_lang":          "EN",
        "add_keyname":       "键名（唯一标识）",
        "add_display":       "显示名称",
        "add_command":       "命令",
        "add_icon":          "图标路径（可选）",
        "add_target":        "应用到",
        "add_file":          "文件",
        "add_dir":           "文件夹",
        "add_desktop":       "桌面/空白处",
        "hint_cmd":          "提示：%1 = 选中文件路径，%V = 文件夹路径",
        "no_select":         "请先选择一项",
        "already_enabled":   "该项已启用",
        "already_disabled":  "该项已禁用",
        "confirm_del":       "确定删除「{name}」？此操作不可撤销。",
        "del_ok":            "已删除：{name}",
        "del_fail":          "删除失败（可能需要管理员权限）",
        "disable_ok":        "已禁用：{name}",
        "enable_ok":         "已启用：{name}",
        "op_fail":           "操作失败",
        "add_ok":            "✔ 已添加",
        "add_fail":          "✘ 添加失败",
        "field_empty":       "请填写键名、显示名称和命令",
        "need_target":       "请至少勾选一个应用目标",
        "admin_badge":       "管理员",
        "status_bar":        "共 {n} 项（已隐藏系统项 {h} 项）  ·  v{ver}",
        "col_source":        "来源软件",
        "src_unknown":       "未知 / 残留",
        "show_system":       "显示系统项",
        "run_hidden":        "隐藏窗口运行（bat / cmd 脚本推荐）",
        "add_ok_hint":       "（在「显示更多选项」里，启用经典菜单后直接可见）",
        "sec_file_shell":    "文件  ›  命令项",
        "sec_file_ext":      "文件  ›  扩展程序",
        "sec_dir_shell":     "文件夹  ›  命令项",
        "sec_dir_ext":       "文件夹  ›  扩展程序",
        "sec_desk_shell":    "桌面 / 空白处  ›  命令项",
        "sec_desk_ext":      "桌面 / 空白处  ›  扩展程序",
        "btn_classic_en":    "启用经典菜单",
        "btn_classic_dis":   "恢复 Win11 菜单",
        "btn_restart_exp":   "重启资源管理器",
        "banner_win11":      "⚠ Win11 新版菜单生效中：本工具管理的项目都藏在「显示更多选项」里，启用经典菜单后更改可见。",
        "need_restart":      "已写入，重启资源管理器后生效（右上角按钮）",
        "applied_now":       "已生效",
        "confirm_restart":   "需要重启资源管理器才能生效。\n\n立即重启？（桌面会闪烁一下，不影响已打开的程序；"
                             "个别程序的托盘图标可能消失，重启对应程序即可恢复）",
        "classic_on_ok":     "已启用经典菜单",
        "classic_off_ok":    "已恢复 Win11 新版菜单",
        "exp_restarted":     "资源管理器已重启",
        "restarting":        "正在重启资源管理器...",
        "btn_help":          "帮助",
        "help_title":        "帮助 — 概念说明",
        "help_text": (
            "【命令项 与 扩展程序】\n"
            "命令项：注册表里的「菜单文字 + 一条命令」，点击后把所选文件路径代入 %1 执行。"
            "结构透明，可自行添加，禁用立即生效。\n"
            "扩展程序：软件安装的 COM 组件（DLL），右键时被资源管理器加载、由代码动态生成菜单"
            "（如 7-Zip 的子菜单）。功能强但不透明，右键菜单卡顿多由它引起。\n\n"
            "【禁用原理】\n"
            "命令项：写入 LegacyDisable 标记（仅当前用户，无需管理员），立即生效。\n"
            "扩展程序 / Win11 新版菜单项：将其 CLSID 加入当前用户的 Blocked 黑名单，"
            "阻止 DLL 被加载，需重启资源管理器生效。\n"
            "禁用随时可恢复，比删除安全；删除系统层条目需要管理员权限。\n\n"
            "【Win11 经典菜单】\n"
            "Win11 默认右键只显示新版菜单，经典项藏在「显示更多选项」里。"
            "启用经典菜单（仅影响当前用户，可随时恢复）后，本工具管理的项目直接可见。\n\n"
            "【添加自定义菜单】\n"
            "%1 = 所选文件路径；%V = 文件夹/空白处路径（应用到桌面时自动替换）。\n"
            "「隐藏窗口运行」适合 bat / cmd 脚本：经 wscript 静默启动，不弹黑窗。\n\n"
            "【来源软件 / 系统项】\n"
            "来源软件解析自菜单项背后 DLL/EXE 的版本信息。位于 Windows 目录或微软出品的"
            "项目默认隐藏，勾选「显示系统项」可见。\n\n"
            "【托盘图标提示】\n"
            "重启资源管理器后，个别程序（如 Spotify）的托盘图标可能消失——"
            "这是该程序未监听任务栏重建消息所致，重启该程序即可恢复。"
        ),
    },
    "en": {
        "title":             "Windows Context Menu Manager",
        "tab_file":          "Files",
        "tab_dir":           "Folder / Desktop",
        "tab_add":           "Add Custom",
        "col_display":       "Display Name",
        "col_type":          "Type",
        "col_status":        "Status",
        "col_name":          "Key Name",
        "col_path":          "Registry Path",
        "type_shell":        "Command",
        "type_shellex":      "Extension",
        "status_on":         "✔ Enabled",
        "status_off":        "✘ Disabled",
        "btn_enable":        "Enable",
        "btn_disable":       "Disable",
        "btn_delete":        "Delete",
        "btn_refresh":       "Refresh",
        "btn_add":           "Add",
        "btn_browse":        "Browse...",
        "btn_lang":          "日本語",
        "add_keyname":       "Key Name (unique ID)",
        "add_display":       "Display Name",
        "add_command":       "Command",
        "add_icon":          "Icon Path (optional)",
        "add_target":        "Apply to",
        "add_file":          "Files",
        "add_dir":           "Folders",
        "add_desktop":       "Desktop / Background",
        "hint_cmd":          "Tip: %1 = selected file path,  %V = folder path",
        "no_select":         "Please select an item first",
        "already_enabled":   "Already enabled",
        "already_disabled":  "Already disabled",
        "confirm_del":       'Delete "{name}"? This cannot be undone.',
        "del_ok":            "Deleted: {name}",
        "del_fail":          "Delete failed (may need admin rights)",
        "disable_ok":        "Disabled: {name}",
        "enable_ok":         "Enabled: {name}",
        "op_fail":           "Operation failed",
        "add_ok":            "✔ Added",
        "add_fail":          "✘ Failed to add",
        "field_empty":       "Please fill in key name, display name, and command",
        "need_target":       "Please select at least one target",
        "admin_badge":       "Administrator",
        "status_bar":        "{n} items ({h} system items hidden)  ·  v{ver}",
        "col_source":        "Source",
        "src_unknown":       "Unknown / orphaned",
        "show_system":       "Show system items",
        "run_hidden":        "Run hidden (recommended for bat / cmd)",
        "add_ok_hint":       "(under \"Show more options\"; enable classic menu to see directly)",
        "sec_file_shell":    "Files  ›  Commands",
        "sec_file_ext":      "Files  ›  Extensions",
        "sec_dir_shell":     "Folder  ›  Commands",
        "sec_dir_ext":       "Folder  ›  Extensions",
        "sec_desk_shell":    "Desktop / Background  ›  Commands",
        "sec_desk_ext":      "Desktop / Background  ›  Extensions",
        "btn_classic_en":    "Enable Classic Menu",
        "btn_classic_dis":   "Restore Win11 Menu",
        "btn_restart_exp":   "Restart Explorer",
        "banner_win11":      "⚠ Win11 new context menu is active: items managed here are hidden under \"Show more options\", so changes won't be visible. Enable the classic menu to see changes directly.",
        "need_restart":      "Saved. Restart Explorer to apply (button at top right)",
        "applied_now":       "Applied",
        "confirm_restart":   "Explorer must be restarted to apply.\n\nRestart now? (The desktop will flicker briefly; "
                             "open apps are not affected. Some tray icons may disappear — restart those apps to restore them)",
        "classic_on_ok":     "Classic menu enabled",
        "classic_off_ok":    "Win11 menu restored",
        "exp_restarted":     "Explorer restarted",
        "restarting":        "Restarting Explorer...",
        "btn_help":          "Help",
        "help_title":        "Help — Concepts",
        "help_text": (
            "[Commands vs Extensions]\n"
            "Command: a registry entry of \"menu text + one command line\"; clicking it runs the "
            "command with the selected file substituted for %1. Transparent, user-creatable, "
            "disabling takes effect immediately.\n"
            "Extension: a COM component (DLL) installed by software. Explorer loads it on "
            "right-click and its code builds the menu dynamically (e.g. the 7-Zip submenu). "
            "Powerful but opaque — context-menu lag is usually caused by these.\n\n"
            "[How disabling works]\n"
            "Command: a LegacyDisable marker is written (current user only, no admin needed); "
            "effective immediately.\n"
            "Extension / Win11 new-menu item: its CLSID is added to the per-user Blocked list "
            "so the DLL is never loaded; requires an Explorer restart.\n"
            "Disabling is always reversible and safer than deleting. Deleting system-level "
            "entries requires administrator rights.\n\n"
            "[Win11 classic menu]\n"
            "Win11 shows only the new menu by default; classic items hide under \"Show more "
            "options\". Enable the classic menu (current user only, reversible) to see all "
            "managed items directly.\n\n"
            "[Adding custom items]\n"
            "%1 = selected file path; %V = folder/background path (auto-substituted for "
            "desktop targets).\n"
            "\"Run hidden\" suits bat / cmd scripts: launched silently via wscript, no console "
            "window.\n\n"
            "[Source / system items]\n"
            "Source is resolved from the version info of the DLL/EXE behind each item. Items "
            "in the Windows directory or published by Microsoft are hidden by default; check "
            "\"Show system items\" to reveal them.\n\n"
            "[Tray icon note]\n"
            "After restarting Explorer, some apps' tray icons (e.g. Spotify) may disappear — "
            "those apps don't listen for the taskbar-recreated message. Restart the app to "
            "restore its icon."
        ),
    },
    "ja": {
        "title":             "Windows 右クリックメニュー管理",
        "tab_file":          "ファイル",
        "tab_dir":           "フォルダー / デスクトップ",
        "tab_add":           "カスタム追加",
        "col_display":       "表示名",
        "col_type":          "種類",
        "col_status":        "状態",
        "col_name":          "キー名",
        "col_path":          "レジストリ パス",
        "type_shell":        "コマンド項目",
        "type_shellex":      "拡張機能",
        "status_on":         "✔ 有効",
        "status_off":        "✘ 無効",
        "btn_enable":        "有効化",
        "btn_disable":       "無効化",
        "btn_delete":        "削除",
        "btn_refresh":       "更新",
        "btn_add":           "追加",
        "btn_browse":        "参照...",
        "btn_lang":          "中文",
        "add_keyname":       "キー名（一意の ID）",
        "add_display":       "表示名",
        "add_command":       "コマンド",
        "add_icon":          "アイコン パス（任意）",
        "add_target":        "適用先",
        "add_file":          "ファイル",
        "add_dir":           "フォルダー",
        "add_desktop":       "デスクトップ / 背景",
        "hint_cmd":          "ヒント：%1 = 選択ファイルのパス、%V = フォルダーのパス",
        "no_select":         "先に項目を選択してください",
        "already_enabled":   "既に有効です",
        "already_disabled":  "既に無効です",
        "confirm_del":       "「{name}」を削除しますか？この操作は元に戻せません。",
        "del_ok":            "削除しました：{name}",
        "del_fail":          "削除に失敗しました（管理者権限が必要な場合があります）",
        "disable_ok":        "無効化しました：{name}",
        "enable_ok":         "有効化しました：{name}",
        "op_fail":           "操作に失敗しました",
        "add_ok":            "✔ 追加しました",
        "add_fail":          "✘ 追加に失敗しました",
        "field_empty":       "キー名・表示名・コマンドを入力してください",
        "need_target":       "適用先を 1 つ以上選択してください",
        "admin_badge":       "管理者",
        "status_bar":        "全 {n} 件（システム項目 {h} 件を非表示）  ·  v{ver}",
        "col_source":        "提供元",
        "src_unknown":       "不明 / 残留",
        "show_system":       "システム項目を表示",
        "run_hidden":        "ウィンドウを隠して実行（bat / cmd 推奨）",
        "add_ok_hint":       "（「その他のオプションを表示」内。クラシック メニュー有効化で直接表示）",
        "sec_file_shell":    "ファイル  ›  コマンド項目",
        "sec_file_ext":      "ファイル  ›  拡張機能",
        "sec_dir_shell":     "フォルダー  ›  コマンド項目",
        "sec_dir_ext":       "フォルダー  ›  拡張機能",
        "sec_desk_shell":    "デスクトップ / 背景  ›  コマンド項目",
        "sec_desk_ext":      "デスクトップ / 背景  ›  拡張機能",
        "btn_classic_en":    "クラシック メニューを有効化",
        "btn_classic_dis":   "Win11 メニューに戻す",
        "btn_restart_exp":   "エクスプローラー再起動",
        "banner_win11":      "⚠ Win11 の新メニューが有効です：本ツールで管理する項目は「その他のオプションを表示」内に隠れています。クラシック メニューを有効にすると変更が直接見えます。",
        "need_restart":      "保存しました。エクスプローラー再起動後に反映されます（右上のボタン）",
        "applied_now":       "反映しました",
        "confirm_restart":   "反映にはエクスプローラーの再起動が必要です。\n\n今すぐ再起動しますか？（デスクトップが一瞬ちらつきます。"
                             "起動中のアプリには影響しません。一部のトレイ アイコンが消える場合は、該当アプリを再起動すると戻ります）",
        "classic_on_ok":     "クラシック メニューを有効にしました",
        "classic_off_ok":    "Win11 メニューに戻しました",
        "exp_restarted":     "エクスプローラーを再起動しました",
        "restarting":        "エクスプローラーを再起動しています...",
        "btn_help":          "ヘルプ",
        "help_title":        "ヘルプ — 用語説明",
        "help_text": (
            "【コマンド項目 と 拡張機能】\n"
            "コマンド項目：レジストリ上の「メニュー文字列 + コマンド 1 行」。クリックすると"
            "選択ファイルのパスを %1 に代入して実行します。構造が透明で、自作でき、無効化は即時反映。\n"
            "拡張機能：ソフトがインストールする COM コンポーネント（DLL）。右クリック時に"
            "エクスプローラーへ読み込まれ、コードがメニューを動的に生成します（例：7-Zip の"
            "サブメニュー）。強力ですが不透明で、右クリックが重い原因の多くはこれです。\n\n"
            "【無効化の仕組み】\n"
            "コマンド項目：LegacyDisable マークを書き込み（現在のユーザーのみ、管理者不要）、即時反映。\n"
            "拡張機能 / Win11 新メニュー項目：CLSID をユーザーの Blocked リストへ追加して"
            "DLL の読み込みを阻止。エクスプローラーの再起動が必要です。\n"
            "無効化はいつでも戻せるため削除より安全。システム層の削除には管理者権限が必要です。\n\n"
            "【Win11 クラシック メニュー】\n"
            "Win11 の既定では新メニューのみ表示され、クラシック項目は「その他のオプションを表示」"
            "内に隠れます。クラシック メニューを有効化（現在のユーザーのみ・可逆）すると、"
            "本ツールで管理する項目が直接見えます。\n\n"
            "【カスタム メニューの追加】\n"
            "%1 = 選択ファイルのパス、%V = フォルダー / 背景のパス（デスクトップ適用時は自動置換）。\n"
            "「ウィンドウを隠して実行」は bat / cmd 向け：wscript 経由で静かに起動し、"
            "黒いウィンドウが出ません。\n\n"
            "【提供元 / システム項目】\n"
            "提供元は各項目の DLL/EXE のバージョン情報から解決します。Windows ディレクトリ内"
            "または Microsoft 製の項目は既定で非表示。「システム項目を表示」で確認できます。\n\n"
            "【トレイ アイコンについて】\n"
            "エクスプローラー再起動後、一部アプリ（例：Spotify）のトレイ アイコンが消えることが"
            "あります。タスクバー再生成メッセージを監視していないアプリ側の問題で、"
            "そのアプリを再起動すれば戻ります。"
        ),
    },
}

def t(key: str, **kw) -> str:
    return _UI.get(_lang, _UI["en"]).get(key, key).format(**kw)

def t_sys(key: str) -> str:
    """按系统语言取文案（标题/logo 用，不随界面语言切换）"""
    return _UI.get(_SYS_LANG, _UI["en"]).get(key, key)

# ─── Registry constants ───────────────────────────────────────────────────────

HKCR = winreg.HKEY_CLASSES_ROOT
HKCU = winreg.HKEY_CURRENT_USER
HKLM = winreg.HKEY_LOCAL_MACHINE

BLOCKED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked"

# HKCR base paths (merged view)
_HKCR_BASE = {
    "file":    r"*",
    "dir":     r"Directory",
    "desktop": r"Directory\Background",
}

# HKCU paths for user-space overrides (no admin required)
_HKCU_BASE = {
    "file":    r"SOFTWARE\Classes\*",
    "dir":     r"SOFTWARE\Classes\Directory",
    "desktop": r"SOFTWARE\Classes\Directory\Background",
}

# Win11 经典菜单开关：此键存在（InprocServer32 默认值为空）即恢复 Win10 经典右键菜单
_CLASSIC_CLSID    = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
_CLASSIC_KEY      = _CLASSIC_CLSID + r"\InprocServer32"

def is_win11() -> bool:
    try:
        return sys.getwindowsversion().build >= 22000
    except Exception:
        return False

def classic_menu_enabled() -> bool:
    try:
        k = winreg.OpenKey(HKCU, _CLASSIC_KEY)
        winreg.CloseKey(k)
        return True
    except OSError:
        return False

def set_classic_menu(enable: bool) -> bool:
    try:
        if enable:
            k = winreg.CreateKeyEx(HKCU, _CLASSIC_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "")
            winreg.CloseKey(k)
        else:
            _delete_key_tree(HKCU, _CLASSIC_CLSID)
        return True
    except OSError:
        return False

def restart_explorer() -> None:
    """重启资源管理器。

    使用 taskkill /f 终止，然后通过 cmd /c start 以完全独立的进程启动
    explorer，避免作为 Python 子进程拉起导致 Shell 注册异常（黑屏/任务栏
    不出现）。系统若已自动拉起则跳过启动步骤，避免多开文件夹窗口。
    """
    import time
    user32 = ctypes.windll.user32
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def tray_alive() -> bool:
        return bool(user32.FindWindowW("Shell_TrayWnd", None))

    # 强制结束 explorer
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"],
                   capture_output=True, creationflags=flags)

    # 等待彻底退出（最多 2 秒）
    for _ in range(20):
        if not tray_alive():
            break
        time.sleep(0.1)
    time.sleep(0.3)

    # 系统有时会自动拉起 shell；只有没拉起时才由我们启动，
    # 用 cmd /c start 确保 explorer 作为独立顶层进程运行
    if not tray_alive():
        subprocess.Popen(
            ["cmd", "/c", "start", "", "explorer.exe"],
            creationflags=flags,
        )

    for _ in range(50):                  # 等待任务栏出现，最多 5 秒
        if tray_alive():
            return
        time.sleep(0.1)

def _key_exists(hive: int, path: str) -> bool:
    try:
        k = winreg.OpenKey(hive, path)
        winreg.CloseKey(k)
        return True
    except OSError:
        return False

def _load_indirect(s: str) -> str:
    """解析 @shell32.dll,-8506 形式的 MUI 资源字符串为可读文本"""
    if s.startswith("@"):
        buf = ctypes.create_unicode_buffer(512)
        try:
            if ctypes.windll.shlwapi.SHLoadIndirectString(s, buf, 512, None) == 0:
                s = buf.value or s
        except Exception:
            pass
    # 去掉菜单加速键标记：& 单独出现是标记，&& 是字面 &
    return s.replace("&&", "\x00").replace("&", "").replace("\x00", "&")

# ─── Source-software resolution ───────────────────────────────────────────────

_WINDIR = os.environ.get("SystemRoot", r"C:\Windows").lower()
_MODINFO_CACHE: dict[str, tuple[str, bool]] = {}

def _file_version_strings(path: str) -> dict[str, str]:
    """读取 PE 文件版本资源中的产品名 / 描述 / 公司名"""
    try:
        ver = ctypes.windll.version
        size = ver.GetFileVersionInfoSizeW(path, None)
        if not size:
            return {}
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(path, 0, size, buf):
            return {}
        p, ln = ctypes.c_void_p(), ctypes.c_uint()
        if ver.VerQueryValueW(buf, r"\VarFileInfo\Translation",
                              ctypes.byref(p), ctypes.byref(ln)) and ln.value >= 4:
            arr = ctypes.cast(p, ctypes.POINTER(ctypes.c_ushort))
            lang, cp = arr[0], arr[1]
        else:
            lang, cp = 0x0409, 1252
        out: dict[str, str] = {}
        for key in ("FileDescription", "ProductName", "CompanyName"):
            sub = "\\StringFileInfo\\%04x%04x\\%s" % (lang, cp, key)
            if ver.VerQueryValueW(buf, sub, ctypes.byref(p), ctypes.byref(ln)) and ln.value:
                out[key] = ctypes.wstring_at(p.value).strip("\x00").strip()
        return out
    except Exception:
        return {}

def _classify_module(module: str) -> tuple[str, bool]:
    """模块路径 -> (来源软件名, 是否系统项)"""
    if not module:
        return "", False
    cached = _MODINFO_CACHE.get(module.lower())
    if cached:
        return cached
    info = _file_version_strings(module)
    label = (info.get("FileDescription") or info.get("ProductName")
             or os.path.basename(module))
    company = info.get("CompanyName", "")
    is_sys = (module.lower().startswith(_WINDIR)
              or company.lower().startswith("microsoft"))
    result = (label, is_sys)
    _MODINFO_CACHE[module.lower()] = result
    return result

def _clsid_module(clsid: str) -> str:
    """CLSID -> 注册的 DLL/EXE 路径（含 32 位 WOW6432Node 残留项）"""
    if not clsid:
        return ""
    for root in (rf"CLSID\{clsid}", rf"WOW6432Node\CLSID\{clsid}"):
        for server in ("InprocServer32", "LocalServer32"):
            try:
                k = winreg.OpenKey(HKCR, rf"{root}\{server}")
                val = str(winreg.QueryValueEx(k, "")[0])
                winreg.CloseKey(k)
                if val:
                    return _resolve_module_path(val)
            except OSError:
                pass
    return ""

def _extract_exe(cmd: str) -> str:
    """从命令行字符串中取出可执行文件路径（容忍未加引号的含空格路径）"""
    cmd = cmd.strip()
    if not cmd:
        return ""
    if cmd.startswith('"'):
        end = cmd.find('"', 1)
        return cmd[1:end] if end > 0 else cmd.strip('"')
    parts = cmd.split()
    for i in range(len(parts), 0, -1):
        cand = " ".join(parts[:i])
        if os.path.exists(cand):
            return cand
    return parts[0]

def _resolve_module_path(p: str) -> str:
    """展开环境变量；裸 DLL 名（如 shell32.dll / efscore.dll）按 System32 补全"""
    p = os.path.expandvars(p.strip().strip('"'))
    if p and not os.path.isabs(p):
        cand = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                            "System32", p)
        if os.path.exists(cand):
            return cand
    return p

def _reg_value(hive: int, path: str, name: str) -> str:
    try:
        k = winreg.OpenKey(hive, path)
        try:
            return str(winreg.QueryValueEx(k, name)[0])
        finally:
            winreg.CloseKey(k)
    except OSError:
        return ""

def _shell_item_info(target: str, name: str) -> tuple[str, str, str]:
    """shell 命令项 -> (模块路径, ExplorerCommandHandler CLSID, MUIVerb 显示名)

    模块解析顺序覆盖各代验证机制：
    command 可执行文件 -> DelegateExecute -> ExplorerCommandHandler（Win11
    新版菜单项）-> DropTarget -> MUIVerb 所引用的 DLL
    """
    base = _HKCR_BASE[target] + r"\shell" + "\\" + name

    handler  = _reg_value(HKCR, base, "ExplorerCommandHandler")
    muiverb  = _reg_value(HKCR, base, "MUIVerb")
    cmd      = _reg_value(HKCR, base + r"\command", "")
    delegate = _reg_value(HKCR, base + r"\command", "DelegateExecute")
    droptgt  = _reg_value(HKCR, base + r"\DropTarget", "CLSID")

    module = _extract_exe(os.path.expandvars(cmd)) if cmd else ""
    # cmd/rundll32 这类宿主进程不代表归属，继续向真正的组件追溯
    if not module or os.path.basename(module).lower() in (
            "rundll32.exe", "cmd.exe", "wscript.exe", "cscript.exe"):
        for clsid in (delegate, handler, droptgt):
            dm = _clsid_module(clsid) if clsid else ""
            if dm:
                module = dm
                break
    if not module and muiverb.startswith("@"):
        module = muiverb[1:].split(",")[0]
    return _resolve_module_path(module), handler, muiverb

# ─── Data model ───────────────────────────────────────────────────────────────

@dataclass
class MenuItem:
    name:     str    # registry subkey name
    display:  str    # text shown in right-click menu
    kind:     str    # "shell" | "shellex"
    target:   str    # "file" | "dir" | "desktop"
    reg_path: str    # display-only registry path
    clsid:    str = ""
    disabled: bool = False
    source:   str  = ""     # 来源软件（DLL/EXE 版本信息里的产品名）
    is_system: bool = False  # Windows 目录下 或 Microsoft 出品

# ─── Registry reading ─────────────────────────────────────────────────────────

def _get_blocked_clsids() -> set[str]:
    blocked: set[str] = set()
    try:
        key = winreg.OpenKey(HKCU, BLOCKED_KEY)
        i = 0
        while True:
            try:
                val, _, _ = winreg.EnumValue(key, i)
                blocked.add(val.upper())
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except OSError:
        pass
    return blocked

def _resolve_clsid(clsid: str) -> str:
    """Try to get a human-readable name for a CLSID."""
    if not clsid or not clsid.startswith("{"):
        return ""
    for hive, path in (
        (HKCR, rf"CLSID\{clsid}"),
        (HKCR, rf"WOW6432Node\CLSID\{clsid}"),
        (HKLM, rf"SOFTWARE\Classes\CLSID\{clsid}"),
        (HKCU, rf"SOFTWARE\Classes\CLSID\{clsid}"),
    ):
        try:
            k = winreg.OpenKey(hive, path)
            name, _ = winreg.QueryValueEx(k, "")
            winreg.CloseKey(k)
            if name:
                return _load_indirect(str(name))
        except OSError:
            pass
    return ""

def _is_disabled_via_hkcu_override(target: str, name: str) -> bool:
    """Check if a shell item has been disabled via our HKCU LegacyDisable override."""
    path = _HKCU_BASE[target] + r"\shell" + "\\" + name
    try:
        k = winreg.OpenKey(HKCU, path)
        winreg.QueryValueEx(k, "LegacyDisable")
        winreg.CloseKey(k)
        return True
    except OSError:
        return False

def read_shell_items(target: str) -> list[MenuItem]:
    items: list[MenuItem] = []
    base = _HKCR_BASE[target]
    shell_path = base + r"\shell"
    blocked = _get_blocked_clsids()

    try:
        key = winreg.OpenKey(HKCR, shell_path)
    except OSError:
        return items

    i = 0
    while True:
        try:
            name = winreg.EnumKey(key, i)
            i += 1
        except OSError:
            break
        try:
            module, handler, muiverb = _shell_item_info(target, name)

            display = _reg_value(HKCR, shell_path + "\\" + name, "") \
                      or muiverb or name
            display = _load_indirect(display)

            # 禁用判定：本工具的 HKCU LegacyDisable 覆盖（经典菜单），
            # 或 ExplorerCommandHandler 已进 Blocked 列表（Win11 新版菜单）
            disabled = _is_disabled_via_hkcu_override(target, name) \
                       or (handler.upper() in blocked if handler else False)
            source, is_sys = _classify_module(module)

            items.append(MenuItem(
                name=name,
                display=display,
                kind="shell",
                target=target,
                reg_path=f"HKCR\\{shell_path}\\{name}",
                clsid=handler,
                disabled=disabled,
                source=source,
                is_system=is_sys,
            ))
        except OSError:
            pass

    winreg.CloseKey(key)
    return items

def read_shellex_items(target: str) -> list[MenuItem]:
    items: list[MenuItem] = []
    base = _HKCR_BASE[target]
    shellex_path = base + r"\shellex\ContextMenuHandlers"
    blocked = _get_blocked_clsids()

    try:
        key = winreg.OpenKey(HKCR, shellex_path)
    except OSError:
        return items

    i = 0
    while True:
        try:
            name = winreg.EnumKey(key, i)
            i += 1
        except OSError:
            break
        try:
            sub = winreg.OpenKey(key, name)
            try:
                raw = str(winreg.QueryValueEx(sub, "")[0]).strip()
            except OSError:
                raw = ""
            winreg.CloseKey(sub)

            # 默认值通常是 CLSID；但部分系统项（如 Taskband Pin）默认值是
            # 描述文字、键名本身才是 CLSID
            name_clean   = name.strip()
            display_hint = ""
            if raw.lstrip("-").startswith("{"):
                clsid = raw
            elif name_clean.startswith("{"):
                clsid = name_clean
                display_hint = raw
            else:
                clsid = raw

            effective_clsid = clsid.lstrip("-").strip()
            # Normalise: ensure braces
            if effective_clsid and not effective_clsid.startswith("{"):
                effective_clsid = "{" + effective_clsid + "}"

            disabled = (
                effective_clsid.upper() in blocked
                or clsid.startswith("-")
            )

            display = _resolve_clsid(effective_clsid) or display_hint or name
            source, is_sys = _classify_module(_clsid_module(effective_clsid))

            items.append(MenuItem(
                name=name,
                display=display,
                kind="shellex",
                target=target,
                reg_path=f"HKCR\\{shellex_path}\\{name}",
                clsid=clsid,
                disabled=disabled,
                source=source,
                is_system=is_sys,
            ))
        except OSError:
            pass

    winreg.CloseKey(key)
    return items

# ─── Registry writing ─────────────────────────────────────────────────────────

def _add_to_blocked(clsid: str) -> None:
    clsid = clsid.lstrip("-")
    if clsid and not clsid.startswith("{"):
        clsid = "{" + clsid + "}"
    key = winreg.CreateKeyEx(HKCU, BLOCKED_KEY, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, clsid, 0, winreg.REG_SZ, "")
    winreg.CloseKey(key)

def disable_item(item: MenuItem) -> bool:
    try:
        if item.kind == "shell":
            path = _HKCU_BASE[item.target] + r"\shell" + "\\" + item.name
            key = winreg.CreateKeyEx(HKCU, path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "LegacyDisable", 0, winreg.REG_SZ, "")
            winreg.CloseKey(key)
            # 带 ExplorerCommandHandler 的项还出现在 Win11 新版菜单里，
            # LegacyDisable 管不到，必须同时拉黑其 CLSID
            if item.clsid:
                _add_to_blocked(item.clsid)
            item.disabled = True
            return True
        elif item.kind == "shellex":
            if not item.clsid:
                return False
            _add_to_blocked(item.clsid)
            item.disabled = True
            return True
    except OSError:
        pass
    return False

def enable_item(item: MenuItem) -> bool:
    try:
        if item.kind == "shell":
            path = _HKCU_BASE[item.target] + r"\shell" + "\\" + item.name
            try:
                key = winreg.OpenKey(HKCU, path, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "LegacyDisable")
                winreg.CloseKey(key)
            except OSError:
                pass  # value didn't exist — already enabled
            if item.clsid:
                _remove_from_blocked(item.clsid)
            item.disabled = False
            return True
        elif item.kind == "shellex":
            if item.clsid:
                _remove_from_blocked(item.clsid)
            item.disabled = False
            return True
    except OSError:
        pass
    return False

def _delete_key_tree(hive: int, path: str) -> bool:
    """Recursively delete a registry key and all its subkeys."""
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS)
        while True:
            try:
                subkey = winreg.EnumKey(key, 0)
                _delete_key_tree(hive, path + "\\" + subkey)
            except OSError:
                break
        winreg.CloseKey(key)
        winreg.DeleteKey(hive, path)
        return True
    except OSError:
        return False

def _remove_from_blocked(clsid: str) -> None:
    clsid = clsid.lstrip("-")
    if clsid and not clsid.startswith("{"):
        clsid = "{" + clsid + "}"
    try:
        key = winreg.OpenKey(HKCU, BLOCKED_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, clsid)
        winreg.CloseKey(key)
    except OSError:
        pass

def delete_item(item: MenuItem) -> bool:
    """删除菜单项。HKCU 覆盖键无论如何先清理；若 HKCR（系统层）仍存在
    则继续删系统层——失败说明需要管理员，如实报失败而不是假成功。"""
    if item.kind == "shell":
        suffix = r"\shell" + "\\" + item.name
    elif item.kind == "shellex":
        suffix = r"\shellex\ContextMenuHandlers" + "\\" + item.name
    else:
        return False

    _delete_key_tree(HKCU, _HKCU_BASE[item.target] + suffix)

    hkcr_path = _HKCR_BASE[item.target] + suffix
    gone = (not _key_exists(HKCR, hkcr_path)) or _delete_key_tree(HKCR, hkcr_path)

    # 彻底删除后清理 Blocked 列表残留，避免同 CLSID 的新装扩展被误禁
    if gone and item.clsid:
        _remove_from_blocked(item.clsid)
    return gone

# 隐藏窗口运行 bat/cmd 的 VBS 包装器（wscript 是 GUI 宿主，不弹控制台）
_VBS_HIDDEN = (
    'Dim sh, cmd, i\r\n'
    'Set sh = CreateObject("WScript.Shell")\r\n'
    'cmd = ""\r\n'
    'For i = 0 To WScript.Arguments.Count - 1\r\n'
    '    cmd = cmd & """" & WScript.Arguments(i) & """ "\r\n'
    'Next\r\n'
    'sh.Run cmd, 0, False\r\n'
)

def ensure_hidden_runner() -> str:
    """生成（或刷新）隐藏运行辅助脚本，返回其绝对路径。
    放在 LOCALAPPDATA 下固定位置，菜单项注册后不依赖本工具所在目录。"""
    d = os.path.join(os.environ.get("LOCALAPPDATA",
                     os.path.expanduser("~")), "Toolbox")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "run-hidden.vbs")
    with open(p, "w", encoding="ascii") as f:
        f.write(_VBS_HIDDEN)
    return p

def add_custom_item(name: str, display: str, command: str, icon: str,
                    targets: list[str]) -> bool:
    success = True
    for target in targets:
        # 桌面/空白处右键没有选中对象，%1 不会被替换，必须用 %V（当前目录）
        cmd = command.replace("%1", "%V") if target == "desktop" else command
        path = _HKCU_BASE[target] + r"\shell" + "\\" + name
        try:
            key = winreg.CreateKeyEx(HKCU, path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, display)
            if icon:
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon)
            cmd_key = winreg.CreateKeyEx(key, "command", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(cmd_key)
            winreg.CloseKey(key)
        except OSError:
            success = False
    return success

# ─── GUI — ItemList widget ────────────────────────────────────────────────────

class ItemList(ttk.Frame):
    """Treeview + scrollbar for displaying context-menu items in sections."""

    def __init__(self, parent: tk.Widget, **kw):
        super().__init__(parent, **kw)
        self._items: list[MenuItem] = []
        self._build()

    def _build(self):
        cols = ("display", "source", "type", "status", "name", "path")
        tv = ttk.Treeview(self, columns=cols, show="tree headings",
                          selectmode="browse")
        self._tv = tv

        tv.heading("#0", text="")
        tv.column("#0", width=20, stretch=False, minwidth=20)

        tv.heading("display", text=t("col_display"))
        tv.column("display", width=190, minwidth=120)
        tv.heading("source", text=t("col_source"))
        tv.column("source", width=170, minwidth=100)
        tv.heading("type", text=t("col_type"))
        tv.column("type", width=75, minwidth=60)
        tv.heading("status", text=t("col_status"))
        tv.column("status", width=70, minwidth=60)
        tv.heading("name", text=t("col_name"))
        tv.column("name", width=150, minwidth=80)
        tv.heading("path", text=t("col_path"))
        tv.column("path", width=330, minwidth=120)

        tv.tag_configure("disabled", foreground="#999999")
        tv.tag_configure("section", foreground="#444444",
                         font=("Segoe UI", 9, "bold"))

        ys = ttk.Scrollbar(self, orient="vertical",   command=tv.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)

        tv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def populate_sections(self, sections: list[tuple[str, list[MenuItem]]]):
        tv = self._tv
        tv.delete(*tv.get_children())
        self._items.clear()

        for sec_name, items in sections:
            # Always show section headers even if empty (helpful for orientation)
            sec_iid = tv.insert("", "end",
                values=(sec_name, "", "", "", "", ""),
                tags=("section",),
                open=True,
            )
            for item in items:
                self._items.append(item)
                tag = "disabled" if item.disabled else ""
                tv.insert(sec_iid, "end",
                    values=self._row_values(item),
                    tags=(tag,),
                    iid=str(id(item)),
                )

    @staticmethod
    def _row_values(item: MenuItem) -> tuple:
        source = item.source
        if not source and item.kind == "shellex":
            source = t("src_unknown")
        return (
            item.display,
            source,
            t("type_shellex") if item.kind == "shellex" else t("type_shell"),
            t("status_off") if item.disabled else t("status_on"),
            item.name,
            item.reg_path,
        )

    def selected_item(self) -> Optional[MenuItem]:
        sel = self._tv.selection()
        if not sel:
            return None
        iid = sel[0]
        return next((i for i in self._items if str(id(i)) == iid), None)

    def update_row(self, item: MenuItem):
        iid = str(id(item))
        tag = "disabled" if item.disabled else ""
        self._tv.item(iid, values=self._row_values(item), tags=(tag,))

    def refresh_headings(self):
        self._tv.heading("display", text=t("col_display"))
        self._tv.heading("source",  text=t("col_source"))
        self._tv.heading("type",    text=t("col_type"))
        self._tv.heading("status",  text=t("col_status"))
        self._tv.heading("name",    text=t("col_name"))
        self._tv.heading("path",    text=t("col_path"))

# ─── GUI — Main app ───────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self._admin = is_admin()
        self._build_ui()
        self.after(80, self.refresh_all)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # 标题（logo）固定为系统语言，不随界面语言切换
        self.title(t_sys("title"))
        self.geometry("1050x650")
        self.minsize(760, 500)

        # ── Top bar ──
        top = ttk.Frame(self, padding=(10, 5, 10, 5))
        top.pack(fill="x")

        ttk.Label(top, text=t_sys("title"),
                  font=("Segoe UI", 12, "bold")).pack(side="left")

        # 第三方菜单管理全程不需要管理员，常态不标注；
        # 仅以管理员运行（非常规状态）时显示徽章
        self._badge: Optional[tk.Label] = None
        if self._admin:
            self._badge = tk.Label(top, text=t("admin_badge"), fg="white",
                                   bg="#2a9d5c", padx=7, pady=2,
                                   font=("Segoe UI", 8))
            self._badge.pack(side="left", padx=10)

        self._lang_var = tk.StringVar()
        self._lang_cb = ttk.Combobox(
            top, textvariable=self._lang_var,
            values=[_LANG_DISPLAY[l] for l in _LANG_ORDER],
            state="readonly", width=9,
        )
        self._lang_cb.pack(side="right")
        self._lang_cb.bind("<<ComboboxSelected>>", self._on_lang_select)
        self._lang_var.set(_LANG_DISPLAY[_lang])

        self._help_btn = ttk.Button(top, text=t("btn_help"), width=6,
                                    command=self._show_help)
        self._help_btn.pack(side="right", padx=(0, 6))

        self._restart_btn = ttk.Button(top, text=t("btn_restart_exp"),
                                       command=self._restart_explorer)
        self._restart_btn.pack(side="right", padx=(0, 6))

        self._classic_btn: Optional[ttk.Button] = None
        if is_win11():
            self._classic_btn = ttk.Button(top, command=self._toggle_classic)
            self._classic_btn.pack(side="right", padx=(0, 6))
            self._update_classic_btn()

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # ── Win11 新版菜单提示横幅 ──
        self._banner = tk.Frame(self, bg="#fff3cd")
        self._banner_label = tk.Label(
            self._banner, text=t("banner_win11"), bg="#fff3cd", fg="#7a5c00",
            anchor="w", justify="left", padx=10, pady=6,
            font=("Segoe UI", 9), wraplength=980)
        self._banner_label.pack(fill="x")
        self._update_banner()

        # ── Notebook ──
        self._v_showsys = tk.BooleanVar(value=False)
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=4, pady=(4, 2))

        # Tab 1 — Files
        tab1 = ttk.Frame(self._nb)
        self._nb.add(tab1, text=t("tab_file"))
        self._file_list = ItemList(tab1)
        self._file_list.pack(fill="both", expand=True)
        self._make_action_bar(tab1, "file")

        # Tab 2 — Dir + Desktop
        tab2 = ttk.Frame(self._nb)
        self._nb.add(tab2, text=t("tab_dir"))
        self._dir_list = ItemList(tab2)
        self._dir_list.pack(fill="both", expand=True)
        self._make_action_bar(tab2, "dir")

        # Tab 3 — Add custom
        tab3 = ttk.Frame(self._nb)
        self._nb.add(tab3, text=t("tab_add"))
        self._build_add_tab(tab3)

        # ── Status bar ──
        self._status_var = tk.StringVar(value="")
        ttk.Separator(self, orient="horizontal").pack(fill="x", side="bottom")
        ttk.Label(self, textvariable=self._status_var,
                  anchor="w", padding=(8, 3)).pack(fill="x", side="bottom")

    def _make_action_bar(self, parent: tk.Widget, tab_id: str):
        bar = ttk.Frame(parent, padding=(4, 4))
        bar.pack(fill="x")
        lst = self._file_list if tab_id == "file" else self._dir_list
        ttk.Button(bar, text=t("btn_enable"),
                   command=lambda: self._on_enable(lst)).pack(side="left", padx=2)
        ttk.Button(bar, text=t("btn_disable"),
                   command=lambda: self._on_disable(lst)).pack(side="left", padx=2)
        ttk.Button(bar, text=t("btn_delete"),
                   command=lambda: self._on_delete(lst)).pack(side="left", padx=2)
        ttk.Separator(bar, orient="vertical").pack(side="left", padx=8, fill="y", pady=2)
        ttk.Button(bar, text=t("btn_refresh"),
                   command=self.refresh_all).pack(side="left", padx=2)
        cb = ttk.Checkbutton(bar, text=t("show_system"),
                             variable=self._v_showsys, command=self.refresh_all)
        cb.pack(side="right", padx=6)
        if not hasattr(self, "_showsys_cbs"):
            self._showsys_cbs: list[ttk.Checkbutton] = []
        self._showsys_cbs.append(cb)

    def _build_add_tab(self, parent: tk.Widget):
        outer = ttk.Frame(parent, padding=24)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        def row_label(text: str, r: int):
            ttk.Label(outer, text=text + "  ").grid(
                row=r, column=0, sticky="e", pady=5)

        r = 0

        row_label(t("add_keyname"), r)
        self._f_keyname = ttk.Entry(outer, width=40)
        self._f_keyname.grid(row=r, column=1, columnspan=2, sticky="ew", pady=5)
        r += 1

        row_label(t("add_display"), r)
        self._f_display = ttk.Entry(outer, width=40)
        self._f_display.grid(row=r, column=1, columnspan=2, sticky="ew", pady=5)
        r += 1

        row_label(t("add_command"), r)
        cmd_row = ttk.Frame(outer)
        cmd_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=5)
        cmd_row.columnconfigure(0, weight=1)
        self._f_cmd = ttk.Entry(cmd_row)
        self._f_cmd.grid(row=0, column=0, sticky="ew")
        ttk.Button(cmd_row, text=t("btn_browse"), width=10,
                   command=self._browse_exe).grid(row=0, column=1, padx=(6, 0))
        r += 1

        ttk.Label(outer, text=t("hint_cmd"), foreground="#666666",
                  font=("Segoe UI", 8)).grid(
            row=r, column=1, columnspan=2, sticky="w", pady=(0, 6))
        r += 1

        self._v_runhidden = tk.BooleanVar(value=False)
        self._runhidden_cb = ttk.Checkbutton(outer, text=t("run_hidden"),
                                             variable=self._v_runhidden)
        self._runhidden_cb.grid(row=r, column=1, columnspan=2,
                                sticky="w", pady=(0, 6))
        r += 1

        row_label(t("add_icon"), r)
        icon_row = ttk.Frame(outer)
        icon_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=5)
        icon_row.columnconfigure(0, weight=1)
        self._f_icon = ttk.Entry(icon_row)
        self._f_icon.grid(row=0, column=0, sticky="ew")
        ttk.Button(icon_row, text=t("btn_browse"), width=10,
                   command=self._browse_icon).grid(row=0, column=1, padx=(6, 0))
        r += 1

        row_label(t("add_target"), r)
        tgt = ttk.Frame(outer)
        tgt.grid(row=r, column=1, columnspan=2, sticky="w", pady=5)
        self._v_file  = tk.BooleanVar(value=True)
        self._v_dir   = tk.BooleanVar(value=False)
        self._v_desk  = tk.BooleanVar(value=False)
        ttk.Checkbutton(tgt, text=t("add_file"),    variable=self._v_file ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(tgt, text=t("add_dir"),     variable=self._v_dir  ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(tgt, text=t("add_desktop"), variable=self._v_desk ).pack(side="left")
        r += 1

        btn_row = ttk.Frame(outer)
        btn_row.grid(row=r, column=1, columnspan=2, sticky="w", pady=(14, 0))
        ttk.Button(btn_row, text=t("btn_add"), width=10,
                   command=self._on_add).pack(side="left")
        self._add_result = ttk.Label(btn_row, text="")
        self._add_result.pack(side="left", padx=12)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_enable(self, lst: ItemList):
        item = lst.selected_item()
        if not item:
            self._status(t("no_select")); return
        if not item.disabled:
            self._status(t("already_enabled")); return
        if enable_item(item):
            lst.update_row(item)
            msg = t("enable_ok", name=item.display)
            if item.kind == "shellex" or item.clsid:
                msg += "  ·  " + t("need_restart")
            self._status(msg)
        else:
            self._status(t("op_fail"))

    def _on_disable(self, lst: ItemList):
        item = lst.selected_item()
        if not item:
            self._status(t("no_select")); return
        if item.disabled:
            self._status(t("already_disabled")); return
        if disable_item(item):
            lst.update_row(item)
            msg = t("disable_ok", name=item.display)
            if item.kind == "shellex" or item.clsid:
                msg += "  ·  " + t("need_restart")
            self._status(msg)
        else:
            self._status(t("op_fail"))

    def _on_delete(self, lst: ItemList):
        item = lst.selected_item()
        if not item:
            self._status(t("no_select")); return
        if not messagebox.askyesno(t("btn_delete"),
                                   t("confirm_del", name=item.display),
                                   parent=self):
            return
        if delete_item(item):
            self.refresh_all()
            msg = t("del_ok", name=item.display)
            if item.kind == "shellex" or item.clsid:
                msg += "  ·  " + t("need_restart")
            self._status(msg)
        else:
            self._status(t("del_fail"))
            messagebox.showwarning(t("btn_delete"), t("del_fail"), parent=self)

    def _on_add(self):
        name    = self._f_keyname.get().strip()
        display = self._f_display.get().strip()
        command = self._f_cmd.get().strip()
        icon    = self._f_icon.get().strip()

        if not name or not display or not command:
            self._add_result.config(text=t("field_empty"), foreground="red")
            return

        targets = []
        if self._v_file.get():  targets.append("file")
        if self._v_dir.get():   targets.append("dir")
        if self._v_desk.get():  targets.append("desktop")

        if not targets:
            self._add_result.config(text=t("need_target"), foreground="red")
            return

        if self._v_runhidden.get():
            vbs = ensure_hidden_runner()
            command = f'wscript.exe //B "{vbs}" ' + command

        if add_custom_item(name, display, command, icon, targets):
            msg = t("add_ok")
            if is_win11() and not classic_menu_enabled():
                msg += " " + t("add_ok_hint")
            self._add_result.config(text=msg, foreground="#2a9d5c")
            for entry in (self._f_keyname, self._f_display, self._f_cmd, self._f_icon):
                entry.delete(0, "end")
            self._v_runhidden.set(False)
            self.refresh_all()
        else:
            self._add_result.config(text=t("add_fail"), foreground="red")

    def _browse_exe(self):
        path = filedialog.askopenfilename(
            parent=self,
            title=t("add_command"),
            filetypes=[
                ("可执行文件", "*.exe *.bat *.cmd *.ps1"),
                ("所有文件", "*.*"),
            ],
        )
        if not path:
            return
        path = os.path.normpath(path)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".ps1":
            # .ps1 直接执行会用记事本打开，必须经由 powershell -File
            cmd = (f'powershell.exe -NoProfile -ExecutionPolicy Bypass '
                   f'-File "{path}" "%1"')
        else:
            cmd = f'"{path}" "%1"'
        self._f_cmd.delete(0, "end")
        self._f_cmd.insert(0, cmd)
        # 脚本类命令默认勾选隐藏运行，避免弹黑窗
        if ext in (".bat", ".cmd", ".ps1"):
            self._v_runhidden.set(True)

    def _browse_icon(self):
        path = filedialog.askopenfilename(
            parent=self,
            title=t("add_icon"),
            filetypes=[
                ("图标 / 可执行文件", "*.ico *.exe *.dll"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self._f_icon.delete(0, "end")
            self._f_icon.insert(0, path)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh_all(self):
        show_sys = self._v_showsys.get()

        def flt(items: list[MenuItem]) -> list[MenuItem]:
            return items if show_sys else [i for i in items if not i.is_system]

        file_shell  = read_shell_items("file")
        file_ext    = read_shellex_items("file")
        dir_shell   = read_shell_items("dir")
        dir_ext     = read_shellex_items("dir")
        desk_shell  = read_shell_items("desktop")
        desk_ext    = read_shellex_items("desktop")
        all_lists = [file_shell, file_ext, dir_shell, dir_ext, desk_shell, desk_ext]

        self._file_list.populate_sections([
            (t("sec_file_shell"),  flt(file_shell)),
            (t("sec_file_ext"),    flt(file_ext)),
        ])
        self._dir_list.populate_sections([
            (t("sec_dir_shell"),   flt(dir_shell)),
            (t("sec_dir_ext"),     flt(dir_ext)),
            (t("sec_desk_shell"),  flt(desk_shell)),
            (t("sec_desk_ext"),    flt(desk_ext)),
        ])

        shown  = sum(len(flt(l)) for l in all_lists)
        hidden = sum(len(l) for l in all_lists) - shown
        msg = t("status_bar", n=shown, h=hidden, ver=_VERSION)
        if self._admin:
            msg += "  ·  " + t("admin_badge")
        self._status(msg)

    # ── Win11 classic menu / Explorer ─────────────────────────────────────────

    def _update_banner(self):
        show = is_win11() and not classic_menu_enabled()
        if show:
            kw = {"fill": "x"}
            if hasattr(self, "_nb"):
                kw["before"] = self._nb
            self._banner.pack(**kw)
        else:
            self._banner.pack_forget()

    def _update_classic_btn(self):
        if self._classic_btn is None:
            return
        text = t("btn_classic_dis") if classic_menu_enabled() else t("btn_classic_en")
        self._classic_btn.config(text=text)

    def _toggle_classic(self):
        enable = not classic_menu_enabled()
        if not set_classic_menu(enable):
            self._status(t("op_fail"))
            return
        self._update_classic_btn()
        self._update_banner()
        self._status(t("classic_on_ok") if enable else t("classic_off_ok"))
        if messagebox.askyesno(t("btn_restart_exp"), t("confirm_restart"),
                               parent=self):
            self._do_restart_explorer()

    def _restart_explorer(self):
        if messagebox.askyesno(t("btn_restart_exp"), t("confirm_restart"),
                               parent=self):
            self._do_restart_explorer()

    def _do_restart_explorer(self):
        # restart_explorer 内部有等待循环（最长数秒），先把状态画出来
        self._status(t("restarting"))
        self.update_idletasks()
        restart_explorer()
        self._status(t("exp_restarted"))

    # ── Help ──────────────────────────────────────────────────────────────────

    def _show_help(self):
        win = tk.Toplevel(self)
        win.title(t("help_title"))
        win.geometry("700x560")
        win.transient(self)

        txt = tk.Text(win, wrap="word", padx=16, pady=12,
                      font=("Segoe UI", 10), spacing1=2, spacing3=6,
                      relief="flat", background=self.cget("background"))
        ys = ttk.Scrollbar(win, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ys.set)
        txt.insert("1.0", t("help_text"))
        txt.configure(state="disabled")
        ys.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

    # ── Lang toggle ───────────────────────────────────────────────────────────

    def _on_lang_select(self, event=None):
        global _lang
        _lang = _LANG_FROM_DISPLAY.get(self._lang_var.get(), "en")
        self._lang_cb.selection_clear()
        self._rebuild_labels()
        self.refresh_all()

    def _rebuild_labels(self):
        # 窗口标题与顶部 logo 固定系统语言，这里不更新
        self._lang_var.set(_LANG_DISPLAY[_lang])
        self._help_btn.config(text=t("btn_help"))
        self._restart_btn.config(text=t("btn_restart_exp"))
        self._update_classic_btn()
        self._banner_label.config(text=t("banner_win11"))
        if self._badge is not None:
            self._badge.config(text=t("admin_badge"))
        self._nb.tab(0, text=t("tab_file"))
        self._nb.tab(1, text=t("tab_dir"))
        self._nb.tab(2, text=t("tab_add"))
        for cb in self._showsys_cbs:
            cb.config(text=t("show_system"))
        self._runhidden_cb.config(text=t("run_hidden"))
        self._file_list.refresh_headings()
        self._dir_list.refresh_headings()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self._status_var.set(msg)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
