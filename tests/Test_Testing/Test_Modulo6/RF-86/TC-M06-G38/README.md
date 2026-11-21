# TC-M06-G38 — preparación local RF-86 v2.0

Ordenes `ORD-G38-001`, `ORD-G38-002` y `ORD-G38-003`, casos `TC-M06-014` y `TC-M06-015`. El oráculo procede de `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv:381`, CA-17, CA-18 y CA-22. D1: 4.600.000 y 600.000 son ejemplos; el valor exigido es el componente real de la medición, truncado. D2: `id_linea` es único e inmutable sin formato UUID obligatorio. Equivalencias: `nit_titular` = `numero_id_tributaria`; `indicador_estimacion` = `es_estimacion`.

## Inventario y origen

Un ejecutor (`g38.mjs`), un núcleo (`lib/g38_core.mjs`), una colección (`G38.postman_collection.json`), un contrato (`pruebas/contrato_g38.json`), un hijo Newman (`pruebas/newman_hijo.mjs`), registro QA y tres pruebas locales. No hay Cypress: los dos casos son solo API. G37 fue referencia de solo lectura; sus `g37.mjs`, contrato, colección, pruebas, README y RUN oficial fueron revisados. Los archivos G38 nacieron de copias de la estructura G37, con flujo propio. No se trasladó evidencia histórica ni se creó RUN durante esta preparación.

## Flujo y decisiones

| Paso | Decisión | Efecto |
| --- | --- | --- |
| Preflight | autorización, URL, herramientas, huellas, contexto | Sin petición cuando falla |
| Permisos | Contador y Admin antes de escribir | Sin escritura si falta permiso |
| Selección | bovino individual ACTIVO, período ABIERTO, titular, peso, precio MERCADO_ACTIVO, cálculo | Sin escritura si no hay candidato |
| Lecturas previas | configuración, variaciones, mediciones, líneas; contrato de todas las GET | Sin escritura ante discrepancia |
| Matriz | par TB/GANANCIA y PM/PERDIDA por especie, luego genérico | 014 BLOQUEADO si falta par; no cambia RF-109 |
| Rebase | solo si el cálculo previo usó otro precio | Evento, procesar y releer cálculo |
| 014 | precio MERCADO_ACTIVO con centavos a +/-5% y peso +1% a +5%, elegidos antes del POST | Dos variaciones y dos líneas del mismo bovino |
| 015 | comparte el evento 014 cuando la predicción da TB+ y PM- con TB discriminante | Compara valor de línea con TB de cuatro decimales, truncado distinto de redondeo |
| Sin combinación discriminante | búsqueda local agotada antes del POST | 014 y 015 NO_CONCLUYENTE técnico; cero escrituras |
| Estructura | todas las líneas del período y estabilidad de IDs | Cuentas distintas en líneas REGISTRADA nuevas; pendientes antiguas se informan |
| Newman | configuración, líneas y mediciones | Tres lecturas en serie, reportes saneados |
| Cierre | DELETE 200 y lecturas públicas poscierre | Oficial solo con rollback verificado y Newman conforme |

Presupuesto: 150 solicitudes y 1800 s. Las llamadas del ejecutor están protegidas con `PETICION_CONCURRENTE`; Newman corre por `process.execPath`. `leerEnv` consulta `.env.qa` solo con `QA_AUTORIZADO=SI`. El ensayo usa únicamente loopback y directorio temporal. El CLI real usa `Resultados/` únicamente con contexto y autorización suministrados por el lanzador externo.

## Contrato: campos nuevos

Las rutas reutilizadas de G37 conservan tipos y citas en `contrato_g38.json`. Los campos nuevos se validan por presencia y tipo sin rechazar campos adicionales legítimos. `Decimal` admite número JSON o cadena decimal, `date` cadena ISO y `None` nulo. **Evidencia real** significa respuesta observada en G37; `solo código` requiere contraste en el primer RUN G38. Las líneas G37 solo demostraron ID, origen, tabla, trazabilidad y evidencia; el resto del cuerpo nuevo aún carece de respuesta TEST saneada.

