# updatelog

## further task
- Add a `-WhatIf` pass; the delete is destructive and there is currently no preview.

## v1.0
- Removes the Microsoft Store package volume Windows auto-creates on a data drive, then seizes ownership of and force-deletes the `Program Files`, `WindowsApps` and `WpSystem` folders it leaves behind, and reports whether each is actually gone.
- The target drive is a validated parameter (`-Drive`, default `D:`) instead of a hard-coded letter -- this takes ownership and recursively force-deletes, so running it against the wrong drive is not recoverable.
- Kept as its own tool rather than folded into Cleanup: Cleanup clears caches, this changes ACLs and deletes system-created directories, and burying that in a category list invites accidents.
