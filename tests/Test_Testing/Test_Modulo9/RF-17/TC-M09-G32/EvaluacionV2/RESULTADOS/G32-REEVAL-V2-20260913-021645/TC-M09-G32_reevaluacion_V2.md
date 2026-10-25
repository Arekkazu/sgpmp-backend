# TC-M09-G32 — REEVALUACIÓN V2

Caso original: **TC-M09-69 — Verificar que una modificación de umbral actualice la configuración utilizada por monitoreo**
RF-17 · CU-03 · Integración (Backend + Monitoreo) · Herramienta: Newman
Responsable QA: Juan Esteban · RUN_ID: `G32-REEVAL-V2-20260913-021645` · Fecha local: 2026-09-13 · Entorno decisorio: **TEST (confirmado en DEV)**

---

## DECISIÓN GENERAL

### REEVALUACIÓN DESAPROBADA — DEFECTO DEL PRODUCTO / FUNCIONALIDAD NO IMPLEMENTADA

El módulo de Monitoreo **no consume la configuración RF-17**, ni en TEST ni en
DEV:

- El historial resuelve el semáforo con `UmbralHistoricoM09Adapter`, un stub que
  siempre devuelve `None`, así que todos los semáforos históricos quedan GRIS.
- El dashboard toma `estado_semaforo` de `modulo3.estados_actuales_sensores`,
  sin relación con los umbrales de M09.
- Ningún código de telemetría, predicción o compartido lee
  `umbrales_ambientales` ni `niveles_alerta_ambientales`.
- Las respuestas de Monitoreo no exponen `id_umbral_ambiental`, `valor_min`,
  `valor_max`, niveles, versión ni especie para correlacionar.

Por tanto, una modificación RF-17 no puede reflejarse en Monitoreo. La
condición central de TC-69
(`MONITORING_AFTER == RF17_AFTER ≠ MONITORING_BEFORE`) no puede cumplirse.

