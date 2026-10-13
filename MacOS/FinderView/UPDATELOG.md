# updatelog

## v1.0
- Existing state recorded as the first version; no earlier history was kept
- Interactive menu tool for Finder view settings: icon size, grid spacing, text size, label position, icon preview, arrange-by
- Writes with `plutil -replace -xml` and explicit types, never `defaults write`. The old plist dictionary syntax stores numbers as `<string>`, which makes Finder silently fall back to minimum values while `defaults read` keeps printing the expected numbers — the failure is invisible from the command line
- Writes `FK_StandardViewSettings` alongside `StandardViewSettings`, and scans every top-level key containing `IconViewSettings`, so virtual locations (Computer, Network, Trash, SearchRecents) are covered as well. Those have no real directory and therefore no .DS_Store
- `--clean-dsstore` removes per-folder overrides in the only order that works: close windows, quit Finder, delete, relaunch. Finder writes window state back to .DS_Store on exit, so skipping a step undoes the deletion
- Serves as the reference implementation for the Toolbox interactive-menu conventions documented in 脚本编写手册.md
