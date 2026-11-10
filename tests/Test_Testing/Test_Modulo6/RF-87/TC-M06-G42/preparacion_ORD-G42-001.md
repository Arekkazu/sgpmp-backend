# Preparacion ORD-G42-001 - TC-M06-G42

Estado: **PREPARADO LOCALMENTE; sin RUN, sin TEST y sin veredicto de producto**. RF-87 v1.1; casos TC-M06-021, TC-M06-022 y TC-M06-023. La fila G42 de `Casos_Prueba(Modulo6Agrup).csv` fue leida en solo lectura. Los oraculos son los de esa fila y de la orden; los nombres de API se derivaron del codigo.

## Inventario y fuentes consultadas

G42 estaba vacia antes de la orden. Se revisaron G41 (`g41.mjs`, `lib/g41_core.mjs`, contrato, coleccion, pruebas, README y dependencias), G38 (`g38.mjs`, crecimiento M02) y G39 (`g39.mjs`, costos y facturas RF-90), todos en solo lectura. En G42 hay un ejecutor, una coleccion vigente, contrato, librerias y pruebas locales; no hay duplicados ni legado. No existe spec Cypress porque los casos son solo API.

Fuentes de codigo consultadas realmente: `src/financial_valuation/infrastructure/routers/m06_router.py`; `src/financial_valuation/infrastructure/dto/m06_dto.py`; `src/financial_valuation/infrastructure/repositories/{asiento,costo,periodo,reporte,valoracion,auditoria_financiera}_repository.py`; `src/financial_valuation/application/use_cases/{cierre/ejecutar_cierre_periodo,costos/registrar_costo}_use_case.py`; `src/financial_valuation/application/services/{medidor,reportes}.py`; `src/financial_valuation/domain/services/consolidacion.py`; `src/biological_assets/infrastructure/{routers/activo_biologico_router.py,dto/registrar_evento_crecimiento_dto.py,schema/activo_biologico_schema.py}`; `src/biological_assets/application/use_cases/gestion/registrar_evento_crecimiento_use_case.py`; `src/identity_access/infrastructure/{routers/sesiones_routers.py,dependencies.py}`. Las citas de linea por campo constan en la tabla.

## Contrato derivado del codigo: campo por campo

Cada lectura instrumentada falla si accede a un campo no declarado. La prueba de ruptura fuerza `LECTURA_FUERA_CONTRATO` y `CAMPO_AUSENTE`. `?` indica campo opcional; no relaja el oraculo del producto.

