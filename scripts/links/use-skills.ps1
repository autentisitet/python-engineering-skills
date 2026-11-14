#Requires -Version 5.1

<#
.SYNOPSIS
Installs selected repository skills into a native Windows project.

.DESCRIPTION
Creates project-scoped junctions under .agents\skills. The request is validated before any
directory or junction is created, and linked destination ancestors are rejected.

.PARAMETER Target
Path to the target project. It must not be this skill repository.

.PARAMETER Skills
Optional skill names. When omitted, all repository skills are installed.

.EXAMPLE
.\scripts\links\use-skills.ps1 -Target C:\work\my-project

.EXAMPLE
.\scripts\links\use-skills.ps1 -Target C:\work\my-project -Skills python-domain-modeling

.NOTES
Use install.sh on macOS, Linux, or WSL. This script does not require elevation or modify
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

if ($TargetProject -eq $Repo) {
    throw "Choose a target Python project, not the skill source repository."
}

if ($Skills.Count -eq 0) {
    $Skills = Get-ChildItem (Join-Path $Repo "skills") -Directory |
        Sort-Object Name |
        Select-Object -ExpandProperty Name
}

# Validate the complete request before creating directories or junctions.
foreach ($Name in $Skills) {
    if ($Name -notmatch '^[a-z0-9]+(-[a-z0-9]+)*$') {
        throw "Invalid skill name: $Name"
    }
    $SourceDirectory = Join-Path $Repo "skills\$Name"
    $SkillFile = Join-Path $SourceDirectory "SKILL.md"
    $Link = Join-Path $Destination $Name

    if (-not (Test-Path -LiteralPath $SkillFile -PathType Leaf)) {
        throw "Unknown skill: $Name"
    }

    if (Test-Path -LiteralPath $Link) {
        $Item = Get-Item -LiteralPath $Link -Force
        if ($Item.LinkType -eq "Junction" -and $Item.Target -contains $SourceDirectory) {
            Write-Output "keep  $Name"
            continue
        }
        throw "Refusing to replace existing path: $Link"
    }
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null

foreach ($Name in $Skills) {
    $SourceDirectory = Join-Path $Repo "skills\$Name"
    $Link = Join-Path $Destination $Name
    if (Test-Path -LiteralPath $Link) {
        Write-Output "keep  $Name"
        continue
    }
    New-Item -ItemType Junction -Path $Link -Target $SourceDirectory | Out-Null
    Write-Output "link  $Name -> $Link"
}

Write-Output "Project skills are available in $Destination"
