# TC-M06-G45 — reevaluación V2 oficial - APROBADO

Grupo G45 · TC-M06-031, TC-M06-032, TC-M06-033 · RF-87 v1.1 · V2 · RUN-G45-V2-20261113-122125 · TEST. Autorización: AUT-G45-V2-R7-[RESERVADO]. Commit de referencia informado: 453277e4.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-031 | APROBADO | Criterios conformes |
| TC-M06-032 | APROBADO | Criterios conformes |
| TC-M06-033 | APROBADO | Criterios conformes |

## Preflight de datos y permisos

| Requisito | Esperado | Observado | Cumple | Bloqueante |
|---|---|---|---|---|
| permiso_cierre_periodo_5 | presente | "presente" | Sí | Sí |
| permiso_cierre_periodo_2 | presente | "presente" | Sí | Sí |
| permiso_costos_activos_1 | presente | "presente" | Sí | Sí |
| permiso_reconocimiento_inicial_4 | presente | "presente" | Sí | Sí |
| permiso_valoracion_activos_5 | presente | "presente" | Sí | Sí |
| permiso_valoracion_activos_2 | presente | "presente" | Sí | Sí |
| permiso_auditoria_financiera_2 | presente | "presente" | Sí | Sí |
| permiso_administrador_activos_biologicos_1 | presente | "presente" | Sí | No |
| periodo_7_estado | CERRADO | "CERRADO" | Sí | Sí |
| periodo_8_estado | EN_CIERRE, cierre 67 | {"estado":"EN_CIERRE","id_cierre":67} | Sí | Sí |
| periodo_219_estado | CERRADO | "CERRADO" | Sí | Sí |
| periodo_260_estado | ABIERTO | "ABIERTO" | Sí | Sí |
| periodo_266_estado | ABIERTO sin cierre | {"estado":"ABIERTO","ultimo_cierre":null} | Sí | No |
| linea_2625_en_219 | REGISTRADA y VERIFICADO | {"estado":"REGISTRADA","trazabilidad":"VERIFICADO"} | Sí | Sí |
| activo_944 | ACTIVO con reconocimiento en 7 | {"estado":"ACTIVO","reconocimiento":true} | Sí | Sí |
| activo_949 | ACTIVO con reconocimiento 20 en 7 | {"estado":"ACTIVO","reconocimiento":"CONFIRMADO"} | Sí | Sí |
| periodo_260_sin_ajustes | 0 | 0 | Sí | Sí |
| 031_configuracion_especies | categorías por especie | "HTTP 200; especies 322" | Sí | No |
| 031_220_sin_precio_especie_422 | activos 1569/1570/1571 sin precio vigente de especie 422 | {"activos_sin_precio":[],"especie_422_sin_precio_vigente":false} | No | No |
| 031_candidato_220 | ABIERTO, contiene hoy, sin bloqueos, causa de pausa y activo de la finca accesible; 266 admite ausencia de precio | {"estado":"ABIERTO","dentro":true,"bloqueos":0,"lineas_sin_trazabilidad":0,"activos_sin_precio":0,"activo_id":null,"estado_m02":null,"peso":null,"fecha_peso":null,"tipo":null,"cantidad":null} | No | No |
| 031_1644_tipo_cantidad | ficha o activo con tipo POBLACIONAL y cantidad actual positiva | {"tipo":"POBLACIONAL","cantidad":1} | Sí | No |
| 031_1644_fase_activa | fase productiva activa si la API la expone | {"fase_activa":null} | No | No |
| 031_candidato_266 | ABIERTO, contiene hoy, sin bloqueos, causa de pausa y activo de la finca accesible; 266 admite ausencia de precio | {"estado":"ABIERTO","dentro":true,"bloqueos":0,"lineas_sin_trazabilidad":0,"activos_sin_precio":1,"activo_id":1644,"estado_m02":"ACTIVO","peso":null,"fecha_peso":null,"tipo":"POBLACIONAL","cantidad":1} | Sí | No |

Período elegido para 031 y causa de pausa: {"id":266,"activo_id":1644,"tipo":"POBLACIONAL","cantidad_actual":1,"precio_peso":false,"categoria_precio":"POR_CABEZA","categoria_efectiva":"POR_CABEZA","categoria_por_defecto":false,"ultimo_peso":0,"fecha_ultimo_peso":null,"causa_pausa":{"lineas_sin_trazabilidad":0,"activos_sin_precio":1},"activos_sin_precio_ids":[1644]}.

