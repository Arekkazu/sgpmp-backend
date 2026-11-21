# TC-M09-G30 — REEVALUACIÓN V3

RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental
CU-03 — Configurar Umbrales y Alertas Ambientales por Especie

Caso: TC-M09-64 — Verificar auditoría de creación y modificación de umbrales
Tipo: Auditoría / seguridad
Responsable QA: Juan Esteban
RUN_ID: `G30-REEVAL-V3-20260926-212150`
Fecha: 2026-09-26
Entorno decisorio: **TEST**

---

## 0. DECISIÓN GENERAL

### TC-M09-64: APROBADO

Con **1 POST + 1 PATCH** sobre el mismo recurso (`id_umbral_ambiental = 56`), el mecanismo de
auditoría propio de umbrales registró los dos eventos con correlación inequívoca: recurso,
usuario autenticado, fecha/hora dentro de la ventana medida, operación, valores anteriores y
valores nuevos. El evento CREATE **se conserva** después del UPDATE.

> **El endpoint `GET /auditoria/` global NO forma parte del oráculo de TC-M09-64.**
> La referencia D9–Auditoría del diseño no se interpretó como equivalencia con dicho endpoint.
> En esta corrida no se consultó, no se generó ninguna assertion sobre él y no se registró
> ninguna observación por su contenido.

**Hallazgo colateral, ajeno al oráculo del caso.** El POST y el PATCH respondieron
**HTTP 500 `FALLO_SINCRONIZACION_EDGE`** habiendo persistido correctamente. Pertenece a la
integración Backend–Edge ya trazada en otros grupos. Se reconcilió por GET, sin repetir
ninguna escritura, y no se creó incidencia duplicada.

| Resultado | Estado |
| --- | --- |
| **TC-M09-64** | **APROBADO** |
| INC-M09-30-G30 (auditoría RF-17 no consultable, V1) | **SIN REGRESIÓN** |
| Representación decimal en snapshots auditados | **OBSERVACIÓN RESUELTA** (24/24 valores con dos decimales) |
| Hallazgo colateral HTTP 500 Edge | Documentado; ya trazado; sin incidencia nueva |

---

## 1. MOTIVO DE LA NUEVA CORRIDA V3

La corrida V3 anterior (`G30-REEVAL-V3-20260926-195724`) aplicó un oráculo sobreinterpretado:
además del mecanismo de auditoría por umbral, consultó `GET /auditoria/` global y registró su
ausencia de eventos de RF-17 como observación del caso (OBS-1).

Esta corrida **corrige esa interpretación**: TC-M09-64, RF-17 y CU-03 no exigen que los
eventos de umbrales se expongan en la auditoría global, de modo que ese endpoint queda fuera
del oráculo, del flujo y de las assertions. Sigue siendo la **tercera evaluación (V3)**, con
un nuevo `RUN_ID`; no se crea una V4.

---

## 2. INTERPRETACIÓN DOCUMENTAL CORREGIDA

| Elemento | ¿Pertenece al oráculo de TC-M09-64? |
| --- | --- |
| `GET /configuracion/umbrales/{id_umbral_ambiental}/auditoria` | **Sí — es el oráculo del caso** |
| Evento CREATE con recurso, usuario, fecha, operación y `valores_nuevos` | **Sí** |
| Evento UPDATE con `valores_anteriores` y `valores_nuevos` | **Sí** |
| Conservación del evento CREATE tras el UPDATE | **Sí** |
| `GET /auditoria/` global | **No** |
| Auditoría global del Módulo 1 | **No** |
| Equivalencia D9 ≡ `/auditoria/` | **No** — no hay respaldo documental |
| MQTT, broker, ACK, Raspberry, Edge, propagación a hardware | **No** |

Un error de sincronización Edge durante POST o PATCH se trata **únicamente como hallazgo
colateral**, siempre que pueda demostrarse con seguridad si la escritura persistió.

---

## 3. V1 — solo lectura

Evidencia: `TC-M09-G30/RESULTADOS/run-20260905/` (intacta).

| Aspecto | Valor |
| --- | --- |
| Resultado | **BLOCKED — auditoría no expuesta/no verificable en TEST** |
| Causa | `CONTRACT_REQUIREMENT_MISMATCH`: la auditoría de RF-17 existía en el modelo persistente pero no había endpoint para consultarla por `id_umbral_ambiental` |
| Escrituras | 0 de 2 |
| Incidencia derivada | **INC-M09-30-G30** |

