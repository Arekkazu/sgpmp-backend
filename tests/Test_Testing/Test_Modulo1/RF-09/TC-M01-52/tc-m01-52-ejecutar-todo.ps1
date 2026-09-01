# TC-M01-52 -- dispara la recuperacion, te da tiempo para pegar el token real,
# y espera automaticamente lo que falte para completar 16 minutos reales antes
# de probar que el token ya vencido es rechazado. Version PowerShell (Windows).
#
# IMPORTANTE: en cuanto el Paso 0 termine, ve a tu correo, copia el token del link,
# y pegalo en la variable "token_recuperacion" dentro de tc-m01-52.json (reemplaza
# el texto PEGAR_AQUI_EL_TOKEN_DEL_CORREO). Guarda el archivo. Luego vuelve a esta
# ventana y presiona Enter para que el script siga solo -- el descuenta automaticamente
# el tiempo que ya pasaste editando, para no esperar de mas.
# Para correr: .\tc-m01-52-ejecutar-todo.ps1

$coleccion = "tc-m01-52.json"
$minutosObjetivo = 16   # un poco mas de 15 para no arriesgar el limite justo

$inicio = Get-Date
Write-Host "=== Paso 0: disparando recuperacion ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "0. Disparar recuperacion" `
  -r htmlextra --reporter-htmlextra-export resultado-52-paso0.html

Write-Host ""
Write-Host "=== Ahora ve a tu correo, copia el token del link, y pegalo en tc-m01-52.json ==="
Write-Host "    (reemplaza PEGAR_AQUI_EL_TOKEN_DEL_CORREO por el token real, y GUARDA el archivo)"
Read-Host "Presiona Enter aqui cuando ya hayas guardado el archivo con el token real"

$transcurrido = (Get-Date) - $inicio
$restante = ($minutosObjetivo * 60) - $transcurrido.TotalSeconds

if ($restante -gt 0) {
    Write-Host ""
    Write-Host "=== Esperando $([math]::Round($restante)) segundos mas para completar ~$minutosObjetivo minutos reales... ==="
    Start-Sleep -Seconds $restante
} else {
    Write-Host ""
    Write-Host "=== Ya pasaron $([math]::Round($transcurrido.TotalMinutes,1)) minutos, no hace falta esperar mas ==="
}

Write-Host ""
Write-Host "=== Paso 1: probando el token ya vencido ($(Get-Date -Format 'HH:mm:ss')) ==="
newman run $coleccion --folder "1. Intentar usar el token ya expirado (15+ min despues)" `
  -r htmlextra --reporter-htmlextra-export resultado-52-paso1.html

Write-Host ""
Write-Host "=== Listo. Reportes generados: resultado-52-paso0.html, resultado-52-paso1.html ==="