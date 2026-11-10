# Preparación local ORD-G41-009 — G41 / RF-87

Estado: **preparado localmente**, sin veredicto de TEST. Casos originales `TC-M06-019` y `TC-M06-020`: `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv:384`. Se conservaron los oráculos de cierre, notificación, reportes y valor inicial; la única precisión del universo es la orden F3. RF y criterios consultados en `tests/Test_Testing/Test_Modulo6/CASOS_DE_USO_actualizado - Modulo 6.csv` y la fila 384 anterior. Los tres RUN históricos no se modificaron.

## Archivos y correcciones

Inventario revisado: `g41.mjs` (ejecutor canónico), `lib/g41_core.mjs`, `G41.postman_collection.json` (una colección vigente), `pruebas/g41_local.test.mjs`, `pruebas/newman_hijo.mjs`, `pruebas/registro_qa.mjs`, `pruebas/g41_dto.test.py` y `README.md`. No existe spec Cypress vigente porque estos casos son API. No se detectaron duplicados ni archivos de legado editables en G41.

| Hallazgo | Corrección local | Fuente revisada |
| --- | --- | --- |
| F1 | Se exige `general.pct_umbral_desviacion_precio` en el contraste GET, antes de toda escritura; el precio usa ese decimal. | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84`; `src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| F2 | Categoría de `especies` o PESO_KG por defecto; precio con `es_aplicado=true`, métrica nula y coincidencia de id con simulación 1569. | `src/financial_valuation/application/services/valorador.py:52-62`; `src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34`; `src/financial_valuation/infrastructure/routers/m06_router.py:206-216` |
| F3 | 1569/1570 medidos; 1571/1572/1573 sin medición, variación ni línea nueva; excluidos vacío y procesados ≥ 4. Se registran el número, ids medidos e ids ajenos como observación. | `src/financial_valuation/infrastructure/adapters/activo_financiero_m02_adapter.py:81-86`; orden ORD-G41-009 |
| F4 | Auditoría filtrada por período y ambos tipos de cierre; evento fallido solo en la rama de error. | `src/financial_valuation/infrastructure/routers/m06_router.py:498-508`; `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:54-79` |
| F5 | Se toman cuentas del mismo sentido: TB/PERDIDA ← PM/PERDIDA; PM/GANANCIA ← TB/GANANCIA; DEPRECIACION/UNICO ← BAJA/UNICO. El informe futuro imprimirá cada asignación realmente creada con cuenta y origen. | `src/financial_valuation/infrastructure/dto/m06_dto.py:49-61`; orden ORD-G41-009 |

## Contrato por ruta y campo leído

Cada campo de la tabla siguiente está declarado en `pruebas/contrato_g41.json`; la columna cita indica el origen del contrato, no una ejecución en TEST. Los campos de cuerpo se verifican por nombre y tipo en la prueba local. Las rutas con `{id}` cubren sus variantes de período o activo. La instrumentación `Proxy` registra lecturas del ensayo conforme y falla ante un campo leído que no figure en la forma declarada; la validación de forma falla si falta un campo declarado. La ruptura intencional del umbral en la raíz fue detectada antes de las escrituras.