Desarrollo añadió después `GET /configuracion/umbrales/{id_umbral_ambiental}/auditoria`.

---

## 4. V2 — solo lectura

Evidencia: `EvaluacionV2/RESULTADOS/G30-REEVAL-V2-20260913-020215/` (intacta).

| Aspecto | Valor |
| --- | --- |
| Resultado | **APROBADO** |
| Actor | `administador.dev@gmail.com`, Administrador, id 104 |
| Recurso | `id_umbral_ambiental = 44` · especie 39 Bovino · variable 13 Temperatura Corporal |
| CREATE A | 38.00–42.00 · niveles 38.00–39.33 / 39.33–40.66 / 40.66–42.00 · **HTTP 201** · auditoría #7 |
| UPDATE B | 37.00–43.00 · niveles 37.00–39.00 / 39.00–41.00 / 41.00–43.00 · **HTTP 200** · auditoría #8 |
| Newman | 30 assertions · 30 passed (6 / 8 / 5 / 11) |
| Observaciones | D09 global sin eventos de umbrales · formato decimal inconsistente (`"42.0"` vs `"42.00"`) |

El umbral **#44 no se tocó**. Hoy figura con 37.00–43.00 e inactivo, coherente con el UPDATE
de V2 y con una desactivación posterior ajena a QA.

---

## 5. V3 ANTERIOR — solo lectura

La carpeta `EvaluacionV3/` de G30 **ya no existe en el repositorio**: el procedimiento de
limpieza autorizado la eliminó por completo, incluidas la evidencia de
`G30-REEVAL-V3-20260926-195724` y la automatización adaptada. Esta corrida **no la recreó ni
la reconstruyó**; se limitó a crear la carpeta de su propio `RUN_ID`.

De lo observado hoy en TEST se desprende que la limpieza fue **local**, no de datos:

| Dato de la corrida anterior | Estado hoy en TEST |
| --- | --- |
| Umbral `#55` (especie 42 Equino + variable 13) | **Sigue existiendo**, con 37.00–43.00 y activo |

Por eso el discovery de esta corrida descartó la combinación (42, 13) y seleccionó otra libre.
No se borró ni modificó `#55`.

---

## 6. AUTOMATIZACIÓN UTILIZADA/ADAPTADA

**ADAPTADA MÍNIMAMENTE** a partir de `EvaluacionV2/`.

La **colección de V2 se reutiliza sin copiarla ni modificarla**: `EvaluacionV3/run.cjs` la lee
desde `../EvaluacionV2/TC-M09-G30-reevaluacion-v2.postman_collection.json`. Sus 30 assertions,
sus requests y la secuencia de cuatro fases son exactamente los de V2. La colección **no
contiene ninguna assertion sobre `/auditoria/` global, MQTT, ACK ni hardware**: su oráculo ya
era el correcto.

Cambios respecto de V2, todos de infraestructura o forzados por el comportamiento observado:

| # | Cambio | Motivo |
| --- | --- | --- |
| 1 | `G30_REEVAL_V2_RUN_ID` → `G30_REEVAL_V3_RUN_ID`; salida a `EvaluacionV3/RESULTADOS/<RUN_ID>`; nombres `-v2` → `-v3`; metadatos de rama/tipo | V2 escribe a partir de su propio `__dirname` y esa carpeta es inmutable |
| 2 | Colección referenciada desde `../EvaluacionV2/` | Reutilizar sin duplicar ni tocar |
| 3 | **Se retiró del flujo la consulta a `/auditoria/` global** (helper `d09Global` y sus dos llamadas en las fases `plan` y `audit`) | No es el oráculo de TC-M09-64 |
| 4 | Fase `create`: si la respuesta no trae `id_umbral_ambiental`, el recurso se identifica por GET como el **único** registro nuevo de la combinación, libre en PRE | Sin esto no se puede continuar sin repetir la escritura, que está prohibido |
| 5 | Fase `update`: la persistencia se decide comparando por GET valores y los tres niveles del mismo recurso, en lugar de leerlos del cuerpo de la respuesta | En un error el cuerpo no trae el recurso |
| 6 | Snapshot `before-update-v3.json` con verificación de que el recurso sigue en A, y evidencias con los nombres pedidos por el paquete | Trazabilidad exigida |

