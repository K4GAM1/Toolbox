<#
.SYNOPSIS
  Bootstraps passwordless SSH from this machine to a new target device (Windows or
  Unix), the same way HAKUTO -> Mac(eeast) and HAKUTO -> beast were set up by hand.

.DESCRIPTION
  - Generates a local ed25519 (+ rsa, needed for SSHFS-Win ".k" mode) keypair if
    one does not already exist.
  - Probes the target with key auth first; if it already works, skips straight to
    reporting success (safe to re-run against an already-configured target).
  - Otherwise pushes the public key(s) to the target's authorized_keys the right
    way for the target's account type:
      windows-admin : C:\ProgramData\ssh\administrators_authorized_keys, ACL locked
                       to ONLY Administrators + SYSTEM. Mixing in any other account
                       (even the target user itself) makes Windows sshd silently
                       reject ALL pubkey auth with no useful error -- this bit
                       everyone the first few times, see UPDATELOG.
      windows-user  : per-user ~\.ssh\authorized_keys (sshd/firewall must already
                       be set up by an admin; a non-admin session cannot do that).
      unix          : ~/.ssh/authorized_keys (created/chmod'd if missing).
  - Adds a Host block to ~\.ssh\config so `ssh <alias>` just works afterwards.
  - Optionally (-Mount) installs WinFsp + SSHFS-Win via winget if missing, and maps
    a persistent network drive to the target over SFTP.

.PARAMETER TargetHost
  IP address or hostname of the target device.

.PARAMETER TargetUser
  Username to log into the target with. You will be prompted for its password
  (ssh's own prompt) unless key auth already works -- once for a unix target,
  twice for a windows-admin/windows-user target (scp + ssh are separate
  connections; tried collapsing this via ControlMaster but Windows' bundled
  OpenSSH client doesn't support it reliably, see Invoke-RemotePowerShellFile).

.PARAMETER TargetOS
  'windows-admin', 'windows-user', or 'unix'.

.PARAMETER Alias
  Short name for ~\.ssh\config (`ssh <alias>`). Defaults to TargetHost.

.PARAMETER Mount
  Also map a persistent SSHFS-Win drive to the target.

.PARAMETER MountDrive
  Drive letter to use with -Mount, e.g. "N:". Auto-picks the next free letter if
  omitted.

.EXAMPLE
  .\Register-SSHDevice.ps1 -TargetHost 100.102.232.72 -TargetUser home -TargetOS windows-admin -Alias beast -Mount

.EXAMPLE
  .\Register-SSHDevice.ps1 -TargetHost 100.105.26.53 -TargetUser max -TargetOS unix -Alias mac
#>

[CmdletBinding()]
param(
    [string]$TargetHost,
    [string]$TargetUser,
    [ValidateSet('windows-admin', 'windows-user', 'unix')]
    [string]$TargetOS,
    [string]$Alias,
    [switch]$Mount,
    [string]$MountDrive
)

$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Text)
    Write-Host "    [OK] $Text" -ForegroundColor Green
}

function Write-Warn2 {
    param([string]$Text)
    Write-Host "    [!] $Text" -ForegroundColor Yellow
}

function Invoke-RemotePowerShellFile {
    # `powershell -Command -` (script piped over ssh stdin) silently mangles
    # multi-line constructs like a `@( ... )` array literal spanning lines --
    # it appears to consume stdin closer to line-by-line REPL semantics than a
    # real script parse. Writing the script to a temp file and running it with
    # -File sidesteps that entirely, at the cost of one extra scp round trip.
    param(
        [string]$RemoteScript,
        [string]$TargetUser,
        [string]$TargetHost
    )
    # NOTE: scp + ssh below are two separate connections, so on a windows-*
    # target the target's password gets asked twice (once per connection) --
    # tried collapsing this into one prompt via ssh ControlMaster/ControlPath,
    # but Windows' bundled OpenSSH client fails on it ("getsockname failed:
    # Not a socket" -- a known Win32-OpenSSH limitation with AF_UNIX control
    # sockets). Not fixable from here; left as two prompts.
    $localTemp = New-TemporaryFile
    $remoteName = "ssh-bootstrap-$([guid]::NewGuid().ToString('N').Substring(0,8)).ps1"
    try {
        Set-Content -Path $localTemp -Value $RemoteScript -Encoding ascii -NoNewline
        # destination has no path prefix so it lands in the target's own
        # SFTP-default (home) directory, regardless of what that path actually is
        & scp -o StrictHostKeyChecking=accept-new $localTemp "${TargetUser}@${TargetHost}:$remoteName"
        if ($LASTEXITCODE -ne 0) { throw "scp of provisioning script failed" }
        # `del` always running after the script (regardless of its exit code) is
        # the point, but plain cmd `&` chaining would otherwise leave the *del*
        # exit code as what ssh reports back -- stash and re-exit the real one.
        & ssh "${TargetUser}@${TargetHost}" "powershell -NoProfile -ExecutionPolicy Bypass -File $remoteName & set RC=%ERRORLEVEL% & del $remoteName & exit /b %RC%"
        return $LASTEXITCODE
    } finally {
        Remove-Item $localTemp -Force -ErrorAction SilentlyContinue
    }
}

# ---------- interactive fallback for missing params ----------

if (-not $TargetHost) { $TargetHost = Read-Host "Target host (IP or hostname)" }
if (-not $TargetUser) { $TargetUser = Read-Host "Target username" }
if (-not $TargetOS) {
    Write-Host "Target OS / account type:"
    Write-Host "  1) windows-admin  (Windows, target account is a local administrator)"
    Write-Host "  2) windows-user   (Windows, target account is NOT an administrator)"
    Write-Host "  3) unix           (macOS / Linux)"
    $choice = Read-Host "Choose 1/2/3"
    $TargetOS = switch ($choice) {
        '1' { 'windows-admin' }
        '2' { 'windows-user' }
        '3' { 'unix' }
        default { throw "Invalid choice: $choice" }
    }
}
if (-not $Alias) { $Alias = $TargetHost }

Write-Host ""
Write-Host "Registering SSH device" -ForegroundColor White
Write-Host "  Target : $TargetUser@$TargetHost ($TargetOS)"
Write-Host "  Alias  : $Alias"
Write-Host "  Mount  : $($Mount.IsPresent)"

# ---------- local keypair ----------

Write-Step "Checking local SSH keypair"

$sshDir = Join-Path $HOME ".ssh"
if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
}

