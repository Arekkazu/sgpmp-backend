# Preparación V2 — ORD-G37-026 (2026-11-12)

**Alcance vigente:** REEVALUAR V2 de TC-M06-011 y TC-M06-013. TC-M06-012 fue APROBADO en V1 (RUN-G37-V1-20261108-233956) y queda fuera de las comprobaciones, la colección y el registro V2. Las secciones históricas de V1 más abajo documentan la preparación anterior. Un único informe se genera dentro de EvaluacionV2/Resultados/RUN-G37-V2-<timestamp>/TC-M06-G37_reevaluacion_V2.md solo durante un RUN autorizado; esta preparación no crea RUN ni consulta TEST.

La matriz original consultada fue Casos_Prueba(Modulo6Agrup).csv:380 en Windows-1252. RF-86 se consultó en Especificacion-Requerimientos-Modulo6.md:1222+. La V1 se leyó dentro de su RUN. El oráculo 011 compara el GET de acumulado del período 241 antes y después de las variaciones, por componente, total de ingresos y gastos, y otro período ABIERTO sin cambios. El 013 exige VERIFICACION_PENDIENTE inicial, POST RF-91 HTTP 200, VERIFICADO final y cadena con el evento M02 y la lectura M03. El POST RF-93 versionado no participa.

**Precondiciones preparadas:** el responsable QA autorizó vincular por SQL el dispositivo 856 al bovino 1831 y crear la lectura 120035 (2026-11-12 07:06:25 UTC) con apto_para_nic41=true; telemetria_calidad figura INDETERMINADA. No existe API para vincular el dispositivo. Se aceptó TEMP_CORPORAL como desviación del pesaje IoT de la matriz porque el producto no ofrece variable de peso. El ejecutor consulta el detalle del activo, el período ABIERTO actual, el historial M03 y la ventana de 24 h; la aptitud se acredita por GET cadena. Son precondiciones persistentes fuera del rollback.

**Código consultado realmente en origin/test mediante git show (solo lectura):** src/financial_valuation/infrastructure/routers/m06_router.py:587-591 expone el acumulado con permiso estado_resultados:R; application/use_cases/reportes/generar_estado_resultados_use_case.py:38-46 admite período ABIERTO; application/services/reportes.py:31-43 arma componentes y totales; domain/services/consolidacion.py:69-79 mapea tipo y sentido; application/use_cases/valoracion/procesar_eventos_m02_use_case.py:193 usa IOT_DIRECTO cuando el activo tiene dispositivo; infrastructure/repositories/trazabilidad_repository.py:38-93,127-138 relaciona evento, dispositivo y lectura en ventana de 24 h; application/use_cases/trazabilidad/verificar_trazabilidad_use_case.py:108-119 devuelve verificadas y pendientes. Las rutas abreviadas parten de src/financial_valuation/. No se verificó el despliegue ni se consultó TEST.

**Oficialidad:** resultado.json registra exactamente 011 y 013, seguimiento de INC-M06-G37-01 e INC-M06-G32-01, montos, cuatro acumulados y cadena completa. El informe declara las condiciones de oficialidad fallidas. El presupuesto de 150 cuenta solicitudes del ejecutor y Newman; logins fuera del RUN y DELETE/lecturas poscierre se consignan aparte. El ensayo conforme local consumió 52/150 solicitudes y validó el registro con pruebas/registro_qa.mjs; el conteo real deberá comprobarse en TEST. DELETE y lecturas sin cabeceras del RUN comprueban ausencia de variaciones, líneas, precios, eventos y auditorías, estado y peso de activos y período 241 ABIERTO.

**Validación local:** node --check de módulos activos, node g37.mjs --comprobar, node pruebas/g37_env.test.mjs, node pruebas/g37_decisiones.test.mjs y node pruebas/g37_ensayo.mjs. El simulador cubre conforme con y sin campos adicionales, código V1, deltas incorrectos, otro período alterado, cadena sin lectura, dispositivo ausente, ventana vencida, período cerrado, REINTENTAR V2 y DELETE fallido. El proceso hijo para copiar el ejemplo completo a %TEMP%/g37-verificar-ejemplo devuelve spawn EPERM en el entorno de Codex; queda pendiente ejecutarlo donde se permitan subprocesos. Los escenarios simulan API local y no son evidencia de TEST.

---

# TC-M06-G37 — preparación local ORD-G37-007

## Corrección de arranque ORD-G37-007

El intento técnico `RUN-G37-V1-20261108-202328` permanece intacto. El lanzador entrega solo el entorno del proceso más `QA_AUTORIZADO=SI`; ahora `principal()` carga `.env.qa` con prioridad del proceso, ejecuta el preflight y escribe `preflight.json` antes de cualquier petición. Sin barreras superadas sale con código 2, sin `resultado.json` ni informe oficial. El preflight comprueba los SHA-256 fijos de la colección (`EAFC2DE6FA78D5927D460A27D1D1C5BDA5CBF5E245C8ECD65820CB0FBD4AB098`) y del contrato vigente (`7885D82FE4B9E4D8D0927BB925289F6231049D283C8799CD3BC9A38A17588EEA`). Los efectos externos declarados se cotejaron con `SIGAB_QA_ORQUESTACION/estado/SOL-G37-006.json` (solo lectura): avisos NIC41, auditoría de logins, posible bitácora M02, backlog M06 y alcance de DELETE.

### Ruta del lanzador vs ensayo

| Elemento | Lanzador real | Ensayo local `arranque_lanzador` |
|---|---|---|
| CWD y argumentos | Carpeta G37; `--autorizacion`, `--operacion`, `--version`, `--intento`, `--run-id`, `--contexto` | Misma carpeta lógica y misma lista de argumentos entregada a `principal()`; la CLI real se intenta aparte con `process.execPath` |
| Entorno | Proceso con `QA_AUTORIZADO=SI`; `.env.qa` de la raíz del repo | Proceso con solo `QA_AUTORIZADO=SI`; archivo temporal con base loopback y valores ficticios |
| Base y peticiones | Base TEST canónica; `fetch` real tras preflight | Base loopback; `fetcher` simulado, sin red externa |
| Archivos de salida | `preflight.json` y, si pasa, `resultado.json` e informe dentro del RUN | Mismos nombres y rutas en RUN temporal de G37; se eliminan al terminar |
| Cierre | DELETE y lecturas reales según el flujo | DELETE 200 simulado; `rollback.verificado=true` solo para datos del sandbox sin escrituras, sin evidencia de producto |

