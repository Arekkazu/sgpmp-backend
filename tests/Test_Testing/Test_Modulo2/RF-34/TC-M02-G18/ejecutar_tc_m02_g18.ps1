$ErrorActionPreference = "Stop"

$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
$Email = "productor@pecuaria.co"
$Password = "Test1234!"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Collection = Join-Path $ScriptDir "tc_m02_g18.json"
$Resultados = Join-Path $ScriptDir "Resultados"

New-Item -ItemType Directory -Force -Path $Resultados | Out-Null

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " TC-M02-G18 - RF-34" -ForegroundColor Cyan
Write-Host " Consulta asociacion a infraestructura" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 1. LOGIN
# ============================================================

Write-Host "1. Login Productor..." -ForegroundColor Yellow

$loginBody = @{
    correo_electronico = $Email
    contrasena = $Password
} | ConvertTo-Json

$login = Invoke-RestMethod `
    -Uri "$BaseUrl/sesiones/" `
    -Method Post `
    -ContentType "application/json" `
    -Body $loginBody

$Token = $login.token

if ([string]::IsNullOrWhiteSpace($Token)) {
    throw "No se obtuvo token de autenticacion."
}

Write-Host "   Login OK" -ForegroundColor Green

$headers = @{
    Authorization = "Bearer $Token"
}

# ============================================================
# 2. CONSULTAR ACTIVOS
# ============================================================

Write-Host ""
Write-Host "2. Consultando activos..." -ForegroundColor Yellow

