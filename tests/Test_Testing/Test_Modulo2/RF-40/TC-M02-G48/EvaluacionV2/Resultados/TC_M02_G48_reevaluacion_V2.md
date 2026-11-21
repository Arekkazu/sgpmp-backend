# REEVALUACIÓN V2 — TC-M02-G48

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| RF | RF-40 — Registro de eventos de crecimiento |
| Caso | TC-M02-G48 (TC-M02-304 activo inexistente · TC-M02-305 activo no ACTIVO) |
| Ambiente | TEST |
| Rama | `qa/juan-esteban-re-evaluacion-m02` (nombre devuelto por `git branch --show-current`) |
| HEAD V2 | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c` — *Merge branch 'dev' of https://github.com/Arekkazu/sgpmp-backend into test* (= `origin/test`; ver §2.1) |
| Ejecutable | `test_tc_m02_g48.json` de V1 **sin modificar**. `construir_coleccion.cjs` no se ejecutó |
| Hash V1/V2 | `71790cf24858cebff5d51a27d053d185a2a0b672`, igual antes y después de ejecutar y al blob de `HEAD` |
| Newman | 1 iteración · 25 peticiones · **88 aserciones · 1 fallo**. El fallo es la aserción diagnóstica de OpenAPI, no funcional (§4) |
| TC-M02-304 | ✅ **APROBADO**: 3/3 → `404 ACTIVO_NO_ENCONTRADO` |
| TC-M02-305 | ✅ **APROBADO**: 3/3 → `409 ESTADO_NO_PERMITE_EVENTOS` |
| Persistencia indebida | **NO**. Δ = 0 en eventos, activos y estados |
| Observación formal V1 | OBS-G48-01 (§10; V1 propone ID OBS-G48-03): **OBSERVACIÓN RESUELTA** a nivel de código; no se verificó funcionalmente (§8) |
| Regresiones | Ninguna |

**Veredicto V2: ✅ APROBADO — SIN REGRESIÓN.**

---

## 1. Trazabilidad V1

Informe: `TC-M02-G48/Resultados/TC-M02-G48_resultado.md`, leído completo. Su hash `5bd605b3…` coincide con el blob de `HEAD`.

| Elemento | V1 |
|---|---|
| Veredicto | **APROBADO** |
| TC-M02-304 / TC-M02-305 | APROBADO / APROBADO |
| Actores | Productor (usuario 35), Veterinario (usuario 3, `juan.carlos.qa133@sgpmp-test.com`), Ingeniero de campo (usuario 4) |
| Fixtures | 304: ID inexistente `99999`. 305: 288 `QAJE-CREC-CERRADO` / 329 `QAJE-RF40-CERRADO-VET` / 336 `QAJE-RF40-CERRADO-ING`, todos INDIVIDUAL y CERRADO |
| Resultados | 304: 404 `ACTIVO_NO_ENCONTRADO` ×3. 305: 409 `ESTADO_NO_PERMITE_EVENTOS` ×3 |
| Newman | 25 peticiones · 88 aserciones · 0 fallos · 6 peticiones oficiales (reporte JSON: 2026-09-10 09:36 UTC) |
| Persistencia | Δ = 0 (eventos 106 / máx. 240; activos 259) |
| Diagnóstico | No fue necesario |
| HEAD V1 | `41369ea4ab3948eacb1ab9b2d0549310e285eeae` (rama `qa/juan-esteban-m02`) |
| Observación formal (§10) | **OBS-G48-01** — *El POST de crecimiento no aplica el filtro de alcance por finca que sí aplica la consulta* (ID sugerido: OBS-G48-03). No verificada por QA, basada en lectura de código y fuera del alcance de G48 |
| Contexto no formal | §2.1: el contrato no declaraba 409 (V1 lo llama OBS-G48-02). §3.3: la credencial documentada del Veterinario estaba desactualizada (V1 también la llama OBS-G48-01). Ninguna de las dos es una entrada formal de §10 |

La nomenclatura de V1 es inconsistente: usa `OBS-G48-01` para dos cosas distintas y propone `OBS-G48-03` en §10. No se renombra: la observación formal se cita como **OBS-G48-01 (§10; V1 propone ID OBS-G48-03)**.

---

## 2. Gate V2

### 2.1 Rama y HEAD

`git branch --show-current` devuelve `qa/juan-esteban-re-evaluacion-m02`. Sin cambios en archivos versionados; solo hay carpetas `EvaluacionV2/` sin seguimiento.

**HEAD V2 = `a6220fc8`.** Según `git reflog`, la rama avanzó de `7e1174d1` a `a6220fc8` por `merge origin/test: Fast-forward` el 2026-09-19 a las 02:27:02 −05:00 (07:27 UTC), antes de este gate. El agente no hizo esa operación; fue una acción de QA sobre el repositorio local. Desde ese momento la rama de reevaluación contiene exactamente el código de `origin/test`. El nombre de la rama es el esperado, así que la reevaluación continuó.

### 2.2 Base de datos y API

Gate realizado el 2026-09-19 a las 07:31:55 UTC. BD con `SET default_transaction_read_only = on`: `member_qa` / `sgpmp_test` / `transaction_read_only = on`. Solo `SELECT`.

**TC-M02-304**

| Verificación | Resultado |
|---|---|
| `SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999` | **0** |
| Eventos asociados a 99999 | 0 |
| `GET /activos-biologicos/99999` (Productor / Veterinario / Ingeniero) | 404 `ACTIVO_NO_ENCONTRADO` ×3 |
| ¿Precondición válida? | **SÍ**; se usó el ID oficial sin sustituirlo |

**TC-M02-305**

| Activo | Identificador | Tipo | Estado (`id_estado`) | Finca → propietario | Actor | `GET` del actor | Eventos de crecimiento |
|---:|---|---|---|---|---|---|---:|
| 288 | `QAJE-CREC-CERRADO` | INDIVIDUAL | CERRADO (5) | 57 → usuario 35 | Productor | 200, `CERRADO` | 0 |
| 329 | `QAJE-RF40-CERRADO-VET` | INDIVIDUAL | CERRADO (5) | 64 → usuario 3 | Veterinario | 200, `CERRADO` | 0 |
| 336 | `QAJE-RF40-CERRADO-ING` | INDIVIDUAL | CERRADO (5) | 65 → usuario 4 | Ingeniero de campo | 200, `CERRADO` | 0 |

Los tres fixtures existen, están CERRADO, son INDIVIDUAL y quedan dentro del alcance legítimo de su actor: finca propia, GET 200, sin 403 ni 404. **La precondición es válida.**

---

## 3. Reutilización exacta del ejecutable V1

- Se ejecutó `TC-M02-G48/test_tc_m02_g48.json`, la colección oficial de V1, **sin copiarla ni modificarla**. No se creó `test_tc_m02_g48_v2.json`.
- `git hash-object test_tc_m02_g48.json` = `71790cf24858cebff5d51a27d053d185a2a0b672`, igual al blob de `HEAD` antes y después de la ejecución. `git status` no muestra cambios.
- **`construir_coleccion.cjs` no se ejecutó**; su hash `50cb80a0…` coincide con `HEAD`.
- La colección sigue usando literalmente `99999`, `288`, `329` y `336`, y las credenciales de V1. Los tres logins devolvieron 200 con el `sub` esperado (2/2 aserciones cada uno).
- Mismos 25 ítems y 88 aserciones que en V1.

Comando ejecutado **una sola vez**, desde la raíz de `sgpmp-backend`:

```bash
newman run "$G/test_tc_m02_g48.json" -r cli,json,htmlextra \
  --reporter-json-export "$G/EvaluacionV2/Resultados/reporte_tc_m02_g48_v2.json" \
  --reporter-htmlextra-export "$G/EvaluacionV2/Resultados/reporte_tc_m02_g48_v2.html"
