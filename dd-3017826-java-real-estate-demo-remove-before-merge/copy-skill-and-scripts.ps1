<#
.SYNOPSIS
    Copies shepherd-task skills and agentic-development scripts from copilot-sdk to BRK206-00.
#>

$source = 'C:\Users\edburns\workareas\copilot-sdk'
$dest   = 'C:\Users\edburns\workareas\BRK206-00'

$dirs = @(
    '.github/skills/shepherd-task-approve-workflows-and-wait-for-completion'
    '.github/skills/shepherd-task-from-assignment-to-ready'
    '.github/skills/shepherd-task-from-ready-to-merged-to-base'
    'scripts/agentic-development'
)

foreach ($dir in $dirs) {
    $src = Join-Path $source $dir
    $dst = Join-Path $dest $dir
    if (-not (Test-Path $dst)) {
        New-Item -ItemType Directory -Path $dst -Force | Out-Null
    }
    Copy-Item -Path "$src\*" -Destination $dst -Recurse -Force
}

Write-Host "Done. Copied $($dirs.Count) directories from copilot-sdk to BRK206-00."
