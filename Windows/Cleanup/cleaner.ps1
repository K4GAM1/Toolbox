<#
.SYNOPSIS
    Windows 垃圾清理工具 (PowerShell 版，功能对齐 cleaner.py v1.04，无 TUI)
.EXAMPLE
    .\cleaner.ps1                        # 交互模式：欢迎界面 -> 分类菜单
    .\cleaner.ps1 -Execute                # 执行清理（所有分类）
    .\cleaner.ps1 -Cache -Execute         # 只清理缓存并执行
    .\cleaner.ps1 -GpuCache -Execute      # 只清理 GPU 着色器缓存并执行
    .\cleaner.ps1 -Logs -Execute          # 只清理日志与崩溃转储并执行
    .\cleaner.ps1 -EmptyDirs -Execute     # 只删除空文件夹并执行
    .\cleaner.ps1 -System -Execute        # 只清理系统级缓存，建议管理员权限运行
    .\cleaner.ps1 -Execute -Detail        # 执行并显示每个被处理的文件
#>
param(
    [switch]$Cache,
    [switch]$Installers,
    [switch]$GpuCache,
    [switch]$Logs,
    [switch]$EmptyDirs,
    [switch]$System,
    [string]$UserPath,
    [Alias('x')][switch]$Execute,
    [Alias('v')][switch]$Detail,
    [Alias('y')][switch]$Yes
)

# ---------- 终端颜色 (VT100) ----------

Add-Type -Name Console -Namespace CleanerNative -MemberDefinition @'
[DllImport("kernel32.dll")]
public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
[DllImport("kernel32.dll")]
public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
[DllImport("kernel32.dll")]
public static extern IntPtr GetStdHandle(int nStdHandle);
[DllImport("kernel32.dll")]
public static extern bool SetConsoleOutputCP(uint wCodePageID);
[DllImport("kernel32.dll")]
public static extern bool SetConsoleCP(uint wCodePageID);
'@ -ErrorAction SilentlyContinue

function Enable-Vt {
    try {
        $h = [CleanerNative.Console]::GetStdHandle(-11)
        $mode = 0
        [CleanerNative.Console]::GetConsoleMode($h, [ref]$mode) | Out-Null
        [CleanerNative.Console]::SetConsoleMode($h, $mode -bor 0x0004) | Out-Null
        # 控制台默认代码页可能不是 UTF-8（如日文系统的 932），不切换会导致
        # 中日文文字在新开的控制台窗口里乱码（对应 cleaner.py v1.04 的修复）
        [CleanerNative.Console]::SetConsoleOutputCP(65001) | Out-Null
        [CleanerNative.Console]::SetConsoleCP(65001) | Out-Null
    } catch {}
    try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
    try { [Console]::TreatControlCAsInput = $true } catch {}
}

$script:ESC     = [char]27
$script:RED     = $script:ESC + '[91m'
$script:GREEN   = $script:ESC + '[92m'
$script:YELLOW  = $script:ESC + '[93m'
$script:BLUE    = $script:ESC + '[94m'
$script:MAGENTA = $script:ESC + '[95m'
$script:CYAN    = $script:ESC + '[96m'
$script:BOLD    = $script:ESC + '[1m'
$script:RESET   = $script:ESC + '[0m'

$script:RAINBOW = @($script:RED, $script:YELLOW, $script:GREEN, $script:CYAN, $script:MAGENTA, $script:BLUE)
$script:VERSION = '1.04'

function Get-RainbowWords {
    param([string]$Text)
    $words = $Text -split ' '
    $out = @()
    for ($i = 0; $i -lt $words.Count; $i++) {
        $color = $script:RAINBOW[$i % $script:RAINBOW.Count]
        $out += ($color + $words[$i] + $script:RESET)
    }
    return ($out -join ' ')
}

function Clear-HostSafe {
    # 非交互/管道重定向环境下没有真实控制台句柄，Clear-Host 会抛异常；
    # 静默失败，跟 Python 版 os.system('cls') 的行为对齐
    try { Clear-Host } catch {}
}

function Exit-AndClose {
    Clear-HostSafe
    exit 0
}

# ---------- 国際化 / i18n ----------

$script:Lang = 'en'

$script:UI = @{
    zh = @{
        title = "Windows 用户目录清理工具"
        mode_dry = "预览模式"
        mode_exec = "执行模式"
        target_dir = "目标目录"
        scan_phase = "扫描{name}..."
        exec_phase = "删除{name}..."
        found = "发现 {size}，{deleted} 项可清理，{skipped} 项无权限"
        verb_scan = "已发现"
        verb_exec = "已释放"
        menu_header = "选择要清理的分类  (数字键切换 / a 全选↔全不选 / 回车删除 / l 语言 / q 退出)"
        menu_total = "合计 (已选)"
        items_del = "项可删"
        items_skip = "项跳过"
        at_least_one = "请至少选择一项"
        press_any_key = "按任意键返回菜单..."
        confirm = "即将执行删除操作，确认继续？[y/N] "
        cancelled = "已取消。"
        done = "清理完成！"
        err_no_dir = "错误：用户目录不存在: {path}"
        col_category = "分类"
        col_freed = "释放空间"
        col_deleted = "删除数"
        col_skipped = "跳过数"
        col_total = "合计"
        cat_cache = "缓存文件"
        cat_installers = "安装包文件"
        cat_empty_dirs = "空文件夹"
        lang_title = "选择语言 / Select Language / 言語選択"
        lang_hint = "数字键选择 / q 返回菜单"
        lang_invalid = "无效选项，请重新输入"
        cat_gpu_cache = "GPU着色器缓存"
        cat_logs = "日志与崩溃转储"
        cat_system = "系统级缓存"
        welcome_desc = "清理 Windows 用户目录及系统级下的缓存、日志、GPU 着色器缓存与空文件夹"
        welcome_lang = "切换语言"
        welcome_scan = "开始扫描"
        welcome_quit = "退出"
        post_success = "本次共释放 {size}，删除 {deleted} 项"
        post_nothing = "未能清理任何文件（可能权限不足）"
        post_skipped = "另有 {skipped} 项因权限不足被跳过"
        post_back = "返回主菜单"
        post_exit = "退出并关闭窗口"
        post_header = "清理结束  (1 返回主菜单 / q 退出)"
    }
    en = @{
        title = "Windows User Directory Cleaner"
        mode_dry = "Preview Mode"
        mode_exec = "Execute Mode"
        target_dir = "Target directory"
        scan_phase = "Scanning {name}..."
        exec_phase = "Deleting {name}..."
        found = "Found {size},  {deleted} items to clean,  {skipped} skipped"
        verb_scan = "Found"
        verb_exec = "Freed"
        menu_header = "Select categories  (number toggle / a all<->none / Enter delete / l language / q quit)"
        menu_total = "Total (selected)"
        items_del = "to delete"
        items_skip = "skipped"
        at_least_one = "Please select at least one category"
        press_any_key = "Press any key to return to menu..."
        confirm = "About to delete files. Continue? [y/N] "
        cancelled = "Cancelled."
        done = "Cleanup complete!"
        err_no_dir = "Error: User directory not found: {path}"
        col_category = "Category"
        col_freed = "Freed"
        col_deleted = "Deleted"
        col_skipped = "Skipped"
        col_total = "Total"
        cat_cache = "Cache Files"
        cat_installers = "Installers"
        cat_empty_dirs = "Empty Dirs"
        lang_title = "選択言語 / Select Language / 选择语言"
        lang_hint = "number to select / q back to menu"
        lang_invalid = "Invalid option, please try again"
        cat_gpu_cache = "GPU Shader Cache"
        cat_logs = "Logs & Crash Dumps"
        cat_system = "System-level Cache"
        welcome_desc = "Cleans cache, logs, GPU shader cache, empty folders & system-level junk"
        welcome_lang = "Change Language"
        welcome_scan = "Start Scan"
        welcome_quit = "Quit"
        post_success = "Freed {size}, deleted {deleted} items"
        post_nothing = "Nothing could be cleaned (possibly insufficient permissions)"
        post_skipped = "{skipped} items skipped due to insufficient permissions"
        post_back = "Back to main menu"
        post_exit = "Exit and close window"
        post_header = "Done  (1 back / q exit)"
    }
    ja = @{
        title = "Windowsユーザーディレクトリ クリーナー"
        mode_dry = "プレビューモード"
        mode_exec = "実行モード"
        target_dir = "対象ディレクトリ"
        scan_phase = "{name}をスキャン中..."
        exec_phase = "{name}を削除中..."
        found = "{size} 発見、{deleted} 件削除可能、{skipped} 件スキップ"
        verb_scan = "発見"
        verb_exec = "解放"
        menu_header = "カテゴリ選択  (数字トグル / a 全選択⇔全解除 / Enter 削除 / l 言語 / q 終了)"
        menu_total = "合計（選択中）"
        items_del = "件削除可"
        items_skip = "件スキップ"
        at_least_one = "少なくとも1つ選択してください"
        press_any_key = "何かキーを押してメニューへ戻る..."
        confirm = "削除を実行しますか？[y/N] "
        cancelled = "キャンセルしました。"
        done = "クリーニング完了！"
        err_no_dir = "エラー：ユーザーディレクトリが見つかりません: {path}"
        col_category = "カテゴリ"
        col_freed = "解放容量"
        col_deleted = "削除数"
        col_skipped = "スキップ"
        col_total = "合計"
        cat_cache = "キャッシュ"
        cat_installers = "インストーラー"
        cat_empty_dirs = "空フォルダ"
        lang_title = "言語選択 / Select Language / 选择语言"
        lang_hint = "数字で選択 / q メニューへ戻る"
        lang_invalid = "無効な選択です。再入力してください"
        cat_gpu_cache = "GPUシェーダーキャッシュ"
        cat_logs = "ログ・クラッシュダンプ"
        cat_system = "システムレベルキャッシュ"
        welcome_desc = "AppData 内のキャッシュ・ログ・GPUシェーダー・空フォルダ・システムレベルの不要ファイルを削除"
        welcome_lang = "言語変更"
        welcome_scan = "スキャン開始"
        welcome_quit = "終了"
        post_success = "{size} 解放、{deleted} 件削除しました"
        post_nothing = "クリーニングできたファイルはありませんでした（権限不足の可能性）"
        post_skipped = "{skipped} 件は権限不足でスキップされました"
        post_back = "メインメニューへ戻る"
        post_exit = "終了してウィンドウを閉じる"
        post_header = "完了  (1 戻る / q 終了)"
    }
}

