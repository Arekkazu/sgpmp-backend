# TC-M06-G41 — RF-87 v1.1

Automatización API de TC-M06-019 y TC-M06-020. Oráculo original: fila `TC-M06-G41` de `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv`, CA-1, CA-7, CA-9, CA-11, proceso 1–9, salida y actualización v1.1. La orden `ORD-G41-001` fija las decisiones D1–D4. La existencia de un cálculo previo no sustituye el valor inicial requerido por TC-M06-020.

## Archivos activos

- `g41.mjs`: ejecutor canónico. `--capacidades` y `--comprobar` son locales.
- `lib/g41_core.mjs`: oráculos y decimal exacto con `BigInt`.
- `G41.postman_collection.json`: cuatro lecturas finales Newman, sin UI.
- `pruebas/newman_hijo.mjs`: proceso Newman con reportes saneados.
- `pruebas/registro_qa.mjs`: validación estructural para el registro QA externo.
- `pruebas/g41_local.test.mjs`: pruebas locales sin TEST.
- `pruebas/g41_dto.test.py`: validación local con los DTO Pydantic reales del backend.
- `pruebas/contrato_g41.json`: contrato de rutas, cuerpos y respuestas con citas del backend.
- `preparacion_ORD-G41-009.md`: informe local de preparación; no es informe de RUN.

G41 estaba vacío antes de esta orden. Se consultaron en solo lectura G40 (`g40.mjs`, `lib/g40_core.mjs`, colección y pruebas), G39 (baja y contrato) y G37 (colección de reportes). No hay duplicados ni legado G41.

## Operación

### Permisos del flujo (ORD-G41-005)

Acciones M06: C=1, R=2, E=5 (`src/financial_valuation/infrastructure/routers/m06_router.py:8-10,48`). El preflight exige solo las dependencias de las rutas utilizadas:

| Actor | Recurso:acción | Declaración de ruta |
| --- | --- | --- |
| Contador | `cierre_periodo:2`, `cierre_periodo:5` | `m06_router.py:295,302-303,312-313` |
| Contador | `configuracion_contable:2`, `configuracion_contable:1` | `m06_router.py:79,115-116` |
| Contador | `precios_mercado:2`, `precios_mercado:1` | `m06_router.py:137,143` |
| Contador | `valoracion_activos:2`, `valoracion_activos:5` | `m06_router.py:190,196,219,225,234-249` |
| Contador | `estado_resultados:2` | `m06_router.py:423-424,429` |
| Contador | `revelaciones_nic41:2` | `m06_router.py:458-459,464` |
| Contador | `auditoria_financiera:2` | `m06_router.py:498` |
| Administrador | `activos_biologicos:2`, `activos_biologicos:1`, `activos_biologicos:5` | `src/biological_assets/infrastructure/routers/activo_biologico_router.py:219,1132-1135,1223-1227,1343-1347` |

La bandeja `/notificaciones` exige autenticación y no permiso de recurso (`tests/Test_Testing/Test_Modulo6/RF-86/TC-M06-G40/pruebas/contrato_g40.json:468-486`). Los faltantes se guardan por actor en `permisos_faltantes`, como pares `recurso:acción`. Si el flujo no envió escrituras, el DELETE 200 y las lecturas válidas de períodos y activos acreditan `SIN_ESCRITURAS`. La protección de rutas detiene localmente cualquier `undefined` o `null` antes de la petición. Las pruebas locales usan loopback y reportes Newman temporales; no son evidencia de TEST.

El lanzador externo crea `contexto_operacion.json` dentro de `Resultados/RUN-G41-V1-.../` o `EvaluacionV2/Resultados/RUN-G41-V2-.../`, aporta autorización particular y ejecuta el CLI. El ejecutor escribe `preflight.json` antes de cualquier petición. No se debe invocar aquí para TEST en fase preparar. `QA_AUTORIZADO=SI` y el host exacto son barreras; los dos cierres producen dos avisos persistentes para cinco Contadores fuera del sandbox. El registro de los dos precios vigentes también emite dos alertas persistentes para esos Contadores (`registrar_precio_use_case.py:84-95`). Diciembre se cierra anticipadamente por D2. Estos efectos externos deben constar en la solicitud del RUN.

El informe oficial se genera solo dentro del RUN, junto a `resultado.json` y Newman JSON/HTML reales. El `DELETE /test-control/runs/{id}` va seguido de lecturas de período, activos, matriz, precios y mediciones. Un `DELETE 200` aislado no acredita rollback. No hay Cypress porque los casos son solo API.

## Equivalencias de TC-M06-019(c)

