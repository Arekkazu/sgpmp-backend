# ============================================================
# TC-M02-G01
# Gestion general del catalogo de especies
# RF-00 - Prueba general del Modulo 02
#
# Casos:
#   TC-M02-001 - Registrar especie nueva valida
#   TC-M02-002 - Rechazar especie con nombre duplicado
# ============================================================

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# Rutas
# ------------------------------------------------------------

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$CollectionFile = Join-Path $ScriptDir "tc_m02_g01.json"
$ResultadosDir = Join-Path $ScriptDir "Resultados"
$EnvironmentFile = Join-Path $ScriptDir "environment-g01.json"

# ------------------------------------------------------------
# Configuracion TEST
# ------------------------------------------------------------

$BaseUrl = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"

$AdminEmail = "admin@pecuaria.co"
$AdminPassword = "Test1234!"

$NombreNuevo = "Especie QA M02 20260910"
$DescripcionNueva = "Especie creada para prueba funcional TC-M02-001"

# ------------------------------------------------------------
# Encabezado
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " TC-M02-G01 - GESTION DEL CATALOGO DE ESPECIES" -ForegroundColor Cyan
Write-Host " RF-00 - PRUEBA GENERAL MODULO 02" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Ruta del script:" -ForegroundColor Gray
Write-Host $ScriptDir
Write-Host ""

# ------------------------------------------------------------
# Validar archivos
# ------------------------------------------------------------

if (-not (Test-Path -LiteralPath $CollectionFile)) {
    Write-Host "ERROR: No existe la coleccion JSON:" -ForegroundColor Red
    Write-Host $CollectionFile
    exit 1
}

Write-Host "OK - Coleccion encontrada:" -ForegroundColor Green
Write-Host $CollectionFile
Write-Host ""