$script:Languages = @(
    @{ Code = 'zh'; Label = '中文' }
    @{ Code = 'en'; Label = 'English' }
    @{ Code = 'ja'; Label = '日本語' }
)

function S {
    param([string]$Key, [hashtable]$P = @{})
    $t = $script:UI[$script:Lang][$Key]
    foreach ($k in $P.Keys) {
        $t = $t.Replace('{' + $k + '}', [string]$P[$k])
    }
    return $t
}

# ---------- 工具函数 ----------

function Format-Size {
    param([double]$N)
    foreach ($unit in @('B', 'KB', 'MB', 'GB', 'TB')) {
        if ($N -lt 1024) { return ('{0:F1} {1}' -f $N, $unit) }
        $N = $N / 1024
    }
    return ('{0:F1} TB' -f $N)
}

function Get-PathSize {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $item) { return 0 }
    if (-not $item.PSIsContainer) { return [long]$item.Length }
    $total = [long]0
    try {
        Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
            ForEach-Object { $total += $_.Length }
    } catch {}
    return $total
}

# ---------- 清理结果容器 ----------

function New-CleanResult {
    param([string]$Name, [string]$Key = "")
    [PSCustomObject]@{
        Name    = $Name
        Key     = $Key
        Freed   = [long]0
        Deleted = 0
        Skipped = 0
    }
}

function Get-ResultDisplayName {
    param($Result)
    if ($Result.Key) { return (S $Result.Key) }
    return $Result.Name
}

function Merge-Result {
    param($Result, [long]$Freed, [int]$Deleted, [int]$Skipped)
    $Result.Freed += $Freed
    $Result.Deleted += $Deleted
    $Result.Skipped += $Skipped
}

# ---------- 底层删除原语 ----------

function Remove-SingleItem {
    param([string]$Path, [bool]$Dry, [bool]$Detail)
    $size = Get-PathSize -Path $Path
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    $isDir = $item -and $item.PSIsContainer
    $tag = if ($isDir) { "DIR " } else { "FILE" }

    if ($Dry) {
        if ($Detail) {
            Write-Host ("    " + $script:YELLOW + "[DRY]" + $script:RESET + " " + $tag + " " + $Path + "  (" + (Format-Size $size) + ")")
        }
        return @{ Freed = $size; Skipped = 0 }
    }
    try {
        if ($isDir) {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        } else {
            Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
        }
        if ($Detail) {
            Write-Host ("    " + $script:RED + "[DEL]" + $script:RESET + " " + $tag + " " + $Path + "  (" + (Format-Size $size) + ")")
        }
        return @{ Freed = $size; Skipped = 0 }
    } catch [System.UnauthorizedAccessException] {
        if ($Detail) { Write-Host ("    " + $script:YELLOW + "[SKIP]" + $script:RESET + " " + $Path + "  (权限不足)") }
        return @{ Freed = 0; Skipped = 1 }
    } catch {
        if ($Detail) { Write-Host ("    " + $script:YELLOW + "[ERR]" + $script:RESET + "  " + $Path + "  (" + $_.Exception.Message + ")") }
        return @{ Freed = 0; Skipped = 1 }
    }
}

function Remove-DirContents {
    param([string]$Directory, [bool]$Dry, [bool]$Detail)
    if (-not (Test-Path -LiteralPath $Directory)) { return @{ Freed = 0; Deleted = 0; Skipped = 0 } }
    $freed = 0; $deleted = 0; $skipped = 0
    $children = Get-ChildItem -LiteralPath $Directory -Force -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        $res = Remove-SingleItem -Path $child.FullName -Dry $Dry -Detail $Detail
        if ($res.Skipped -gt 0) { $skipped++ } else { $freed += $res.Freed; $deleted++ }
    }
    return @{ Freed = $freed; Deleted = $deleted; Skipped = $skipped }
}

function Get-GlobMatches {
    param([string]$Base, [string]$Pattern)
    if (-not (Test-Path -LiteralPath $Base)) { return @() }
    $segments = $Pattern -split '/'
    $current = @(Get-Item -LiteralPath $Base -Force -ErrorAction SilentlyContinue)
    foreach ($seg in $segments) {
        $next = @()
        foreach ($c in $current) {
            if (-not $c -or -not $c.PSIsContainer) { continue }
            $next += @(Get-ChildItem -LiteralPath $c.FullName -Force -Filter $seg -ErrorAction SilentlyContinue)
        }
        $current = $next
    }
    return $current
}