**Ninguna assertion funcional fue modificada, eliminada ni relajada.** Las 8 que fallaron se
reportan como fallos (§21).

---

## 7. GIT / SHAs

Inspección inicial y final, sólo lectura (`git-final-v3.txt`, `git-final.json`):

| Repositorio | Rama | HEAD | `HEAD...origin/test` | `diff --cached --stat` |
| --- | --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-tercera-evaluacion-M09` | `91f7738667a934a4eaf3db5519a57d7cf4803b0e` | `0  0` | **(vacío)** |
| SGPMP-FRONT-END-PWA | `qa/juan-esteban-tercera-evaluacion-M09` | `ad2b1e59bb872491bae368ae812993a3ded08d63` | `0  0` | **(vacío)** |

Archivos no rastreados preexistentes, de otros grupos, que **no se modificaron ni borraron**:
`tests/.../TC-M09-G29/EvaluacionV3/` en el backend y
`testing/.../TC-M09-G22/EvaluacionV3/` y `.../TC-M09-G28/EvaluacionV3/` en el frontend.

---

## 8. ENTORNO

Backend TEST (HTTPS, ambiente decisorio):
`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`
`GET /health` → **200** · `GET /openapi.json` → **200**. La URL HTTP suministrada devuelve 404
del proxy, como ya documentaba V2.

---

## 9. ACTOR

Descubierto en runtime, **sin asumir el `id_usuario` histórico**:

| Campo | Valor |
| --- | --- |
| Correo | `administador.dev@gmail.com` |
| `id_usuario` | **104** (coincide con V2, pero se verificó en esta corrida) |
| Rol | **Administrador** |
| Estado | **Activo** |
| Permisos recurso 20 (umbrales) | `[1, 2, 3, 4]` — crear, consultar, modificar, desactivar |

Ese `id_usuario` es el expected del campo `id_usuario` en los eventos de auditoría. Evidencia
saneada en `discovery-pre-v3.json`: sin token ni credenciales.

---

## 10. OPENAPI

Contrato leído en runtime desde TEST:

| Operación | Respuestas declaradas |
| --- | --- |
| `POST /configuracion/umbrales` | `201, 401, 403, 404, 409, 422` |
| `PATCH /configuracion/umbrales/{id_umbral_ambiental}` | `200, 401, 403, 404, 412, 422` |
| `GET /configuracion/umbrales/{id_umbral_ambiental}/auditoria` | `200, 401, 403, 404, 422` |

`AuditoriaUmbralResponse` conserva los siete campos necesarios: `id_auditoria_umbral`,
`id_umbral_ambiental`, `id_usuario`, `tipo_operacion`, `valores_anteriores`, `valores_nuevos`,
`fecha_gestion`. **El contrato no cambió** respecto de V2 y permite conservar el mismo oráculo
funcional, así que no procedía detenerse.

Ninguna escritura declara 500 pese a que ambas lo devolvieron: desalineación de contrato ya
trazada, tratada como hallazgo colateral (§21).

---

## 11. DISCOVERY

Sólo GET: especies, variables ambientales y umbrales por especie (`discovery-pre-v3.json`).

| Elemento | Valor |
| --- | --- |
| Especie | **43 — Equina** (activa) |
| Variable | **13 — Temperatura Corporal** (°C) |
| Rango físico | **30 – 50** |
| Umbrales previos de la especie | ninguno |
| Combinación (43, 13) libre antes del POST | **Sí**, confirmado por GET |
| A y B dentro del rango físico | **Sí** |

Combinaciones descartadas por estar ocupadas: **(39 Bovino, 13)** por el umbral #44 de V2 y
**(42 Equino, 13)** por el umbral #55 de la corrida V3 anterior. Ninguno se tocó. Se mantuvo
la misma naturaleza de fixture de V2 —especie terrestre + Temperatura Corporal— y todos los
IDs se descubrieron de nuevo.

---

## 12. PLAN DE EJECUCIÓN

`estado-tc64-v3.json`, creado antes de la primera escritura, con el checklist completo en
verde: TEST accesible, `/health` y `/openapi.json` 200, actor autenticado, activo, rol y
permisos correctos, endpoints CREATE/UPDATE/auditoría identificados, especie activa, variable
real, rango físico conocido, combinación libre, A y B válidas, evidencia V1/V2 intacta e
índice de Git vacío.

Presupuesto: **1 POST + 1 PATCH**, sin reintentos, sin cleanup, sin DELETE, sin SQL.

---

## 13. FIXTURE

| Configuración | valor_min | valor_max | Niveles |
| --- | --- | --- | --- |
| **A (CREATE)** | 38.00 | 42.00 | 38.00–39.33 / 39.33–40.66 / 40.66–42.00 |
| **B (UPDATE)** | 37.00 | 43.00 | 37.00–39.00 / 39.00–41.00 / 41.00–43.00 |

Son los valores históricos de V2: el rango físico 30–50 de Temperatura Corporal los admite, así
que **no hubo que cambiar ningún dato de la prueba**. Lo único distinto respecto de V2 es la
especie (43 Equina en lugar de 39 Bovino) y, respecto de la corrida V3 anterior, también la
especie (43 en lugar de 42), en ambos casos porque la combinación previa está ocupada.

---

## 14. CREATE

| Elemento | Valor |
| --- | --- |
| Ventana | `CREATE_START_UTC` 2026-09-27T02:25:53.186Z → `CREATE_END_UTC` 2026-09-27T02:25:56.896Z |
| POST ejecutados | **1**, sin reintentos |
| HTTP | **500 `FALLO_SINCRONIZACION_EDGE`** (contrato: 201) |
| ¿Persistió? | **Sí** — `id_umbral_ambiental = 56` |
| Identificación | Único registro nuevo de la combinación (43, 13), libre en PRE → inequívoca |
| Valores persistidos | 38.00 – 42.00 con los tres niveles exactos de A, activo, registro único |

Conforme al procedimiento no se repitió el POST: se reconcilió por GET, se verificó que el
recurso coincide con A y se continuó con él. Evidencias: `create-response-sanitized.json` y
`create-error-persistencia-v3.json`.

---

## 15. AUDITORÍA CREATE

`GET /configuracion/umbrales/56/auditoria` → **HTTP 200**, total 1. **8/8 assertions.**
Evidencia: `auditoria-create-v3.json`.

| Campo | Valor | Esperado | ✔ |
| --- | --- | --- | --- |
| `id_auditoria_umbral` | **21** | presente | Sí |
| `id_umbral_ambiental` | **56** | 56 | Sí |
| `id_usuario` | **104** | actor autenticado descubierto | Sí |
| `tipo_operacion` | **CREATE** | CREATE | Sí |
| `fecha_gestion` | 2026-09-27T02:25:55.930967Z | dentro de la ventana del CREATE | Sí |
| `valores_anteriores` | **null** | null / equivalente de creación | Sí |
| `valores_nuevos` | 38.00 / 42.00 + 3 niveles de A, especie 43, variable 13, activo | configuración A | Sí |
| Secretos en la respuesta | ninguno | ninguno | Sí |

---

## 16. SNAPSHOT ANTES DEL UPDATE

`before-update-v3.json`, obtenido por GET inmediatamente antes del PATCH:

| Campo | Valor |
| --- | --- |
| ID | 56 |
| Especie / variable | 43 / 13 |
| valor_min / valor_max | 38.00 / 42.00 |
| Niveles | 38.00–39.33 / 39.33–40.66 / 40.66–42.00 |
| Coincide con configuración A | **Sí** |
| `fecha_actualizacion` vigente | capturada y usada en el PATCH (control de concurrencia) |

El runner se detiene si el recurso ya no coincide con A; no fue el caso.

---

## 17. UPDATE

| Elemento | Valor |
| --- | --- |
| Ventana | `UPDATE_START_UTC` 2026-09-27T02:26:24.963Z → `UPDATE_END_UTC` 2026-09-27T02:26:27.369Z |
| PATCH ejecutados | **1**, sin reintentos |
| HTTP | **500 `FALLO_SINCRONIZACION_EDGE`** (contrato: 200) |
| ¿Persistió? | **Sí** — mismo `id 56`: 37.00 – 43.00 con los tres niveles de B |
| Especie / variable | Sin cambio (43 / 13) |
| Registro | Único de la combinación |

No se repitió el PATCH. Evidencias: `update-response-sanitized.json` y
`update-error-persistencia-v3.json`.

---

## 18. AUDITORÍA FINAL

`GET /configuracion/umbrales/56/auditoria` → **HTTP 200**, total **2**. **11/11 assertions.**
Evidencia: `auditoria-final-v3.json`.

| Campo | Evento CREATE | Evento UPDATE |
| --- | --- | --- |
| `id_auditoria_umbral` | **21** | **22** (distinto) |
| `id_umbral_ambiental` | 56 | 56 |
| `id_usuario` | 104 | 104 |
| `tipo_operacion` | CREATE | UPDATE |
| `fecha_gestion` | 02:25:55.930967Z | 02:26:26.329269Z (posterior) |
| `valores_anteriores` | null | **= A** (38.00/42.00 + niveles de A) |
| `valores_nuevos` | **= A** | **= B** (37.00/43.00 + niveles de B) |

**El evento CREATE sigue presente después del UPDATE**: el historial conserva ambos.

---

## 19. CORRELACIÓN CREATE ↔ UPDATE

| Evento | Resource ID | Usuario | Fecha/hora | Operación | Valores | Resultado |
| --- | --- | --- | --- | --- | --- | --- |
| **#21** | 56 | 104 | 02:25:55.930967Z — dentro de 02:25:53.186Z → 02:25:56.896Z | CREATE | anteriores `null` · nuevos = **A** | **PASS** |
| **#22** | 56 | 104 | 02:26:26.329269Z — dentro de 02:26:24.963Z → 02:26:27.369Z y posterior a #21 | UPDATE | anteriores = **A** · nuevos = **B** | **PASS** |

Comparación **campo a campo** (especie, variable, min, max y los tres niveles), no por
igualdad de cadenas JSON completas, y numérica con `Decimal` para los decimales:

- A enviada == `valores_nuevos` del CREATE → **True**
- A == `valores_anteriores` del UPDATE → **True**
- B enviada == `valores_nuevos` del UPDATE → **True**
- Mismo recurso y mismo usuario en ambos eventos → **True**
- `fecha UPDATE > fecha CREATE` → **True**

**Representación decimal:** los 24 valores decimales de ambos snapshots auditados
(`37.00`, `38.00`, `39.00`, `39.33`, `40.66`, `41.00`, `42.00`, `43.00`) usan **exactamente dos
decimales**. La inconsistencia que V2 observó (`"42.0"` frente a `"42.00"`) **no se reproduce**:
observación **RESUELTA**.

---

## 20. ASSERTIONS

Colección de V2 reutilizada: **30 assertions ejecutadas**, 22 passed, 8 failed.

| Fase | Total | Passed | Failed |
| --- | --- | --- | --- |
| CREATE | 6 | 1 | 5 |
| AUDIT CREATE | 8 | **8** | **0** |
| UPDATE | 5 | 2 | 3 |
| AUDIT FINAL | 11 | **11** | **0** |

**Las 19 assertions del oráculo —auditoría CREATE y auditoría final— pasaron íntegras.** Las 8
fallidas pertenecen a las fases de escritura y derivan todas del HTTP 500 (§21). Ninguna
assertion se añadió sobre `/auditoria/`, M01, MQTT, ACK, Raspberry, broker ni hardware.

---

## 21. HALLAZGOS

### Hallazgo colateral — HTTP 500 `FALLO_SINCRONIZACION_EDGE` en POST y PATCH

| Aspecto | Detalle |
| --- | --- |
| Hecho observado | Ambas escrituras respondieron 500 con `error_code = FALLO_SINCRONIZACION_EDGE` y el mensaje «Configuración guardada en la base de datos, pero falló la actualización de los nodos Edge…» |
| Efecto sobre los datos | **Ninguno**: el umbral se creó y se modificó correctamente, con valores, niveles, especie, variable y estado correctos, y el recurso quedó único |
| Efecto sobre la auditoría | **Ninguno**: los dos eventos se registraron completos y correlacionables |
| Clasificación | `PRODUCT_DEFECT` (integración Backend–Edge) + `CONTRACT_PROBLEM` (el 500 no está declarado) |
| Responsable | Backend |
| Trazabilidad | Ya trazado en otros grupos; **no se crea incidencia duplicada** |
| Acción de QA | Documentado, reconciliado por GET, sin repetir escrituras, sin convertirlo en criterio de rechazo de G30 |

### Assertions fallidas y su causa

| Fase | Assertion | Causa |
| --- | --- | --- |
| create | `CREATE HTTP 201 segun contrato` | El endpoint devolvió 500 |
| create | `ID de umbral creado` | Consecuencia: el cuerpo del 500 no trae `id_umbral_ambiental` |
| create | `Especie y variable del CREATE` | Consecuencia: sin cuerpo de recurso |
| create | `Valores CREATE almacenados` | Consecuencia: ídem |
| create | `Umbral creado persistido una vez con valores CREATE` | Se apoya en el id de la respuesta; el GET posterior sí confirma la persistencia |
| update | `UPDATE HTTP 200 segun contrato` | El endpoint devolvió 500 |
| update | `UPDATE sobre el mismo ID` | Consecuencia: el cuerpo del 500 no trae el recurso |
| update | `Valores UPDATE aplicados` | Consecuencia: ídem; el GET posterior confirma B |

Descartados antes de clasificar: problema de datos (la combinación estaba libre y quedó única),
de automatización (la colección es la de V2, sin cambios), de ambiente (`/health` y
`/openapi.json` 200, login correcto) y de contrato del caso (los tres endpoints y el esquema de
auditoría siguen intactos).

### Sin hallazgos de auditoría

No se observó ninguno de los supuestos de rechazo: hay evento CREATE y evento UPDATE, con
recurso, usuario y operación correctos, fecha correlacionable, snapshots correctos y CREATE
conservado.

---

## 22. INCIDENCIAS

Regla aplicada: **1 grupo = 1 incidencia consolidada**; no se crean duplicadas.

- **INC-M09-30-G30** (auditoría de RF-17 no consultable, origen V1) → **SIN REGRESIÓN**. El
  endpoint de auditoría por umbral existe, responde 200 y registra correctamente CREATE y
  UPDATE con todos los campos. Se sugiere mantenerla como corrección verificada por QA,
  añadiendo la referencia a este RUN_ID.
- **Observación de formato decimal** (V2) → **RESUELTA**; se sugiere cerrarla como verificada.
- **Observación sobre `/auditoria/` global** (registrada en la corrida V3 anterior) → **se
  retira**: no corresponde al oráculo de TC-M09-64 y no debe pedirse a Desarrollo integrar
  RF-17 en ese endpoint a partir de este caso.
- **Hallazgo colateral HTTP 500 Edge** → pertenece a la integración Backend–Edge ya trazada;
  **no se duplica**. G30 aporta que afecta también al `PATCH` y que no altera datos ni auditoría.

---

## 23. SEGURIDAD

- Contraseña únicamente en la variable de proceso `TEST_ADMIN_PASSWORD`; nunca escrita en
  colección, scripts, JSON, Markdown, reportes ni logs.
- Token sólo en memoria: reporter con `omitHeaders`, `showEnvironmentData: false`,
  `showGlobalData: false` y `skipEnvironmentVars: ['token']`; el runner elimina la cabecera
  `Authorization` y las `set-cookie` de los eventos antes de guardarlos, y el saneador redacta
  contraseña, JWT, `Bearer` con valor y `refresh_token`.
- Al no consultarse `/auditoria/` global, la evidencia no contiene IP ni user agent.

**Escaneo final** (`seguridad-evidencias.json`): **20 archivos revisados, 0 comprometidos**.
Sin contraseñas literales, sin JWT, sin `Bearer` con valor y sin cookies con valor.

Nota metodológica: una primera pasada marcó tres scripts por contener las cadenas
`set-cookie` y `refresh_token=` **de su propio saneador**. Se afinó el detector para evaluar
cookies sólo en archivos de evidencia y exigiendo un valor real; se conservó la trazabilidad
del ajuste y no se borró ningún archivo.

---

## 24. GIT FINAL

`git-final-v3.txt` (salida literal de los comandos) y `git-final.json`:

| Repositorio | Rama | HEAD | `status --short` | `diff --stat` | `diff --cached --stat` |
| --- | --- | --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-tercera-evaluacion-M09` | `91f7738667a934a4eaf3db5519a57d7cf4803b0e` | `?? .../TC-M09-G29/EvaluacionV3/`, `?? .../TC-M09-G30/EvaluacionV3/` | (vacío) | **(vacío)** |
| SGPMP-FRONT-END-PWA | `qa/juan-esteban-tercera-evaluacion-M09` | `ad2b1e59bb872491bae368ae812993a3ded08d63` | `?? .../TC-M09-G22/EvaluacionV3/`, `?? .../TC-M09-G28/EvaluacionV3/` | (vacío) | **(vacío)** |

