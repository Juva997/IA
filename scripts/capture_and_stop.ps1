$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$logdir = 'logs'
if (-not (Test-Path $logdir)) { New-Item -ItemType Directory -Path $logdir | Out-Null }
netstat -ano | findstr :11435 > "$logdir\netstat_11435_$ts.txt"
netstat -ano | findstr :8000 > "$logdir\netstat_8000_$ts.txt"
netstat -ano > "$logdir\netstat_all_$ts.txt"
tasklist /FI "IMAGENAME eq python.exe" > "$logdir\python_tasks_$ts.txt"
$pid11435 = (Get-NetTCPConnection -LocalPort 11435 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -ErrorAction SilentlyContinue) -join ','
$pid8000 = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -ErrorAction SilentlyContinue) -join ','
if ($pid11435) { 'pid11435='+$pid11435 | Out-File "$logdir\pids_$ts.txt" -Append }
if ($pid8000) { 'pid8000='+$pid8000 | Out-File "$logdir\pids_$ts.txt" -Append }
if ($pid11435) { Get-Process -Id $pid11435 | Out-File "$logdir\process_11435_$ts.txt" -Append -ErrorAction SilentlyContinue }
if ($pid8000) { Get-Process -Id $pid8000 | Out-File "$logdir\process_8000_$ts.txt" -Append -ErrorAction SilentlyContinue }
if ($pid11435) { Stop-Process -Id $pid11435 -Force -ErrorAction SilentlyContinue }
if ($pid8000) { Stop-Process -Id $pid8000 -Force -ErrorAction SilentlyContinue }
$zip = Join-Path (Get-Location) "captured_logs_$ts.zip"
Compress-Archive -Path "$logdir\*" -DestinationPath $zip -Force
Move-Item $zip "$logdir\" -Force
Write-Output "Captured logs into $logdir\captured_logs_$ts.zip"
netstat -ano | findstr :11435 > "$logdir\netstat_11435_after_$ts.txt"
netstat -ano | findstr :8000 > "$logdir\netstat_8000_after_$ts.txt"
Get-ChildItem -Path "$logdir" -Filter "captured_logs_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { Write-Output "Archive: $($_.FullName)" }