function Remove-GlobContents {
    param([string]$Base, [string]$Pattern, [bool]$Dry, [bool]$Detail)
    $freed = 0; $deleted = 0; $skipped = 0
    foreach ($m in (Get-GlobMatches -Base $Base -Pattern $Pattern)) {
        if ($m.PSIsContainer) {
            $res = Remove-DirContents -Directory $m.FullName -Dry $Dry -Detail $Detail
            $freed += $res.Freed; $deleted += $res.Deleted; $skipped += $res.Skipped
        }
    }
    return @{ Freed = $freed; Deleted = $deleted; Skipped = $skipped }
}

function Remove-GlobFiles {
    param([string]$Base, [string]$Pattern, [bool]$Dry, [bool]$Detail)
    if (-not (Test-Path -LiteralPath $Base)) { return @{ Freed = 0; Deleted = 0; Skipped = 0 } }
    $freed = 0; $deleted = 0; $skipped = 0
    $files = Get-ChildItem -LiteralPath $Base -Filter $Pattern -File -Force -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        $res = Remove-SingleItem -Path $f.FullName -Dry $Dry -Detail $Detail
        if ($res.Skipped -gt 0) { $skipped++ } else { $freed += $res.Freed; $deleted++ }
    }
    return @{ Freed = $freed; Deleted = $deleted; Skipped = $skipped }
}

function Remove-GlobFilesRecursive {
    param([string]$Base, [string]$Pattern, [bool]$Dry, [bool]$Detail)
    if (-not (Test-Path -LiteralPath $Base)) { return @{ Freed = 0; Deleted = 0; Skipped = 0 } }
    $freed = 0; $deleted = 0; $skipped = 0
    $files = Get-ChildItem -LiteralPath $Base -Recurse -Filter $Pattern -File -Force -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        $res = Remove-SingleItem -Path $f.FullName -Dry $Dry -Detail $Detail
        if ($res.Skipped -gt 0) { $skipped++ } else { $freed += $res.Freed; $deleted++ }
    }
    return @{ Freed = $freed; Deleted = $deleted; Skipped = $skipped }
}

# ---------- UI 辅助函数 ----------

function Get-DisplayWidth {
    param([string]$Text)
    $width = 0
    foreach ($ch in $Text.ToCharArray()) {
        $cp = [int][char]$ch
        if (
            ($cp -ge 0x1100 -and $cp -le 0x115F) -or
            ($cp -eq 0x2329 -or $cp -eq 0x232A) -or
            ($cp -ge 0x2E80 -and $cp -le 0xA4CF -and $cp -ne 0x303F) -or
            ($cp -ge 0xAC00 -and $cp -le 0xD7A3) -or
            ($cp -ge 0xF900 -and $cp -le 0xFAFF) -or
            ($cp -ge 0xFE30 -and $cp -le 0xFE6F) -or
            ($cp -ge 0xFF00 -and $cp -le 0xFF60) -or
            ($cp -ge 0xFFE0 -and $cp -le 0xFFE6)
        ) {
            $width += 2
        } else {
            $width += 1
        }
    }
    return $width
}

function Pad-Text {
    param([string]$Text, [int]$Width)
    $w = Get-DisplayWidth $Text
    $pad = [Math]::Max(0, $Width - $w)
    return $Text + (" " * $pad)
}

function PadLeft-Text {
    param([string]$Text, [int]$Width)
    $w = Get-DisplayWidth $Text
    $pad = [Math]::Max(0, $Width - $w)
    return (" " * $pad) + $Text
}

function Show-ProgressBar {
    param([string]$SubLabel, [long]$Freed, [int]$Step, [int]$Width = 79)
    $barWidth = 30
    $pos = [Math]::Min($Step, $barWidth)
    $bar = "[" + ("*" * $pos) + (" " * ($barWidth - $pos)) + "]"
    $sizeStr = Format-Size $Freed
    $right = "  $sizeStr"
    $available = [Math]::Max(0, $Width - $bar.Length - $right.Length - 2)
    if ($SubLabel.Length -gt $available) {
        $cut = [Math]::Max(0, $available - 1)
        $label = $SubLabel.Substring(0, $cut) + "…"
    } else {
        $label = $SubLabel
    }
    $label = $label.PadRight($available)
    $line = $bar + "  " + $label + $right
    if ($line.Length -gt $Width) { $line = $line.Substring(0, $Width) }
    Write-Host -NoNewline ("`r" + $line)
}

function Get-CategoryMenuText {
    param([array]$Results, [array]$Selected, [string]$Status = "")
    $header = S 'menu_header'
    $nameCol = 14
    foreach ($r in $Results) {
        $w = Get-DisplayWidth (Get-ResultDisplayName -Result $r)
        if ($w -gt $nameCol) { $nameCol = $w }
    }
    $delW = 1; $skipW = 1
    foreach ($r in $Results) {
        if (([string]$r.Deleted).Length -gt $delW) { $delW = ([string]$r.Deleted).Length }
        if (([string]$r.Skipped).Length -gt $skipW) { $skipW = ([string]$r.Skipped).Length }
    }
    $sepW = [Math]::Max((Get-DisplayWidth $header) + 4, $nameCol + 36)
    $sep = "=" * $sepW
    $sep2 = "-" * $sepW
    $lines = @($sep, "  " + $header, $sep)
    $delTxt = S 'items_del'
    $skipTxt = S 'items_skip'
    for ($i = 0; $i -lt $Results.Count; $i++) {
        $r = $Results[$i]
        $sel = $Selected[$i]
        $check = if ($sel) { "✓" } else { " " }
        $name = Pad-Text (Get-ResultDisplayName -Result $r) $nameCol
        $freedStr = PadLeft-Text (Format-Size $r.Freed) 10
        $delStr = PadLeft-Text ([string]$r.Deleted) $delW
        $skipStr = PadLeft-Text ([string]$r.Skipped) $skipW
        $lines += "  [$($i+1)] $check  $name  $freedStr   $delStr $delTxt  $skipStr $skipTxt"
    }
    $lines += $sep2
    $total = 0
    for ($i = 0; $i -lt $Results.Count; $i++) { if ($Selected[$i]) { $total += $Results[$i].Freed } }
    $lines += "  " + (S 'menu_total') + ": " + (Format-Size $total)
    if ($Status) { $lines += "  " + $script:YELLOW + $Status + $script:RESET }
    $lines += "> "
    return ($lines -join "`n")
}

