#Requires -Version 5.1
<#
  deploy-node.ps1 - Idempotent Node.js provisioning / restore (Windows PowerShell 5.1+)

  Handles both cases:
    - Fresh machine            : download latest LTS (or pinned ver), verify SHA256, extract to D:, configure
    - Same box, C: reinstalled : Node runtime / global / cache already survive on D:,
                                 only rebuild .npmrc + user PATH (no download)

  Usage:
    powershell -ExecutionPolicy Bypass -File deploy-node.ps1                       # latest LTS
    powershell -ExecutionPolicy Bypass -File deploy-node.ps1 -NodeVersion v24.19.0 # pin a version

  Safe to re-run any time (idempotent).
#>
[CmdletBinding()]
param(
    [string]$NodeVersion = 'lts',          # 'lts' = auto latest LTS; or e.g. 'v24.19.0' to pin
    # Defaults match the layout this was written for; override them for another one.
    [string]$NodeHome  = 'D:\Software Library\Nodejs',
    [string]$NpmPrefix = 'D:\Develop Library\Nodejs\npm',
    [string]$NpmCache  = 'D:\Develop Library\Nodejs\npm-cache'
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12   # 5.1 needs this for HTTPS

# ---- Layout (keep in sync with machine-and-drive-layout) ----
$NpmrcPath = Join-Path $HOME '.npmrc'                # user config (lives on C:)
$Legacy    = 'D:\Develop Library\npm'                # stale PATH entry to drop

function Step($m){ Write-Host "`n==> $m" -ForegroundColor Cyan }

# 1) Runtime -----------------------------------------------------------------
if (Test-Path (Join-Path $NodeHome 'node.exe')) {
    Step "Node runtime present on D: ($(& (Join-Path $NodeHome 'node.exe') -v)) - skip download"
} else {
    Step "Node runtime missing - downloading"
    $ProgressPreference = 'SilentlyContinue'
    if ($NodeVersion -eq 'lts') {
        $ver = ((Invoke-RestMethod 'https://nodejs.org/dist/index.json' -TimeoutSec 60) |
                Where-Object { $_.lts } | Select-Object -First 1).version
    } else { $ver = $NodeVersion }
    $pkg = "node-$ver-win-x64"
    $zip = Join-Path $env:TEMP "$pkg.zip"
    Write-Host "    version $ver"
    Invoke-WebRequest "https://nodejs.org/dist/$ver/$pkg.zip" -OutFile $zip -TimeoutSec 300 -UseBasicParsing
    # SHA256 verify against official checksums
    $sums = (Invoke-WebRequest "https://nodejs.org/dist/$ver/SHASUMS256.txt" -TimeoutSec 60 -UseBasicParsing).Content
    $want = (($sums -split "`n") | Where-Object { $_ -match [regex]::Escape("$pkg.zip") } |
             Select-Object -First 1).Trim().Split(' ')[0].ToLower()
    $got  = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($want -ne $got) { throw "SHA256 mismatch: want=$want got=$got" }
    Write-Host "    SHA256 OK"
    $parent = Split-Path $NodeHome -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    if (Test-Path $NodeHome) { Remove-Item $NodeHome -Recurse -Force }   # clear broken remnant
    Expand-Archive $zip -DestinationPath $parent -Force
    Rename-Item (Join-Path $parent $pkg) (Split-Path $NodeHome -Leaf)
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    Write-Host "    extracted to $NodeHome"
}

# 2) D: dirs -----------------------------------------------------------------
Step "Ensure global + cache dirs"
New-Item -ItemType Directory -Path $NpmPrefix -Force | Out-Null
New-Item -ItemType Directory -Path $NpmCache  -Force | Out-Null

# 3) .npmrc (BOM-less UTF8, idempotent) --------------------------------------
Step "Write .npmrc"
[System.IO.File]::WriteAllText($NpmrcPath, "prefix=$NpmPrefix`r`ncache=$NpmCache`r`n",
    (New-Object System.Text.UTF8Encoding($false)))
Write-Host "    $NpmrcPath"

# 4) User PATH (idempotent: drop legacy, ensure both entries) ----------------
Step "Fix user PATH"
$items = @(([Environment]::GetEnvironmentVariable('Path','User') -split ';') |
           Where-Object { $_ -and $_ -ne $Legacy })
foreach ($need in @("$NodeHome\", $NpmPrefix)) {
    if (-not ($items | Where-Object { $_.TrimEnd('\') -eq $need.TrimEnd('\') })) { $items += $need }
}
[Environment]::SetEnvironmentVariable('Path', ($items -join ';'), 'User')

# 5) Verify ------------------------------------------------------------------
Step "Verify"
$env:Path = [Environment]::GetEnvironmentVariable('Path','User') + ';' +
            [Environment]::GetEnvironmentVariable('Path','Machine')
Write-Host "    node   : $(node -v)"
Write-Host "    npm    : v$(npm -v)"
Write-Host "    prefix : $(npm config get prefix)"
Write-Host "    cache  : $(npm config get cache)"
Write-Host "`nDone - open a NEW terminal to use node/npm." -ForegroundColor Green
