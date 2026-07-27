#Requires -Version 5.1
<#
.SYNOPSIS
    迁移后把指定目录下所有文件/目录的所有者(owner)改回当前用户。

.DESCRIPTION
    重装系统或更换账户后，从旧环境继承到 D:/E: 的目录，其 owner 仍是
    旧账户的 SID（新系统里显示为无法解析的 O:S-1-5-21-...）。这会导致：
      - git 报 "detected dubious ownership"，rev-parse 等命令静默失败，
        连带 scoop 自更新等上层工具崩溃
      - 个别程序写配置 / 自更新异常
    本脚本用 icacls 递归把 owner 设回当前用户，一次根治，免去逐个加
    git safe.directory。

    设计要点：
      - 自动检测并提升到管理员（改他人 owner 需要管理员特权）
      - icacls /L 不跟随符号链接/junction 的目标，避免顺着 Scoop 这类
        junction 误改到链接目标；真实目录会在遍历中被直接命中改好
      - /C 遇到无权限的系统目录(如 System Volume Information)自动跳过
      - -DryRun 先只查看每个根目录当前 owner，不做任何修改

.PARAMETER Path
    要处理的根目录，可多个。默认是 D:/E: 上的用户数据目录。
    注意：不要传盘根 D:\ E:\（其 owner 本就是 SYSTEM，应保持不变）。

.PARAMETER Owner
    新所有者，默认当前用户(域\用户名)。

.PARAMETER AddGitSafe
    完成后顺手 git config --global --add safe.directory '*'（一般不需要，
    owner 改对后 git 就不再报 dubious ownership）。

.PARAMETER DryRun
    只列出每个根目录当前 owner，不修改，也不需要管理员。

.PARAMETER NoPause
    跑完不暂停（默认会 Read-Host 暂停，方便看提权新窗口里的结果）。

.EXAMPLE
    pwsh -File .\Reset-OwnerForMigration.ps1 -DryRun
    pwsh -File .\Reset-OwnerForMigration.ps1
    pwsh -File .\Reset-OwnerForMigration.ps1 -Path 'D:\Software Library','E:\Max'
#>
[CmdletBinding()]
param(
    [string[]] $Path  = @('D:\Software Library', 'D:\Develop Library', 'E:\Max'),
    [string]   $Owner = "$env:USERDOMAIN\$env:USERNAME",
    [switch]   $AddGitSafe,
    [switch]   $DryRun,
    [switch]   $NoPause
)

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    ([Security.Principal.WindowsPrincipal]$id).IsInRole(
        [Security.Principal.WindowsBuiltinRole]::Administrator)
}

# ---- 1. 提权（DryRun 不需要管理员）----
if (-not $DryRun -and -not (Test-Admin)) {
    Write-Host "需要管理员权限，正在请求提权(UAC)..." -ForegroundColor Yellow
    $hostExe = (Get-Process -Id $PID).Path        # 用同款宿主重启: pwsh.exe / powershell.exe
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
    foreach ($p in $Path) { $a += @('-Path', $p) }
    $a += @('-Owner', $Owner)
    if ($AddGitSafe) { $a += '-AddGitSafe' }
    try {
        Start-Process -FilePath $hostExe -ArgumentList $a -Verb RunAs
    } catch {
        Write-Host "提权被取消或失败：$($_.Exception.Message)" -ForegroundColor Red
    }
    return
}

# ---- 2. 执行 ----
$me = "$env:USERDOMAIN\$env:USERNAME"
Write-Host ("新所有者 : {0}" -f $Owner)
Write-Host ("当前身份 : {0}  (管理员: {1})" -f $me, (Test-Admin))
Write-Host ("目标路径 : {0}" -f ($Path -join '  ;  '))
Write-Host ("模式     : {0}" -f $(if ($DryRun) { 'DryRun (只查看, 不修改)' } else { '实际修改' }))
Write-Host ('-' * 64)

$sw = [System.Diagnostics.Stopwatch]::StartNew()
foreach ($p in $Path) {
    if (-not (Test-Path -LiteralPath $p)) {
        Write-Host ("跳过(不存在): {0}" -f $p) -ForegroundColor DarkYellow
        continue
    }
    $before = try { (Get-Acl -LiteralPath $p).Owner } catch { '读取失败' }

    if ($DryRun) {
        Write-Host ("[DryRun] {0}" -f $p)
        Write-Host ("         当前 owner: {0}" -f $before)
        continue
    }

    Write-Host (">>> 处理: {0}" -f $p) -ForegroundColor Cyan
    Write-Host ("    改前 owner: {0}" -f $before)
    # /setowner 设所有者; /T 递归子项; /C 出错继续; /L 不跟随符号链接; /Q 安静
    & icacls $p /setowner $Owner /T /C /L /Q
    $after = try { (Get-Acl -LiteralPath $p).Owner } catch { '读取失败' }
    Write-Host ("    改后 owner: {0}" -f $after) -ForegroundColor Green
}
$sw.Stop()

Write-Host ('-' * 64)
if (-not $DryRun) {
    Write-Host ("完成，用时 {0:n1} 秒" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
}

# ---- 3. 可选 git 善后 ----
if ($AddGitSafe -and -not $DryRun) {
    git config --global --add safe.directory '*'
    Write-Host "已添加 git safe.directory '*'"
}

if (-not $DryRun -and -not $NoPause) {
    Read-Host "`n按 Enter 关闭"
}
