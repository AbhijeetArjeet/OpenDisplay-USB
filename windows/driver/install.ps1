# OpenDisplay USB IddCx Driver Installation Helper
param (
    [switch]$Install,
    [switch]$Uninstall
)

$infPath = Join-Path $PSScriptRoot "OpenDisplayIdd.inf"

if ($Install) {
    Write-Host "Installing OpenDisplay USB Virtual Display Driver..."
    pnputil /add-driver $infPath /install
} elseif ($Uninstall) {
    Write-Host "Uninstalling OpenDisplay USB Virtual Display Driver..."
    pnputil /delete-driver $infPath /uninstall /force
} else {
    Write-Host "Usage: .\install.ps1 -Install | -Uninstall"
}
