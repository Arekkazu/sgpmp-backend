# TC-M09-G24 — REEVALUACIÓN V2

RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental
Casos: TC-M09-52 · TC-M09-53 · TC-M09-54 · Herramienta: Newman
Responsable QA: Juan Esteban · RUN_ID: `G24-REEVAL-V2-20260913-012209` · Fecha local: 2026-09-13 · Entorno decisorio: **TEST**

---

## DECISIÓN GENERAL

### REEVALUACIÓN APROBADA — G24 APROBADO

Los tres originales cumplen RF-17 en TEST con un único POST cada uno:

- **TC-M09-52:** un nivel fuera del rango general se rechaza con 400
  `NIVEL_FUERA_DE_RANGO` y no se guarda nada.
- **TC-M09-53:** el solapamiento entre niveles se rechaza con 422
  `SOLAPAMIENTO_NIVELES`, que identifica el intervalo en conflicto, y no se
  guarda nada.
- **TC-M09-54:** una configuración continua y sin ambigüedad se acepta (201,
  id 42) y se guarda con sus tres niveles y fronteras exactas.

El defecto que rechazó el grupo en V1 (HTTP 500 al crear un umbral válido,
`QA-JE-G22-01`) **ya no se reproduce: corrección verificada por QA**.

| Caso | V1 | V2 | Ambiente decisorio | Motivo | Categoría | Equipo | Acción |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-M09-52 | APROBADO | **APROBADO** | TEST | 400 `NIVEL_FUERA_DE_RANGO` («critico (11.0–17.0) cae fuera del rango general [5.0, 14.0]»); sin ID ni persistencia | No aplica | No aplica | Ninguna |
| TC-M09-53 | APROBADO (tras corregir aserción QA 400→422) | **APROBADO** | TEST | 422 `SOLAPAMIENTO_NIVELES` («precaucion termina en 11.0 pero el siguiente comienza en 9.6»); sin ID ni persistencia | No aplica · observación documental HTTP (ver ORÁCULO) | No aplica | Documentar la discrepancia matriz/RF-17 frente al contrato |
| TC-M09-54 | DESAPROBADO — DEFECTO DEL PRODUCTO (500) | **APROBADO** | TEST | 201, id 42, tres niveles continuos persistidos e idénticos en el GET | No aplica | Desarrollo (cierre) | **ACTUALIZAR INCIDENCIA COMO CORRECCIÓN VERIFICADA POR QA** |

> **Observaciones (no afectan al resultado):**
> 1. **Oráculo HTTP de TC-53:** la matriz y RF-17 indican 400; el contrato
>    vigente responde 422. Hay una inconsistencia documental entre RF/matriz y
>    contrato API respecto al código HTTP de solapamiento. Detalle en «ORÁCULO
>    HTTP TC-M09-53».
> 2. **OpenAPI incompleto para TC-52:** `POST /configuracion/umbrales` no declara
>    la respuesta 400 que el backend emite de forma legítima para
>    `NIVEL_FUERA_DE_RANGO` (`ValidationError`). Es un vacío de documentación del
>    contrato (HTTP_COM, Desarrollo). No es un defecto funcional; se informa para
>    que Desarrollo complete el OpenAPI.

---

## RESUMEN V1

Evidencia V1: `RF-17/TC-M09-G24/RESULTADOS/` (solo lectura, intacta). Ejecución
del 2026-09-05 en TEST, actor Administrador. Resultado general **Rechazado**,
arrastrado por un único original.

| Caso | Resultado V1 | HTTP esperado / obtenido | POST | Datos V1 | Persistencia | Detalle |
| --- | --- | --- | --: | --- | --- | --- |
| TC-M09-52 | **APROBADO** | 400 / 400 `NIVEL_FUERA_DE_RANGO` | 1 | Especie 4 Cachama Blanca + variable 9 Temp. Ambiental; general −20..70; critico 40..85 | Ninguna (correcto) | 8/8 aserciones |
| TC-M09-53 | **APROBADO** | 400 (aserción inicial) → 422 / 422 `SOLAPAMIENTO_NIVELES` | 2 | Mismo par; critico 25..70 sobre precaucion 10..40 | Ninguna (correcto) | Intento 1: 7/8 por status. Se corrigió solo la aserción QA (400→422) y el intento 2 cerró 8/8 |
| TC-M09-54 | **DESAPROBADO — DEFECTO DEL PRODUCTO** | 201 / **500 `ERROR_INTERNO`** | 2 | Mismo par; niveles −20..10, 10..40, 40..70 | Ninguna (defecto) | Reproducción de `QA-JE-G22-01` |

