# Desktop shortcut yaratish — Minar Camera uchun
# Ishga tushirish: PowerShell -ExecutionPolicy Bypass -File create_shortcut.ps1

$CameraDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $CameraDir) { $CameraDir = "C:\Users\Administrator\it-hub\camera" }
$BatFile   = Join-Path $CameraDir "start_camera.bat"
$IconFile  = Join-Path $CameraDir "icons\minar.ico"
$Desktop   = [Environment]::GetFolderPath("Desktop")
$LinkPath  = Join-Path $Desktop "Minar Camera.lnk"

$WshShell  = New-Object -ComObject WScript.Shell
$Shortcut  = $WshShell.CreateShortcut($LinkPath)
$Shortcut.TargetPath     = $BatFile
$Shortcut.WorkingDirectory = $CameraDir
$Shortcut.WindowStyle    = 1
$Shortcut.Description    = "Minar O'quv Markazi — Kamera Davomat Tizimi"

if (Test-Path $IconFile) {
    $Shortcut.IconLocation = $IconFile
}

$Shortcut.Save()

Write-Host ""
Write-Host "  Desktop shortcut yaratildi:" -ForegroundColor Green
Write-Host "  $LinkPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Eslatma: O'z ikonangizni qo'shish uchun" -ForegroundColor Yellow
Write-Host "  camera\icons\minar.ico fayliga joylashtiring." -ForegroundColor Yellow
Write-Host ""
