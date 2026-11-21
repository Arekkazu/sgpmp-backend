# TC-M06-G45 — RF-87

## ORD-G45-019 — preparación V2, ronda 8 (2026-11-13)

El crecimiento de 1644 usa el tipo y la cantidad actual leídos de la ficha M02 o del activo financiero. Para POBLACIONAL envía PESO en kg, `nuevo_peso_promedio` igual a `valor_medicion`, `cantidad_medida` y `tipo_agregacion: PROMEDIO`; con peso previo nulo, B usa 30 kg y A 35 kg. Para INDIVIDUAL omite los campos del lote. El preflight informa el tipo, la cantidad y la fase activa si la API la expone.

La evidencia de procesamiento de B y A se vincula al id del crecimiento propio. Admite auditorías `MEDICION_*` y líneas o variaciones con origen en ese evento, y conserva los registros usados en `resultado.json.respuestas.evidencias_medicion`. Durante EN_CIERRE exige ausencia de estos registros en el período elegido; B debe quedar en ese período tras cancelar y A en el período siguiente nuevo tras cerrar. Cuando la evidencia no contiene fecha del hecho, el acta identifica la comprobación con la fecha original del historial M02. Los oráculos de 031, 032 y 033 de la matriz se conservan.

Fuentes leídas: fila G45 de `Casos_Prueba(Modulo6Agrup).csv` (RF-87 y criterios), `AGENTS.md`, `lib/flujo_v2.mjs`, `pruebas/`, `README.md`, `registrar_evento_crecimiento_use_case.py`, su DTO y modelo, y `medidor.py`. Sin TEST, RUN ni consultas remotas.

## ORD-G45-018 - preparación V2, ronda 7 (2026-11-13)

El 031 prioriza 220, luego 266 y 241. El 220 solo se elige si está ABIERTO, contiene la fecha actual, su prevalidación no tiene bloqueos y muestra como sin precio a 1569, 1570 o 1571 (especie 422). El primer caprino ACTIVO de la finca 467 con reconocimiento a valor razonable y peso previo recibe crecimientos PESO de +5 kg (B) y +10 kg (A). La categoría POR_CABEZA permite comprobar el procesamiento mediante auditoría `MEDICION_SIN_VARIACION`, vinculada al evento M02 y al período contable, sin exigir variación monetaria. En A se exige el período siguiente nuevo y la exclusión `PENDIENTE_PRECIO` del activo; en B, el período 220.

`resultado.json.respuestas` conserva HTTP y cuerpo saneado de cada crecimiento, procesamiento y consulta de auditoría usada como evidencia. Un crecimiento no exitoso deja `031_m02` NO_CONCLUYENTE con código y mensaje; 032 y 033 continúan. El rollback compara 220 con su base y comprueba la ausencia del período siguiente y de los crecimientos propios. El vencimiento temporal de precios de la especie 422 y la asignación de `usuarios_fincas` fila 3493 son precondiciones externas al RUN que revierte el responsable QA al cerrar G45. No se valida su reversión desde el RUN.

Fuentes consultadas en esta ronda: fila G45 de `Casos_Prueba(Modulo6Agrup).csv` (RF-87 y criterios), `AGENTS.md` de la raíz, RUN V2 115410, `g45.mjs`, `lib/`, `pruebas/`, `README.md`, `G45.postman_collection.json`, `registrar_evento_crecimiento_use_case.py`, `registrar_evento_crecimiento_dto.py` y `medidor.py`. No se accedió a TEST ni se creó RUN.

## ORD-G45-016 - preparacion V2, ronda 6 (2026-11-13)

Se preparo la evaluacion local de TC-M06-031 con el periodo 266 como primer candidato, seguido de 241 y 220. El 266 exige ABIERTO, fecha actual incluida, cero bloqueos, 1644 en activos_sin_precio, ninguna ejecucion de cierre previa y GET /finanzas/activos/1644 HTTP 200 para el Contador. Si ese GET devuelve 404, queda registrado en preflight_datos y 266 se descarta. El activo 1644 es POR_CABEZA y no exige precio PESO_KG ni variacion contable para acreditar procesamiento.

