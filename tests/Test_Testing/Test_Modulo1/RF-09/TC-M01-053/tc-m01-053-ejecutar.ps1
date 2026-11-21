# TC-M01-053 -- prueba la frontera de expiracion del token (14:59 aceptado / 15:01 rechazado).
# Usa 2 tokens reales SEPARADOS (uno por cada extremo). El script dispara cada uno, te
# pausa para que lo pegues en tc-m01-053.json, y espera automaticamente lo que falte
# para llegar al segundo exacto de cada prueba (descuenta el tiempo que ya usaste pegando
# el token). Version PowerShell (Windows). En total tarda un poco mas de 30 minutos porque
# son 2 esperas de ~15 min cada una, en secuencia (usa 2 de tus 3 solicitudes por hora).

$coleccion = "tc-m01-053.json"

function Esperar-Hasta($inicio, $segundosObjetivo, $etiqueta) {
    $transcurrido = (Get-Date) - $inicio
    $restante = $segundosObjetivo - $transcurrido.TotalSeconds
    if ($restante -gt 0) {
        Write-Host ""
        Write-Host "=== Esperando $([math]::Round($restante)) segundos mas para llegar a $etiqueta... ==="
        Start-Sleep -Seconds $restante
    } else {
        Write-Host ""
        Write-Host "=== Ya pasaron $([math]::Round($transcurrido.TotalSeconds)) segundos, no hace falta esperar mas para $etiqueta ==="
    }
}

# ---------- TOKEN A: se prueba a los 14:59 (899 segundos) ----------
$inicioA = Get-Date
Write-Host "=== 0A: disparando recuperacion para Token A ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "0A. Disparar recuperacion - Token A (se probara a los 14:59)" `
  --reporters "cli,htmlextra" --reporter-htmlextra-export resultado-053-0A.html

Write-Host ""
Write-Host "=== Ve a tu correo, copia el TOKEN A, y pegalo en la variable token_a de tc-m01-053.json ==="
Write-Host "    (reemplaza PEGAR_AQUI_EL_TOKEN_A_DEL_CORREO por el token real, y GUARDA el archivo)"
Read-Host "Presiona Enter aqui cuando ya hayas guardado el archivo con el Token A real"

Esperar-Hasta $inicioA 899 "14 minutos 59 segundos (Token A)"

Write-Host ""
Write-Host "=== 1A: probando Token A dentro del limite ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "1A. Usar token A a los 14:59 (debe ACEPTAR)" `
  --reporters "cli,htmlextra" --reporter-htmlextra-export resultado-053-1A.html

# ---------- TOKEN B: se prueba a los 15:01 (901 segundos) ----------
$inicioB = Get-Date
Write-Host ""
Write-Host "=== 0B: disparando recuperacion para Token B ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "0B. Disparar recuperacion - Token B (se probara a los 15:01)" `
  --reporters "cli,htmlextra" --reporter-htmlextra-export resultado-053-0B.html

Write-Host ""
Write-Host "=== Ve a tu correo, copia el TOKEN B (el nuevo, no el de antes), y pegalo en la variable token_b de tc-m01-053.json ==="
Write-Host "    (reemplaza PEGAR_AQUI_EL_TOKEN_B_DEL_CORREO por el token real, y GUARDA el archivo)"
Read-Host "Presiona Enter aqui cuando ya hayas guardado el archivo con el Token B real"

Esperar-Hasta $inicioB 901 "15 minutos 1 segundo (Token B)"

Write-Host ""
Write-Host "=== 1B: probando Token B fuera del limite ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "1B. Usar token B a los 15:01 (debe RECHAZAR)" `
  --reporters "cli,htmlextra" --reporter-htmlextra-export resultado-053-1B.html

Write-Host ""
Write-Host "=== Listo. Reportes generados: resultado-053-0A.html, resultado-053-1A.html, resultado-053-0B.html, resultado-053-1B.html ==="
Write-Host "=== 1A deberia salir en verde (200 OK). 1B deberia salir en verde tambien (401 esperado, es lo correcto en este caso). ==="