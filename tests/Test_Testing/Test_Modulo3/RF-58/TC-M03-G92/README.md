# TC-M03-G92 — RF-58 / CU04

**Estado:** ORD-G92-030, conciliación documental y de automatización de TC-M03-181 conforme a decisiones QA de 2026-10-25 y 2026-10-31. No se accedió a TEST ni se creó un RUN. Se actualizó únicamente el informe del RUN oficial existente; `resultado.json` y las evidencias históricas permanecen intactos.

## Fuente y oráculos

Se consultaron la fila TC-M03-G92 de `Casos_Prueba(Modulo3 Agrupado).csv` (Windows-1252), RF-58 CA-14 y la salida 5 en `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3 (1).md`. La matriz exige API Postman/Newman, no UI.

- **TC-M03-181:** «El resumen de la unidad presenta ROJO como estado general (peor estado presente), incluyendo variables en atención/críticas, alertas activas asociadas y timestamp de actualización.» La matriz pide VERDE, AMARILLO y ROJO en B. El ensayo construye VERDE y ROJO; AMARILLO queda como limitación observada del sandbox, sin cambiar el oráculo.
- **TC-M03-182:** «El monitoreo muestra únicamente los sensores e información de la unidad seleccionada, sin datos de otras unidades.» El Productor debe acceder a A y B; se consultan por separado.
- **TC-M03-183:** «En la página 1, estado_general="ROJO" aunque el sensor en ROJO no aparezca en el arreglo de sensores de esa página.» La unidad A tiene 60 sensores ordenados por ID, ROJO en 1196 (posición 55), con `pagina=1&por_pagina=50`.

`API-181-01` comprueba estado general ROJO y `API-181-02` la alerta CRÍTICA activa asociada y el timestamp. Esas dos API son obligatorias en 181. `PRE-181-01` exige VERDE y ROJO en B; AMARILLO no construible en el sandbox queda como observación de entorno (ORD-G92-026). `API-181-03` registra las variables visibles como observación `EXCLUIDA_DEL_ORACULO`: QA confirmó el 2026-10-25 que RF-58 no exige campos de variables en atención/críticas en el resumen. El RUN oficial conserva la antigua aserción Newman fallida y el registro técnico previo entre obligatorias; el informe explica ambos desajustes sin alterar el veredicto APROBADO de 181 ni `resultado.json`. El recálculo local de `estado_general` con la página era candidato para 183 y quedó confirmado por su evidencia pública del RUN autorizado.

## Archivos vigentes

| Archivo | Función |
|---|---|
| `g92.mjs` | Ejecutor canónico y `--comprobar` sin red. |
| `G92.postman_collection.json` | Colección Newman única, cuatro consultas filtradas en una invocación. |
| `lib/contrato_ejecutor.mjs`, `lib/g92_escenario.mjs`, `lib/g92_seguridad.mjs` | Contrato, escenario y saneamiento. |
| `pruebas/g92.test.mjs`, `pruebas/validar_cuerpos_g92.py`, `pruebas/respuestas_run_021342_saneadas.json` | Ensayos locales en memoria y proyección saneada de respuestas reales, sin RUN nuevo. |
| `BLOQUEO.md` | Antecedente técnico del sandbox. |
| `Resultados/RUN-G92-V1-20261031-022537/` | RUN oficial V1-10, con informe, resultado y evidencia saneada. |

No hay spec Cypress vigente porque estos casos no exigen UI. No se retiran archivos ni evidencias históricas.

## Historial de intentos V1

Las referencias siguientes son identificadores históricos en texto. El orquestador retirará las carpetas técnicas; el RUN oficial conservado es **RUN-G92-V1-20261031-022537**.

