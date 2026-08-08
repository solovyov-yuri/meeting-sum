#requires -Version 5.1
<#
.SYNOPSIS
    Build a portable (no-install) Windows distribution of Recap.

.DESCRIPTION
    Produces dist\portable\Recap\ containing Recap.exe plus a frozen recap-bridge\ sidecar (Python +
    faster-whisper + CUDA libs), then zips it. The app finds the bundled bridge automatically
    (see docs/portable-build.md) — the target machine needs no Python.

    Pipeline:
      1. uv sync                        (Python deps into .venv)  — skip with -SkipDeps
      2. PyInstaller freeze the bridge  -> dist\bridge\recap-bridge\   — skip with -SkipBridge
      3. tauri build --no-bundle        -> target\release\recap-desktop.exe  — skip with -SkipApp
      4. Assemble dist\portable\Recap\  and zip it

    Run from the repo root on Windows PowerShell, with uv, Node.js and the Rust toolchain installed:
      pwsh -File scripts\build-portable.ps1

.PARAMETER Ffmpeg
    Optional path to an ffmpeg.exe to copy next to Recap.exe (needed for full-mode preprocessing;
    otherwise ffmpeg must be on PATH).
#>
[CmdletBinding()]
param(
    [switch]$SkipDeps,
    [switch]$SkipBridge,
    [switch]$SkipApp,
    [string]$Ffmpeg
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Need($cmd) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Required tool '$cmd' not found on PATH. Install it and retry."
    }
}

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$pyInstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"
$bridgeDist = Join-Path $root "dist\bridge"
$portableDir = Join-Path $root "dist\portable\Recap"

# App version (for the zip name) from tauri.conf.json.
$version = (Get-Content "desktop\src-tauri\tauri.conf.json" -Raw | ConvertFrom-Json).version

# ── 1. Python deps ───────────────────────────────────────────────────────────
if (-not $SkipDeps) {
    Step "Syncing Python deps (uv sync)"
    Need uv
    # PyInstaller is a build-only tool, declared in the `packaging` dependency group so its
    # version is locked like everything else.
    uv sync --group packaging
}
if (-not (Test-Path $venvPy)) { throw "venv not found at $venvPy — run 'uv sync' first." }

# ── 2. Freeze the bridge ─────────────────────────────────────────────────────
if (-not $SkipBridge) {
    Step "Freezing recap-bridge (PyInstaller)"
    if (-not (Test-Path $pyInstaller)) { throw "pyinstaller not found — run without -SkipDeps (uv sync --group packaging)." }
    & $pyInstaller --noconfirm `
        --distpath $bridgeDist `
        --workpath (Join-Path $root "dist\bridge-work") `
        (Join-Path $root "packaging\recap-bridge.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)." }
}
$frozenBridge = Join-Path $bridgeDist "recap-bridge\recap-bridge.exe"
if (-not (Test-Path $frozenBridge)) { throw "Frozen bridge not found at $frozenBridge." }

# ── 3. Build the Tauri app (raw exe, no installer) ───────────────────────────
if (-not $SkipApp) {
    Step "Building the desktop app (tauri build --no-bundle)"
    Need node
    Push-Location (Join-Path $root "desktop")
    if (-not (Test-Path "node_modules")) { npm install }
    npm run tauri build -- --no-bundle
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "tauri build failed ($LASTEXITCODE)." }
    Pop-Location
}
$appExe = Join-Path $root "desktop\src-tauri\target\release\recap-desktop.exe"
if (-not (Test-Path $appExe)) { throw "App exe not found at $appExe." }

# ── 4. Assemble the portable folder ──────────────────────────────────────────
Step "Assembling portable folder"
if (Test-Path $portableDir) { Remove-Item $portableDir -Recurse -Force }
New-Item -ItemType Directory -Path $portableDir | Out-Null

Copy-Item $appExe (Join-Path $portableDir "Recap.exe")
Copy-Item (Join-Path $bridgeDist "recap-bridge") (Join-Path $portableDir "recap-bridge") -Recurse
# WebView2Loader.dll ships next to the exe when present (system WebView2 is used at runtime).
$wv2 = Join-Path $root "desktop\src-tauri\target\release\WebView2Loader.dll"
if (Test-Path $wv2) { Copy-Item $wv2 $portableDir }
if ($Ffmpeg) {
    if (-not (Test-Path $Ffmpeg)) { throw "ffmpeg not found at $Ffmpeg" }
    Copy-Item $Ffmpeg (Join-Path $portableDir "ffmpeg.exe")
}

# ── 5. Zip (best effort) ─────────────────────────────────────────────────────
# The assembled FOLDER is the deliverable; the zip is convenience. Compress-Archive errors/hangs on
# multi-GB inputs (CUDA libs push this to 2-4 GB), so guard on size and never let a zip failure
# discard the folder.
$sizeMB = [math]::Round((Get-ChildItem $portableDir -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
$zip = Join-Path $root "dist\portable\Recap-$version-portable.zip"
if ($sizeMB -gt 1500) {
    Write-Warning "Portable folder is $sizeMB MB — skipping Compress-Archive (unreliable above ~2 GB)."
    Write-Warning "Zip it yourself with 7-Zip/tar if you need an archive, e.g.: tar -a -c -f `"$zip`" -C `"$(Split-Path $portableDir)`" Recap"
    $zip = $null
} else {
    Step "Zipping"
    try {
        if (Test-Path $zip) { Remove-Item $zip -Force }
        Compress-Archive -Path $portableDir -DestinationPath $zip
    } catch {
        Write-Warning "Zip failed ($_). The portable folder is still ready."
        $zip = $null
    }
}

Write-Host "`nDone." -ForegroundColor Green
Write-Host "  Portable folder: $portableDir  ($sizeMB MB)"
if ($zip) { Write-Host "  Zip:             $zip" }