El ensayo recorre el arranque y llega a `cierre` con catálogo vacío simulado para cubrir la ruta de salida sin datos; los oráculos y el rollback real quedan para un RUN autorizado. El subproceso de la CLI y el hijo Newman quedan pendientes si Windows devuelve `spawn EPERM`.

Casos originales: TC-M06-011, 012 y 013; RF-86 con RF-93, RF-94 y RF-91. Fuente: `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv`, fila `TC-M06-G37`. La matriz original exige acumulado exacto por ingresos/gastos sin otro período; una auditoría por variación con registro, activo, tipo, monto y período; y verificación de la variación TB+ hasta M02 y M03. Los oráculos se conservan en `lib/g37_core.mjs`.

## Inventario previo

Al comenzar ORD-G37-001 la carpeta no tenía automatización. Al comenzar ORD-G37-002 se recibieron diez archivos: `g37.mjs` (ejecutor y diagnóstico), `G37.postman_collection.json` (colección única), `README.md`, `lib/g37_core.mjs`, `pruebas/contrato_g37.json`, `pruebas/g37_ensayo.mjs`, `pruebas/g37_env.test.mjs`, `pruebas/newman_hijo.mjs`, `pruebas/registro_qa.mjs` y `pruebas/resultado_g36_fixture.json`. Ninguno era inservible ni duplicado. Se completaron citas por campo y prueba de ausencia; se corrigieron la selección parcial, el signo de las pérdidas, el GET posterior de RF-93, la clasificación del HTTP 500 y la reserva del presupuesto. `G37.postman_collection.json` y el fixture se conservaron; el fixture se cotejó por estructura y metadatos contra el `resultado.json` oficial de G36, sin imprimir datos privados. El README heredado registraba como referencias opciones de G32 y G36 (`g32.mjs`, `lib/g32_core.mjs`, `G32.postman_collection.json`, `g36.mjs`, `pruebas/newman_hijo.mjs`, `pruebas/registro_qa.mjs`, README y un `resultado.json` oficial); en ORD-G37-002 se leyó el informe G32, el fixture y la estructura del `resultado.json` G36, además de los archivos G37 y las rutas fuente enumeradas abajo. No hay importaciones de esos grupos en G37. La matriz original pide API Postman/Newman; no corresponde un spec Cypress.

## Matriz de contrato resumida

La matriz campo a campo, tipos, actor, permiso, router, constructor de respuesta y cita por cada campo usado está en `pruebas/contrato_g37.json` (`fuentes_campos`). En ORD-G37-002 se consultaron directamente los casos originales en `Casos_Prueba(Modulo6Agrup).csv:380` y estas rutas de código: `src/financial_valuation/infrastructure/routers/m06_router.py:137-146,190-245,295-300,401-443,498-508`; `src/financial_valuation/infrastructure/repositories/valoracion_repository.py:246-319`; `src/financial_valuation/application/use_cases/auditoria/consultar_auditoria_financiera_use_case.py:58-82`; `src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py:65-79`; `src/financial_valuation/infrastructure/repositories/trazabilidad_repository.py:37-117`; `src/financial_valuation/application/use_cases/trazabilidad/verificar_trazabilidad_use_case.py:44-90`; `src/financial_valuation/application/services/medidor.py:88-143`; `src/financial_valuation/infrastructure/repositories/precio_repository.py:20-64`; `src/biological_assets/infrastructure/routers/activo_biologico_router.py:1132-1155`; `src/biological_assets/infrastructure/schema/activo_biologico_schema.py:325-354,403-431`; `src/financial_valuation/domain/entities/contabilidad.py:15-30,71-98`; `src/telemetry/infrastructure/schema/monitoreo_schema.py:118-150`; `alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py:82-98` y `alembic/versions/a7f3c92e4d18_rf28_catalogo_widgets_y_defaults.py:90-95,132-136`. Las demás citas de la matriz proceden del inventario heredado y no se releen como prueba de comportamiento en TEST.

| Respuesta | Campos usados | Actor y permiso | Fuente |
|---|---|---|---|
| Activos, períodos, detalle, ficha y precios | IDs, titular, estado, peso, cálculo y precio vigente | Contador para M06; Administrador para ficha M02 | `m06_router.py:137-148,190-203,295-300`; `valoracion_repository.py:246-294`; `activo_biologico_router.py:1690-1705` |
| Variaciones, mediciones y líneas | IDs nuevos, tipo, monto, estado y `id_linea` | Contador, `valoracion_activos:2` | `valoracion_repository.py:297-319`; `m06_router.py:225-245` |
| RF-93 | `id_estado`, `total_ingresos`, `total_gastos`, `version` | Contador, `estado_resultados:1/2` | `m06_router.py:423-444`; `reporte_repository.py:40-62` |
| RF-94 técnico paginado | `total_registros`, `pagina_actual`, `eventos`, `id_referencia`, `payload_evento`, activo, monto y período | Contador, `auditoria_financiera:2` | `m06_router.py:498-508`; `consultar_auditoria_financiera_use_case.py:58-82`; `auditoria_financiera_repository.py:68-78` |
| RF-91 y M03 | `estado_verificacion`, `eslabones.ids.id_evento`, `ids_lectura_iot`, historial M03 | Contador, `trazabilidad_contable:2/5`, `historial_telemetria:2` | `m06_router.py:401-417`; `trazabilidad_repository.py:37-117`; `monitoreo_router.py:287-365` |

`GET /finanzas/periodos/{p}/variaciones` **no** devuelve `id_evento`; la cadena posterior a RF-91 lo ofrece mediante `eslabones.ids.id_evento`. `CADENA_COMPLETA` figura como resultado de auditoría de RF-91; en la cadena el nivel de fallo es `null` y `estado_verificacion` es `VERIFICADO` (`verificar_trazabilidad_use_case.py:45-90`, `trazabilidad_repository.py:30,91-117`).

**DEFECTO_FUNCIONAL_CANDIDATO del 011:** `generar_estado_resultados_use_case.py:4-5,29-35` exige período CERRADO y guarda versiones independientes. El caso pide acumulado observable antes y después en un período ABIERTO. La comprobación mínima preparada es GET de versiones y POST público en ABIERTO, cuyo error de negocio declarado es HTTP 422 `PERIODO_NO_CERRADO` (`shared/errors.py:91-99`). Solo un RUN TEST autorizado puede convertirlo en RECHAZADO. Los casos 012 y 013 continúan sin depender del éxito de RF-93.

## Diseño y presupuesto