| Método y ruta | Campo | Tipo/forma | Cita |
| --- | --- | --- | --- |
| POST /sesiones/ | cuerpo.correo_electronico | string | src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235 |
| POST /sesiones/ | cuerpo.contrasena | string | src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235 |
| POST /sesiones/ | respuesta.token | string | src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235 |
| GET /sesiones/me/permisos | respuesta.permisos[].nombre_recurso | string | src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235 |
| GET /sesiones/me/permisos | respuesta.permisos[].id_accion | integer | src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235 |
| GET /finanzas/periodos | respuesta[].id_periodo_contable | integer | src/financial_valuation/infrastructure/routers/m06_router.py:295-299 |
| GET /finanzas/periodos | respuesta[].numero_id_tributaria | string | src/financial_valuation/infrastructure/routers/m06_router.py:295-299 |
| GET /finanzas/periodos | respuesta[].fecha_inicio | date | src/financial_valuation/infrastructure/routers/m06_router.py:295-299 |
| GET /finanzas/periodos | respuesta[].fecha_cierre | date|null | src/financial_valuation/infrastructure/routers/m06_router.py:295-299 |
| GET /finanzas/periodos | respuesta[].estado | string | src/financial_valuation/infrastructure/routers/m06_router.py:295-299 |
| GET /finanzas/activos | respuesta[].id_activo_biologico | integer | src/financial_valuation/infrastructure/routers/m06_router.py:190-193 |
| GET /finanzas/activos | respuesta[].id_especie | integer | src/financial_valuation/infrastructure/routers/m06_router.py:190-193 |
| GET /finanzas/activos | respuesta[].estado | string | src/financial_valuation/infrastructure/routers/m06_router.py:190-193 |
| GET /finanzas/activos | respuesta[].valorado_por_costo | boolean | src/financial_valuation/infrastructure/routers/m06_router.py:190-193 |
| GET /finanzas/activos | respuesta[].depreciacion_acumulada | decimal|null | src/financial_valuation/infrastructure/routers/m06_router.py:190-193 |
| GET /finanzas/configuracion | respuesta.general.pct_umbral_desviacion_precio | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.especies[].id_especie | integer | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.especies[].categoria_precio | string|null | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.matriz[].id_asignacion_cuenta_contable | integer | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.matriz[].tipo_hecho | string | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.matriz[].sentido | string | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.matriz[].id_especie | integer|null | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.matriz[].subtipo_costo | string|null | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.matriz[].cuenta_debito | string | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/configuracion | respuesta.matriz[].cuenta_credito | string | src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39 |
| GET /finanzas/periodos/{id}/mediciones | respuesta[].id_medicion_posterior | integer | src/financial_valuation/infrastructure/routers/m06_router.py:234-239 |
| GET /finanzas/periodos/{id}/mediciones | respuesta[].id_activo_biologico | integer | src/financial_valuation/infrastructure/routers/m06_router.py:234-239 |
| GET /finanzas/periodos/{id}/mediciones | respuesta[].origen_medicion | string | src/financial_valuation/infrastructure/routers/m06_router.py:234-239 |
| GET /finanzas/periodos/{id}/mediciones | respuesta[].valor_razonable_anterior | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:234-239 |
| GET /finanzas/periodos/{id}/mediciones | respuesta[].valor_razonable_actual | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:234-239 |
| GET /finanzas/periodos/{id}/mediciones | respuesta[].variacion_total | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:234-239 |
| GET /finanzas/periodos/{id}/mediciones | respuesta[].ganancia_perdida_transformacion | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:234-239 |
| GET /finanzas/periodos/{id}/mediciones | respuesta[].ganancia_perdida_precio_mercado | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:234-239 |
| GET /finanzas/periodos/{id}/variaciones | respuesta[].id_variacion_valor_razonable | integer | src/financial_valuation/infrastructure/routers/m06_router.py:241-245 |
| GET /finanzas/periodos/{id}/variaciones | respuesta[].id_activo_biologico | integer | src/financial_valuation/infrastructure/routers/m06_router.py:241-245 |
| GET /finanzas/periodos/{id}/calculos | respuesta | array | src/financial_valuation/infrastructure/routers/m06_router.py:248-252 |
| GET /finanzas/lineas | respuesta[].id_linea_asiento_nic41 | integer | src/financial_valuation/infrastructure/routers/m06_router.py:225-230 |
| GET /finanzas/lineas | respuesta[].id_activo_biologico | integer | src/financial_valuation/infrastructure/routers/m06_router.py:225-230 |
| GET /finanzas/lineas | respuesta[].estado | string | src/financial_valuation/infrastructure/routers/m06_router.py:225-230 |
| GET /finanzas/lineas | respuesta[].tipo_hecho | string | src/financial_valuation/infrastructure/routers/m06_router.py:225-230 |
| GET /finanzas/lineas | respuesta[].sentido | string | src/financial_valuation/infrastructure/routers/m06_router.py:225-230 |
| GET /finanzas/lineas | respuesta[].id_especie | integer|null | src/financial_valuation/infrastructure/routers/m06_router.py:225-230 |
| GET /finanzas/lineas | respuesta[].subtipo_costo | string|null | src/financial_valuation/infrastructure/routers/m06_router.py:225-230 |
| GET /finanzas/periodos/{id}/prevalidacion | respuesta.bloqueos | array | src/financial_valuation/infrastructure/routers/m06_router.py:302-309 |
| GET /finanzas/periodos/{id}/prevalidacion | respuesta.activos_sin_precio | array | src/financial_valuation/infrastructure/routers/m06_router.py:302-309 |
| GET /finanzas/periodos/{id}/prevalidacion | respuesta.lineas_sin_trazabilidad | array | src/financial_valuation/infrastructure/routers/m06_router.py:302-309 |
| GET /finanzas/periodos/{id}/prevalidacion | respuesta.puede_cerrar | boolean | src/financial_valuation/infrastructure/routers/m06_router.py:302-309 |
| GET /finanzas/periodos/{id}/prevalidacion | respuesta.requiere_autorizacion | boolean | src/financial_valuation/infrastructure/routers/m06_router.py:302-309 |
| GET /notificaciones | respuesta.items[].id_notificacion | integer | src/identity_access/infrastructure/routers/notificaciones_routers.py:30-60 |
| GET /notificaciones | respuesta.items[].mensaje | string | src/identity_access/infrastructure/routers/notificaciones_routers.py:30-60 |
| GET /notificaciones | respuesta.total | integer | src/identity_access/infrastructure/routers/notificaciones_routers.py:30-60 |
| GET /finanzas/auditoria | respuesta.eventos[].tipo_evento | string | src/financial_valuation/infrastructure/routers/m06_router.py:498-508 |
| GET /finanzas/auditoria | respuesta.eventos[].id_referencia | integer | src/financial_valuation/infrastructure/routers/m06_router.py:498-508 |
| GET /finanzas/auditoria | respuesta.total_registros | integer | src/financial_valuation/infrastructure/routers/m06_router.py:498-508 |
| GET /finanzas/activos/{id} | respuesta.reconocimientos[].estado | string | src/financial_valuation/infrastructure/routers/m06_router.py:196-203 |
| GET /finanzas/activos/{id} | respuesta.reconocimientos[].fecha_reconocimiento | date | src/financial_valuation/infrastructure/routers/m06_router.py:196-203 |
| GET /finanzas/activos/{id} | respuesta.reconocimientos[].valor_razonable_neto_inicial | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:196-203 |
| GET /finanzas/activos/{id} | respuesta.mediciones[].id_medicion_posterior | integer | src/financial_valuation/infrastructure/routers/m06_router.py:196-203 |
| GET /finanzas/activos/{id} | respuesta.mediciones[].fecha_medicion | date | src/financial_valuation/infrastructure/routers/m06_router.py:196-203 |
| GET /finanzas/activos/{id} | respuesta.mediciones[].valor_razonable_anterior | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:196-203 |
| GET /finanzas/activos/{id} | respuesta.mediciones[].variacion_total | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:196-203 |
| GET /finanzas/activos/{id} | respuesta.calculos | array | src/financial_valuation/infrastructure/routers/m06_router.py:196-203 |
| GET /activos-biologicos/{id}/eventos | respuesta.eventos[].id_eventos | integer | src/biological_assets/infrastructure/routers/activo_biologico_router.py:1132-1170 |
| GET /finanzas/precios | respuesta[].id_precio_mercado | integer | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/precios | respuesta[].id_especie | integer | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/precios | respuesta[].categoria | string | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/precios | respuesta[].id_metrica_produccion | integer|null | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/precios | respuesta[].es_aplicado | boolean | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/precios | respuesta[].precio_unitario | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/precios | respuesta[].fuente | string | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/precios | respuesta[].fecha_vigencia | date | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/precios | respuesta[].fecha_vencimiento | date|null | src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34 |
| GET /finanzas/activos/{id}/simulacion | respuesta.es_valido | boolean | src/financial_valuation/infrastructure/routers/m06_router.py:206-216 |
| GET /finanzas/activos/{id}/simulacion | respuesta.precio.id_precio_mercado | integer | src/financial_valuation/infrastructure/routers/m06_router.py:206-216 |
| POST /finanzas/configuracion/matriz | cuerpo.tipo_hecho | string | src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121 |
| POST /finanzas/configuracion/matriz | cuerpo.sentido | string | src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121 |
| POST /finanzas/configuracion/matriz | cuerpo.id_especie | integer|null | src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121 |
| POST /finanzas/configuracion/matriz | cuerpo.subtipo_costo | string|null | src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121 |
| POST /finanzas/configuracion/matriz | cuerpo.cuenta_debito | string | src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121 |
| POST /finanzas/configuracion/matriz | cuerpo.cuenta_credito | string | src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121 |
| POST /finanzas/configuracion/matriz | respuesta.id_asignacion_cuenta_contable | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121 |
| PATCH /activos-biologicos/{id}/estado | cuerpo.estado_nuevo | string | src/biological_assets/infrastructure/dto/cambiar_estado_dto.py:25-48; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1343-1370 |
| PATCH /activos-biologicos/{id}/estado | cuerpo.fecha_cambio_estado | date | src/biological_assets/infrastructure/dto/cambiar_estado_dto.py:25-48; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1343-1370 |
| PATCH /activos-biologicos/{id}/estado | cuerpo.motivo_cambio | string | src/biological_assets/infrastructure/dto/cambiar_estado_dto.py:25-48; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1343-1370 |
| POST /activos-biologicos/{id}/eventos/baja | cuerpo.tipo_baja | string | src/biological_assets/infrastructure/dto/registrar_evento_baja_dto.py:15-45; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1223-1261 |
| POST /activos-biologicos/{id}/eventos/baja | cuerpo.fecha_baja | date | src/biological_assets/infrastructure/dto/registrar_evento_baja_dto.py:15-45; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1223-1261 |
| POST /activos-biologicos/{id}/eventos/baja | cuerpo.motivo_baja | string | src/biological_assets/infrastructure/dto/registrar_evento_baja_dto.py:15-45; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1223-1261 |
| POST /finanzas/precios | cuerpo.id_especie | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/precios | cuerpo.categoria | string | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/precios | cuerpo.precio_unitario | decimal | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/precios | cuerpo.fecha_vigencia | date | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/precios | cuerpo.fuente | string | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/precios | cuerpo.evidencia_documental | string | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/precios | cuerpo.confirmar_desviacion | boolean | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/precios | cuerpo.justificacion_estimacion | string? | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/precios | respuesta.id_precio_mercado | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146 |
| POST /finanzas/periodos/{id}/cierre | cuerpo.autorizar_exclusiones | boolean | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | cuerpo.incluir_activos_sin_precio | boolean | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.id_cierre | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.id_periodo_contable | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.periodo | string | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.estado | string | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.activos_procesados | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.activos_excluidos | array | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.lineas_excluidas | array | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.id_periodo_siguiente | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.reportes.estado_resultados.id_estado | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.reportes.estado_resultados.resultado_neto | decimal | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.reportes.informe_revelaciones.id_informe | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| POST /finanzas/periodos/{id}/cierre | respuesta.reportes.informe_revelaciones.version | integer | src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318 |
| GET /finanzas/estados-resultados/{id} | respuesta.resultado_neto | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:429-435 |

