<#
PowerShell helper: build + up docker compose, wait health, test /query
Run from repository root (PowerShell Admin recommended):

  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
  .\scripts\run_compose.ps1

#>

param(
    [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'

function Ensure-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "Docker CLI não encontrado." -ForegroundColor Yellow
        Write-Host "Instale Docker Desktop: https://docs.docker.com/desktop/windows/install/" -ForegroundColor Yellow
        return $false
    }
    try {
        docker info > $null 2>&1
        return $true
    } catch {
        Write-Host "Docker daemon não está rodando. Abra o Docker Desktop e aguarde." -ForegroundColor Yellow
        return $false
    }
}

function Wait-For-Url {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 120,
        [int]$IntervalSeconds = 2
    )
    $end = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $end) {
        try {
            Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5 -ErrorAction Stop | Out-Null
            return $true
        } catch {
            Start-Sleep -Seconds $IntervalSeconds
        }
    }
    return $false
}

if (-not (Ensure-Docker)) { exit 1 }

if (-not $NoBuild) {
    Write-Host "Construindo imagens (docker compose build --no-cache)..."
    docker compose build --no-cache
}

Write-Host "Subindo serviços (docker compose up -d)..."
docker compose up -d

Write-Host "Verificando status dos containers..."
docker compose ps

Write-Host "Aguardando /health em http://localhost:8000/health"
if (-not (Wait-For-Url -Url 'http://localhost:8000/health' -TimeoutSeconds 120 -IntervalSeconds 2)) {
    Write-Host "Serviço não ficou saudável no tempo esperado." -ForegroundColor Red
    docker compose logs --no-color --tail 200 app
    exit 2
}

Write-Host "Teste POST /query"
$body = @{ goal = 'oi' } | ConvertTo-Json
try {
    $resp = Invoke-RestMethod -Uri 'http://localhost:8000/query' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 15 -ErrorAction Stop
    Write-Host "Resposta /query:`n$($resp | ConvertTo-Json -Depth 4)"
} catch {
    Write-Host "Falha no POST /query: $_" -ForegroundColor Red
    docker compose logs --no-color --tail 200 app
    exit 3
}

Write-Host "Operação concluída com sucesso. Use docker compose logs -f app para ver logs em tempo real."
