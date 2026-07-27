#!/usr/bin/env python3
"""
Evict.py  —  System Drive Directory Migration Tool
将常见开发工具目录从系统盘迁移到用户指定位置。
只处理可通过环境变量或配置文件实现的迁移，不使用符号链接。
"""

import os
import sys
import msvcrt
import string as _string
import shutil
import winreg
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional

# ── ANSI & console ────────────────────────────────────────────────────────────

def _enable_ansi():
    import ctypes
    ctypes.windll.kernel32.SetConsoleMode(
        ctypes.windll.kernel32.GetStdHandle(-11), 7
    )

try:
    _enable_ansi()
except Exception:
    pass

R    = "\033[0m";  BOLD = "\033[1m";  DIM  = "\033[2m"
RED  = "\033[31m"; GRN  = "\033[32m"; YEL  = "\033[33m"; CYN  = "\033[36m"

def _ok(msg):   print(f"  {GRN}✓{R} {msg}")
def _err(msg):  print(f"  {RED}✗{R} {msg}")
def _warn(msg): print(f"  {YEL}⚠{R} {msg}")
def _info(msg): print(f"  {CYN}→{R} {msg}")
def _clear():   os.system("cls")

def _get_key() -> str:
    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(
            msvcrt.getwch(), "")
    return {"\r": "ENTER", " ": "SPACE", "\x1b": "ESC"}.get(ch, ch.lower())

# ── Banner ────────────────────────────────────────────────────────────────────

_BANNER_ART = (
    "\n"
    "    ___  __   __ ___   ___  _____\n"
    "   | __| \\ \\ / /|_ _| / __||_   _|\n"
    "   | _|   \\ V /  | | | (__   | |  \n"
    "   |___|   \\_/  |___| \\___| |_|   \n"
    "\n"
    "   System Drive Directory Migration Tool  \xb7  beta 0.1\n"
    "   " + "─" * 51 + "\n"
)

def _print_banner():
    print(f"{CYN}{BOLD}{_BANNER_ART}{R}")

# ── i18n ─────────────────────────────────────────────────────────────────────

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "lang_title":     "Select Language",
        "target_title":   "Target Directory",
        "target_prompt":  "Enter target root path",
        "avail_drives":   "Available non-system drives",
        "hint_nav":       "↑↓ Move   Space Toggle   A All/None   Enter Confirm   B Back",
        "hint_input":     "Enter path   (B = back)",
        "select_title":   "Select items to migrate",
        "confirm_title":  "Confirm target paths",
        "exec_title":     "Migrating",
        "done_title":     "Done",
        "success":        "Succeeded",
        "failed":         "Failed",
        "no_items":       "No items found on the system drive. Nothing to do.",
        "none_sel":       "No items selected — please select at least one.",
        "sysdrive_warn":  "Target is still on the system drive. Please choose another.",
        "empty_warn":     "Path cannot be empty.",
        "restart_hint":   "Restart your terminal for changes to take effect.",
        "press_any":      "Press any key to continue...",
        "frm":            "from",
        "to":             "  to",
        "override_hint":  "Enter to confirm  /  type a new path  /  B to go back",
    },
    "zh": {
        "lang_title":     "选择语言",
        "target_title":   "目标目录",
        "target_prompt":  "输入目标根路径",
        "avail_drives":   "可用非系统盘",
        "hint_nav":       "↑↓ 移动   空格 切换   A 全选/取消   Enter 确认   B 返回",
        "hint_input":     "输入路径（B = 返回）",
        "select_title":   "选择要迁移的项目",
        "confirm_title":  "确认目标路径",
        "exec_title":     "正在迁移",
        "done_title":     "完成",
        "success":        "成功",
        "failed":         "失败",
        "no_items":       "系统盘上未发现需要迁移的目录。",
        "none_sel":       "未选择任何项目，请至少选择一项。",
        "sysdrive_warn":  "目标路径仍在系统盘，请选择其他盘。",
        "empty_warn":     "路径不能为空。",
        "restart_hint":   "请重新启动终端使环境变量生效。",
        "press_any":      "按任意键继续...",
        "frm":            "来源",
        "to":             "目标",
        "override_hint":  "Enter 确认 / 输入新路径 / B 返回",
    },
    "ja": {
        "lang_title":     "言語を選択",
        "target_title":   "移行先ディレクトリ",
        "target_prompt":  "移行先のルートパスを入力",
        "avail_drives":   "利用可能な非システムドライブ",
        "hint_nav":       "↑↓ 移動   スペース 選択   A 全/解除   Enter 確認   B 戻る",
        "hint_input":     "パスを入力（B = 戻る）",
        "select_title":   "移行する項目を選択",
        "confirm_title":  "移行先パスの確認",
        "exec_title":     "移行中",
        "done_title":     "完了",
        "success":        "成功",
        "failed":         "失敗",
        "no_items":       "システムドライブに移行対象が見つかりません。",
        "none_sel":       "項目が選択されていません。少なくとも1つ選択してください。",
        "sysdrive_warn":  "移行先がシステムドライブです。別のドライブを選択してください。",
        "empty_warn":     "パスを入力してください。",
        "restart_hint":   "変更を反映するにはターミナルを再起動してください。",
        "press_any":      "何かキーを押してください...",
        "frm":            "移行元",
        "to":             "移行先",
        "override_hint":  "Enter で確認 / 新しいパスを入力 / B で戻る",
    },
}