| Metodo y ruta | Campo del cuerpo o respuesta | Tipo declarado | Cita de codigo |
| --- | --- | --- | --- |
| POST `/sesiones/` | `cuerpo.correo_electronico` | `string` | `src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235` |
| POST `/sesiones/` | `cuerpo.contrasena` | `string` | `src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235` |
| POST `/sesiones/` | `respuesta.token` | `string` | `src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235` |
| GET `/sesiones/me/permisos` | `respuesta.permisos[].nombre_recurso` | `string` | `src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235` |
| GET `/sesiones/me/permisos` | `respuesta.permisos[].id_accion` | `integer` | `src/identity_access/infrastructure/dto/usuario_dto.py:26-30; src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235` |
| GET `/finanzas/periodos` | `respuesta[].id_periodo_contable` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| GET `/finanzas/periodos` | `respuesta[].numero_id_tributaria` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| GET `/finanzas/periodos` | `respuesta[].fecha_inicio` | `date` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| GET `/finanzas/periodos` | `respuesta[].fecha_fin` | `date` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72` |
| GET `/finanzas/periodos` | `respuesta[].fecha_cierre` | `date|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| GET `/finanzas/periodos` | `respuesta[].estado` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| GET `/finanzas/periodos` | `respuesta[].ultimo_cierre.id_cierre` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| GET `/finanzas/periodos` | `respuesta[].ultimo_cierre.id_usuario_ejecutor` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| GET `/finanzas/periodos` | `respuesta[].ultimo_cierre.fecha_fin` | `datetime` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299; src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,68-72,124-130` |
| GET `/finanzas/activos` | `respuesta[].id_activo_biologico` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:190-193` |
| GET `/finanzas/activos` | `respuesta[].id_especie` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:190-193` |
| GET `/finanzas/activos` | `respuesta[].estado` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:190-193` |
| GET `/finanzas/activos` | `respuesta[].valorado_por_costo` | `boolean` | `src/financial_valuation/infrastructure/routers/m06_router.py:190-193` |
| GET `/finanzas/activos` | `respuesta[].depreciacion_acumulada` | `decimal|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:190-193` |
| GET `/finanzas/configuracion` | `respuesta.general.pct_umbral_desviacion_precio` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.especies[].id_especie` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.especies[].categoria_precio` | `string|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.matriz[].id_asignacion_cuenta_contable` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.matriz[].tipo_hecho` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.matriz[].sentido` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.matriz[].id_especie` | `integer|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.matriz[].subtipo_costo` | `string|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.matriz[].cuenta_debito` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/configuracion` | `respuesta.matriz[].cuenta_credito` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:79-84; src/financial_valuation/domain/entities/contabilidad.py:33-39` |
| GET `/finanzas/periodos/{id}/mediciones` | `respuesta[].id_medicion_posterior` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:234-239` |
| GET `/finanzas/periodos/{id}/mediciones` | `respuesta[].id_activo_biologico` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:234-239` |
| GET `/finanzas/periodos/{id}/mediciones` | `respuesta[].origen_medicion` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:234-239` |
| GET `/finanzas/periodos/{id}/mediciones` | `respuesta[].valor_razonable_anterior` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:234-239` |
| GET `/finanzas/periodos/{id}/mediciones` | `respuesta[].valor_razonable_actual` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:234-239` |
| GET `/finanzas/periodos/{id}/mediciones` | `respuesta[].variacion_total` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:234-239` |
| GET `/finanzas/periodos/{id}/mediciones` | `respuesta[].ganancia_perdida_transformacion` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:234-239` |
| GET `/finanzas/periodos/{id}/mediciones` | `respuesta[].ganancia_perdida_precio_mercado` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:234-239` |
| GET `/finanzas/periodos/{id}/variaciones` | `respuesta[].id_variacion_valor_razonable` | `integer` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-322` |
| GET `/finanzas/periodos/{id}/variaciones` | `respuesta[].id_activo_biologico` | `integer` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-322` |
| GET `/finanzas/periodos/{id}/variaciones` | `respuesta[].tipo` | `string` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-322` |
| GET `/finanzas/periodos/{id}/variaciones` | `respuesta[].monto_variacion` | `decimal` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-322` |
| GET `/finanzas/periodos/{id}/variaciones` | `respuesta[].id_linea` | `integer` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-322` |
| GET `/finanzas/periodos/{id}/variaciones` | `respuesta[].tipo_evidencia` | `string` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-322` |
| GET `/finanzas/periodos/{id}/variaciones` | `respuesta[].estado_trazabilidad` | `string` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-322` |
| GET `/finanzas/periodos/{id}/calculos` | `respuesta[].id_calculo_valor_razonable` | `integer` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:324-330; src/financial_valuation/infrastructure/routers/m06_router.py:248-252` |
| GET `/finanzas/periodos/{id}/calculos` | `respuesta[].id_activo_biologico` | `integer` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:324-330; src/financial_valuation/infrastructure/routers/m06_router.py:248-252` |
| GET `/finanzas/periodos/{id}/calculos` | `respuesta[].fecha_calculo` | `datetime` | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:324-330; src/financial_valuation/infrastructure/routers/m06_router.py:248-252` |
| GET `/finanzas/lineas` | `respuesta[].id_linea_asiento_nic41` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].id_activo_biologico` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].estado` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].tipo_hecho` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].sentido` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].id_especie` | `integer|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].subtipo_costo` | `string|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].valor` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].cuenta_debito` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].cuenta_credito` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].numero_id_tributaria` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/lineas` | `respuesta[].id_periodo_contable` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230; src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83` |
| GET `/finanzas/periodos/{id}/prevalidacion` | `respuesta.bloqueos[].codigo` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:302-309` |
| GET `/finanzas/periodos/{id}/prevalidacion` | `respuesta.bloqueos[].mensaje` | `string?` | `src/financial_valuation/infrastructure/routers/m06_router.py:302-309` |
| GET `/finanzas/periodos/{id}/prevalidacion` | `respuesta.activos_sin_precio` | `array` | `src/financial_valuation/infrastructure/routers/m06_router.py:302-309` |
| GET `/finanzas/periodos/{id}/prevalidacion` | `respuesta.lineas_sin_trazabilidad[].id_linea` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:302-309` |
| GET `/finanzas/periodos/{id}/prevalidacion` | `respuesta.lineas_sin_trazabilidad[].tipo_hecho` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:302-309` |
| GET `/finanzas/periodos/{id}/prevalidacion` | `respuesta.puede_cerrar` | `boolean` | `src/financial_valuation/infrastructure/routers/m06_router.py:302-309` |
| GET `/finanzas/periodos/{id}/prevalidacion` | `respuesta.requiere_autorizacion` | `boolean` | `src/financial_valuation/infrastructure/routers/m06_router.py:302-309` |
| GET `/notificaciones` | `respuesta.items[].id_notificacion` | `integer` | `src/identity_access/infrastructure/routers/notificaciones_routers.py:30-60` |
| GET `/notificaciones` | `respuesta.items[].mensaje` | `string` | `src/identity_access/infrastructure/routers/notificaciones_routers.py:30-60` |
| GET `/notificaciones` | `respuesta.total` | `integer` | `src/identity_access/infrastructure/routers/notificaciones_routers.py:30-60` |
| GET `/finanzas/auditoria` | `respuesta.eventos[].tipo_evento` | `string` | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:66-76; src/financial_valuation/infrastructure/routers/m06_router.py:498-508` |
| GET `/finanzas/auditoria` | `respuesta.eventos[].id_referencia` | `integer` | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:66-76; src/financial_valuation/infrastructure/routers/m06_router.py:498-508` |
| GET `/finanzas/auditoria` | `respuesta.eventos[].id_usuario` | `integer|null` | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:66-76; src/financial_valuation/infrastructure/routers/m06_router.py:498-508` |
| GET `/finanzas/auditoria` | `respuesta.eventos[].timestamp_evento` | `datetime` | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:66-76; src/financial_valuation/infrastructure/routers/m06_router.py:498-508` |
| GET `/finanzas/auditoria` | `respuesta.eventos[].payload_evento.id_cierre` | `integer?` | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:66-76; src/financial_valuation/infrastructure/routers/m06_router.py:498-508` |
| GET `/finanzas/auditoria` | `respuesta.eventos[].payload_evento.paso` | `integer?` | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:66-76; src/financial_valuation/infrastructure/routers/m06_router.py:498-508` |
| GET `/finanzas/auditoria` | `respuesta.eventos[].payload_evento.error` | `string?` | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:66-76; src/financial_valuation/infrastructure/routers/m06_router.py:498-508` |
| GET `/finanzas/auditoria` | `respuesta.total_registros` | `integer` | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:66-76; src/financial_valuation/infrastructure/routers/m06_router.py:498-508` |
| GET `/activos-biologicos/{id}/eventos` | `respuesta.eventos[].id_eventos` | `integer` | `src/biological_assets/infrastructure/routers/activo_biologico_router.py:1132-1170` |
| GET `/finanzas/precios` | `respuesta[].id_precio_mercado` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/precios` | `respuesta[].id_especie` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/precios` | `respuesta[].categoria` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/precios` | `respuesta[].id_metrica_produccion` | `integer|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/precios` | `respuesta[].es_aplicado` | `boolean` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/precios` | `respuesta[].precio_unitario` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/precios` | `respuesta[].fuente` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/precios` | `respuesta[].fecha_vigencia` | `date` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/precios` | `respuesta[].fecha_vencimiento` | `date|null` | `src/financial_valuation/infrastructure/routers/m06_router.py:137-140; src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34` |
| GET `/finanzas/activos/{id}/simulacion` | `respuesta.es_valido` | `boolean` | `src/financial_valuation/infrastructure/routers/m06_router.py:206-216` |
| GET `/finanzas/activos/{id}/simulacion` | `respuesta.precio.id_precio_mercado` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:206-216` |
| POST `/finanzas/configuracion/matriz` | `cuerpo.tipo_hecho` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121` |
| POST `/finanzas/configuracion/matriz` | `cuerpo.sentido` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121` |
| POST `/finanzas/configuracion/matriz` | `cuerpo.id_especie` | `integer|null` | `src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121` |
| POST `/finanzas/configuracion/matriz` | `cuerpo.subtipo_costo` | `string|null` | `src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121` |
| POST `/finanzas/configuracion/matriz` | `cuerpo.cuenta_debito` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121` |
| POST `/finanzas/configuracion/matriz` | `cuerpo.cuenta_credito` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121` |
| POST `/finanzas/configuracion/matriz` | `respuesta.id_asignacion_cuenta_contable` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:49-61; src/financial_valuation/infrastructure/routers/m06_router.py:115-121` |
| POST `/finanzas/eventos/procesar` | `cuerpo` | `object` | `src/financial_valuation/infrastructure/routers/m06_router.py:219-222` |
| POST `/finanzas/eventos/procesar` | `respuesta` | `object` | `src/financial_valuation/infrastructure/routers/m06_router.py:219-222` |
| POST `/finanzas/precios` | `cuerpo.id_especie` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/precios` | `cuerpo.categoria` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/precios` | `cuerpo.precio_unitario` | `decimal` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/precios` | `cuerpo.fecha_vigencia` | `date` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/precios` | `cuerpo.fuente` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/precios` | `cuerpo.evidencia_documental` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/precios` | `cuerpo.confirmar_desviacion` | `boolean` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/precios` | `cuerpo.justificacion_estimacion` | `string?` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/precios` | `respuesta.id_precio_mercado` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77; src/financial_valuation/infrastructure/routers/m06_router.py:143-146` |
| POST `/finanzas/periodos/{id}/cierre` | `cuerpo.autorizar_exclusiones` | `boolean` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `cuerpo.incluir_activos_sin_precio` | `boolean` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.id_cierre` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.id_periodo_contable` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.periodo` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.estado` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.activos_procesados` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.activos_excluidos` | `array` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.lineas_excluidas` | `array` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.comprobantes` | `array` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.hash_cierre` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.id_periodo_siguiente` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.reportes.estado_resultados.id_estado` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.reportes.estado_resultados.resultado_neto` | `decimal` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.reportes.informe_revelaciones.id_informe` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| POST `/finanzas/periodos/{id}/cierre` | `respuesta.reportes.informe_revelaciones.version` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134; src/financial_valuation/infrastructure/routers/m06_router.py:312-318` |
| GET `/finanzas/estados-resultados/{id}` | `respuesta.resultado_neto` | `decimal` | `src/financial_valuation/infrastructure/repositories/reporte_repository.py:50-58` |
| GET `/finanzas/estados-resultados/{id}` | `respuesta.id_estado` | `integer` | `src/financial_valuation/infrastructure/repositories/reporte_repository.py:50-58` |
| GET `/finanzas/estados-resultados/{id}` | `respuesta.componentes.costos_mantenimiento` | `decimal` | `src/financial_valuation/infrastructure/repositories/reporte_repository.py:50-58` |
| GET `/finanzas/periodos/{id}/estados-resultados` | `respuesta[].id_estado` | `integer` | `src/financial_valuation/infrastructure/repositories/reporte_repository.py:61-66` |
| GET `/finanzas/periodos/{id}/estados-resultados` | `respuesta[].resultado_neto` | `decimal` | `src/financial_valuation/infrastructure/repositories/reporte_repository.py:61-66` |
| DELETE `/test-control/runs/{id}` | `respuesta` | `object` | `src/shared/rollback/presentation/test_control_router.py:31-40` |
| GET `/finanzas/costos` | `respuesta[].id_registro_costo` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-273; src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114` |
| GET `/finanzas/costos` | `respuesta[].subtipo_costo` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-273; src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114` |
| GET `/finanzas/costos` | `respuesta[].naturaleza_costo` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-273; src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114` |
| GET `/finanzas/costos` | `respuesta[].monto_costo` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-273; src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114` |
| GET `/finanzas/costos` | `respuesta[].fecha_costo` | `date` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-273; src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114` |
| GET `/finanzas/costos` | `respuesta[].id_periodo_contable` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-273; src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114` |
| GET `/finanzas/costos` | `respuesta[].id_activo_biologico` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-273; src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114` |
| POST `/finanzas/costos` | `cuerpo.subtipo_costo` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.origen_costo` | `string` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.monto_costo` | `decimal` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.fecha_costo` | `date` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.id_activo_biologico` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.naturaleza_costo` | `MANTENIMIENTO` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.tercero_nit` | `string?` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.tercero_dv` | `string?` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.tercero_razon_social` | `string?` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.factura_numero` | `string?` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.fecha_factura` | `date?` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `cuerpo.fecha_vencimiento_factura` | `date?` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/finanzas/costos` | `respuesta.registros[].id_registro_costo` | `integer` | `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124; src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:74-130; src/financial_valuation/infrastructure/routers/m06_router.py:277-281` |
| POST `/activos-biologicos/{id}/eventos/crecimiento` | `cuerpo.tipo_medicion` | `PESO` | `src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py:27-89; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1175-1220` |
| POST `/activos-biologicos/{id}/eventos/crecimiento` | `cuerpo.valor_medicion` | `decimal` | `src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py:27-89; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1175-1220` |
| POST `/activos-biologicos/{id}/eventos/crecimiento` | `cuerpo.unidad_medida` | `kg` | `src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py:27-89; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1175-1220` |
| POST `/activos-biologicos/{id}/eventos/crecimiento` | `cuerpo.descripcion` | `string?` | `src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py:27-89; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1175-1220` |
| POST `/activos-biologicos/{id}/eventos/crecimiento` | `respuesta.evento` | `object` | `src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py:27-89; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1175-1220` |
| POST `/activos-biologicos/{id}/eventos/crecimiento` | `respuesta.fase_avanzada` | `boolean` | `src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py:27-89; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1175-1220` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].id_comprobante_nic41` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].codigo` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].numero_id_tributaria` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].tipo_hecho` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].id_especie` | `integer` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].fecha_comprobante` | `date` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].lineas[].cuenta_debito` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].lineas[].cuenta_credito` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].lineas[].valor` | `decimal` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes` | `respuesta[].hash_integridad` | `string` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325; src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| GET `/finanzas/periodos/{id}/comprobantes/descarga?formato=csv` | `respuesta.Content-Type` | `text/csv` | `src/financial_valuation/infrastructure/routers/m06_router.py:327-331` |
| GET `/finanzas/periodos/{id}/comprobantes/descarga?formato=csv` | `respuesta.contenido` | `bytes` | `src/financial_valuation/infrastructure/routers/m06_router.py:327-331` |
| GET `/finanzas/periodos/{id}/comprobantes/descarga?formato=pdf` | `respuesta.Content-Type` | `application/pdf` | `src/financial_valuation/infrastructure/routers/m06_router.py:327-331` |
| GET `/finanzas/periodos/{id}/comprobantes/descarga?formato=pdf` | `respuesta.cabecera` | `%PDF` | `src/financial_valuation/infrastructure/routers/m06_router.py:327-331` |
| GET `/activos-biologicos/{id}/ficha-integral` | `respuesta.peso_actual` | `decimal|null` | `src/biological_assets/infrastructure/schema/activo_biologico_schema.py:403-440; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1690-1740` |
| GET `/activos-biologicos/{id}/ficha-integral` | `respuesta.unidad_peso` | `string` | `src/biological_assets/infrastructure/schema/activo_biologico_schema.py:403-440; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1690-1740` |
| GET `/activos-biologicos/{id}/metricas` | `respuesta.items[].tipo_medicion` | `string` | `src/biological_assets/infrastructure/schema/activo_biologico_schema.py:81-111; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1489-1530` |
| GET `/activos-biologicos/{id}/metricas` | `respuesta.items[].unidad_medida` | `string` | `src/biological_assets/infrastructure/schema/activo_biologico_schema.py:81-111; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1489-1530` |
| GET `/activos-biologicos/{id}/metricas` | `respuesta.items[].valor_min` | `decimal|null` | `src/biological_assets/infrastructure/schema/activo_biologico_schema.py:81-111; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1489-1530` |
| GET `/activos-biologicos/{id}/metricas` | `respuesta.items[].valor_max` | `decimal|null` | `src/biological_assets/infrastructure/schema/activo_biologico_schema.py:81-111; src/biological_assets/infrastructure/routers/activo_biologico_router.py:1489-1530` |

