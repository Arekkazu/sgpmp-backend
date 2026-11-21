# NARRATIVO DE REEVALUACION - TC-M05-G43 (RF-81 / RF-80) - REINTENTO 1

| Fecha      | Autor                    | Cambio |
|------------|--------------------------|--------|
| 12/11/2026 | Juan Sebastian Gutierrez | Narrativo oficial de promocion del Reintento 1 (run-20261112-083011) |

## 1. Contexto e incidente
- **Incidente**: INC-M05-284-G43
- **Commit evaluado**: `21513288` (#971) — eventos `CONSULTA_HISTORIAL_EJECUTADA` y `EXPORTACION_HISTORIAL_GENERADA` con `datos_nuevos` (`filtros_aplicados` y `total_registros_retornados`).
- **Linea base Ronda 1**: `evidencias/run-20261107-230054/`, Veredicto **RECHAZADO 5/10** (B01, B02, B03, A02, A03 en falla).

## 2. Corridas archivadas como no oficiales
- **`run-20261112-081621`**: Archivada como no oficial (`ARCHIVADO_NO_OFICIAL.txt`) por defectos del test: `TypeError` en los `finally` de A03 y T99 al indexar `requests.Response` como `dict`, `contexto_g43.json` no escrito (`obtenido` con `None`), esperados reescritos sin fuente y runner sin verificacion SHA-256 de las suites previas.
- **`run-20261112-082314`**: Archivada como no oficial (`ARCHIVADO_NO_OFICIAL.txt`) porque el runner salio con `exit 1` en la verificacion de integridad antes de ejecutar el escaneo de secretos, y `contexto_g43.json` no se escribio por usar `pytest_sessionfinish` en un archivo `test_*.py`.

## 3. Tabla de checkpoints (10 evaluados + A04 OBS)
| paso | esperado | fuente | obtenido | estado |
|---|---|---|---|---|
| T00 Setup de activo C y línea base (Admin) | Linea base de auditoria en T00, usuario autenticado y creacion de activo C + fase + 3 suministros en sandbox (HTTP 201) | Testing Harness / Setup de linea base | T00_auditoria_inicial HTTP 200 (total=69503, ultimo_id=76708); T00_usuarios_me HTTP 200 (id_usuario=104); T00_crear_activo_c HTTP 201 (id_activo_biologico=1879, id_ciclo=5, X-Request-Id=b1d3cd2c-2bb7-4b69-8a08-b11de4432bc4) | OK |
| B01 Auditoría de consulta con resultados (105 / 040) | HTTP 200 con 3 registros; exactamente 1 CONSULTA_HISTORIAL_EJECUTADA nuevo con id_usuario = /usuarios/me, id_activo_biologico = activo C, fecha_emision no nula, datos_nuevos.filtros_aplicados con cada filtro enviado y datos_nuevos.total_registros_retornados = 3 | RF-81 Fase 7, CA-8, Postcondicion 2 | B01_consultar_historial HTTP 200 (registros=3, X-Request-Id=01300b9d-6a8a-4a4e-85ec-8fe3956188c4); B01_auditoria_despues_p* HTTP 200 (eventos=[76861:CONSULTA_HISTORIAL_EJECUTADA:EXITOSO], total_registros_retornados=3, filtros_aplicados={"id_activo_biologico": 1879, "id_ciclo_productivo": 5, "fecha_inicio_filtro": "2026-08-01", "fecha_fin_filtro": "2026-08-31", "tipo_suministro_filtro": "TODOS", "origen_precio_filtro": "TODOS", "costo_min": null, "costo_max": null}) | OK |
| B02 Auditoría de consulta sin resultados (105 / 040, CU04 FA-01) | HTTP 200 con 0 registros; exactamente 1 CONSULTA_HISTORIAL_EJECUTADA nuevo con las mismas verificaciones de B01 y datos_nuevos.total_registros_retornados = 0 | RF-81 Fase 7, CA-8, E1; caso TC-M05-105/040 | B02_consulta_vacia HTTP 200 (registros=0, X-Request-Id=18fcca3b-24e3-463c-a43e-83aaa2504efe); B02_auditoria_despues_p* HTTP 200 (eventos=[76862:CONSULTA_HISTORIAL_EJECUTADA:EXITOSO], total_registros_retornados=0, filtros_aplicados={"id_activo_biologico": 1879, "id_ciclo_productivo": 5, "fecha_inicio_filtro": "2026-08-01", "fecha_fin_filtro": "2026-08-05", "tipo_suministro_filtro": "TODOS", "origen_precio_filtro": "TODOS", "costo_min": null, "costo_max": null}) | OK |
| B03 Auditoría de exportación síncrona PDF y Excel (105 / 040) | PDF y EXCEL: HTTP 200; por cada formato exactamente 1 EXPORTACION_HISTORIAL_GENERADA nuevo con id_usuario = /usuarios/me, id_activo_biologico = activo C, fecha_emision no nula, filtros_aplicados con cada filtro enviado y total_registros_retornados = 3 | RF-81 Fase 6 a, Fase 7, CA-8, Postcondicion 2 | B03_exportar_pdf HTTP 200 (X-Request-Id=de635276-140b-476f-91d5-2fa1d45a505b); audit HTTP 200 (eventos=[76863:EXPORTACION_HISTORIAL_GENERADA:EXITOSO], total_registros_retornados=3, filtros_aplicados={"id_activo_biologico": 1879, "id_ciclo_productivo": 5, "fecha_inicio_filtro": "2026-08-01", "fecha_fin_filtro": "2026-08-31", "tipo_suministro_filtro": "TODOS", "origen_precio_filtro": "TODOS", "costo_min": null, "costo_max": null}) / B03_exportar_excel HTTP 200 (X-Request-Id=b90b4530-e8cf-4818-adcc-92f7bb926426); audit HTTP 200 (eventos=[76864:EXPORTACION_HISTORIAL_GENERADA:EXITOSO], total_registros_retornados=3, filtros_aplicados={"id_activo_biologico": 1879, "id_ciclo_productivo": 5, "fecha_inicio_filtro": "2026-08-01", "fecha_fin_filtro": "2026-08-31", "tipo_suministro_filtro": "TODOS", "origen_precio_filtro": "TODOS", "costo_min": null, "costo_max": null}) | OK |
| B04 Naturaleza de solo lectura e inmutabilidad (102 / 037) | POST, PUT, PATCH, DELETE sobre /suministros/historial rechazados con 405 Method Not Allowed; historial inalterado | RF-81 Restr. 4 / TC-M05-102 (037) | POST=405, PUT=405, PATCH=405, DELETE=405 sobre /suministros/historial; B04_despues items=3 | OK |
| A01 Gestor de Granja consulta activo de su unidad (102 / 037) | HTTP 200 con items y resumen para activo 1042 en finca 464 asignada; PUT/DELETE rechazados (405) | RF-81 Restr. 1 / CA-3 / TC-M05-102 (037) | A01_gestor_su_finca HTTP 200 (items=50, X-Request-Id=24594807-0fbb-47f8-9db2-b8609dc97dc7); A01_gestor_put HTTP 405 | OK |
| A02 Rechazo a usuario sin la unidad del activo (102 / 037) | HTTP 403 con mensaje de E2 ('No tiene permisos para consultar el historial del activo [id]. Verifique su rol y unidades productivas asignadas.') y sin fuga de datos | RF-81 Restr. 1 / E2 / CA-3 / TC-M05-102 (037) | PENDIENTE_DIAGNOSTICO / AssertionError: DEFECTO DE PRODUCTO (E2 / CA-3): Se esperaba HTTP 403 con mensaje de permisos por rol y unidades, pero el backend respondio HTTP 404 ({"error_code":"ACTIVO_NO_ENCONTRADO","message":"El activo biológico 957 no existe.","field / A02_gestor_finca_ajena HTTP 404 (error_code=ACTIVO_NO_ENCONTRADO, X-Request-Id=4015c0e0-578b-4c29-8f78-e72b2d69d3c7) | FALLA |
| A03 Auditoría de consulta rechazada (102 / 037, CU04 FA-04) | Registro de al menos 1 evento de auditoría en la bitácora con resultado RECHAZADO tras el intento denegado | Caso CU04 FA-04 / TC-M05-102 (037) | PENDIENTE_DIAGNOSTICO / AssertionError: DEFECTO DE PRODUCTO (CU04 FA-04): No se registro evento de auditoria con resultado != 'EXITOSO' tras consulta no autorizada al activo 957 (HTTP 404). Eventos nuevos desde id 76708: 0. / A03_intento_rechazado HTTP 404 (error_code=ACTIVO_NO_ENCONTRADO, X-Request-Id=7707d804-f129-46cf-a88f-4cb4e73bec16); id_base=76708, eventos_nuevos=0 ([]), teardown_a03_admin HTTP 200 | FALLA |
| A04 [OBSERVACION] Productor consulta activo de su unidad | Productor consulta activo 957 de su unidad -> HTTP 200 (observacion fuera de spec RF-81) | Observacion de interoperabilidad (fuera de spec RF-81) | A04_productor_su_finca HTTP 200 (items=50, X-Request-Id=1dd832e0-0fa3-44e4-b00b-c1d8ed95f4cd) | OBS |
| T98 Cierre estricto de todas las corridas sandbox | Todas las corridas previas (t00, admin, gestor, productor) cerradas con DELETE /test-control/runs/{run_id} -> HTTP 200 ('Rollback exitoso') | Testing Harness / Sandbox Protocol | Corridas cerradas con DELETE 200 Rollback exitoso (t00:200, admin:200, productor:200, gestor:200, a03_admin:200, t99:200) | OK |
| T99 Inocuidad final en sandbox | Inocuidad en sandbox: total y max id de auditoria restaurados a T00; activo C y su historial retornan 404 y run t99 cierra con 200 Rollback exitoso | Testing Harness / Sandbox Protocol | T99_audit_inocuidad HTTP 200 (total=69503, max_id=76708 vs T00=76708), T99_activo_c_404 HTTP 404, T99_historial_c_404 HTTP 404, teardown_t99 HTTP 200 | OK |

## 4. Verificacion de INC-M05-284-G43 (eventos 76861-76864)
[HECHO] Con `id_usuario = 104` (`/usuarios/me`) e `id_activo_biologico = 1879` (creado en sandbox), se registraron los 4 eventos esperados en `GET /suministros/auditoria` con `datos_nuevos` completos:
- **76861** (B01): `CONSULTA_HISTORIAL_EJECUTADA`, `EXITOSO`, `total_registros_retornados = 3`.
- **76862** (B02): `CONSULTA_HISTORIAL_EJECUTADA`, `EXITOSO`, `total_registros_retornados = 0`.
- **76863** (B03 PDF): `EXPORTACION_HISTORIAL_GENERADA`, `EXITOSO`, `formato_exportacion = "PDF"`, `total_registros_retornados = 3`.
- **76864** (B03 EXCEL): `EXPORTACION_HISTORIAL_GENERADA`, `EXITOSO`, `formato_exportacion = "EXCEL"`, `total_registros_retornados = 3`.

```json
{
    "B01":  {
                "filtros_aplicados":  {
                                          "id_activo_biologico":  1879,
                                          "id_ciclo_productivo":  5,
                                          "fecha_inicio_filtro":  "2026-08-01",
                                          "fecha_fin_filtro":  "2026-08-31",
                                          "tipo_suministro_filtro":  "TODOS",
                                          "origen_precio_filtro":  "TODOS",
                                          "costo_min":  null,
                                          "costo_max":  null
                                      },
                "pagina":  1,
                "registros_por_pagina":  50,
                "total_registros_retornados":  3,
                "total_registros_filtrados":  3
            },
    "B02":  {
                "filtros_aplicados":  {
                                          "id_activo_biologico":  1879,
                                          "id_ciclo_productivo":  5,
                                          "fecha_inicio_filtro":  "2026-08-01",
                                          "fecha_fin_filtro":  "2026-08-05",
                                          "tipo_suministro_filtro":  "TODOS",
                                          "origen_precio_filtro":  "TODOS",
                                          "costo_min":  null,
                                          "costo_max":  null
                                      },
                "pagina":  1,
                "registros_por_pagina":  50,
                "total_registros_retornados":  0,
                "total_registros_filtrados":  0
            },
    "B03_PDF":  {
                    "filtros_aplicados":  {
                                              "id_activo_biologico":  1879,
                                              "id_ciclo_productivo":  5,
                                              "fecha_inicio_filtro":  "2026-08-01",
                                              "fecha_fin_filtro":  "2026-08-31",
                                              "tipo_suministro_filtro":  "TODOS",
                                              "origen_precio_filtro":  "TODOS",
                                              "costo_min":  null,
                                              "costo_max":  null
                                          },
                    "formato_exportacion":  "PDF",
                    "total_registros_retornados":  3
                },
    "B03_EXCEL":  {
                      "filtros_aplicados":  {
                                                "id_activo_biologico":  1879,
                                                "id_ciclo_productivo":  5,
                                                "fecha_inicio_filtro":  "2026-08-01",
                                                "fecha_fin_filtro":  "2026-08-31",
                                                "tipo_suministro_filtro":  "TODOS",
                                                "origen_precio_filtro":  "TODOS",
                                                "costo_min":  null,
                                                "costo_max":  null
                                            },
                      "formato_exportacion":  "EXCEL",
                      "total_registros_retornados":  3
                  }
}
```

## 5. Fallas de producto (ajenas a #971)
- **A02** (`FALLA`): Gestor de Granja consulta activo `957` (finca ajena) -> backend responde **HTTP 404** (`ACTIVO_NO_ENCONTRADO`) en lugar de **HTTP 403** (RF-81 E2). `X-Request-Id: 4015c0e0-578b-4c29-8f78-e72b2d69d3c7`.
  - *[INFERENCIA]*: La politica RLS en `modulo2.activos_biologicos` oculta el activo ajeno antes de que `AlcanceActivoPort` evalue pertenencia a la unidad.
- **A03** (`FALLA`): Tras el intento rechazado sobre el activo `957` (HTTP 404, `X-Request-Id: 7707d804-f129-46cf-a88f-4cb4e73bec16`), `GET /suministros/auditoria` reporto **0 eventos nuevos** desde `id_base = 76708`.

## 6. Observaciones
- **OBS-PAG**: Para `pagina=1, registros_por_pagina=2` (evento `76867`), `total_registros_retornados = 2` (items de la pagina) y `total_registros_filtrados = 3`.
- **OBS-R8**: En los eventos `76861`–`76864`, `ip_origen` e `id_sesion` son `null` pero `registro_incompleto = false` (`detalle_causa = null`).
- **OBS-HASH**: Los eventos `76861`–`76864` presentan `version_hash_integridad = 2` con hash SHA-256 hexadecimal de 64 caracteres valido.
- **PII en trazas**: `trazas_http.jsonl` guarda la respuesta completa de `GET /usuarios/me` (incluyendo telefono, direccion y fecha de nacimiento); conviene recortarla antes de cualquier commit al repositorio.

## 7. Inocuidad
[HECHO]
- `T00_auditoria_inicial` y `T99_audit_inocuidad` coinciden exactamente: `total = 69503`, `max_id = 76708`.
- `GET /activos-biologicos/1879` -> HTTP `404`; `GET /suministros/historial?id_activo_biologico=1879` -> HTTP `404`.
- Todas las 6 corridas sandbox (`t00`, `admin`, `gestor`, `productor`, `a03_admin`, `t99`) cerraron con `DELETE /test-control/runs/{run_id}` -> HTTP `200` (`"Rollback exitoso"`).

## 8. Veredicto
- **Veredicto oficial**: **RECHAZADO (8/10 OK, 2 FALLA)** por defectos de producto preexistentes en **A02** y **A03**.
- **Estado de INC-M05-284-G43 (#971)**: **CORREGIDO** (checkpoints **B01**, **B02** y **B03** aprobados).