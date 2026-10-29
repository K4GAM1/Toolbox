#Requires -Version 5.1
<#
================================================================================
  电源 & WiFi 配置工具  (Windows)
================================================================================
  一个交互式的电源 / 网络电源管理小工具:选预设,或逐项自定义,再一键应用。
  面向任何想调整电脑电源相关设定的人,不限于远程场景。

  可配置项目:
    · 休眠 (Hibernate)            开 / 关
    · 快速启动 (Fast Startup)     开 / 关(依赖休眠)
    · 睡眠超时 (Sleep)            多少分钟无操作后睡眠(0 = 永不)
    · 无人值守睡眠超时            针对「无人操作」的隐藏超时(0 = 永不)
    · 显示器超时 (Monitor)        多少分钟无操作后关屏(0 = 永不)
    · 无线适配器省电模式          最高性能 … 最大省电
    · 网卡「允许关闭省电」        允许 / 禁止(设备管理器里那个复选框)

  内置预设:
    [1] 远程 / 无人值守
        永不睡眠、关快速启动(每次干净冷启动)、无线最高性能、网卡不省电、
        关屏 10 分钟。目标是机器 7x24 在线、随时可被远程连入
        (RustDesk / TeamViewer / SSH 等),配合 BIOS「来电自启」或 WOL 还能远程开机。
        适合:留守主机、家庭服务器、放在异地要远程用的机器。

    [2] 个人省电
        适度睡眠(20 分钟)、保留快速启动(开机快)、无线最大省电、网卡可省电、
        关屏 5 分钟。目标是省电、发热小、安静。
        适合:笔记本 / 日常插电使用,不需要长期挂机。

    [3] 自定义      —— 逐项自己选,每项都给出不同场景的建议。
    [4] 查看当前设置 —— 只读,不改动任何东西。

  说明:本工具配置的是【交流电源(插电)】下的行为。
        需要管理员权限(会自动提权)。所有改动可重复运行、随时切换预设。
================================================================================
#>

# ============================ 自动提权 ============================
$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "需要管理员权限,正在请求提权(UAC)..." -ForegroundColor Yellow
    $engine = (Get-Process -Id $PID).Path
    Start-Process -FilePath $engine -Verb RunAs -ArgumentList @(
        '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
    )
    exit
}

# ============================ 常量 ============================
$SUB_SLEEP    = '238c9fa8-0aad-41ed-83f4-97be242c8f20'
$STANDBYIDLE  = '29f6c1db-86da-48c5-9fdb-f2b67b1f44da'
$UNATTENDED   = '7bc4a2f9-d8fc-4469-b07b-33eb785aaca0'
$SUB_VIDEO    = '7516b95f-f776-4464-8c53-06167f40cc99'
$VIDEOIDLE    = '3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e'
$SUB_WIRELESS = '19cbb8fa-5279-450e-9fac-8a3d5fedd0c1'
$PSM          = '12bbebe6-58d6-4636-95bb-3217ef867c1a'

$FSU_KEY = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power'

# ============================ 输出 / 文本工具 ============================
function Step($m) { Write-Host "`n[*] $m" -ForegroundColor Cyan }
function Ok  ($m) { Write-Host "    [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    [!!] $m" -ForegroundColor Yellow }

function State([bool]$b)  { if ($b) { '开' } else { '关' } }
function MinText([int]$m) { if ($m -lt 0) { '未知' } elseif ($m -eq 0) { '永不' } else { "$m 分钟" } }
function PsmText([int]$v) {
    $t = @('最高性能', '低省电', '中省电', '最大省电')
    if ($v -ge 0 -and $v -lt 4) { $t[$v] } else { "未知($v)" }
}