## Correccion local ORD-G42-002 (sin RUN ni TEST)

Se conservaron los oraculos de la fila TC-M06-G42 de `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv`, RF-87 v1.1 y las decisiones D1-D2. R1: el costo de noviembre pertenece al periodo anterior ya CERRADO cuando se evalua el RF-93 de diciembre; no se exige un periodo previo de NIT-C. R2: fecha de Bogota dentro de 219/220 y anterior a diciembre antes de cualquier escritura; costos, facturas y precios toman esa fecha. R3: G32 solo se reutiliza si HTTP 500 identifica `CIERRE_PERIODO_FALLIDO` en paso 3 y la auditoria de 8 contiene el mismo tipo, paso 3 y error de TGR-M06-26/trazabilidad/periodo CERRADO. Otro fallo produce INC-M06-G42-021 para Desarrollo con causa raiz sin determinar.

R4: el oraculo 021 coteja por (tipo_hecho, sentido, id_especie) y par de cuentas la suma decimal exacta de `valor` de lineas RF-86 REGISTRADA contra el comprobante. Exige correspondencia uno a uno de variaciones y lineas. La suma de abs(monto_variacion) se informa; una diferencia por redondeo frente al truncamiento de RF-86 es observacion, no rechazo. Los pesos creados se llevan a kg enteros si el rango M02 lo permite y los precios propuestos a enteros. Si no, `PESO_FUERA_RANGO_M02` documenta la imposibilidad. Citas de codigo leido: `src/financial_valuation/domain/services/nic41.py:38,155`, `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-322`, `src/financial_valuation/infrastructure/repositories/asiento_repository.py:72-83`.

