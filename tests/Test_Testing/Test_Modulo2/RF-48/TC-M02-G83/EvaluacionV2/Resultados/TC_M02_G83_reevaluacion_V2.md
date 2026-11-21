# REEVALUACIÓN V2 — TC-M02-G83

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| RF / CU | RF-48 — Transferencia interna de activos biológicos / CU10C |
| Subcasos | TC-M02-306 (E-02), TC-M02-307 (E-04), TC-M02-308-A (E-05, destino inexistente), TC-M02-308-B (E-05, destino inactivo) |
| Rama / HEAD | `qa/juan-esteban-re-evaluacion-m02` / `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`. Tras `git fetch origin`, `HEAD...origin/test` = `0 0` |
| Ambiente | TEST compartido |
| Ejecutable | Variante mínima `EvaluacionV2/test_tc_m02_g83_v2.json`: solo cambian las 4 aserciones de mensaje de E-05 (§2) |
| Newman | 1 ejecución · 24 peticiones · **134 aserciones · 132 correctas · 2 fallidas**. Las 2 fallas son **defecto del arnés V2**, no del producto (§2.2) |
| Persistencia de dominio | **NO** (Δ = 0) |
| Auditoría RF-52 | +8 `TRANSFERENCIA_RECHAZADA`, una por POST oficial, con la distribución esperada |
| DEF-G83-01 (directo) | **CORREGIDO**: las 6 ejecuciones afectadas responden 422 |
| OBS-G83-02 (colateral) | **OBSERVACIÓN RESUELTA**: los mensajes distinguen "no existe" de "se encuentra inactiva". No determina el veredicto |
| Regresiones | Ninguna |
| **Veredicto** | ✅ **APROBADO — CORREGIDO / SIN REGRESIÓN** (V1: RECHAZADO) |

---

## 1. Gate

### 1.1 Rama e integridad V1

