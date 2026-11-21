# TC-M01-96 (reformulado) -- ejecuta las 3 fases con las esperas reales YA integradas.
# Version para PowerShell (Windows). Solo corre este script UNA vez y espera a que termine solo
# (tarda un poco mas de 5 minutos y medio en total). No necesitas estar pendiente del reloj.
#
# IMPORTANTE: cada "newman run" es un proceso separado y por defecto NO recuerda las variables
# que guardo la fase anterior (como el id de la notificacion base). Por eso aqui se usa
# --export-environment / --environment para pasar ese "estado" de una fase a la siguiente
# a traves de un archivo (tc-m01-96-estado.json). No borres ese archivo mientras el script corre.

$coleccion = "tc-m01-96.json"
$estado = "tc-m01-96-estado.json"

# Si existe un estado viejo de una corrida anterior, lo borramos para empezar limpio
if (Test-Path $estado) { Remove-Item $estado }

Write-Host "=== Fase 1: notificacion base ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "Fase 1 - Notificacion base" `
  --export-environment $estado `
  -r htmlextra --reporter-htmlextra-export resultado-96-fase1.html

Write-Host ""
Write-Host "=== Esperando ~4 min 5 seg antes de la Fase 2 (no cierres esta ventana)... ==="
Start-Sleep -Seconds 245

Write-Host ""
Write-Host "=== Fase 2: dentro de la ventana anti-spam ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "Fase 2 - Dentro de la ventana (~4 min)" `
  --environment $estado --export-environment $estado `
  -r htmlextra --reporter-htmlextra-export resultado-96-fase2.html

Write-Host ""
Write-Host "=== Esperando ~1 min 30 seg antes de la Fase 3 (no cierres esta ventana)... ==="
Start-Sleep -Seconds 90

Write-Host ""
Write-Host "=== Fase 3: fuera de la ventana anti-spam ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "Fase 3 - Fuera de la ventana (~5:30 min)" `
  --environment $estado --export-environment $estado `
  -r htmlextra --reporter-htmlextra-export resultado-96-fase3.html

Write-Host ""
Write-Host "=== Listo. Reportes generados: resultado-96-fase1.html, resultado-96-fase2.html, resultado-96-fase3.html ==="