## Esperado y observado por caso

### TC-M06-031 — APROBADO

- 031_en_cierre: se esperaba 409 EXCLUSION_REQUIERE_AUTORIZACION, EN_CIERRE y último cierre EN_PROCESO paso 3. Se observó HTTP 409; error EXCLUSION_REQUIERE_AUTORIZACION; estado EN_CIERRE; último cierre {"id_cierre":124,"estado":"EN_PROCESO","paso_actual":3,"activos_procesados":0,"activos_pendientes":0,"activos_excluidos":null,"precios_congelados":null,"error_detalle":null,"fecha_inicio":"2026-11-13T12:21:27.836101Z","fecha_fin":null,"tiempo_ejecucion_ms":null,"hash_cierre":null,"id_usuario_ejecutor":5,"nombre_usuari. Estado APROBADO. Evidencia G45-048.
- 031_costo: se esperaba cualquier 4xx sin cambio de líneas, costos ni variaciones. Se observó HTTP 422; contenido idéntico true. Estado APROBADO. Evidencia G45-054.
- 031_m02: se esperaba evento M02 encolado con timestamp_original y sin efectos en período EN_CIERRE. Se observó crecimiento HTTP 201; error_code ninguno; mensaje ninguno; evento 1949; fecha 2026-11-13; cola ENCOLADO_CIERRE visible; auditoria []; sin medicion propia en pausa true. Estado APROBADO. Evidencia G45-066.
- 031_escenario_b: se esperaba cancelación ABIERTO; registro propio de B en el período actual con fecha original. Se observó cancelación HTTP 200; estado ABIERTO; procesamiento HTTP 200; evidencia [{"fuente":"AUDITORIA","tipo":"MEDICION_SIN_VARIACION","id_evento_m02":1949,"id_periodo_contable":266}]; fecha original comprobada con historial M02. Estado APROBADO. Evidencia G45-077.
- 031_escenario_a: se esperaba segunda pausa; evento M02 encolado y procesado en período siguiente nuevo con fecha original. Se observó segunda pausa HTTP 409; cierre HTTP 200; período siguiente 547; nuevo true; procesamiento HTTP 200; exclusion 1644 true; evidencia [{"fuente":"AUDITORIA","tipo":"MEDICION_SIN_VARIACION","id_evento_m02":1950,"id_periodo_contable":547}]; efecto siguiente true; efecto en cerrado false; fecha original comprobada con historial M02. Estado APROBADO. Evidencia G45-105.

### TC-M06-032 — APROBADO

- 032_alta_costo: se esperaba Rechazo por período cerrado (CA-3: 409) y período 7 idéntico. Se observó HTTP 422; error_code PERIODO_CONTABLE_CERRADO; mensaje La fecha del costo pertenece a un período cerrado. Regístrelo como ajuste en el período abierto.; íntegro true. Estado APROBADO. Evidencia G45-110.
- 032_eliminar_reconocimiento: se esperaba HTTP 409 REVERSION_BLOQUEADA y 7 idéntico. Se observó HTTP 409; error REVERSION_BLOQUEADA; íntegro true. Estado APROBADO. Evidencia G45-115.
- 032_integridad: se esperaba 7 y 219 idénticos en estado, fecha, líneas, comprobantes y variaciones. Se observó integridad true. Estado APROBADO. Evidencia G45-123.

### TC-M06-033 — APROBADO

- 033_ajuste: se esperaba 201; AJUSTE_PERIODO_ANTERIOR en 260 con referencia 2625, justificación y auditoría. Se observó HTTP 201; período obtenido 260; línea true; auditoría true. Estado APROBADO. Evidencia G45-126.
- 033_cerrado_intacto: se esperaba 219 CERRADO con líneas, comprobantes, variaciones y fecha idénticos. Se observó integridad true. Estado APROBADO. Evidencia G45-130.

Las comprobaciones son solo API; no hay UI obligatoria para este grupo.

## Respuestas, integridad y seguimiento V1

Respuestas saneadas: {"crecimientos":[{"solicitud":"G45-055","http":201,"cuerpo":{"evento":{"id_eventos":1949,"id_activo_biologico":1644,"fecha":"2026-11-13T12:21:36.808000Z","descripcion":"Pesaje de verificacion G45","id_usuario":104,"crecimiento":{"tipo_medicion":"PESO","valor_medicion":"30.00","unidad_medida":"kg","tipo_agregacion":"PROMEDIO","frecuencia":null,"nuevo_peso_promedio":"30.0000","cantidad_medida":1},"baja":null,"sanitario":null,"productivo":null,"reproductivo":null,"ingreso":null},"fase_avanzada":false},"escenario":"B","cuerpo_enviado":{"tipo_medicion":"PESO","valor_medicion":"30","unidad_medida":"kg","fecha":"2026-11-13T12:21:36.808Z","descripcion":"Pesaje de verificacion G45","nuevo_peso_promedio":"30","cantidad_medida":1,"tipo_agregacion":"PROMEDIO"}},{"solicitud":"G45-083","http":201,"cuerp.
Bases: {"7":{"estado":"CERRADO","fecha_cierre":"2026-11-07T20:11:44.408365Z","ultimo_cierre":{"id_cierre":1,"estado":"COMPLETADO","paso_actual":9,"activos_procesados":8,"activos_pendientes":0,"activos_excluidos":[{"id_linea":9,"faltantes":["lecturas_nic41"],"tipo_hecho":"VARIACION_VR_TB","nivel_fallo":1,"id_activo_biologico":943}],"precios_congelados":[{"fuente":"MERCADO_ACTIVO","id_especie":39,"fecha_vigencia":"2026-11-07","precio_unitario":"9300.00","id_precio_mercado":17},{"fuente":"UPRA","id_especie":421,"fecha_vigencia":"2026-11-01","precio_unitario":"14500.00","id_precio_mercado":16}],"error_detalle":null,"fecha_inicio":"2026-11-07T20:11:36.147116Z","fecha_fin":"2026-11-07T20:11:44.408365Z","tiempo_ejecucion_ms":8261,"hash_cierre":"4537aa86903869b2e7df2d1e3a11a6531dd2f7f00b65233abdfe86adfbb.
Seguimiento de INC-M06-G45-01, 02 y 03: {"INC-M06-G45-01":"CORREGIDA","INC-M06-G45-02":"CORREGIDA","INC-M06-G45-03":"CORREGIDA"}.
Rutas M02 revisadas y motivo: {"activo_id":1644,"ultimo_peso":0,"fecha_ultimo_peso":null,"evento_ids":[1949,1950],"crecimientos":[{"escenario":"B","id_evento":1949,"timestamp_original":"2026-11-13T12:21:36.808000Z","peso_nuevo":"30","autor":"Administrador QA"},{"escenario":"A","id_evento":1950,"timestamp_original":"2026-11-13T12:21:41.924000Z","peso_nuevo":"35","autor":"Administrador QA"}]}.

## Incidencias de producto

Ninguna discrepancia de producto acreditada en este RUN.
## Evidencias y herramientas

Node v22.15.1; Newman 0; Cypress no aplica (0 pruebas); solicitudes 166.
- newman/newman-G45.html
- newman/newman-G45.json

## Problemas técnicos

Ninguno registrado.

## Observaciones

- 032: las rutas públicas de modificación y eliminación histórica de costos y variaciones no están disponibles; se comprueban las escrituras públicas pertinentes y la integridad.
- El vencimiento temporal de precios de la especie 422 y la asignacion temporal de usuarios_fincas fila 3493 se hacen fuera del RUN; el responsable QA revierte ambos al cerrar G45.
- OBS-G45-01 para Desarrollo: CA-3 pide 409; el producto responde HTTP 422 PERIODO_CONTABLE_CERRADO. Mensaje: La fecha del costo pertenece a un período cerrado. Regístrelo como ajuste en el período abierto..

## Cierre y rollback

DELETE del RUN: HTTP 200. Rollback verificado: sí. {"periodo_7":true,"periodo_8":true,"periodo_219":true,"periodo_220":true,"periodo_260":true,"periodo_266":true,"periodos_nuevos":true,"periodo_siguiente_ausente":true,"costos_944":true,"costos_031":true,"crecimientos_ausentes":true,"reconocimiento_949":true,"ajustes_ausentes":true}
Registro OFICIAL. Los tres casos cumplen las comprobaciones ejecutadas.
