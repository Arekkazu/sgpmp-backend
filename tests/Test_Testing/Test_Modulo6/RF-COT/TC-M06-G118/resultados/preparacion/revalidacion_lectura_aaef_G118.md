# TC-M06-G118 — Revalidación de lectura (AAEF + baseline)

Fecha (UTC): 2026-11-13 · Fase: solo lectura · POST cotizaciones: **no ejecutado**

## Resultado de la revalidación

| Consulta | Resultado |
|---|---|
| Activo 1571 | `QA-M06O-VR-03` · ACTIVO · VR neto `3760000.0000` · cálculo `2026-11-08T21:25:06.574099Z` |
| Líneas periodo 220 | **7** (sin cambio respecto a la preparación previa) |
| Periodo 220 (NIT 900000003) | **ABIERTO** |
| Periodo 219 (NIT 900000002) | **CERRADO** |
| Contratos AAEF (`GET /integracion/contratos`) | v1.0 **INACTIVO**; v2.0 **DEPRECADO**; **ninguna versión ACTIVO** |
| Vista previa AAEF Contador | HTTP **422** `CONTRATO_NO_ACTIVO` |
| Canal AAEF (`GET /integracion/aaef/productores/900000003`) | **No ejecutado** — credencial temporal no disponible en el entorno del agente |

## Credencial temporal

- No se encontró en variables de entorno del agente ninguna de: `QA_AAEF_*`, `AAEF_*`, `QA_CLIENT_*`, `CLIENT_ID`/`CLIENT_SECRET`.
- **No se escribió, imprimió ni persistió ninguna secret.**
- El endpoint de canal exige `Authorization: Bearer <token de canal>`.
- Ese token se obtiene con `POST /integraciones/agrofusion/token` (`client_id` + `client_secret` + `email`).
- En esta fase la instrucción vigente prohíbe operaciones POST; por tanto **tampoco** se emitió token de canal.

## Limitaciones abiertas (bloquean verificación AAEF)

1. **Contrato AAEF no activo** en TEST (confirmado por listado Contador y por vista previa).
2. **Credencial temporal aún no entregada** al agente por mecanismo seguro (env).
3. Incluso con credencial, el flujo de canal requiere un POST de emisión de token (auditoría `TOKEN_CANAL_EMITIDO`); hace falta autorización expresa para ese POST auxiliar (distinto del POST de cotización).
4. El periodo 220 está ABIERTO; RF-AE01 de canal opera sobre periodos cerrados — la consulta AAEF del rango noviembre 2026 puede no devolver paquete exportable aunque el contrato esté activo.

## Consultas posteriores al registro (preparadas; pendientes de autorización)

Tras un único `POST /finanzas/cotizaciones` autorizado sobre 1571:

1. `GET /finanzas/activos/1571`
2. `GET /finanzas/lineas?id_periodo_contable=220`
3. `GET /finanzas/periodos` (220 y 219)
4. `GET /finanzas/cotizaciones` + auditoría `COTIZACION_REGISTRADA`
5. AAEF: vista previa Contador y/o canal (si contrato ACTIVO + credencial + autorización de emisión de token)

## Confirmación

- Sin POST de cotizaciones.
- Sin SQL.
- Sin modificación de periodos, activos ni catálogo.
- Sin commit/push.

## Continuación — reevaluación 2026-11-13 (post novedades Samuel)

Nueva evidencia (sin alterar este archivo histórico): `resultados/reevaluacion_2026-11-13_aaef/`.

Hallazgo principal verificado por API: contrato **2.1 ACTIVO**; vista previa QA ahora `422 PERIODO_NO_CERRADO`; referencia 900000002 `200`. G118 sigue **no aprobado completo**.