Tras cada POST /finanzas/eventos/procesar, el flujo lee la auditoria financiera en formato TECNICO, filtrada por id_activo_biologico y paginada. Relaciona MEDICION_* con el crecimiento propio mediante id_referencia o payload_evento.id_evento y exige id_periodo_contable: ninguno en 266 durante EN_CIERRE, B en 266 tras cancelar, A en el periodo siguiente nuevo tras cerrar con autorizar_exclusiones=true. Una medicion propia en 266 durante la pausa o la de A en 266 cerrado rechaza; ausencia de auditoria propia deja el escenario NO_CONCLUYENTE. El cierre debe excluir el 1644 como PENDIENTE_PRECIO. La fuente M02 conserva el timestamp_original capturado; la auditoria de medicion pendiente no expone una fecha original de destino para compararla.

Rollback compara 266 ABIERTO, sin cierre, lineas, comprobantes, variaciones y costos, ademas de la ausencia del periodo siguiente creado. La asignacion temporal de finca 472 al Contador QA es una precondicion externa al RUN que el responsable QA revierte al cerrar G45. Se conservaron los tres casos, el ejecutor, la coleccion Newman y todas las pruebas anteriores. Se agregaron cinco escenarios nuevos (diez ejecuciones por variantes) y el simulador cubre precios_congelados con arreglo y null.

Fuentes consultadas realmente: fila G45 de Casos_Prueba(Modulo6Agrup).csv, el RUN V2 113954, AGENTS.md de la raiz, g45.mjs, lib/, pruebas/, README.md, G45.postman_collection.json, medidor.py, procesar_eventos_m02_use_case.py, m06_router.py, consultar_auditoria_financiera_use_case.py y auditoria_financiera_repository.py. RF-87 y criterios se leyeron de la matriz y de la orden. No se consulto TEST, no se creo RUN y no se uso Git.

## ORD-G45-008 · preparación V2, ronda 3 (2026-11-13)

El 032_alta_costo exige rechazo por período cerrado y período 7 idéntico. HTTP 409 con ese motivo aprueba sin observación; otro 4xx con ese motivo aprueba y añade OBS-G45-01 para Desarrollo con HTTP, error_code y mensaje. Un 2xx o cambio de 7 rechaza; otra respuesta es NO_CONCLUYENTE. INC-M06-G45-02 solo se emite si el caso 032 termina RECHAZADO; el seguimiento V1 conserva CORREGIDA o REPRODUCIDA según el veredicto.

El 031 lee `GET /finanzas/configuracion` y compara `categoria_precio` de la especie del activo financiero. Solo crea crecimientos M02 con PESO_KG. Si el 241 no es apto y el 220 solo tiene POR_CABEZA, evalúa cierre y costo, cancela la pausa y registra 031_m02, 031_escenario_a y 031_escenario_b como NO_CONCLUYENTE con el motivo. Si la configuración no permite acreditar una categoría, no crea pesajes. Los 34 escenarios locales conservan los 30 anteriores y añaden 201 de costo cerrado y el 220 sin activo PESO_KG. No se consultó TEST ni se creó RUN.

Fuentes consultadas: fila G45 de `Casos_Prueba(Modulo6Agrup).csv`; decisión D2-V2 y criterios de la orden; `lib/flujo_v2.mjs`, `lib/informe.mjs`, `pruebas/` y configuración de especies en `m06_router.py`, `m06_dto.py`, `activo_financiero.py` y `configuracion_contable_repository.py`. No se leyó un documento RF-87 independiente ni se usó Git.

## ORD-G45-007 · preparación V2, ronda 2 (2026-11-13)

El ejecutor V2 conserva los tres casos y la colección Newman vigente. El Contador inicia sesión para cierre, cancelación, procesamiento, escrituras financieras y lecturas M06. El Administrador inicia una sesión adicional para leer la ficha e historial M02 y crear dos crecimientos. `preflight_datos` registra `permiso_administrador_activos_biologicos_1`, `permiso_valoracion_activos_5` y `permiso_cierre_periodo_5`. Si falta Crear al Administrador, 031_m02 queda NO_CONCLUYENTE con el requisito identificado; 032 y 033 continúan.

