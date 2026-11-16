# Matriz de precondiciones AAEF — G118 (fixture 2026-11-15)

| Elemento | Identificador | Esperado | Encontrado | Resultado | Evidencia | Acción pendiente |
|---|---|---|---|---|---|---|
| Activo 2548 existe | `2548` | HTTP 200 | `200` | **CUMPLE** | GET /finanzas/activos/2548 | Ninguna |
| Código activo | `QA-AAEF-OVINO-01` | QA-AAEF-OVINO-01 | `QA-AAEF-OVINO-01` | **CUMPLE** | identificador | Ninguna |
| Finca asociada | `481` | 481 | `481` | **CUMPLE** | id_finca | Ninguna |
| Área/infraestructura | `1457` | 1457 | `1457` | **CUMPLE** | id_infraestructura | Ninguna |
| Reconocimiento 1248 | `1248` | presente | `[1248]` | **CUMPLE** | reconocimientos embebidos | Ninguna |
| Finca 481 (API configuración) | `HTTP 200` | HTTP 403 | `403` | **NO VERIFICABLE** | Limitación Contador; asociación verificada vía activo | Usar activo.id_finca=481 como evidencia alternativa |
| Costos 4476 y 4477 en activo 2548 | `4476,4477` | ambos presentes | `[4476, 4477]` | **CUMPLE** | GET /finanzas/costos?id_activo_biologico=2548 | Ninguna |
| Factura/datos costo 4476 | `CH-10421` | 350000 · 2026-11-14 · venc 2026-12-14 · cta 158405 · Concentrados del Huila S.A.S. | `{"id_registro_costo": 4476, "monto_costo": "350000.0000", "fecha_costo": "2026-11-14", "fecha_vencimiento_f...` | **CUMPLE** | detalle costos por activo (factura_prefijo/numero, fecha_vencimiento_factura, cuenta_debito) | Ninguna |
| Factura/datos costo 4477 | `VS-2287` | 180000 · 2026-11-14 · venc 2026-12-14 · cta 158405 · Clínica Veterinaria San Roque S.A.S. | `{"id_registro_costo": 4477, "monto_costo": "180000.0000", "fecha_costo": "2026-11-14", "fecha_vencimiento_f...` | **CUMPLE** | detalle costos por activo (factura_prefijo/numero, fecha_vencimiento_factura, cuenta_debito) | Ninguna |
| Período 622 CERRADO | `622` | CERRADO nov-2026 | `{"id_periodo_contable": 622, "estado": "CERRADO", "fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-30", ...` | **CUMPLE** | GET /finanzas/periodos | Ninguna |
| Período 623 ABIERTO | `623` | ABIERTO dic-2026 | `{"id_periodo_contable": 623, "estado": "ABIERTO", "fecha_inicio": "2026-12-01", "fecha_fin": "2026-12-31", ...` | **CUMPLE** | GET /finanzas/periodos | Ninguna |
| Titular AAEF en períodos | `Agropecuaria Aaef QA S.A.S.` | razón social + NIT | `[{"id_periodo_contable": 623, "estado": "ABIERTO", "fecha_inicio": "2026-12-01", "fecha_fin": "2026-12-31",...` | **CUMPLE** | periodos filtrados por NIT API | Ninguna |
| Período 220 NIT 900000003 intacto ABIERTO | `220` | ABIERTO | `{"id_periodo_contable": 220, "estado": "ABIERTO", "fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-30", ...` | **CUMPLE** | GET /finanzas/periodos — sin cierre | Ninguna |
| Vista previa Contador HTTP | `/integracion/aaef/vista-previa/productores/901333217?desde=2026-11-01&hasta=2026-11-30` | 200 | `200` | **CUMPLE** | GET vista-previa productores 901333217 | Ninguna |
| Documentos tipo 02 | `2 docs factura compra` | 2 × type 02 | `{"count": 2, "summary_TotalDocuments": 2, "types": ["02", "02"], "ids": ["COS-4476-20261114", "COS-4477-202...` | **CUMPLE** | body.invoices[].Header.Type.Code | Ninguna |
| IDs documentos COS | `COS-4476/4477-20261114` | ['COS-4476-20261114', 'COS-4477-20261114'] | `["COS-4476-20261114", "COS-4477-20261114"]` | **CUMPLE** | invoices[].Header.DocumentId | Ninguna |
| Totales bruto/neto | `530000 COP` | 530000 | `{"bruto": 530000.0, "neto": 530000.0, "currency": "COP"}` | **CUMPLE** | summary.TotalGrossAmount / TotalNet | Ninguna |
| Transactions | `0` | 0 | `0` | **CUMPLE** | summary.TotalTransactions | Ninguna |
| Auth externa AAEF (token) | `QA_AAEF_* env` | credenciales seguras disponibles | `{"QA_AAEF_CLIENT_ID": false, "QA_AAEF_CLIENT_SECRET": false, "QA_AAEF_EMAIL": false}` | **NO VERIFICABLE** | inspección de variables de entorno (sin leer secretos) | Rotar y entregar el client_secret por canal seguro (env local o gestor autorizado). |
| Escenario negativo período 220 | `900000003 / 220 ABIERTO` | HTTP 422 PERIODO_NO_CERRADO | `{"http": 422, "error_code": "PERIODO_NO_CERRADO"}` | **CUMPLE** | GET vista-previa productores 900000003 | Ninguna |
| TC-M06-50 cotización | `POST /finanzas/cotizaciones` | no ejecutar sin autorización | `NO_EJECUTADO` | **NO VERIFICABLE** | Escritura pendiente de autorización expresa | Autorizar POST cotización tras precondiciones de cotización |

**Resumen:** CUMPLE=18 · NO CUMPLE=0 · NO VERIFICABLE=3