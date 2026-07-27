#!/usr/bin/env python3
"""
Windows 启动项管理工具
管理 HKCU/HKLM Run 注册表项、启动文件夹与用户计划任务
"""

from __future__ import annotations

import os
import sys
import winreg
import subprocess
import argparse
import csv
import io
from pathlib import Path
from dataclasses import dataclass

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
        "title":          "Windows 启动项管理",
        "scan_phase":     "正在扫描启动项...",
        "scan_done":      "扫描完成，共发现 {n} 个启动项",
        "menu_header":    "选择启动项  (数字键切换 / a 全选 / n 全不选 / < > 翻页 / 回车切换状态 / p 预览 / l 语言 / q 退出)",
        "menu_total":     "已选",
        "menu_will_dis":  "项将禁用",
        "menu_will_en":   "项将启用",
        "at_least_one":   "请至少选择一项",
        "press_any_key":  "按任意键返回菜单...",
        "confirm":        "将禁用 {n_dis} 项、启用 {n_en} 项，确认继续？[y/N] ",
        "cancelled":      "已取消。",
        "done":           "完成：禁用 {n_dis} 项，启用 {n_en} 项",
        "warn_admin":     "提示：修改 HKLM 项需要管理员权限，失败项请以管理员身份重新运行",
        "no_items":       "未发现可管理的启动项",
        "col_name":       "名称",
        "col_desc":       "描述",
        "col_source":     "来源",
        "col_status":     "状态",
        "col_action":     "操作",
        "col_result":     "结果",
        "status_on":      "已启用",
        "status_off":     "已禁用",
        "act_disable":    "→ 禁用",
        "act_enable":     "→ 启用",
        "res_ok":         "成功",
        "res_fail":       "失败(权限不足)",
        "page_info":      "第 {cur}/{total} 页",
        "preview_title":  "预览",
        "legend_hkcu":    "HKCU\\Run = 仅当前用户生效的注册表启动项",
        "legend_hklm":    "HKLM\\Run = 所有用户生效（修改需管理员权限）",
        "legend_sf":      "Startup = 启动文件夹中的快捷方式",
        "legend_task":    "Task Scheduler = 用户计划任务",
        "tip_unknown":    "提示：未显示描述的项目作者也不清楚其功能，请自行斟酌是否禁用",
        "lang_title":     "选择语言 / Select Language / 言語選択",
        "lang_hint":      "数字键选择 / q 返回菜单",
        "lang_invalid":   "无效选项，请重新输入",
        "welcome_desc":   "管理 Windows 启动项：注册表 Run 键、启动文件夹、用户计划任务",
        "welcome_scan":   "开始扫描",
        "welcome_quit":   "退出",
    },
    "en": {
        "title":          "Windows Startup Manager",
        "scan_phase":     "Scanning startup entries...",
        "scan_done":      "Scan complete — {n} entries found",
        "menu_header":    "Select entries  (number toggle / a all / n none / < > page / Enter toggle state / p preview / l lang / q quit)",
        "menu_total":     "Selected",
        "menu_will_dis":  "to disable",
        "menu_will_en":   "to enable",
        "at_least_one":   "Please select at least one entry",
        "press_any_key":  "Press any key to return...",
        "confirm":        "Will disable {n_dis} and enable {n_en} entries. Continue? [y/N] ",
        "cancelled":      "Cancelled.",
        "done":           "Done: disabled {n_dis}, enabled {n_en}",
        "warn_admin":     "Note: Modifying HKLM entries requires administrator privileges",
        "no_items":       "No manageable startup entries found",
        "col_name":       "Name",
        "col_desc":       "Description",
        "col_source":     "Source",
        "col_status":     "Status",
        "col_action":     "Action",
        "col_result":     "Result",
        "status_on":      "Enabled",
        "status_off":     "Disabled",
        "act_disable":    "→ Disable",
        "act_enable":     "→ Enable",
        "res_ok":         "OK",
        "res_fail":       "FAIL (no permission)",
        "page_info":      "Page {cur}/{total}",
        "preview_title":  "Preview",
        "legend_hkcu":    "HKCU\\Run = Registry run key for current user only",
        "legend_hklm":    "HKLM\\Run = Registry run key for all users (admin required to modify)",
        "legend_sf":      "Startup = Shortcut in the Startup folder",
        "legend_task":    "Task Scheduler = User-defined scheduled task",
        "tip_unknown":    "Tip: items with no description are unknown to the author — use your own judgment before disabling",
        "lang_title":     "言語選択 / Select Language / 选择语言",
        "lang_hint":      "number to select / q back",
        "lang_invalid":   "Invalid option",
        "welcome_desc":   "Manage Windows startup: registry Run keys, startup folder, user tasks",
        "welcome_scan":   "Start Scan",
        "welcome_quit":   "Quit",
    },
    "ja": {
        "title":          "Windows スタートアップ管理",
        "scan_phase":     "スタートアップ項目をスキャン中...",
        "scan_done":      "スキャン完了 — {n} 件発見",
        "menu_header":    "項目選択  (数字 / a 全選択 / n 全解除 / < > ページ / Enter 状態切替 / p プレビュー / l 言語 / q 終了)",
        "menu_total":     "選択中",
        "menu_will_dis":  "件無効化",
        "menu_will_en":   "件有効化",
        "at_least_one":   "少なくとも1つ選択してください",
        "press_any_key":  "何かキーを押して戻る...",
        "confirm":        "{n_dis} 件を無効化、{n_en} 件を有効化します。続行しますか？[y/N] ",
        "cancelled":      "キャンセルしました。",
        "done":           "完了：無効化 {n_dis} 件、有効化 {n_en} 件",
        "warn_admin":     "注意：HKLM の変更には管理者権限が必要です",
        "no_items":       "管理可能なスタートアップ項目が見つかりません",
        "col_name":       "名前",
        "col_desc":       "説明",
        "col_source":     "ソース",
        "col_status":     "状態",
        "col_action":     "操作",
        "col_result":     "結果",
        "status_on":      "有効",
        "status_off":     "無効",
        "act_disable":    "→ 無効化",
        "act_enable":     "→ 有効化",
        "res_ok":         "成功",
        "res_fail":       "失敗（権限不足）",
        "page_info":      "{cur}/{total} ページ",
        "preview_title":  "プレビュー",
        "legend_hkcu":    "HKCU\\Run = 現在のユーザーのみに適用されるレジストリ起動項目",
        "legend_hklm":    "HKLM\\Run = 全ユーザー適用（変更には管理者権限が必要）",
        "legend_sf":      "Startup = スタートアップフォルダのショートカット",
        "legend_task":    "Task Scheduler = ユーザー定義のスケジュールタスク",
        "tip_unknown":    "ヒント：説明のない項目は作者も機能不明です。無効化は慎重にご判断ください",
        "lang_title":     "言語選択 / Select Language / 选择语言",
        "lang_hint":      "数字で選択 / q 戻る",
        "lang_invalid":   "無効な選択です",
        "welcome_desc":   "Windowsスタートアップ管理：レジストリ Run キー・スタートアップフォルダ・タスク",
        "welcome_scan":   "スキャン開始",
        "welcome_quit":   "終了",
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


# ---------- 软件描述数据库 ----------
# 每条: (关键词元组, (中文描述, 英文描述, 日文描述))

_KNOWN: list[tuple[tuple[str, ...], tuple[str, str, str]]] = [
    # Windows 系统组件
    (("securityhealth",),               ("Windows 安全中心通知",           "Windows Security notification",            "Windowsセキュリティ通知")),
    (("windowsdefender",),              ("Windows Defender 实时保护",      "Windows Defender real-time protection",    "Windows Defenderリアルタイム保護")),
    (("ctfmon",),                       ("输入法/文字服务框架（系统组件）",   "Input method / CTF Loader (system)",       "入力メソッドサービス（システム）")),
    (("onedrive",),                     ("Microsoft OneDrive 云同步",       "Microsoft OneDrive sync",                  "Microsoft OneDrive同期")),
    (("msedge", "edgeautolaunch"),      ("Edge 浏览器后台预启动",            "Edge browser background pre-launch",       "Edgeバックグラウンド起動")),
    (("backgroundtaskhost",),           ("Windows 后台任务宿主（系统组件）", "Windows Background Task Host (system)",    "Windowsバックグラウンドタスクホスト")),
    (("sihost",),                       ("Shell 基础设施宿主（系统组件）",   "Shell Infrastructure Host (system)",       "シェルインフラホスト（システム）")),
    (("runtimebroker",),                ("UWP 应用运行时代理（系统组件）",   "UWP Runtime Broker (system)",              "UWPランタイムブローカー（システム）")),
    # 社交 / 通讯
    (("discord",),                      ("Discord 即时通讯",                "Discord messaging client",                 "Discordメッセージクライアント")),
    (("slack",),                        ("Slack 团队协作",                  "Slack team collaboration",                 "Slackチームコラボレーション")),
    (("msteams", "teams"),              ("Microsoft Teams 会议",            "Microsoft Teams",                          "Microsoft Teams")),
    (("zoom",),                         ("Zoom 视频会议",                   "Zoom video conferencing",                  "Zoomビデオ会議")),
    (("wechat",),                       ("微信",                            "WeChat",                                   "WeChat")),
    (("wecom",),                        ("企业微信",                         "WeCom (WeChat Work)",                      "WeCom")),
    (("dingtalk",),                     ("钉钉",                            "DingTalk",                                 "DingTalk")),
    (("feishu", "lark"),                ("飞书",                            "Feishu / Lark",                            "Feishu")),
    (("qq",),                           ("腾讯 QQ",                         "Tencent QQ",                               "Tencent QQ")),
    (("telegram",),                     ("Telegram 即时通讯",               "Telegram messaging",                       "Telegramメッセージ")),
    (("skype",),                        ("Skype 通话",                      "Skype calling",                            "Skype通話")),
    (("line",),                         ("LINE 即时通讯",                   "LINE messaging",                           "LINEメッセージ")),
    # 游戏平台
    (("steam",),                        ("Steam 游戏平台",                  "Steam gaming platform",                    "Steamゲームプラットフォーム")),
    (("epicgames", "epiclauncher"),     ("Epic Games 启动器",               "Epic Games Launcher",                      "Epic Gamesランチャー")),
    (("eadesktop",),                    ("EA Desktop 游戏平台",             "EA Desktop gaming platform",               "EA Desktopゲームプラットフォーム")),
    (("origin",),                       ("EA Origin（旧版）",               "EA Origin (legacy)",                       "EA Origin（旧版）")),
    (("ubisoftconnect", "ubisoft"),     ("Ubisoft Connect",                 "Ubisoft Connect",                          "Ubisoft Connect")),
    (("battlenet",),                    ("Battle.net 战网游戏平台",          "Battle.net launcher",                      "Battle.netランチャー")),
    (("gog",),                          ("GOG Galaxy 游戏平台",             "GOG Galaxy gaming platform",               "GOG Galaxyゲームプラットフォーム")),
    (("itch",),                         ("itch.io 独立游戏平台",             "itch.io indie game platform",              "itch.io インディーゲームプラットフォーム")),
    (("wallpaperengine",),              ("Wallpaper Engine 动态壁纸",        "Wallpaper Engine",                         "Wallpaper Engine")),
    (("leigod",),                       ("雷神加速器",                       "Leigod game accelerator",                  "Leigodゲームアクセラレーター")),
    (("uuyp", "uubooster"),             ("UU 网游加速器",                    "UU game accelerator",                      "UUゲームアクセラレーター")),
    (("wegame",),                       ("WeGame 腾讯游戏平台",              "WeGame (Tencent gaming)",                  "WeGameゲームプラットフォーム")),
    # 硬件 / 驱动工具
    (("nvspcap", "shadowplay", "nvshare"), ("NVIDIA ShadowPlay 游戏录制",   "NVIDIA ShadowPlay game capture",           "NVIDIA ShadowPlay")),
    (("nvbackend", "nvtmrep"),          ("NVIDIA Telemetry 后台服务",        "NVIDIA Telemetry backend",                 "NVIDIA Telemetryバックグラウンド")),
    (("geforceexperience",),            ("NVIDIA GeForce Experience 驱动管理", "NVIDIA GeForce Experience",             "NVIDIA GeForce Experience")),
    (("nvcontainer",),                  ("NVIDIA Container 核心服务",        "NVIDIA Container service",                 "NVIDIA Containerサービス")),
    (("rtkaudioservice", "rtkaud"),     ("Realtek 音频服务",                 "Realtek Audio service",                    "Realtekオーディオサービス")),
    (("corsair", "icue"),               ("Corsair iCUE 外设控制",            "Corsair iCUE peripheral control",          "Corsair iCUE周辺機器制御")),
    (("logioptions", "logitech"),       ("罗技外设驱动",                      "Logitech Options driver",                  "Logitechドライバー")),
    (("razer", "synapse"),              ("雷蛇 Synapse 外设驱动",            "Razer Synapse driver",                     "Razer Synapseドライバー")),
    (("steelseries",),                  ("SteelSeries 外设驱动",             "SteelSeries Engine driver",                "SteelSeries Engineドライバー")),
    (("armourycrate",),                 ("ASUS Armoury Crate 设备控制",      "ASUS Armoury Crate",                       "ASUS Armoury Crate")),
    (("dragoncenter", "msicenter"),     ("微星系统控制工具",                  "MSI Center / Dragon Center",               "MSIシステムコントロール")),
    (("ryzenmaster",),                  ("AMD Ryzen Master CPU 工具",        "AMD Ryzen Master",                         "AMD Ryzen Master")),
    (("radeon", "amdrsserv"),           ("AMD Radeon 显卡驱动工具",          "AMD Radeon Software",                      "AMD Radeon Software")),
    (("iastore", "iastordatasvc"),      ("Intel 快速存储技术",               "Intel Rapid Storage Technology",           "Intel Rapid Storage Technology")),
    (("itype", "setpoint"),             ("罗技键鼠软件（旧版）",              "Logitech SetPoint (legacy)",               "Logitechドライバー（旧版）")),
    # 生产力 / 工具
    (("powertoys",),                    ("Microsoft PowerToys 工具集",       "Microsoft PowerToys utilities",            "Microsoft PowerToys")),
    (("spotify",),                      ("Spotify 音乐播放器",               "Spotify music player",                     "Spotify音楽プレーヤー")),
    (("everything",),                   ("Everything 文件搜索（极速）",       "Everything fast file search",              "Everythingファイル検索")),
    (("listary",),                      ("Listary 文件浏览增强",             "Listary file browser enhancement",         "Listaryファイルブラウザ拡張")),
    (("flowlauncher", "flow.launcher"), ("Flow Launcher 快速启动器",         "Flow Launcher quick launcher",             "Flow Launcher")),
    (("utools",),                       ("uTools 效率工具箱",                "uTools productivity suite",                "uToolsツールボックス")),
    (("autohotkey",),                   ("AutoHotkey 脚本自动化",            "AutoHotkey script automation",             "AutoHotkeyスクリプト")),
    (("sharex",),                       ("ShareX 截图录制",                  "ShareX screenshot / capture tool",         "ShareXスクリーンショット")),
    (("snipaste",),                     ("Snipaste 截图贴图",                "Snipaste screenshot tool",                 "Snipasteスクリーンショット")),
    (("pixpin",),                       ("PixPin 截图贴图",                  "PixPin screenshot tool",                   "PixPinスクリーンショット")),
    (("translucenttb",),                ("TranslucentTB 任务栏透明化",        "TranslucentTB taskbar transparency",        "TranslucentTBタスクバー透過")),
    (("lively",),                       ("Lively 动态壁纸",                  "Lively dynamic wallpaper",                 "Livelyダイナミック壁紙")),
    (("rainmeter",),                    ("Rainmeter 桌面自定义",             "Rainmeter desktop customization",          "Rainmeterデスクトップカスタマイズ")),
    (("keypirinha",),                   ("Keypirinha 快速启动器",             "Keypirinha quick launcher",                "Keypirinaクイックランチャー")),
    (("ditto",),                        ("Ditto 剪贴板增强",                 "Ditto clipboard manager",                  "Dittoクリップボードマネージャー")),
    (("carnac",),                       ("Carnac 按键可视化",                "Carnac keystroke visualizer",              "Carnacキーストローク表示")),
    # 云存储 / 同步
    (("dropbox",),                      ("Dropbox 文件同步",                 "Dropbox file sync",                        "Dropboxファイル同期")),
    (("googledrive", "googledrivesync"),("Google Drive 同步",                "Google Drive sync",                        "Google Drive同期")),
    (("baidupan", "baidunetdisk"),      ("百度网盘",                         "Baidu Netdisk",                            "百度ネットディスク")),
    (("nutstore",),                     ("坚果云 文件同步",                   "Nutstore cloud sync",                      "Nutstore同期")),
    # 开发工具
    (("docker",),                       ("Docker Desktop 容器环境",          "Docker Desktop",                           "Docker Desktop")),
    (("vscode", "code - insiders"),     ("Visual Studio Code 编辑器",        "VS Code editor",                           "VS Codeエディター")),
    (("git",),                          ("Git 版本控制",                     "Git version control",                      "Gitバージョン管理")),
    # Adobe
    (("adobegc", "acrdsvc"),            ("Adobe 许可证管理服务",              "Adobe licensing service",                  "Adobeライセンスサービス")),
    (("adobeupdater",),                 ("Adobe 自动更新",                   "Adobe auto-updater",                       "Adobe自動アップデート")),
    (("cclibrary", "adobedesktop"),     ("Adobe Creative Cloud",             "Adobe Creative Cloud",                     "Adobe Creative Cloud")),
    # 密码管理器
    (("1password",),                    ("1Password 密码管理器",              "1Password password manager",               "1Passwordパスワードマネージャー")),
    (("bitwarden",),                    ("Bitwarden 密码管理器",              "Bitwarden password manager",               "Bitwardenパスワードマネージャー")),
    (("keepass",),                      ("KeePass 密码管理器",               "KeePass password manager",                 "KeePassパスワードマネージャー")),
    (("dashlane",),                     ("Dashlane 密码管理器",              "Dashlane password manager",                "Dashlaneパスワードマネージャー")),
    # 代理 / 网络
    (("clash",),                        ("Clash 代理工具",                   "Clash proxy tool",                         "Clashプロキシ")),
    (("v2rayn", "v2ray"),               ("v2rayN 代理工具",                  "v2rayN proxy tool",                        "v2rayNプロキシ")),
    (("mihomo",),                       ("Mihomo (Clash Meta) 代理核心",     "Mihomo (Clash Meta) proxy",                "Mihomo（Clash Meta）プロキシ")),
    (("wireguard",),                    ("WireGuard VPN",                    "WireGuard VPN",                            "WireGuard VPN")),
    (("openvpn",),                      ("OpenVPN",                          "OpenVPN",                                  "OpenVPN")),
    # 安全 / 其他
    (("malwarebytes",),                 ("Malwarebytes 恶意软件扫描",         "Malwarebytes anti-malware",                "Malwarebytesマルウェアスキャン")),
    (("nordvpn",),                      ("NordVPN",                          "NordVPN",                                  "NordVPN")),
    (("expressvpn",),                   ("ExpressVPN",                       "ExpressVPN",                               "ExpressVPN")),
]

_LANG_IDX = {"zh": 0, "en": 1, "ja": 2}


def _get_desc(name: str, command: str) -> str:
    idx = _LANG_IDX.get(_lang, 1)
    name_l = name.lower().replace(" ", "").replace("-", "").replace("_", "")
    try:
        exe_l = Path(command.strip('"').split('"')[0].split()[0]).stem.lower()
        exe_l = exe_l.replace("-", "").replace("_", "")
    except Exception:
        exe_l = ""
    for keywords, descs in _KNOWN:
        for kw in keywords:
            kw_l = kw.replace(" ", "").replace("-", "").replace("_", "")
            if kw_l in name_l or name_l in kw_l or (exe_l and kw_l in exe_l):
                return descs[idx]
    return ""


# ---------- 数据结构 ----------

@dataclass
class StartupEntry:
    name:        str
    command:     str
    source:      str        # 显示用来源标签
    source_type: str        # hkcu_run | hklm_run | startup_folder | task
    enabled:     bool
    desc:        str = ""
    # 注册表专用
    key_name:    str = ""
    hive:        int = 0
    reg_path:    str = ""
    # 启动文件夹专用
    sf_filename: str = ""
    # 计划任务专用
    task_path:   str = ""


# ---------- 注册表 StartupApproved 工具 ----------

_SA_HKCU_RUN = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
_SA_HKLM_RUN = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
_SA_SF       = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"

_ENABLED_BYTES  = bytes([0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
_DISABLED_BYTES = bytes([0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])


def _sa_is_enabled(hive: int, sa_path: str, value_name: str) -> bool:
    try:
        key = winreg.OpenKey(hive, sa_path, 0, winreg.KEY_READ)
        data, _ = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return not (isinstance(data, bytes) and len(data) >= 1 and data[0] == 0x03)
    except OSError:
        return True  # 不在 Approved 表中 = 启用


def _sa_set(hive: int, sa_path: str, value_name: str, enable: bool) -> bool:
    try:
        key = winreg.CreateKeyEx(hive, sa_path, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, value_name, 0, winreg.REG_BINARY,
                          _ENABLED_BYTES if enable else _DISABLED_BYTES)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


# ---------- 枚举函数 ----------

def _enum_reg(hive: int, run_path: str, sa_path: str,
              label: str, stype: str) -> list[StartupEntry]:
    entries = []
    try:
        key = winreg.OpenKey(hive, run_path, 0, winreg.KEY_READ)
    except OSError:
        return entries
    i = 0
    while True:
        try:
            name, cmd, _ = winreg.EnumValue(key, i)
            entries.append(StartupEntry(
                name=name, command=cmd,
                source=label, source_type=stype,
                enabled=_sa_is_enabled(hive, sa_path, name),
                desc=_get_desc(name, cmd),
                key_name=name, hive=hive, reg_path=run_path,
            ))
            i += 1
        except OSError:
            break
    winreg.CloseKey(key)
    return entries


def _enum_startup_folder(folder: Path, label: str) -> list[StartupEntry]:
    entries = []
    if not folder.exists():
        return entries
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in (".lnk", ".url", ".exe", ".bat", ".cmd"):
            continue
        name = f.stem
        cmd  = str(f)
        enabled = _sa_is_enabled(winreg.HKEY_CURRENT_USER, _SA_SF, f.name)
        entries.append(StartupEntry(
            name=name, command=cmd,
            source=label, source_type="startup_folder",
            enabled=enabled, desc=_get_desc(name, cmd),
            key_name=f.name,
            hive=winreg.HKEY_CURRENT_USER,
            sf_filename=f.name,
        ))
    return entries


def _enum_tasks() -> list[StartupEntry]:
    entries = []
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/FO", "CSV", "/V"],
            capture_output=True, timeout=20,
            text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0 or not result.stdout.strip():
            return entries
        reader = csv.DictReader(io.StringIO(result.stdout))
        seen: set[str] = set()
        for row in reader:
            task_name = (row.get("TaskName") or row.get("任务名称") or "").strip()
            status    = (row.get("Status")   or row.get("状态")     or "").strip()
            to_run    = (row.get("Task To Run") or row.get("要运行的任务") or "").strip()
            if not task_name or task_name in seen:
                continue
            seen.add(task_name)
            if task_name.startswith(r"\Microsoft\Windows" + "\\"):
                continue
            enabled = status not in ("Disabled", "已禁用", "無効")
            name = task_name.lstrip("\\").split("\\")[-1]
            entries.append(StartupEntry(
                name=name, command=to_run,
                source="Task Scheduler", source_type="task",
                enabled=enabled, desc=_get_desc(name, to_run),
                task_path=task_name,
            ))
    except Exception:
        pass
    return entries


def scan_all() -> list[StartupEntry]:
    entries: list[StartupEntry] = []
    entries += _enum_reg(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        _SA_HKCU_RUN, "HKCU\\Run", "hkcu_run",
    )
    entries += _enum_reg(
        winreg.HKEY_LOCAL_MACHINE,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        _SA_HKLM_RUN, "HKLM\\Run", "hklm_run",
    )
    startup_user = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    startup_all  = Path(os.environ.get("PROGRAMDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\StartUp"
    entries += _enum_startup_folder(startup_user, "Startup(User)")
    entries += _enum_startup_folder(startup_all,  "Startup(All)")
    entries += _enum_tasks()
    return entries


# ---------- 应用操作 ----------

def apply_entry(entry: StartupEntry, enable: bool) -> bool:
    if entry.source_type == "hkcu_run":
        return _sa_set(winreg.HKEY_CURRENT_USER, _SA_HKCU_RUN, entry.key_name, enable)
    if entry.source_type == "hklm_run":
        return _sa_set(winreg.HKEY_LOCAL_MACHINE, _SA_HKLM_RUN, entry.key_name, enable)
    if entry.source_type == "startup_folder":
        return _sa_set(winreg.HKEY_CURRENT_USER, _SA_SF, entry.sf_filename, enable)
    if entry.source_type == "task":
        flag = "/ENABLE" if enable else "/DISABLE"
        try:
            r = subprocess.run(
                ["schtasks", "/Change", "/TN", entry.task_path, flag],
                capture_output=True, timeout=10,
            )
            return r.returncode == 0
        except Exception:
            return False
    return False


# ---------- 欢迎界面 ----------

_WELCOME_ART = r"""  ____ _____  _    ____ _____ _   _ ____
 / ___|_   _|/ \  |  _ \_   _| | | |  _ \
 \___ \ | | / _ \ | |_) || | | | | | |_) |
  ___) || |/ ___ \|  _ < | | | |_| |  __/
 |____/ |_/_/   \_\_| \_\|_|  \___/|_|   """


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
    menu_text = _render_lang_menu(status)
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


# ---------- 主菜单（分页） ----------

_PAGE_SIZE = 8


def _status_str(enabled: bool) -> str:
    return f"{GREEN}{s('status_on')}{RESET}" if enabled else f"{YELLOW}{s('status_off')}{RESET}"


def render_menu(entries: list[StartupEntry], selected: list[bool],
                page: int, status: str = "") -> str:
    total_pages = max(1, (len(entries) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    start = page * _PAGE_SIZE
    page_ents = entries[start: start + _PAGE_SIZE]
    page_sel  = selected[start: start + _PAGE_SIZE]

    SEP  = "=" * 74
    SEP2 = "-" * 74

    # 统计选中项中将要执行的操作
    n_dis = sum(1 for e, sel in zip(entries, selected) if sel and e.enabled)
    n_en  = sum(1 for e, sel in zip(entries, selected) if sel and not e.enabled)

    lines = [
        SEP,
        f"  {s('menu_header')}",
        f"  {CYAN}{s('page_info', cur=page+1, total=total_pages)}{RESET}",
        SEP,
    ]

    NAME_W = 20
    DESC_W = 26
    SRC_W  = 14

    for i, (entry, sel) in enumerate(zip(page_ents, page_sel), 1):
        check = "✓" if sel else " "
        name_s = _trunc(entry.name, NAME_W)
        desc_s = _trunc(entry.desc, DESC_W) if entry.desc else ""
        src_s  = _trunc(entry.source, SRC_W)
        stat_s = _status_str(entry.enabled)
        # 若已选中，在行首提示即将执行的操作
        if sel:
            act_s = f" {YELLOW}{s('act_disable')}{RESET}" if entry.enabled else f" {GREEN}{s('act_enable')}{RESET}"
        else:
            act_s = ""
        lines.append(
            f"  [{i}] {check}  {_pad(name_s, NAME_W)}  "
            f"{_pad(desc_s, DESC_W)}  "
            f"{_pad(src_s, SRC_W)}  {stat_s}{act_s}"
        )

    lines.append(SEP2)
    sel_count = sum(1 for x in selected if x)
    summary = f"  {s('menu_total')}: {sel_count}"
    if sel_count > 0:
        parts = []
        if n_dis > 0:
            parts.append(f"{YELLOW}{n_dis} {s('menu_will_dis')}{RESET}")
        if n_en > 0:
            parts.append(f"{GREEN}{n_en} {s('menu_will_en')}{RESET}")
        summary += "  (" + "  ".join(parts) + ")"
    lines.append(summary)

    # 来源说明栏
    lines.append(SEP2)
    lines.append(f"  {DIM}{s('legend_hkcu')}{RESET}")
    lines.append(f"  {DIM}{s('legend_hklm')}{RESET}")
    lines.append(f"  {DIM}{s('legend_sf')}{RESET}")
    lines.append(f"  {DIM}{s('legend_task')}{RESET}")
    lines.append(f"  {YELLOW}{s('tip_unknown')}{RESET}")

    if status:
        lines.append(f"  {YELLOW}{status}{RESET}")
    lines.append("> ")
    return "\n".join(lines)


def print_result_table(entries: list[StartupEntry],
                       actions: list[bool],   # True=已执行启用, False=已执行禁用
                       results: list[bool]) -> None:
    COL_NAMES = [s("col_name"), s("col_source"), s("col_action"), s("col_result")]
    rows = []
    for entry, enable, ok in zip(entries, actions, results):
        act_str = s("act_enable") if enable else s("act_disable")
        rows.append([
            _trunc(entry.name, 28),
            entry.source,
            act_str,
            s("res_ok") if ok else s("res_fail"),
        ])

    widths = [
        max(_dw(COL_NAMES[i]), max((_dw(r[i]) for r in rows), default=0))
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
    for row in rows:
        print(_row(row))
    print(_div("╚", "╩", "╝"))

    n_dis = sum(1 for en, ok in zip(actions, results) if not en and ok)
    n_en  = sum(1 for en, ok in zip(actions, results) if en and ok)
    print(f"\n{GREEN}{s('done', n_dis=n_dis, n_en=n_en)}{RESET}\n")


def select_menu(entries: list[StartupEntry]) -> list[bool] | None:
    """交互菜单。返回 selected 列表，或 None（退出）。"""
    import msvcrt
    while msvcrt.kbhit():
        msvcrt.getch()

    selected = [False] * len(entries)
    page = 0
    status = ""
    total_pages = max(1, (len(entries) + _PAGE_SIZE - 1) // _PAGE_SIZE)

    menu_text = render_menu(entries, selected, page, status)
    print(menu_text, end="", flush=True)

    def _redraw():
        nonlocal menu_text
        n_up = menu_text.count("\n")
        print(f"\033[{n_up}A\r\033[J", end="", flush=True)
        menu_text = render_menu(entries, selected, page, status)
        print(menu_text.replace("\n", "\033[K\n") + "\033[K", end="", flush=True)

    while True:
        try:
            key = msvcrt.getch()
        except KeyboardInterrupt:
            print(); sys.exit(0)

        # 方向键
        if key in (b"\x00", b"\xe0"):
            arrow = msvcrt.getch()
            if arrow == b"K":    # 左箭头
                page = max(0, page - 1); status = ""; _redraw()
            elif arrow == b"M":  # 右箭头
                page = min(total_pages - 1, page + 1); status = ""; _redraw()
            continue

        try:
            ch = key.decode("utf-8").lower()
        except (UnicodeDecodeError, AttributeError):
            continue

        if ch == "\x03":
            print(); sys.exit(0)
        elif ch in "12345678":
            idx = page * _PAGE_SIZE + int(ch) - 1
            if idx < len(entries):
                selected[idx] = not selected[idx]; status = ""; _redraw()
        elif ch == "a":
            selected = [True] * len(entries); status = ""; _redraw()
        elif ch == "n":
            selected = [False] * len(entries); status = ""; _redraw()
        elif ch == "<":
            page = max(0, page - 1); status = ""; _redraw()
        elif ch == ">":
            page = min(total_pages - 1, page + 1); status = ""; _redraw()
        elif ch in ("\r", "\n"):
            if not any(selected):
                status = s("at_least_one"); _redraw()
            else:
                print(); return selected
        elif ch == "p":
            if not any(selected):
                status = s("at_least_one"); _redraw()
            else:
                os.system("cls")
                active = [(e, not e.enabled) for e, sel in zip(entries, selected) if sel]
                print(f"\n{BOLD}  {s('preview_title')}{RESET}\n")
                for entry, enable in active:
                    if enable:
                        print(f"  {GREEN}{s('act_enable')}{RESET}  {entry.name}  {DIM}[{entry.source}]{RESET}")
                    else:
                        print(f"  {YELLOW}{s('act_disable')}{RESET}  {entry.name}  {DIM}[{entry.source}]{RESET}")
                print(f"\n{YELLOW}{s('press_any_key')}{RESET}", end="", flush=True)
                while msvcrt.kbhit():
                    msvcrt.getch()
                msvcrt.getch()
                os.system("cls")
                menu_text = render_menu(entries, selected, page, "")
                print(menu_text, end="", flush=True)
        elif ch == "l":
            os.system("cls"); select_language(); os.system("cls")
            menu_text = render_menu(entries, selected, page, "")
            print(menu_text, end="", flush=True)
        elif ch == "q":
            print(); return None


# ---------- 主流程 ----------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="startup",
        description="Windows 启动项管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python startup.py           # 交互式管理界面
  python startup.py --list    # 列出所有启动项后退出
  python startup.py --list -v # 列出启动项并显示命令行路径
        """,
    )
    p.add_argument("--list",    action="store_true", help="列出所有启动项后退出（不进入交互界面）")
    p.add_argument("-v", "--verbose", action="store_true", help="显示完整命令行路径")
    return p.parse_args()


def _wait_key() -> None:
    import msvcrt
    while msvcrt.kbhit():
        msvcrt.getch()
    msvcrt.getch()


def main():
    args = parse_args()

    if not args.list:
        show_welcome()
        os.system("cls")

    print(f"\n{BOLD}{s('title')}{RESET}")
    print(f"{CYAN}{s('scan_phase')}{RESET}", end="", flush=True)
    entries = scan_all()
    print(f"\r{GREEN}✓{RESET}  {s('scan_done', n=len(entries))}\n")

    if args.list:
        if not entries:
            print(f"  {YELLOW}{s('no_items')}{RESET}")
            return
        name_w = max((_dw(e.name)   for e in entries), default=10)
        src_w  = max((_dw(e.source) for e in entries), default=10)
        for e in entries:
            stat = f"{GREEN}[{s('status_on')}]{RESET} " if e.enabled else f"{YELLOW}[{s('status_off')}]{RESET}"
            line = f"  {stat}  {_pad(e.name, name_w)}  {_pad(e.source, src_w)}"
            if e.desc:
                line += f"  {DIM}{e.desc}{RESET}"
            print(line)
            if args.verbose:
                print(f"           {DIM}{e.command[:110]}{RESET}")
        return

    if not entries:
        print(f"  {YELLOW}{s('no_items')}{RESET}")
        return

    while True:
        selected = select_menu(entries)
        if selected is None:
            break

        # 每项按当前状态取反：启用→禁用，禁用→启用
        active_pairs: list[tuple[StartupEntry, bool]] = [
            (e, not e.enabled)
            for e, sel in zip(entries, selected) if sel
        ]
        n_dis = sum(1 for _, en in active_pairs if not en)
        n_en  = sum(1 for _, en in active_pairs if en)

        print()
        answer = input(
            f"{YELLOW}{s('confirm', n_dis=n_dis, n_en=n_en)}{RESET}"
        ).strip().lower()
        if answer != "y":
            print(s("cancelled"))
            os.system("cls")
            continue

        print()
        action_flags: list[bool] = []
        result_flags: list[bool] = []
        active_entries: list[StartupEntry] = []

        for entry, enable in active_pairs:
            ok = apply_entry(entry, enable)
            if ok:
                entry.enabled = enable
            tag = f"{GREEN}OK  {RESET}" if ok else f"{RED}FAIL{RESET}"
            print(f"  [{tag}]  {entry.name}")
            active_entries.append(entry)
            action_flags.append(enable)
            result_flags.append(ok)

        print()
        print_result_table(active_entries, action_flags, result_flags)

        hklm_failed = [e for e, ok in zip(active_entries, result_flags)
                       if not ok and e.source_type == "hklm_run"]
        if hklm_failed:
            print(f"{YELLOW}{s('warn_admin')}{RESET}\n")

        print(f"{YELLOW}{s('press_any_key')}{RESET}", end="", flush=True)
        _wait_key()
        os.system("cls")


if __name__ == "__main__":
    main()