function Show-Table {
    param([array]$Results, [bool]$Dry)
    $colNames = @((S 'col_category'), (S 'col_freed'), (S 'col_deleted'), (S 'col_skipped'))

    $dataRows = @()
    foreach ($r in $Results) {
        $dataRows += , @((Get-ResultDisplayName -Result $r), (Format-Size $r.Freed), [string]$r.Deleted, [string]$r.Skipped)
    }
    $totalFreed = [long]0; $totalDeleted = 0; $totalSkipped = 0
    foreach ($r in $Results) { $totalFreed += $r.Freed; $totalDeleted += $r.Deleted; $totalSkipped += $r.Skipped }
    $totalRow = @((S 'col_total'), (Format-Size $totalFreed), [string]$totalDeleted, [string]$totalSkipped)

    $allRows = $dataRows + , $totalRow
    $widths = @()
    for ($c = 0; $c -lt 4; $c++) {
        $w = Get-DisplayWidth $colNames[$c]
        foreach ($row in $allRows) {
            $cw = Get-DisplayWidth $row[$c]
            if ($cw -gt $w) { $w = $cw }
        }
        $widths += $w
    }

    function Cell($text, $idx) { return " " + (Pad-Text $text $widths[$idx]) + " " }
    function RowLine($cells) {
        $parts = @()
        for ($i = 0; $i -lt $cells.Count; $i++) { $parts += (Cell $cells[$i] $i) }
        return "║" + ($parts -join "║") + "║"
    }
    function DivLine($l, $m, $r, $fill = "═") {
        $parts = @()
        foreach ($w in $widths) { $parts += ($fill * ($w + 2)) }
        return $l + ($parts -join $m) + $r
    }

    Write-Host (DivLine "╔" "╦" "╗")
    Write-Host (RowLine $colNames)
    Write-Host (DivLine "╠" "╬" "╣")
    foreach ($row in $dataRows) { Write-Host (RowLine $row) }
    Write-Host (DivLine "╠" "╬" "╣")
    Write-Host (RowLine $totalRow)
    Write-Host (DivLine "╚" "╩" "╝")
}

function Get-LangMenuText {
    param([string]$Status = "")
    $sep = "=" * 60
    $sep2 = "-" * 60
    $lines = @($sep, "  " + (S 'lang_title'), "  (" + (S 'lang_hint') + ")", $sep)
    for ($i = 0; $i -lt $script:Languages.Count; $i++) {
        $entry = $script:Languages[$i]
        $marker = if ($entry.Code -eq $script:Lang) { "●" } else { " " }
        $lines += "  [$($i+1)] $marker  $($entry.Label)"
    }
    $lines += $sep2
    if ($Status) { $lines += "  " + $script:YELLOW + $Status + $script:RESET }
    $lines += "> "
    return ($lines -join "`n")
}

function Clear-PendingKeys {
    while ([Console]::KeyAvailable) { [Console]::ReadKey($true) | Out-Null }
}

function Test-CtrlC {
    param($Key)
    return ($Key.Key -eq [ConsoleKey]::C -and ($Key.Modifiers -band [ConsoleModifiers]::Control))
}

function Select-Language {
    Clear-PendingKeys
    $status = ""
    $menuText = Get-LangMenuText $status
    Write-Host -NoNewline $menuText

    while ($true) {
        $key = [Console]::ReadKey($true)
        if (Test-CtrlC $key) { Write-Host ""; exit 0 }
        if ($key.Key -in @([ConsoleKey]::UpArrow, [ConsoleKey]::DownArrow, [ConsoleKey]::LeftArrow, [ConsoleKey]::RightArrow)) { continue }
        $ch = ([string]$key.KeyChar).ToLower()

        if ($ch -eq 'q') { Write-Host ""; return }
        elseif ($ch -match '^[123]$') {
            $idx = [int]$ch - 1
            if ($idx -lt $script:Languages.Count) {
                $script:Lang = $script:Languages[$idx].Code
                Write-Host ""
                return
            } else {
                $status = S 'lang_invalid'
            }
        } else {
            $status = S 'lang_invalid'
        }

        $nUp = ([regex]::Matches($menuText, "`n")).Count
        Write-Host -NoNewline ($script:ESC + "[${nUp}A`r" + $script:ESC + "[J")
        $menuText = Get-LangMenuText $status
        Write-Host -NoNewline (($menuText -replace "`n", ($script:ESC + "[K`n")) + $script:ESC + "[K")
    }
}

# ---------- 欢迎界面 ----------

$script:WelcomeArt = @(
    "  ____  _     _____    _    _   _   _   _ ____ "
    " / ___|| |   | ____|  / \  | \ | | | | | |  _ \"
    "| |    | |   |  _|   / _ \ |  \| | | | | | |_) |"
    "| |___ | |___| |___ / ___ \| |\  | | |_| |  __/ "
    " \____||_____|_____/_/   \_\_| \_|  \___/ |_|   "
)

function Get-WelcomeText {
    $sep = "=" * 62
    $sep2 = "-" * 62
    $lines = @($sep, "")
    for ($i = 0; $i -lt $script:WelcomeArt.Count; $i++) {
        $color = $script:RAINBOW[$i % $script:RAINBOW.Count]
        $lines += "  " + $color + $script:WelcomeArt[$i] + $script:RESET
    }
    $lines += ""
    $lines += "  " + (Get-RainbowWords (S 'welcome_desc'))
    $lines += "  " + $script:CYAN + "v" + $script:VERSION + $script:RESET
    $lines += ""
    $lines += $sep2
    $lines += "  [1]  Change Language / 切换语言 / 言語変更"
    $lines += "  [2]  " + (S 'welcome_scan')
    $lines += "  [q]  " + (S 'welcome_quit')
    $lines += $sep
    $lines += "> "
    return ($lines -join "`n")
}

function Show-Welcome {
    while ($true) {
        Clear-HostSafe
        Write-Host -NoNewline (Get-WelcomeText)
        Clear-PendingKeys

        $handled = $false
        while (-not $handled) {
            $key = [Console]::ReadKey($true)
            if (Test-CtrlC $key) { Write-Host ""; exit 0 }
            if ($key.Key -in @([ConsoleKey]::UpArrow, [ConsoleKey]::DownArrow, [ConsoleKey]::LeftArrow, [ConsoleKey]::RightArrow)) { continue }
            $ch = ([string]$key.KeyChar).ToLower()

            if ($ch -eq '1') {
                Write-Host ""
                Clear-HostSafe
                Select-Language
                $handled = $true  # re-render welcome (possibly new language)
            } elseif ($ch -eq '2') {
                Write-Host ""
                return
            } elseif ($ch -eq 'q') {
                Write-Host ""
                Exit-AndClose
            }
        }
    }
}

# ---------- 分类菜单 ----------

function Select-CategoryMenu {
    param([array]$Results, $Initial)
    Clear-PendingKeys

    if ($Initial) {
        $selected = @($Initial)
    } else {
        $selected = @($Results | ForEach-Object { ($_.Freed -gt 0) -or ($_.Deleted -gt 0) })
    }
    $status = ""
    $menuText = Get-CategoryMenuText -Results $Results -Selected $selected -Status $status
    Write-Host -NoNewline $menuText

    while ($true) {
        $key = [Console]::ReadKey($true)
        if (Test-CtrlC $key) { Write-Host ""; exit 0 }
        if ($key.Key -in @([ConsoleKey]::UpArrow, [ConsoleKey]::DownArrow, [ConsoleKey]::LeftArrow, [ConsoleKey]::RightArrow)) { continue }
        $ch = ([string]$key.KeyChar).ToLower()
        $redraw = $false

        if ($ch -match '^[1-9]$') {
            $idx = [int]$ch - 1
            if ($idx -lt $Results.Count) {
                $selected[$idx] = -not $selected[$idx]
                $status = ""
                $redraw = $true
            }
        } elseif ($ch -eq 'a') {
            if (($selected -contains $false) -eq $false) {
                $selected = @($Results | ForEach-Object { $false })
            } else {
                $selected = @($Results | ForEach-Object { $true })
            }
            $status = ""
            $redraw = $true
        } elseif ($key.Key -eq [ConsoleKey]::Enter) {
            if (-not ($selected -contains $true)) {
                $status = S 'at_least_one'
                $redraw = $true
            } else {
                Write-Host ""
                return $selected
            }
        } elseif ($ch -eq 'l') {
            Clear-HostSafe
            Select-Language
            Clear-HostSafe
            $status = ""
            $menuText = Get-CategoryMenuText -Results $Results -Selected $selected -Status $status
            Write-Host -NoNewline $menuText
        } elseif ($ch -eq 'q') {
            Write-Host ""
            Exit-AndClose
        }

        if ($redraw) {
            $nUp = ([regex]::Matches($menuText, "`n")).Count
            Write-Host -NoNewline ($script:ESC + "[${nUp}A`r" + $script:ESC + "[J")
            $menuText = Get-CategoryMenuText -Results $Results -Selected $selected -Status $status
            Write-Host -NoNewline (($menuText -replace "`n", ($script:ESC + "[K`n")) + $script:ESC + "[K")
        }
    }
}

