try {
  $root='D:\IA'
  $binDir = Join-Path $root '.bin'
  New-Item -ItemType Directory -Force -Path $binDir | Out-Null
  Write-Output "RELEASE: fetching..."
  $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/zricethezav/gitleaks/releases/latest" -Headers @{ 'User-Agent'='PowerShell' }
  Write-Output "RELEASE: $($rel.tag_name)"
  $asset = $rel.assets | Where-Object { $_.name -match 'windows' -and ($_.name -match 'x64|amd64|x86_64') } | Select-Object -First 1
  if (-not $asset) { $asset = $rel.assets | Where-Object { $_.name -match 'windows' } | Select-Object -First 1 }
  if (-not $asset) { Write-Error 'No Windows asset found'; exit 2 }
  Write-Output "ASSET: $($asset.name)"
  $dl = $asset.browser_download_url
  # Prefer download/extract on workspace drive to avoid C: temp space issues
  $zip = Join-Path $binDir $asset.name
  Write-Output "Downloading $dl to $zip"
  Invoke-WebRequest -Uri $dl -OutFile $zip -Headers @{ 'User-Agent'='PowerShell' }
  Write-Output "Downloaded"
  $extractDir = Join-Path $binDir ('gitleaks_extracted_' + [System.Guid]::NewGuid().ToString())
  New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
  Write-Output "Extracting to $extractDir"
  Expand-Archive -Path $zip -DestinationPath $extractDir -Force
  Write-Output "Extracted"
  $exe = Get-ChildItem -Path $extractDir -Recurse -Filter 'gitleaks*.exe' | Select-Object -First 1
  if (-not $exe) { $exe = Get-ChildItem -Path $extractDir -Recurse -Filter 'gitleaks.exe' | Select-Object -First 1 }
  if (-not $exe) { Write-Error 'gitleaks.exe not found after extraction'; exit 3 }
  $dest = Join-Path $binDir 'gitleaks.exe'
  Copy-Item -Path $exe.FullName -Destination $dest -Force
  Write-Output "Installed to $dest"
  & $dest version
} catch {
  Write-Error $_.Exception.Message
  exit 1
}