Antecedente verificado contra los archivos V1: TC-52 rechazó correctamente,
TC-53 tuvo una expectativa QA desalineada con el contrato (400 frente a 422) y
TC-54 dio error interno con una configuración continua válida. Los tres hechos
se confirman.

**Sobre TC-53 en V1:** el resultado V1 estuvo afectado por una expectativa QA
desalineada con el contrato vigente. V1 no lo registró como defecto del
producto y V2 tampoco lo hace.

Hallazgo UI de V1 no reevaluado aquí: `QA-JE-G24-UI-01` (campos de niveles
superpuestos en el modal «Nuevo umbral ambiental»). G24 V2 es solo API y no
ejecuta UI, así que ese hallazgo conserva el estado que tenga en el Registro de
Errores.

---

## CAUSA DE REEVALUACIÓN

Verificar la corrección del HTTP 500 al crear umbrales válidos (TC-54) y
confirmar que las validaciones de TC-52 y TC-53 siguen vigentes sobre el
despliegue actual. Se ejecutaron los tres originales porque comparten
`_validar_rangos` y el flujo de creación.

La causa del 500 está confirmada por Desarrollo en
`anotaciones/modulo_9/inc_m09_umbrales_500_enum_insertmanyvalues.md`: ENUM
`nivel` con `insertmanyvalues`. Se corrigió con `use_insertmanyvalues=False`
(PR #146), presente en `src/shared/database.py` del backend `ff5f6c9`
(= `origin/test`).

---

## ENTORNOS

| Elemento | Valor |
| --- | --- |
| Entorno decisorio | **TEST** para los tres originales (G24 no usa MQTT) |
| Backend usado | `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| URL suministrada (HTTP) | `http://…/api-sgpmp-test`: `/health` y `/openapi.json` responden **404 del proxy**. Se usó HTTPS, el mismo criterio aplicado y autorizado en G77 y G22 V2; queda registrado en el preflight de cada JSON |
| Preflight por original | `/health` 200 · `/openapi.json` 200 · el contrato contiene `POST /configuracion/umbrales` |
| DEV | **No utilizado**: TEST tiene la funcionalidad completa y los tres originales pasaron |
| Herramientas | Newman 6.2.2 + htmlextra 1.23.1 (instalación global existente); nada instalado |
| Cypress / UI | No ejecutado (fuera del alcance de G24) |
| PostgreSQL | No utilizado; persistencia verificada por API |

---

## GIT / SHAs

| Repositorio | Rama | SHA | Uso |
| --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-re-evaluacion-M02` | `ff5f6c9f6161e46c94d3d6f325a7d07d80d84aa0` (= `origin/test`) | Lectura de contrato y única zona escribible (`TC-M09-G24/EvaluacionV2/`) |

El frontend no se utilizó.

---

## ACTOR

| Elemento | Valor |
| --- | --- |
| Usuario | `administador.dev@gmail.com` (el mismo rol que en V1) |
| Rol (`GET /usuarios/me`) | **Administrador**, cuenta `Activo` |
| Permisos recurso 20 | `[1, 2, 3, 4]` (crear y consultar confirmados en cada ejecución) |
| Fallback Veterinario | No necesario |
| Credenciales | Contraseña solo por variable de proceso; token en memoria |

---

## DISCOVERY

Solo GET, sin POST exploratorios.

- **Contrato leído una vez (código `ff5f6c9` + OpenAPI desplegado):**
  - DTO: `id_especie`, `id_variable_ambiental`, `valor_min < valor_max` y
    exactamente tres niveles `normal`/`precaucion`/`critico`, cada uno con
    `limite_inferior < limite_superior`.
  - `_validar_rangos` aplica las reglas en este orden:
    1. FA-04, límites físicos de `valor_min`/`valor_max`: `RANGO_FISICO_INVALIDO`, 400.
    2. FA-08, cada nivel dentro de `[valor_min, valor_max]`: `NIVEL_FUERA_DE_RANGO`, `ValidationError`, **400**.
    3. FA-05, el primer nivel debe empezar en `valor_min`, el último terminar en
       `valor_max` y cada `superior_i` coincidir exactamente con
       `inferior_{i+1}`: `SOLAPAMIENTO_NIVELES`, `BusinessRuleError`, **422**.
       La misma regla detecta huecos y solapamientos.
  - Continuidad: las fronteras son compartidas y se comparan por igualdad
    decimal exacta; no hay semántica abierta/cerrada adicional.
- **Mapa especie-variable:** 11 especies activas × 16 variables = 176
  combinaciones; 15 ocupadas (cualquier umbral, activo o inactivo) y 161
  libres. El mapa completo está en `plan-v2.json` (`mapaCombinaciones`).
- **Selección:** especie **3 Camarón Blanco** (activa) + variable **3 Oxígeno
  disuelto** (mg/L, rango físico **0–20**), combinación libre. Antes de cada
  POST se volvió a comprobar por GET que la especie seguía activa, la variable
  publicada y la combinación libre. No se reutilizaron los datos de la matriz
  (35–40 y similares) ni los de V1 (especie 4, variable 9, −20..70).
- **Puntos** (fracciones del rango físico, decimales exactos): a=5.00,
  b=8.00, e=9.60, c=11.00, d=14.00, g=17.00. Rango general [a, d] = 5.00–14.00
  en los tres originales.

| Caso | Especie | Variable | General Min | General Max | Tipo escenario | Persistió |
| --- | --- | --- | --: | --: | --- | --- |
| TC52 | 3 Camarón Blanco | 3 Oxígeno disuelto | 5.00 | 14.00 | Fuera de rango | No (esperado No) |
| TC53 | 3 Camarón Blanco | 3 Oxígeno disuelto | 5.00 | 14.00 | Solapamiento | No (esperado No) |
| TC54 | 3 Camarón Blanco | 3 Oxígeno disuelto | 5.00 | 14.00 | Continuo válido | **Sí**, id 42 (esperado Sí) |

| Caso | Normal | Precaución | Crítico | Dentro del general | Solapamiento | Huecos |
| --- | --- | --- | --- | --- | --- | --- |
| TC52 | 5.00–8.00 | 8.00–11.00 | 11.00–**17.00** | **No** (solo crítico: 17.00 > 14.00) | No | No |
| TC53 | 5.00–8.00 | 8.00–11.00 | **9.60**–14.00 | Sí | **Sí** — precaución/crítico [9.60, 11.00] | No |
| TC54 | 5.00–8.00 | 8.00–11.00 | 11.00–14.00 | Sí | No | No |

El análisis de cada payload se hizo con aritmética BigInt y está en
`plan-v2.json` y en cada JSON de caso (`analisisPayload`).

---

## TC-M09-52

**APROBADO** · TEST · 1 POST · combinación libre antes y después.

| Checklist (§135 / §138) | Resultado |
| --- | --- |
| Rama, V1 revisada, actor autorizado | Sí |
| Especie activa / variable real / combinación libre | Sí / Sí / Sí |
| Rango físico conocido y rango general válido | 0–20; 5.00 < 14.00 dentro del físico |
| Única invalidez = nivel fuera de rango | Sí: solo `critico` termina en 17.00; sin solapamientos ni huecos internos |
| Payload contractual | Sí (DTO, nombres, `inferior < superior`) |
| HTTP | **400** (oráculo 400) |
| Motivo | `NIVEL_FUERA_DE_RANGO` — «El nivel 'critico' (11.0–17.0) cae fuera del rango general [5.0, 14.0].» No es un 400 de DTO ni de rango físico |
| Sin ID / sin estado de éxito | Sí |
| Persistencia | GET: IDs [7, 41, 9, 8] antes y después; 0 registros de la variable 3 |
| Newman | 8 aserciones, 0 fallidas |

## TC-M09-53

**APROBADO** · TEST · 1 POST · combinación libre antes y después.

| Checklist (§136 / §139) | Resultado |
| --- | --- |
| Combinación libre | Sí (revalidada tras TC-52) |
| Todos los niveles dentro del general | Sí |
| Solapamiento real y único | Sí — precaución 8.00–11.00 y crítico 9.60–14.00 comparten [9.60, 11.00] |
| Sin otra invalidez | Sí: empieza en `valor_min`, termina en `valor_max`, sin huecos, dentro del físico |
| Oráculo HTTP resuelto antes del POST | Sí — **422** (ver ORÁCULO) |
| HTTP | **422** |
| Motivo | `SOLAPAMIENTO_NIVELES` — «Los niveles de alerta deben ser contiguos sin huecos ni solapamientos. El nivel 'precaucion' termina en 11.0 pero el siguiente comienza en 9.6.» |
| Sin ID / sin persistencia | Sí; GET con IDs [7, 41, 9, 8], 0 registros de la variable 3 |
| Newman | 8 aserciones, 0 fallidas |

## TC-M09-54

**APROBADO** · TEST · 1 POST.

| Checklist (§137 / §140) | Resultado |
| --- | --- |
| Especie activa / combinación libre | Sí / Sí (revalidada tras TC-53) |
| Rango general y límites físicos válidos | 5.00–14.00 dentro de 0–20 |
| Niveles dentro del rango, sin solapamiento ni huecos | Sí / Sí / Sí |
| Transiciones conformes al contrato | `normal.sup = precaucion.inf = 8.00`, `precaucion.sup = critico.inf = 11.00`, `normal.inf = valor_min`, `critico.sup = valor_max` |
| HTTP | **201** |
| ID | **42** |
| Respuesta | Especie 3, variable 3, `es_activo` true, `valor_min` 5.00, `valor_max` 14.00, tres niveles idénticos a los enviados |
| GET posterior | Registro 42 presente exactamente una vez, con valores, niveles y continuidad persistidos; previos 7, 8, 9 y 41 conservados |
| Newman | 15 aserciones (POST + GET), 0 fallidas |

El umbral 42 se conserva en TEST como evidencia V2.

---

## PERSISTENCIA

| Momento | Especie 3 — IDs | Registros de Oxígeno disuelto (var. 3) |
| --- | --- | --: |
| Antes de TC-52 | 7, 41, 9, 8 | 0 |
| Después de TC-52 | 7, 41, 9, 8 | 0 |
| Después de TC-53 | 7, 41, 9, 8 | 0 |
| Después de TC-54 | 7, 41, **42**, 9, 8 | 1 (id 42) |
| Verificación final (`verificacion-final-readonly.json`) | 7, 41, 42, 9, 8 | 1 — idéntico al creado, continuidad `true` |

Ningún negativo persistió (`STOP_COMBINACION` falso en los tres). No se borró,
editó ni desactivó ningún umbral.

---

## ORÁCULO HTTP TC-M09-53

| Fuente | HTTP para solapamiento |
| --- | --- |
| Matriz | HTTP 400 |
| RF-17 | HTTP 400 |
| V1 | **422** real; la aserción QA de 400 estaba desalineada con el contrato y se corrigió (400→422) sin atribuir defecto al producto |
| Contrato/OpenAPI V2 | Código: `SOLAPAMIENTO_NIVELES` se lanza como `BusinessRuleError`, que `src/shared/errors.py` mapea a **422**. OpenAPI desplegado en TEST para `POST /configuracion/umbrales`: `201, 401, 403, 404, 409, 422`, sin 400 |
| **HTTP utilizado como oráculo** | **422** |

**Justificación:** el contrato vigente (código desplegado y OpenAPI) es la
autoridad técnica verificable y coincide con lo observado en V1. Esperar 400
generaría un falso defecto por una aserción desactualizada. Criterio
funcional: el sistema rechaza, identifica el solapamiento y no persiste, y así
ocurrió.

**Inconsistencia documental:** existe una inconsistencia entre RF/matriz y el
contrato API respecto al código HTTP de solapamiento. Se deja registrada para
que el responsable de la matriz o de RF-17 decida si actualiza la documentación
(400→422). No se modificó RF, matriz ni código.

Nota relacionada con TC-52: su 400 coincide con matriz, RF-17 y código
(`ValidationError`), pero el OpenAPI no lo declara. Es la observación 2 de la
decisión general.

---

## COMPARACIÓN V1 VS V2

| Caso | V1 | V2 | HTTP V1 | HTTP V2 | Persistencia V1 | Persistencia V2 |
| --- | --- | --- | --- | --- | --- | --- |
| TC52 | APROBADO | APROBADO | 400 `NIVEL_FUERA_DE_RANGO` | 400 `NIVEL_FUERA_DE_RANGO` | No (correcto) | No (correcto) |
| TC53 | APROBADO (aserción QA corregida en el intento 2) | APROBADO (1 intento; oráculo resuelto de antemano) | 422 (esperado 400→422) | 422 `SOLAPAMIENTO_NIVELES` | No (correcto) | No (correcto) |
| TC54 | DESAPROBADO — defecto (500) | **APROBADO** | 500 `ERROR_INTERNO` ×2 | **201**, id 42 | No (defecto) | **Sí**, verificada |

| Aspecto | V1 | V2 |
| --- | --- | --- |
| Datos | Especie 4 Cachama Blanca + var. 9 Temperatura Ambiental, general −20..70 | Especie 3 Camarón Blanco + var. 3 Oxígeno disuelto, general 5.00..14.00 |
| POST | 5 (1 + 2 + 2) | 3 (1 + 1 + 1) |
| Resultado del grupo | Rechazado | **APROBADO** |

---

## COMPARACIÓN TEST VS DEV

DEV no se utilizó. La checklist de fallback (§141) no se activó: TEST tiene
endpoint, DTO y reglas desplegados, y los tres originales se decidieron allí
con PASS.

---

## ORIGEN DE FALLOS

No hay originales no aprobados en V2.

| Hallazgo | Producto | Automatización | Entorno | Bloqueo | Estado |
| --- | --- | --- | --- | --- | --- |
| HTTP 500 al crear umbral válido (V1, TC-54) | Sí | No | No | No | **Corregido y verificado en V2** |
| Aserción 400 en TC-53 (V1) | No | Sí | No | No | Corregido en V1; V2 lo resolvió antes de ejecutar |
| HTTP del solapamiento distinto en RF/matriz y contrato | No (documental) | No | No | No | Observación |
| OpenAPI sin respuesta 400 declarada | Documentación de contrato | No | No | No | Observación a Desarrollo |

---

## CATEGORÍA / EQUIPO / ACCIÓN

| Hallazgo | Categoría | Equipo | Acción |
| --- | --- | --- | --- |
| TC-54: 500 al crear umbral válido (V1) | FLUJO | Desarrollo | **ACTUALIZAR INCIDENCIA COMO CORRECCIÓN VERIFICADA POR QA** |
| Observación: HTTP de solapamiento 400 (RF/matriz) frente a 422 (contrato) | Documental | Responsable de matriz/RF-17 | Documentar y revisar la documentación; no es defecto del producto |
| Observación: OpenAPI no declara 400 en `POST /configuracion/umbrales` | HTTP_COM — HTTP / Comunicación | Desarrollo | Informar a Desarrollo para completar el contrato OpenAPI; no afecta al resultado |

---

## INCIDENCIAS

### QA-JE-G22-01 / INC-M09-27-G24 — actualizar como corregida/verificada

- **Identificación:** V1 lo registró como reproducción de `QA-JE-G22-01`.
  Desarrollo lo documenta como el mismo defecto que INC-M09-27-G24,
  INC-M09-26-G28 e INC-M09-31-G22 (issues #148, #149 y #158), con causa raíz
  confirmada. No se crea incidencia nueva.
- **Severidad:** la vigente en el Registro de Errores (V1 la sugirió Alta); QA
  no la reevalúa.
- **Texto sugerido:** «Reevaluación V2 de TC-M09-G24 (RUN_ID
  `G24-REEVAL-V2-20260913-012209`, TEST, 2026-09-13): `POST
  /configuracion/umbrales` con niveles continuos válidos (Camarón Blanco +
  Oxígeno disuelto, 5.00–14.00; 5.00–8.00 / 8.00–11.00 / 11.00–14.00) devuelve
  201, id 42, y persiste con continuidad exacta verificada por GET. El HTTP 500
  `ERROR_INTERNO` ya no se reproduce. Corrección verificada por QA.»
- Coherente con la verificación de G22 V2 (ids 38–41, mismo endpoint).

### Observaciones sin incidencia de producto

- Discrepancia documental 400/422 en TC-53: sin ID; se deja constancia para la
  documentación.
- OpenAPI sin 400 declarado: si Desarrollo decide registrarlo, `ID pendiente de
  asignación según Registro de Errores vigente`; severidad pendiente de validar.

No se creó ningún ticket (Taiga, issue ni PR).

---

## EVIDENCIAS

En `RF-17/TC-M09-G24/EvaluacionV2/RESULTADOS/G24-REEVAL-V2-20260913-012209/`:

| Archivo | Contenido |
| --- | --- |
| `plan-v2.json` | Preflight, actor, oráculos, mapa especie-variable completo, selección, payloads, análisis matemático y checklists previos |
| `TC-M09-52-v2.json` · `TC-M09-53-v2.json` · `TC-M09-54-v2.json` | Por original: ambiente, actor, especie, variable, límites físicos, rango general, niveles, endpoint, payload, HTTP, error code, ID, GET posterior, persistencia y resultado |
| `newman/newman-TC-M09-52-v2.html` · `-53-v2.html` · `-54-v2.html` | Reportes htmlextra reales |
| `verificacion-final-readonly.json` | GET final de cierre |
| `seguridad-evidencias.json` · `git-final.json` | Escaneo de secretos y estado Git |

No hubo segundo intento en ningún original, así que no existen archivos
`-intento2`. Automatización en `EvaluacionV2/`: `helpers.cjs`, `plan.cjs`,
`run-newman.cjs`, `verificar-cierre.cjs`,
`TC-M09-G24-reevaluacion-v2.postman_collection.json` (copia de la colección V1
ya corregida) y `README.md`.

---

## SEGURIDAD

- Contraseña solo por variable de proceso (`TEST_ADMIN_PASSWORD`); token en
  memoria. Reporter con `omitHeaders`, sin datos de entorno y omitiendo la
  variable `token`; HTML y JSON saneados al escribirse.
- Escaneo final de `EvaluacionV2/`: detalle en `seguridad-evidencias.json`.
- Sin SQL, sin PostgreSQL y sin cambios de datos salvo el umbral 42, creado por
  el flujo bajo prueba de TC-54.

---

## GIT FINAL

Detalle en `git-final.json`.

- Backend (`qa/juan-esteban-re-evaluacion-M02`, `ff5f6c9`): `git diff --stat`
  vacío. Todos los archivos nuevos de esta reevaluación están en
  `tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/EvaluacionV2/`.
- Cambios preexistentes ajenos a G24 EvaluacionV2 (carpetas sin seguimiento de
  evaluaciones anteriores): `RF-24/TC-M09-G77/EvaluacionV2/` y
  `RF-24/TC-M09-G78/EvaluacionV1/`. No se tocaron.
- V1 de G24 intacta. Sin commit, push, pull, merge, rebase, reset, clean,
  stash, checkout, cambio de rama, tag ni PR. Sin cambios en código funcional,
  infraestructura ni dependencias. Sin Cypress.

**Resultado final: REEVALUACIÓN APROBADA — TC-M09-52, TC-M09-53 y TC-M09-54 APROBADOS. La ejecución se detiene aquí para revisión humana. No se avanza a otro grupo.**
