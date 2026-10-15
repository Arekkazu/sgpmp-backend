# ------------------------------------------------------------------
# Script de re-ejecución diferida: TC-M02-148
# Estado actual: BLOQUEADO
# Motivo: Requiere modelo de compatibilidad especie-sensor y catálogo
#         I3P-1 aplicado a especies, aún no implementados.
# Se ejecutará cuando el modelo esté disponible en TEST.
# ------------------------------------------------------------------
npx newman run sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/test_tc_m02_g85.json `
  --folder "TC-M02-148" `
  -r cli,htmlextra `
  --reporter-htmlextra-export sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/RESULTADOS/reporte_TC-M02-148.html `
  --reporter-htmlextra-title "Reporte TC-M02-148 (Retest post-implementación)"
