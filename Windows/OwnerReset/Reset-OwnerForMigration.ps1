#Requires -Version 5.1
<#
.SYNOPSIS
    迁移善后：把 D:/E: 上从旧系统继承的目录，所有者(owner)改回当前用户，
    并修复其写入权限(ACL)。

.DESCRIPTION
    重装系统或更换账户后，从旧环境继承到 D:/E: 的目录常有两类残留问题：

      1) owner 仍是旧账户的 SID（新系统里无法解析，显示为 O:S-1-5-21-...）：
         - git 报 "detected dubious ownership"，rev-parse 静默失败，连带
           scoop 自更新等上层工具崩溃
      2) DACL 里普通用户(Users)只剩「读取和执行」，没有写入权限：
         - 安装程序在该目录下建文件夹 / 写卸载器时报 "Error opening file for
           writing"（Tuta 等 electron-builder 安装包尤为常见）
         - 程序写配置 / 自更新失败

    注意 owner 与写权限是两回事：owner 归位并不会自动给写权限，两者要分别修。
    （典型现象：某目录 owner 已是你，但装东西仍报写入失败 —— 就是缺 grant。）

    本脚本用 icacls 递归：
      - /setowner  把 owner 设回当前用户（根治问题 1）
      - /grant     给当前用户加「修改(Modify)」权限、可继承(OI)(CI)（根治问题 2）
        可选 -RemoveStaleAces 把 DACL 里无法解析的旧账户 ACE 一并按 SID 递归清掉。

    owner 与写权限的传播规律不同（决定了要不要 -T 递归）：
      - 写权限(grant)：ACE 可继承(OI)(CI)，只加在根目录，现有子项与将来新建的
        子项都会自动继承 —— 所以 grant 其实不必递归。
      - owner：不走继承，每个文件各自记 owner —— 要让子文件也归位必须递归(/T)。
    默认递归(两者都 /T)最彻底；文件巨多的目录可用 -NoRecurse 只改根：写权限照
    样靠继承覆盖全树，owner 则只清掉根这一层的幽灵账户(通常已够，git 只看仓库根)。

    设计要点：
      - 自动检测并提升到管理员（改他人 owner / 改 DACL 需要管理员特权）
      - -Drive D: 自动枚举盘内所有顶层目录，并跳过系统托管目录
        ($RECYCLE.BIN / System Volume Information / WindowsApps / WpSystem /
         Program Files / ProgramData / Config.Msi ...) 与 junction/符号链接
      - icacls /L 不跟随符号链接/junction，避免顺着 Scoop 这类 junction 误改到目标
      - /C 遇到无权限的系统目录自动跳过
      - -DryRun 只扫描并报告(owner 是否旧账户 / 能否写入 / 旧ACE)，不改动、不需管理员

.PARAMETER Path
    显式指定要处理的根目录，可多个。别传盘根 D:\ E:\（其 owner 本就是 SYSTEM，应保持不变）。
    不传 -Path 也不传 -Drive 时，默认处理 D:/E: 上的用户数据目录。

.PARAMETER Drive
    要整盘扫描的盘符（如 'D:'），自动枚举其下所有顶层目录并排除系统目录。
    可与 -Path 叠加，最终目标去重。

.PARAMETER Owner
    新所有者，默认当前用户(域\用户名)。

.PARAMETER GrantTo
    授予「修改」权限的主体，默认与 -Owner 相同(当前用户)。
    单人机器保持默认即可；若想让所有本地用户可写，传 -GrantTo 'Users'。

.PARAMETER SkipGrant
    只改 owner、不加写权限（等同旧版行为）。

.PARAMETER RemoveStaleAces
    额外清理 DACL 中无法解析的旧账户 ACE（从根按 SID 递归 icacls /remove）。

.PARAMETER NoRecurse
    只处理根目录、不加 /T。写权限靠继承仍覆盖全树；owner 只改根这一层。
    文件极多的目录(如已装满软件的库、大型游戏目录)用它可秒完成。

