# TC-M09-G136 — SEGUNDA EVALUACIÓN

RF-24 v2.0 · Módulo 9 · CU05 — Gestionar Dispositivos IoT, Flujo D · Caso **TC-M09-274**
RUN_ID: **run-20261010-010830** · Ambiente: **LOCAL AISLADO** · Herramienta: **Pytest + PostgreSQL local real + logs del backend**
Newman: **NO APLICA**

---

## DECISIÓN GENERAL

| Elemento | Resultado |
|---|---|
| Variante A — RANGE (valor fuera de rango) | **APROBADO** |
| Variante B — INACTIVE (dispositivo inactivo) | **APROBADO** |
| **TC-M09-274** | **APROBADO** |
| **TC-M09-G136** | **APROBADO** |
| Mecanismo best-effort | **FUNCIONA** (sin regresión) |
| Causa del rechazo anterior | **CORREGIDA** |
| INCIDENCIA REQUERIDA | **NO** |

Con el `INSERT` sobre la tabla de RF-10 realmente denegado al rol de la aplicación, los dos rechazos conservaron su código funcional (400 y 422, nunca 500), **y además** sus mensajes coincidieron literalmente con el flujo alterno de RF-24 v2.0 — que era el único fallo de la primera evaluación. Ninguna calibración se creó, el evento RF-10 no se escribió en ninguno de los dos intentos y quedaron dos constancias observables e independientes del fallo de auditoría.

---

## RESUMEN

| Variante | Esperado | Obtenido | Resultado |
|---|---|---|---|
| RANGE | 400 · `VALOR_FUERA_DE_RANGO` · mensaje del FA · sin persistencia · alerta | HTTP **400**, `VALOR_FUERA_DE_RANGO`, **mensaje literal exacto**, 0 calibraciones, alerta del sensor 1 | **APROBADO** |
| INACTIVE | 422 · `DISPOSITIVO_INACTIVO` · mensaje del FA · sin persistencia · alerta | HTTP **422**, `DISPOSITIVO_INACTIVO`, **mensaje literal exacto**, 0 calibraciones, alerta del sensor 2 | **APROBADO** |

Presupuesto respetado: **2 POST funcionales** (1 por variante), **0 reintentos**, ninguna petición repetida.

---

## BASELINE — PRIMERA EVALUACIÓN

Único baseline oficial: **run-20261007-140122**
Fuente: `tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G136/RESULTADOS/run-20261007-140122/TC-M09-G136_resultado.md`
Commit del baseline: `30ddd72144102a60af006b265a20cb18c1c72c85` — **es baseline, no el código reevaluado**.

Resultado entonces: TC-M09-274 **RECHAZADO**, TC-M09-G136 **RECHAZADO**.

El mecanismo best-effort **ya funcionaba**: ambas variantes conservaron su HTTP, ninguna creó calibraciones, en ninguna se escribió el evento RF-10 y en ambas hubo alerta. El **único fallo era el mensaje**.

| Variante | HTTP | ¿500? | `error_code` | Calibración | Evento RF-10 | Alerta | Único fallo |
|---|---|---|---|---|---|---|---|
| RANGE | 400 | NO | `VALOR_FUERA_DE_RANGO` | NO | NO | SÍ | mensaje |
| INACTIVE | 422 | NO | `DISPOSITIVO_INACTIVO` | NO | NO | SÍ | mensaje |

**Mensaje RANGE en la primera evaluación:**

> El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el estándar de calibración utilizado.

Faltaba el prefijo `Valor fuera de límites:` y sobraba `(permitido 0.0000–45.0000)`.

**Mensaje INACTIVE en la primera evaluación:**

> Solo se pueden calibrar sensores de dispositivos activos.

Texto completamente distinto: sin prefijo, sin el serial del dispositivo y sin la instrucción de activarlo.

---

## LABORATORIO AISLADO

La prueba se ejecutó **exclusivamente en local**. No se tocó TEST, DEV ni MAIN, y **las credenciales de TEST entregadas a QA no se usaron**: el laboratorio tiene identidades locales propias.

