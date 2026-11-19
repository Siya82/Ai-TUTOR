<#
.SYNOPSIS
    NEW 20 Nov 2026 (deep scan H4). Backs up, or restores, the LOCAL
    THUTOra database running in Docker. Production backups are Cloud SQL's
    job -- see docs/RUNBOOK.md.

.EXAMPLE
    .\backup-thutora.ps1                       # writes backups\thutora-<date>.dump
    .\backup-thutora.ps1 -Restore backups\thutora-2026-11-20-0900.dump
#>
param(
    [string]$Restore = "",
    [string]$Service = "db",
    [string]$Database = "caps_tutor"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force -Path backups | Out-Null

if ($Restore -eq "") {
    $file = "backups\thutora-$(Get-Date -Format 'yyyy-MM-dd-HHmm').dump"
    # custom format (-Fc): compressed, and pg_restore can restore one table
    # dump inside the container, then copy the file out: piping binary output
    # through PowerShell can corrupt it
    docker compose exec -T $Service pg_dump -U postgres -Fc -f /tmp/thutora.dump $Database
    docker compose cp "${Service}:/tmp/thutora.dump" $file
    docker compose exec -T $Service rm -f /tmp/thutora.dump
    if ((Get-Item $file).Length -lt 1024) { throw "Backup looks empty: $file" }
    Write-Host "Backed up to $file ($([math]::Round((Get-Item $file).Length / 1MB, 1)) MB)"
} else {
    if (-not (Test-Path $Restore)) { throw "No such file: $Restore" }
    Write-Host "This REPLACES everything in the local '$Database' database." -ForegroundColor Yellow
    if ((Read-Host "Type RESTORE to continue") -ne "RESTORE") { Write-Host "Cancelled."; exit 1 }
    docker compose cp $Restore "${Service}:/tmp/thutora.dump"
    docker compose exec -T $Service pg_restore -U postgres -d $Database --clean --if-exists --no-owner /tmp/thutora.dump
    docker compose exec -T $Service rm -f /tmp/thutora.dump
    Write-Host "Restored $Restore. Run 'alembic upgrade head' if the backup is older than your code."
}
