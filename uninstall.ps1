$ErrorActionPreference = "Stop"
Write-Host "[lookhere] uninstalling..." -ForegroundColor Cyan

foreach ($p in @(
    (Join-Path $HOME ".claude\skills\lookhere"),
    (Join-Path $HOME ".codex\skills\lookhere"),
    (Join-Path $HOME ".lookhere\bin\lookhere.cmd")
)) {
    if (Test-Path $p) {
        Remove-Item -Recurse -Force $p
        Write-Host "  removed $p"
    }
}

$binDir = Join-Path $HOME ".lookhere\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -split ";" | Where-Object { $_ -ieq $binDir }) {
    $newPath = (($userPath -split ";") | Where-Object { $_ -ine $binDir }) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "  removed $binDir from PATH"
}

Write-Host "[lookhere] done. ~/.lookhere/ kept for any captures you marked --keep." -ForegroundColor Green