El ejecutor selecciona cuatro bovinos individuales con reconocimiento previo y período ABIERTO común; recorre los candidatos del catálogo, documenta por qué descarta cada uno y prioriza cálculo anterior al precio vigente. Conserva los cuatro tipos de variación; reducir escrituras perdería al menos uno de los tipos de TC-M06-001 a 004. TB+ y TB- usan pesajes; TB- cambia a EN_TRATAMIENTO tras el evento; TB+/PM- y PM+ usan dos precios nuevos. El rebase de precio, si hace falta, queda separado mediante una nueva línea base antes del evento evaluado. Compara IDs de variaciones, líneas, mediciones, auditorías y estados antes y después. RF-94 se pagina hasta `total_registros`. RF-91 se solicita una vez por período y la cadena se lee después.

| Concepto | Máximo |
|---|---:|
| Login fuera del RUN | 2 |
| Eventos M02 | 5 |
| Precios RF-89 | 2 |
| Procesamientos M06 | 5 |
| PATCH EN_TRATAMIENTO | 1 |
| POST estado RF-93 | 1 |
| POST verificación RF-91 | 1 |
| Solicitudes dentro del RUN | 150 (120 del ejecutor como máximo; reserva de 30 para Newman, DELETE, bandeja y verificación poscierre) |
| Duración | 1800 s |

Dos precios `MERCADO_ACTIVO` pueden producir avisos NIC41 y efectos fuera del sandbox. El criterio aceptado por el responsable QA, registrado en el cierre oficial G32, limita `rollback.verificado` a los datos del sandbox: cuando hay escrituras exige DELETE HTTP 200, lecturas públicas poscierre completas, ausencia de los registros del RUN (eventos, precios, variaciones, líneas, mediciones, estados y auditorías) y restauración del estado M02 cambiado. Sin escrituras, DELETE 200 es suficiente. Las escrituras sin respuesta o sin ID conciliado y los registros aún presentes dejan el rollback no verificado. Los avisos NIC41 se declaran por separado en `efectos_persistentes_declarados`; no alteran veredictos ni oficialidad. No se crean telemetrías ni se usa MQTT/Edge. El historial público M03 no expone `apto_para_nic41` (`monitoreo_schema.py:118-150`), de modo que el 013 queda BLOQUEADO si no puede demostrarse una lectura apta enlazada. Un HTTP 500 de RF-91 se registra como síntoma similar a `INC-M06-G32-01`; solo se reutiliza esa incidencia si su causa se confirma con evidencia independiente, como el log mencionado en el informe G32.

| Efecto | Comprobación de cierre | Tratamiento |
|---|---|---|
| Datos del sandbox | DELETE 200 y lecturas públicas completas sin IDs del RUN; estado M02 restaurado | `rollback.verificado=true` solo si las escrituras están conciliadas |
| Aviso `ALERTA_FINANCIERA_NIC41` de precios | Tipo, cantidad e IDs de precios; bandeja propia del Contador observada cuando la lectura lo permite | Efecto persistente declarado y aceptado; informativo en `resultado.json` y «Cierre y rollback» |
| Escritura incierta o registro persistente | Respuesta del POST y lecturas poscierre | `rollback.verificado=false` |

## Contraste de contrato dentro del RUN

La ruta `--operacion diagnostico` se retiró porque el lanzador no admite los GET financieros de G37. Dentro de un RUN autorizado, `pedir` contrasta cada cuerpo exitoso con `pruebas/contrato_g37.json` antes de entregarlo al oráculo. El cierre hace el mismo contraste en sus lecturas públicas; el hijo Newman contrasta sus tres respuestas y devuelve únicamente el resultado y, si hay discrepancia, el esquema de nombres y tipos. `resultado.json` guarda `contraste_contrato` y `discrepancias_contrato` (ruta declarada, actor, HTTP, motivo y esquema real sin valores). El informe expone la sección «Contraste de contrato». Una discrepancia convierte el caso afectado en `NO_CONCLUYENTE` técnico y retira cualquier incidencia de producto inferida de esa respuesta.

Tras seleccionar el período y el primer activo, el ejecutor lee RF-93, RF-94 filtrado y el historial M03 antes del primer POST/PATCH del RUN, junto con las demás GET enumeradas en ORD-G37-011. Si una lectura previa discrepa o está incompleta, termina la preparación sin escrituras y entra en `finally` para cerrar. Las lecturas posteriores y los casos independientes continúan cuando una discrepancia aparece después del primer cambio. Las respuestas vacías permiten verificar solo el contenedor; los campos de elementos se comprueban cuando hay elementos reales. No hubo consulta TEST en esta preparación.

La primera página RF-94 se reutiliza en `auditoriaTodas`; el presupuesto vigente se detalla en ORD-G37-011. Las dos lecturas de login continúan fuera del RUN.

## Lista de control de lecciones G32–G36

| Lección | Estado | Evidencia local |
|---|---|---|
| G32 secreto en DELETE | aplicada | `g37.mjs:220-224`, cabecera `X-Sandbox-Secret` |
| G32 período destino | aplicada | `lib/g37_core.mjs:84-90`; `g37.mjs:297-305` |
| G32 precio vigente | aplicada | `lib/g37_core.mjs:74-82,91-128` |
| G32 RF-91 tras evaluar | aplicada | `g37.mjs:412-430` |
| G33 hijo Newman | aplicada | `pruebas/newman_hijo.mjs:7-27`; `pruebas/g37_env.test.mjs:56-61` |
| G34 base del frontend | no aplica | Solo API/Postman/Newman según fila original; no se prueba UI |
| G34 sincronización | no aplica | No hay UI Cypress ni sincronización frontend |
| G34 id corto del registro | aplicada | `g37.mjs:136-138`, `comprobaciones[].caso` usa TC-M06-011/012/013 |
| G35 selección | aplicada | `lib/g37_core.mjs:91-128`; `g37.mjs:286-305`; `pruebas/g37_ensayo.mjs:50-60` |
| G35 MODULE_NOT_FOUND | aplicada | `g37.mjs:31-35,188-191`; `pruebas/newman_hijo.mjs:7,26` |
| G35 actor de Newman | aplicada | `G37.postman_collection.json:3-30`; `pruebas/g37_env.test.mjs:37-55` |
| G35 presupuesto | aplicada | `lib/g37_core.mjs:9-11`; `g37.mjs:148-151` |
| G36 id_evento | aplicada | `pruebas/contrato_g37.json:147,388`; `pruebas/g37_env.test.mjs:30-35` |
| G36 saneado del RUN | aplicada | `pruebas/newman_hijo.mjs:8-22,38-40`; `g37.mjs:153-168` |

## Validación local