# ============================ 交互输入 ============================
function Ask-YesNo($prompt, [bool]$default) {
    $hint = if ($default) { 'Y/n' } else { 'y/N' }
    while ($true) {
        $r = Read-Host "  $prompt  [当前:$(State $default)] ($hint)"
        if ([string]::IsNullOrWhiteSpace($r)) { return $default }
        switch -Regex ($r.Trim().ToLower()) {
            '^(y|yes|是|开|1)$' { return $true }
            '^(n|no|否|关|0)$'  { return $false }
            default { Write-Host "    请输入 y 或 n" -ForegroundColor DarkYellow }
        }
    }
}
function Ask-Int($prompt, [int]$default, [int]$max = 2147483647) {
    while ($true) {
        $r = Read-Host "  $prompt  [当前:$default]"
        if ([string]::IsNullOrWhiteSpace($r)) { return $default }
        $n = 0
        if ([int]::TryParse($r.Trim(), [ref]$n) -and $n -ge 0 -and $n -le $max) { return $n }
        Write-Host "    请输入 0 到 $max 之间的整数" -ForegroundColor DarkYellow
    }
}

# ============================ 读取当前值 ============================
function Get-HibernateState {
    $v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Power' -Name HibernateEnabled -EA SilentlyContinue).HibernateEnabled
    if ($v -eq 1) { $true } else { $false }
}
function Get-FastStartupState {
    if (-not (Get-HibernateState)) { return $false }    # 休眠关 → 快速启动必然失效
    $v = (Get-ItemProperty $FSU_KEY -Name HiberbootEnabled -EA SilentlyContinue).HiberbootEnabled
    if ($null -eq $v) { $true } else { $v -eq 1 }        # 未设时 Windows 默认开启
}
function Get-AcMin($sub, $setting) {
    $line = (powercfg /q SCHEME_CURRENT $sub $setting | Select-String 'Current AC').Line
    if ($line -match '0x([0-9a-fA-F]+)') { [Convert]::ToInt32($matches[1], 16) / 60 } else { -1 }
}
function Get-UnattendedMin {
    # 无人值守睡眠是隐藏设置,powercfg /q 不输出其值行,改从注册表读
    $scheme = (powercfg /getactivescheme) -replace '.*GUID:\s*([0-9a-fA-F-]+).*', '$1'
    $p = "HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\$scheme\$SUB_SLEEP\$UNATTENDED"
    $v = (Get-ItemProperty $p -Name ACSettingIndex -EA SilentlyContinue).ACSettingIndex
    if ($null -eq $v) { -1 } else { [int]$v / 60 }
}
function Get-WirelessPsm {
    $line = (powercfg /q SCHEME_CURRENT $SUB_WIRELESS $PSM | Select-String 'Current AC').Line
    if ($line -match '0x([0-9a-fA-F]+)') { [Convert]::ToInt32($matches[1], 16) } else { -1 }
}
function Get-NicPowerOffAllowed($adapter) {
    $dev = Get-CimInstance -Namespace root\wmi -ClassName MSPower_DeviceEnable -EA SilentlyContinue |
           Where-Object { $_.InstanceName -like "$($adapter.PnPDeviceID)*" } | Select-Object -First 1
    if ($dev) { [bool]$dev.Enable } else { $null }
}

# ============================ 应用设置 ============================
function Apply-Hibernate([bool]$on) {
    powercfg /hibernate $(if ($on) { 'on' } else { 'off' }) 2>&1 | Out-Null
}
function Apply-FastStartup([bool]$on) {
    Set-ItemProperty $FSU_KEY -Name HiberbootEnabled -Value $(if ($on) { 1 } else { 0 }) -Type DWord
}
function Apply-SleepMin([int]$m)   { powercfg /change standby-timeout-ac $m | Out-Null }
function Apply-MonitorMin([int]$m) { powercfg /change monitor-timeout-ac $m | Out-Null }
function Apply-UnattendedMin([int]$m) {
    powercfg /setacvalueindex SCHEME_CURRENT $SUB_SLEEP $UNATTENDED ($m * 60) | Out-Null
}
function Apply-WirelessPsm([int]$v) {
    powercfg /setacvalueindex SCHEME_CURRENT $SUB_WIRELESS $PSM $v | Out-Null
}
function Apply-NicPowerOff([bool]$block) {
    foreach ($a in $script:WifiAdapters) {
        $dev = Get-CimInstance -Namespace root\wmi -ClassName MSPower_DeviceEnable -EA SilentlyContinue |
               Where-Object { $_.InstanceName -like "$($a.PnPDeviceID)*" } | Select-Object -First 1
        if ($dev) {
            try { Set-CimInstance -InputObject $dev -Property @{ Enable = (-not $block) } -EA Stop }
            catch { Warn "[$($a.Name)] 网卡省电设置失败:$($_.Exception.Message)" }
        }
    }
}

