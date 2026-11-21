# Reporte de Resultados: TC-M05-G22

## Información General

> **Tipo de corrida:** evaluacion oficial; corrida realizada tras corregir el test; la corrida anterior queda archivada en evidencias/.

- **Módulo:** Módulo 5 (Suministros y Alimentación) - RF-77
- **Endpoint Principal:** `POST /suministros/reportes-gastos`
- **Caso Agrupado:** TC-M05-G22 — Validación de rango y límites síncrono/asíncrono
- **Subcasos Cubiertos:** TC-M05-017 (validaciones E2, E3, E7, E9 y fecha futura), TC-M05-019 (límites de 12 meses individual y 6 meses agregado, E4 y E8)
- **Ambiente:** API Staging (`https://www.api.inmero.co/api-sgpmp-test`)
- **Veredicto Global:** **APROBADO** (12/12 superados, 0 fallas)

## Resumen de Ejecución
| Métrica | Valor |
|---------|-------|
| Total Checkpoints | 12 |
| Checkpoints Aprobados | 12 |
| Checkpoints Fallidos | 0 |
| Veredicto Computable | **Aprobado** |

## Detalle de Checkpoints
| Paso | Esperado | Obtenido | Estado |
|------|----------|----------|--------|
| T00 Línea base del historial y creación de activo QA con ciclo antiguo | HTTP 200 en historial, HTTP 201 en activo biológico con fecha_inicio_ciclo en el pasado y fase iniciada | HTTP 200 en consulta de historial de Administrador y activo QA con ciclo antiguo creado exitosamente. Estado: OK. | **OK** |
| A01 Rango de fechas invertido (fecha_inicio > fecha_fin) | HTTP 400 descriptivo y el historial de reportes no crece | HTTP 400 descriptivo obtenido ante fecha_inicio > fecha_fin; historial inalterado. Estado: OK. | **OK** |
| A02 Fecha fin futura posterior a la fecha actual | HTTP 400 descriptivo y el historial de reportes no crece | HTTP 400 descriptivo obtenido ante fecha fin futura; historial inalterado. Estado: OK. | **OK** |
| A03 Fecha de inicio anterior al inicio del ciclo productivo | HTTP 400 descriptivo y el historial de reportes no crece | HTTP 400 descriptivo obtenido ante fecha_inicio < ciclo; historial inalterado. Estado: OK. | **OK** |
| A04 Activo biológico sin ciclo productivo registrado | HTTP 422 descriptivo y el historial de reportes no crece | HTTP 422 descriptivo obtenido sobre activo sin ciclo (fecha_inicio_ciclo null); historial inalterado. Estado: OK. | **OK** |
| A05 Consulta agregada sin rango de fechas obligatorio | HTTP 400 descriptivo y el historial de reportes no crece | HTTP 400 descriptivo obtenido ante consulta agregada sin rango de fechas; historial inalterado. Estado: OK. | **OK** |
| B01 Límite síncrono para activo individual de 12 meses (<= 366 días) | HTTP 200 síncrono en tiempo <= 12 s (CA-7 / RNF) | Reporte individual frontera de 366 días (12 meses calendario exactos) respondió HTTP 200 síncrono en <= 12 s con id_reporte generado. Estado: OK. | **OK** |
| B02 Umbral asíncrono para activo individual que supera 12 meses (> 366 días) | HTTP 202 con id_cola, estado 'PENDIENTE' y mensaje explicativo del procesamiento asíncrono | Reporte individual frontera de 367 días (12 meses + 1 día) respondió HTTP 202 con id_cola, estado PENDIENTE y mensaje con meses y 'asíncrona'. Estado: OK. | **OK** |
| B03 Límite síncrono para consulta agregada de 6 meses (<= 183 días) | HTTP 200 síncrono en tiempo <= 12 s (Restr. 13) | Consulta agregada frontera de 183 días (6 meses calendario exactos) respondió HTTP 200 síncrono en <= 12 s con id_reporte generado. Estado: OK. | **OK** |
| B04 Umbral asíncrono para consulta agregada que supera 6 meses (> 183 días) | HTTP 202 con id_cola, estado 'PENDIENTE' y mensaje explicativo del procesamiento asíncrono | Consulta agregada frontera de 184 días (6 meses + 1 día) respondió HTTP 202 con id_cola, estado PENDIENTE y mensaje con meses y 'asíncrona'. Estado: OK. | **OK** |
| T98 Cierre ordenado de sandbox Administrador | DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| T99 Verificación de inocuidad final e integridad de la base | Historial de reportes del Administrador fuera de sandbox coincide exactamente con la línea base capturada en T00 (0 efectos persistidos) | Verificación sin sandbox completada; historial final coincide 100% con línea base (0 efectos persistidos). Estado: OK. | **OK** |

## Observaciones para Análisis y Arquitectura
1. **Fórmula Exacta del Umbral Síncrono/Asíncrono en Backend (HECHO OBSERVADO en código):**
   - Individual: `_DIAS_UMBRAL_ASYNC_INDIVIDUAL = 366` días. `filtros.dias = (fecha_fin - fecha_inicio).days + 1`. Si `filtros.dias > 366` se encola (`HTTP 202`), si `<= 366` es síncrono (`HTTP 200`).
   - Agregado: `_DIAS_UMBRAL_ASYNC_AGREGADO = 183` días. Si `filtros.dias > 183` se encola (`HTTP 202`), si `<= 183` es síncrono (`HTTP 200`).
2. **Validación de Fronteras Exactas:**
   - Activo individual: rango de 366 días (2025-08-01 a 2026-08-01) responde `HTTP 200` en <= 12 s (CA-7 / RNF).
   - Activo individual: rango de 367 días (2025-08-01 a 2026-08-02, 12 meses + 1 día) responde `HTTP 202` con `id_cola`, estado `PENDIENTE` y mensaje con meses y `asíncrona`.
   - Consulta agregada: rango de 183 días (2026-01-01 a 2026-07-02) responde `HTTP 200` en <= 12 s.
   - Consulta agregada: rango de 184 días (2026-01-01 a 2026-07-03, 6 meses + 1 día) responde `HTTP 202` con `id_cola`, estado `PENDIENTE` y mensaje explicativo.
3. **Inocuidad en Errores de Validación:**
   - En todos los casos de error de validación (A01..A05), se comprobó que el historial de reportes no creció (0 registros agregados).