| Elemento | Valor |
|---|---|
| Local aislado | **SÍ** |
| Compose project | `sgpmp-g136-v2` |
| Contenedores | `sgpmp-g136-v2-db`, `sgpmp-g136-v2-backend` |
| PostgreSQL | **18.6** (Debian 18.6-1.pgdg13+2), imagen `Dockerfile.postgres` del proyecto |
| Base dedicada | `sgpmp_g136_lab` |
| Volumen | `sgpmp_g136_v2_pgdata` — **exclusivo de esta reevaluación** |
| Puerto BD | `127.0.0.1:55437` → 5432 (solo localhost) |
| Backend | imagen `Dockerfile` real del proyecto, `127.0.0.1:18037` → 8000 (solo localhost) |
| `DATABASE_URL` efectivo del backend | `postgresql://g136_app:[REDACTED]@db:5432/sgpmp_g136_lab` |
| `ENV` | `local` |
| Datos | sembrados por SQL local e idempotente; **nada copiado de TEST** |

Se **reutilizó** el patrón de laboratorio de la primera evaluación (misma imagen, misma base, mismos dos roles, mismo guard, mismo oráculo). Lo único que cambió fueron los **nombres de la instancia** (proyecto, contenedores, volumen y puertos), para que esta reevaluación **no comparta volumen** con el laboratorio de la primera evaluación ni con ningún otro: así la reevaluación no destruye nada previo y el aislamiento es estricto.

---

## GUARD DE SEGURIDAD

El guard corre **antes** de cualquier migración, seed o `REVOKE`, y aborta con `BLOCKED / SAFETY GUARD` si algo apunta a un entorno compartido.

| Comprobación | Valor observado | Veredicto |
|---|---|---|
| `current_database()` | `sgpmp_g136_lab` | coincide con la base dedicada |
| `current_user` | `g136_owner` | rol administrativo local |
| `inet_server_port()` | 5432 (publicado en `127.0.0.1:55437`) | local |
| Host del DSN | `127.0.0.1` | local |
| Host de la API | `127.0.0.1` | local |
| Configuración efectiva del backend | `DATABASE_URL`, `ENV=local`, `ALLOWED_ORIGINS=http://127.0.0.1:18037` | local y apuntando a la base del laboratorio |
| `inmero.co` / `sslip.io` / `back-sigab` / `dokploy` | **ninguna aparición** en DSN, API ni configuración del backend | sin referencias remotas |
| Guard de carpeta | `TC-M09-G136/EvaluacionV2/automation` | autorizado |

**Referencias a TEST/DEV/MAIN: NINGUNA. Guard: PASS.** `STOP_ALL` no se activó, por lo que el `REVOKE` quedó autorizado.

---

## RAMA Y COMMIT

