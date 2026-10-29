#Requires -Version 7.0

<#
.SYNOPSIS
    Remove auto generate Program Files folder.
.DESCRIPTION
    Remove auto generate Program Files folder.
.PARAMETER NAME
    None.
.INPUTS
    None. The script does not take any input objects.
.OUTPUTS
    None. The script does not take any output objects.
.NOTES
    Ensure that run Administrators. This SEIZES OWNERSHIP and force-deletes the
    three directories on the target drive -- check the drive letter first.
.PARAMETER Drive
    Drive to clean, e.g. "D:". Defaults to D:.
#>
[CmdletBinding()]
param([ValidatePattern('^[A-Za-z]:$')][string]$Drive = 'D:')

$dirs = @("$Drive\Program Files", "$Drive\WindowsApps", "$Drive\WpSystem")
Get-AppxVolume | Where-Object { $_.PackageStorePath -like "$Drive*" } | Remove-AppxVolume
foreach ($d in $dirs) {
  if (Test-Path -LiteralPath $d) {
    icacls $d /setowner Administrators /T /C /L /Q | Out-Null
    icacls $d /grant '*S-1-5-32-544:(F)' /T /C /L /Q | Out-Null
    Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue
  }
}
$dirs | ForEach-Object { "{0}  Still? {1}" -f $_, (Test-Path -LiteralPath $_) }
