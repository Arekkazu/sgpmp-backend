# TC-M06-G43 — preparación local de la reevaluación V3 de RF-87

## ORD-G43-036: reevaluación V3 tras e73c9c9e

El ejecutor canónico `g43.mjs` acepta `reevaluar --version 3` con `version_anterior=2` y `reintentar --version 3`. La salida autorizada se ubica en `EvaluacionV3/Resultados/RUN-G43-V3-…/`; esta preparación no creó un RUN ni consultó TEST. Se conservan la colección Newman, el spec/config Cypress y las pruebas históricas V1/V2.

El contrato admite `precios_congelados` con `id_especie` entero y `estimacion` booleana, además de la forma antigua y `null`. La respuesta del cierre admite objetos de `activos_estimados` con los identificadores de medición y precio; la petición sigue enviando enteros. Para 024 se guarda el congelado visible en ambas pausas. Para 026, `resultado.json.diagnostico.estimacion_1644` contiene cada vía y sus identificadores. Los oráculos de la fila G43 se mantienen.

Ensayos locales: `node pruebas/g43_v3_local.test.mjs` y `node pruebas/g43_v3_escenarios.test.mjs`; este último usa únicamente loopback y simula respuesta, auditoría, cálculo y recongelado. `node pruebas/verificar.mjs` genera en `%TEMP%/g43-verificar-ejemplo` un ejemplo V3 con `capacidades.json` para `registro_qa.py validar`. En este sandbox, el humo Cypress, el lanzador Newman y Pydantic pueden fallar con `spawn EPERM`; se deben ejecutar en el entorno Windows del responsable QA. El ejemplo es sintético y no acredita TEST.

Se consultaron por lectura la fila G43 de `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv`, RF-87 v1.2 en `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo6.md`, el RUN V2 `074459`, el diff `e73c9c9e` de `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py` y los archivos locales `src/financial_valuation/application/services/medidor.py` y `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py`. No se consultaron otras rutas de producción para esta ronda.

## ORD-G43-030: corrección local, ronda 10

El caso 024 calcula `p_ini` antes del segundo cierre con la categoría configurada para la especie 39 (`PESO_KG` por defecto), la prioridad de fuentes y el precio vigente más reciente para el día del cierre. El precio registrado durante la pausa usa la misma categoría y fuente, con fecha posterior; el resultado conserva ambos precios, la regla aplicada y cualquier congelado visible en pausa. El veredicto compara el congelado final y el cálculo del activo 943 con `p_ini`.

El spec Cypress captura tramos del contenedor desplazable de la vista de cierre y guarda controles saneados con texto, `aria-label`, `title`, rol, tipo y estados. El acta y el informe citan los controles observados al decidir 026 y 027. Los ensayos locales incluyen categorías distintas, recongelado, vista en pausa con y sin autorización y controles nombrados por texto o `aria-label`. No se generó un RUN en esta preparación; Cypress real mediante `pruebas/verificar.mjs` queda a cargo del responsable QA.

La orden `ORD-G43-015` abarca los cuatro casos `024` a `027`. `026` se comprueba con RF-87 v1.2 (RFC-026 C26.3); la fila de la matriz sigue desactualizada para ese caso. La ejecución V2 del ejecutor canónico `g43.mjs` usa el período 8 para 024/027, el 266 para 025 y el período siguiente creado por el cierre del 266 para 026. La ruta V1 y todas sus pruebas locales se conservan para contrastar el historial, sin modificar el RUN V1.

`--operacion reevaluar --version 2` requiere `version_anterior=1` y `alcance_reevaluacion.casos` con los cuatro casos en el contexto. `--operacion reintentar --version 2` exige el mismo alcance. La preparación no crea un RUN ni consulta TEST.

Antes de cualquier escritura, la ruta V2 lee ambos períodos, sus últimos cierres, prevalidaciones y líneas base, los activos 943/944/1643/1644 y los precios de las especies 39/544. Si el período 8 no está ABIERTO o EN_CIERRE con cierre 67 en paso 3, o si el 266 no tiene el activo 1644 sin precio, conserva el diagnóstico y queda NO_CONCLUYENTE. Dentro del RUN cancela primero el cierre 67, comprueba la rama «No», registra el precio de 39 durante la segunda pausa y verifica la rama «Sí». Luego comprueba «No» y «Sí» en 266 y la estimación del 1644 en el período siguiente. Cada cierre registra los avisos nuevos de la bandeja; el informe advierte que esos avisos y alertas NIC 41 pueden persistir fuera del rollback. El DELETE se verifica con lecturas sin cabeceras del RUN.