- Código productivo intacto · V1 intacta · V2 intacta · índice de Git intacto.
- La corrida V3 anterior ya había sido eliminada por el procedimiento de limpieza autorizado
  antes de empezar; esta ejecución no la tocó ni la recreó.
- Todos los cambios de G30 están dentro de `TC-M09-G30/EvaluacionV3/`.
- Sin commit, push, merge, rebase, reset, clean, stash, checkout, switch, tag ni deploy.
  **Sin SQL directo. Sin MQTT.**

---

## 25. COMPARACIÓN HISTÓRICA

| Aspecto | V1 | V2 | V3 anterior | **V3 (esta corrida)** | Evolución |
| --- | --- | --- | --- | --- | --- |
| Ambiente | TEST | TEST | TEST | TEST | Sin cambio |
| Actor | — | Admin id 104 | Admin id 104 | **Admin id 104 (verificado)** | Sin cambio |
| Recurso | — | 44 | 55 | **56** | Nuevo por unicidad |
| Especie | — | 39 Bovino | 42 Equino | **43 Equina** | Sólo fixture |
| Variable | — | 13 Temp. Corporal | 13 | **13** | Sin cambio |
| CREATE A | No ejecutado | 38.00–42.00 | 38.00–42.00 | **38.00–42.00** | Sin cambio |
| HTTP CREATE | — | 201 | 500 (persistió) | **500 (persistió)** | Hallazgo colateral |
| Audit CREATE | No consultable | #7 | #19 | **#21** | Funciona |
| UPDATE B | No ejecutado | 37.00–43.00 | 37.00–43.00 | **37.00–43.00** | Sin cambio |
| HTTP UPDATE | — | 200 | 500 (persistió) | **500 (persistió)** | Hallazgo colateral |
| Audit UPDATE | No consultable | #8 | #20 | **#22** | Funciona |
| Valores anteriores / nuevos | — | A / B | A / B | **A / B** | Correcto |
| CREATE conservado | — | Sí | Sí | **Sí** | Correcto |
| Oráculo aplicado | Contrato | Auditoría por umbral (+ D09 como observación) | Auditoría por umbral **+ D09 como observación** | **Sólo auditoría por umbral** | **Corregido** |
| D09 global | — | Observación | OBS-1 registrada | **Fuera del oráculo, no consultado** | **Retirado** |
| Formato decimal | — | Inconsistente | Normalizado | **Normalizado (24/24)** | **Resuelto** |
| Escrituras | 0 | 1 + 1 | 1 + 1 | **1 + 1** | Sin cambio |
| Newman | — | 30/30 | 30: 22 passed | **30: 22 passed** | Oráculo 19/19 |
| Resultado | **BLOCKED** | **APROBADO** | APROBADO | **APROBADO** | Estable |