R5: RF-93 se lee en detalle y listado publico. Se acepta cualquier clave publica con importes separados ALIMENTO, MEDICAMENTO, MANO_OBRA y VETERINARIO iguales a los cuatro costos del RUN; se registran las claves observadas en `componentes`. Falta de desglose: `sin_desglose_por_tipo`, candidato funcional sujeto a TEST. Citas leidas: `src/financial_valuation/domain/services/consolidacion.py:67-71,125-140` y `src/financial_valuation/infrastructure/repositories/reporte_repository.py:50-54`. R6: PDF validado en memoria por HTTP, Content-Type, tamano, SHA-256 y `%PDF`; solo CSV saneado se guarda. Se elimino `pruebas/sanear_pdf.py` y el test de saneamiento PDF. No hay Python ni directorios temporales en el ejecutor.

### Tabla de decisiones

| Fila | Esperado local |
| --- | --- |
| `023_sin_periodo_anterior_NIT_C` | 023 APROBADO si noviembre incluye costos y diciembre no; no busca costo previo. |
| `fecha_distinta_9` / `fecha_fuera_periodo` | 10 de noviembre permitido; 1 de diciembre NO_CONCLUYENTE y cero escrituras. |
| `cierre8_coincide_G32` | 021 RECHAZADO, referencia G32; 022/023 continuan. |
| `cierre8_otro_error` | 021 RECHAZADO, incidencia G42 nueva; 022/023 continuan. |
| `redondeo_monto` / `doble_conteo` / `especie_distinta` | Redondeo observacion; doble conteo y especie incorrecta fallan. |
| `rf93_clave_alterna` / `rf93_sin_desglose` | Desglose con nombre libre aprueba; ausencia rechaza 023. |
| `pdf_sin_python` | PDF no se guarda; metadatos y cabecera se comprueban. |
| `prevalidacion_bloqueada`, `rollback_fallido`, `newman_fallido` | No oficial; los casos independientes conservan su evaluacion. |