_lang = "en"

def t(key: str) -> str:
    return _STRINGS[_lang].get(key, key)

# ── 注册表 / 环境变量 ──────────────────────────────────────────────────────────

def _get_env(name: str) -> Optional[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            v, _ = winreg.QueryValueEx(k, name)
            return v
    except FileNotFoundError:
        return None

def _set_env(name: str, value: str):
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
    ) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_EXPAND_SZ, value)

def _get_path() -> list[str]:
    raw = _get_env("PATH") or ""
    return [e for e in raw.split(";") if e.strip()]

def _set_path(entries: list[str]):
    _set_env("PATH", ";".join(entries))

def _replace_path(old: str, new: Optional[str]):
    """PATH 中将 old 替换为 new，new 为 None 时仅删除。"""
    entries = _get_path()
    result = []
    replaced = False
    for e in entries:
        if e.lower() == old.lower():
            if new and not replaced:
                result.append(new)
                replaced = True
        else:
            result.append(e)
    if new and not replaced:
        result.append(new)
    _set_path(result)

def _sysdrive() -> str:
    return os.environ.get("SystemDrive", "C:").rstrip("\\").upper()

def _on_sysdrive(p: Path) -> bool:
    return str(p).upper().startswith(_sysdrive())

def _run(*cmd) -> tuple[int, str, str]:
    r = subprocess.run(list(cmd), capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

# ── 文件操作 ───────────────────────────────────────────────────────────────────

def _move(src: Path, dst: Path) -> bool:
    if not src.exists():
        return True
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True
    except Exception as e:
        _err(f"移动失败: {e}")
        return False

def _copy(src: Path, dst: Path) -> bool:
    if not src.exists():
        return True
    try:
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            d = dst / item.name
            try:
                if item.is_dir():
                    shutil.copytree(str(item), str(d), dirs_exist_ok=True)
                else:
                    shutil.copy2(str(item), str(d))
            except Exception as e:
                _warn(f"  跳过 {item.name}: {e}")
        return True
    except Exception as e:
        _err(f"复制失败: {e}")
        return False

# ── 迁移基类 ───────────────────────────────────────────────────────────────────

class Migration(ABC):
    name: str
    description: str
    default_subdir: str  # 在目标根目录下的子文件夹名

    @abstractmethod
    def is_installed(self) -> bool: ...

    @abstractmethod
    def current_path(self) -> Optional[Path]: ...

    def needs_migration(self) -> bool:
        p = self.current_path()
        return p is not None and _on_sysdrive(p)

    @abstractmethod
    def migrate(self, target: Path) -> bool: ...

    def proposed(self, base: Path) -> Path:
        return base / self.default_subdir

# ── 各迁移项 ───────────────────────────────────────────────────────────────────

class Scoop(Migration):
    name = "Scoop"
    description = "Scoop 包管理器根目录（SCOOP 环境变量）"
    default_subdir = "Scoop"

    def is_installed(self) -> bool:
        return bool(shutil.which("scoop") or _get_env("SCOOP"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("SCOOP")
        if p: return Path(p)
        d = Path.home() / "scoop"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if not src or not src.exists():
            _warn("目录不存在，仅更新环境变量")
        else:
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False

        _set_env("SCOOP", str(target))

        old_shims = str(src / "shims") if src else None
        new_shims = str(target / "shims")
        if old_shims:
            _replace_path(old_shims, new_shims)

        # 更新 .shim 文件中的硬编码路径
        shims_dir = target / "shims"
        if shims_dir.exists() and src:
            count = 0
            for f in shims_dir.glob("*.shim"):
                txt = f.read_text(encoding="utf-8", errors="ignore")
                if str(src).lower() in txt.lower():
                    f.write_text(
                        txt.replace(str(src), str(target)), encoding="utf-8"
                    )
                    count += 1
            _info(f"更新了 {count} 个 .shim 文件")
        return True


class PythonUserBase(Migration):
    name = "Python UserBase"
    description = "pip --user 安装目录（PYTHONUSERBASE）"
    default_subdir = "Python"

    def _ver_tag(self) -> str:
        rc, out, _ = _run("python", "-c",
            "import sys; print(f'Python{sys.version_info.major}{sys.version_info.minor}')")
        return out if rc == 0 else "Python3"

    def is_installed(self) -> bool:
        return bool(shutil.which("python"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("PYTHONUSERBASE")
        if p: return Path(p)
        for candidate in [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Python",
            Path(os.environ.get("APPDATA", "")) / "Python",
        ]:
            if candidate.exists():
                return candidate
        return None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        ver = self._ver_tag()

        if src and src.exists() and _on_sysdrive(src):
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False

        _set_env("PYTHONUSERBASE", str(target))

        # 更新 PATH 中的 Scripts 路径
        new_scripts = str(target / ver / "Scripts")
        entries = _get_path()
        old = next(
            (e for e in entries
             if src and e.lower() in [
                 str(src / "bin").lower(),
                 str(src / ver / "Scripts").lower(),
             ]),
            None
        )
        if old:
            _replace_path(old, new_scripts)
        elif new_scripts not in entries:
            entries.append(new_scripts)
            _set_path(entries)
        return True


class NpmPrefix(Migration):
    name = "npm 全局包"
    description = "npm install -g 目录（npm config prefix）"
    default_subdir = "npm"

    def is_installed(self) -> bool:
        return bool(shutil.which("npm"))

    def current_path(self) -> Optional[Path]:
        rc, out, _ = _run("npm", "config", "get", "prefix")
        return Path(out) if rc == 0 and out else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"复制 {src} → {target}")
            if not _copy(src, target):
                return False

        rc, _, err = _run("npm", "config", "set", "prefix", str(target))
        if rc != 0:
            _err(f"npm config set prefix 失败: {err}")
            return False

        old = str(src) if src else None
        if old:
            _replace_path(old, str(target))
        else:
            entries = _get_path()
            if str(target) not in entries:
                entries.append(str(target))
                _set_path(entries)

        if src and src.exists() and src != target:
            try:
                shutil.rmtree(str(src))
                _info(f"已删除旧目录")
            except Exception as e:
                _warn(f"无法删除旧目录: {e}")
        return True


class NpmCache(Migration):
    name = "npm 缓存"
    description = "npm 下载缓存目录（npm config cache）"
    default_subdir = ".npm-cache"

    def is_installed(self) -> bool:
        return bool(shutil.which("npm"))

    def current_path(self) -> Optional[Path]:
        rc, out, _ = _run("npm", "config", "get", "cache")
        return Path(out) if rc == 0 and out else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        rc, _, err = _run("npm", "config", "set", "cache", str(target))
        if rc != 0:
            _err(f"设置失败: {err}")
            return False
        return True


class PipCache(Migration):
    name = "pip 缓存"
    description = "pip 下载缓存目录（pip config cache-dir）"
    default_subdir = ".pip-cache"

    def is_installed(self) -> bool:
        return bool(shutil.which("pip") or shutil.which("python"))

    def current_path(self) -> Optional[Path]:
        rc, out, _ = _run("pip", "config", "get", "global.cache-dir")
        if rc == 0 and out and out != "None":
            return Path(out)
        d = Path(os.environ.get("LOCALAPPDATA", "")) / "pip" / "Cache"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        rc, _, err = _run("pip", "config", "set", "global.cache-dir", str(target))
        if rc != 0:
            _err(f"设置失败: {err}")
            return False
        return True


class Cargo(Migration):
    name = "Cargo"
    description = "Rust Cargo 主目录（CARGO_HOME）"
    default_subdir = "Cargo"

    def is_installed(self) -> bool:
        return bool(shutil.which("cargo") or (Path.home() / ".cargo").exists())

    def current_path(self) -> Optional[Path]:
        p = _get_env("CARGO_HOME") or os.environ.get("CARGO_HOME")
        if p: return Path(p)
        d = Path.home() / ".cargo"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("CARGO_HOME", str(target))
        old_bin = str(src / "bin") if src else None
        new_bin = str(target / "bin")
        if old_bin:
            _replace_path(old_bin, new_bin)
        else:
            entries = _get_path()
            if new_bin not in entries:
                entries.append(new_bin)
                _set_path(entries)
        return True


class GoPath(Migration):
    name = "Go"
    description = "Go 工作目录（GOPATH）"
    default_subdir = "Go"

    def is_installed(self) -> bool:
        return bool(shutil.which("go") or (Path.home() / "go").exists())

    def current_path(self) -> Optional[Path]:
        p = _get_env("GOPATH") or os.environ.get("GOPATH")
        if p: return Path(p)
        d = Path.home() / "go"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("GOPATH", str(target))
        old_bin = str(src / "bin") if src else None
        new_bin = str(target / "bin")
        if old_bin:
            _replace_path(old_bin, new_bin)
        else:
            entries = _get_path()
            if new_bin not in entries:
                entries.append(new_bin)
                _set_path(entries)
        return True


class Gradle(Migration):
    name = "Gradle"
    description = "Gradle 用户主目录（GRADLE_USER_HOME）"
    default_subdir = "Gradle"

    def is_installed(self) -> bool:
        return bool(shutil.which("gradle") or (Path.home() / ".gradle").exists())

    def current_path(self) -> Optional[Path]:
        p = _get_env("GRADLE_USER_HOME") or os.environ.get("GRADLE_USER_HOME")
        if p: return Path(p)
        d = Path.home() / ".gradle"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("GRADLE_USER_HOME", str(target))
        return True


class NuGet(Migration):
    name = "NuGet"
    description = "NuGet 包缓存（NUGET_PACKAGES）"
    default_subdir = "NuGet"

    def is_installed(self) -> bool:
        d = Path.home() / ".nuget" / "packages"
        return bool(shutil.which("nuget") or shutil.which("dotnet") or d.exists())

    def current_path(self) -> Optional[Path]:
        p = _get_env("NUGET_PACKAGES") or os.environ.get("NUGET_PACKAGES")
        if p: return Path(p)
        d = Path.home() / ".nuget" / "packages"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("NUGET_PACKAGES", str(target))
        return True


class Maven(Migration):
    name = "Maven"
    description = "Maven 本地仓库（~/.m2/settings.xml localRepository）"
    default_subdir = "Maven\\repository"

    def is_installed(self) -> bool:
        return bool(shutil.which("mvn") or (Path.home() / ".m2").exists())

    def _read_settings_repo(self) -> Optional[Path]:
        s = Path.home() / ".m2" / "settings.xml"
        if not s.exists():
            return None
        try:
            root = ET.parse(s).getroot()
            ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
            lr = root.find(f"{ns}localRepository")
            if lr is not None and lr.text:
                return Path(lr.text)
        except Exception:
            pass
        return None

    def current_path(self) -> Optional[Path]:
        p = self._read_settings_repo()
        if p: return p
        d = Path.home() / ".m2" / "repository"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False

        settings = Path.home() / ".m2" / "settings.xml"
        settings.parent.mkdir(parents=True, exist_ok=True)
        if settings.exists():
            try:
                tree = ET.parse(settings)
                root = tree.getroot()
                ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
                lr = root.find(f"{ns}localRepository")
                if lr is not None:
                    lr.text = str(target)
                else:
                    ET.SubElement(root, "localRepository").text = str(target)
                ET.indent(tree)
                tree.write(str(settings), xml_declaration=True, encoding="utf-8")
            except Exception as e:
                _err(f"更新 settings.xml 失败: {e}")
                return False
        else:
            settings.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<settings>\n  <localRepository>{target}</localRepository>\n</settings>\n',
                encoding="utf-8",
            )
        return True


class Yarn(Migration):
    name = "Yarn 缓存"
    description = "Yarn 缓存目录（YARN_CACHE_FOLDER）"
    default_subdir = ".yarn-cache"

    def is_installed(self) -> bool:
        return bool(shutil.which("yarn"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("YARN_CACHE_FOLDER")
        if p: return Path(p)
        rc, out, _ = _run("yarn", "cache", "dir")
        return Path(out) if rc == 0 and out else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("YARN_CACHE_FOLDER", str(target))
        return True


class Pnpm(Migration):
    name = "pnpm"
    description = "pnpm 主目录（PNPM_HOME）"
    default_subdir = "pnpm"

    def is_installed(self) -> bool:
        return bool(shutil.which("pnpm"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("PNPM_HOME") or os.environ.get("PNPM_HOME")
        if p: return Path(p)
        rc, out, _ = _run("pnpm", "root", "-g")
        if rc == 0 and out:
            return Path(out).parent
        return None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("PNPM_HOME", str(target))
        old = str(src) if src else None
        if old:
            _replace_path(old, str(target))
        else:
            entries = _get_path()
            if str(target) not in entries:
                entries.append(str(target))
                _set_path(entries)
        return True


class Composer(Migration):
    name = "Composer"
    description = "PHP Composer 主目录（COMPOSER_HOME）"
    default_subdir = "Composer"

    def is_installed(self) -> bool:
        return bool(shutil.which("composer"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("COMPOSER_HOME") or os.environ.get("COMPOSER_HOME")
        if p: return Path(p)
        d = Path(os.environ.get("APPDATA", "")) / "Composer"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("COMPOSER_HOME", str(target))
        return True


class AndroidSdk(Migration):
    name = "Android SDK"
    description = "Android SDK 目录（ANDROID_HOME）"
    default_subdir = "Android\\Sdk"

    def is_installed(self) -> bool:
        for v in ["ANDROID_HOME", "ANDROID_SDK_ROOT"]:
            p = _get_env(v) or os.environ.get(v)
            if p and Path(p).exists():
                return True
        d = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"
        return d.exists()

    def current_path(self) -> Optional[Path]:
        for v in ["ANDROID_HOME", "ANDROID_SDK_ROOT"]:
            p = _get_env(v) or os.environ.get(v)
            if p and Path(p).exists():
                return Path(p)
        d = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("ANDROID_HOME", str(target))
        _set_env("ANDROID_SDK_ROOT", str(target))
        if src:
            _replace_path(str(src / "platform-tools"), str(target / "platform-tools"))
            _replace_path(str(src / "tools"), str(target / "tools"))
        return True


class Chocolatey(Migration):
    name = "Chocolatey"
    description = "Chocolatey 安装目录（ChocolateyInstall）"
    default_subdir = "Chocolatey"

    def is_installed(self) -> bool:
        return bool(shutil.which("choco") or _get_env("ChocolateyInstall"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("ChocolateyInstall") or os.environ.get("ChocolateyInstall")
        if p: return Path(p)
        d = Path("C:/ProgramData/chocolatey")
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target):
                return False
        _set_env("ChocolateyInstall", str(target))
        old_bin = str(src / "bin") if src else None
        if old_bin:
            _replace_path(old_bin, str(target / "bin"))
        return True


# ── 嵌入式 / 树莓派 ────────────────────────────────────────────────────────────

class PlatformIO(Migration):
    name = "PlatformIO"
    description = "PlatformIO 核心目录（PLATFORMIO_CORE_DIR）"
    default_subdir = "PlatformIO"

    def is_installed(self) -> bool:
        return bool(shutil.which("platformio") or shutil.which("pio") or
                    (Path.home() / ".platformio").exists())

    def current_path(self) -> Optional[Path]:
        p = _get_env("PLATFORMIO_CORE_DIR") or os.environ.get("PLATFORMIO_CORE_DIR")
        if p: return Path(p)
        d = Path.home() / ".platformio"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("PLATFORMIO_CORE_DIR", str(target))
        return True


class Arduino(Migration):
    name = "Arduino"
    description = "Arduino 草图/库目录（preferences.txt sketchbook.path）"
    default_subdir = "Arduino"

    def _prefs(self) -> Optional[Path]:
        p = Path(os.environ.get("APPDATA", "")) / "Arduino15" / "preferences.txt"
        return p if p.exists() else None

    def is_installed(self) -> bool:
        return bool(shutil.which("arduino") or shutil.which("arduino-cli") or self._prefs())

    def current_path(self) -> Optional[Path]:
        prefs = self._prefs()
        if prefs:
            for line in prefs.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("sketchbook.path="):
                    return Path(line.split("=", 1)[1].strip())
        d = Path.home() / "Documents" / "Arduino"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        prefs = self._prefs()
        if prefs:
            lines = prefs.read_text(encoding="utf-8", errors="ignore").splitlines()
            updated, found = [], False
            for line in lines:
                if line.startswith("sketchbook.path="):
                    updated.append(f"sketchbook.path={target}")
                    found = True
                else:
                    updated.append(line)
            if not found:
                updated.append(f"sketchbook.path={target}")
            prefs.write_text("\n".join(updated), encoding="utf-8")
        return True


# ── 科学计算 / 数据 ─────────────────────────────────────────────────────────────

class Conda(Migration):
    name = "Conda"
    description = "conda 包/环境目录（.condarc pkgs_dirs / envs_dirs）"
    default_subdir = "conda"

    def is_installed(self) -> bool:
        return bool(shutil.which("conda") or shutil.which("mamba") or
                    shutil.which("micromamba") or (Path.home() / ".conda").exists())

    def current_path(self) -> Optional[Path]:
        d = Path.home() / ".conda"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        for sub in ["pkgs", "envs"]:
            s = src / sub if src else None
            if s and s.exists():
                _info(f"{s} → {target / sub}")
                if not _move(s, target / sub): return False

        condarc = Path.home() / ".condarc"
        lines = []
        if condarc.exists():
            lines = [l for l in condarc.read_text(encoding="utf-8").splitlines()
                     if not l.startswith(("pkgs_dirs", "envs_dirs", "  -"))]
        lines += [
            "pkgs_dirs:", f"  - {target / 'pkgs'}",
            "envs_dirs:", f"  - {target / 'envs'}",
        ]
        condarc.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True


class Julia(Migration):
    name = "Julia"
    description = "Julia 包仓库（JULIA_DEPOT_PATH）"
    default_subdir = "Julia"

    def is_installed(self) -> bool:
        return bool(shutil.which("julia") or (Path.home() / ".julia").exists())

    def current_path(self) -> Optional[Path]:
        p = _get_env("JULIA_DEPOT_PATH") or os.environ.get("JULIA_DEPOT_PATH")
        if p: return Path(p.split(";")[0])
        d = Path.home() / ".julia"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("JULIA_DEPOT_PATH", str(target))
        return True


class RLibs(Migration):
    name = "R 用户库"
    description = "R 用户包目录（R_LIBS_USER）"
    default_subdir = "R\\library"

    def is_installed(self) -> bool:
        return bool(shutil.which("Rscript") or shutil.which("R"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("R_LIBS_USER") or os.environ.get("R_LIBS_USER")
        if p: return Path(p)
        rc, out, _ = _run("Rscript", "-e",
                          "cat(Sys.getenv('R_LIBS_USER', unset=.libPaths()[1]))")
        return Path(out.strip()) if rc == 0 and out.strip() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("R_LIBS_USER", str(target))
        return True


# ── 容器 / 基础设施 ─────────────────────────────────────────────────────────────

class DockerDesktop(Migration):
    name = "Docker Desktop"
    description = "Docker 数据根目录（~/.docker/daemon.json data-root）"
    default_subdir = "Docker"

    def _daemon(self) -> Path:
        return Path.home() / ".docker" / "daemon.json"

    def is_installed(self) -> bool:
        return bool(shutil.which("docker") or self._daemon().exists())

    def current_path(self) -> Optional[Path]:
        import json as _j
        djson = self._daemon()
        if djson.exists():
            try:
                cfg = _j.loads(djson.read_text(encoding="utf-8"))
                if "data-root" in cfg:
                    return Path(cfg["data-root"])
            except Exception:
                pass
        d = Path("C:/ProgramData/Docker")
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        import json as _j
        src = self.current_path()
        if src and src.exists() and _on_sysdrive(src):
            _warn("Docker 数据量可能较大，移动耗时较长")
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        djson = self._daemon()
        djson.parent.mkdir(parents=True, exist_ok=True)
        cfg = {}
        if djson.exists():
            try: cfg = _j.loads(djson.read_text(encoding="utf-8"))
            except Exception: pass
        cfg["data-root"] = str(target)
        djson.write_text(_j.dumps(cfg, indent=2), encoding="utf-8")
        _warn("需要重启 Docker Desktop 生效")
        return True


class Vagrant(Migration):
    name = "Vagrant"
    description = "Vagrant 主目录（VAGRANT_HOME）"
    default_subdir = "Vagrant"

    def is_installed(self) -> bool:
        return bool(shutil.which("vagrant"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("VAGRANT_HOME") or os.environ.get("VAGRANT_HOME")
        if p: return Path(p)
        d = Path.home() / ".vagrant.d"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("VAGRANT_HOME", str(target))
        return True


class Helm(Migration):
    name = "Helm"
    description = "Helm 数据/缓存目录（HELM_DATA_HOME / HELM_CACHE_HOME）"
    default_subdir = "Helm"

    def is_installed(self) -> bool:
        return bool(shutil.which("helm"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("HELM_DATA_HOME") or os.environ.get("HELM_DATA_HOME")
        if p: return Path(p)
        d = Path(os.environ.get("APPDATA", "")) / "helm"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        data_src = self.current_path()
        cp = _get_env("HELM_CACHE_HOME") or os.environ.get("HELM_CACHE_HOME")
        cache_src = Path(cp) if cp else Path(os.environ.get("LOCALAPPDATA", "")) / "helm"

        for s, d in [(data_src, target / "data"), (cache_src, target / "cache")]:
            if s and s.exists() and _on_sysdrive(s):
                _info(f"{s} → {d}")
                if not _move(s, d): return False

        _set_env("HELM_DATA_HOME",  str(target / "data"))
        _set_env("HELM_CACHE_HOME", str(target / "cache"))
        return True


class Terraform(Migration):
    name = "Terraform"
    description = "Terraform 插件缓存（TF_PLUGIN_CACHE_DIR）"
    default_subdir = "Terraform\\plugin-cache"

    def is_installed(self) -> bool:
        return bool(shutil.which("terraform") or shutil.which("tofu"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("TF_PLUGIN_CACHE_DIR") or os.environ.get("TF_PLUGIN_CACHE_DIR")
        if p: return Path(p)
        d = Path(os.environ.get("APPDATA", "")) / "terraform.d" / "plugins"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        target.mkdir(parents=True, exist_ok=True)
        _set_env("TF_PLUGIN_CACHE_DIR", str(target))
        return True


class Krew(Migration):
    name = "Krew (kubectl)"
    description = "kubectl 插件管理器 krew（KREW_ROOT）"
    default_subdir = "krew"

    def is_installed(self) -> bool:
        return bool(shutil.which("kubectl-krew") or (Path.home() / ".krew").exists())

    def current_path(self) -> Optional[Path]:
        p = _get_env("KREW_ROOT") or os.environ.get("KREW_ROOT")
        if p: return Path(p)
        d = Path.home() / ".krew"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("KREW_ROOT", str(target))
        old_bin = str(src / "bin") if src else None
        new_bin = str(target / "bin")
        if old_bin: _replace_path(old_bin, new_bin)
        else:
            entries = _get_path()
            if new_bin not in entries:
                entries.append(new_bin); _set_path(entries)
        return True


# ── 其他运行时 ─────────────────────────────────────────────────────────────────

class RubyGems(Migration):
    name = "Ruby Gems"
    description = "Ruby gem 安装目录（GEM_HOME）"
    default_subdir = "Ruby\\gems"

    def is_installed(self) -> bool:
        return bool(shutil.which("gem") or shutil.which("ruby"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("GEM_HOME") or os.environ.get("GEM_HOME")
        if p: return Path(p)
        rc, out, _ = _run("gem", "environment", "gemdir")
        return Path(out) if rc == 0 and out else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("GEM_HOME", str(target))
        old_bin = str(src / "bin") if src else None
        new_bin = str(target / "bin")
        if old_bin: _replace_path(old_bin, new_bin)
        else:
            entries = _get_path()
            if new_bin not in entries:
                entries.append(new_bin); _set_path(entries)
        return True


class DartPub(Migration):
    name = "Dart / Flutter Pub"
    description = "Dart / Flutter pub 缓存（PUB_CACHE）"
    default_subdir = "pub-cache"

    def is_installed(self) -> bool:
        return bool(shutil.which("dart") or shutil.which("flutter"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("PUB_CACHE") or os.environ.get("PUB_CACHE")
        if p: return Path(p)
        d = Path(os.environ.get("APPDATA", "")) / "Pub" / "Cache"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("PUB_CACHE", str(target))
        old_bin = str(src / "bin") if src else None
        new_bin = str(target / "bin")
        if old_bin: _replace_path(old_bin, new_bin)
        else:
            entries = _get_path()
            if new_bin not in entries:
                entries.append(new_bin); _set_path(entries)
        return True


class Deno(Migration):
    name = "Deno"
    description = "Deno 缓存和模块目录（DENO_DIR）"
    default_subdir = "Deno"

    def is_installed(self) -> bool:
        return bool(shutil.which("deno"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("DENO_DIR") or os.environ.get("DENO_DIR")
        if p: return Path(p)
        d = Path(os.environ.get("LOCALAPPDATA", "")) / "deno"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("DENO_DIR", str(target))
        return True


class Bun(Migration):
    name = "Bun"
    description = "Bun 安装目录（BUN_INSTALL）"
    default_subdir = "bun"

    def is_installed(self) -> bool:
        return bool(shutil.which("bun"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("BUN_INSTALL") or os.environ.get("BUN_INSTALL")
        if p: return Path(p)
        d = Path.home() / ".bun"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("BUN_INSTALL", str(target))
        old_bin = str(src / "bin") if src else None
        new_bin = str(target / "bin")
        if old_bin: _replace_path(old_bin, new_bin)
        else:
            entries = _get_path()
            if new_bin not in entries:
                entries.append(new_bin); _set_path(entries)
        return True


class ElixirMix(Migration):
    name = "Elixir Mix"
    description = "Elixir Mix 主目录（MIX_HOME）"
    default_subdir = "Mix"

    def is_installed(self) -> bool:
        return bool(shutil.which("mix") or shutil.which("elixir"))

    def current_path(self) -> Optional[Path]:
        p = _get_env("MIX_HOME") or os.environ.get("MIX_HOME")
        if p: return Path(p)
        d = Path.home() / ".mix"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        if src and src.exists():
            _info(f"{src} → {target}")
            if not _move(src, target): return False
        _set_env("MIX_HOME", str(target))
        return True


class GHCup(Migration):
    name = "GHCup (Haskell)"
    description = "GHCup Haskell 工具链（GHCUP_INSTALL_BASE_PREFIX）"
    default_subdir = "ghcup"

    def is_installed(self) -> bool:
        return bool(shutil.which("ghcup") or (Path.home() / ".ghcup").exists())

    def current_path(self) -> Optional[Path]:
        p = _get_env("GHCUP_INSTALL_BASE_PREFIX") or os.environ.get("GHCUP_INSTALL_BASE_PREFIX")
        if p: return Path(p) / ".ghcup"
        d = Path.home() / ".ghcup"
        return d if d.exists() else None

    def migrate(self, target: Path) -> bool:
        src = self.current_path()
        actual_dst = target / ".ghcup"
        if src and src.exists():
            _info(f"{src} → {actual_dst}")
            if not _move(src, actual_dst): return False
        _set_env("GHCUP_INSTALL_BASE_PREFIX", str(target))
        old_bin = str(src / "bin") if src else None
        if old_bin: _replace_path(old_bin, str(actual_dst / "bin"))
        return True


# ── 全部迁移项 ─────────────────────────────────────────────────────────────────

ALL: list[Migration] = [
    # 包管理器
    Scoop(),
    Chocolatey(),
    # Python
    PythonUserBase(),
    PipCache(),
    Conda(),
    # Node.js 生态
    NpmPrefix(),
    NpmCache(),
    Yarn(),
    Pnpm(),
    Bun(),
    Deno(),
    # JVM
    Gradle(),
    Maven(),
    NuGet(),
    # 其他语言
    Cargo(),
    GoPath(),
    Julia(),
    RLibs(),
    RubyGems(),
    DartPub(),
    ElixirMix(),
    GHCup(),
    Composer(),
    # 嵌入式 / 硬件
    PlatformIO(),
    Arduino(),
    # 容器 / 云原生
    DockerDesktop(),
    Vagrant(),
    Helm(),
    Terraform(),
    Krew(),
    # 移动
    AndroidSdk(),
]

# ── UI screens ────────────────────────────────────────────────────────────────

def _lang_select() -> str:
    global _lang
    opts = [("en", "English"), ("zh", "中文"), ("ja", "日本語")]
    cur = 0
    while True:
        _clear()
        _print_banner()
        print(f"  {BOLD}Select Language / 选择语言 / 言語選択{R}\n")
        for i, (_, label) in enumerate(opts):
            arrow = f"{YEL}>{R}" if i == cur else " "
            hl = BOLD if i == cur else DIM
            print(f"    {arrow}  {hl}{label}{R}")
        print(f"\n  {DIM}↑↓  Navigate     Enter  Select{R}")
        k = _get_key()
        if   k == "UP":    cur = (cur - 1) % 3
        elif k == "DOWN":  cur = (cur + 1) % 3
        elif k == "ENTER":
            _lang = opts[cur][0]
            return _lang


def _target_input() -> Optional[Path]:
    sys_d = _sysdrive()[0]
    drives = [f"{d}:\\" for d in _string.ascii_uppercase
              if d != sys_d and Path(f"{d}:\\").exists()]
    msg = ""
    while True:
        _clear()
        _print_banner()
        print(f"  {BOLD}{CYN}{t('target_title')}{R}\n")
        if drives:
            print(f"  {t('avail_drives')}: {DIM}{' / '.join(drives)}{R}\n")
        print(f"  {DIM}{t('hint_input')}{R}\n")
        if msg:
            print(f"  {YEL}⚠{R}  {msg}\n")
            msg = ""
        print(f"  {YEL}▶{R} ", end="", flush=True)
        ans = input().strip()
        if ans.lower() == "b":
            return None
        if not ans:
            msg = t("empty_warn"); continue
        base = Path(ans)
        if base.drive.upper().rstrip(":\\") == sys_d:
            msg = t("sysdrive_warn"); continue
        return base


def _checkbox_select(candidates: list) -> Optional[list[int]]:
    n = len(candidates)
    selected = [False] * n
    cur = 0
    msg = ""
    while True:
        _clear()
        _print_banner()
        print(f"  {BOLD}{CYN}{t('select_title')}{R}\n")
        for i, (m, p) in enumerate(candidates):
            mark  = f"{GRN}*{R}" if selected[i] else " "
            arrow = f"{YEL}>{R}" if i == cur else " "
            hl    = BOLD if i == cur else DIM
            print(f"  {arrow} [{mark}] {hl}{m.name:<20}{R}  {DIM}{p}{R}")
        print(f"\n  {DIM}{t('hint_nav')}{R}")
        if msg:
            print(f"\n  {YEL}⚠{R}  {msg}")
            msg = ""
        k = _get_key()
        if   k == "UP":    cur = (cur - 1) % n
        elif k == "DOWN":  cur = (cur + 1) % n
        elif k == "SPACE": selected[cur] = not selected[cur]
        elif k == "a":
            v = not all(selected); selected = [v] * n
        elif k == "ENTER":
            result = [i for i, s in enumerate(selected) if s]
            if not result: msg = t("none_sel")
            else: return result
        elif k in ("b", "ESC"):
            return None


def _confirm_targets(candidates: list, indices: list[int], base: Path) -> Optional[dict]:
    targets: dict[str, Path] = {}
    _clear()
    _print_banner()
    print(f"  {BOLD}{CYN}{t('confirm_title')}{R}\n")
    for i in indices:
        m, cur_p = candidates[i]
        proposed = m.proposed(base)
        print(f"  {BOLD}{m.name}{R}")
        print(f"    {DIM}{t('frm')}:{R} {cur_p}")
        print(f"    {DIM}{t('to')}:{R}  {CYN}{proposed}{R}")
        print(f"    {DIM}{t('override_hint')}{R}")
        print(f"    {YEL}▶{R} ", end="", flush=True)
        ans = input().strip()
        if ans.lower() == "b":
            return None
        targets[m.name] = Path(ans) if ans else proposed
        print()
    return targets


# ── Scan & main ───────────────────────────────────────────────────────────────

def scan() -> list[tuple[Migration, Path]]:
    results = []
    for m in ALL:
        try:
            if m.is_installed():
                p = m.current_path()
                if p and _on_sysdrive(p):
                    results.append((m, p))
        except Exception:
            pass
    return results


def main():
    global _lang

    # ── Step 1: Language ──────────────────────────────────────────────────────
    _lang_select()

    while True:
        # ── Step 2: Target directory ──────────────────────────────────────────
        base = _target_input()
        if base is None:          # Back → language
            _lang_select()
            continue

        # ── Step 3: Scan ──────────────────────────────────────────────────────
        _clear()
        _print_banner()
        print(f"  {DIM}Scanning...{R}\n")
        candidates = scan()

        if not candidates:
            _clear()
            _print_banner()
            _ok(t("no_items"))
            print(f"\n  {DIM}{t('press_any')}{R}")
            msvcrt.getwch()
            return

        while True:
            # ── Step 4: Checkbox select ───────────────────────────────────────
            indices = _checkbox_select(candidates)
            if indices is None:   # Back → target input
                break

            while True:
                # ── Step 5: Confirm paths ─────────────────────────────────────
                targets = _confirm_targets(candidates, indices, base)
                if targets is None:   # Back → checkbox select
                    break

                # ── Step 6: Execute ───────────────────────────────────────────
                _clear()
                _print_banner()
                print(f"  {BOLD}{CYN}{t('exec_title')}...{R}\n")
                results: dict[str, bool] = {}
                for i in indices:
                    m, _ = candidates[i]
                    if m.name not in targets:
                        continue
                    print(f"\n  {BOLD}▶ {m.name}{R}")
                    try:
                        ok = m.migrate(targets[m.name])
                        results[m.name] = ok
                        (_ok if ok else _err)(t("success") if ok else t("failed"))
                    except Exception as e:
                        _err(f"{t('failed')}: {e}")
                        results[m.name] = False

                # ── Step 7: Summary ───────────────────────────────────────────
                _clear()
                _print_banner()
                print(f"  {BOLD}{CYN}{t('done_title')}{R}\n")
                ok_l   = [k for k, v in results.items() if     v]
                fail_l = [k for k, v in results.items() if not v]
                if ok_l:   _ok(f"{t('success')}: {', '.join(ok_l)}")
                if fail_l: _err(f"{t('failed')}: {', '.join(fail_l)}")
                print(f"\n  {YEL}⚠{R}  {t('restart_hint')}\n")
                print(f"  {DIM}{t('press_any')}{R}")
                msvcrt.getwch()
                return


if __name__ == "__main__":
    main()