```

---

## 4. Resultado Newman

Ejecución del 2026-09-19, de 07:32:39 a 07:32:47 UTC (7,3 s), con Newman 6.2.2.

| Métrica | Ejecutado | Fallido |
|---|---:|---:|
| Iteraciones | 1 | 0 |
| Peticiones | 25 | 0 |
| Scripts de test | 25 | 0 |
| Scripts pre-request | 25 | 0 |
| **Aserciones** | **88** | **1** |

**Único fallo:** `00-SETUP-LECTURA / Contrato vivo OpenAPI por HTTPS`, aserción *«DISCREPANCIA DOCUMENTADA: el contrato no declara 409 pese a que la ficha lo exige»*.

```text
respuestas declaradas: 201,400,401,403,404,409,422: expected [ '201', '400', '401', '403', …(3) ] to not include '409'
```

Análisis:

- No es un criterio funcional de TC-M02-304/305. Solo documentaba la discrepancia histórica de V1 §2.1.
- Falla porque **la discrepancia ya está corregida**: el contrato desplegado declara 409 en `POST /activos-biologicos/{id_activo}/eventos/crecimiento`, lo que alinea ficha, implementación y contrato.
- Conforme a la metodología, la colección no se modificó ni se reejecutó, y el fallo no convierte el caso en RECHAZADO.
- **Las otras 87 aserciones pasaron**, entre ellas todas las funcionales de G48.

---

## 5. TC-M02-304

El payload es el de V1: la fecha la calcula la colección (≈ `2026-09-19T07:30:4xZ`) y `tipo_agregacion` se omite.

```json
{"tipo_medicion":"PESO","valor_medicion":250,"unidad_medida":"kg","fecha":"2026-09-19T07:30:44Z","descripcion":"TC-M02-304 <actor>: payload valido, unica condicion invalida en el activo"}
```

| Actor | ID | HTTP V1 | HTTP V2 | Respuesta V2 | Aserciones | ¿Persistió? | Resultado |
|---|---:|---:|---:|---|---:|---|---|
| Productor | 99999 | 404 | **404** | `ACTIVO_NO_ENCONTRADO`: *El activo biológico con id 99999 no existe.* | 7/7 | NO | **APROBADO** |
| Veterinario | 99999 | 404 | **404** | idéntico | 7/7 | NO | **APROBADO** |
| Ingeniero de campo | 99999 | 404 | **404** | idéntico | 7/7 | NO | **APROBADO** |

Las aserciones comprueban:

- que el actor está autenticado;
- la URL real `/activos-biologicos/99999/eventos/crecimiento`;
- que el payload es válido;
- HTTP 404;
- el `error_code` de activo inexistente, y no el `{"detail":"Not Found"}` del enrutador;
- que el mensaje nombra 99999;
- que el activo 99999 no se creó (los GET posteriores siguen devolviendo 404).

**TC-M02-304: APROBADO. Evolución: SIN REGRESIÓN.**

---

## 6. TC-M02-305

| Actor | Activo | Estado | HTTP V1 | HTTP V2 | Respuesta V2 | Aserciones | Conteo antes → después | Resultado |
|---|---:|---|---:|---:|---|---:|---|---|
| Productor | 288 | CERRADO | 409 | **409** | `ESTADO_NO_PERMITE_EVENTOS` | 7/7 | 0 → 0 | **APROBADO** |
| Veterinario | 329 | CERRADO | 409 | **409** | `ESTADO_NO_PERMITE_EVENTOS` | 7/7 | 0 → 0 | **APROBADO** |
| Ingeniero de campo | 336 | CERRADO | 409 | **409** | `ESTADO_NO_PERMITE_EVENTOS` | 7/7 | 0 → 0 | **APROBADO** |

Mensaje V2, idéntico al de V1, para los tres actores:

```text
El activo no se encuentra en estado ACTIVO. Estado actual: CERRADO.
Los eventos de crecimiento solo se pueden registrar sobre activos en estado ACTIVO.
```

Las aserciones comprueban:

- que el activo existe y está CERRADO;
- que el actor tiene acceso legítimo;
- que el payload es válido;
- HTTP 409;
- que el mensaje corresponde a un activo no ACTIVO e identifica el estado CERRADO;
- que el rechazo no proviene de otra regla de RF-40;
- la no persistencia, con un `GET …/historial` que da Δ 0.

**TC-M02-305: APROBADO. Evolución: SIN REGRESIÓN.**

---

## 7. Verificación BD PRE/POST

Se ejecutaron las mismas consultas en solo lectura antes (07:31:55Z) y después (07:33:04Z) de Newman:

```sql
SELECT count(*), max(id_eventos) FROM modulo2.eventos_activos;
SELECT count(*), max(id_activo_biologico) FROM modulo2.activos_biologicos;
SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999;
SELECT count(*) FROM modulo2.eventos_activos    WHERE id_activo_biologico = 99999;
SELECT ab.id_activo_biologico, e.nombre AS estado,
       (SELECT count(*) FROM modulo2.eventos_activos ea
          JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
         WHERE ea.id_activo_biologico = ab.id_activo_biologico) AS eventos_crecimiento
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico IN (288,329,336);
```

| Métrica | ANTES | DESPUÉS | Δ |
|---|---:|---:|---:|
| `eventos_activos`: filas | 169 | 169 | **0** |
| `eventos_activos`: `max(id_eventos)` | 357 | 357 | **0** |
| `activos_biologicos`: filas | 363 | 363 | **0** |
| `activos_biologicos`: `max(id_activo_biologico)` | 452 | 452 | **0** |
| Activo 99999 | 0 | 0 | **0** |
| Eventos asociados a 99999 | 0 | 0 | **0** |
| 288: estado / eventos de crecimiento | CERRADO / 0 | CERRADO / 0 | **0** |
| 329: estado / eventos de crecimiento | CERRADO / 0 | CERRADO / 0 | **0** |
| 336: estado / eventos de crecimiento | CERRADO / 0 | CERRADO / 0 | **0** |

**No hubo persistencia indebida**: no se creó el activo 99999, no se registró ningún evento y ningún estado cambió. Los totales difieren de los de V1 (106 / 240 / 259) por la actividad posterior en TEST. El criterio aplicable es DESPUÉS = ANTES, y se cumple.

**Auditoría RF-52, escritura esperada y no de dominio.** En `modulo2.bitacora_auditoria_m02` hay, entre 07:32:44 y 07:32:47Z, exactamente **6 registros `RF40 / EVENTO_CRECIMIENTO_RECHAZADO / RECHAZADO`**, uno por cada POST oficial:

- `ACTIVO_NO_ENCONTRADO`, con `id_activo_solicitado = 99999`, para los usuarios 35, 3 y 4;
- `ESTADO_NO_PERMITE_EVENTOS` para 288/35, 329/3 y 336/4.

Además aparecen los registros de consulta RF35/RF46 que generan los GET de la colección. Se trata de la trazabilidad de rechazos que exige RF-52, no de persistencia del evento rechazado. En V1 no existía este mecanismo: lo introdujo el commit `17ae99bc`, del 2026-09-11.

---

## 8. Reevaluación de observación formal V1

### OBS-G48-01 (§10; ID sugerido OBS-G48-03): el POST de crecimiento no aplicaba el alcance por finca

**Estado en V1:** observación de lectura de código, **no verificada funcionalmente** y fuera del alcance de G48. Sus evidencias eran estas:

- en `activo_biologico_router.py`, el endpoint de crecimiento (líneas 666–690) no usaba `_ids_fincas_alcance`, mientras que las consultas (líneas 279, 417 y 497) sí lo usaban;
- en el caso de uso, `obtener_por_id(id_activo)` no aplicaba alcance.

Tenía severidad provisional Media y estado Abierto.

**Evidencia V2.** Proviene solo de la lectura del código de la rama actual (HEAD `a6220fc8`) y de metadatos de Git:

1. **Endpoint.** `src/biological_assets/infrastructure/routers/activo_biologico_router.py:709-743`. `registrar_evento_crecimiento` calcula y propaga el alcance, igual que las rutas de consulta (líneas 316, 455, 488, 540, 583, 700…):
   ```python
   evento, fase_avanzada = use_case.execute(
       id_activo, dto, usuario_actual,
       ids_fincas_permitidas=_ids_fincas_alcance(db, usuario_actual),   # línea 740
   )
   ```
2. **Caso de uso.** `src/biological_assets/application/use_cases/gestion/registrar_evento_crecimiento_use_case.py:72`, dentro de `_execute`. La primera acción, antes de cualquier otra validación y antes de registrar el evento, es:
   ```python
   activo = self.activo_repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
   if activo is None:
       raise NotFoundError(code='ACTIVO_NO_ENCONTRADO', ...)
   ```
3. **Repositorio.** `src/biological_assets/infrastructure/repositories/activo_biologico_repository.py:157-170`. `obtener_por_id` devuelve `None` cuando `ids_fincas_permitidas` no es `None` y la infraestructura del activo no pertenece a ninguna finca permitida (`_pertenece_a_fincas`). Un activo de otra finca se trata, por tanto, como inexistente (404), igual que en las consultas.
4. **Llamada sin alcance: solo para auditoría.** En `registrar_evento_crecimiento_use_case.py:57`, `execute` pasa `obtener_por_id` sin alcance al envoltorio `ejecutar_con_auditoria_de_rechazo` (`_auditoria_rechazos.py`). Ese envoltorio solo lo usa **después** de que la operación haya sido rechazada, para completar el registro RF-52, y siempre vuelve a lanzar el error original. No registra el evento ni devuelve datos del activo al cliente, así que no reabre la asimetría.
5. **Trazabilidad de la corrección.** La corrección llegó con el commit `05a8002f` (2026-09-12, *fix(rf40): aplicar alcance por finca en registro de eventos de crecimiento*), que:
   - añade `anotaciones/modulo_2/inc_m02_71_g48_alcance_finca_crecimiento.md` (*INC-M02-71-G48*, que cita `OBS-G48-01` con «causa raíz (confirmada)»);
   - añade la prueba `tests/biological_assets/test_registrar_evento_crecimiento_alcance_finca.py`.

   El commit forma parte de HEAD (`git merge-base --is-ancestor 05a8002f HEAD`).
6. **Correspondencia fuente ↔ TEST.** El OpenAPI desplegado declara `409` en este endpoint, igual que el código de HEAD (línea 718). Esa declaración la introdujo `9cbb4418` (2026-09-15), un commit posterior a `05a8002f` que también está en HEAD. El contrato vivo es, por tanto, coherente con un despliegue que incluye la corrección. Aun así, el commit exacto desplegado no consta en la evidencia.

**Evolución: OBSERVACIÓN RESUELTA.** El código actual aplica el alcance por finca antes de registrar el evento, con el mismo mecanismo que las consultas.

**Limitación.** La corrección y la antigua explotabilidad **no se verificaron funcionalmente en TEST**. No se hizo ningún POST de crecimiento sobre un activo ACTIVO de otra finca, porque si la observación siguiera vigente se habría creado un evento no autorizado en datos compartidos. La clasificación se basa en el código fuente y en su coherencia con el contrato desplegado.

---

## 9. Contexto no formal

- **OpenAPI y el código 409 (V1 §2.1).** La discrepancia histórica **ya no existe**: el contrato desplegado declara `201, 400, 401, 403, 404, 409, 422`. Es una mejora contextual y es la causa del único fallo de Newman (§4). No se registra como incidencia.
- **Credencial del Veterinario (V1 §3.3).** La colección usa `juan.carlos.qa133@sgpmp-test.com`, que autenticó con HTTP 200 y `sub` = 3. No interfirió con la ejecución.

---

## 10. Comparación V1 ↔ V2

| Dimensión | V1 | V2 | Evolución |
|---|---|---|---|
| Ejecutable | `test_tc_m02_g48.json` | El mismo archivo, con el mismo hash | Idéntico |
| TC-M02-304 Productor | 404 `ACTIVO_NO_ENCONTRADO` | 404 `ACTIVO_NO_ENCONTRADO` | **SIN REGRESIÓN** |
| TC-M02-304 Veterinario | 404 | 404 | **SIN REGRESIÓN** |
| TC-M02-304 Ingeniero | 404 | 404 | **SIN REGRESIÓN** |
| TC-M02-305 Productor (288) | 409 `ESTADO_NO_PERMITE_EVENTOS` | 409 `ESTADO_NO_PERMITE_EVENTOS` | **SIN REGRESIÓN** |
| TC-M02-305 Veterinario (329) | 409 | 409 | **SIN REGRESIÓN** |
| TC-M02-305 Ingeniero (336) | 409 | 409 | **SIN REGRESIÓN** |
| Persistencia | Δ 0 | Δ 0 | **SIN REGRESIÓN** |
| Newman | 88 aserciones / 0 fallos | 88 aserciones / 1 fallo (diagnóstico de OpenAPI) | Cambio contextual: la discrepancia se corrigió |
| OBS-G48-01 (§10; ID sugerido OBS-G48-03) | Abierta, sin verificar | Alcance aplicado en el código actual (`05a8002f`), coherente con el contrato desplegado | **OBSERVACIÓN RESUELTA** (sin verificación funcional) |
| Veredicto | APROBADO | APROBADO | **SIN REGRESIÓN** |

---

## 11. Regresiones

No se identificaron regresiones. Todas las aserciones funcionales de TC-M02-304 y TC-M02-305 pasaron con los tres actores, sin persistencia. El único fallo de Newman refleja una mejora del contrato, no un defecto.

---

## 12. Veredicto final

# ✅ APROBADO — SIN REGRESIÓN

- **TC-M02-304:** 3/3 → 404 `ACTIVO_NO_ENCONTRADO`. No se creó el activo 99999.
- **TC-M02-305:** 3/3 → 409 `ESTADO_NO_PERMITE_EVENTOS`. Los estados no cambiaron.
- **Sin persistencia:** Δ = 0 en eventos, activos y estados.
- **OBS-G48-01 (§10; ID sugerido OBS-G48-03):** OBSERVACIÓN RESUELTA a nivel de código. No se verificó funcionalmente, por seguridad.

---

## 13. Declaración de integridad

- ✅ **V1 intacta.** Los siguientes archivos coinciden con `HEAD` al terminar y conservan su fecha de modificación (2026-09-12):
  - `test_tc_m02_g48.json` (`71790cf2…`);
  - `construir_coleccion.cjs` (`50cb80a0…`);
  - `Resultados/TC-M02-G48_resultado.md` (`5bd605b3…`);
  - `reporte_tc_m02_g48.json` (`9b91ee46…`);
  - `reporte_tc_m02_g48.html` (`92e72b3c…`).
- ✅ **`construir_coleccion.cjs` no se ejecutó.** No se creó `test_tc_m02_g48_v2.json`.
- ✅ **Newman se ejecutó una sola vez en esta reevaluación.** Los artefactos V2 de un intento anterior los retiró QA antes de empezar, y `EvaluacionV2/` estaba vacía. Las únicas escrituras potenciales fueron los 6 POST oficiales. Todos fueron rechazados y no persistieron datos de dominio; solo quedó la auditoría de rechazo RF-52 (§7).
- ✅ **BD solo en lectura** (`transaction_read_only = on`): únicamente `SELECT`, sin tocar ningún trigger.
- ✅ No se sustituyó `99999`, no se cambiaron 288/329/336 ni sus estados, no se crearon fixtures y no se borraron datos.
- ✅ **No se hizo ningún POST entre fincas.** OBS-G48-01 se reevaluó solo leyendo código y metadatos de Git (`git log`, `git reflog`, `git merge-base`), sin fetch.
- ✅ **No se cambió de rama.** El avance de HEAD a `a6220fc8` fue un fast-forward previo, ajeno al agente (§2.1).
- ✅ No se crearon suites, scripts ni JSON adicionales en el repositorio. La evidencia V2 consiste en `reporte_tc_m02_g48_v2.json`, `reporte_tc_m02_g48_v2.html` y este informe.
- ✅ **DEV no se usó.**
- ✅ **No se modificó código productivo** y no se hizo **commit, push, merge, rebase ni deploy**.
- ✅ No se crearon incidencias en Taiga ni en GitHub, y no se modificó el Registro de Errores.
