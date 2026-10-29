$ErrorActionPreference = 'Stop'
$grupo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ejecutor = Join-Path $grupo 'g93.mjs'
$temporal = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$base = Join-Path $temporal ('g93-ensayo-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $base | Out-Null
$anteriorAutorizado = [Environment]::GetEnvironmentVariable('QA_AUTORIZADO', 'Process')
$anteriorModo = [Environment]::GetEnvironmentVariable('G93_ENSAYO_LOCAL', 'Process')
$aprobados = 0
try {
  foreach ($modo in @('ausentes', 'infra', 'hijo', 'tecnico')) {
    $operacion = if ($modo -eq 'infra') { 'reintentar' } else { 'evaluar' }
    $id = 'ENSAYO-G93-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + $modo
    $carpeta = Join-Path $base $id
    New-Item -ItemType Directory -Path $carpeta | Out-Null
    $contexto = Join-Path $carpeta 'contexto_operacion.json'
    $contenido = @{ grupo = 'G93'; version = 1; intento = 1; run_id = $id; operacion = $operacion.ToUpperInvariant();
      referencia = 'ENSAYO_LOCAL'; casos = @('TC-M03-184'); alcance_reevaluacion = $null;
      version_anterior = $null } | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($contexto, $contenido, (New-Object System.Text.UTF8Encoding($false)))
    [Environment]::SetEnvironmentVariable('QA_AUTORIZADO', 'SI', 'Process')
    [Environment]::SetEnvironmentVariable('G93_ENSAYO_LOCAL', $modo, 'Process')
    $salida = & node $ejecutor --autorizacion ENSAYO_LOCAL --operacion $operacion --version 1 --intento 1 --run-id $id --contexto $contexto 2>&1
    $codigo = $LASTEXITCODE
    $archivo = Join-Path $carpeta 'resultado.json'
    if (!(Test-Path -LiteralPath $archivo)) { throw "Falta resultado.json en $modo" }
    $r = Get-Content -LiteralPath $archivo -Raw | ConvertFrom-Json
    $p = Get-Content -LiteralPath (Join-Path $carpeta 'preflight.json') -Raw | ConvertFrom-Json
    $revisionTexto = & node $ejecutor --validar-resultado-local $archivo --run-id $id --version 1
    if ($LASTEXITCODE -ne 0) { throw "Contrato inválido en $modo" }
    $revision = $revisionTexto | ConvertFrom-Json
    $metadatosValidos = $revision.clasificacion -eq 'TECNICO' -and $revision.estado_run -eq 'PREPARADO'
    $metadatosValidos = $metadatosValidos -and $r.oficial -eq $false -and $r.consume_version -eq $false
    $metadatosValidos = $metadatosValidos -and $r.cierre.rollback.estado -eq 'NO_APLICA'
    $metadatosValidos = $metadatosValidos -and (Get-ChildItem -LiteralPath $carpeta -Filter '*.md').Count -eq 0
    if (!$metadatosValidos) {
      throw "Metadatos incorrectos en $modo"
    }
    $ausentesValidos = $codigo -ne 0 -and !$p.ok -and $r.casos.'TC-M03-184'.estado -eq 'NO_EJECUTADA'
    if ($modo -eq 'ausentes' -and !$ausentesValidos) { throw 'Escenario ausentes falló' }
    if ($modo -ne 'ausentes' -and !$p.ok) { throw "La carga .env.qa falló en $modo" }
    if ($r.operacion -ne $operacion -or $r.version -ne 1) { throw "Operación/versión incorrecta en $modo" }
    $hijoValido = $codigo -ne 0 -and ($r.problemas_tecnicos -join ' ') -match 'HIJO_NEWMAN_NO_DISPONIBLE'
    if ($modo -eq 'hijo' -and !$hijoValido) { throw 'Escenario hijo falló' }
    if ($modo -eq 'tecnico' -and $codigo -ne 0) { throw 'Escenario técnico no completó recorrido' }
    Write-Output ("{0}: exit={1}; preflight={2}; clasificación={3}/{4}; caso={5}" -f
      $modo, $codigo, $p.ok, $revision.clasificacion, $revision.estado_run,
      $r.casos.'TC-M03-184'.estado)
    $aprobados++
  }
  Write-Output "Ensayo local: $aprobados/4 escenarios conformes; sin conexión TEST ni informes creados."
} finally {
  [Environment]::SetEnvironmentVariable('QA_AUTORIZADO', $anteriorAutorizado, 'Process')
  [Environment]::SetEnvironmentVariable('G93_ENSAYO_LOCAL', $anteriorModo, 'Process')
  $resuelto = [IO.Path]::GetFullPath($base)
  if (!$resuelto.StartsWith($temporal, [StringComparison]::OrdinalIgnoreCase)) { throw 'Temporal fuera de os.tmpdir' }
  Remove-Item -LiteralPath $resuelto -Recurse -Force
}