# ---------- 清理结果后菜单 ----------

function Show-PostMenu {
    param([long]$TotalFreed, [int]$TotalDeleted, [int]$TotalSkipped)
    $sep = "=" * 62
    $sep2 = "-" * 62

    if ($TotalDeleted -gt 0) {
        $resultColor = $script:GREEN
        $resultMsg = S 'post_success' @{ size = (Format-Size $TotalFreed); deleted = $TotalDeleted }
    } else {
        $resultColor = $script:YELLOW
        $resultMsg = S 'post_nothing'
    }

    $lines = @("", $sep, "  " + $resultColor + $script:BOLD + $resultMsg + $script:RESET)
    if ($TotalSkipped -gt 0) {
        $lines += "  " + $script:YELLOW + (S 'post_skipped' @{ skipped = $TotalSkipped }) + $script:RESET
    }
    $lines += $sep2
    $lines += "  [1]  " + (S 'post_back')
    $lines += "  [q]  " + (S 'post_exit')
    $lines += $sep
    $lines += "> "
    Write-Host -NoNewline ($lines -join "`n")

    Clear-PendingKeys
    while ($true) {
        $key = [Console]::ReadKey($true)
        if (Test-CtrlC $key) { Write-Host ""; exit 0 }
        $ch = ([string]$key.KeyChar).ToLower()
        if ($ch -eq '1') { Write-Host ""; return 'back' }
        elseif ($ch -eq 'q') { Write-Host ""; return 'exit' }
    }
}

# ---------- 六大清理模块 ----------

function Invoke-CleanCache {
    param([string]$UserDir, [bool]$Dry, [bool]$Detail, [scriptblock]$ProgressCb)
    $r = New-CleanResult -Name "缓存文件" -Key "cat_cache"
    $loc = "$UserDir\AppData\Local"
    $roam = "$UserDir\AppData\Roaming"

    $tasks = @(
        @{ Label = 'Windows Temp';               Type = 'DirContents';  Path = "$loc\Temp" }
        @{ Label = 'INetCache';                  Type = 'DirContents';  Path = "$loc\Microsoft\Windows\INetCache" }
        @{ Label = 'WebCache';                   Type = 'DirContents';  Path = "$loc\Microsoft\Windows\WebCache" }
        @{ Label = '最近使用的文件快捷方式';      Type = 'GlobFiles';    Path = "$roam\Microsoft\Windows\Recent"; Pattern = '*.lnk' }
        @{ Label = '缩略图缓存';                  Type = 'GlobFiles';    Path = "$loc\Microsoft\Windows\Explorer"; Pattern = 'thumbcache_*.db' }
        @{ Label = 'Chrome Cache';               Type = 'GlobContents'; Path = "$loc\Google\Chrome\User Data"; Pattern = '*/Cache' }
        @{ Label = 'Chrome Code Cache';          Type = 'GlobContents'; Path = "$loc\Google\Chrome\User Data"; Pattern = '*/Code Cache' }
        @{ Label = 'Edge Cache';                 Type = 'GlobContents'; Path = "$loc\Microsoft\Edge\User Data"; Pattern = '*/Cache' }
        @{ Label = 'Edge Code Cache';            Type = 'GlobContents'; Path = "$loc\Microsoft\Edge\User Data"; Pattern = '*/Code Cache' }
        @{ Label = 'Firefox Cache';              Type = 'GlobContents'; Path = "$loc\Mozilla\Firefox\Profiles"; Pattern = '*/cache2' }
        @{ Label = 'Teams Cache';                Type = 'DirContents';  Path = "$roam\Microsoft\Teams\Cache" }
        @{ Label = 'Teams blob_storage';         Type = 'DirContents';  Path = "$roam\Microsoft\Teams\blob_storage" }
        @{ Label = 'Teams GPUCache';             Type = 'DirContents';  Path = "$roam\Microsoft\Teams\GPUCache" }
        @{ Label = 'Discord Cache';              Type = 'DirContents';  Path = "$roam\discord\Cache" }
        @{ Label = 'Discord Code Cache';         Type = 'DirContents';  Path = "$roam\discord\Code Cache" }
        @{ Label = 'Spotify Cache';              Type = 'DirContents';  Path = "$loc\Spotify\Storage" }
        @{ Label = 'pip Cache';                  Type = 'DirContents';  Path = "$loc\pip\cache" }
        @{ Label = 'npm Cache';                  Type = 'DirContents';  Path = "$loc\npm-cache" }
        @{ Label = 'Yarn Cache';                 Type = 'DirContents';  Path = "$loc\Yarn\Cache" }
        @{ Label = 'VS Code CachedData';         Type = 'DirContents';  Path = "$roam\Code\CachedData" }
        @{ Label = 'VS Code Cache';              Type = 'DirContents';  Path = "$roam\Code\Cache" }
        @{ Label = 'VS Code GPUCache';           Type = 'DirContents';  Path = "$roam\Code\GPUCache" }
        @{ Label = 'Cursor CachedData';          Type = 'DirContents';  Path = "$roam\Cursor\CachedData" }
        @{ Label = 'Cursor Cache';               Type = 'DirContents';  Path = "$roam\Cursor\Cache" }
        @{ Label = 'Cursor GPUCache';            Type = 'DirContents';  Path = "$roam\Cursor\GPUCache" }
        @{ Label = 'Discord GPUCache';           Type = 'DirContents';  Path = "$roam\discord\GPUCache" }
        @{ Label = 'Calibre 缓存';                Type = 'DirContents';  Path = "$loc\calibre-cache" }
        @{ Label = 'Steam htmlcache';            Type = 'DirContents';  Path = "$loc\Steam\htmlcache" }
        @{ Label = 'Battle.net htmlcache';       Type = 'GlobContents'; Path = "$loc\Battle.net"; Pattern = '*/Cache' }
        @{ Label = 'EA Desktop Cache';           Type = 'GlobContents'; Path = "$loc\EADesktop"; Pattern = '*/webcache' }
        @{ Label = 'Quark Cache';                Type = 'GlobContents'; Path = "$loc\Quark\User Data"; Pattern = '*/Cache' }
        @{ Label = 'Quark Code Cache';           Type = 'GlobContents'; Path = "$loc\Quark\User Data"; Pattern = '*/Code Cache' }
        @{ Label = 'Zoom WebCache';              Type = 'DirContents';  Path = "$roam\Zoom\data\WebviewCacheX64" }
        @{ Label = 'QQ 临时系统缓存';             Type = 'DirContents';  Path = "$roam\Tencent\QQTempSys" }
        @{ Label = '*-updater 暂存目录';          Type = 'GlobContents'; Path = $loc; Pattern = '*-updater' }
        @{ Label = 'WER ReportArchive';          Type = 'DirContents';  Path = "$loc\Microsoft\Windows\WER\ReportArchive" }
        @{ Label = 'WER ReportQueue';            Type = 'DirContents';  Path = "$loc\Microsoft\Windows\WER\ReportQueue" }
    )

    foreach ($t in $tasks) {
        if (-not $Detail -and $ProgressCb) { & $ProgressCb $t.Label $r.Freed }
        if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $t.Label + $script:RESET) }
        $res = switch ($t.Type) {
            'DirContents'  { Remove-DirContents  -Directory $t.Path -Dry $Dry -Detail $Detail }
            'GlobContents' { Remove-GlobContents -Base $t.Path -Pattern $t.Pattern -Dry $Dry -Detail $Detail }
            'GlobFiles'    { Remove-GlobFiles    -Base $t.Path -Pattern $t.Pattern -Dry $Dry -Detail $Detail }
        }
        Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
    }

    return $r
}