| Campo | Tipo | Cita de código | Evidencia |
| --- | --- | --- | --- |
| `configuracion.matriz[]` y `id_asignacion_cuenta_contable`, `tipo_hecho`, `sentido`, `id_especie`, `subtipo_costo`, `cuenta_debito`, `cuenta_credito` | array; number, string, string, number/null, string/null, string, string | `m06_router.py:79-85`; `configuracion_contable_repository.py:107-115` | Solo código; asignaciones genéricas comunicadas por QA para especie 39 |
| `configuracion.costos_venta[]`: `id_especie`, `region`, `es_activo`, `pct_transporte`, `pct_comisiones`, `pct_impuestos` | array; number, string, boolean, decimal/number/null | `m06_router.py:82-85`; `configuracion_contable_repository.py:80-87` | Solo código; entrada del predictor |
| `lineas[].id_linea_asiento_nic41` | number | `asiento_repository.py:17-19,77-87`; `m06_router.py:225-231` | G37: IDs 903, 904 |
| `tipo_hecho`, `sentido`, `estado` | string | `contabilidad.py:76-98`; `asiento_repository.py:17-19,77-87` | Solo código |
| `valor` | decimal/number | `contabilidad.py:78`; `asiento_repository.py:17-19,77-87` | Solo código |
| `fecha_hecho` | string | `contabilidad.py:79`; `m06_router.py:225-231` | Solo código |
| `id_periodo_contable`, `id_activo_biologico`, `id_especie`, `id_finca` | number | `contabilidad.py:80-83`; `asiento_repository.py:17-19` | Solo código |
| `numero_id_tributaria` | string/null | `contabilidad.py:84`; `asiento_repository.py:17-19` | Solo código; nulabilidad precautoria para líneas antiguas |
| `tabla_origen`, `id_origen`, `tipo_evidencia` | string, number, string | `contabilidad.py:85-87`; `asiento_repository.py:17-19` | G37: origen/tabla/evidencia en respuesta |
| `subtipo_costo` | string/null | `contabilidad.py:88`; `asiento_repository.py:17-19` | Solo código |
| `es_estimacion`, `es_reverso` | boolean | `contabilidad.py:89-90`; `asiento_repository.py:17-19` | Solo código |
| `tipo_hecho_corregido`, `id_linea_corregida` | string/null, number/null | `contabilidad.py:91-92`; `asiento_repository.py:17-19` | Solo código |
| `cuenta_debito`, `cuenta_credito`, `justificacion` | string/null | `contabilidad.py:93-95`; `asiento_repository.py:17-19` | Solo código |
| `id_usuario` | number/null | `contabilidad.py:96`; `asiento_repository.py:17-19` | Solo código |
| `estado_trazabilidad`, `id_comprobante_nic41` | string, number/null | `asiento_repository.py:77-87`; `m06_router.py:225-231` | G37 trazabilidad; comprobante solo código |
| `extra` | object | `contabilidad.py:99`; `asiento_repository.py:83-85`; `m06_router.py:230-231` | Solo código |

El predictor reproduce `nic41.py:38-40,72-116,129-151`: bruto y costos por componente con q4 HALF_UP, neto q4, preajustado q4, componentes q4. La fuente de los cuatro decimales es `GET /finanzas/periodos/{p}/mediciones` (`valoracion_repository.py:297-305`); la tabla de variaciones usa escala 2 y puede redondear. **Límite de evidencia:** el RUN oficial G37 conservó en `resultado.json` los importes persistidos de variación (272615.04 y -53805.60), pero no guardó magnitud, neto previo, parámetros ni componente q4 de la medición del paso 3. Por ello esa reproducción exacta no puede afirmarse con sus artefactos saneados. El primer RUN G38 debe conservar el predictor y el componente q4 observado para contrastarlo.

La matriz observada por QA para especie 39 usa TB/GANANCIA: 158405→424805 y PM/PERDIDA: 539505→158405. El ejecutor lee la matriz de nuevo antes de escribir y compara contra esa lectura; los códigos no están fijos en el oráculo.

## ORD-G38-002: cobertura local antes de RUN

El ensayo `pruebas/g38_ensayo.mjs` invoca `principal()` contra 127.0.0.1. Cada respuesta tarda al menos 55 ms; el servidor devuelve HTTP 500 si detecta peticiones simultáneas con el mismo `X-Test-Run-Id`. Cuenta el hijo Newman real. Todos los contextos, reportes y resultados simulados viven en un directorio temporal que se elimina al terminar: no son evidencia TEST. El CLI externo sigue pendiente si Windows devuelve `spawn EPERM`; la validación de contexto y preflight se ejerce directamente.

El catálogo usa los 16 identificadores de `TC-M06-G37/Resultados/RUN-G37-V1-20261108-233956/resultado.json`: cinco candidatos 943–947 de especie 39 y cinco especies consultadas. El mismo RUN fija los pares variación/línea 256/903 y 257/904 del paso 3. Los cuerpos que no se conservaron allí se simulan según `contrato_g38.json`; no se atribuyen a TEST. Matriz genérica: TB/GANANCIA 158405→424805 y PM/PERDIDA 539505→158405. D1 y D2 no cambian.

