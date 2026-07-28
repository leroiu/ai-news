[CmdletBinding()]
param(
    [string]$Task,
    [string]$Model = "fable",
    [string]$FallbackModels = "sonnet,haiku",
    [ValidateSet("low", "medium", "high", "xhigh", "max")]
    [string]$Effort = "high",
    [switch]$Headless,
    [Nullable[double]]$MaxBudgetUsd,
    [switch]$CurrentWorktree,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$currentRoot = (git -C $repoRoot rev-parse --show-toplevel).Trim()

if ((Resolve-Path $currentRoot).Path -ne $repoRoot) {
    throw "Run this script from the ai-news Git repository."
}

if ($Headless -and [string]::IsNullOrWhiteSpace($Task)) {
    throw "Headless mode requires an explicit -Task."
}

if ($Headless -and $null -eq $MaxBudgetUsd) {
    throw "Headless mode requires -MaxBudgetUsd to cap API spending."
}

$sourceSettingsPath = Join-Path $repoRoot ".claude\settings.longrun.json"
if (-not (Test-Path -LiteralPath $sourceSettingsPath)) {
    throw "Long-run settings are missing: $sourceSettingsPath"
}

$claudeCommand = Get-Command claude -ErrorAction SilentlyContinue
if ($null -eq $claudeCommand) {
    throw "Claude Code command was not found."
}

$runName = "ai-news-longrun-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$workingRoot = $repoRoot
if ($CurrentWorktree) {
    $dirty = git -C $repoRoot status --porcelain
    if ($dirty) {
        throw "The current worktree is dirty. Use the default isolated worktree."
    }
}

if ($DryRun) {
    Write-Host "Starting LongRun Host: mode=dontAsk, model=$Model, isolatedWorktree=$(-not $CurrentWorktree)"
    Write-Host "Validation passed. Claude Code was not started."
    exit 0
}

if (-not $CurrentWorktree) {
    $worktreeParent = Join-Path ([IO.Path]::GetTempPath()) "ai-news-longrun-worktrees"
    $workingRoot = Join-Path $worktreeParent $runName
    $branchName = "codex/$runName"
    New-Item -ItemType Directory -Force -Path $worktreeParent | Out-Null
    & git -C $repoRoot worktree add -b $branchName $workingRoot HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create isolated worktree $workingRoot."
    }

    $policyFiles = @(
        ".claude\settings.json",
        ".claude\settings.longrun.json",
        "AGENTS.md",
        "CLAUDE.md",
        "docs\LONG_RUNNING_AGENT_MODE.md",
        "tools\claude_checkpoint.py"
    )
    foreach ($relativePath in $policyFiles) {
        $sourcePath = Join-Path $repoRoot $relativePath
        $targetPath = Join-Path $workingRoot $relativePath
        $targetParent = Split-Path -Parent $targetPath
        New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
    }
}

$settingsPath = Join-Path $workingRoot ".claude\settings.longrun.json"
$arguments = @(
    "--settings", $settingsPath,
    "--setting-sources", "user,project,local",
    "--permission-mode", "dontAsk",
    "--model", $Model,
    "--effort", $Effort,
    "--name", $runName
)

if ($Headless) {
    $arguments += @(
        "--print",
        "--fallback-model", $FallbackModels,
        "--max-budget-usd", $MaxBudgetUsd.ToString([Globalization.CultureInfo]::InvariantCulture),
        $Task
    )
} elseif (-not [string]::IsNullOrWhiteSpace($Task)) {
    $arguments += $Task
}

Write-Host "Starting LongRun Host: mode=dontAsk, model=$Model, root=$workingRoot"
Push-Location $workingRoot
try {
    & $claudeCommand.Source @arguments
    $claudeExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $claudeExitCode
