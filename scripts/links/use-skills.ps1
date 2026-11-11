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

New-Item -ItemType Directory -Force -Path $Destination | Out-Null

if ($Skills.Count -eq 0) {
    $Skills = Get-ChildItem (Join-Path $Repo "skills") -Directory |
        Sort-Object Name |
        Select-Object -ExpandProperty Name
}

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

    New-Item -ItemType Junction -Path $Link -Target $SourceDirectory | Out-Null
    Write-Output "link  $Name -> $Link"
}

Write-Output "Project skills are available in $Destination"
