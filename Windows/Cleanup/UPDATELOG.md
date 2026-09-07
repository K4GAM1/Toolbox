# updatelog

## further task
- Add more application cache.

## v1.04
- Fixed CJK text becoming garbled in a fresh console window on non-UTF-8 system locales (e.g. Japanese cp932) by explicitly setting the console code page to UTF-8 (`SetConsoleOutputCP`/`SetConsoleCP`)
- Added an optional Textual-based TUI (`cleaner_tui.py`): dock with category checkboxes, live scan/execute log, results table, light/dark theme toggle (Nord-based palette), language switch. Auto-launches when `cleaner.py` is run with no arguments in an interactive terminal; falls back to the existing keypress menu if `textual` isn't installed or the session isn't interactive — `--cache`/`-x`/etc. always use the non-interactive CLI path regardless
- Added a PowerShell port (`cleaner.ps1`) with the same six categories, welcome/post-cleanup screens and console-menu flow as `cleaner.py`, for machines without Python
- Added a prebuilt onedir Windows package (`cleaner-1.04-win64.zip`) for convenience; PyInstaller executables can trigger antivirus false positives (ML heuristics — confirmed hit `Trojan:Win32/Bearfoos.B!ml` on Defender during testing), so `start.bat` (running from source) remains the primary recommended way to use this tool

## v1.03
- Fixed a crash on Python 3.9 (`X | None` union syntax needs 3.10+) by adding `from __future__ import annotations`
- Added a new system-level category (`--system`): Windows Temp, Windows Update download cache (`SoftwareDistribution\Download`), and Recycle Bin (via `SHEmptyRecycleBinW`)
- Added Calibre cache, a generic `*-updater` glob for Electron/Squirrel auto-updater staging folders, extra VS Code/Cursor/Discord cache subfolders, and Tencent `QQTempSys`/`Logs` to the cache and log categories
- Added `CrashFiles` (game crash dumps) to the crash-dump scan list

## v1.02
- Added post-cleanup summary screen showing total freed space and deleted item count
- Added option to return to main menu or exit after cleanup completes
- Pressing `[q]` in any menu now clears the screen and closes the terminal window
- Fixed operation flow: execution progress is cleared before displaying the results table

## v1.01
- Redesigned the welcome screen with ASCII art and rainbow coloring
- Fixed UI display logic for menu rendering and in-place redraws

## Pre-release
- Fixed an issue where recursive empty folder scanning would incorrectly remove Quick Access entries and other user-specific configuration directories under AppData