La prueba local V2 se ejecuta con `node pruebas/g43_v2_escenarios.test.mjs` y usa solo un servidor de loopback. `node pruebas/g43_v2_local.test.mjs` comprueba el alcance, rutas y títulos. `node pruebas/verificar.mjs` intenta el humo real de Cypress y deja un ejemplo sintético en `%TEMP%/g43-verificar-ejemplo` si se permiten procesos hijos; en este sandbox los procesos hijos pueden fallar con `spawn EPERM`.

El RUN `041055` consumió 187 solicitudes API y superó el límite anterior de 180. La ronda 9 fija 230: 187 observadas + 2 lecturas nuevas de auditoría/período para 026 + 41 de margen para paginación y variación de datos. El fixture conforme local consume 103 solicitudes, incluidas lecturas Newman simuladas; ese conteo no sustituye el observado en TEST. Cypress conserva presupuesto separado de 120 solicitudes, máximo 40 por panel. Una prueba local no confirma el resultado del producto en TEST.

## ORD-G43-028: preparación local, ronda 9

La UI guarda una segunda captura `G43-UI-<panel>-pagina-completa.png` y un `resumen_dom` saneado en cada acta: encabezados, tarjetas de cierre/precondiciones, tablas, listas y controles con nombre, etiqueta y estado. La búsqueda de 026 y 027 recorre toda la vista de cierre y exige la fila o lista del activo/asiento y la opción o autorización pertinente. Si en pausa solo aparece «Cancelar el cierre», el acta lo deja explícito y la UI se rechaza por evidencia visible. El simulador local incluye la tarjeta de pausa con lista y controles debajo, y la variante sin decisión.

Para 026, el resultado conserva los cálculos del 1644, eventos de auditoría del período/activo, avisos nuevos, precio congelado y respuesta del cierre. Una vía solo acredita estimación cuando marca el 1644 y enlaza con el último precio 492; `activos_procesados` sin marca no basta. Si hay `MEDICION_SIN_VARIACION` sin marca de estimación, 026 falla ese criterio y el informe consulta a la líder de requisito sobre variación cero. En 024, la referencia inicial sale del congelado visible durante el segundo intento; si no se expone, se usa el congelado del primer intento porque no se registra precio entre ambos. Si tampoco se expone, se usa el precio vigente calculado antes del segundo intento. El criterio sigue exigiendo que el precio congelado final no sea el registrado durante la pausa.

Se consultaron por lectura `src/financial_valuation/application/services/medidor.py:108-197`, `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:336-380` y `src/financial_valuation/infrastructure/routers/m06_router.py:663-676`. No se creó RUN ni se consultó TEST en esta preparación.

Rutas de código consultadas por lectura de `origin/test`: `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py`, `src/financial_valuation/infrastructure/routers/m06_router.py`, `src/financial_valuation/infrastructure/repositories/periodo_repository.py`, `src/financial_valuation/infrastructure/repositories/valoracion_repository.py`, `src/financial_valuation/application/services/medidor.py`; en el frontal `src/financial_valuation/pages/CierreView.tsx`. También se leyeron la matriz M06, RF-87 v1.2, el informe V1 de G43, el análisis V2 de la orquestación y las referencias acotadas de G42.

La cobertura conserva los oráculos de `TC-M06-024` a `TC-M06-027`, la matriz, la expiración, las ramas 409/500 y la comparación de cierre 8 con el paso 3 observadas en G43. La colección `G43.postman_collection.json`, `g43.cy.js`, `g43.cypress.config.cjs` y `g43.mjs` son las entradas vigentes. Los RUN anteriores permanecen históricos y no forman parte de esta preparación.

## Verificación local única

```powershell
node pruebas/verificar.mjs
```

El procedimiento usa `os.tmpdir()`, ejecuta ocho pasos en orden, bloquea intentos de red externa en los procesos Node que controla y comunica clasificación por paso. En el sandbox de Codex, `spawn EPERM` impide Cypress real, los lanzadores en proceso hijo y Pydantic desde el procedimiento; el responsable QA debe ejecutarlo en un entorno que permita procesos hijos. No requiere acceso a TEST. La validación local en proceso de CLI, escenarios y forma de resultado sí se ejecuta aquí.

## Infraestructura copiable

Cada archivo deduce el grupo por la carpeta `TC-M06-Gnn` o recibe capacidades y datos específicos. La copia a otro grupo debe incluir sus propios archivos de escenario y contrato, sin importar G43 en tiempo de ejecución.

