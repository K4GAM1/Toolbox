# updatelog

## further task
- Verify the `unix` target branch end to end against a real macOS/Linux box (only the `windows-admin` branch has been tested against a live target so far).
- Consider a `-DryRun` switch to preview what would change on the target before touching it.

## v1.0
- Initial tool: bootstraps passwordless SSH from this machine to a new target device, the same way HAKUTO -> Mac(eeast) and HAKUTO -> beast were set up by hand.
- Generates a local ed25519 (+ rsa, for SSHFS-Win) keypair if missing; probes the target with key auth first so re-running against an already-configured target is a safe no-op.
- Supports three target account types: `windows-admin` (administrators_authorized_keys, ACL locked to Administrators+SYSTEM only -- mixing in any other account silently breaks all pubkey auth), `windows-user` (per-user authorized_keys, does not touch sshd/firewall since a non-admin session cannot), and `unix` (~/.ssh/authorized_keys).
- Adds a Host block to ~\.ssh\config so `ssh <alias>` works afterwards; skips if the alias already exists.
- Optional `-Mount` installs WinFsp + SSHFS-Win via winget if missing and maps a persistent network drive to the target.
- Ships the remote provisioning script to the target via `scp` + `-File` rather than piping it over ssh stdin: `powershell -Command -` was found to silently mangle multi-line constructs like a multi-line `@( ... )` array literal (near-REPL stdin semantics rather than a real script parse) -- burned about an hour chasing a "no error, no output" failure before finding this.
