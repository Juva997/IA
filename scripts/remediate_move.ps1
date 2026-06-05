<#
Remediate move script
Usage: powershell -ExecutionPolicy Bypass -File .\scripts\remediate_move.ps1 [-Commit] [-Branch <name>]

This script moves `reports/`, `logs/` and patch files into `secure_archive/<timestamp>/`, preferring `git mv` for tracked files to preserve history in the index prior to a history-rewrite.
#>
param(
    [switch]$Commit = $true,
    [string]$Branch = ""
)

Set-StrictMode -Version Latest

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "git is required in PATH. Install Git and re-run."
    exit 1
}

if (-not $Branch -or $Branch -eq "") {
    $Branch = "remediation/remove-sensitive-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
}

Write-Output "Creating and switching to branch: $Branch"
git fetch --all
# create branch (will fail if already exists)
if ((git rev-parse --verify $Branch) -ne $null) {
    Write-Output "Branch $Branch already exists locally. Checking it out."
    git checkout $Branch
} else {
    git checkout -b $Branch
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$archiveRoot = Join-Path (Get-Location) "secure_archive\$timestamp"
if (-not (Test-Path $archiveRoot)) { New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null }

# Move listed directories if present
$dirs = @('reports','logs')
foreach ($d in $dirs) {
    if (Test-Path $d) {
        Write-Output "Processing folder: $d"
        # check if tracked
        git ls-files --error-unmatch $d > $null 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Output "Using git mv for tracked path: $d"
            git mv $d $archiveRoot\ 2>$null
        } else {
            Write-Output "Moving filesystem path: $d"
            Move-Item -Path $d -Destination $archiveRoot -Force
        }
    } else {
        Write-Output "Path not found: $d"
    }
}

# Move patch files under patches/ (only files with extensions .patch and .orig)
if (Test-Path 'patches') {
    $patchFiles = Get-ChildItem -Path 'patches' -Include *.patch,*.orig -File -Recurse -ErrorAction SilentlyContinue
    if ($patchFiles) {
        $destDir = Join-Path $archiveRoot 'patches'
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        foreach ($p in $patchFiles) {
            $rel = $p.FullName.Substring((Get-Location).Path.Length + 1)
            Write-Output "Processing patch file: $rel"
            git ls-files --error-unmatch $rel > $null 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Output "git mv tracked file: $rel"
                git mv $rel $destDir\ 2>$null
            } else {
                Move-Item -Path $p.FullName -Destination $destDir -Force
            }
        }
    } else {
        Write-Output "No patch files found under patches/"
    }
} else {
    Write-Output "No patches/ directory present"
}

# Stage changes and commit
Write-Output "Staging changes..."
git add -A
if ($Commit) {
    try {
        git commit -m "chore(remediation): move sensitive artifacts to secure_archive and update .gitignore" | Out-Null
        Write-Output "Committed changes on branch $Branch"
    } catch {
        Write-Output "No changes to commit or commit failed: $($_.Exception.Message)"
    }
} else {
    Write-Output "Commit skipped (Commit flag not set)"
}

Write-Output "Remediation move complete. Archive root: $archiveRoot"
Write-Output "Next: inspect $archiveRoot, rotate secrets, then run scripts/prepare_git_filter_repo.* to rewrite history if needed."