`node --check g37.mjs`, `node --check lib/g37_core.mjs`, `node pruebas/g37_env.test.mjs`, `node g37.mjs --comprobar`, `node pruebas/g37_ensayo.mjs`. El corredor `node --test` intenta crear un subproceso y recibe `spawn EPERM` en este entorno; la ejecución directa del archivo usa `node:test` en el mismo proceso. Estas órdenes no usan red ni crean RUN. El fixture `pruebas/resultado_g36_fixture.json` contiene únicamente estructura y metadatos no sensibles derivados del RUN G36 oficial; no es evidencia G37.

La base ORD-G37-003 tenía 17 modos locales. ORD-G37-004 conserva esos modos y añade `esquema_rf93_distinto_sin_escrituras` y `esquema_coincide` (19 en total). Validar con `node pruebas/g37_env.test.mjs`, `node pruebas/g37_ensayo.mjs`, `node g37.mjs --comprobar`, `node g37.mjs --capacidades` y la regresión local G36. El SHA-256 se calcula con `Get-FileHash <archivo> -Algorithm SHA256` después de las últimas ediciones. G32–G35 usan subprocesos en sus ensayos y no se ejecutan bajo esta restricción del entorno.

## ORD-G37-010: contrato de salida y precisión decimal

Los 20 endpoints y los 114 campos originales se revisaron contra `pruebas/contrato_g37.json`; se añadió el campo anidado `ultimo_cierre.precios_congelados[].precio_unitario` (115 citas ahora). Para M06, `m06_router.py` retorna diccionarios/listas y las lecturas salen de `repositories/sql.py:27-33` sin convertir `Decimal` a `float`. En TEST, el intento 3 muestra importes como cadenas decimales; esa evidencia prevalece sobre la inferencia de código. En rutas sin esquema real, `decimal|number` admite también el número que puede producir la codificación de un `Decimal` devuelto en un diccionario sin DTO; sigue siendo un riesgo a contrastar. La nulabilidad de `numero_id_tributaria` observada en TEST prevalece sobre `domain/entities/contabilidad.py:18-23` y la migración `c4d81e6f2a95_m06_nic41_esquema_rfc018.py:230-236`, que permiten NULL en filas preexistentes. Los campos de RF-94 y RF-91 conservan sus tipos estrictos de ID, estado y bandera. `decimal` acepta solo cadenas que cumplan `^-?\d+(\.\d+)?$`; no acepta exponentes ni valores no numéricos. Los oráculos 011 y 012 comparan importes con enteros `BigInt` escalados.

| Campo | Antes | Ahora | Cita de respuesta/serialización | Esquema real previo |
|---|---|---|---|---|
| activos[].valor_razonable_neto | number\|null | decimal\|null | `m06_router.py:190-193`; `valoracion_repository.py:246-270` | Sí, G37 intento 3 |
| periodos[].numero_id_tributaria | string | string\|null | `m06_router.py:295-299`; `periodo_repository.py:19-33` | Sí, G37 intento 3 |
| periodos[].ultimo_cierre.precios_congelados[].precio_unitario | sin control | decimal | `m06_router.py:297-299`; `periodo_repository.py:124-132` | Sí, G37 intento 3 |
| activo_detalle.calculos[].magnitud, valor_neto | number | decimal\|number | `m06_router.py:196-203`; `valoracion_repository.py:273-293` | No |
| ficha.peso_actual | number\|null | decimal\|null | `activo_biologico_router.py:1690-1704`; `activo_biologico_schema.py:403-431` | No |
| precios_get[].precio_unitario | number | decimal\|number | `m06_router.py:137-140`; `precio_repository.py:20-25` | No |
| variaciones[].monto_variacion, valor_razonable_anterior, valor_razonable_nuevo | number | decimal\|number | `m06_router.py:241-245`; `valoracion_repository.py:307-319` | No |
| mediciones[].ganancia_perdida_transformacion, ganancia_perdida_precio_mercado, variacion_total | number | decimal\|number | `m06_router.py:234-238`; `valoracion_repository.py:297-305` | No |
| estados_get[].total_ingresos, total_gastos, resultado_neto | number | decimal\|number | `m06_router.py:423-427`; `reporte_repository.py:55-62` | No |
| estado_detalle.total_ingresos, total_gastos, resultado_neto | number | decimal\|number | `m06_router.py:429-436`; `reporte_repository.py:40-48` | No |
| estado_post.total_ingresos, total_gastos, resultado_neto | number | decimal\|number | `m06_router.py:438-444`; `generar_estado_resultados_use_case.py:35-67` | No |
| auditoria.eventos[].monto_afectado | number | decimal\|number\|null | `m06_router.py:498-508`; `auditoria_financiera_repository.py:68-78` | No |
| auditoria.eventos[].payload_evento.monto | string | decimal | `medidor.py:128-134`; `m06_router.py:498-508` | No |

Los `resultado.json` oficiales de G32–G36 indicados en la orden se consultaron. No contienen `contraste_contrato[].esquema_real` para una ruta coincidente; sus comprobaciones no se trataron como observaciones de tipo. **Derivado solo de código:** `activo_detalle`, `ficha`, `precios_get`, `precios_post`, `evento_crecimiento`, `estado_patch`, `procesar`, `variaciones`, `mediciones`, `lineas`, `cadena`, `trazabilidad`, `estados_get`, `estado_detalle`, `estado_post`, `auditoria`, `m03_historial`, `eventos_get`. Sus campos de elemento aún requieren contraste en un RUN autorizado. `activos` y `periodos` tienen esquema observado únicamente para los campos presentes en el intento 3.

El intento 3 cerró con DELETE 200 y cero POST/PATCH. El ejecutor intentaba lecturas con `hechos.periodo === null`; el resultado solo registra el motivo genérico «No se completaron lecturas poscierre», de modo que no permite distinguir si falló una lectura o se lanzó una excepción. Ahora, sin escrituras ni período elegido, DELETE 200 verifica el rollback de datos del sandbox y registra `lecturas_poscierre: []`. Con escrituras, exige las lecturas completas y la ausencia/conciliación de IDs; cada lectura poscierre ejecutada queda registrada. La discrepancia de contrato se resume en Markdown como campo, esperado y recibido; el esquema completo permanece en `resultado.json`.

## Regresión local ORD-G37-005

`pruebas/g37_env.test.mjs` conserva la comprobación separada de ruta y versión (`OK paquete_newman <versión>`) y añade una prueba que lanza `pruebas/newman_hijo.mjs` con `process.execPath`, el mismo JSON por stdin y la misma síntesis JSON por stdout del ejecutor. Un servidor HTTP en `127.0.0.1` responde a una única lectura `estados_get` tomada de la colección vigente. Se exigen salida 0, HTTP 200, una solicitud, ninguna aserción fallida y ambos reportes en un directorio temporal del sistema, que se elimina al finalizar. La línea esperada es `OK newman_hijo: process.execPath, 1 lectura loopback HTTP 200`; debe tardar el tiempo de un proceso Newman real, no milisegundos de una mera consulta de versión. Un sandbox que impida crear subprocesos devuelve `spawn EPERM` antes de ejercitar al hijo; en ese entorno esta regresión queda pendiente de ejecución local permitida.