Para 031 se prueba 241 y luego 220; dentro de cada uno se consideran solo los candidatos de la orden, en su orden. La ficha pública aporta último peso y fecha, y la prevalidación descarta un activo sin precio. Se guardan período, activo y peso basal en `resultado.json`. El primer pesaje usa +5 kg y el segundo +10 kg respecto de ese peso. La API de historial identifica cada evento creado. El Contador procesa después de cada crecimiento y después de cancelar o cerrar. La medición filtrada por evento y período permite verificar el destino y `fecha_medicion` frente a la fecha original; en EN_CIERRE se exige ausencia de efectos en líneas, variaciones y mediciones propias. Si la respuesta de procesamiento no expone `ENCOLADO_CIERRE`, el acta indica que el estado de cola no fue visible y juzga la ausencia de efectos.

Después del DELETE, el rollback compara el historial de eventos con la base, comprueba que los dos IDs creados están ausentes, compara todos los períodos basales y comprueba que el período siguiente creado ya no existe. Un fallo de estas lecturas impide oficializar. La ruta de procesamiento también puede consumir eventos M02 y provisiones M05 ajenos; esto queda declarado en los efectos del preflight, igual que las llamadas de cierre. La prueba local usa un simulador HTTP en loopback y no crea RUN real ni consulta TEST.

Fuentes leídas en esta ronda: fila G45 de `Casos_Prueba(Modulo6Agrup).csv`; RF-87 y criterios resumidos en la orden y matriz; `registrar_evento_crecimiento_dto.py`, `activo_biologico_router.py`, `activo_biologico_schema.py`, `m06_router.py`, `procesar_eventos_m02_use_case.py`, `valoracion_repository.py` y `ejecutar_cierre_periodo_use_case.py`. No se consultó otro código ni un documento RF-87 independiente.

## ORD-G45-006 · preparación V2 (2026-11-13)

La automatización vigente es `g45.mjs` con el flujo V2 en `lib/flujo_v2.mjs`, una colección `G45.postman_collection.json` y solo API. La salida autorizada futura va en `EvaluacionV2/Resultados/RUN-G45-V2-.../`. En esta fase no se creó RUN ni se consultó TEST.

- 031 selecciona 241 y luego 220, únicamente si contiene la fecha de Bogotá, está ABIERTO, su prevalidación no tiene bloqueos y sí tiene una causa de pausa, y existe un activo ACTIVO de la finca asignada. La causa y el período quedan en `periodo_031` y `preflight_datos`. Si no hay candidato, 031 queda NO_CONCLUYENTE sin escrituras propias y 032/033 continúan.
- 031 verifica la pausa en paso 3, el rechazo del costo sin cambio de líneas, costos o variaciones, la cancelación a ABIERTO y el cierre autorizado a CERRADO. La ruta M02 de crecimiento existe y fue revisada junto con el historial de eventos. La única ruta pública para procesar la cola consume hasta 500 eventos M02 **y provisiones M05 sin filtro por evento**; por ello `031_m02` queda NO_APLICA con las rutas y el motivo en el resultado. No se usa el período 266.
- 032 conserva el oráculo de HTTP 409 sobre período 7 y la integridad de 7 y 219; el 8 se preflighta EN_CIERRE con cierre 67. 033 llama `POST /finanzas/lineas-asiento/2625/ajustes` y exige 201, línea de ajuste en 260, referencia 2625, justificación, auditoría y 219 intacto.
- Las bases se leen antes de escribir. Tras DELETE se comparan 7, 8, 219, 260, el elegido para 031, costos de ambos activos, reconocimiento del 949, ausencia de ajustes y ausencia de períodos nuevos. Las lecturas de rollback no están sujetas al presupuesto. Si se aborta sin escrituras y DELETE responde 200, el rollback se registra como verificado sin escrituras y la clasificación conserva la causa del aborto.
- El informe V2 usa el título y las fichas de rechazo de la orden; el seguimiento de incidencias V1 queda en `seguimiento_v1`. El ejemplo local conforme se conserva en `os.tmpdir()/g45-verificar-ejemplo/` con `resultado.json`, `capacidades.json`, el informe y reportes Newman simulados realmente generados.

