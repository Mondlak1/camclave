# lookhere install.ps1 — Windows installer
# - pip-installs runtime deps (opencv-python, Pillow)
# - links skill/ into ~/.claude/skills/lookhere/ and ~/.codex/skills/lookhere/
#   (symlink if Developer Mode is on; recursive copy otherwise)
# - writes a `lookhere.cmd` shim into %USERPROFILE%\.lookhere\bin

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillSrc = Join-Path $repo "skill"

if (-not (Test-Path $skillSrc)) { throw "skill/ not found next to install.ps1" }

function Write-Step($msg) { Write-Host "[lookhere] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[lookhere] $msg" -ForegroundColor Yellow }

# 1. Python deps
Write-Step "Installing Python dependencies (opencv-python, Pillow)..."
$python = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) { throw "Python not found on PATH. Install Python 3.10+ first." }
& $python.Source -m pip install --user --upgrade opencv-python Pillow | Out-Host

# 2. Install skill into both agent skill dirs
function Install-Skill($targetRoot) {
    $target = Join-Path $targetRoot "lookhere"
    New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
    if (Test-Path $target) {
        Write-Warn "Existing $target removed."
        Remove-Item -Recurse -Force $target
    }
    try {
        New-Item -ItemType SymbolicLink -Path $target -Target $skillSrc -ErrorAction Stop | Out-Null
        Write-Step "Linked $target -> $skillSrc"
    } catch {
        Write-Warn "Symlink failed (likely no Developer Mode privilege). Falling back to copy."
        Copy-Item -Recurse -Force $skillSrc $target
        Write-Step "Copied $skillSrc -> $target"
    }
}

Install-Skill (Join-Path $HOME ".claude\skills")
Install-Skill (Join-Path $HOME ".codex\skills")

# 3. Shim on PATH
$binDir = Join-Path $HOME ".lookhere\bin"
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$shim = Join-Path $binDir "lookhere.cmd"
$pyExe = $python.Source
$entry = Join-Path $skillSrc "scripts\lookhere.py"
@"
@echo off
"$pyExe" "$entry" %*
"@ | Set-Content -Encoding ASCII $shim

# Add to user PATH if not present
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not ($userPath -split ";" | Where-Object { $_ -ieq $binDir })) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    Write-Step "Added $binDir to your user PATH (open a fresh terminal)."
} else {
    Write-Step "$binDir already on PATH."
}

Write-Host ""
Write-Host "[lookhere] installed. Try this in a fresh terminal:" -ForegroundColor Green
Write-Host "    lookhere start" -ForegroundColor Green
Write-Host "Then ask Claude Code or Codex: 'use lookhere to show me what I'm holding'." -ForegroundColor Green
