# Matriz de trazabilidad — reevaluación AAEF G118 (2026-11-13)

| Criterio | Evidencia requerida | Evidencia obtenida | Resultado | Observación |
|---|---|---|---|---|
| Existe contrato AAEF 2.1 | `GET /integracion/contratos` | Versión 2.1 presente | **APROBADO** | |
| ID de versión = 3 | Campo `id_version_contrato_aaef` | `3` | **APROBADO** | |
| Estado ACTIVA/ACTIVO | Estado en API | `ACTIVO` | **APROBADO** | API usa `ACTIVO` (Samuel: ACTIVA) |
| Fecha vigencia 2026-11-13 | `fecha_vigencia` | `2026-11-13` | **APROBADO** | `fecha_activacion` UTC 2026-11-14T01:49Z |
| Anexo mapeo AAEF v2.0 | `GET /integracion/anexos` + vínculo contrato | id anexo 2, `version_anexo=2.0`, `APROBADO` | **APROBADO** | |
| Transformador solo compras | `mapeadores` del contrato | `["COMPRAS"]` | **APROBADO** | Sin `COMPROBANTE_NIC41` |
| v1.0 INACTIVA | Listado contratos | `INACTIVO` | **APROBADO** | |
| v2.0 DEPRECADA | Listado contratos | `DEPRECADO` | **APROBADO** | |
| Contrato global | Ausencia de NIT/titular en versión | Sin campos de titular | **APROBADO** | |
| Cliente ID 5 / código QA | `GET /integracion/clientes` | HTTP 403 Contador | **BLOQUEADO** | Falta `clientes_externos` R |
| Canal exclusivo CONSULTA_AAEF | Canales del cliente | No obtenido | **BLOQUEADO** | |
| Sin canal M2M | Canales del cliente | No obtenido | **BLOQUEADO** | |
| Límite 60 req/min | `limite_por_minuto` | No obtenido | **BLOQUEADO** | |
| Credencial vigente a 27/11/2026 | Credencial activa | No obtenido | **BLOQUEADO** | Secret no en env |
| Auth canal AAEF | Token + GET productores | Sin secret; GET sin token → 401 | **BLOQUEADO** / negativa 401 **APROBADO** | Token POST no ejecutado |
| Vista previa QA sin CONTRATO_NO_ACTIVO | GET vista-previa 900000003 | 422 `PERIODO_NO_CERRADO` | **APROBADO** (error esperado) | No aprueba paquete |
| Paquete AAEF titular QA | Vista previa 200 con compras | No | **BLOQUEADO** | Período 220 abierto |
| Vista previa referencia 200 | GET 900000002 | 200 + header contrato 2.1 | **APROBADO** (referencia) | No sustituye QA |
| Estructura envelope | Keys metadata/summary/invoices/transactions | Presentes | **APROBADO** (estática) | invoices=0 en referencia |
| Mapeo compras funcional QA | Contenido vs anexo v2.0 | No | **BLOQUEADO** | |
| TC-M06-50 cotización | POST /finanzas/cotizaciones | No ejecutado | **PENDIENTE DE AUTORIZACIÓN** | Activo 1571 preparado |