| RF-87 | API pública |
| --- | --- |
| `valor_razonable_inicio` | `mediciones[].valor_razonable_anterior` |
| `valor_razonable_cierre` | `mediciones[].valor_razonable_actual` |
| `variacion_total` | `mediciones[].variacion_total` |
| `variacion_transformacion_biologica` | `mediciones[].ganancia_perdida_transformacion` |
| `variacion_precio_mercado` | `mediciones[].ganancia_perdida_precio_mercado` |
| `metodo_valoracion` | `activos[].valorado_por_costo` (`false` = valor razonable, `true` = costo) |

Fuentes de código consultadas: `src/financial_valuation/infrastructure/routers/m06_router.py:190-252,295-330,423-508`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:246-340`; `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:54-65,93-153,187-301,342-357`; `src/financial_valuation/application/services/medidor.py:7-9,62-114`; `src/financial_valuation/application/use_cases/precios/registrar_precio_use_case.py:59-95,104-116`; `src/financial_valuation/infrastructure/adapters/notificacion_financiera_m01_adapter.py:33-57`; `src/financial_valuation/domain/entities/contabilidad.py:16-30`; `src/financial_valuation/infrastructure/dto/m06_dto.py:64-77,132-134`; `src/biological_assets/infrastructure/routers/activo_biologico_router.py:1133-1170,1223-1261,1343-1370`; DTO de cambio de estado y baja en `src/biological_assets/infrastructure/dto/`.

## Riesgo funcional candidato

`medidor.py` usa el último cálculo para `valor_razonable_anterior`; TC-M06-020 pide el valor inicial RF-82 o el cierre anterior. Esta discrepancia se clasifica `DEFECTO_FUNCIONAL_CANDIDATO` hasta comprobarla por API pública en un RUN autorizado. No es veredicto local.

## Ajustes ORD-G41-002

Para el primer cierre, el ejecutor toma del historial leído antes del cierre las mediciones posteriores al reconocimiento CONFIRMADO, ordenadas por fecha e identificador. Sin mediciones intermedias (rama a), exige `valor_razonable_anterior` del cierre igual al inicio RF-82. Con ellas (rama b), exige que la primera parta de RF-82 y que inicio RF-82 + variaciones intermedias + variación del cierre iguale el valor actual del cierre. En ambas ramas verifica además variación del cierre = actual − anterior y transformación + precio = variación. `resultado.json` y el informe enumeran la rama y los ids por activo. En diciembre se conserva el valor actual del cierre de noviembre como inicio esperado.

Los dos precios nuevos usan `general.pct_umbral_desviacion_precio` leído de `/finanzas/configuracion`: el primero busca la mitad del umbral y el segundo una cuarta parte, con dos decimales. Si el cambio mínimo de 0,01 alcanza o supera el umbral, el POST envía `confirmar_desviacion=true`; cada decisión queda registrada en `resultado.json` y el informe. Las pruebas locales incluyen la rama b con Newman en loopback y el umbral bajo. Son ensayos locales, no evidencia de TEST.

## Ajustes ORD-G41-008: orden de respuestas

- `g41.mjs:99-100`: activos 1569-1573 seleccionados por `id_activo_biologico`; especie de 1569, igualdad con 1570 y 1571, y costo de 1572 y 1573. Falta de un id: `ACTIVO_FALTANTE_<id>`. La consulta global puede incluir activos de otras fincas.
- `g41.mjs:100`: precio vigente por fuente, `fecha_vigencia` e `id_precio_mercado`, sin tomar el primer elemento de la lista.
- `g41.mjs:76`: HTTP del cierre por id de período, sin tomar el último elemento de la lista de cierres local.
- `lib/g41_core.mjs:24`: primera medición previa por fecha e id de medición, sin tomar la primera posición recibida.
- `g41.mjs:50,94`: los dos logins constan en `solicitudes[]` con método, ruta y HTTP o timeout, sin cuerpo ni credenciales; no se cuentan como escrituras del sandbox.

Las demás listas leídas de API usan `find`/`some` por id, origen, tipo o estado, `filter` por identidad de línea base, o recorren todos los elementos. `medicionesPrevias` se ordena explícitamente por fecha e id para la traza cronológica; no depende del orden del servidor. El fixture de `/finanzas/activos` ordena por `identificador`, presenta primero los equinos e incluye dos activos ajenos. `orden_api_distinto` invierte además períodos, mediciones, matriz, notificaciones, auditoría y precios; las listas vacías de variaciones, cálculos y líneas se conservan vacías. El ensayo integral con Newman en loopback obtuvo 019 y 020 APROBADO; los reportes temporales del ensayo no son evidencia de TEST.