function Invoke-CleanInstallers {
    param([string]$UserDir, [bool]$Dry, [bool]$Detail, [scriptblock]$ProgressCb)
    $r = New-CleanResult -Name "安装包文件" -Key "cat_installers"
    $loc = "$UserDir\AppData\Local"
    $temp = "$loc\Temp"
    $installerExts = @('*.exe', '*.msi', '*.msp', '*.cab', '*.pkg', '*.msix')

    if (-not $Detail -and $ProgressCb) { & $ProgressCb "Temp 目录安装包" $r.Freed }
    if ($Detail) { Write-Host ("  " + $script:CYAN + "→ Temp 目录安装包" + $script:RESET) }
    foreach ($pat in $installerExts) {
        $res = Remove-GlobFiles -Base $temp -Pattern $pat -Dry $Dry -Detail $Detail
        Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
    }

    if (-not $Detail -and $ProgressCb) { & $ProgressCb "WinGet 临时下载" $r.Freed }
    if ($Detail) { Write-Host ("  " + $script:CYAN + "→ WinGet 临时下载" + $script:RESET) }
    foreach ($wt in @("$temp\WinGet", "$temp\winget")) {
        $res = Remove-DirContents -Directory $wt -Dry $Dry -Detail $Detail
        Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
    }

    if (-not $Detail -and $ProgressCb) { & $ProgressCb "Teams 旧版本文件" $r.Freed }
    if ($Detail) { Write-Host ("  " + $script:CYAN + "→ Teams 旧版本文件" + $script:RESET) }
    $teamsDir = "$loc\Microsoft\Teams"
    if (Test-Path -LiteralPath $teamsDir) {
        $prevItems = Get-ChildItem -LiteralPath $teamsDir -Filter 'previous' -Force -ErrorAction SilentlyContinue
        foreach ($old in $prevItems) {
            $res = Remove-SingleItem -Path $old.FullName -Dry $Dry -Detail $Detail
            if ($res.Skipped -gt 0) { $r.Skipped++ } else { $r.Freed += $res.Freed; $r.Deleted++ }
        }
    }

    if (-not $Detail -and $ProgressCb) { & $ProgressCb "UWP TempState" $r.Freed }
    if ($Detail) { Write-Host ("  " + $script:CYAN + "→ UWP TempState" + $script:RESET) }
    $res = Remove-GlobContents -Base "$loc\Packages" -Pattern '*/TempState' -Dry $Dry -Detail $Detail
    Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped

    $squirrelRoots = @("$loc\Discord", "$loc\slack", "$loc\GitHubDesktop")
    foreach ($root in $squirrelRoots) {
        if (Test-Path -LiteralPath $root) {
            $label = "Squirrel 旧包: " + (Split-Path -Leaf $root)
            if (-not $Detail -and $ProgressCb) { & $ProgressCb $label $r.Freed }
            if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $label + $script:RESET) }
            $nupkgs = Get-ChildItem -LiteralPath $root -Recurse -Filter '*.nupkg' -File -Force -ErrorAction SilentlyContinue |
                Where-Object { $_.Directory.Name -in @('packages', 'nupkg') }
            foreach ($n in $nupkgs) {
                $res = Remove-SingleItem -Path $n.FullName -Dry $Dry -Detail $Detail
                if ($res.Skipped -gt 0) { $r.Skipped++ } else { $r.Freed += $res.Freed; $r.Deleted++ }
            }
        }
    }

    return $r
}

function Invoke-CleanGpuCache {
    param([string]$UserDir, [bool]$Dry, [bool]$Detail, [scriptblock]$ProgressCb)
    $r = New-CleanResult -Name "GPU着色器缓存" -Key "cat_gpu_cache"
    $loc = "$UserDir\AppData\Local"

    $tasks = @(
        @{ Label = 'NVIDIA DXCache';       Type = 'DirContents';  Path = "$loc\NVIDIA\DXCache" }
        @{ Label = 'NVIDIA GLCache';       Type = 'DirContents';  Path = "$loc\NVIDIA\GLCache" }
        @{ Label = 'D3DSCache';            Type = 'DirContents';  Path = "$loc\D3DSCache" }
        @{ Label = 'NVIDIA App Cache';     Type = 'GlobContents'; Path = "$loc\NVIDIA Corporation\NVIDIA App"; Pattern = '*/cache' }
        @{ Label = 'NVIDIA Overlay Cache'; Type = 'GlobContents'; Path = "$loc\NVIDIA Corporation\NVIDIA Overlay"; Pattern = '*/cache' }
    )

    foreach ($t in $tasks) {
        if (-not $Detail -and $ProgressCb) { & $ProgressCb $t.Label $r.Freed }
        if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $t.Label + $script:RESET) }
        $res = switch ($t.Type) {
            'DirContents'  { Remove-DirContents  -Directory $t.Path -Dry $Dry -Detail $Detail }
            'GlobContents' { Remove-GlobContents -Base $t.Path -Pattern $t.Pattern -Dry $Dry -Detail $Detail }
        }
        Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
    }

    return $r
}