Fuentes consultadas en esta ronda: fila G45 del CSV de casos de M06, el resumen RF-87 de la orden, `m06_router.py`, `m06_dto.py`, `registrar_ajuste_periodo_anterior_use_case.py`, `procesar_eventos_m02_use_case.py`, `evento_m02_adapter.py`, `periodo_repository.py`, `asiento_repository.py` y las rutas M02 de `activo_biologico_router.py`. No se leyó un documento RF-87 independiente porque no apareció en las rutas de fuentes indicadas. La sección siguiente describe la preparación V1 y se conserva como contexto histórico.

## Contexto V1

Órdenes `ORD-G45-001` y `ORD-G45-002`, fase preparar. Cubre por API TC-M06-031, 032 y 033 en TEST; este directorio contiene solo la automatización local. El lanzador externo debe proporcionar contexto y autorización particulares. Codex no ejecuta TEST.

## Archivos activos

- `g45.mjs`: ejecutor canónico, preflight, oráculos, DELETE y validación posterior.
- `G45.postman_collection.json`: única colección Newman vigente, cinco lecturas finales.
- `lib/infra.mjs`, `lib/contrato.mjs`, `pruebas/newman_hijo.mjs`: copias independientes de G44.
- `lib/informe.mjs`: plantilla de informe de G45.
- `pruebas/contrato_g45.json`: rutas y estructura de respuestas observables.
- `pruebas/simulador_g45.mjs`, `pruebas/g45_escenarios.test.mjs`, `pruebas/escenarios_g45.json`, `pruebas/verificar.mjs`: validación solo local.

No hay Cypress: la orden solo exige API. No hay ejecutores, colecciones ni artefactos históricos duplicados en G45.

## Oráculos

- 031: cierre sin autorización y lectura del período 8; solo EN_CIERRE tras 409 de exclusión aprueba.
- 032: costo y reversión sobre período 7 deben devolver 409, con 7 y 219 íntegros.
- 033: ajuste en 8 con referencia a línea del 7 y justificación, manteniendo 7 intacto.

Las operaciones no evaluables y no aplicables constan en `observaciones` del resultado. La OpenAPI es evidencia complementaria; solo se prueban `/openapi.json` y, ante 404, `/docs/openapi.json`. El ejecutor nunca autoriza exclusiones.

## Hallazgos de código local

Son `DEFECTO_FUNCIONAL_CANDIDATO`, sin veredicto de TEST: (1) el caso de uso de cierre revisado comprueba la autorización de exclusión antes de cambiar a EN_CIERRE; (2) el alta de costo revisada puede responder 422 para la fecha cerrada; (3) la reversión revisada bloquea cuando el cierre original es dependiente, mientras RF-87 exige una vía de ajuste en el período abierto. Las comprobaciones 031, 032 y 033 por API pública están preparadas para acreditar o descartar cada discrepancia en un RUN autorizado. Se consultaron la matriz de M06 línea 388, RF-87/RF-86/RF-82 en las líneas indicadas en `ORD-G45-001` y solo los tramos de backend citados allí. No se infiere el resultado de TEST del código local.

## Flujo autorizado futuro

Un inicio de sesión Contador, lectura de permisos y preflight de datos sin escrituras. Si pasa: POST cierre 8, POST costo 944, POST reversión 949, lecturas de ajustes e integridad, hasta dos GET OpenAPI, Newman, DELETE del RUN siempre y lecturas poscierre sin cabeceras. El informe solo se considera oficial con todas las comprobaciones concluyentes, reportes Newman reales, DELETE 200 y rollback verificado.

En V1 el lanzador crea `Resultados/RUN-G45-V1-<timestamp>/`; V2 requiere decisión explícita y va en `EvaluacionV2/Resultados/RUN-G45-V2-<timestamp>/`. El ejecutor escribe `resultado.json`, un solo `TC-M06-G45_resultado.md` o `TC-M06-G45_reevaluacion_V2.md`, y reportes Newman dentro del RUN. No hay RUN en esta carpeta durante preparar.

