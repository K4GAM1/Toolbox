# updatelog

## Pre-release
- Initial tool: recursively reset directory ownership to the current user after a drive/account migration — fixes git "dubious ownership" caused by stale account SIDs left on D:/E: folders
- Uses `icacls /setowner /T /C /L /Q`; auto-elevates via UAC; `-DryRun` to preview without changes; defaults to the D:/E: data folders