## ORD-G37-014: una petición a la vez por RUN

El ejecutor envía **una petición HTTP a la vez por RUN**. El sandbox comparte una sesión de base de datos por `X-Test-Run-Id`; el log del intento 5 mostró `InvalidRequestError` al obtener conexión, `IllegalStateChangeError` por `commit()` simultáneo y fallo al limpiar el contexto RLS. Las lecturas de detalle y ficha y las cuatro lecturas posteriores ahora se esperan en serie. `fetchEnContexto` rechaza una segunda petición en curso con `PETICION_CONCURRENTE`; Newman solo arranca sin peticiones pendientes y reserva la capa de peticiones mientras corre.

Una respuesta inesperada durante selección o preparación deja los casos en `NO_CONCLUYENTE` técnico con ruta, HTTP y código. `BLOQUEADO` por falta de cuatro candidatos requiere que todas las lecturas necesarias sean válidas. Las observaciones de candidatos y el informe enumeran únicamente condiciones incumplidas. Los ensayos locales incluyen un servidor de loopback lento que devuelve 500 ante solapamiento del mismo RUN, además de los modos `seleccion_con_500` y `seleccion_sin_candidatos_validos`. No se alteraron los oráculos, la colección, el contrato, el presupuesto ni el rollback.


## ORD-G37-015: cobertura local del flujo en serie

`pruebas/g37_env.test.mjs` recorre `principal()` contra un servidor HTTP loopback con 55 ms de retardo por peticion. Simula cuatro candidatos aptos y cubre seleccion, lecturas previas, escrituras M02/M06, procesar, RF-93, RF-91, DELETE 200 y lecturas poscierre. El servidor registra cualquier solapamiento y devuelve HTTP 500 `CONCURRENCIA` cuando ocurre. La variante sin Newman comprueba el recorrido del ejecutor y el rollback simulado. La variante completa recibe tambien las tres lecturas del hijo Newman real lanzado mediante `process.execPath`. Si el entorno devuelve `spawn EPERM`, esa variante queda pendiente de ejecucion en Windows con subprocesos habilitados. El hijo se espera de forma asincrona para que el servidor loopback del proceso de prueba pueda responder. Estas pruebas locales no son evidencia de TEST ni modifican los oraculos, contrato, coleccion, presupuesto o rollback.

## ORD-G37-019: decisiones antes de un nuevo RUN

La matriz original `Casos_Prueba(Modulo6Agrup).csv:380` conserva sus tres oráculos. El POST RF-93 en período ABIERTO tiene salida declarada HTTP 422 `PERIODO_NO_CERRADO` (`generar_estado_resultados_use_case.py:28-35`, `shared/errors.py:91-99`, `error_handlers.py:59-62`); esa respuesta rechaza 011 y deja continuar 012 y 013. Un 403 es una discrepancia de autorización técnica. Se consultó `permisos_schema.py:7-20` y `sesiones_routers.py:217-243`: GET `/sesiones/me/permisos` expone `permisos[]` con `id_recurso`, `id_accion` y `nombre_recurso`. Ambos actores se contrastan con cada par recurso:acción de `contrato_g37.json` antes de escribir.

## Precondición IoT de 013

`pruebas/precondicion_iot.json` documenta el SELECT de solo lectura del responsable QA en TEST del 2026-11-08: activo 943 (QA-M06-BOV-01, ACTIVO), dispositivo 849, telemetría apta 120011 capturada `2026-11-07T19:26:08Z`, último evento M02 `2026-11-07T20:16:16Z` y creación del activo `2026-11-07T19:55:29Z`. El rebase queda fechado `2026-11-08T11:58:00Z` y TB+ `2026-11-08T12:00:00Z`. Para TB+, la ventana RF-91 es `[2026-11-07T12:00:00Z, 2026-11-08T13:00:00Z]`; contiene la lectura 120011. La lectura precede a la creación del activo por 29 minutos y 21 segundos. `trazabilidad_repository.py:67-73` compara dispositivo, aptitud y ventana alrededor del evento, sin comparar el ciclo de vida del activo; se registra como observación, no incidencia.

El preflight valida orden de fechas, límites M02/creación, no futuro y pertenencia a la ventana; informa SHA-256 del archivo. Si cambia el estado, período, dispositivo o precio del 943, 013 queda BLOQUEADO con motivo y 011/012 siguen con los otros elegibles. El historial M03 se consulta por API pública para 943 entre `2026-11-07` y `2026-11-08`, antes de escribir para él; debe contener 120011. Una respuesta M02 `FECHA_INCOHERENTE`, `FECHA_ANTERIOR_REGISTRO` o `FECHA_FUTURA` bloquea 013 y detiene las escrituras posteriores para 943. El oráculo final exige el ID del evento TB+ y 120011 en `ids_lectura_iot`. No se crea telemetría. Según `contabilizador.periodo_para`, el hecho del 2026-11-08 usa el período ABIERTO que contiene esa fecha, o el primer ABIERTO posterior si estuviera cerrado; `periodoDestino` aplica la misma elección. El precio para el 943 se elige a la fecha de TB+, con vigencia no posterior a `2026-11-08`; un precio registrado después en el RUN no cambia la elección ya realizada para TB+.

### Tabla de decisiones

En la tabla, `N/C` significa NO_CONCLUYENTE técnico; la respuesta concreta HTTP/código o la ausencia de respuesta se conserva en `resultado.json`. Las filas posteriores no se atribuyen al producto cuando falla su preparación. Un RECHAZADO debe citar la respuesta observada.

