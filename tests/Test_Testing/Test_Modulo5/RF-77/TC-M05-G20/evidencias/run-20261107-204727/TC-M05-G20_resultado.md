# Reporte de Prueba: TC-M05-G20 (RF-77)
## Consolidado y Promedio por Individuo (Subcasos TC-M05-014 y TC-M05-015)

> **Tipo de corrida:** evaluacion oficial; corrida realizada tras corregir el test; la corrida anterior queda archivada en evidencias/.


- **ID Caso:** TC-M05-G20 (TC-M05-014 y TC-M05-015)
- **Ambiente:** `https://www.api.inmero.co/api-sgpmp-test`
- **Veredicto Global:** **RECHAZADO** (6/7 OK, 1 Fallas)
- **Fecha:** 2026-11-07 20:47:40 (America/Bogota)

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Línea base de historial del Administrador | HTTP 200 en GET /suministros/reportes-gastos/historial, captura del total inicial de reportes | HTTP 200 en consulta de historial de Administrador. Estado: OK. | **OK** |
| 2 | A01 Consolidado monetario y exclusión de anulados en activo individual | HTTP 200; gasto_total_acumulado = 100.000 COP exacto (75.000 COP alimentación + 25.000 COP medicación); porcentajes exactos 75% y 25%; exclusión estricta de consumo anulado de 10.000 COP | Activo INDIVIDUAL creado (HTTP 201). 3 consumos (75.000 COP) y 2 medicamentos (25.000 COP) registrados. Consumo C4 (10.000 COP) registrado y anulado exitosamente (HTTP 200). Reporte consolidado HTTP 200 con gasto_total_acumulado = 100.000 COP exacto (75% ALIMENTACION, 25% MEDICACION); C4 excluido. Estado: OK. | **OK** |
| 3 | A02 Filtro por categorias_incluidas=['ALIMENTACION'] | HTTP 200; total = 75.000 COP; desglose_categorias incluye únicamente la categoría ALIMENTACION | Reporte filtrado por categorias_incluidas=['ALIMENTACION'] HTTP 200; total = 75.000 COP exacto y única categoría presente en el desglose. Estado: OK. | **OK** |
| 4 | B01 Gasto promedio por individuo en lote poblacional con bajas parciales | HTTP 200; lote P1 con inicial 110 y 10 bajas (actual 100); total 1.000.000 COP; gasto_promedio_individuo = 10.000 COP exacto; nota_bajas presente informando N=10 bajas y uso de cantidad actual | Lote P1 creado (110 ind), fase abierta, 1.000.000 COP en gastos, baja de 10 ind (actual 100). Reporte HTTP 200: total 1.000.000 COP, gasto_promedio_individuo = 10.000 COP exacto y nota_bajas conforme con spec mencionando N=10 bajas y uso de cantidad actual. Estado: OK. | **OK** |
| 5 | B02 Gasto promedio no calculable en lote poblacional con baja total | gasto_promedio_individuo = 'NO_CALCULABLE'; causa_no_calculable_promedio = 'La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.' | AssertionError: Defecto de producto: gasto_promedio_individuo es null en lugar del literal 'NO_CALCULABLE' exigido por spec (Restr. 6). Causa textual observada: 'La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.'. | **FALLA** |
| 6 | T98 Cierre ordenado de sandbox Administrador | DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| 7 | T99 Verificación de inocuidad final e integridad de la base | Historial de reportes del Administrador fuera de sandbox coincide exactamente con la línea base capturada en T00 (0 efectos persistidos) | Verificación sin sandbox completada; historial final coincide 100% con línea base (0 efectos persistidos). Estado: OK. | **OK** |

## Diagnóstico de B02 (Defecto de Producto)
- **Causa Raíz:** El contrato OpenAPI y el DTO `ReporteGastoAcumuladoResponse` definen `gasto_promedio_individuo: Optional[Decimal]`. En consecuencia, cuando `cantidad_actual == 0`, el backend retorna `null` en lugar de la cadena literal `'NO_CALCULABLE'` estipulada en la especificación RF-77 (Restricción 6).
- **Hecho Observado en Respuesta API:**
  * `gasto_promedio_individuo`: `null`
  * `causa_no_calculable_promedio`: `"La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."`
  * `estado`: `"GENERADO"`