| Decisión probada por `principal()` | Escenario | 014 | 015 | Oficial local |
| --- | --- | --- | --- | --- |
| Selección sin apto y detalle HTTP 500 | `seleccion`, `seleccion_500` | NO_CONCLUYENTE | NO_CONCLUYENTE | no |
| Permisos | `permisos` | NO_CONCLUYENTE | NO_CONCLUYENTE | no |
| Lecturas previas | `lecturas_previas` | NO_CONCLUYENTE | NO_CONCLUYENTE | no |
| Matriz sin par | `matriz_sin_par` | BLOQUEADO | NO_CONCLUYENTE | no |
| Rebase | `rebase` | APROBADO | APROBADO | sí |
| Precio | `precio` | NO_CONCLUYENTE | NO_CONCLUYENTE | no |
| Pesaje HTTP 400 de fecha | `pesaje` | NO_CONCLUYENTE | NO_CONCLUYENTE | no |
| Procesar | `procesar` | NO_CONCLUYENTE | NO_CONCLUYENTE | no |
| Lecturas posteriores | `lecturas_posteriores` | NO_CONCLUYENTE | NO_CONCLUYENTE | no |
| Línea faltante | `linea_faltante` | RECHAZADO | APROBADO | sí |
| PENDIENTE_CUENTA | `pendiente_cuenta` | RECHAZADO | RECHAZADO | sí |
| Cuentas iguales | `cuentas_iguales` | RECHAZADO | RECHAZADO | sí |
| Valor redondeado | `pm_redondeada` | RECHAZADO | RECHAZADO | sí |
| Componente observado sin discriminación pese a la predicción | `componente_no_discriminante` | APROBADO | NO_CONCLUYENTE | no |
| ID duplicado o cambiado | `id_duplicado`, `id_cambiado` | APROBADO | RECHAZADO | sí |
| Cierre HTTP 500 | `cierre` | APROBADO | APROBADO | no |
| Newman HTTP 500 | `newman` | APROBADO | APROBADO | no |

Son resultados de **mocks locales**, no veredictos de producto. `conforme_sin_newman` registra 37 peticiones, cero Newman y cero solapamientos; `conforme` registra 37+3=40 y DELETE 200. Con rebase se observaron 47 peticiones. El contador incluye logins, Newman y DELETE; `resultado.solicitudes` enumera las peticiones de negocio del ejecutor.

### ORD-G38-003: predictor con datos reales de TEST

`pruebas/predictor_datos_reales.json` contiene exactamente el objeto `datos` aportado por la orden: parametro M09 6, diez calculos (15, 16, 21-28) y cinco mediciones (6-10). La prueba `predictor_datos_reales` reproduce en cuatro decimales bruto, transporte, comisiones, impuestos, neto, TB y PM. Para EVENTO usa la descomposicion de `nic41.py`; para CIERRE_PERIODO sin evento asigna todo el cambio a PM y TB cero. El ejemplo 943 / calculo 26 con precio 9612.37 y peso 351.37 da TB 57556.9491 y PM 101301.5910.

Con los precios enteros 9300 y 9600, pesos de dos decimales y costos de 2%, 3% y 1%, el neto es 0,94 x bruto y TB/PM tienen como maximo dos decimales. Asi 015 no distingue truncado de redondeo. El predictor busca localmente un precio MERCADO_ACTIVO con centavos dentro de +/-5% del vigente y un peso entre +1% y +5%. Solo elige una pareja con TB positiva, PM negativa y tercer decimal de TB entre 5 y 9. Se registra el precio con `confirmar_desviacion: true`. La variacion persistida en dos decimales es informativa; el oraculo compara la linea con la TB de cuatro decimales de la medicion. Si ninguna pareja sirve, termina como NO_CONCLUYENTE tecnico antes de escribir. Un solo evento cubre 014 y 015; no se requiere segundo bovino ni segundo pesaje, y se mantiene el presupuesto de 150 solicitudes.

La fuente fue un SELECT de solo lectura aportado por QA; esta preparacion no consulto TEST ni produjo RUN. Los ensayos usan loopback y directorios temporales, que no son evidencia de producto.

Si el calculo previo uso otro precio, el preflight predice primero el neto del rebase y busca la combinacion antes de escribir. Despues del rebase repite la busqueda con el calculo observado; una discrepancia deja ambos casos NO_CONCLUYENTE sin registrar el precio ni el pesaje del evento principal.

## Uso local

`node pruebas/g38_env.test.mjs`, `node pruebas/g38_decisiones.test.mjs`, `node pruebas/g38_ensayo.mjs`, `node g38.mjs --capacidades`, `node g38.mjs --comprobar`. `node --test` puede fallar con `spawn EPERM` en este Windows; la ejecución directa de `node` informa las aserciones. No ejecutar el flujo TEST desde esta preparación.
