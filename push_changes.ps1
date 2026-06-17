$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RepoRoot

$Message = if ($args.Count -gt 0) { ($args -join " ") } else { "" }
if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = Read-Host "Commit message"
}
if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = "Update Queensland Roadtrains telemetry assistant $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
}

git pull --rebase --autostash
git add -A

$staged = git diff --cached --name-only
if ([string]::IsNullOrWhiteSpace(($staged -join ""))) {
    Write-Host "No changes to push."
    exit 0
}

git commit -m $Message
git push origin main
