# updatelog

## further task
- Add more application cache.

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
