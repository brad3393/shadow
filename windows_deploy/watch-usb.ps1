# Shadow Sentinel — watches for the SHADOW-DEPLOY USB stick and
# launches Shadow automatically. Runs in the background at logon.
# No admin rights required; only reacts to a stick labeled SHADOW-DEPLOY.

$ErrorActionPreference = 'SilentlyContinue'
$label = 'SHADOW-DEPLOY'
$stateDir = Join-Path $env:LOCALAPPDATA 'Shadow'
$stateFile = Join-Path $stateDir 'last-usb-serial.txt'
if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Path $stateDir | Out-Null }

while ($true) {
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=2 AND VolumeName='$label'" |
            Where-Object { $_.VolumeSerialNumber } |
            Select-Object -First 1
    if ($disk) {
        $serial = $disk.VolumeSerialNumber
        $last = Get-Content $stateFile -ErrorAction SilentlyContinue
        if ($serial -and ($last -ne $serial)) {
            Set-Content -Path $stateFile -Value $serial
            $launcher = Join-Path $disk.DeviceID 'START_SHADOW.bat'
            if (Test-Path $launcher) {
                Start-Process -FilePath $launcher -WindowStyle Minimized
            }
        }
    }
    Start-Sleep -Seconds 5
}