.PARAMETER AddGitSafe
    完成后顺手 git config --global --add safe.directory '*'（owner 改对后一般不需要）。

.PARAMETER DryRun
    只扫描报告，不修改，也不需要管理员。

.PARAMETER NoPause
    跑完不暂停（默认会 Read-Host 暂停，方便看提权新窗口里的结果）。

.EXAMPLE
    # 先预览整个 D 盘现状（不改动、不需管理员）
    pwsh -File .\Reset-OwnerForMigration.ps1 -Drive D: -DryRun

.EXAMPLE
    # 修复整个 D 盘：owner 归位 + 给自己加写权限（自动提权 UAC）
    pwsh -File .\Reset-OwnerForMigration.ps1 -Drive D:

.EXAMPLE
    # 只修指定目录，并清理旧账户残留 ACE
    pwsh -File .\Reset-OwnerForMigration.ps1 -Path 'D:\Software Library' -RemoveStaleAces

.EXAMPLE
    # 文件极多的目录：只改根(秒完成)，写权限靠继承覆盖全树
    pwsh -File .\Reset-OwnerForMigration.ps1 -Path 'D:\XboxGames' -NoRecurse
#>
[CmdletBinding()]
param(
    [string[]] $Path,
    [string[]] $Drive,
    [string]   $Owner   = "$env:USERDOMAIN\$env:USERNAME",
    [string]   $GrantTo,
    [switch]   $SkipGrant,
    [switch]   $RemoveStaleAces,
    [switch]   $NoRecurse,
    [switch]   $AddGitSafe,
    [switch]   $DryRun,
    [switch]   $NoPause
)

if (-not $GrantTo) { $GrantTo = $Owner }
# 都没指定就沿用旧版默认目标
if (-not $Path -and -not $Drive) {
    $Path = @('D:\Software Library', 'D:\Develop Library', 'E:\Max')
}

# 整盘扫描时要跳过的系统托管目录（大小写不敏感）——动它们会弄坏系统/商店应用
$ExcludeNames = @(
    '$RECYCLE.BIN', 'System Volume Information', 'Config.Msi', 'WindowsApps', 'WpSystem',
    'Program Files', 'Program Files (x86)', 'ProgramData', 'Recovery', 'PerfLogs',
    '$SysReset', '$WinREAgent', '$Windows.~WS', '$Windows.~BT', 'OneDriveTemp'
)

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    ([Security.Principal.WindowsPrincipal]$id).IsInRole(
        [Security.Principal.WindowsBuiltinRole]::Administrator)
}

# 取目录 owner；返回 SID / 解析后的名字 / 是否为无法解析的旧账户
function Get-OwnerInfo {
    param([string]$Dir)
    try {
        $acl = Get-Acl -LiteralPath $Dir -ErrorAction Stop
        $sid = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
        try {
            $name  = (New-Object Security.Principal.SecurityIdentifier($sid)).Translate([Security.Principal.NTAccount]).Value
            $stale = $false
        } catch { $name = $sid; $stale = $true }
        [pscustomobject]@{ Sid = $sid; Name = $name; Stale = $stale }
    } catch {
        [pscustomobject]@{ Sid = $null; Name = '<ACL读取失败>'; Stale = $null }
    }
}

# 实测能否在该目录写入（最贴近真实结果的判断）
function Test-CanWrite {
    param([string]$Dir)
    $t = Join-Path $Dir ('.__wtest_{0}.tmp' -f [guid]::NewGuid().ToString('N'))
    try { [IO.File]::WriteAllText($t, 'x'); [IO.File]::Delete($t); $true }
    catch { $false }
}

# 该目录 DACL 里无法解析的 SID（旧账户残留 ACE）
function Get-StaleSids {
    param([string]$Dir)
    try { $acl = Get-Acl -LiteralPath $Dir -ErrorAction Stop } catch { return @() }
    $out = @()
    foreach ($ace in $acl.Access) {
        $ref = $ace.IdentityReference
        if ($ref -is [Security.Principal.SecurityIdentifier]) {
            try { [void]$ref.Translate([Security.Principal.NTAccount]) } catch { $out += $ref.Value }
        } elseif ($ref.Value -match '^S-1-') {
            $out += $ref.Value
        }
    }
    $out | Select-Object -Unique
}

