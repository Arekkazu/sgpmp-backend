# TC-M06-G118 — wrapper Newman (deshabilitado a proposito).
#
# Estado del grupo: APROBADO (TC-M06-50 cotizacion 15 / RF-94 29463).
# La evidencia oficial NO proviene de Newman; ver:
#   resultados/estado_oficial_G118.json
#   resultados/ejecucion_tc50_2026-11-15/
#   resultados/REPORTE_FINAL_G118_RF_AAEF.html
#
# Este script NO ejecuta la coleccion Postman ni realiza POST financieros.
# Cualquier re-ejecucion de cotizacion exige autorizacion expresa y el script
# autorizado (_ejecutar_tc50_autorizado.py), no Newman automatico.

$ErrorActionPreference = "Stop"
Write-Output "TC-M06-G118: Newman permanece deshabilitado (no es evidencia de aprobacion)."
Write-Output "Dictamen vigente: APROBADO. Consulte resultados/estado_oficial_G118.json"
Write-Output "Proteccion: no se lanza newman ni POST /finanzas/cotizaciones desde este wrapper."
exit 2