$activosResponse = Invoke-RestMethod `
    -Uri "$BaseUrl/activos-biologicos" `
    -Method Get `
    -Headers $headers

Write-Host "   Tipo de respuesta: $($activosResponse.GetType().FullName)" -ForegroundColor DarkGray

$activos = @()

# ------------------------------------------------------------
# Detectar diferentes estructuras posibles de respuesta
# ------------------------------------------------------------

if ($activosResponse -is [System.Array]) {

    $activos = @($activosResponse)

}
elseif ($null -ne $activosResponse.items) {

    $activos = @($activosResponse.items)

}
elseif ($null -ne $activosResponse.data) {

    if ($activosResponse.data -is [System.Array]) {
        $activos = @($activosResponse.data)
    }
    elseif ($null -ne $activosResponse.data.items) {
        $activos = @($activosResponse.data.items)
    }

}
elseif ($null -ne $activosResponse.result) {

    if ($activosResponse.result -is [System.Array]) {
        $activos = @($activosResponse.result)
    }
    elseif ($null -ne $activosResponse.result.items) {
        $activos = @($activosResponse.result.items)
    }

}

# ------------------------------------------------------------
# Mostrar estructura si no se pudo detectar
# ------------------------------------------------------------

if ($activos.Count -eq 0) {

    Write-Host "   No se pudo interpretar la estructura de la lista." -ForegroundColor DarkYellow
    Write-Host "   Estructura recibida:" -ForegroundColor DarkYellow

    $activosResponse |
        ConvertTo-Json -Depth 10 |
        Write-Host

    Write-Host ""
    Write-Host "   Se utilizara el activo conocido 181 para RF-34." -ForegroundColor Yellow

    $ActivoId = 181

}
else {

    # --------------------------------------------------------
    # Buscar primer elemento con ID valido
    # --------------------------------------------------------

    $activoSeleccionado = $activos |
        Where-Object {
            $null -ne $_.id_activo_biologico -or
            $null -ne $_.id
        } |
        Select-Object -First 1

    if ($null -eq $activoSeleccionado) {

        Write-Host "   Los elementos no contienen un ID reconocible." -ForegroundColor DarkYellow
        Write-Host "   Se utilizara el activo conocido 181 para RF-34." -ForegroundColor Yellow

        $ActivoId = 181

    }
    else {

        if ($null -ne $activoSeleccionado.id_activo_biologico) {
            $ActivoId = $activoSeleccionado.id_activo_biologico
        }
        else {
            $ActivoId = $activoSeleccionado.id
        }

    }
}

Write-Host "   Activo seleccionado: $ActivoId" -ForegroundColor Green

# ============================================================
# 3. BUSCAR ACTIVO SIN ASOCIACION ACTIVA
# ============================================================

Write-Host ""
Write-Host "3. Buscando activo existente sin asociacion activa..." -ForegroundColor Yellow

$ActivoSinAsociacion = $null

# ------------------------------------------------------------
# Construir lista de IDs candidatos
# ------------------------------------------------------------

$idsCandidatos = @()

foreach ($activo in $activos) {

    $id = $null

    if ($null -ne $activo.id_activo_biologico) {
        $id = $activo.id_activo_biologico
    }
    elseif ($null -ne $activo.id) {
        $id = $activo.id
    }

    if ($null -ne $id) {
        $idsCandidatos += $id
    }
}

# Agregar activo conocido si no apareció en la lista
if (-not ($idsCandidatos -contains 181)) {
    $idsCandidatos += 181
}

# ------------------------------------------------------------
# Consultar asociación activa de cada activo
# ------------------------------------------------------------

foreach ($id in $idsCandidatos) {

    try {

        $url = "$BaseUrl/activos-biologicos/$id/infraestructura?tipo_consulta=ACTIVA"

        $respuesta = Invoke-WebRequest `
            -Uri $url `
            -Method Get `
            -Headers $headers `
            -UseBasicParsing

        if ($respuesta.StatusCode -eq 404) {

            $ActivoSinAsociacion = $id
            break

        }

    }
    catch {

        $status = $null

        if ($_.Exception.Response) {

            try {
                $status = [int]$_.Exception.Response.StatusCode
            }
            catch {
                $status = $null
            }

        }

        if ($status -eq 404) {

            $ActivoSinAsociacion = $id
            break

        }

    }

}

if ($null -ne $ActivoSinAsociacion) {

    Write-Host "   Encontrado activo sin asociacion activa: $ActivoSinAsociacion" -ForegroundColor Green

}
else {

    Write-Host "   No se encontro activo sin asociacion activa." -ForegroundColor DarkYellow
    Write-Host "   TC-M02-025 quedara NO EJECUTABLE por falta de precondicion." -ForegroundColor DarkYellow

}

# ============================================================
# 4. CREAR ENVIRONMENT PARA NEWMAN
# ============================================================

$EnvironmentFile = Join-Path $Resultados "environment-g18.json"

$environment = @{
    id = "tc-m02-g18-environment"
    name = "TC-M02-G18 TEST"
    values = @(
        @{
            key = "base_url"
            value = $BaseUrl
            enabled = $true
        },
        @{
            key = "access_token"
            value = $Token
            enabled = $true
        },
        @{
            key = "activo_id"
            value = "$ActivoId"
            enabled = $true
        },
        @{
            key = "activo_sin_asociacion_id"
            value = if ($null -ne $ActivoSinAsociacion) {
                "$ActivoSinAsociacion"
            }
            else {
                ""
            }
            enabled = $true
        }
    )
} | ConvertTo-Json -Depth 10

Set-Content `
    -Path $EnvironmentFile `
    -Value $environment `
    -Encoding UTF8

Write-Host ""
Write-Host "   Environment generado correctamente." -ForegroundColor Green

# ============================================================
# 5. EJECUTAR NEWMAN
# ============================================================

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

$HtmlReport = Join-Path `
    $Resultados `
    "TC-M02-G18-Newman-$Timestamp.html"

Write-Host ""
Write-Host "4. Ejecutando Newman..." -ForegroundColor Yellow
Write-Host ""

npx newman run $Collection `
    -e $EnvironmentFile `
    --reporters "cli,htmlextra" `
    --reporter-htmlextra-export $HtmlReport

$NewmanExit = $LASTEXITCODE

# ============================================================
# 6. RESULTADO FINAL
# ============================================================

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Resultado Newman" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

if ($NewmanExit -eq 0) {

    Write-Host " Newman finalizo sin assertions fallidas." -ForegroundColor Green

}
else {

    Write-Host " Newman termino con assertions fallidas." -ForegroundColor Red

}

Write-Host ""
Write-Host "Reporte HTML:" -ForegroundColor Yellow
Write-Host $HtmlReport
Write-Host ""

exit $NewmanExit