## Validación local

`node --check g45.mjs`, `node g45.mjs --comprobar`, `node g45.mjs --capacidades`, `node pruebas/verificar.mjs`. `verificar.mjs` deja un ejemplo simulado de `resultado.json` y `capacidades.json` en `os.tmpdir()/g45-verificar-ejemplo/` para validación del registro; no corresponde a TEST ni a un RUN oficial.

## Corrección ORD-G45-002 y origen de las formas simuladas

El historial de `/finanzas/activos/{id}` envuelve `DatosActivo` en `activo` y añade `reconocimientos`, `calculos`, `mediciones`, `productos`, `valoracion_costo` y `lineas` (`src/financial_valuation/infrastructure/routers/m06_router.py:196-203`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:273-293`; `src/financial_valuation/domain/entities/activo_financiero.py:17-37`). Los reconocimientos incluyen `id_reconocimiento_inicial`, `estado`, `id_periodo_contable`, `fecha_reversion` y `justificacion_reversion` (`src/financial_valuation/infrastructure/repositories/valoracion_repository.py:30-34,178-183`). El preflight de 944 exige el reconocimiento 15 CONFIRMADO en 7; el de 949 exige el 20 CONFIRMADO en 7. En `preflight_datos` solo quedan estado, finca e identificadores/estado/período de reconocimientos. La base de rollback de 949 conserva solo estado, fecha y justificación de reversión del 20 y el conjunto de ids, sin cabeceras ni datos personales. El simulador usa `TipoHecho` de `src/financial_valuation/domain/value_objects/nic41.py:11-25` y estados de período de `:110-113`; una compra no presupone línea de reconocimiento.

| Respuesta local simulada | Fuente de su forma |
| --- | --- |
| `POST /sesiones/`, `GET /sesiones/me/permisos` | `src/identity_access/infrastructure/dto/usuario_dto.py:26-30`; `src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235` |
| `GET /finanzas/periodos` | `src/financial_valuation/infrastructure/routers/m06_router.py:295-299`; `src/financial_valuation/infrastructure/repositories/periodo_repository.py:19-20,65,68-72,124-130`; `src/financial_valuation/domain/entities/contabilidad.py:16-23` |
| `GET /finanzas/periodos/8/prevalidacion` | `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:63-66,93-127`; `src/financial_valuation/application/use_cases/trazabilidad/verificar_trazabilidad_use_case.py:31-42` |
| `GET /finanzas/lineas` y `TipoHecho` | `src/financial_valuation/infrastructure/routers/m06_router.py:225-230`; `src/financial_valuation/infrastructure/repositories/asiento_repository.py:18-21,72-83`; `src/financial_valuation/domain/value_objects/nic41.py:11-25` |
| `GET /finanzas/periodos/{id}/comprobantes` | `src/financial_valuation/infrastructure/routers/m06_router.py:321-325`; `src/financial_valuation/infrastructure/repositories/periodo_repository.py:116-122` |
| `GET /finanzas/periodos/{id}/variaciones` | `src/financial_valuation/infrastructure/routers/m06_router.py:241-245`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:309-319` |
| `GET /finanzas/costos`, `POST /finanzas/costos` | `src/financial_valuation/infrastructure/routers/m06_router.py:267-281`; `src/financial_valuation/infrastructure/repositories/costo_repository.py:21-30,110-114`; `src/financial_valuation/infrastructure/dto/m06_dto.py:103-124` |
| `GET /finanzas/activos/{id}` | `src/financial_valuation/infrastructure/routers/m06_router.py:196-203`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:30-34,178-183,273-293`; `src/financial_valuation/domain/entities/activo_financiero.py:17-37` |
| `POST /finanzas/periodos/8/cierre`, `POST /finanzas/reconocimientos/949/reversion` | `src/financial_valuation/infrastructure/routers/m06_router.py:177-182,312-318`; `src/financial_valuation/infrastructure/dto/m06_dto.py:132-134`; `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:298-302` |
| `DELETE /test-control/runs/{id}` | `src/shared/rollback/presentation/test_control_router.py:31-40` |
| Errores `{error_code, message, fields, timestamp}` (409, 422, 404 y fallo simulado de DELETE) | `src/shared/error_handlers.py:40-68` |

`/openapi.json` y el fallback `/docs/openapi.json` son lecturas complementarias aprobadas en `ORD-G45-001`; el simulador entrega la estructura OpenAPI `paths` o el error citado, sin usarla como oráculo de producto. Las referencias de las respuestas anteriores provienen de `pruebas/contrato_g45.json` y de los tramos de backend expresamente indicados en la orden; en esta ronda se consultaron directamente `m06_router.py:186-205`, `valoracion_repository.py:30-34,178-183,273-293`, `activo_financiero.py` y `nic41.py:11-25,105-115`.

## ORD-G45-004: corrección local

K4: `pruebas/verificar.mjs` se copió byte a byte del G44 con SHA-256 `b8cfd167b1f44848aa27fb6ab719dd2813fd41e3173693c3cbb31859f4c7d316`. El único diff en ese archivo es A4:

```diff
-    const ejemplo=path.join(salidas,'conforme','resultado.json');
+    const ejemplo=path.join(os.tmpdir(),'g45-verificar-ejemplo');
+    fs.mkdirSync(ejemplo,{recursive:true});
+    fs.copyFileSync(path.join(salidas,'conforme_normal','resultado.json'),path.join(ejemplo,'resultado.json'));
+    fs.writeFileSync(path.join(ejemplo,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));
```

El directorio persistente se imprime antes de borrar el temporal. `simulador_base.mjs` adapta el nombre del simulador de G45 a la importación esperada por el verificador; `g45_cli.test.mjs` y `g45_dto.test.py` cubren el CLI/preflight y los bodies literales de costo y reversión con `CostoDTO` y `RevertirReconocimientoDTO` reales. El simulador no produce respuestas con modelo Pydantic. Los archivos de salida de la prueba local se espejan temporalmente en cada carpeta de escenario para que el paso 6 del verificador conserve su lógica original.

K5: `g45.mjs:109-110` clasifica el costo: 409 por período cerrado e integridad conservada aprueba; 422 por período cerrado rechaza por CA-3; 2xx o cambio del período rechaza; otros errores quedan no concluyentes. `g45.mjs:115-116` exige 409 con `REVERSION_BLOQUEADA` para aprobar la reversión; 2xx o cambio rechaza y otros errores quedan no concluyentes. `g45.mjs:136-137` asigna ALTA a escritura aceptada o alteración del período y MEDIA al 422 por período cerrado. `costo_422_validacion` y `reversion_400_motivo` quedan `NO_CONCLUYENTE` y sin INC-M06-G45-02, con y sin campos inyectados.

Validación local: `node --check g45.mjs`, `node --check pruebas/verificar.mjs`, `--comprobar`, `--capacidades`, 24 escenarios locales y el DTO Pydantic ejecutado directamente: OK. `verificar.mjs`: pasos 3, 5, 6, 8 y RED OK; pasos 2 y 9 NO_APLICA por ausencia de UI obligatoria; pasos 1, 4 y 7 marcados SANDBOX por `spawn EPERM`. Las comprobaciones directas de sintaxis y Pydantic pasaron. No se accedió a TEST ni se creó RUN. Los efectos previstos en TEST siguen siendo los de SOL-G45-001: inicio de sesión Contador, POST cierre 8, POST costo 944, POST reversión 949, lecturas API y Newman, DELETE siempre y lecturas posteriores sin cabeceras, sujetos al preflight y a autorización externa.

SHA-256 final: `g45.mjs` `9ea11a76b79feee27e5207065da54344e5273ef12763933a701aa3eae4d0673c`; `pruebas/verificar.mjs` `902874ba54870e01283396f190a6dd3d604ba5707d0ee4d81ae23589d9824b66`; `lib/infra.mjs` sin cambios `97562a7d9269eee82413be798d116a0e271277381fc3b69ba058199358874238`.
