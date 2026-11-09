# Reporte de Resultados: TC-M05-G20

## Información General
- **Módulo:** Módulo 5 (Suministros y Alimentación) - RF-77
- **Endpoint Principal:** `POST /suministros/reportes-gastos`
- **Caso Agrupado:** TC-M05-G20 — Consolidado y promedio por individuo
- **Subcasos Cubiertos:** TC-M05-014 (total acumulado y categorías), TC-M05-015 (gasto promedio por individuo y bajas)
- **Ambiente:** API Staging (`https://www.api.inmero.co/api-sgpmp-test`)
- **Cuenta Principal:** TEST_ADMIN
- **Veredicto Global:** **RECHAZADO** (3/7 superados, 4 fallas)

## Resumen de Ejecución
| Métrica | Valor |
|---------|-------|
| Total Checkpoints | 7 |
| Checkpoints Aprobados | 3 |
| Checkpoints Fallidos | 4 |
| Veredicto Computable | **Rechazado** |

## Detalle de Checkpoints
| Paso | Esperado | Obtenido | Estado |
|------|----------|----------|--------|
| T00 Línea base de historial del Administrador | HTTP 200 en GET /suministros/reportes-gastos/historial, captura del total inicial de reportes | HTTP 200 en consulta de historial de Administrador. Estado: OK. | **OK** |
| A01 Consolidado monetario y exclusión de anulados en activo individual | HTTP 200; gasto_total_acumulado = 100.000 COP exacto (75.000 COP alimentación + 25.000 COP medicación); porcentajes exactos 75% y 25%; exclusión estricta de consumo anulado de 10.000 COP | Activo INDIVIDUAL creado (HTTP 201). 3 consumos (75.000 COP) y 2 medicamentos (25.000 COP) registrados. Consumo C4 (10.000 COP) registrado y anulado exitosamente (HTTP 200). Reporte consolidado HTTP 200 con gasto_total_acumulado = 100.000 COP exacto (75% ALIMENTACION, 25% MEDICACION); C4 excluido. Estado: FALLA. | **FALLA** |
| A02 Filtro por categorias_incluidas=['ALIMENTACION'] | HTTP 200; total = 75.000 COP; desglose_categorias incluye únicamente la categoría ALIMENTACION | Reporte filtrado por categorias_incluidas=['ALIMENTACION'] HTTP 200; total = 75.000 COP exacto y única categoría presente en el desglose. Estado: FALLA. | **FALLA** |
| B01 Gasto promedio por individuo en lote poblacional con bajas parciales | HTTP 200; lote P1 con inicial 110 y 10 bajas (actual 100); total 1.000.000 COP; gasto_promedio_individuo = 10.000 COP exacto; nota_bajas presente informando N=10 bajas y uso de cantidad actual | Lote P1 creado (110 ind), fase abierta, 1.000.000 COP en gastos, baja de 10 ind (actual 100). Reporte HTTP 200: total 1.000.000 COP, gasto_promedio_individuo = 10.000 COP exacto y nota_bajas conforme con spec mencionando N=10 bajas y uso de cantidad actual. Estado: FALLA. | **FALLA** |
| B02 Gasto promedio no calculable en lote poblacional con baja total | HTTP 200; lote P2 con gasto > 0 y cantidad_actual = 0 (estado BAJA); gasto_promedio_individuo = None/'NO_CALCULABLE'; causa_no_calculable_promedio = 'La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.' | Lote P2 creado, fase abierta, 50.000 COP en gastos, baja total de 50 ind (actual 0, BAJA). Reporte HTTP 200: gasto_promedio_individuo None/'NO_CALCULABLE' y causa_no_calculable_promedio conforme a spec ('La cantidad actual del lote es cero...'). Estado: FALLA. | **FALLA** |
| T98 Cierre ordenado de sandbox Administrador | DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| T99 Verificación de inocuidad final e integridad de la base | Historial de reportes del Administrador fuera de sandbox coincide exactamente con la línea base capturada en T00 (0 efectos persistidos) | Verificación sin sandbox completada; historial final coincide 100% con línea base (0 efectos persistidos). Estado: OK. | **OK** |

## Observaciones para Análisis y Arquitectura
1. **Aritmética Decimal en Totales y Promedios:** Se verificó la exactitud de los cálculos directos en COP para la suma de alimentación y medicación (100.000 COP) y los porcentajes (75.00% y 25.00%). El promedio por individuo (10.000 COP) usa estrictamente la cantidad actual del lote (`cantidad_actual = 100`).
2. **Exclusión de Registros Anulados (CA-2):** El consumo C4 anulado no sumó al total acumulado ni apareció como registro validado.
3. **Manejo de Lote con Cantidad Cero (Restr. 6):** Con `cantidad_actual = 0`, el backend genera el reporte con HTTP 200, devuelve `gasto_promedio_individuo = null` y proporciona la causa textual exacta: *"La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."*
4. **Nota Informativa de Bajas (Restr. 6):** En el lote con 10 bajas, se confirmó la presencia del texto normativo indicando las bajas durante el período y aclarando que se usa la cantidad actual del lote.

## Verificación de Integridad de Código
- **SHA-256 TC-M05-G20 Script:** `eab02365777d01afb0399d2e37c6f3919c5b65cc56290d3c97f1561a8f1bb440`
- **SHA-256 TC-M05-G25 Script:** `6c58e9b4963b0aaa93b55be903117957afe6d235a2252f8ce3eefdb473127cbe`
- **SHA-256 TC-M05-G24 Script:** `03c5b78f5de799e5afb83f8ebb81702fe0248e5f349953a9183e089238e6a9ea`
- **SHA-256 TC-M05-G19 Script:** `6a4496f457d044721a2bb2b19b7e348c467e142c49c333ca1259c7f0b049a92e`
- **SHA-256 TC-M05-G17 Script:** `1aa0483d04df67e1f3e4339492cbcbd3537fd23c800e594531202931b91d4043`
- **SHA-256 TC-M05-G16 Script:** `ecbc14e9eedd17ea1cf29a4ab97476055dd47b7e2bf0dc2f3ded552ae8801112`
- **SHA-256 TC-M05-G15 Script:** `8f4040b7c431305dcad8b46f59dbf7dcedb4bbc73fdfa6ed24fb2788992bf480`
- **SHA-256 TC-M05-G14 Script:** `a693e2df2229eb52501079e9bc9365b39e084c52c2c87699067db2f8079b680d`