### Validaciones locales

- `node --check g42.mjs`: OK.
- `node pruebas/g42_local.test.mjs`: 31/31 OK.
- `node pruebas/g42_escenarios.test.mjs`: escenarios locales de loopback; ver salida final de Codex.
- `.venv/Scripts/python.exe pruebas/g42_dto.test.py`: Pydantic OK (una prueba).
- `node g42.mjs --comprobar`: OK; sin llamadas remotas.

### Residuos heredados

`g42-pdf-yssadehy/` y `pruebas/__pycache__/` permanecen en G42. La politica impide eliminarlos en esta orden; el responsable QA debe retirarlos. No son evidencia de este trabajo ni archivos vigentes.

### Salida de escenarios locales

```text
OK escenario_conforme: 021/022/023=APROBADO/APROBADO/APROBADO oficial=si solicitudes=127/260
OK escenario_cierre8_coincide_G32: 021/022/023=RECHAZADO/APROBADO/APROBADO oficial=si solicitudes=120/260
OK escenario_cierre8_otro_error: 021/022/023=RECHAZADO/APROBADO/APROBADO oficial=si solicitudes=120/260
OK escenario_cierre219_fallido: 021/022/023=APROBADO/RECHAZADO/APROBADO oficial=si solicitudes=107/260
OK escenario_rf93_sin_desglose: 021/022/023=APROBADO/APROBADO/RECHAZADO oficial=si solicitudes=127/260
OK escenario_rf93_clave_alterna: 021/022/023=APROBADO/APROBADO/APROBADO oficial=si solicitudes=127/260
OK escenario_redondeo_monto: 021/022/023=APROBADO/APROBADO/APROBADO oficial=si solicitudes=127/260
OK escenario_orden_distinto: 021/022/023=APROBADO/APROBADO/APROBADO oficial=si solicitudes=127/260
OK escenario_fecha_distinta_9: 021/022/023=APROBADO/APROBADO/APROBADO oficial=si solicitudes=127/260
OK escenario_fecha_fuera_periodo: 021/022/023=NO_CONCLUYENTE/NO_CONCLUYENTE/NO_CONCLUYENTE oficial=no solicitudes=0/260
OK escenario_prevalidacion_bloqueada: 021/022/023=NO_CONCLUYENTE/NO_CONCLUYENTE/NO_CONCLUYENTE oficial=no solicitudes=21/260
OK escenario_rollback_fallido: 021/022/023=APROBADO/APROBADO/APROBADO oficial=no solicitudes=127/260
OK escenario_newman_fallido: 021/022/023=APROBADO/APROBADO/APROBADO oficial=no solicitudes=127/260
```

