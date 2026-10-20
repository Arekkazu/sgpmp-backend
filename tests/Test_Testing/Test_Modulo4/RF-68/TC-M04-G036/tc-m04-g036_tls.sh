#!/usr/bin/env bash
# TC-M04-G036 - Comunicacion cifrada (ASVS V9): envio por HTTP plano y escaneo de configuracion TLS.
# Criterio: conexion insegura rechazada; sin cifrados debiles ni protocolos SSLv2/SSLv3/TLS 1.0/TLS 1.1 (solo TLS >= 1.2).
# SCRIPT SIN EJECUTAR: el ambiente de pruebas aun no esta listo.
# Uso: ./tc-m04-g036_tls.sh api.inmero.co [puerto]      (requiere testssl.sh o sslyze, y curl)
set -uo pipefail
HOST="${1:?host, ej. api.inmero.co}"; PORT="${2:-443}"; FALLOS=0
echo "== 1. HTTP plano (no debe procesarse la peticion) =="
CODE=$(curl -s -o /dev/null -m 10 -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"correo_electronico":"x@x.co","contrasena":"x"}' "http://${HOST}/back-sigab-test/sesiones/" || true)
echo "codigo HTTP plano: ${CODE:-sin respuesta}"
case "${CODE:-000}" in 000|301|302|307|308|400|403|404|426) echo "OK: rechazada o redirigida";; *) echo "FALLO: el servidor proceso la peticion sin cifrar"; FALLOS=$((FALLOS+1));; esac
echo "== 2. Escaneo TLS =="
if command -v testssl.sh >/dev/null 2>&1 || command -v testssl >/dev/null 2>&1; then
  T=$(command -v testssl.sh || command -v testssl)
  OUT=$("$T" --color 0 --protocols --std --quiet "${HOST}:${PORT}" 2>&1); echo "$OUT"
  echo "$OUT" | grep -E '^ *(SSLv2|SSLv3|TLS 1 |TLS 1.1)' | grep -q 'offered' && { echo "FALLO: protocolo inseguro ofrecido (<TLS 1.2)"; FALLOS=$((FALLOS+1)); }
  echo "$OUT" | grep -Eiq 'NULL|EXPORT|RC4|anon|3DES' && echo "$OUT" | grep -Ei 'NULL|EXPORT|RC4|anon|3DES' | grep -qi 'offered' && { echo "FALLO: cifrados debiles ofrecidos"; FALLOS=$((FALLOS+1)); }
elif command -v sslyze >/dev/null 2>&1; then
  OUT=$(sslyze --sslv2 --sslv3 --tlsv1 --tlsv1_1 --tlsv1_2 --tlsv1_3 "${HOST}:${PORT}" 2>&1); echo "$OUT"
  echo "$OUT" | grep -E 'SSL 2.0|SSL 3.0|TLS 1.0 Cipher|TLS 1.1 Cipher' -A2 | grep -q 'Accepted' && { echo "FALLO: protocolo inseguro aceptado (<TLS 1.2)"; FALLOS=$((FALLOS+1)); }
else
  echo "No se encontro testssl.sh ni sslyze: instalar uno de los dos"; exit 2
fi
[ "$FALLOS" -eq 0 ] && echo "VEREDICTO: APROBADO" || { echo "VEREDICTO: FALLIDO ($FALLOS hallazgo/s)"; exit 1; }