# icacls 收尾会打印一行汇总(“已成功处理 X 个文件；处理 Y 个失败”)，取来显示
function Invoke-Icacls {
    param([string[]]$Args, [string]$Label)
    $o = & icacls @Args 2>&1
    $last = $o | Where-Object { $_ -and $_.ToString().Trim() } | Select-Object -Last 1
    if ($last) { Write-Host ("    {0}: {1}" -f $Label, $last) -ForegroundColor DarkGray }
}

# 把字符串包成 PowerShell 单引号字面量(内部单引号翻倍)，用于安全拼接提权命令
function ConvertTo-SqLiteral { param([string]$s) "'" + ($s -replace "'", "''") + "'" }

# ---- 1. 汇总目标目录（-Path 显式 + -Drive 枚举，去重）----
$targets = [System.Collections.Generic.List[string]]::new()
foreach ($p in ($Path | Where-Object { $_ })) { $targets.Add($p.TrimEnd('\')) }
foreach ($drv in ($Drive | Where-Object { $_ })) {
    $root = ($drv.TrimEnd('\', ':')) + ':\'
    if (-not (Test-Path -LiteralPath $root)) {
        Write-Host ("跳过(盘不存在): {0}" -f $root) -ForegroundColor DarkYellow
        continue
    }
    foreach ($item in (Get-ChildItem -LiteralPath $root -Directory -Force -ErrorAction SilentlyContinue)) {
        if ($ExcludeNames -contains $item.Name) {
            Write-Host ("  跳过(系统目录): {0}" -f $item.Name) -ForegroundColor DarkGray; continue
        }
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Write-Host ("  跳过(junction/链接): {0}" -f $item.Name) -ForegroundColor DarkGray; continue
        }
        $targets.Add($item.FullName)
    }
}
$targets = @($targets | Select-Object -Unique)
if ($targets.Count -eq 0) {
    Write-Host "没有可处理的目标目录。用 -Path 或 -Drive 指定。" -ForegroundColor Yellow
    if (-not $NoPause) { Read-Host "`n按 Enter 关闭" }
    return
}

# ---- 2. 提权（DryRun 不需要管理员）；把已解析好的目标以 -Path 转发，避免重复枚举 ----
if (-not $DryRun -and -not (Test-Admin)) {
    Write-Host "需要管理员权限，正在请求提权(UAC)..." -ForegroundColor Yellow
    $hostExe = (Get-Process -Id $PID).Path        # 用同款宿主重启: pwsh.exe / powershell.exe
    # 用 -EncodedCommand 转发：把已解析好的目标当数组重建。彻底避开 -File 下的坑
    # (重复 -Path 会报 “specified more than once”；逗号数组经 -File 只取到第一个)
    $pathLit = ($targets | ForEach-Object { ConvertTo-SqLiteral $_ }) -join ','
    $cmd  = "& $(ConvertTo-SqLiteral $PSCommandPath) -Path $pathLit"
    $cmd += " -Owner $(ConvertTo-SqLiteral $Owner) -GrantTo $(ConvertTo-SqLiteral $GrantTo)"
    if ($SkipGrant)       { $cmd += ' -SkipGrant' }
    if ($RemoveStaleAces) { $cmd += ' -RemoveStaleAces' }
    if ($NoRecurse)       { $cmd += ' -NoRecurse' }
    if ($AddGitSafe)      { $cmd += ' -AddGitSafe' }
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd))
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $enc)
    try {
        Start-Process -FilePath $hostExe -ArgumentList $a -Verb RunAs
    } catch {
        Write-Host "提权被取消或失败：$($_.Exception.Message)" -ForegroundColor Red
    }
    return
}

# ---- 3. 执行 ----
$me = "$env:USERDOMAIN\$env:USERNAME"
Write-Host ("新所有者   : {0}" -f $Owner)
Write-Host ("授予写权限 : {0}" -f $(if ($SkipGrant) { '否 (仅改 owner)' } else { "$GrantTo -> Modify (可继承)" }))
Write-Host ("清旧 ACE   : {0}" -f $(if ($RemoveStaleAces) { '是' } else { '否' }))
Write-Host ("递归子项   : {0}" -f $(if ($NoRecurse) { '否 (仅根目录, owner 只改根/写权限靠继承)' } else { '是 (/T 全递归)' }))
Write-Host ("当前身份   : {0}  (管理员: {1})" -f $me, (Test-Admin))
Write-Host ("目标数     : {0}" -f $targets.Count)
Write-Host ("模式       : {0}" -f $(if ($DryRun) { 'DryRun (只扫描, 不修改)' } else { '实际修改' }))
Write-Host ('=' * 72)

$T = if ($NoRecurse) { @() } else { @('/T') }   # 递归开关
$sw = [System.Diagnostics.Stopwatch]::StartNew()
foreach ($p in $targets) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Host ("跳过(不存在): {0}" -f $p) -ForegroundColor DarkYellow; continue
    }
    $oi = Get-OwnerInfo $p
    $ownerTag = if ($oi.Stale) { "$($oi.Name)  <<旧账户!" } else { $oi.Name }

    if ($DryRun) {
        $canW   = Test-CanWrite $p
        $stales = Get-StaleSids $p
        Write-Host ("[DryRun] {0}" -f $p) -ForegroundColor Cyan
        Write-Host ("         owner : {0}" -f $ownerTag)   -ForegroundColor $(if ($oi.Stale) { 'Red' } else { 'Gray' })
        Write-Host ("         可写  : {0}" -f $(if ($canW) { '是' } else { '否  <<需修' })) -ForegroundColor $(if ($canW) { 'Gray' } else { 'Red' })
        if ($stales) { Write-Host ("         旧ACE : {0}" -f ($stales -join ', ')) -ForegroundColor DarkYellow }
        continue
    }

    Write-Host (">>> {0}" -f $p) -ForegroundColor Cyan
    Write-Host ("    改前 owner: {0}" -f $ownerTag)

    # /setowner 设所有者; /grant 加权限; /T 递归(见 $T); /C 出错继续; /L 不跟符号链接; /Q 安静
    Invoke-Icacls -Label 'owner' -Args (@($p, '/setowner', $Owner) + $T + @('/C', '/L', '/Q'))
    if (-not $SkipGrant) {
        Invoke-Icacls -Label 'grant' -Args (@($p, '/grant', "${GrantTo}:(OI)(CI)(M)") + $T + @('/C', '/L', '/Q'))
    }
    if ($RemoveStaleAces) {
        foreach ($sid in (Get-StaleSids $p)) {
            Write-Host ("    移除旧ACE: {0}" -f $sid) -ForegroundColor DarkYellow
            Invoke-Icacls -Label 'remove' -Args (@($p, '/remove', "*$sid") + $T + @('/C', '/L', '/Q'))
        }
    }

    $oi2   = Get-OwnerInfo $p
    $canW2 = Test-CanWrite $p       # 注意：提权后用的是管理员令牌，SkipGrant 时此处可能偏乐观
    Write-Host ("    改后 owner: {0}   可写: {1}" -f $oi2.Name, $(if ($canW2) { '是' } else { '否' })) -ForegroundColor Green
}
$sw.Stop()

Write-Host ('=' * 72)
if (-not $DryRun) {
    Write-Host ("完成，用时 {0:n1} 秒" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
}

# ---- 4. 可选 git 善后 ----
if ($AddGitSafe -and -not $DryRun) {
    git config --global --add safe.directory '*'
    Write-Host "已添加 git safe.directory '*'"
}

if (-not $DryRun -and -not $NoPause) {
    Read-Host "`n按 Enter 关闭"
}