### SHA-256 de archivos activos modificados

| Archivo | SHA-256 |
| --- | --- |
| `g42.mjs` | `172547f8bfa4372b131b288be40eecf360fb5d401dfb87fb99492657cf95e849` |
| `lib/g42_core.mjs` | `c1a5933f7532273a3490bd26be1ae749a66649c5644c9e0d632ac751916a8d18` |
| `pruebas/contrato_g42.json` | `9990e3bb07626051a8fdaa5dfa2b8433dc13beecf2bfdacb02fb68725eeb82b6` |
| `pruebas/g42_local.test.mjs` | `e2e527c923a0b02805fdfc1e96b27fe2c8d8916c0d12e1e238c440cbf498c26c` |
| `pruebas/g42_escenarios.test.mjs` | `bf574d1ce36f3b295a2df92390b26844254461da90ef0c835b91d88d7d401172` |
| `pruebas/g42_dto.test.py` | `d6d12d1899ae96d3a3e373dd7e88489b2412c22f326d48f2b9e66e3bc84426a8` |
| `README.md` | `99d6a0152c72731bbb0060e2613ec9052649919ec40db0eecc622e24e2b7ede9` |

La proxima accion es revision QA del paquete. Un RUN en TEST requiere autorizacion particular del lanzador externo. No se emitio veredicto de producto.