| Intento | Fecha y referencia | Motivo principal | Resultado |
|---|---|---|---|
| 1 | 2026-10-25 07:25:18, RUN-G92-V1-20261025-072518 | Timeout de GET global del dashboard. | NO_CONCLUYENTE. |
| 2 | 2026-10-25 07:56:32, RUN-G92-V1-20261025-075632 | POST de sensor HTTP 500. | NO_CONCLUYENTE. |
| 3 | 2026-10-31 01:06:17, RUN-G92-V1-20261031-010617 | Login de Productor sin finca HTTP 401. | NO_CONCLUYENTE. |
| 4 | 2026-10-31 01:14:56, RUN-G92-V1-20261031-011456 | POST de telemetría HTTP 400. | NO_CONCLUYENTE. |
| 5 | 2026-10-31 01:22:36, RUN-G92-V1-20261031-012236 | POST de telemetría HTTP 400 ERROR_TIEMPO. | NO_CONCLUYENTE; antecedente SBX-G92-01. |
| 6 | 2026-10-31 01:30:32, RUN-G92-V1-20261031-013032 | POST de telemetría HTTP 401 con sensor asociado dentro del RUN. | NO_CONCLUYENTE; antecedente SBX-G92-01. |
| 7 | 2026-10-31 01:59:06, RUN-G92-V1-20261031-015906 | Riesgo de aviso E7 por falta de umbral antes del dashboard. | NO_CONCLUYENTE. |
| 8 | 2026-10-31 02:05:49, RUN-G92-V1-20261031-020549 | Consolidación E14/E15 interpretada por el ejecutor como alerta duplicada. | ERROR_QA, sin veredicto funcional. |
| 9 | 2026-10-31 02:13:42, RUN-G92-V1-20261031-021342 | Lecturas sin clasificar por worker postcommit durante el RUN. | 182 APROBADO; 181 y 183 NO_CONCLUYENTE; antecedente SBX-G92-02. |
| 10 | 2026-10-31 02:25:37, RUN-G92-V1-20261031-022537 | Escenario ROJO por alerta CRITICO y paginación de 60 sensores. | OFICIAL, rollback VERIFICADO; 181 y 182 APROBADOS, 183 RECHAZADO. |

## Semilla persistente y acreditación

La semilla informada por IA de BD y responsable QA en 2026-10-31 tiene finca 184, especie 126, área A 697 (`QA G92 Unidad A`) con dispositivo 785 y sensores 1142–1201, y área B 698 (`QA G92 Unidad B`) con dispositivo 786 y sensores 1202–1204. Los seriales se leen por nombre de variable: `QA_G92_A_SERIAL` y `QA_G92_B_SERIAL`. La ausencia de cualquiera detiene el preflight. No se imprimen sus valores. Las asociaciones 804–866 y calibraciones 319–381 preceden al RUN; ambas áreas carecen de gateway. Se acreditan por GET, con sensores activos, asociaciones vigentes, calibraciones de referencia 25/ganancia 1/offset 0, cero alertas y cero lecturas desde 2026-10-30. Si alguna comprobación falla, se aborta antes de escribir. El GET de área no expone vínculos de activos biológicos; su ausencia fue informada por la IA de BD y queda como límite de acreditación pública.

El umbral activo 70 de especie 126 debe corresponder a TEMPERATURA_AMBIENTAL según el catálogo público GET /configuracion/variables-ambientales y cubrir 25/29 °C como normal. La acreditación por GET y los canarios E7 preceden toda escritura. El preflight conserva la lista blanca: máximo dos POST de sensor en 785 (uno legítimo y uno intento RLS sin finca), **63 ingestas y dos alertas, una por área**. Se prohíben POST de áreas, dispositivos, asociaciones y calibraciones. Los 60 sensores de A y los tres de B reciben 25 °C. Una alerta `ESTRES_TERMICO` CRÍTICA, con humedad en `correlacion_variables` y THI validado localmente por RF-57, se liga a la lectura de 1196 (posición 55) en A; otra a la de 1204 en B. CA-4 lleva esos sensores a ROJO; los demás permanecen VERDE. Los resúmenes deben tener una alerta activa asociada por área. Un `es_duplicado:true` solo se acepta como consolidación cuando `id_alerta` y `alerta_existente_id` coinciden con una alerta creada en el mismo RUN y área; la respuesta y el GET quedan en `resultado.json`. Un ID ajeno sigue siendo `ALERTA_DUPLICADA_ERROR_QA`.

