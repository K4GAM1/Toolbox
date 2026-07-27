# updatelog

## v1.05
- Fixed black screen / taskbar not appearing on some machines after restarting Explorer: the v1.03 approach (graceful-exit message + launching explorer.exe as a Python subprocess) left Explorer as a child process, which corrupted shell registration on some setups. Now force-kills and relaunches via `cmd /c start "" explorer.exe` so Explorer runs as a fully independent top-level process
- Language selector changed from a cycling button to a dropdown list (Combobox): it now shows the current language (English / 日本語 / 中文) and lets you pick any language directly instead of clicking through them

## v1.04
- Fixed start.bat not launching the GUI on double-click: the file had Unix LF line endings, but cmd batch files require CRLF — LF mangles goto/labels/multi-line if-blocks, so the script silently failed. Converted to CRLF (and the launcher is now pure ASCII to avoid any encoding issues)
- Fixed start.bat still referencing cleaner.py (copied from the Cleanup tool) — now checks for and launches ctxmenu.py
- Fixed broken script structure: added the missing :quit label and removed dead code after an orphaned `goto end` (the pythonw launch added in v1.03 was unreachable, which is why that change never actually took effect)
- start.bat now genuinely launches via pythonw, so no console window lingers while the GUI is open; the Python auto-detect/install fallback (winget → download → website) is preserved

## v1.03
- Fixed taskbar occasionally not reappearing after restarting Explorer: now sends the graceful exit message (equivalent to Ctrl+Shift+right-click taskbar → Exit Explorer) instead of force-killing, waits for shutdown, and only launches a new Explorer if the system didn't auto-restart it (the old force-kill raced against auto-restart)
- Tray icons of apps that don't listen for taskbar re-creation (e.g. Spotify) may still vanish after a restart — this is an app-side limitation; the restart confirmation dialog and Help now explain it
- Added Japanese UI; language now cycles EN → 日本語 → 中文 and defaults to English
- Window title / top logo now follows the Windows display language (fixed, independent of the UI language toggle)
- Added Help window explaining commands vs extensions, how disabling works, the Win11 classic menu, %1/%V, and source/system-item filtering
- Removed the "Standard User" badge — third-party menu management never needs admin; a badge is shown only when running elevated (with a status-bar note)

## v1.02
- Added "Source" column: each item now shows the owning software, resolved from the handler DLL/EXE version info (command → DelegateExecute → ExplorerCommandHandler → DropTarget → MUIVerb chain)
- System items (Windows directory or Microsoft-signed) are now hidden by default; "Show system items" checkbox to reveal them
- Disabling items registered via ExplorerCommandHandler (Win11 new-menu entries, e.g. Baidu NetDisk) now actually works: their CLSID is added to the per-user Blocked list in addition to LegacyDisable
- Fixed shellex handlers whose default value is a description instead of a CLSID (Taskband Pin / Start Menu Pin) showing as raw GUIDs
- MUIVerb-based items (e.g. UpdateEncryptionSettingsWork) now show their real display name
- Added "Run hidden" option for custom menu items — wraps the command with a wscript VBS helper so bat/cmd scripts run without flashing a console window; auto-checked when browsing to a script
- Browsing to a .ps1 now generates a proper `powershell -File` command (plain .ps1 would open in Notepad)
- Custom items applied to Desktop/Background now auto-substitute %1 → %V (%1 is never filled on background clicks, which silently broke the command)

## v1.01
- Fixed changes appearing to have no effect on Windows 11: added a banner explaining that classic-menu items live under "Show more options", plus a one-click "Enable Classic Menu" toggle (per-user registry tweak, reversible)
- Added "Restart Explorer" button; extension (shellex) enable/disable/delete now hints that an Explorer restart is required to take effect
- Fixed delete falsely reporting success when only the per-user override key was removed while the system-level (HKLM) entry remained — now reports failure honestly when admin rights are needed
- Deleting an extension now also cleans up its CLSID from the Blocked list
- Display names like `@shell32.dll,-8506` are now resolved to readable text (SHLoadIndirectString); accelerator `&` markers stripped
- Enabled per-monitor DPI awareness — UI is no longer blurry on high-DPI screens
- Status message no longer overwritten immediately after deletion

## v1.00
- Initial release: view / enable / disable / delete context-menu items for files, folders and desktop background (shell commands + shellex extensions); add custom menu entries; bilingual UI (中/EN)
