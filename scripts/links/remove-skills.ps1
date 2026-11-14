#Requires -Version 5.1

<#
.SYNOPSIS
Removes selected repository skill junctions from a native Windows project.

.DESCRIPTION
Removes only junctions managed by this repository. Missing targets are ignored, while ordinary
directories, files, and junctions owned by another source are preserved.

.PARAMETER Target
Path to the target project. It must not be this skill repository.

.PARAMETER Skills
Optional skill names. When omitted, all repository skills are considered.

.EXAMPLE
.\scripts\links\remove-skills.ps1 -Target C:\work\my-project

.EXAMPLE
.\scripts\links\remove-skills.ps1 -Target C:\work\my-project -Skills python-domain-modeling

.NOTES
Use uninstall.sh on macOS, Linux, or WSL. This script does not require elevation or modify
persistent environment variables.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Target,

    [string[]]$Skills = @()
)

$ErrorActionPreference = "Stop"

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$TargetProject = (Resolve-Path $Target).Path
$Destination = Join-Path $TargetProject ".agents\skills"
foreach ($Parent in @((Join-Path $TargetProject ".agents"), $Destination)) {
    $Entry = Get-Item -LiteralPath $Parent -Force -ErrorAction SilentlyContinue
    if ($Entry -and $Entry.LinkType) {
        throw "Refusing a linked destination ancestor: $Parent"
    }
}

if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
    Write-Output "No project skill directory: $Destination"
    exit 0
}

if ($Skills.Count -eq 0) {
    $Skills = Get-ChildItem (Join-Path $Repo "skills") -Directory |
        Sort-Object Name |
        Select-Object -ExpandProperty Name
}

# Reject an invalid request before removing any junctions.
foreach ($Name in $Skills) {
    if ($Name -notmatch '^[a-z0-9]+(-[a-z0-9]+)*$') {
        throw "Invalid skill name: $Name"
    }
}

foreach ($Name in $Skills) {
    $SourceDirectory = Join-Path $Repo "skills\$Name"
    $Link = Join-Path $Destination $Name

    $Item = Get-Item -LiteralPath $Link -Force -ErrorAction SilentlyContinue
    if (-not $Item) {
        continue
    }

    if ($Item.LinkType -ne "Junction" -or $Item.Target -notcontains $SourceDirectory) {
        Write-Output "skip  $Name (not a junction managed by this repository)"
        continue
    }

    Remove-Item -LiteralPath $Link -Force
    Write-Output "unlink $Name"
}

if ((Get-ChildItem -LiteralPath $Destination -Force | Measure-Object).Count -eq 0) {
    Remove-Item -LiteralPath $Destination -Force
    $Agents = Split-Path $Destination -Parent
    if ((Get-ChildItem -LiteralPath $Agents -Force | Measure-Object).Count -eq 0) {
        Remove-Item -LiteralPath $Agents -Force
    }
}