| Paso | Respuesta posible | Acción del ejecutor | 011 / 012 / 013 |
|---|---|---|---|
| Selección | 200/esquema válido; 4xx, 500, sin respuesta o esquema discordante | Revisar catálogo completo; ante respuesta inesperada cerrar sin escribir | pendientes / pendientes / pendientes → N/C; sin cuatro elegibles → BLOQUEADO justificado |
| Permisos | 200 con pares exactos; falta recurso:acción, 4xx, 500, sin respuesta o esquema discordante | Contrastar ambos actores antes del primer POST/PATCH; cerrar si falla | N/C / N/C / N/C |
| Lecturas previas | 200 y esquema; 4xx, 500, sin respuesta o esquema discordante | Contrastar las GET y cerrar sin escribir ante fallo | N/C / N/C / N/C |
| Precondición IoT | Archivo inválido o fecha fuera de ventana | Preflight `ok=false`, SHA-256 informado, cero peticiones | N/C / N/C / N/C |
| Selección 943 | Estado, período, dispositivo o precio cambiados | BLOQUEAR 013 con motivo y buscar otros cuatro elegibles | Independientes / independientes / BLOQUEADO |
| Historial M03 943 | No contiene 120011 entre 2026-11-07 y 2026-11-08 | BLOQUEAR 013 antes de escribir para 943; continuar 011/012 | Independientes / independientes / BLOQUEADO |
| RF-93 POST | 201; 422 PERIODO_NO_CERRADO; 403; otro 4xx, 500, sin respuesta o esquema discordante | Guardar ID si 201; con 422 registrar incidencia Desarrollo y continuar; con 403 registrar fallo técnico; en otros fallos conservar respuesta y continuar casos independientes | 201: pendiente; 422: RECHAZADO; demás: N/C / pendiente / pendiente |
| Rebase | 201 evento y 200 procesar; 4xx, 500, sin respuesta o esquema discordante | Conciliar ID; si falla, no repetir escritura incierta y continuar pasos independientes | 011 pendiente o RECHAZADO / N/C si faltan tipos / N/C si falta TB+ |
| Eventos M02 | 201 con evento.id_eventos; 4xx, 500, sin respuesta o esquema discordante | Registrar ID o detener solo ese paso; no reintentar escritura incierta | pendiente o RECHAZADO / N/C si faltan variaciones / N/C si falta TB+ |
| Rebase/TB+ fechado 943 | 400 FECHA_INCOHERENTE, FECHA_ANTERIOR_REGISTRO o FECHA_FUTURA | Detener escrituras posteriores para 943 y pedir renovar precondición | 011/012 independientes / 013 BLOQUEADO |
| PATCH estado | 200; 4xx, 500, sin respuesta o esquema discordante | Registrar cambio o detener solo TB-; conservar respuesta | pendiente o RECHAZADO / N/C si falta TB- / independiente |
| Precios | 201 con id_precio_mercado; 4xx, 500, sin respuesta o esquema discordante | Registrar ID o detener solo PM; conservar efecto incierto | pendiente o RECHAZADO / N/C si faltan PM / independiente |
| Procesar | 200; 4xx, 500, sin respuesta o esquema discordante | Leer variaciones solo con 200; conservar respuesta | pendiente o RECHAZADO / N/C si faltan tipos / N/C si falta TB+ |
| Lecturas posteriores | 200 y esquema; 4xx, 500, sin respuesta o esquema discordante | Conciliar registros; evaluar cada caso con datos disponibles | N/C si falta RF-93; 012 N/C si falta RF-94; 013 independiente |
| Cadena inicial | 200 y esquema; 4xx, 500, sin respuesta o esquema discordante | Leer antes de RF-91; llamar RF-91 si existe TB+ y línea válida | 011/012 independientes; 013 N/C si cadena ilegible salvo RF-91 500 |
| RF-91 | 200; 500; 4xx conocido, otro 4xx, sin respuesta o esquema discordante | Con 200 leer variación/cadena final; con 500 rechazar con HTTP/código; demás N/C | 011/012 independientes; 013: 500 RECHAZADO, 200 pendiente, demás N/C |
| Cadena final | VERIFICADO con M02 y lectura M03; nivel 1; niveles 2–4; 4xx, 500, sin respuesta o esquema discordante | Contrastar eslabones; nivel 1 usa precondición QA; niveles 2–4 rechazan | 011/012 independientes; 013 APROBADO / BLOQUEADO o RECHAZADO / RECHAZADO / N/C |
| Newman | 1 iteración, 0 fallos y 3 respuestas; 4xx, 500, sin respuesta o esquema discordante | Ejecutar solo con línea positiva; guardar JSON/HTML reales | Veredictos conservados; RUN oficial solo con Newman válido |
| Cierre | DELETE 200 y lecturas de ausencia/restauración; 4xx, 500, sin respuesta o esquema discordante | Verificar rollback del sandbox, declarar efectos persistentes | Veredictos conservados; RUN oficial solo con rollback verificado |

### Evidencia de escrituras y presupuesto

`contrato_g37.json.evidencia_escrituras` separa las respuestas observadas en G32 TEST (crecimiento 201, precio 201, PATCH 200, procesar 200 y RF-91 500) de las previstas por código sin respuesta equivalente G32 (RF-93 422 y RF-91 200). `resultado.json` de G32 registra los HTTP; `g32.mjs:502-580` y los routers citados fijan los campos usados. Los mocks de escritura deben respetar esa procedencia. El intento 6 de G37 registró 16 activos, 5 especies, candidatos 943–948 y 26 GET previas; esa es la base para estimar el flujo, no el catálogo mínimo de los ensayos iniciales.

Presupuesto máximo del camino completo con ese catálogo: 2 logins + 2 permisos + 26 lecturas previas + 1 RF-93 + 6 de rebase (dos eventos, procesamientos y detalles) + 16 de cuatro pasos (base, evento, proceso, variaciones) + 2 precios + 1 PATCH + 5 lecturas posteriores + 4 de RF-91/cadenas + 3 Newman + 23 lecturas de cierre (incluye hasta diez páginas RF-94) + 1 DELETE + 2 bandeja = **94 solicitudes, frente al límite 150**. Las páginas RF-94 extra se limitan a diez. La guarda del ejecutor conserva la reserva de 30 para Newman y cierre.

La prueba local `g37_env.test.mjs` incluye el escenario de 422 + cuatro variaciones auditadas + RF-91 500 con catálogo de 16 activos y cinco especies. Cada fila de la tabla tiene ensayo con `principal()` y servidor loopback; los RUN sintéticos se crean en `os.tmpdir()` y se eliminan al terminar. Los escenarios sin Newman se ejecutan localmente y no acreditan oficialidad de un RUN real. Las variantes con el hijo Newman real quedan pendientes en Windows cuando el entorno devuelve `spawn EPERM`.

## ORD-G37-011: precontraste de todas las GET

El orden vigente es: selección del período y candidatos → lecturas previas completas → escrituras → lecturas posteriores → cierre. Antes del primer POST/PATCH, el ejecutor contrasta las GET del contrato sobre datos existentes. `lecturasPrevias` comprueba HTTP 200, eco del RUN y esquema en cada respuesta; usa Administrador para ficha y eventos, Contador para las demás. Lee cadena de la primera línea existente y detalle del primer estado existente. Si falta cualquiera de esos recursos, el contraste registra «sin elementos para contrastar» y sigue. Una discrepancia de HTTP o esquema termina la preparación sin escrituras y queda en `resultado.json` y en el informe con ruta, campo, esperado y recibido. Las rutas vacías contrastan el contenedor; sus campos de elemento siguen sin evidencia real hasta un RUN autorizado con elementos.