function Invoke-CleanLogs {
    param([string]$UserDir, [bool]$Dry, [bool]$Detail, [scriptblock]$ProgressCb)
    $r = New-CleanResult -Name "日志与崩溃转储" -Key "cat_logs"
    $loc = "$UserDir\AppData\Local"
    $roam = "$UserDir\AppData\Roaming"

    $dumpDirs = @(
        "$loc\CrashDumps", "$loc\CrashFiles", "$loc\Microsoft\Windows\WER\Temp", "$loc\Temp",
        "$loc\Activision", "$loc\Google\Chrome\User Data\Crashpad\reports",
        "$loc\Microsoft\Edge\User Data\Crashpad\reports"
    )
    $dumpPatterns = @('*.dmp', '*.mdmp', '*.hdmp', '*.rpt')

    foreach ($d in $dumpDirs) {
        $dName = Split-Path -Leaf $d
        $label = "崩溃转储 $dName"
        if (-not $Detail -and $ProgressCb) { & $ProgressCb $label $r.Freed }
        if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $label + $script:RESET) }
        if (Test-Path -LiteralPath $d) {
            foreach ($pat in $dumpPatterns) {
                $res = if ($dName -eq 'Activision') {
                    Remove-GlobFilesRecursive -Base $d -Pattern $pat -Dry $Dry -Detail $Detail
                } else {
                    Remove-GlobFiles -Base $d -Pattern $pat -Dry $Dry -Detail $Detail
                }
                Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
            }
        }
    }

    $fullLogDirs = @("$roam\Tencent\Logs")
    foreach ($d in $fullLogDirs) {
        $label = "日志目录 " + (Split-Path -Leaf $d)
        if (-not $Detail -and $ProgressCb) { & $ProgressCb $label $r.Freed }
        if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $label + $script:RESET) }
        $res = Remove-DirContents -Directory $d -Dry $Dry -Detail $Detail
        Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
    }

    $logTasks = @(
        @{ Label = 'Temp *.log';                Base = "$loc\Temp"; Pattern = '*.log' }
        @{ Label = 'PowerToys 日志';             Base = "$loc\Microsoft\PowerToys"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'OneDrive 日志';              Base = "$loc\Microsoft\OneDrive\logs"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'OneDrive 安装日志';          Base = "$loc\Microsoft\OneDrive\setup\logs"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'MSIPC 日志';                 Base = "$loc\Microsoft\MSIPC\Logs"; Pattern = '*.log' }
        @{ Label = '新版 Outlook 日志';          Base = "$loc\Microsoft\Olk\logs"; Pattern = '*.log' }
        @{ Label = 'Xbox Gaming 日志';           Base = "$loc\Packages\Microsoft.GamingApp_8wekyb3d8bbwe\LocalState\Logs"; Pattern = '*.log' }
        @{ Label = 'Xbox Services 日志';         Base = "$loc\Packages\Microsoft.GamingServices_8wekyb3d8bbwe\LocalState\Logs"; Pattern = '*.log' }
        @{ Label = 'Steam 日志';                 Base = "$loc\Steam"; Pattern = '*.log' }
        @{ Label = 'Battle.net 日志';            Base = "$loc\Battle.net"; Pattern = '*.log' }
        @{ Label = 'EA Desktop 日志';            Base = "$loc\Electronic Arts"; Pattern = '*.log'; Recurse = $true }
        @{ Label = '鸣潮 日志';                  Base = "$loc\PioneerGame\Saved\Logs"; Pattern = '*.log' }
        @{ Label = 'Discord 日志';               Base = "$roam\discord\logs"; Pattern = '*.log' }
        @{ Label = 'QQ 日志';                    Base = "$roam\QQ\log"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'QQ Crashpad 日志';           Base = "$roam\QQ\Crashpad"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'QQEX 日志';                  Base = "$roam\QQEX"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'Tencent 日志';               Base = "$roam\Tencent"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'Teams 日志';                 Base = "$loc\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\Logs"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'Zoom 日志';                  Base = "$roam\Zoom\logs"; Pattern = '*.log' }
        @{ Label = 'Quark ulog';                 Base = "$loc\Quark\User Data\ulog"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'VS Code 日志';               Base = "$roam\Code\logs"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'Cursor 日志';                Base = "$roam\Cursor\logs"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'NVIDIA 日志';                Base = "$loc\NVIDIA Corporation"; Pattern = '*.log'; Recurse = $true }
        @{ Label = 'qBittorrent 日志';           Base = "$loc\qBittorrent"; Pattern = '*.log' }
        @{ Label = 'Spotify Launcher 日志';      Base = "$loc\Packages\SpotifyAB.SpotifyMusic_zpdnekdrzrea0\LocalCache\Spotify\Launcher\Logs"; Pattern = '*.log' }
        @{ Label = 'leigod 日志';                Base = "$roam\leigod"; Pattern = '*.log' }
        @{ Label = '百度网盘 日志';              Base = "$roam\baidu"; Pattern = '*.log'; Recurse = $true }
        @{ Label = '百度云管家 日志';            Base = "$roam\BaiduYunGuanjia\logs"; Pattern = '*.log' }
        @{ Label = 'clash_win 日志';             Base = "$roam\clash_win\logs"; Pattern = '*.log' }
        @{ Label = 'HMCL 日志';                  Base = "$roam\.hmcl\logs"; Pattern = '*.log' }
        @{ Label = 'Minecraft Bedrock 日志';     Base = "$roam\Minecraft Bedrock\logs"; Pattern = '*.log' }
    )

    foreach ($t in $logTasks) {
        if (-not $Detail -and $ProgressCb) { & $ProgressCb $t.Label $r.Freed }
        if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $t.Label + $script:RESET) }
        $res = if ($t.Recurse) {
            Remove-GlobFilesRecursive -Base $t.Base -Pattern $t.Pattern -Dry $Dry -Detail $Detail
        } else {
            Remove-GlobFiles -Base $t.Base -Pattern $t.Pattern -Dry $Dry -Detail $Detail
        }
        Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
    }

    $squirrelRoots = @("$loc\Discord", "$loc\slack", "$loc\GitHubDesktop")
    foreach ($root in $squirrelRoots) {
        if (Test-Path -LiteralPath $root) {
            $label = "Squirrel 安装日志: " + (Split-Path -Leaf $root)
            if (-not $Detail -and $ProgressCb) { & $ProgressCb $label $r.Freed }
            if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $label + $script:RESET) }
            $res = Remove-GlobFiles -Base $root -Pattern '*.log' -Dry $Dry -Detail $Detail
            Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
        }
    }

    return $r
}

function Invoke-CleanEmptyDirs {
    param([string]$UserDir, [bool]$Dry, [bool]$Detail, [scriptblock]$ProgressCb)
    $r = New-CleanResult -Name "空文件夹" -Key "cat_empty_dirs"

    $scanRoots = @("$UserDir\AppData\Local", "$UserDir\AppData\Roaming", "$UserDir\AppData\LocalLow")

    foreach ($root in $scanRoots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        $children = Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue
        foreach ($d in $children) {
            if (-not $d.PSIsContainer) { continue }
            if (-not $Detail -and $ProgressCb) { & $ProgressCb $d.FullName $r.Freed }
            $inner = Get-ChildItem -LiteralPath $d.FullName -Force -ErrorAction SilentlyContinue
            if (@($inner).Count -eq 0) {
                if ($Detail) { Write-Host ("  " + $script:CYAN + "→ 空目录: " + $d.FullName + $script:RESET) }
                $res = Remove-SingleItem -Path $d.FullName -Dry $Dry -Detail $Detail
                if ($res.Skipped -gt 0) { $r.Skipped++ } else { $r.Freed += $res.Freed; $r.Deleted++ }
            }
        }
    }

    return $r
}

function Invoke-EmptyRecycleBin {
    param([bool]$Dry, [bool]$Detail)
    $binPath = "$($env:SystemDrive)\`$Recycle.Bin"
    $size = Get-PathSize -Path $binPath
    if ($Dry) {
        if ($Detail -and $size) { Write-Host ("    " + $script:YELLOW + "[DRY]" + $script:RESET + " 回收站  (" + (Format-Size $size) + ")") }
        return @{ Freed = $size; Deleted = 0; Skipped = 0 }
    }
    try {
        $shell = New-Object -ComObject Shell.Application
        $shell.Namespace(0xA).Items() | ForEach-Object { Remove-Item -LiteralPath $_.Path -Recurse -Force -ErrorAction SilentlyContinue }
        if ($Detail -and $size) { Write-Host ("    " + $script:RED + "[DEL]" + $script:RESET + " 回收站  (" + (Format-Size $size) + ")") }
        return @{ Freed = $size; Deleted = $(if ($size) { 1 } else { 0 }); Skipped = 0 }
    } catch {
        if ($Detail) { Write-Host ("    " + $script:YELLOW + "[ERR]" + $script:RESET + "  回收站  (" + $_.Exception.Message + ")") }
        return @{ Freed = 0; Deleted = 0; Skipped = 1 }
    }
}

