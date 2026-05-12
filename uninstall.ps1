$ErrorActionPreference = "Stop"
Write-Host "[camclave] uninstalling..." -ForegroundColor Cyan

foreach ($p in @(
    (Join-Path $HOME ".claude\skills\camclave"),
    (Join-Path $HOME ".codex\skills\camclave"),
    (Join-Path $HOME ".camclave\bin\camclave.cmd")
)) {
    if (Test-Path $p) {
        Remove-Item -Recurse -Force $p
        Write-Host "  removed $p"
    }
}

$binDir = Join-Path $HOME ".camclave\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -split ";" | Where-Object { $_ -ieq $binDir }) {
    $newPath = (($userPath -split ";") | Where-Object { $_ -ine $binDir }) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "  removed $binDir from PATH"
}

Write-Host "[camclave] done. ~/.camclave/ kept for any captures you marked --keep." -ForegroundColor Green