$ed25519Priv = Join-Path $sshDir "id_ed25519"
$rsaPriv     = Join-Path $sshDir "id_rsa"

if (-not (Test-Path $ed25519Priv)) {
    Write-Warn2 "No id_ed25519 found, generating one"
    ssh-keygen -t ed25519 -N '""' -f $ed25519Priv -C "$env:USERNAME@$env:COMPUTERNAME" | Out-Null
} else {
    Write-Ok "id_ed25519 exists"
}

# rsa key is only needed for SSHFS-Win's ".k" alias (IdentitiesOnly, rsa-only), but
# it is cheap to have around and several of these setups end up wanting -Mount later.
if (-not (Test-Path $rsaPriv)) {
    Write-Warn2 "No id_rsa found, generating one (needed later if you ever use -Mount)"
    ssh-keygen -t rsa -b 4096 -N '""' -f $rsaPriv -C "$env:USERNAME@$env:COMPUTERNAME" | Out-Null
} else {
    Write-Ok "id_rsa exists"
}

$pubKeys = @(
    (Get-Content "$ed25519Priv.pub" -Raw).Trim()
    (Get-Content "$rsaPriv.pub" -Raw).Trim()
)

# ---------- probe: is key auth already working? ----------

Write-Step "Probing target for existing key auth"

$probeArgs = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', "$TargetUser@$TargetHost", 'echo PROBE_OK')
$probeOutput = & ssh @probeArgs 2>$null
$alreadyTrusted = ($LASTEXITCODE -eq 0) -and ($probeOutput -match 'PROBE_OK')