| GET /finanzas/periodos/{id}/estados-resultados | respuesta[].resultado_neto | decimal | src/financial_valuation/infrastructure/routers/m06_router.py:423-426; G41.postman_collection.json:6 |
| GET /finanzas/periodos/{id}/revelaciones | respuesta | array | src/financial_valuation/infrastructure/routers/m06_router.py:458-461; G41.postman_collection.json:7 |

| POST /finanzas/periodos/{id}/cierre | respuesta.comprobantes | array | src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:298-302 |
| POST /finanzas/periodos/{id}/cierre | respuesta.hash_cierre | string | src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:298-302 |

## Validación y límites

La suite local ejecuta decisiones previas y nuevas ramas en loopback: **71/71 pruebas** en verde. `node --check` para los tres módulos JavaScript y `node g41.mjs --comprobar` finalizaron bien. `node --test` no pudo iniciar el subproceso de pruebas en este sandbox (EPERM), por lo que se ejecutó directamente `node pruebas/g41_local.test.mjs`. El Python del sistema no tiene Pydantic; la prueba `pruebas/g41_dto.test.py` se ejecutó con `.venv/Scripts/python.exe` y validó cuerpos representativos contra los seis DTO Pydantic reales. La suite JavaScript contrasta además todos los cuerpos enviados en el ensayo conforme con el contrato. El fixture valida cada respuesta correcta contra el contrato antes de devolverla en todos los escenarios. Las cuatro respuestas alteradas intencionalmente para probar discrepancias de producto o ruptura de contrato se exceptúan de esa validación; la instrumentación de todas las rutas de lectura del ejecutor cubre el escenario conforme. Esa instrumentación no se repite en las ramas de error.