| Verificación | Resultado |
|---|---|
| `git branch --show-current` | `qa/juan-esteban-re-evaluacion-m02` ✅ |
| `git rev-parse HEAD` | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c` ✅ |
| `git fetch origin` · `HEAD...origin/test` | `origin/test` = `a6220fc8` · `0 0` ✅ (no avanzó) |
| `git status --short` | Sin cambios en archivos versionados. Solo aparecen carpetas `EvaluacionV2/` sin seguimiento |
| `test_tc_m02_g83.json` | `--no-filters` `f717c6eeffa74037e528c8b23ec6823ee5c2a95f` ✅ (blob `HEAD` `9ee04692…` = archivo) |
| `construir_coleccion.cjs` | `--no-filters` `18f0ebccdc0498f6e68c15b3335d9160870aa497` ✅ (blob `HEAD` `4c3d683e…` = archivo). **No se ejecutó** |

V1 (`TC-M02-G83_resultado.md`) se leyó completo. Sus hallazgos formales (§11) son DEF-G83-01, directo, y OBS-G83-02, colateral. No se reevalúan como hallazgos propios de G83: `INFRAESTRUCTURA_ORIGEN_INCORRECTA` (que V1 marcaba como "presunto, no probado"), DEF-G80-02, DEF-G81-01 ni la nota operativa sobre TEST compartido.

### 1.2 Contrato OpenAPI

El SETUP de la colección, con sus aserciones aprobadas, confirma que `POST /activos-biologicos/{id_activo}/transferencias` declara `201, 401, 403, 404, 409, 422, 500`: incluye 404 (TC-306) y 422 (TC-307/308) y no declara 400. Body: `infraestructura_origen_id`, `infraestructura_destino_id`, `fecha_transferencia` y `motivo_transferencia`.

### 1.3 Fixture 99999

BD con `SET default_transaction_read_only = on`: `member_qa` / `sgpmp_test` / `transaction_read_only = on`. Consulta del 2026-09-19 a las 09:19:48 UTC.

| Comprobación | Resultado |
|---|---|
| `SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999` | **0** |
| `SELECT count(*) FROM modulo9.infraestructuras WHERE id_infraestructura = 99999` | **0** (hay 64 infraestructuras, con máximo 81) |
| `GET /activos-biologicos/99999` (Productor / Administrador) | 404 `ACTIVO_NO_ENCONTRADO` ×2 |

### 1.4 Fixture 287

| Activo | Identificador | Estado | `id_infraestructura` | Asociaciones vigentes | Historial | Movimientos |
|---:|---|---|---:|---:|---:|---:|
| 287 | `QAJE-TRF-SINORIG` | ACTIVO | 48 | **0** | 0 | 0 |

La columna `id_infraestructura = 48` no invalida el fixture: E-04 evalúa la asociación vigente en `historial_infraestructura_activo` (`fecha_fin IS NULL`), y hay **0**. `GET /activos-biologicos/287` devuelve 200, ACTIVO, para ambos actores.

### 1.5 Fixture 279

| Activo | Identificador | Estado | Infra | Asociación vigente | Historial | Movimientos |
|---:|---|---|---:|---|---:|---:|
| 279 | `QAJE-CREC-OK` | ACTIVO | 48 | [48] | 1 | 0 |

`GET /activos-biologicos/279` devuelve ACTIVO en la 48 para ambos actores.

### 1.6 Infraestructura 50

| Infra | Nombre | Tipo | `es_activo` | Capacidad | Especie | Finca | Ocupación |
|---:|---|---|---|---:|---|---:|---:|
| **50** | Corral QA JE Inactivo | Corral | **false** | 50 | NULL | 57 | 0 |
| 48 (origen) | Corral QA JE Origen | Corral | true | 1000 | NULL | 57 | 221 |
| 51 (destino válido) | Corral QA JE Destino OK | Corral | true | 200 | 40 | 57 | 1 |

La 50 existe y está inactiva; además es distinta del origen, está en la misma finca que el 279, cumple C1 (especie NULL), C2 (Corral) y C3 (0 + 1 ≤ 50). Solo incumple E-05. `GET /activos-biologicos/279/transferencias/disponibles` devuelve `[47, 51]` para ambos actores, así que no aparecen ni la 50 ni la 99999.

No fue necesario crear ni modificar ningún dato: todos los fixtures de V1 siguen siendo válidos.

**Línea base de dominio**, tomada inmediatamente antes de Newman: `movimientos` 28 filas (máximo 32) · `historial_infraestructura_activo` 367 (máximo 405) · `activos_biologicos` 363 (máximo 452) · bitácora RF48, 31 registros · movimientos hacia 99999 o 50: 0.

---

## 2. Variante V2 del ejecutable

### 2.1 Diff exacto V1 → V2

`EvaluacionV2/test_tc_m02_g83_v2.json` (`--no-filters` `e2a91917e0efb780dfdd41fceef537326208e061`) es una copia byte a byte de V1 con reemplazos literales. `git diff --no-index` da 14 líneas añadidas y 10 eliminadas, todas dentro de las 4 aserciones de mensaje de E-05:

```diff
- pm.test('TC-M02-308-A / <actor>: el mensaje corresponde a destino inexistente o inactivo', () => {
-   pm.expect(txt).to.match(/no existe|no esta activa/);
+ pm.test('TC-M02-308-A / <actor>: el mensaje identifica destino INEXISTENTE y nombra el ID (OBS-G83-02)', () => {
+   pm.expect(txt).to.include('no existe');
    pm.expect(txt).to.include('99999');                                   (sin cambio)
+   pm.expect(txt, 'no debe indicar inactividad').to.not.include('inactiva');

- pm.test('TC-M02-308-B / <actor>: el mensaje corresponde a destino no activo', () => {
-   pm.expect(txt).to.match(/no existe|no esta activa/);
-   pm.expect(txt).to.include('50');
+ pm.test('TC-M02-308-B / <actor>: el mensaje identifica destino INACTIVO y nombra el ID (OBS-G83-02)', () => {
+   pm.expect(txt).to.include('inactiva');
+   pm.expect(txt).to.match(/id 50\b/);        ← ver §2.2
+   pm.expect(txt, 'no debe afirmar que no existe').to.not.include('no existe');
```

(`<actor>` = Productor y Administrador: 4 bloques en total.)

**Justificación.** La aserción V1 `/no existe|no esta activa/` solo aceptaba el mensaje genérico anterior. El producto corregido responde en 308-B *"se encuentra inactiva"*, así que ejecutar V1 tal cual habría producido una falla de arnés precisamente porque OBS-G83-02 fue corregida. **No cambian** los HTTP esperados, los `error_code`, los IDs, los payloads, los actores, los endpoints, la fecha, el origen, el destino ni los criterios de no persistencia.

### 2.2 Defecto de construcción del arnés V2 (2 aserciones fallidas)

- **Qué ocurrió.** Al generar la variante, la secuencia `\b` de la regex `/id 50\b/` se escribió en el JSON sin doble escape. Al decodificarse, se convirtió en el carácter de control *backspace* (`\x08`), y la regex efectiva fue `/id 50<BS>/`, que no puede coincidir con ningún texto. Se verificó en el archivo: los bytes `\b` se decodifican como `'/id 50\x08/'`.
- **Efecto.** Fallaron las 2 aserciones que contenían esa regex: *"TC-M02-308-B / Productor | Administrador: el mensaje identifica destino INACTIVO y nombra el ID (OBS-G83-02)"*. Chai detiene la evaluación en la primera expectativa fallida, así que la siguiente comprobación de esa misma aserción (`not.include('no existe')`) no llegó a evaluarse en el arnés.
- **Clasificación: DEFECTO DEL ARNÉS V2, atribuible a QA.** No es un defecto del producto ni del ambiente.
- **Evaluabilidad.** La ejecución es **evaluable**: el reporte registra íntegros los cuerpos de las 8 respuestas y todas las demás aserciones de 308-B pasaron (HTTP 422, `error_code`, aislamiento y no persistencia). Las tres comprobaciones de esa aserción se verificaron directamente sobre la respuesta registrada de ambos actores, *"La infraestructura con id 50 se encuentra inactiva."*:

| Comprobación prevista | Resultado sobre la respuesta registrada |
|---|---|
| contiene "inactiva" | ✅ (el arnés también la aprobó antes de la regex) |
| nombra el id 50 | ✅ contiene "id 50" |
| no afirma "no existe" | ✅ |

- **Decisión.** Conforme a §25 del paquete, **no se reejecutó Newman**, porque la primera ejecución es objetivamente evaluable. La colección V2 se conserva **tal como se ejecutó**. Para una reejecución futura, la corrección sería escribir `\\\\b` en el generador para que el JSON contenga `\\b`, o usar `/id 50(?!\d)/`.

---

## 3. TC-M02-306 — activo inexistente (E-02)

| Actor | V1 | V2 | Mensaje V2 | Aserciones | Evolución |
|---|---|---|---|---:|---|
| Productor | 404 `ACTIVO_NO_ENCONTRADO` | **404 `ACTIVO_NO_ENCONTRADO`** | *El activo biológico con id 99999 no fue encontrado en el sistema.* | 12/12 | **SIN REGRESIÓN** |
| Administrador | 404 `ACTIVO_NO_ENCONTRADO` | **404 `ACTIVO_NO_ENCONTRADO`** | idéntico | 12/12 | **SIN REGRESIÓN** |

- El 404 es de negocio y no del enrutador.
- No se devolvió `id_movimiento`.
- El GET posterior de 99999 sigue devolviendo 404.

---

## 4. TC-M02-307 — activo sin infraestructura origen (E-04)

| Actor | Activo | V1 | V2 | Mensaje V2 | Aserciones | Evolución |
|---|---:|---|---|---|---:|---|
| Productor | 287 | 400 `SIN_INFRAESTRUCTURA_ORIGEN` | **422 `SIN_INFRAESTRUCTURA_ORIGEN`** | *El activo QAJE-TRF-SINORIG no tiene una infraestructura origen registrada. Asocie el activo a una infraestructura antes de realizar la transferencia.* | 11/11 | **CORREGIDO** |
| Administrador | 287 | 400 `SIN_INFRAESTRUCTURA_ORIGEN` | **422 `SIN_INFRAESTRUCTURA_ORIGEN`** | idéntico | 11/11 | **CORREGIDO** |

La misma regla funcional se aplica ahora con el código correcto. El rechazo no creó ninguna asociación ni movimiento y no cambió el estado del activo (§7).

---

## 5. TC-M02-308-A — destino inexistente (E-05)

| Actor | Activo · origen → destino | V1 | V2 | Mensaje V2 | Aserciones | Evolución |
|---|---|---|---|---|---:|---|
| Productor | 279 · 48 → **99999** | 400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | **422 `INFRAESTRUCTURA_DESTINO_INVALIDA`** · `field = infraestructura_destino_id` | *La infraestructura con id 99999 no existe.* | 10/10 | **CORREGIDO** |
| Administrador | 279 · 48 → **99999** | 400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | **422 `INFRAESTRUCTURA_DESTINO_INVALIDA`** · `field = infraestructura_destino_id` | idéntico | 10/10 | **CORREGIDO** |

La nueva aserción de mensaje pasó: dice "no existe", nombra el 99999 y no menciona "inactiva". No se creó ningún movimiento, historial ni infraestructura 99999.

---

## 6. TC-M02-308-B — destino inactivo (E-05)

| Actor | Activo · origen → destino | V1 | V2 | Mensaje V2 | Aserciones | Evolución |
|---|---|---|---|---|---:|---|
| Productor | 279 · 48 → **50** (inactiva) | 400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | **422 `INFRAESTRUCTURA_DESTINO_INVALIDA`** · `field = infraestructura_destino_id` | *La infraestructura con id 50 se encuentra inactiva.* | 10/11 (la falla es del arnés, §2.2) | **CORREGIDO** |
| Administrador | 279 · 48 → **50** (inactiva) | 400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | **422 `INFRAESTRUCTURA_DESTINO_INVALIDA`** · `field = infraestructura_destino_id` | idéntico | 10/11 (la falla es del arnés, §2.2) | **CORREGIDO** |

Todas las aserciones funcionales pasaron con ambos actores: HTTP 422, `error_code`, aislamiento frente a las demás reglas y no persistencia. El activo 279 no se movió, no se creó movimiento ni historial y la infraestructura 50 **sigue inactiva** (§7).

---

## 7. Persistencia de dominio

Lectura con `SELECT` antes (09:19:48Z) y después (09:21:49Z) de Newman, que se ejecutó de 09:20:55 a 09:21:02Z:

| Métrica | ANTES | DESPUÉS | Δ |
|---|---:|---:|---:|
| `modulo2.movimientos`: filas / máximo | 28 / 32 | 28 / 32 | **0** |
| `historial_infraestructura_activo`: filas / máximo | 367 / 405 | 367 / 405 | **0** |
| `activos_biologicos`: filas / máximo | 363 / 452 | 363 / 452 | **0** |
| Movimientos de 279 / 287 | 0 / 0 | 0 / 0 | **0** |
| Historial de 279 / 287 | 1 / 0 | 1 / 0 | **0** |
| Asociación vigente de 279 | [48] | [48] | — |
| Asociación vigente de 287 | ninguna | **ninguna** | — |
| Ubicación de 279 | 48 | 48 | — |
| Estado de 287 | ACTIVO | ACTIVO | — |
| Activo 99999 | no existe | no existe | — |
| Infraestructura 99999 | no existe | no existe | — |
| Infraestructura 50 `es_activo` | false | **false** | — |
| Movimientos hacia 99999 o 50 | 0 | 0 | **0** |
| Ocupación 48 / 50 / 51 | 221 / 0 / 1 | 221 / 0 / 1 | **0** |

**Ninguna de las 8 peticiones dejó persistencia de dominio.** Los totales de V1 (26 / 255) no se reutilizaron, porque otros casos, entre ellos G81 V2, generaron después movimientos e historiales válidos.

---

## 8. Auditoría RF-52

La bitácora `modulo2.bitacora_auditoria_m02` con `rf_origen='RF48'` pasó de 31 a **39 (+8)**, con exactamente un `TRANSFERENCIA_RECHAZADA / RECHAZADO` por POST oficial:

| Subcaso | Actor (usuario) | `id_activo_biologico` | `error_code` | `id_activo_solicitado` |
|---|---|---|---|---|
| TC-306 | Productor (35) | NULL | `ACTIVO_NO_ENCONTRADO` | 99999 |
| TC-307 | Productor (35) | 287 | `SIN_INFRAESTRUCTURA_ORIGEN` | 287 |
| TC-308-A | Productor (35) | 279 | `INFRAESTRUCTURA_DESTINO_INVALIDA` | 279 |
| TC-308-B | Productor (35) | 279 | `INFRAESTRUCTURA_DESTINO_INVALIDA` | 279 |
| TC-306 | Administrador (1) | NULL | `ACTIVO_NO_ENCONTRADO` | 99999 |
| TC-307 | Administrador (1) | 287 | `SIN_INFRAESTRUCTURA_ORIGEN` | 287 |
| TC-308-A | Administrador (1) | 279 | `INFRAESTRUCTURA_DESTINO_INVALIDA` | 279 |
| TC-308-B | Administrador (1) | 279 | `INFRAESTRUCTURA_DESTINO_INVALIDA` | 279 |

Para el activo inexistente, `id_activo_biologico = NULL` con `id_activo_solicitado = 99999` en `detalle_tecnico` es el comportamiento correcto. Es la trazabilidad de rechazos que exige RF-52, **no persistencia indebida**.

---

## 9. Reevaluación de hallazgos formales

### 9.1 DEF-G83-01 — DIRECTO

- **V1:** E-04 (`SIN_INFRAESTRUCTURA_ORIGEN`) y E-05 (`INFRAESTRUCTURA_DESTINO_INVALIDA`, destino inexistente e inactivo) respondían **HTTP 400**, no declarado en el contrato, en lugar de 422. Afectaba a TC-307, TC-308-A y TC-308-B con ambos actores. Severidad Media, estado Abierto.
- **V2:** las **6 ejecuciones afectadas** (TC-307, TC-308-A y TC-308-B × Productor y Administrador) responden **HTTP 422**, con los `error_code` correctos y sin persistencia de dominio.
- **Evolución: CORREGIDO.** Afecta al veredicto de G83.

### 9.2 OBS-G83-02 — COLATERAL

> Hallazgo colateral de V1. Se reevaluó por trazabilidad, pero no forma parte de los criterios de aceptación de TC-M02-G83 y no determina su veredicto. V1 lo clasificó expresamente como no incumplimiento.

- **V1:** las dos variantes de E-05 compartían el texto *"La infraestructura con id N no existe o no está activa."* Severidad Baja, estado Abierto.
- **V2**, evaluado solo con las respuestas de los POST oficiales, sin peticiones adicionales:
  - 308-A → *"La infraestructura con id 99999 **no existe**."*
  - 308-B → *"La infraestructura con id 50 **se encuentra inactiva**."*

  El mismo resultado se obtuvo con ambos actores. El `error_code` se mantiene (`INFRAESTRUCTURA_DESTINO_INVALIDA`); solo se diferencia el mensaje.
- **Evolución: OBSERVACIÓN RESUELTA.** Impacto en el veredicto: **NO**.

---

## 10. Comparación V1 ↔ V2

| Variante | Actor | V1 | V2 | Evolución |
|---|---|---|---|---|
| TC-M02-306 | Productor | 404 `ACTIVO_NO_ENCONTRADO` | 404 `ACTIVO_NO_ENCONTRADO` | **SIN REGRESIÓN** |
| TC-M02-306 | Administrador | 404 `ACTIVO_NO_ENCONTRADO` | 404 `ACTIVO_NO_ENCONTRADO` | **SIN REGRESIÓN** |
| TC-M02-307 | Productor | 400 `SIN_INFRAESTRUCTURA_ORIGEN` | 422 `SIN_INFRAESTRUCTURA_ORIGEN` | **CORREGIDO** |
| TC-M02-307 | Administrador | 400 `SIN_INFRAESTRUCTURA_ORIGEN` | 422 `SIN_INFRAESTRUCTURA_ORIGEN` | **CORREGIDO** |
| TC-M02-308-A | Productor | 400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | 422 `INFRAESTRUCTURA_DESTINO_INVALIDA` ("no existe") | **CORREGIDO** |
| TC-M02-308-A | Administrador | 400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | 422 `INFRAESTRUCTURA_DESTINO_INVALIDA` ("no existe") | **CORREGIDO** |
| TC-M02-308-B | Productor | 400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | 422 `INFRAESTRUCTURA_DESTINO_INVALIDA` ("se encuentra inactiva") | **CORREGIDO** |
| TC-M02-308-B | Administrador | 400 `INFRAESTRUCTURA_DESTINO_INVALIDA` | 422 `INFRAESTRUCTURA_DESTINO_INVALIDA` ("se encuentra inactiva") | **CORREGIDO** |

| Hallazgo V1 | Relación | V1 | V2 | Evolución | Afecta al veredicto |
|---|---|---|---|---|---|
| DEF-G83-01 | DIRECTO | Abierto (400 en E-04/E-05) | 422 en las 6 ejecuciones | **CORREGIDO** | SÍ |
| OBS-G83-02 | COLATERAL | Abierta (mensaje único y ambiguo) | "no existe" frente a "se encuentra inactiva" | **OBSERVACIÓN RESUELTA** | NO |

| Ejecución | V1 | V2 |
|---|---|---|
| Newman | 24 peticiones · 134 aserciones · 128 correctas / **6 fallidas (producto: HTTP 400)** | 24 peticiones · 134 aserciones · 132 correctas / **2 fallidas (arnés V2, §2.2)** |
| Persistencia de dominio | NO | NO |

---

## 11. Regresiones

No se identificaron regresiones. TC-306 mantiene su comportamiento y las tres variantes que incumplían ahora cumplen. Las 2 aserciones fallidas no reflejan ningún comportamiento del producto (§2.2).

---

## 12. Veredicto final

# ✅ APROBADO — CORREGIDO / SIN REGRESIÓN

- TC-306 = 404 `ACTIVO_NO_ENCONTRADO` ×2 (**SIN REGRESIÓN**)
- TC-307 = 422 `SIN_INFRAESTRUCTURA_ORIGEN` ×2 (**CORREGIDO**)
- TC-308-A = 422 `INFRAESTRUCTURA_DESTINO_INVALIDA` ×2 (**CORREGIDO**)
- TC-308-B = 422 `INFRAESTRUCTURA_DESTINO_INVALIDA` ×2 (**CORREGIDO**)
- Sin persistencia de dominio.
- DEF-G83-01 **CORREGIDO** · OBS-G83-02 **OBSERVACIÓN RESUELTA**, sin impacto en el veredicto.

Evolución del caso: **RECHAZADO (V1) → APROBADO (V2)**.

---

## 13. Integridad

- ✅ **V1 intacta.** `test_tc_m02_g83.json`, `construir_coleccion.cjs` y los tres archivos de `Resultados/` coinciden con `HEAD` y conservan su fecha de modificación (2026-09-12).
- ✅ **`construir_coleccion.cjs` no se ejecutó.** La variante V2 se generó con reemplazos literales sobre una copia de V1.
- ✅ **Newman se ejecutó una sola vez.** Solo se enviaron los 8 POST oficiales, todos rechazados. No hubo POST diagnósticos ni el `curl` de V1: la evidencia oficial fue evaluable.
- ✅ **BD TEST solo en lectura** (`transaction_read_only = on`): únicamente `SELECT`. No se crearon ni modificaron datos, no se borraron asociaciones del 287, no se movió el 279, no se creó el 99999 y no se tocó la infraestructura 50.
- ✅ Llamadas adicionales de solo lectura en el gate: login, `GET /activos-biologicos/99999`, `GET /activos-biologicos/279`, `GET /activos-biologicos/287` y `GET /279/transferencias/disponibles`.
- ✅ **DEV no se usó.** No se modificó código productivo, no se hizo commit, push, merge, rebase ni deploy, y no se crearon tickets.
- ✅ Artefactos V2:
  - `EvaluacionV2/test_tc_m02_g83_v2.json`, conservado tal como se ejecutó;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g83_v2.json`;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g83_v2.html`;
  - este informe.