| Archivo | Origen o función | SHA-256 |
|---|---|---|
| `lib/infra.mjs` | `g43.mjs` de ORD-G43-008; forma del `resultado.json` oficial de G40 | `9880c8b7c192560bed6875fa33a50bb2cd12d3bd411816f762413978c400d416` |
| `lib/contrato.mjs` | módulo de contrato existente en G43, sin nombre de grupo fijo | `bfd07b9e5de3c12ac466c9fe0ff4a4f82afa7c91ffd0d190cb6e529a0b750fff` |
| `lib/informe.mjs` | plantilla extraída del ejecutor G43 | `8ef197d199db2b963860b6c88dd73f3a7340b26c0dc1947e75a506b70bc7866f` |
| `pruebas/newman_hijo.mjs` | `TC-M06-G42/pruebas/newman_hijo.mjs` | `38ecb80490ff6e8fe05bd86896e01c835f850313c04fca0c91c734d4a7b08455` |
| `pruebas/cypress_hijo.mjs` | `TC-M06-G40/pruebas/cypress_hijo.mjs` | `0ba473fe11ddaed69a9611603af66752447ee368960e97e32d3f7c9692b440f6` |
| `pruebas/simulador_base.mjs` | nuevo simulador local parametrizado | `0e969b5fb75e8c6a6f89251b45e6f6ce61dae6c4b6317acd3edbd635760c3da3` |
| `pruebas/verificar.mjs` | nuevo procedimiento local único | `e57b8217888b21ad5200029c0becba49f132ceed3a7342a5e5926e698c439a1e` |

`g43.cy.js` adapta la base de `TC-M06-G40/g40.cy.js` (validación de entorno, `LOCAL_SMOKE`, sonda, login local, intercepción, acta y captura difuminada). `g43.cypress.config.cjs` adapta la configuración de G40. `pruebas/escenarios_g43.json` contiene únicamente las expectativas de los paneles usadas por el simulador local. Los datos de caso y veredictos siguen en `g43.mjs` y `lib/g43_core.mjs`.

## Forma del resultado

El ejecutor conserva los campos anteriores y agrega `cierre.run.cierre_http`, `cierre.rollback.verificado`, `cypress.total_pruebas`, `comprobaciones`, `consume_version`, `clasificacion_fallo` y `sha256`. `lib/infra.mjs` contiene la validación de forma y la clasificación local. El informe oficial se genera una sola vez dentro del RUN correspondiente, junto con `resultado.json` y los artefactos reales. La fase de preparación no crea RUN ni informe.

Las rutas de código de producto consultadas en órdenes anteriores figuran en el historial de G43. La revisión de ORD-G43-018 y sus citas están documentadas a continuación.

## ORD-G43-018: auditoría local de tipos y recuperación V2

La corrección de `nivel_fallo` aplica a las dos respuestas que lo incluyen: `GET /finanzas/periodos/{id}/prevalidacion` y `POST /finanzas/periodos/{id}/cierre`. El valor es `integer|null`: `src/financial_valuation/domain/services/trazabilidad.py:13,25-31` produce niveles 1 a 4 o `None`; `src/financial_valuation/application/use_cases/trazabilidad/verificar_trazabilidad_use_case.py:41-51,54-82,96` los incorpora a prevalidación y cierre. No se observó conversión a texto en estas rutas.

La comprobación de los demás tipos del contrato se hizo por grupos de campos. Cada entrada de `pruebas/contrato_g43.json` identifica los campos y la fuente; estas son las líneas de `origin/test` consultadas en esta ronda para los tipos de sus respuestas:

| Campos del contrato | Origen de tipos en backend |
|---|---|
| `token`, permisos (`nombre_recurso`, `id_accion`) | `src/identity_access/infrastructure/routers/sesiones_routers.py:91-140,215-235` y DTO de sesión citado en el contrato |
| Períodos (`id_periodo_contable`, `numero_id_tributaria`, `tipo_cierre`, `fecha_inicio`, `fecha_fin`, `estado`, `fecha_cierre`, `ultimo_cierre.*`) | `src/financial_valuation/domain/entities/contabilidad.py:16-23`; `src/financial_valuation/infrastructure/repositories/periodo_repository.py:20-21,142-148`; `src/financial_valuation/infrastructure/routers/m06_router.py:433-439` |
| Activos (`id_activo_biologico`, `id_especie`, `id_finca`, `estado`, `valorado_por_costo`, `depreciacion_acumulada`, `valoracion_costo.*`) | `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:287-299`; `src/financial_valuation/infrastructure/adapters/activo_financiero_m02_adapter.py:25-31`; `src/financial_valuation/infrastructure/routers/m06_router.py:222-235` |
| Configuración (`general.pct_umbral_desviacion_precio`, `especies.*`, `matriz.*`) y alta de matriz | `src/financial_valuation/domain/entities/contabilidad.py:33-39`; `src/financial_valuation/infrastructure/routers/m06_router.py:110-115,146-152`; `src/financial_valuation/infrastructure/dto/m06_dto.py:59-65` |
| Precios (`id_precio_mercado`, `id_especie`, `categoria`, `id_metrica_produccion`, `precio_unitario`, `fuente`, fechas, `unidad_medida`, `evidencia`, `estado`) y alta | `src/financial_valuation/domain/services/precios.py:23-35`; `src/financial_valuation/application/use_cases/precios/listar_precios_use_case.py:22-34`; `src/financial_valuation/infrastructure/routers/m06_router.py:168-180`; `src/financial_valuation/infrastructure/dto/m06_dto.py:74-83` |
| Líneas, cálculos, mediciones y variaciones (`id_*`, valores, cuentas, fechas, estados, `tipo_evidencia`) | `src/financial_valuation/domain/entities/contabilidad.py:71-97`; `src/financial_valuation/infrastructure/repositories/asiento_repository.py:19-21`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:321-327,372-387`; `src/financial_valuation/infrastructure/routers/m06_router.py:280-295,305-310,369-374` |
| Prevalidación (`bloqueos.*`, `activos_sin_precio.*`, `lineas_sin_trazabilidad.*`, `puede_cerrar`, `requiere_autorizacion`) | `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:77-87,114-154`; `src/financial_valuation/application/use_cases/trazabilidad/verificar_trazabilidad_use_case.py:41-51`; `src/financial_valuation/infrastructure/routers/m06_router.py:442-449` |
| Cierre, cancelación, comprobantes y reportes (`id_cierre`, estado, excluidos, hash, período siguiente, códigos, lineas, reportes) | `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:318-330,407-443`; `src/financial_valuation/infrastructure/repositories/periodo_repository.py:122-140`; `src/financial_valuation/infrastructure/routers/m06_router.py:452-482` |
| Revelaciones (`id_informe`, `version_informe`, `contenido.parr_54_56_activos_al_costo.*`) | `src/financial_valuation/infrastructure/repositories/reporte_repository.py:161-176,190-195`; `src/financial_valuation/application/services/reportes.py:121-126`; `src/financial_valuation/infrastructure/routers/m06_router.py:623-635` |
| Auditoría (`eventos.*`, `payload_evento.*`, `total_registros`), notificaciones (`items.*`, `total`) y DELETE del RUN | `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:68-76`; `src/financial_valuation/infrastructure/routers/m06_router.py:663-678`; `src/identity_access/infrastructure/routers/notificaciones_routers.py:30-57`; `src/shared/rollback/presentation/test_control_router.py:31-39` |

El RUN `RUN-G43-V2-20261113-025305` quedó sin resultado porque la validación era perezosa. El Proxy de la prevalidación conservaba el valor que contrariaba el contrato; al serializar `r` volvía a lanzar `TIPO_INVALIDO...nivel_fallo`. `guardarResultado` construía el informe antes de escribir `resultado.json`, así que esa excepción impedía ambos archivos. El registro disponible no permite concluir que el DELETE no se enviara: su constancia habría quedado en el resultado que faltó. V2 ahora valida la respuesta completa al recibirla y guarda un diagnóstico de emergencia si falla el `finally` o el informe. Los casos sin veredicto quedan `NO_CONCLUYENTE`; el rollback se declara `NO_VERIFICADO` si no se completan sus lecturas.

Las pruebas locales V2 cubren `nivel_fallo` entero y nulo, fallo de contrato antes de escribir, fallo en `finally` y fallo del informe. El ejemplo A4 se regeneró en `%TEMP%/g43-verificar-ejemplo`. El despacho de la ronda 3 requiere aprobación expresa del responsable QA.

## ORD-G43-021: preparación local, ronda 4

El RUN V2 `RUN-G43-V2-20261113-031156` quedó NO OFICIAL por el tipo de `precios_congelados[].id_especie` y por la selección de los períodos 8 y 266 en Cypress. Esta ronda conserva los oráculos de 024–027. El contrato admite entero o `[entero, booleano]` en ese campo y el caso 024 extrae el primer elemento para localizar la especie; sigue comparando `id_precio_mercado` y `fecha_vigencia` con el precio capturado al inicio. Cuando aparece la lista, `resultado.json` y el informe V2 generados registran una observación sobre esa forma anómala, sin veredicto ni incidencia. Lecturas de sustento: `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:339,431` y `src/financial_valuation/infrastructure/repositories/periodo_repository.py:115,145`.

El spec espera `GET /finanzas/periodos`, guarda en el acta solo identificador, estado y fechas de cada período, además de value y texto de las opciones visibles. Si el período no llega en la API, deja el caso NO_CONCLUYENTE con el motivo exacto. Si llega en la API pero falta en el selector, recarga el proveedor una vez antes de cerrar el diagnóstico. Esta selección deriva de `src/financial_valuation/components/comunes.tsx:123-185` y `src/financial_valuation/api/finanzasApi.ts:100` del frontal. La causa de la ausencia de los períodos en el frontal de TEST sigue sin determinarse.

Las pruebas locales V2 incluyen un congelado `[39, false]`, un tipo inválido y la conservación del motivo de API frente a otro error de Cypress. El humo Cypress local usa un selector con opciones retrasadas y comprueba también el caso de período ausente. `node pruebas/g43_v2_local.test.mjs` y `node pruebas/g43_v2_escenarios.test.mjs` pasan; `node pruebas/verificar.mjs` confirma escenarios, forma y red bloqueada, pero `spawn EPERM` impide sus pasos que lanzan procesos hijos, incluido Cypress real. El ejemplo A4 se regeneró en `%TEMP%/g43-verificar-ejemplo`. No se creó RUN ni se consultó TEST. El despacho de esta ronda requiere aprobación expresa del responsable QA.

## ORD-G43-023: diagnóstico del humo Cypress

El alias `@periodos` se registra en `beforeEach` antes de `cy.visit`, por lo que la primera petición queda interceptada. El cambio previo comprobaba las opciones una sola vez y luego recargaba y esperaba otra petición del proveedor. En `comunes.tsx`, el proveedor carga períodos en un efecto al montarse; esa segunda petición no es una condición garantizada. El simulador demora 250 ms la aparición de opciones, por lo que la lectura inmediata podía provocar la recarga. Además, para el panel 027 el período 8 es la primera opción del simulador: seleccionar de nuevo el valor inicial puede no emitir `change`, dejando sin petición de prevalidación. Estos mecanismos explican el fallo observado, aunque el error exacto del ensayo de QA quedó truncado y la confirmación con Cypress real sigue pendiente.

El spec espera de forma reintentable la opción usando la primera respuesta API y, en `LOCAL_SMOKE`, emite `change` si el período ya estaba seleccionado. `node pruebas/g43_seleccion_periodo.test.mjs` cubre cinco secuencias derivadas de los períodos del escenario local. `verificar.mjs` muestra el motivo y bloqueo del acta, el primer error de Cypress y línea del spec, así como las opciones y respuestas completas. Ante fallo conserva el temporal e imprime su ruta; `QA_VERIFICAR_CONSERVAR=NO` permite retirarlo. El ejemplo A4 se regeneró en `%TEMP%/g43-verificar-ejemplo`. El responsable QA debe ejecutar `node pruebas/verificar.mjs` en Windows antes de despachar esta ronda.

## ORD-G43-024: preparación local, ronda 6

El preflight pasa a cada panel el `numero_id_tributaria` del período objetivo como parámetro interno. Cypress elige primero el control con etiqueta visible «Titular», espera el GET filtrado de `/finanzas/periodos` y después elige «Período contable» por id o por mes y año de `fecha_inicio`. Comprueba el título del panel antes de verificar la prevalidación. El acta conserva alias NIT-A/NIT-G, indicador de selección, queries con alias, razones sociales sin NIT, opciones y respuestas de períodos. La salida de Cypress se sanea antes de escribir el log. El simulador local reproduce el titular por defecto distinto, el filtro y las secciones visibles descritas para TEST; permite ensayar un `value` no numérico.

Pasaron `node pruebas/g43_v2_local.test.mjs`, `node pruebas/g43_v2_escenarios.test.mjs`, `node pruebas/g43_seleccion_periodo.test.mjs` y `node --check` de los archivos modificados. El ejemplo A4 se regeneró en `%TEMP%/g43-verificar-ejemplo`. Queda pendiente `node pruebas/verificar.mjs` con Cypress real en Windows, a cargo del responsable QA; si `spawn EPERM` impide procesos hijos, el resultado de ese humo no es concluyente. No se creó RUN ni se consultó TEST. El despacho de la ronda 6 requiere aprobación expresa del responsable QA.