SHA-256: `g41.mjs` `8c32b1cf8b61c1ef0f4c643c9abb05c2bb4b5e7a106853762d87b4c1841fdc0f`; `lib/g41_core.mjs` `308bd42985135284f1816d579d24814bdb99d6d2f36eb01060b7bf2e65b11743`; `pruebas/g41_local.test.mjs` `35b19bd4bf2753eac3bd9270da4d55ca99fc374ea2c6fb6d7b957c01bdfd827e`; `pruebas/contrato_g41.json` `106c4da22d7e85f5a9c723324c2ecbcf99ba069b27d5a82fe6de003cc9445ea9`; `pruebas/g41_dto.test.py` `16b01c7862a3fe139aa49c4a8b8d17c4344337c04bc002f1a1a41870f9c49da0`; `G41.postman_collection.json` (sin cambio) `79b18ce89b560eddc8e1441f2ed28045a5f9774da1743c952afdf6af11f4a94b`; `README.md` `365c43b203f82be0ba3ef5d107c4862d8ee5f94bb428dd1c9e909f3b9924f5f4`.

No hubo acceso a TEST, red remota, SQL ni Git. Los ensayos locales temporales no constituyen evidencia de producto. El siguiente paso mínimo es revisión de QA y, solo con autorización particular del lanzador externo, un RUN de TEST.