| Ruta GET del contrato | Se contrasta antes de escribir | Evidencia real de tipos de elemento en TEST |
|---|---|---|
| `/finanzas/activos` | Sí | Sí, intento 3, campos presentes |
| `/finanzas/periodos` | Sí | Sí, intento 3, campos presentes |
| `/finanzas/activos/{activo}` | Sí, selección | No |
| `/activos-biologicos/{activo}/ficha-integral` | Sí, selección y candidato elegido | No |
| `/finanzas/precios?id_especie={especie}` | Sí, selección | No |
| `/finanzas/periodos/{periodo}/variaciones` | Sí | No |
| `/finanzas/periodos/{periodo}/mediciones` | Sí | No |
| `/finanzas/lineas?id_periodo_contable={periodo}` | Sí | No |
| `/finanzas/lineas/{linea}/cadena` | Sí, si existe línea | Sí, intento 6, campos presentes |
| `/finanzas/periodos/{periodo}/estados-resultados` | Sí | No |
| `/finanzas/estados-resultados/{estado}` | Sí, si existe estado | No |
| `/finanzas/auditoria?...` | Sí | No |
| `/iot/monitoreo/historial?...` | Sí | No |
| `/activos-biologicos/{activo}/eventos` | Sí | No |

Las tres lecturas previas de ORD-G37-004 y las tres líneas base ya existentes se reutilizan. Se añaden cuatro peticiones máximas (ficha del elegido, eventos, cadena y estado detalle). El ejecutor queda acotado a 120 solicitudes y reserva 30 para el resto: Newman 3, DELETE 1, bandeja inicial y posterior 2, y hasta 22 lecturas públicas de cierre. El techo calculado es 148/150 solicitudes, con duración límite 1800 s. El ensayo de precontraste y continuación usa hasta 14/150 solicitudes simuladas; cubre las tres modalidades nuevas, pero no mide el tiempo ni la totalidad del flujo real de evaluación. La comprobación del techo completo se hará con un RUN autorizado; esta preparación no consultó TEST ni generó evidencias de producto.

## ORD-G37-018: cadena pendiente y lecturas posteriores

El oráculo de `TC-M06-G37` figura en `SIGAB_QA_ORQUESTACION/estado/Casos_Prueba(Modulo6Agrup).csv.respaldo-20261108:380`: una variación nueva está en `VERIFICACION_PENDIENTE`; con `CADENA_COMPLETA` pasa a `VERIFICADO` y permite navegar a M02 y M03. El `LEFT JOIN LATERAL` de `trazabilidad_repository.py:106-117` devuelve `estado_verificacion`, `nivel_fallo` superior y `eslabones` como `null` cuando la línea aún no tiene verificación. `registrar_verificacion` guarda el JSON (`trazabilidad_repository.py:91-104`) y el caso de uso cambia el estado (`verificar_trazabilidad_use_case.py:45-67`). El contrato acepta `eslabones: object|null` y conserva la comprobación de subcampos cuando hay objeto. El ejecutor lee la cadena nueva antes y después de RF-91. Tras RF-91, el oráculo exige `VERIFICADO`, `nivel_fallo: null`, `id_evento` M02 e `ids_lectura_iot` M03.

Campos de lecturas posteriores a escrituras revisados por cambio de forma:

| Lectura | Campos y conclusión | Fuente de código consultada |
|---|---|---|
| Variaciones tras procesar, tras RF-91 y poscierre | `id_linea: number|null` y `tipo_evidencia: string|null` ya cubren el `LEFT JOIN`; `estado_trazabilidad` cambia de valor, no de tipo. IDs e importes conservan forma. | `valoracion_repository.py:307-319` |
| Mediciones y detalle del activo tras procesar y poscierre | `mediciones[].id_evento: number|null`, `calculos[].id_precio_mercado: number|null`, `json_metodo_costo: object|null` ya cubren ausencia; IDs e importes conservan forma. | `valoracion_repository.py:273-305` |
| Líneas y cadena antes/después de RF-91 y poscierre | IDs, `tipo_evidencia` y `estado_trazabilidad` conservan tipo; `estado_verificacion: string|null`, `nivel_fallo: number|null` y `eslabones: object|null` cubren la línea sin verificar y la verificada. | `asiento_repository.py:20-26,79-91`; `trazabilidad_repository.py:91-117`; `verificar_trazabilidad_use_case.py:45-67` |
| GET, detalle y POST de estado de resultados | `id_estado`, `version`, totales y estado conservan forma; la lista puede pasar de vacía a no vacía. | `reporte_repository.py:40-71` |
| Auditoría RF-94 y poscierre | `monto_afectado: decimal|number|null`, `payload_evento.id_evento: number|null` e `id_cierre: number|null` ya cubren las ramas; el filtro `VARIACION_REGISTRADA` mantiene IDs y payload. | `auditoria_financiera_repository.py:68-78`; `consultar_auditoria_financiera_use_case.py:58-82`; `medidor.py:128-134` |
| Historial M03, eventos M02, ficha y precios poscierre | `items[].id_activo_biologico: number|null`, `fecha_vencimiento: string|null`, `peso_actual: decimal|null` y `unidad_peso: string|null` ya admiten ausencia; IDs conservan forma. | `monitoreo_schema.py:206-225`; `precio_repository.py:20-60`; `activo_biologico_schema.py:325-346,403-440` |

Los modos `cadena_pendiente_eslabones_null` y `cadena_verificada_con_ids` cubren ambas formas; `013_cumple` también cubre los IDs finales. Para mantener el techo de 120 solicitudes del ejecutor, la última lectura de variaciones posterior a una escritura se reutiliza cuando sigue vigente. Los ensayos sintéticos actuales viven solo en `os.tmpdir()` y se eliminan. Esta revisión es local y no aporta evidencia de TEST; colección, presupuesto, rollback, serialización y salvaguarda se conservan.

## ORD-G37-017: tipo de nivel de fallo en cadena