function Apply-Config($c) {
    Step "应用设置中..."
    Apply-Hibernate $c.Hibernate;         Ok "休眠 = $(State $c.Hibernate)"
    if ($c.FastStartup -and -not $c.Hibernate) {
        Warn "快速启动需要休眠开启;当前休眠为关,已将快速启动一并设为关"
        Apply-FastStartup $false
    } else {
        Apply-FastStartup $c.FastStartup; Ok "快速启动 = $(State $c.FastStartup)"
    }
    Apply-SleepMin      $c.SleepMin;      Ok "睡眠超时 = $(MinText $c.SleepMin)"
    Apply-UnattendedMin $c.UnattendedMin; Ok "无人值守睡眠 = $(MinText $c.UnattendedMin)"
    Apply-MonitorMin    $c.MonitorMin;    Ok "显示器超时 = $(MinText $c.MonitorMin)"
    Apply-WirelessPsm   $c.WirelessPSM;   Ok "无线省电 = $(PsmText $c.WirelessPSM)"
    if ($script:WifiAdapters) {
        Apply-NicPowerOff $c.NicPowerOffBlock
        Ok "网卡允许省电关闭 = $(if ($c.NicPowerOffBlock) { '禁止' } else { '允许' })"
    }
    powercfg /setactive SCHEME_CURRENT | Out-Null
}

# ============================ 展示 ============================
function Show-Current {
    Step "当前设置(交流电源)"
    Write-Host ("    休眠              : {0}" -f (State (Get-HibernateState)))
    Write-Host ("    快速启动          : {0}" -f (State (Get-FastStartupState)))
    Write-Host ("    睡眠超时          : {0}" -f (MinText (Get-AcMin $SUB_SLEEP $STANDBYIDLE)))
    Write-Host ("    无人值守睡眠      : {0}" -f (MinText (Get-UnattendedMin)))
    Write-Host ("    显示器超时        : {0}" -f (MinText (Get-AcMin $SUB_VIDEO $VIDEOIDLE)))
    Write-Host ("    无线省电模式      : {0}" -f (PsmText (Get-WirelessPsm)))
    foreach ($a in $script:WifiAdapters) {
        $allow = Get-NicPowerOffAllowed $a
        $txt = if ($null -eq $allow) { '未知' } elseif ($allow) { '允许' } else { '禁止' }
        Write-Host ("    网卡[{0}] 允许省电关闭 : {1}" -f $a.Name, $txt)
    }
}

function Show-Summary($c) {
    Step "将应用以下设置(交流电源)"
    if ($c.Name) { Write-Host ("    预设              : {0}" -f $c.Name) -ForegroundColor DarkGray }
    Write-Host ("    休眠              : {0}" -f (State $c.Hibernate))
    Write-Host ("    快速启动          : {0}" -f (State $c.FastStartup))
    Write-Host ("    睡眠超时          : {0}" -f (MinText $c.SleepMin))
    Write-Host ("    无人值守睡眠      : {0}" -f (MinText $c.UnattendedMin))
    Write-Host ("    显示器超时        : {0}" -f (MinText $c.MonitorMin))
    Write-Host ("    无线省电模式      : {0}" -f (PsmText $c.WirelessPSM))
    Write-Host ("    网卡省电关闭      : {0}" -f $(if ($c.NicPowerOffBlock) { '禁止(不省电)' } else { '允许' }))
}