function Invoke-CleanSystem {
    param([string]$UserDir, [bool]$Dry, [bool]$Detail, [scriptblock]$ProgressCb)
    $r = New-CleanResult -Name "系统级缓存" -Key "cat_system"
    $sysDrive = "$($env:SystemDrive)\"
    $winDir = if ($env:SystemRoot) { $env:SystemRoot } else { "$sysDrive" + "Windows" }

    $tasks = @(
        @{ Label = 'Windows Temp（系统）';       Path = "$winDir\Temp" }
        @{ Label = 'Windows Update 下载缓存';   Path = "$winDir\SoftwareDistribution\Download" }
    )
    foreach ($t in $tasks) {
        if (-not $Detail -and $ProgressCb) { & $ProgressCb $t.Label $r.Freed }
        if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $t.Label + $script:RESET) }
        $res = Remove-DirContents -Directory $t.Path -Dry $Dry -Detail $Detail
        Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped
    }

    $label = "回收站"
    if (-not $Detail -and $ProgressCb) { & $ProgressCb $label $r.Freed }
    if ($Detail) { Write-Host ("  " + $script:CYAN + "→ " + $label + $script:RESET) }
    $res = Invoke-EmptyRecycleBin -Dry $Dry -Detail $Detail
    Merge-Result -Result $r -Freed $res.Freed -Deleted $res.Deleted -Skipped $res.Skipped

    return $r
}

# ---------- 主流程 ----------

Enable-Vt

$explicit = $Cache -or $Installers -or $GpuCache -or $Logs -or $EmptyDirs -or $System

while ($true) {
    if (-not $explicit) {
        Show-Welcome
        Clear-HostSafe
    }

    $dry = -not $Execute

    if ($UserPath) {
        $userDir = $UserPath
    } else {
        $userDir = $env:USERPROFILE
    }

    if (-not (Test-Path -LiteralPath $userDir)) {
        Write-Host ($script:RED + (S 'err_no_dir' @{ path = $userDir }) + $script:RESET)
        exit 1
    }

    $categories = @()
    if ($Cache -or -not $explicit) { $categories += @{ Key = 'cat_cache'; Fn = { param($u, $d, $v, $cb) Invoke-CleanCache -UserDir $u -Dry $d -Detail $v -ProgressCb $cb } } }
    if ($Installers -or -not $explicit) { $categories += @{ Key = 'cat_installers'; Fn = { param($u, $d, $v, $cb) Invoke-CleanInstallers -UserDir $u -Dry $d -Detail $v -ProgressCb $cb } } }
    if ($GpuCache -or -not $explicit) { $categories += @{ Key = 'cat_gpu_cache'; Fn = { param($u, $d, $v, $cb) Invoke-CleanGpuCache -UserDir $u -Dry $d -Detail $v -ProgressCb $cb } } }
    if ($Logs -or -not $explicit) { $categories += @{ Key = 'cat_logs'; Fn = { param($u, $d, $v, $cb) Invoke-CleanLogs -UserDir $u -Dry $d -Detail $v -ProgressCb $cb } } }
    if ($EmptyDirs -or -not $explicit) { $categories += @{ Key = 'cat_empty_dirs'; Fn = { param($u, $d, $v, $cb) Invoke-CleanEmptyDirs -UserDir $u -Dry $d -Detail $v -ProgressCb $cb } } }
    if ($System -or -not $explicit) { $categories += @{ Key = 'cat_system'; Fn = { param($u, $d, $v, $cb) Invoke-CleanSystem -UserDir $u -Dry $d -Detail $v -ProgressCb $cb } } }

    $modeLabel = if ($dry) { $script:YELLOW + (S 'mode_dry') + $script:RESET } else { $script:RED + (S 'mode_exec') + $script:RESET }
    Write-Host ""
    Write-Host ($script:BOLD + (S 'title') + $script:RESET + "  [" + $modeLabel + "]")
    Write-Host ((S 'target_dir') + ": " + $script:CYAN + $userDir + $script:RESET)
    Write-Host ""

    # Phase 1: dry scan
    $totalCats = $categories.Count
    $scanResults = @()
    for ($i = 0; $i -lt $totalCats; $i++) {
        $cat = $categories[$i]
        $name = S $cat.Key
        $prefix = "[$($i+1)/$totalCats] " + (S 'scan_phase' @{ name = $name })
        Write-Host ($script:BOLD + $prefix + $script:RESET)

        $stepRef = [ref]0
        $cb = {
            param($label, $freed)
            if (-not $Detail) {
                $stepRef.Value++
                Show-ProgressBar -SubLabel $label -Freed $freed -Step $stepRef.Value
            }
        }.GetNewClosure()

        $r = & $cat.Fn $userDir $true $Detail $cb
        if (-not $Detail) { Write-Host "" }
        Write-Host ("  " + (S 'found' @{ size = (Format-Size $r.Freed); deleted = $r.Deleted; skipped = $r.Skipped }) + "`n")
        $scanResults += $r
    }

    # Phase 2: category selection
    $active = @()
    if ($explicit) {
        for ($i = 0; $i -lt $categories.Count; $i++) {
            $active += @{ Cat = $categories[$i]; Result = $scanResults[$i] }
        }
        if ($dry) {
            Show-Table -Results ($active | ForEach-Object { $_.Result }) -Dry $true
            exit 0
        }
    } else {
        $lastSelected = $null
        Clear-HostSafe
        while ($true) {
            $selected = Select-CategoryMenu -Results $scanResults -Initial $lastSelected
            $dry = $false
            $active = @()
            for ($i = 0; $i -lt $categories.Count; $i++) {
                if ($selected[$i]) { $active += @{ Cat = $categories[$i]; Result = $scanResults[$i] } }
            }
            if ($Yes) { break }
            Write-Host ""
            $answer = Read-Host ($script:YELLOW + (S 'confirm') + $script:RESET)
            if ($answer.Trim().ToLower() -eq 'y') { break }
            $lastSelected = $selected
            Clear-HostSafe
        }
    }

    # Phase 3: execute
    Write-Host ""
    $execTotal = $active.Count
    $execResults = @()
    for ($i = 0; $i -lt $execTotal; $i++) {
        $cat = $active[$i].Cat
        $name = S $cat.Key
        $prefix = "[$($i+1)/$execTotal] " + (S 'exec_phase' @{ name = $name })
        Write-Host ($script:BOLD + $prefix + $script:RESET)

        $stepRef = [ref]0
        $cb = {
            param($label, $freed)
            if (-not $Detail) {
                $stepRef.Value++
                Show-ProgressBar -SubLabel $label -Freed $freed -Step $stepRef.Value
            }
        }.GetNewClosure()

        $r = & $cat.Fn $userDir $false $Detail $cb
        if (-not $Detail) { Write-Host "" }
        $execResults += $r
    }

    Clear-HostSafe
    Show-Table -Results $execResults -Dry $false

    if ($explicit) { exit 0 }

    $totalFreed = [long]0; $totalDeleted = 0; $totalSkipped = 0
    foreach ($r in $execResults) { $totalFreed += $r.Freed; $totalDeleted += $r.Deleted; $totalSkipped += $r.Skipped }

    $action = Show-PostMenu -TotalFreed $totalFreed -TotalDeleted $totalDeleted -TotalSkipped $totalSkipped
    if ($action -eq 'exit') { Exit-AndClose }
    Clear-HostSafe
}