| Elemento | Valor |
|---|---|
| `git branch --show-current` | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` |
| **Commit evaluado** | `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| Fecha del commit | 2026-10-09T17:05:28-05:00 |
| Fecha del RUN | 2026-10-10T06:08:32Z |
| Commit del baseline | `30ddd72144102a60af006b265a20cb18c1c72c85` |
| ¿Se ejecutó el commit del baseline? | **NO** — el test aborta si HEAD coincide con el baseline |
| Divergencia HEAD…origin/test | `0 0` |
| `git diff` / `git diff --cached` | vacíos |
| `git status --short` | solo las ocho carpetas `EvaluacionV2/` sin seguimiento |
| `RESULTADOS/` de la primera evaluación | `(vacío = intacta)` |
| Operaciones git de escritura | **ninguna**: sin `add`, `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, `stash`, `switch` ni `checkout` |

### Migraciones

| Elemento | Valor |
|---|---|
| `alembic current` | `00c60ae92735 (head)` |
| `alembic heads` | `00c60ae92735 (head)` |
| `alembic_version` en la BD | `00c60ae92735` |
| Cabeza coherente con el código actual | **SÍ** (el test aborta si no lo es) |
| Migraciones modificadas para hacer pasar la prueba | **NINGUNA** |

La cabeza avanzó respecto de la primera evaluación (`78f6f579b5ba` → `00c60ae92735`), consistente con que se está reevaluando código posterior.

### Tabla de RF-10 verificada contra el código actual

No se asumió por el baseline. Se leyó el código reevaluado:

| Elemento | Valor |
|---|---|
| Tabla usada en el fault | `modulo1.eventos` |
| Tabla declarada en el código actual | `modulo1.eventos` (`src/identity_access/infrastructure/models/eventos_model.py`) |
| Mecanismo best-effort presente en el código | **SÍ** (`registrar_calibracion_use_case.py`: `except Exception` → `db.rollback()` + `logger.exception("RF-24: no se pudo auditar…")`) |
| Coincide | **SÍ** → el fault injection es válido |

---

## IDENTIDADES DE BD

Dos identidades separadas: es lo que vuelve fiable el fault injection.

| Identidad | Uso | Propiedades |
|---|---|---|
| `g136_owner` | migraciones, seed, `REVOKE`/`GRANT`, consultas administrativas | owner de la base |
| `g136_app` | **`DATABASE_URL` real del backend** | `LOGIN` **sí**, `SUPERUSER` **no**, owner de `modulo1.eventos` **no**, hereda de otro rol **no**, `BYPASSRLS` sí |

| Condición verificada antes del `REVOKE` | Resultado |
|---|---|
| El backend usa realmente `g136_app` | **SÍ** (confirmado en su `DATABASE_URL` efectivo) |
| `g136_app` no es superusuario | **PASS** |
| `g136_app` no es owner de `modulo1.eventos` (owner: `postgres`) | **PASS** |
| `g136_app` no hereda privilegios de otro rol | **PASS** |
| `g136_app` no conserva `INSERT` por otra vía | **PASS** (comprobado empíricamente durante el fault) |

**Sobre `BYPASSRLS`:** se conserva el patrón validado en la primera evaluación. Las políticas RLS de `modulo1` leen `app.current_user_id`, que la aplicación fija **después** de autenticar; sin `BYPASSRLS` el login sería imposible. `BYPASSRLS` afecta políticas de **fila**, no privilegios de **tabla**, y el RUN comprobó empíricamente que el `REVOKE INSERT` sobre `modulo1.eventos` siguió siendo efectivo (`has_table_privilege` → `false`, y el backend recibió `permission denied for table eventos`).

`sgpmp_app` existe como marcador `NOLOGIN` porque una migración del proyecto hace `GRANT … TO sgpmp_app` sin condicional; nadie es miembro suyo, así que no presta privilegios por herencia.

---

## ACTOR LOCAL

| Elemento | Valor |
|---|---|
| Correo | `ingeniero.g136@pecuaria.co` |
| `id_usuario` | 4 |
| Rol | Ingeniero de Campo |
| Estado de cuenta | Activo |
| Credencial | sintética y **exclusiva del laboratorio local**; generada con el value object real del proyecto (`Contrasena.desde_texto_plano`), **sin inventar hashes**, y **no persistida** en informe, evidencia, `pytest.xml`, `backend.log` ni Git |

### Control sin fault (antes del `REVOKE`)

| Comprobación | Resultado |
|---|---|
| Login del Ingeniero local | **HTTP 200 — PASS** |
| `GET /usuarios/me` (rol correcto) | **HTTP 200 — PASS** |
| `GET /configuracion/sensores/1/calibraciones` | **HTTP 200 — PASS** |
| `has_table_privilege('g136_app','modulo1.eventos','INSERT')` antes del fault | **true — PASS** |

**Token obtenido ANTES del `REVOKE`**, porque el login escribe auditoría RF-10 y contaminaría el fault injection. Durante el periodo de fault se reutilizó la misma sesión: **0 logins nuevos**. El control previo fue de **lectura**, para no consumir el caso.

---

## FIXTURES

Sembrados por SQL local idempotente. Solo lo indispensable: autenticación, rol, permisos, finca, área, dispositivo activo, dispositivo inactivo, sensores, asociaciones vigentes y rango TEMPERATURA.

### Fixture RANGE

| Elemento | Valor |
|---|---|
| Dispositivo | **1** — serial `IOT-G136-LAB-ACT` — **ACTIVO** |
| Sensor | **1** — TEMPERATURA — **ACTIVO** |
| Infraestructura | **1** — activa |
| Asociación | **vigente** (`tiene_estado = true`, `fecha_finalizacion = NULL`) |
| Rango | **0.0000 – 45.0000** |
| Valor enviado | **45.0001** = `max + 0.0001`, calculado con `Decimal` sobre el rango sembrado |
| Única invalidez | **VALOR FUERA DE RANGO** |

### Fixture INACTIVE

| Elemento | Valor |
|---|---|
| Dispositivo | **2** — serial `IOT-G136-LAB-INACT` — **INACTIVO** |
| Sensor | **2** — TEMPERATURA — **ACTIVO** |
| Infraestructura | **1** — activa |
| Asociación | **vigente** |
| Valor enviado | **22.5000** — **dentro** del rango (0.0000–45.0000) |
| Única invalidez | **DISPOSITIVO INACTIVO** |

---

## FAULT INJECTION

El fallo lo produce **PostgreSQL real**, no un doble: no hay `DbFake`, repositorios falsos, SQLite, mock del repositorio de eventos ni `monkeypatch` que lance una excepción artificial.

```sql
REVOKE INSERT ON TABLE modulo1.eventos FROM g136_app;   -- único fallo inducido
```

| Elemento | Valor |
|---|---|
| Tabla RF-10 | `modulo1.eventos` (verificada contra el código actual) |
| Rol afectado | `g136_app` — el que realmente usa el backend |
| `INSERT` en `modulo1.eventos` **antes** | **true** |
| `INSERT` en `modulo1.eventos` **durante** | **false** |
| `INSERT` en `modulo1.eventos` **después** | **true** |
| Fault real | **SÍ** |

Alcance estrictamente limitado: **no** se revocó `SELECT` sobre `modulo1.eventos` (se conservó `true`), **no** se revocó `INSERT` sobre `modulo9.calibraciones` (`true`) ni sobre `modulo9.auditorias_calibraciones` (`true`), y el `SELECT` del fixture siguió funcionando. Ninguna otra tabla fue tocada.

El test verificó que el `REVOKE` fuera efectivo **antes** de enviar los POST: si el privilegio hubiera sobrevivido por ownership, superusuario o herencia, el laboratorio se habría declarado inválido y los POST **no** se habrían enviado.

### Estado PRE

| Elemento | Valor |
|---|---|
| Calibraciones del sensor 1 | total **0**, IDs `[]` |
| Calibraciones del sensor 2 | total **0**, IDs `[]` |
| Eventos RF-10 del actor antes del fault | 2 (del login del control; ningún evento de los intentos existe aún porque los POST no habían ocurrido) |
| Marca inicial de la ventana de log | `2026-10-10T06:08:36Z` |

La búsqueda de alertas se limitó a esa ventana: no se contaron logs de arranque, migraciones, seed, login ni ejecuciones anteriores.

---

## RANGE

**Endpoint:** `POST /configuracion/sensores/1/calibrar` · Actor: Ingeniero local · Ejecutado **una** vez, 0 reintentos.

```json
{"modo_calibracion": "SENSOR", "id_dispositivo_iot": 1, "id_infraestructura": 1,
 "valor_referencia": 45.0001, "observaciones": "QA TC-M09-274 RANGE",
 "fecha_calibracion": "2026-10-10T06:08:36.511654+00:00"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | 400 | **400** |
| ¿Se convirtió en 500? | NO | **NO** |
| `error_code` | `VALOR_FUERA_DE_RANGO` | **`VALOR_FUERA_DE_RANGO`** |
| Mensaje | literal del FA | **idéntico, carácter por carácter** |
| `id_calibracion` en la respuesta | ausente | **ausente** |
| Historial del sensor 1 PRE / POST | iguales | **0 / 0**, IDs `[]` / `[]` |
| Calibración creada | NO | **NO** |
| Evento RF-10 escrito en la ventana | NO | **NO** (0 eventos) |
| Alerta observable | SÍ | **SÍ** |

**Mensaje obtenido:**

> Valor fuera de límites: El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA. Verifique el estándar de calibración utilizado.

Comparación **literal estricta** contra el FA de RF-24 v2.0: ya lleva el prefijo `Valor fuera de límites:` y ya **no** incluye `(permitido 0.0000–45.0000)`. El mensaje antiguo habría sido rechazado.

**Alerta correlacionada** (`backend.log`, línea 3):

> `RF-24: no se pudo auditar el rechazo de calibración del sensor 1`

con la causa subyacente en su stacktrace:

> `psycopg2.errors.InsufficientPrivilege: permission denied for table eventos`

La ausencia del evento RF-10 **no es un defecto**: es la condición provocada del caso y demuestra que la escritura de auditoría falló de verdad.

**Resultado: APROBADO** (oráculo completo en `true`: `http_correcto`, `no_es_500`, `error_code_correcto`, `mensaje_fa_correcto`, `sin_calibracion_creada`, `sin_id_calibracion_en_respuesta`, `evento_rf10_no_escrito`, `alerta_observable`).

---

## INACTIVE

Antes de ejecutarla se comprobó que **el fault seguía activo** (`INSERT` → `false`) y que **el dispositivo 2 seguía inactivo** (`es_activo = false`).

**Endpoint:** `POST /configuracion/sensores/2/calibrar` · Ejecutado **una** vez, 0 reintentos.

```json
{"modo_calibracion": "SENSOR", "id_dispositivo_iot": 2, "id_infraestructura": 1,
 "valor_referencia": 22.5, "observaciones": "QA TC-M09-274 INACTIVE",
 "fecha_calibracion": "2026-10-10T06:08:36.574964+00:00"}
```

| Elemento | Esperado | Obtenido |
|---|---|---|
| HTTP | 422 | **422** |
| ¿Se convirtió en 500? | NO | **NO** |
| `error_code` | `DISPOSITIVO_INACTIVO` | **`DISPOSITIVO_INACTIVO`** |
| Mensaje | literal del FA | **idéntico, carácter por carácter** |
| Serial en el mensaje | proviene del fixture | **`IOT-G136-LAB-INACT`**, el del fixture sembrado |
| `id_calibracion` en la respuesta | ausente | **ausente** |
| Historial del sensor 2 PRE / POST | iguales | **0 / 0**, IDs `[]` / `[]` |
| Calibración creada | NO | **NO** |
| Evento RF-10 escrito en la ventana | NO | **NO** (0 eventos) |
| Alerta observable | SÍ | **SÍ** |

**Mensaje obtenido:**

> Operación rechazada: El dispositivo IOT-G136-LAB-INACT está inactivo. Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración.

Ya lleva el prefijo `Operación rechazada:`, nombra el serial real del fixture e incluye la instrucción de activar el dispositivo. El texto genérico de la primera evaluación habría sido rechazado.

**Alerta correlacionada** (`backend.log`, línea 146):

> `RF-24: no se pudo auditar el rechazo de calibración del sensor 2`

con `permission denied for table eventos` en su stacktrace.

**Resultado: APROBADO** (oráculo completo en `true`).

---

## DOS FALLOS DE AUDITORÍA INDEPENDIENTES

| Elemento | Valor |
|---|---|
| Eventos lógicos de alerta esperados | **2** |
| Eventos lógicos de alerta detectados | **2** |
| Distinguibles entre sí | **SÍ** |

| Evento | Sensor | Constancia | `permission denied for table eventos` | Líneas de su excepción |
|---|---|---|---|---|
| 1 | **1** (RANGE) | `RF-24: no se pudo auditar el rechazo de calibración del sensor 1` | **SÍ** | 142 |
| 2 | **2** (INACTIVE) | `RF-24: no se pudo auditar el rechazo de calibración del sensor 2` | **SÍ** | 142 |

Criterio de conteo: las múltiples líneas de una misma excepción se agrupan como **un** evento de alerta; no se cuenta cada línea del stacktrace como alerta independiente. La correlación con su POST se hace por el **sensor que nombra la propia constancia**, que es más fiable que el orden de aparición: una sola entrada genérica no habría valido para ambos intentos.

---

## RESTAURACIÓN DE PRIVILEGIOS

Ejecutada en `finally`: corre **siempre**, aunque Pytest, RANGE, INACTIVE o el propio runner fallen.

```sql
GRANT INSERT ON TABLE modulo1.eventos TO g136_app;
```

| Elemento | Valor |
|---|---|
| `GRANT` ejecutado | **SÍ** (salida: `GRANT`) |
| `INSERT` **antes** | **true** |
| `INSERT` **durante** | **false** |
| `INSERT` **después** | **true** |
| Privilegios restaurados | **SÍ** |
| Resultado de infraestructura | **PASS** |

Se devolvió exactamente el privilegio que el snapshot PRE demostró disponible. Si no se hubiera restaurado, el RUN habría reportado **EJECUCIÓN INVÁLIDA / LABORATORIO NO CERRADO** en lugar de un PASS.

La evidencia (`pytest.xml`, `backend.log`, `evidencia.json`, estados PRE/POST y privilegios antes/durante/después) se capturó y validó **antes** de desmontar el laboratorio.

---

## RESULTADO PYTEST

| Elemento | Valor |
|---|---|
| Tests collected | **1** |
| Passed | **1** |
| Failed | **0** |
| Errors | **0** |
| Skipped | 0 |
| Duration | **4.82 s** |
| Archivo | `pytest.xml` |
| Caso | `…TC-M09-G136.EvaluacionV2.automation.test_g136_v2::test_tc_m09_274_auditoria_best_effort` |

Se ejecutó **únicamente** la prueba de G136 (`pytest test_g136_v2.py --noconftest --junitxml=…`), no la suite del repositorio: ningún fallo ajeno al caso se mezcla con este resultado. Newman: **no aplica**.

---

## CUADRO RANGE VS INACTIVE

| Criterio | RANGE | INACTIVE |
|---|---|---|
| Invalidez intencional | Valor `max + 0.0001` | Dispositivo inactivo |
| Sensor | **1** | **2** |
| Dispositivo | **1** (`IOT-G136-LAB-ACT`) | **2** (`IOT-G136-LAB-INACT`) |
| Valor enviado | 45.0001 | 22.5000 |
| HTTP esperado | 400 | 422 |
| HTTP obtenido | **400** | **422** |
| ¿500? | **NO** | **NO** |
| `error_code` | `VALOR_FUERA_DE_RANGO` | `DISPOSITIVO_INACTIVO` |
| Mensaje exacto | **SÍ** | **SÍ** |
| Calibración creada | **NO** | **NO** |
| Evento RF-10 escrito | **NO** | **NO** |
| Fallo de auditoría real | **SÍ** | **SÍ** |
| Alerta en el log | **SÍ** (sensor 1) | **SÍ** (sensor 2) |
| Privilegio `INSERT` durante | **false** | **false** |
| Resultado | **APROBADO** | **APROBADO** |

---

## COMPARACIÓN PRIMERA VS SEGUNDA EVALUACIÓN

| Dimensión | Primera evaluación | Segunda evaluación | Cambio |
|---|---|---|---|
| RANGE HTTP | 400 | **400** | SIN CAMBIO |
| RANGE ¿500? | NO | **NO** | SIN CAMBIO |
| RANGE mensaje | Incorrecto | **Correcto (literal del FA)** | Incorrecto → Correcto |
| RANGE persistencia | Ninguna | **Ninguna** | SIN CAMBIO |
| RANGE alerta | Sí | **Sí** | SIN CAMBIO |
| INACTIVE HTTP | 422 | **422** | SIN CAMBIO |
| INACTIVE ¿500? | NO | **NO** | SIN CAMBIO |
| INACTIVE mensaje | Incorrecto | **Correcto (literal del FA)** | Incorrecto → Correcto |
| INACTIVE persistencia | Ninguna | **Ninguna** | SIN CAMBIO |
| INACTIVE alerta | Sí | **Sí** | SIN CAMBIO |
| **TC-M09-274** | RECHAZADO | **APROBADO** | RECHAZADO → APROBADO |
| **G136** | RECHAZADO | **APROBADO** | RECHAZADO → APROBADO |

Dimensiones adicionales sin cambio: `error_code` (`VALOR_FUERA_DE_RANGO` y `DISPOSITIVO_INACTIVO`) y ausencia del evento RF-10 en ambas variantes.

### Mensajes, lado a lado

| Variante | Primera evaluación | Segunda evaluación (= esperado del FA) |
|---|---|---|
| RANGE | El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA **(permitido 0.0000–45.0000)**. Verifique el estándar de calibración utilizado. | **Valor fuera de límites:** El ajuste de 45.0001 excede los rangos de seguridad para la variable TEMPERATURA. Verifique el estándar de calibración utilizado. |
| INACTIVE | Solo se pueden calibrar sensores de dispositivos activos. | **Operación rechazada:** El dispositivo **IOT-G136-LAB-INACT** está inactivo. **Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración.** |

| Elemento | Primera | Segunda |
|---|---|---|
| Best-effort | **FUNCIONABA** | **FUNCIONA** (sin regresión) |
| Causa anterior | — | **CORREGIDA** |

---

## EVIDENCIAS

```
TC-M09-G136/
└── EvaluacionV2/
    ├── automation/
    │   ├── test_g136_v2.py
    │   └── docker-compose.g136-v2.yml
    └── RESULTADOS/
        └── run-20261010-010830/
            ├── TC-M09-G136_reevaluacion_V2.md
            ├── evidencia.json
            ├── automation_manifest.json
            ├── pytest.xml
            └── backend.log
```

`evidencia.json` consolida: RUN_ID, git (rama, commit evaluado, fecha, divergencia), entorno local, guard, compose, versión de PostgreSQL, cabeza de Alembic, base, roles, privilegios **antes / durante / después**, verificación de la tabla RF-10 contra el código actual, actor local, control sin fault, fixtures RANGE e INACTIVE, request/response de cada variante, historiales PRE/POST, eventos RF-10 de cada ventana, alertas correlacionadas, comparación primera/segunda, causa raíz, restauración, seguridad y git final.

`automation_manifest.json` registra ruta, función y SHA-256 de los **5** archivos realmente utilizados: el test y el compose de esta reevaluación, el test y el compose de la primera evaluación (reutilizados como base, conservados intactos y no ejecutados en este RUN) y el código del producto leído en solo lectura para verificar la tabla de RF-10. **No se copió ningún script dentro de `RESULTADOS/`.**

`backend.log` (288 líneas) contiene el log del backend **de la ventana del fault injection**, sin modificar los mensajes y sin ocultar el stacktrace relevante, sanitizado de `Authorization`, JWT, contraseñas y DSN con contraseña.

### Seguridad

Escaneo de los artefactos: **limpio**. Hallazgos: **ninguno**. Credenciales en claro: **0**. No quedaron persistidos la contraseña del laboratorio, la del owner, la del app role, la `SECRET_KEY`, ningún JWT, cabecera `Authorization`/`Bearer`, cookie ni DSN con contraseña (el `DATABASE_URL` aparece como `postgresql://g136_app:[REDACTED]@db:5432/sgpmp_g136_lab`). La credencial sintética del laboratorio **no** se persiste en `RESULTADOS/`. El token del Ingeniero vivió solo en memoria del proceso.

---

## INCIDENCIA

**INCIDENCIA REQUERIDA: NO.**

| Elemento | Valor |
|---|---|
| Causa anterior | **CORREGIDA** |
| Best-effort | sigue siendo correcto: el fallo de auditoría no altera el código HTTP ni crea calibraciones |
| Propuesta | **validar y cerrar** la incidencia previa de TC-M09-274 (mensajes del FA en RANGE e INACTIVE) |
| Responsable | n/a |
| Causa raíz (redeterminada, no copiada del baseline) | **Hipótesis A** — 400 y 422 con los mensajes literales del FA y una constancia por intento: la causa del rechazo anterior está corregida y desplegada en el código reevaluado |

Las demás hipótesis se descartan con la evidencia de esta corrida: **B** (códigos correctos pero mensajes antiguos) no se reprodujo — ambos mensajes coinciden literalmente; **C** (regresión del best-effort hacia 500) no se reprodujo — ningún POST devolvió 500; **D** (sin alerta) no aplica — hay dos constancias distinguibles con su `permission denied`; **E** (fault injection inválido) no aplica — `has_table_privilege` fue `false` durante el fault y no se escribió ningún evento RF-10 en ninguna de las dos ventanas.

---

## CONCLUSIÓN

**TC-M09-G136: APROBADO.**

La reevaluación confirma dos cosas distintas. La primera es que el mecanismo **best-effort sigue intacto**: con el `INSERT` sobre `modulo1.eventos` realmente denegado al rol que usa el backend —fallo producido por PostgreSQL, no simulado—, el rechazo por valor fuera de rango siguió siendo HTTP 400 `VALOR_FUERA_DE_RANGO` y el rechazo por dispositivo inactivo siguió siendo HTTP 422 `DISPOSITIVO_INACTIVO`. Ninguno se degradó a 500, ninguno creó calibraciones y en ninguno se escribió el evento RF-10, lo que prueba que la escritura de auditoría falló de verdad; el backend dejó dos constancias observables e independientes, una por intento, cada una con su `permission denied for table eventos`.

La segunda es que el **único fallo de la primera evaluación está corregido**: los dos mensajes funcionales ya corresponden al flujo alterno de RF-24 v2.0, comparados de forma literal y estricta. RANGE ya lleva el prefijo `Valor fuera de límites:` y ya no arrastra el paréntesis con el rango permitido; INACTIVE pasó de un texto genérico a nombrar el serial real del dispositivo e indicar que debe activarse antes de registrar nuevos parámetros de calibración.

Pytest terminó en verde (1 collected, 1 passed, 0 failed, 0 errors), el fault injection fue real y verificado antes de enviar los POST, y el privilegio quedó restaurado (`true → false → true`) con verificación posterior. La prueba corrió íntegramente en un laboratorio local aislado con volumen exclusivo: no se tocó TEST, DEV ni MAIN, no se usaron las credenciales de TEST, no se modificó ninguna migración ni ningún archivo de la primera evaluación, y no se ejecutó ninguna operación git de escritura.