El intento 6 (`RUN-G37-V1-20261108-220244`) registró 26 GET previas con HTTP 200 y eco: 25 coincidieron con el contrato y la cadena discrepó solo en `cadena.eslabones.nivel_fallo`. Su `esquema_real` conserva `number`. `verificar_cadena` devuelve `int | None` (`src/financial_valuation/domain/services/trazabilidad.py:25-34`), el caso de uso lo incorpora al JSON (`src/financial_valuation/application/use_cases/trazabilidad/verificar_trazabilidad_use_case.py:51-52`), el repositorio devuelve ese JSON sin conversión (`src/financial_valuation/infrastructure/repositories/trazabilidad_repository.py:106-117`) y el router retorna el diccionario (`src/financial_valuation/infrastructure/routers/m06_router.py:409-417`). El tipo contratado es `number|null`; los demás campos declarados de cadena coinciden con el esquema real. El `nivel_fallo` superior también es numérico o nulo por la consulta SQL del mismo repositorio, pero no forma parte de los campos declarados del contrato de esta orden.

Los otros 25 contrastes registran `coincide` sin conservar `esquema_real`. Esa marca prueba los tipos de campos presentes que el comparador verificó; no permite enumerar tipos de elementos de listas vacías ni campos que el contrato no declara. Se revisaron las citas de construcción y respuesta de los campos declarados en `pruebas/contrato_g37.json`: los identificadores y versiones se mantienen numéricos, los importes aceptan decimal serializado o número donde corresponde y no se encontró otro entero declarado como cadena. El intento 3 ya había observado `periodos[].ultimo_cierre.activos_excluidos[].nivel_fallo` como número; ese subcampo no está declarado en el contrato superficial de `periodos`. Una línea sin verificación puede tener `eslabones` nulo por el LEFT JOIN (`trazabilidad_repository.py:106-117`); el contrato actual de cadena requiere un objeto, por lo que esa variante sigue pendiente de contraste en un RUN autorizado. La preparación no modifica los oráculos ni evidencia histórica.

## ORD-G37-023: contrato y precondición del intento 7

Se consultó la fila 380 de `tests/Test_Testing/Test_Modulo6/Casos_Prueba(Modulo6Agrup).csv`; sus oráculos 011, 012 y 013 permanecen. Se consultaron realmente `registrar_precio_use_case.py:99-100`, `verificar_trazabilidad_use_case.py:45-90`, `m06_router.py:218-223,401-407,438-444`, `activo_biologico_router.py:1176-1190,1344-1365`, `activo_biologico_schema.py:290-356`, `monitoreo_router.py:302-316`, `historial_telemetria_repository.py:59-80,290-292,318-320` y `trazabilidad_repository.py:59-75` (rutas bajo `src/`). El `resultado.json` del RUN 230500 se leyó sin editarlo: `precios_post` devolvió 201 con `id_precio_mercado`, `estado`, `unidad_medida`, `desviacion_pct` y `fecha_vigencia`, sin `mensaje`.

| Escritura | Campos que lee el ejecutor | Campos declarados obligatorios | Cita | Evidencia real |
|---|---|---|---|---|
| `evento_crecimiento` | `evento.id_eventos` | `evento.id_eventos` | `activo_biologico_schema.py:325-356`; `activo_biologico_router.py:1176-1190`; `g37.mjs:753-805` | G32 TEST, HTTP 201; campos del código |
| `precios_post` | `id_precio_mercado` | `id_precio_mercado`, `estado`, `unidad_medida`, `desviacion_pct`, `fecha_vigencia` por esquema exacto de la orden | `registrar_precio_use_case.py:99-100`; `g37.mjs:774-785` | RUN 230500, `discrepancias_contrato[].esquema_real`, HTTP 201 |
| `estado_patch` | Ninguno; se lee HTTP 200 | Ninguno | `activo_biologico_router.py:1344-1365`; `g37.mjs:800-803` | RUN 230500, HTTP 200; cuerpo solo por código |
| `procesar` | Ninguno; se lee HTTP 200 y luego GET de variaciones | Ninguno | `m06_router.py:218-223`; `g37.mjs:763-806` | RUN 230500, HTTP 200; cuerpo solo por código |
| `estado_post` | `id_estado`, `total_ingresos`, `total_gastos`, `version` cuando 201 | Esos cuatro campos | `generar_estado_resultados_use_case.py:35-67`; `g37.mjs:723-737,843-855` | RUN 230500, HTTP 422 `PERIODO_NO_CERRADO`; respuesta 201 solo código |
| `trazabilidad` | HTTP/código; la cadena final se lee aparte | `verificadas`, `pendientes[].{id_linea,tipo_hecho,id_activo_biologico,faltantes[],nivel_fallo}` por instrucción expresa de la orden | `verificar_trazabilidad_use_case.py:45-90`; `m06_router.py:401-407` | G32 TEST, HTTP 500; respuesta 200 solo código. 422 `PERIODO_NO_ABIERTO` conocido por código |

La regla general es declarar obligatorios solo campos leídos por el ejecutor y devueltos siempre por el código. `precios_post` y RF-91 conservan el esquema completo exigido explícitamente por ORD-G37-023. Un 201 válido de precio con ID no incrementa `registros_sin_id` ni marca `hechos.inciertas`; un POST sin respuesta o un 201 sin el ID necesario sí se contabiliza como incierto.

La precondición IoT declara sensor 1311, área 741, finca 463, vinculación de activo `null` y asociación sensor-área `2026-11-07T19:59:14Z`. Las fincas del Contador verificadas por el responsable QA son `[184, 463]`; el preflight exige pertenencia. El archivo `precondicion_iot.json` tiene SHA-256 `E237AE446D71212466D9AEFEE3AD0C4B4F30F078EC3A0AC448AEE65B9C59DE89`. El contrato tiene SHA-256 `6475F1DAFDAB428A7A68250BD162DAFF43CC56DD1642416B1D0AFFD136ADF99E`. Antes de escribir para 943 se consulta `/iot/monitoreo/historial` con fechas `2026-11-07`, `sensor_id=1311`, página 1 y 100 por página, hasta tres páginas; se exige 120011. Si no aparece, 013 queda BLOQUEADO y 011/012 siguen con los demás activos. La lectura es anterior a la creación del activo y a la asociación sensor-área; RF-91 enlaza por dispositivo, aptitud NIC41 y ventana del evento según `trazabilidad_repository.py:59-75`. Esto se informa como observación, sin incidencia.

`replay_intento7_500` y `replay_intento7_200` usan el servidor loopback y `os.tmpdir()`; reproducen catálogo de 16 activos, permisos, lecturas previas, RF-93 422, escrituras 201/200, historial por sensor y RF-91 500/200. Newman se ejecuta dentro del proceso solo en ensayo local si Windows rechaza el subproceso con `spawn EPERM`. La ruta real conserva el hijo Newman. Ningún ensayo es evidencia de TEST.