function Read-Custom {
    $cur = @{
        Hibernate     = Get-HibernateState
        FastStartup   = Get-FastStartupState
        SleepMin      = [Math]::Max(0, (Get-AcMin $SUB_SLEEP $STANDBYIDLE))
        UnattendedMin = [Math]::Max(0, (Get-UnattendedMin))
        MonitorMin    = [Math]::Max(0, (Get-AcMin $SUB_VIDEO $VIDEOIDLE))
        WirelessPSM   = [Math]::Max(0, (Get-WirelessPsm))
    }
    Write-Host "`n逐项设置(直接回车 = 保持当前值)。括号内为不同场景的建议。" -ForegroundColor Gray
    $c = @{}
    $c.Hibernate     = Ask-YesNo "休眠(远程建议:关 / 省电建议:开)" $cur.Hibernate
    $c.FastStartup   = Ask-YesNo "快速启动(远程建议:关,保证干净冷启动 / 省电建议:开,开机快)" $cur.FastStartup
    $c.SleepMin      = Ask-Int   "睡眠超时,分钟,0=永不(远程建议:0,睡眠会断网 / 省电建议:15~30)" $cur.SleepMin
    $c.UnattendedMin = Ask-Int   "无人值守睡眠超时,分钟,0=永不(远程建议:0)" $cur.UnattendedMin
    $c.MonitorMin    = Ask-Int   "显示器超时,分钟,0=永不(建议:5~15,关屏不影响远程)" $cur.MonitorMin
    $c.WirelessPSM   = Ask-Int   "无线省电 0=最高性能 1=低 2=中 3=最大省电(远程建议:0 / 省电建议:3)" $cur.WirelessPSM 3
    if ($script:WifiAdapters) {
        $c.NicPowerOffBlock = Ask-YesNo "禁止系统为省电关闭无线网卡?(远程建议:是 / 省电建议:否)" $true
    } else {
        $c.NicPowerOffBlock = $false
    }
    return $c
}

# ============================ 预设 ============================
$Presets = @{
    '1' = @{ Name = '远程 / 无人值守(另需进 BIOS 设 Restore after AC Power Loss = Power On,脚本管不到)'; Hibernate = $false; FastStartup = $false; SleepMin = 0;  UnattendedMin = 0; MonitorMin = 10; WirelessPSM = 0; NicPowerOffBlock = $true }
    '2' = @{ Name = '个人省电';        Hibernate = $true;  FastStartup = $true;  SleepMin = 20; UnattendedMin = 2; MonitorMin = 5;  WirelessPSM = 3; NicPowerOffBlock = $false }
}

# ============================ 主循环 ============================
$script:WifiAdapters = Get-NetAdapter -Physical -EA SilentlyContinue | Where-Object {
    $_.PhysicalMediaType -match '802\.11' -or $_.InterfaceDescription -match 'Wi-?Fi|Wireless'
}

while ($true) {
    Write-Host "`n==== 电源 & WiFi 配置工具 ====" -ForegroundColor White
    Write-Host "  [1] 远程 / 无人值守    7x24 在线、随时可远程连入"
    Write-Host "  [2] 个人省电           笔记本 / 日常,尽量省电、安静"
    Write-Host "  [3] 自定义             逐项自己选(每项有建议)"
    Write-Host "  [4] 查看当前设置       只读,不改动"
    Write-Host "  [0] 退出"
    $sel = (Read-Host "请选择").Trim()

    switch ($sel) {
        '0' { Write-Host "已退出。" -ForegroundColor Gray; return }
        '4' { Show-Current; continue }
        '1' { $cfg = $Presets['1'] }
        '2' { $cfg = $Presets['2'] }
        '3' { $cfg = Read-Custom }
        default { Write-Host "无效选择,请重新输入。" -ForegroundColor DarkYellow; continue }
    }

    Show-Summary $cfg
    if (Ask-YesNo "确认应用以上设置?" $false) {
        Apply-Config $cfg
        Write-Host ""
        Show-Current
        Write-Host "`n完成。" -ForegroundColor Green
        if ($cfg.SleepMin -eq 0 -and -not $cfg.Hibernate) {
            Write-Host "提示(远程场景):若还想远程开机,请另进 BIOS 设 Restore after AC Power Loss = Power On。" -ForegroundColor Yellow
        }
    } else {
        Write-Host "已取消,未做任何更改。" -ForegroundColor Gray
    }
}