if ($alreadyTrusted) {
    Write-Ok "Key auth already works, skipping provisioning"
} else {
    Write-Warn2 "Key auth not set up yet, will provision now (you'll be asked for the target's password)"

    switch ($TargetOS) {
        'windows-admin' {
            $remoteScript = @"
`$ErrorActionPreference = 'Continue'
`$keys = @(
$(($pubKeys | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join "`n")
)
`$path = 'C:\ProgramData\ssh\administrators_authorized_keys'
`$dir = Split-Path `$path
if (!(Test-Path `$dir)) { New-Item -ItemType Directory -Force -Path `$dir | Out-Null }
if (!(Test-Path `$path)) { New-Item -ItemType File -Path `$path -Force | Out-Null }
`$existing = @(Get-Content `$path -ErrorAction SilentlyContinue)
foreach (`$k in `$keys) {
    if (`$existing -notcontains `$k) { Add-Content -Path `$path -Value `$k }
}
icacls `$path /inheritance:r | Out-Null
icacls `$path /grant:r Administrators:F | Out-Null
icacls `$path /grant:r SYSTEM:F | Out-Null
`$svc = Get-Service sshd -ErrorAction SilentlyContinue
if (-not `$svc) {
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
    `$svc = Get-Service sshd -ErrorAction SilentlyContinue
}
if (`$svc) {
    Set-Service -Name sshd -StartupType Automatic
    if (`$svc.Status -ne 'Running') { Start-Service sshd }
}
`$fw = Get-NetFirewallRule -DisplayName '*OpenSSH*' -ErrorAction SilentlyContinue
if (-not `$fw) {
    New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH SSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
}
Write-Output 'PROVISION_OK'
"@
            Invoke-RemotePowerShellFile -RemoteScript $remoteScript -TargetUser $TargetUser -TargetHost $TargetHost
        }

        'windows-user' {
            $remoteScript = @"
`$ErrorActionPreference = 'Continue'
`$keys = @(
$(($pubKeys | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join "`n")
)
`$sshDir = Join-Path `$env:USERPROFILE '.ssh'
if (!(Test-Path `$sshDir)) { New-Item -ItemType Directory -Force -Path `$sshDir | Out-Null }
`$path = Join-Path `$sshDir 'authorized_keys'
if (!(Test-Path `$path)) { New-Item -ItemType File -Path `$path -Force | Out-Null }
`$existing = @(Get-Content `$path -ErrorAction SilentlyContinue)
foreach (`$k in `$keys) {
    if (`$existing -notcontains `$k) { Add-Content -Path `$path -Value `$k }
}
try {
    icacls `$path /inheritance:r | Out-Null
    icacls `$path /grant:r "`${env:USERNAME}:F" | Out-Null
    icacls `$path /grant:r SYSTEM:F | Out-Null
} catch { Write-Output "[!] Could not lock ACL: `$_" }
Write-Output 'PROVISION_OK'
Write-Output '[!] This account is not an administrator: sshd/firewall setup was NOT touched.'
Write-Output '[!] Make sure sshd is already installed, running, and reachable (set up by an admin account).'
"@
            Invoke-RemotePowerShellFile -RemoteScript $remoteScript -TargetUser $TargetUser -TargetHost $TargetHost
        }

        'unix' {
            $remoteScript = @"
set -e
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
while IFS= read -r key; do
    [ -z "`$key" ] && continue
    grep -qxF "`$key" ~/.ssh/authorized_keys || echo "`$key" >> ~/.ssh/authorized_keys
done <<'PUBKEYS'
$($pubKeys -join "`n")
PUBKEYS
echo PROVISION_OK
"@
            $remoteScript | & ssh -o StrictHostKeyChecking=accept-new "$TargetUser@$TargetHost" "bash -s"
        }
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Remote provisioning failed (exit $LASTEXITCODE). See output above."
    }

    # re-probe to confirm
    $probeOutput2 = & ssh @probeArgs 2>$null
    if (($LASTEXITCODE -eq 0) -and ($probeOutput2 -match 'PROBE_OK')) {
        Write-Ok "Key auth verified working"
    } else {
        throw "Provisioning ran but key auth still does not work. Check the output above."
    }
}

# ---------- ssh config alias ----------

Write-Step "Updating $sshDir\config"

$configPath = Join-Path $sshDir "config"
if (-not (Test-Path $configPath)) {
    New-Item -ItemType File -Path $configPath -Force | Out-Null
}
$configContent = Get-Content $configPath -Raw -ErrorAction SilentlyContinue
if ($null -eq $configContent) { $configContent = "" }

if ($configContent -match "(?m)^Host\s+$([regex]::Escape($Alias))\s*`$") {
    Write-Warn2 "Host '$Alias' already exists in ssh config, leaving it as-is"
} else {
    $block = @"

Host $Alias
    HostName $TargetHost
    User $TargetUser
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
"@
    Add-Content -Path $configPath -Value $block
    Write-Ok "Added 'Host $Alias' block"
}

# ---------- optional SSHFS-Win mount ----------

if ($Mount) {
    Write-Step "Setting up SSHFS-Win mount"

    $sshfsInstalled = Test-Path "$env:ProgramFiles\SSHFS-Win"
    if (-not $sshfsInstalled) {
        Write-Warn2 "WinFsp / SSHFS-Win not found, installing via winget"
        winget install --id WinFsp.WinFsp -e --accept-package-agreements --accept-source-agreements
        winget install --id SSHFS-Win.SSHFS-Win -e --accept-package-agreements --accept-source-agreements
    } else {
        Write-Ok "WinFsp / SSHFS-Win already installed"
    }

    if (-not $MountDrive) {
        $used = (Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Name)
        $free = 68..90 | ForEach-Object { [char]$_ } | Where-Object { $used -notcontains $_ } | Select-Object -First 1
        if (-not $free) { throw "No free drive letters available for -Mount" }
        $MountDrive = "$($free):"
    }

    Write-Host "    Mounting $MountDrive -> \\sshfs.k\$TargetUser@$TargetHost (persistent)"
    net use $MountDrive "\\sshfs.k\$TargetUser@$TargetHost" /persistent:yes
    Write-Ok "Mounted to $MountDrive"
    Write-Warn2 "SSHFS-Win '.k' mode only reads id_rsa (IdentitiesOnly) -- id_rsa.pub was pushed above for this reason"
}

# ---------- summary ----------

Write-Step "Done"
Write-Ok "ssh $Alias"
if ($Mount) { Write-Ok "$MountDrive  ->  $TargetUser@$TargetHost" }
