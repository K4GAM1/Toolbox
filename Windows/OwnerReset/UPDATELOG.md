# updatelog

## v1.0
- Now repairs **write permissions**, not just ownership: adds an inheritable `Modify`
  grant for the current user (`icacls /grant (OI)(CI)(M)`) alongside the owner reset.
  Fixes installers failing with "Error opening file for writing" on migrated folders
  (e.g. Tuta / electron-builder) where the owner was already correct but `Users` had
  only read-and-execute. Owner and write-permission are separate problems — resetting
  the owner does NOT grant write, so both are now handled.
- New `-Drive D:` mode enumerates every top-level folder on a drive and auto-skips
  system-managed ones ($RECYCLE.BIN, System Volume Information, WindowsApps, WpSystem,
  Program Files(/x86), ProgramData, Config.Msi, Recovery, ...) plus junctions/symlinks.
- New `-NoRecurse` fast mode (root only): the write grant still covers the whole tree
  via ACL inheritance, while the owner is cleared at the root. For folders with huge
  file counts (installed-software libraries, large game dirs) where `/T` is slow.
- New `-RemoveStaleAces`: strips unresolvable old-account ACEs from the DACL by SID.
- New `-GrantTo` picks the grantee (defaults to the owner); `-SkipGrant` keeps the
  old owner-only behavior.
- **Fixed a pre-existing elevation bug**: forwarding multiple paths to the UAC-elevated
  relaunch used repeated `-Path` under `-File`, which errors ("specified more than
  once"); a comma array under `-File` silently kept only the first path. The relaunch
  now uses `-EncodedCommand`, rebuilding the target array safely regardless of spaces
  or quotes in the paths.
- DryRun now reports, per folder: owner (flagging stale accounts), a real write test,
  and any stale ACEs — no admin needed.

## Pre-release
- Initial tool: recursively reset directory ownership to the current user after a drive/account migration — fixes git "dubious ownership" caused by stale account SIDs left on D:/E: folders
- Uses `icacls /setowner /T /C /L /Q`; auto-elevates via UAC; `-DryRun` to preview without changes; defaults to the D:/E: data folders
