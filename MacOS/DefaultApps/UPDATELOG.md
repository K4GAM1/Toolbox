# updatelog

## v1.0
- Existing state recorded as the first version; no earlier history was kept
- Batch and interactive tool for setting the default application per file type, writing through Launch Services
- Uses Swift `NSWorkspace.setDefaultApplication(at:toOpen:)` rather than `duti`: on macOS 26 Tahoe duti fails with error -50 for dynamic UTIs, i.e. extensions no application has ever declared (.env, .toml, .svelte). Falls back to the older `LSSetDefaultRoleHandlerForContentType` for system-protected types (sh/bash/zsh, .caf, .patch)
- The Swift helper is embedded in the script and compiled on first run to `~/.cache/default-apps/lsdefault`; requires the Xcode command line tools (swiftc)
- Clearing a default is not possible through the API — it can only set. Removing one means deleting the LSHandlers entry from secure.plist and running `killall lsd`
- Any direct edit of secure.plist needs `killall lsd` to take effect; `killall Finder` alone does nothing, because Finder reads lsd's in-memory cache