---

## 26. VEREDICTO FINAL

**TC-M09-64: APROBADO.**

La creación y posterior modificación del mismo umbral generaron eventos de auditoría
correlacionables con el recurso y el actor autenticado.

El evento CREATE registra correctamente usuario, fecha/hora, operación y los valores creados.
El evento UPDATE registra el mismo recurso y usuario, conserva como `valores_anteriores` la
configuración A y registra como `valores_nuevos` la configuración B.

El evento CREATE continúa presente después del UPDATE, demostrando conservación del historial.

La validación se realizó mediante el mecanismo específico de auditoría de umbrales:
`GET /configuracion/umbrales/{id}/auditoria`.

No se utilizó `GET /auditoria/` global como criterio, ya que TC-M09-64, RF-17 y CU-03 no
exigen que los eventos de umbrales sean expuestos mediante ese endpoint.

Durante POST y PATCH se observó un hallazgo colateral de sincronización Edge: ambos
respondieron HTTP 500 `FALLO_SINCRONIZACION_EDGE` habiendo persistido correctamente. Fue
documentado y reconciliado mediante GET sin repetir escrituras. Este comportamiento pertenece
a la integración Backend–Edge ya trazada y no modifica el oráculo de G30.

**INC-M09-30-G30: SIN REGRESIÓN.** Observación de formato decimal: **RESUELTA**.