if (-not (Get-Command newman -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Newman no esta instalado o no esta en PATH." -ForegroundColor Red
    Write-Host ""
    Write-Host "Comprueba con:"
    Write-Host "newman --version"
    exit 1
}

Write-Host "OK - Newman disponible." -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------
# Validar JSON antes de ejecutar
# ------------------------------------------------------------

Write-Host "Validando sintaxis del JSON..." -ForegroundColor Yellow

try {
    $JsonContent = Get-Content -LiteralPath $CollectionFile -Raw
    $null = $JsonContent | ConvertFrom-Json

    Write-Host "OK - JSON valido." -ForegroundColor Green
}
catch {
    Write-Host "ERROR: El archivo tc_m02_g01.json tiene errores de sintaxis." -ForegroundColor Red
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------
# Crear Resultados
# ------------------------------------------------------------

if (-not (Test-Path -LiteralPath $ResultadosDir)) {
    New-Item -ItemType Directory -Force -Path $ResultadosDir | Out-Null
}

# ------------------------------------------------------------
# Login de verificacion
# ------------------------------------------------------------

Write-Host ""
Write-Host "1. Verificando acceso del Administrador..." -ForegroundColor Yellow

$LoginBodyObject = @{
    correo_electronico = $AdminEmail
    contrasena = $AdminPassword
}

$LoginBody = $LoginBodyObject | ConvertTo-Json

try {

    $LoginResponse = Invoke-RestMethod `
        -Method POST `
        -Uri "$BaseUrl/sesiones/" `
        -ContentType "application/json" `
        -Body $LoginBody

    if ($null -eq $LoginResponse.token -or [string]::IsNullOrWhiteSpace([string]$LoginResponse.token)) {
        Write-Host "ERROR: El login respondio pero no devolvio token." -ForegroundColor Red
        exit 1
    }

    Write-Host "OK - Login Administrador HTTP 200." -ForegroundColor Green
    Write-Host ""

}
catch {

    Write-Host "ERROR: Fallo el login del Administrador." -ForegroundColor Red
    Write-Host ""

    if ($null -ne $_.Exception.Response) {
        try {
            $Stream = $_.Exception.Response.GetResponseStream()
            $Reader = New-Object System.IO.StreamReader($Stream)
            $ErrorBody = $Reader.ReadToEnd()

            Write-Host "Respuesta del servidor:" -ForegroundColor Yellow
            Write-Host $ErrorBody
        }
        catch {
            Write-Host $_.Exception.Message -ForegroundColor Red
        }
    }
    else {
        Write-Host $_.Exception.Message -ForegroundColor Red
    }

    exit 1
}

# ------------------------------------------------------------
# Consultar catalogo inicial
# ------------------------------------------------------------

Write-Host "2. Consultando catalogo de especies..." -ForegroundColor Yellow

$Headers = @{
    Authorization = "Bearer $($LoginResponse.token)"
}

try {

    $Catalogo = Invoke-RestMethod `
        -Method GET `
        -Uri "$BaseUrl/configuracion/especies" `
        -Headers $Headers

    Write-Host "OK - Catalogo HTTP 200." -ForegroundColor Green

}
catch {

    Write-Host "ERROR: No se pudo consultar el catalogo de especies." -ForegroundColor Red

    if ($null -ne $_.Exception.Response) {
        try {
            $Stream = $_.Exception.Response.GetResponseStream()
            $Reader = New-Object System.IO.StreamReader($Stream)
            $ErrorBody = $Reader.ReadToEnd()
            Write-Host $ErrorBody
        }
        catch {
        }
    }

    exit 1
}

# ------------------------------------------------------------
# Normalizar registros del catalogo
# ------------------------------------------------------------

$Registros = @()

if ($Catalogo -is [System.Array]) {
    $Registros = @($Catalogo)
}
elseif ($null -ne $Catalogo.registros) {
    $Registros = @($Catalogo.registros)
}
elseif ($null -ne $Catalogo.items) {
    $Registros = @($Catalogo.items)
}
elseif ($null -ne $Catalogo.data) {
    $Registros = @($Catalogo.data)
}
elseif ($null -ne $Catalogo.especies) {
    $Registros = @($Catalogo.especies)
}

Write-Host "Registros encontrados: $($Registros.Count)" -ForegroundColor Gray

# ------------------------------------------------------------
# Verificar Bovino
# ------------------------------------------------------------

$Bovino = $null

foreach ($Especie in $Registros) {

    if ($null -ne $Especie.nombre) {

        $NombreEspecie = $Especie.nombre.ToString().Trim().ToLower()

        if ($NombreEspecie -eq "bovino") {
            $Bovino = $Especie
            break
        }
    }
}

if ($null -ne $Bovino) {

    Write-Host "OK - La especie Bovino existe en el catalogo." -ForegroundColor Green

}
else {

    Write-Host "ADVERTENCIA - No se encontro Bovino en el catalogo." -ForegroundColor Yellow
}

# ------------------------------------------------------------
# Verificar que el nombre de prueba no exista previamente
# ------------------------------------------------------------

$NombreNormalizado = $NombreNuevo.Trim().ToLower()

$EspecieExistente = $null

foreach ($Especie in $Registros) {

    if ($null -ne $Especie.nombre) {

        $NombreActual = $Especie.nombre.ToString().Trim().ToLower()

        if ($NombreActual -eq $NombreNormalizado) {
            $EspecieExistente = $Especie
            break
        }
    }
}

if ($null -ne $EspecieExistente) {

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host " ADVERTENCIA: EL DATO DE PRUEBA YA EXISTE" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Nombre:" -ForegroundColor Yellow
    Write-Host $NombreNuevo
    Write-Host ""
    Write-Host "La prueba TC-M02-001 requiere registrar una especie nueva."
    Write-Host "No se ejecutara nuevamente sobre un nombre ya existente."
    Write-Host ""
    Write-Host "Cambia el nombre de prueba en el JSON/PS1 si necesitas"
    Write-Host "realizar una nueva alta."
    Write-Host ""

    exit 1
}

Write-Host "OK - El nombre de prueba no existe previamente." -ForegroundColor Green
Write-Host "Nombre de prueba: $NombreNuevo" -ForegroundColor Gray
Write-Host ""

# ------------------------------------------------------------
# Crear environment para Newman
# ------------------------------------------------------------

Write-Host "3. Generando environment de Newman..." -ForegroundColor Yellow

$Environment = @{
    id = "environment-tc-m02-g01"
    name = "TC-M02-G01 TEST"
    values = @(
        @{
            key = "baseUrl"
            value = $BaseUrl
            enabled = $true
            type = "default"
        },
        @{
            key = "token"
            value = ""
            enabled = $true
            type = "default"
        },
        @{
            key = "nombreNuevo"
            value = $NombreNuevo
            enabled = $true
            type = "default"
        },
        @{
            key = "descripcionNueva"
            value = $DescripcionNueva
            enabled = $true
            type = "default"
        },
        @{
            key = "especieCreadaId"
            value = ""
            enabled = $true
            type = "default"
        }
    )
    _postman_variable_scope = "environment"
    schema = "https://schema.getpostman.com/json/environment/v2.1.0/environment.json"
}

$EnvironmentJson = $Environment | ConvertTo-Json -Depth 10

Set-Content `
    -LiteralPath $EnvironmentFile `
    -Value $EnvironmentJson `
    -Encoding UTF8

Write-Host "OK - Environment creado:" -ForegroundColor Green
Write-Host $EnvironmentFile
Write-Host ""

# ------------------------------------------------------------
# Ejecutar Newman
# ------------------------------------------------------------

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

$HtmlReport = Join-Path `
    $ResultadosDir `
    "TC-M02-G01-Newman-$Timestamp.html"

$JsonReport = Join-Path `
    $ResultadosDir `
    "TC-M02-G01-Newman-$Timestamp.json"

Write-Host "4. Ejecutando Newman..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Coleccion:" -ForegroundColor Gray
Write-Host $CollectionFile
Write-Host ""
Write-Host "Environment:" -ForegroundColor Gray
Write-Host $EnvironmentFile
Write-Host ""

$NewmanArguments = @(
    "run",
    $CollectionFile,
    "-e",
    $EnvironmentFile,
    "--reporters",
    "cli,htmlextra,json",
    "--reporter-htmlextra-export",
    $HtmlReport,
    "--reporter-json-export",
    $JsonReport
)

& newman @NewmanArguments

$NewmanExitCode = $LASTEXITCODE

# ------------------------------------------------------------
# Resultado final
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan

if ($NewmanExitCode -eq 0) {

    Write-Host " TC-M02-G01 FINALIZO SIN ASSERTIONS FALLIDAS" -ForegroundColor Green

}
else {

    Write-Host " TC-M02-G01 FINALIZO CON ASSERTIONS FALLIDAS" -ForegroundColor Red

}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Reporte HTML:" -ForegroundColor Yellow
Write-Host $HtmlReport

Write-Host ""
Write-Host "Reporte JSON:" -ForegroundColor Yellow
Write-Host $JsonReport

Write-Host ""
Write-Host "Casos ejecutados:" -ForegroundColor Cyan
Write-Host "  TC-M02-001 - Registrar especie nueva valida"
Write-Host "  TC-M02-002 - Rechazar nombre duplicado exacto"
Write-Host "  TC-M02-002 - Rechazar Bovino existente"
Write-Host "  TC-M02-002 - Rechazar bovino en minusculas"
Write-Host ""

if ($NewmanExitCode -eq 0) {

    Write-Host "RESULTADO: PASS" -ForegroundColor Green

}
else {

    Write-Host "RESULTADO: REVISAR REPORTE NEWMAN" -ForegroundColor Red

}

Write-Host ""

exit $NewmanExitCode