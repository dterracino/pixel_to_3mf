# Clean all __pycache__ folders recursively
# This script removes all Python bytecode cache directories

Write-Host "Searching for __pycache__ folders..." -ForegroundColor Cyan

$pycacheFolders = Get-ChildItem -Path . -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue

if ($pycacheFolders.Count -eq 0) {
    Write-Host "No __pycache__ folders found." -ForegroundColor Green
    exit 0
}

Write-Host "Found $($pycacheFolders.Count) __pycache__ folder(s):" -ForegroundColor Yellow
$pycacheFolders | ForEach-Object { Write-Host "  - $($_.FullName)" }

Write-Host "`nRemoving __pycache__ folders..." -ForegroundColor Cyan
$pycacheFolders | Remove-Item -Recurse -Force

Write-Host "Done! All __pycache__ folders have been removed." -ForegroundColor Green