| Caso | V1 | V2 | Ambiente decisorio | Motivo | Categoría | Equipo | Acción |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-M09-69 | BLOCKED — configuración efectiva de Monitoreo no verificable (0 PATCH) | **DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA** | TEST (DEV confirma) | Monitoreo no integra umbrales RF-17: semáforo histórico por stub (`None` → GRIS), dashboard sin fuente RF-17 y API sin rango, niveles, ID ni especie de la configuración efectiva | FLUJO — Flujo / Proceso | Desarrollo | **REPORTAR A DESARROLLO** — actualizar/reabrir **INC-M09-33-G32 (#160)**, sin duplicar |

**Escrituras: 0 UPDATE.** El checklist previo (§140) tiene «No» en condiciones
esenciales:

- Punto 11: API de Monitoreo con configuración efectiva identificada.
- Punto 12: correlación configuración ↔ monitoreo demostrable.
- Punto 15: RF17_BEFORE y MONITORING_BEFORE representan la misma configuración.

Un PATCH habría cambiado un umbral sin poder observar su efecto en Monitoreo,
y el producto no tiene camino de código para reflejarlo.

---

## RESUMEN V1

Evidencia V1: `RF-17/TC-M09-G32/RESULTADOS/run-20260906-024626/` (solo lectura, intacta).

| Campo | V1 |
| --- | --- |
| Ambiente | TEST |
| Actor | Administrador TEST (rol confirmado, HTTP 200) |
| Configuración | Umbral 11 · Cachama Blanca · Oxígeno disuelto (0.00–100.00; normal 4–12, precaución 2–4, crítico 0–2), solo discovery |
| Endpoint RF-17 | `PATCH /configuracion/umbrales/{id}` (no ejecutado) |
| Endpoints Monitoreo | `GET /iot/monitoreo/dashboard`, `GET /iot/monitoreo/historial` (200) |
| Valores BEFORE / AFTER | BEFORE RF-17 conocido; Monitoreo no expone valores; AFTER no aplica |
| UPDATE | No ejecutado (0/2) |
| ¿Consultó Monitoreo? | **Sí**: 5 aserciones de discovery PASS; Monitoreo sin umbral, rango ni especie correlacionable; semáforos históricos GRIS |
| Resultado | **BLOCKED — CONFIGURACIÓN EFECTIVA DE MONITOREO NO VERIFICABLE EN TEST** |
| Defecto / blocker / error QA | Blocker de observabilidad; V1 señaló el stub `UmbralHistoricoM09Adapter` pero no lo clasificó como defecto por no poder confirmar el SHA desplegado; sin error QA |
| Acción V1 | Reportar a Desarrollo para desbloqueo |
| Incidencia | Registrada por Desarrollo como **INC-M09-33-G32 (#160)**. Su nota (`anotaciones/modulo_9/inc_m09_monitoreo_umbral_efectivo_bloqueado.md`) confirma el stub, la ausencia de mapeo `tipo_variable ↔ variables_ambientales` y de correlación sensor → activo → especie, y decide «no tocar código» hasta que AIoT entregue la correlación |

V1 no verificó solo RF-17: sí consultó Monitoreo. Su resultado no fue un error
de prueba; quedó bloqueado porque la integración no era observable.

---

## MOTIVO DE REEVALUACIÓN

Determinar si, tras el ciclo de correcciones (rc.33 → rc.37), Monitoreo ya
consume y refleja la configuración RF-17, y resolver lo que V1 dejó abierto:
defecto de producto o solo desfase de despliegue en TEST. La comprobación se
repitió en DEV (§20 y §145).

---

## ENTORNO

| Elemento | Valor |
| --- | --- |
| TEST | `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`. La URL suministrada `http://…` responde 404 del proxy; HTTPS es el criterio ya autorizado en G77, G22, G24 y G30 |
| DEV (contraste) | `https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp` (health 200) |
| API Monitoreo | `GET /iot/monitoreo/dashboard` (permiso 33/2) y `GET /iot/monitoreo/historial` (permiso 34/2): 200 en ambos ambientes |
| Contrato Monitoreo | TEST y DEV idénticos. `EstadoSensorSchema` y `LecturaHistoricaSchema` no tienen campos de umbral, rango, niveles ni versión; `EstadoSensorSchema` tampoco tiene especie |
| MQTT | No aplica: la implementación no usa MQTT para esta integración (no existe) |
| Herramientas | Newman 6.2.2 + htmlextra 1.23.1 (existentes); nada instalado; sin Cypress |
| PostgreSQL | No utilizado |

---

## GIT / SHAs

| Repositorio | Rama | SHA | Uso |
| --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-re-evaluacion-M02` | `ff5f6c9f6161e46c94d3d6f325a7d07d80d84aa0` (= `origin/test`) | Lectura de código y única zona escribible |
| `origin/dev` (ref local) | — | `5d39b366` (rc.37) | `git diff --stat HEAD origin/dev -- src` vacío: Monitoreo y RF-17 idénticos en ambas ramas |

---

## ACTOR

| Ambiente | Actor | Rol | Permisos | Nota |
| --- | --- | --- | --- | --- |
| TEST | `administador.dev@gmail.com` | Administrador, `Activo` | r20 `[1,2,3,4]` · dashboard r33 `[2]` · historial r34 `[2,5]` | El paquete lo cita como `admin.dev@gmail.com`; el responsable QA confirmó el correo correcto |
| DEV | `admin.general@pecuaria.co` | Administrador, `Activo` | r20 `[1,2,3,4]` · r33 `[2]` · r34 `[2,5]` | Primero se probó la cuenta común `administador.dev@gmail.com` con la contraseña general: **401** (un solo intento). Se usó el fallback DEV (§14) |

El mismo actor tiene permisos para modificar RF-17 y para leer Monitoreo. No
se usaron Ingeniero ni Productor. No hubo escrituras RF-17.

---

## MECANISMO DE INTEGRACIÓN RF17 → MONITOREO

Flujo real según el código (`origin/dev` = TEST):

`RF-17 UPDATE` (`PATCH /configuracion/umbrales/{id}`) → `modulo9.umbrales_ambientales` y `niveles_alerta_ambientales` + auditoría → **fin**.

Monitoreo trabaja por separado:

- **Dashboard** (`ObtenerDashboardUseCase`): lee
  `modulo3.estados_actuales_sensores.estado_semaforo`, un valor ya almacenado
  por la ingesta y el estado del sensor. Aplica reglas de alertas activas
  (CRÍTICO → ROJO) y la regla de dato desactualizado → GRIS. No consulta
  umbrales RF-17.
- **Historial** (`ConsultarHistorialUseCase`): calcula
  `estado_semaforo_historico` con `UmbralHistoricoPort`, implementado por
  `UmbralHistoricoM09Adapter`: *«Stub: M09 aún no expone umbrales versionados
  con vigencia temporal… Mientras tanto todos los semáforos históricos quedan en
  GRIS»*, `return None`.
- **Alertas** (`GenerarAlertaUseCase`): usa reglas propias de M03
  (`ReglaAlertaRepository`), no umbrales RF-17.
- **Búsqueda transversal:** `git grep "umbrales_ambientales|niveles_alerta_ambientales|UmbralAmbientalRepository"`
  sobre `src/telemetry`, `src/prediction` y `src/shared` no devuelve ningún
  resultado.

No hay caché, evento, cola, MQTT, polling ni configuración versionada entre
ambos módulos. Tampoco hay consistencia eventual que esperar: no existe
propagación.

---

## CONFIGURACIÓN UTILIZADA

| Ambiente | Configuración RF-17 (solo lectura) | Justificación |
| --- | --- | --- |
| TEST | **Umbral 39**: Tilapia + Temperatura del agua, 18.00–27.00, activo | Creado por QA en TC-M09-G22 EvaluacionV2 (TC-M09-47): recurso QA seguro con ID verificable (§45–46) |
| DEV | Umbral 10: Cachama Blanca + Temperatura del agua, 0.00–100.00, activo | Usado solo para comparar lecturas; no se modificó |

## RF17 BEFORE

TEST (`rf17-before-TEST.json`): umbral 39 · especie 10 Tilapia (activa) ·
variable 1 Temperatura del agua (°C) · `valor_min` 18.00 · `valor_max` 27.00 ·
normal 18.00–21.00 · precaución 21.00–24.00 · crítico 24.00–27.00 · activo ·
`fecha_actualizacion` null.

## MONITOREO BEFORE

| Ambiente | Dashboard | Historial (últimos 30 días) |
| --- | --- | --- |
| TEST | 200 · 5 sensores · semáforos `[GRIS]` · sin campos de umbral ni especie | 200 · 5 lecturas · semáforos históricos `[GRIS]` · 0 lecturas con especie · sin campos de umbral |
| DEV | 200 · 5 sensores · `[GRIS]` · sin campos de umbral ni especie | 200 · 1 lectura · `[GRIS]` · 0 con especie · sin campos de umbral |

`RF17_BEFORE == MONITORING_BEFORE: No verificable. Monitoreo no expone rango, niveles ni referencia al umbral, y no permite correlacionar especie ni configuración.`

## MODIFICACIÓN RF-17

**No ejecutada (0 de 2).** Checklist §140:

| # | Condición | Respuesta |
| --- | --- | --- |
| 1–10 | Rama, V1, carpeta, TEST accesible, actor y rol, configuración QA segura (39) y activa, especie activa, variable conocida | Sí |
| 11 | API de monitoreo identificada con configuración efectiva | **No**: las APIs existen pero no exponen ni usan la configuración RF-17 |
| 12 | Correlación configuración ↔ monitoreo demostrable | **No** |
| 13 | RF17_BEFORE capturado | Sí |
| 14 | MONITORING_BEFORE capturado | Sí (sin valores de umbral) |
| 15 | Ambos representan la misma configuración | **No** |
| 16–17 | Nuevos valores válidos y cambio observable | No aplica sin 11, 12 y 15 |

## RF17 AFTER

No aplica: no hubo UPDATE. No se crearon `rf17-update.json` ni
`rf17-after.json` (§113, no fabricar evidencia).

## MONITOREO AFTER

No aplica. No se creó `monitoring-after.json`.

## EVIDENCIA DE USO DE NUEVA CONFIGURACIÓN

No existe un mecanismo de uso de configuración RF-17 en Monitoreo que ejercitar.
Tampoco se puede usar la clasificación como evidencia (§78–86): el semáforo
histórico es siempre GRIS y el del dashboard no depende de RF-17. Un
`PROBE_VALUE` no cambiaría de clasificación por modificar el umbral. No se
generaron mediciones ni `classification-*.json`.

| Aserción principal | Resultado |
| --- | --- |
| `RF17_BEFORE == MONITORING_BEFORE` | No (no verificable) |
| `RF17_UPDATE exitoso` | No ejecutado |
| `RF17_AFTER contiene nuevos valores` | No aplica |
| `MONITORING_AFTER contiene/usa nuevos valores` | No: no existe integración |
| `MONITORING_AFTER != MONITORING_BEFORE` | No aplica |
| `MONITORING_AFTER == RF17_AFTER` | No aplica |

## CONSISTENCIA EVENTUAL / PROPAGACIÓN

No hay contrato de propagación ni ventana contractual: la integración no
existe. No se hizo polling, no se forzaron refrescos ni se limpió caché, y no se
reinició ningún servicio.

---

## COMPARACIÓN V1 VS V2

| Aspecto | V1 | V2 |
| --- | --- | --- |
| Ambiente | TEST | TEST + contraste DEV |
| Actor | Administrador TEST | Administrador TEST (`administador.dev`) / DEV (`admin.general`) |
| Config ID | 11 (discovery) | 39 TEST (QA de G22 V2) · 10 DEV (lectura) |
| RF17 BEFORE | 0.00–100.00 | TEST 18.00–27.00 |
| Monitoring BEFORE | Sin umbral ni especie; GRIS | Igual en TEST y DEV: sin umbral ni especie; GRIS |
| UPDATE | No (0/2) | No (0/2) |
| RF17 AFTER | No aplica | No aplica |
| Monitoring AFTER | No aplica | No aplica |
| Propagación | No verificable | **No implementada** (código y contrato confirman, igual en DEV) |
| Resultado | Rechazado (BLOCKED) | **DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA** |

## COMPARACIÓN TEST VS DEV

| Elemento | TEST | DEV | Interpretación |
| --- | --- | --- | --- |
| RF-17 | Sí | Sí | Desplegado en ambos |
| API Monitoreo | 200, sin configuración RF-17 | 200, sin configuración RF-17 | Mismo contrato y respuestas |
| Config BEFORE | Umbral 39 | Umbral 10 | Solo lectura |
| Config AFTER | No aplica | No aplica | Sin UPDATE |
| Propagación | No existe | No existe | **No hay desfase de despliegue: falta la funcionalidad** |

---

## ORIGEN DEL FALLO

`Producto: Sí (integración RF-17 → Monitoreo no implementada)`

`Automatización: No en el resultado. Hubo un falso positivo de patrón en el primer intento de lectura TEST, corregido antes de concluir (ver EVIDENCIAS)`

`Entorno: No (TEST y DEV responden 200)`

`Bloqueo: No determinante (la ausencia se demuestra en código, contrato y ejecución)`

`Categoría: FLUJO — Flujo / Proceso`

`Equipo: Desarrollo`

`Acción: REPORTAR A DESARROLLO`

Checklist «no implementado» (§145):

| # | Condición | Resultado |
| --- | --- | --- |
| 1 | TEST carece de integración | Sí |
| 2 | DEV también | Sí |
| 3 | Código/contrato DEV confirma ausencia | Sí: stub `return None`, sin lectura de tablas RF-17, esquemas sin umbral |
| 4 | Actor correcto | Sí (Administrador en ambos) |
| 5 | Configuración correcta | Sí (umbral QA 39 activo) |
| 6 | API Monitoreo revisada | Sí (dashboard e historial, contrato y datos) |
| 7 | Infraestructura funciona | Sí |
| 8 | Error QA descartado | Sí: el falso positivo de patrón se corrigió y la conclusión no depende de él |

---

## CATEGORÍA / EQUIPO / ACCIÓN

- **Categoría:** FLUJO — Flujo / Proceso
- **Equipo responsable:** Desarrollo
- **Acción:** REPORTAR A DESARROLLO (actualizar/reabrir INC-M09-33-G32)

## INCIDENCIAS

### INC-M09-33-G32 (#160) — actualizar / reabrir (misma causa, sin duplicar)

| Campo | Valor |
| --- | --- |
| ID | **INC-M09-33-G32** (issue #160); relacionada con INC-M09-32-G31 (#159) |
| Caso | TC-M09-69 (G32) · RF-17 · Monitoreo (M03) |
| Ambiente | TEST (`ff5f6c9`) y DEV (`5d39b366`, rc.37), idénticos |
| Título | El módulo de monitoreo no consume los umbrales RF-17: una modificación de la configuración no se refleja en el semáforo ni en la configuración efectiva de monitoreo |
| Categoría | FLUJO — Flujo / Proceso |
| Severidad | La vigente en el Registro de Errores; no se infiere de «Prioridad Alta» |
| Responsable | Desarrollo |
| Acción | REPORTAR A DESARROLLO — actualizar/reabrir INC-M09-33-G32 |
| Esperado | Tras modificar un umbral RF-17, Monitoreo usa o expone la nueva configuración (rango y niveles) para la misma especie y variable |
| Obtenido | `UmbralHistoricoM09Adapter.obtener_umbral_vigente()` devuelve siempre `None` (semáforo histórico GRIS); el dashboard lee `estado_semaforo` de M03 sin relación con RF-17; ningún componente de monitoreo lee tablas RF-17; las APIs no exponen umbral, rango, niveles, versión ni especie |
| Evidencia | `TC-M09-69-evidencia-TEST.json` / `-DEV.json` (código y aserciones), `monitoring-before-*.json`, `rf17-before-*.json`, `newman-TC-M09-69-v2-TEST.html` y `-DEV.html` |
| Reproducibilidad | Determinista en TEST y DEV |
| Actualización sugerida | «Reevaluación V2 (RUN_ID `G32-REEVAL-V2-20260913-021645`, 2026-09-13): el stub y la falta de integración persisten en rc.37 (TEST = DEV). TC-M09-69 pasa de BLOCKED a DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA. Sigue pendiente el mapeo `tipo_variable ↔ variables_ambientales` y la correlación sensor → activo → especie, además del adaptador real, según la nota de la incidencia.» |

No se creó ningún ticket (Taiga, issue ni PR).

---

## EVIDENCIAS

En `RF-17/TC-M09-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260913-021645/`:

| Archivo | Contenido |
| --- | --- |
| `rf17-before-TEST.json` · `rf17-before-DEV.json` | Configuración RF-17 de referencia (RF17_BEFORE) |
| `monitoring-before-TEST.json` · `monitoring-before-DEV.json` | Dashboard e historial: campos, semáforos, lecturas de la variable y correlación |
| `TC-M09-69-evidencia-TEST.json` · `TC-M09-69-evidencia-DEV.json` | Consolidado saneado: preflight, actor e intentos de login, RF17_BEFORE, MONITORING_BEFORE, correlación, `updateEjecutado: false` y motivo, AFTER/versión/probe/clasificación = null, evidencia de código (TEST) y aserciones Newman |
| `newman/newman-TC-M09-69-v2-TEST.html` · `newman-TC-M09-69-v2-DEV.html` | Newman solo lectura: 6 precondiciones PASS y 4 aserciones de oráculo FAIL en cada ambiente |
| `*-intento1-falso-positivo-regex.*` (TEST) | Primer intento de lectura en TEST, conservado. El patrón de detección de campos de umbral incluía `nivel`, que coincidía con `nivel_bateria_pct` y daba un PASS falso en «el dashboard expone la configuración RF-17». Error de automatización QA sin escrituras: se corrigió el patrón y se repitió la lectura |
| `seguridad-evidencias.json` · `git-final.json` | Escaneo de secretos y estado Git |

No existen `rf17-update.json`, `rf17-after.json`, `monitoring-after.json` ni
`classification-*.json`: esa evidencia no se produjo.

Automatización: `EvaluacionV2/run-newman.cjs`,
`TC-M09-G32-reevaluacion-v2.postman_collection.json` y `README.md`.

---

## SEGURIDAD

- Contraseñas solo por variables de proceso (`TEST_ADMIN_PASSWORD`,
  `DEV_ADMIN_PASSWORD`); tokens en memoria. Reporter con `omitHeaders`, sin
  entorno y omitiendo `token`; HTML y JSON saneados.
- El login fallido de `administador.dev@gmail.com` en DEV fue un único intento,
  lejos del bloqueo por 5 intentos.
- Sin SQL, sin mediciones fabricadas, sin refrescos forzados ni cleanup.
- Detalle del escaneo en `seguridad-evidencias.json`.

---

## GIT FINAL

Detalle en `git-final.json`.

- Backend (`qa/juan-esteban-re-evaluacion-M02`, `ff5f6c9`): `git diff --stat`
  vacío. Todos los archivos nuevos están en
  `tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G32/EvaluacionV2/`.
- Cambios preexistentes ajenos a TC-M09-G32 EvaluacionV2 (carpetas sin
  seguimiento de evaluaciones anteriores): `RF-17/TC-M09-G24/EvaluacionV2/`,
  `G29/EvaluacionV2/`, `G30/EvaluacionV2/`, `RF-24/TC-M09-G77/EvaluacionV2/` y
  `RF-24/TC-M09-G78/EvaluacionV1/`. No se tocaron.
- V1 de G32 intacta. Sin commit, push, pull, merge, rebase, reset, clean,
  stash, checkout, cambio de rama, tag ni PR.

**La ejecución se detiene aquí para revisión humana. No se avanza a otro grupo.**