La clasificación por niveles RF-17 corre en `src/telemetry/infrastructure/workers/postcommit_worker.py:155,173-185` mediante `ReclasificarSemaforoUseCase` (`src/telemetry/application/use_cases/monitoreo/reclasificar_semaforo_use_case.py:89`) y `calcular_por_niveles` (`src/telemetry/domain/entities/monitoreo.py:263`). Usa una conexión propia y lecturas confirmadas. En el sandbox las lecturas no se confirman: el RUN 021342 mostró 1203 con 19,5 °C VERDE, 1196 con 16 °C VERDE y 1204 con 16 °C ROJO solo por su alerta CRÍTICA. Por eso AMARILLO de la precondición de 181 no es construible aquí; `PRE-181-01` lo documenta como limitación del entorno, no como defecto del producto. El mismo RUN observó resumen A VERDE con 60 sensores VERDE y resumen B ROJO con una alerta. La proyección saneada en `pruebas/` permite repetir el diagnóstico en memoria; el nuevo plan se simula separadamente, sin presentarlo como evidencia de TEST.

`NOW()` de la función de ingesta queda fijo en la apertura de la transacción sandbox, mientras que la API de asociación usa el reloj real. Por ello las 65 marcas de captura/evento se anclan a la cabecera `Date` de `GET /usuarios/me` dentro del RUN: desde apertura −60 s hasta apertura −44 s, posteriores a la asociación y calibración persistentes. Un sensor asociado dentro del RUN no puede recibir estas lecturas. El presupuesto operativo es 417 solicitudes directas; cuatro se reservan antes del cierre y las lecturas posteriores al DELETE se registran incluso si superan ese tope.

## RLS, canario y cierre

`RLS-G92-01` crea un único sensor nuevo sin asociación ni ingesta en el dispositivo 785 y verifica su lectura posterior. `RLS-G92-02` intenta leer y crear con la cuenta Productor sin finca; si ese POST crea un sensor por un fallo de acceso, se inventaría para verificar su reversión y se detiene el escenario. `RLS-G92-03` queda `NO_CONCLUYENTE`: no hay UPDATE público de traslado.

Un canario E7 de un sensor por área protege las consultas completas de baseline, Newman y cierre. No garantiza que los demás sensores no disparen correo; el correo E7 y la auditoría de GET no se revierten con DELETE. El cierre comprueba por GET que desaparecen las alertas del RUN, que ambas áreas quedan sin alertas ni lecturas, que el dispositivo 785 vuelve a tener solo los 60 sensores persistentes, que el sensor RLS no figura, que las respuestas de la semilla coinciden con el baseline y que el estado del dashboard de ambas áreas vuelve al previo cuando hubo escrituras. Si el RUN aborta antes de cualquier escritura, el cierre registra SIN_ESCRITURAS_QUE_REVERTIR sin declarar rollback verificado ni exigir baseline del dashboard. Las áreas, dispositivos, sensores, asociaciones y calibraciones persistentes no se borran.

La **reversión de la semilla persistente**, si QA/DBA la decide después, requeriría inventariar y retirar por procedimiento autorizado los sensores 1142–1204, asociaciones 804–866, calibraciones 319–381, dispositivos 785/786 y áreas 697/698, verificando dependencias y ausencia de uso por otros grupos. **No se ha ejecutado ni se ejecuta en esta orden.** La nota técnica para DBA es la limitación de `NOW()` y `fecha_asociacion` descrita arriba; no se crea SOL ni se solicita SQL.

Una evaluación futura autorizada dejaría un único informe oficial y `resultado.json` dentro de su RUN, junto con reportes Newman reales. V1 reintentado permanece bajo `Resultados/`; V2 exige decisión explícita y usa `EvaluacionV2/Resultados/`.

## Validación local y código consultado

Ejecutar sin TEST: `node --check g92.mjs`, `node g92.mjs --comprobar`, `node pruebas/g92.test.mjs` y `C:/Users/yoloh/OneDrive/Escritorio/pruebas/sgpmp-backend/.venv/Scripts/python.exe pruebas/validar_cuerpos_g92.py`.

En esta orden se leyeron realmente `src/telemetry/infrastructure/workers/postcommit_worker.py`, `src/telemetry/application/use_cases/monitoreo/reclasificar_semaforo_use_case.py`, `src/telemetry/infrastructure/routers/alerta_router.py`, los DTO/reglas de RF-57 importados por `validar_cuerpos_g92.py`, la matriz y el RF-58. Las otras rutas de código citadas arriba constan como antecedente del README previo; no se releyeron en esta orden. No se consultó TEST.

