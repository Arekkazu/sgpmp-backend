# REEVALUACIÓN V2 — TC-M02-G80

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| RF | RF-48 — Transferencia interna de activos biológicos (CU10C) |
| Caso | TC-M02-G80 — TC-M02-134 (E-06), TC-M02-135 (E-07 / C1), TC-M02-136 (E-08 / C2), TC-M02-137 (E-09 / C3) |
| Ambiente | TEST |
| Rama | `qa/juan-esteban-re-evaluacion-m02` |
| HEAD V2 | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`. `HEAD...origin/test` = `0 0` |
| Ejecutable | **Variante V2 equivalente por sustitución de fixtures**: `EvaluacionV2/test_tc_m02_g80_v2.json`, derivada de `test_tc_m02_g80.json` de V1, que se conserva intacta (§1.2) |
| Newman | 1 ejecución · 27 peticiones · **146 aserciones · 0 fallos** · 8 POST oficiales |
| Persistencia de dominio | **V1: SÍ** (TC-M02-136) → **V2: NO** (Δ = 0) |
| Veredicto funcional G80 | ❌ RECHAZADO (V1) → ✅ **APROBADO — CORREGIDO / SIN REGRESIÓN** (V2) |
| DEF-G80-01 (directo, TC-136) | **CORREGIDO** |
| DEF-G80-02 (directo, TC-134) | **CORREGIDO** |
| OBS-G80-03 (colateral) | **OBSERVACIÓN RESUELTA**. No determina el veredicto de G80 |
| Regresiones | Ninguna |

---

## 1. Gate

### 1.1 Rama y colección V1

| Verificación | Resultado |
|---|---|
| `git branch --show-current` | `qa/juan-esteban-re-evaluacion-m02` ✅ |
| `git rev-parse HEAD` | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c` ✅ |
| `git rev-list --left-right --count HEAD...origin/test` | `0 0` ✅ |
| `git status --short` | Sin cambios en archivos versionados. Solo aparecen carpetas `EvaluacionV2/` sin seguimiento |
| Hash de `test_tc_m02_g80.json` | `b0b4e0f508792ccfe65149968bd920da01043da5` con `git hash-object --no-filters` ✅ (el hash esperado) |

**Nota sobre el hash.** Con `core.autocrlf=true`, el comando `git hash-object` sin opciones normaliza los finales de línea y devuelve `7f90039f74fbfc872a1ad01e9c46608c9cb2f54b`, que es el blob versionado en `HEAD`. Ambos valores corresponden al mismo archivo, que no tiene cambios (`git diff` vacío). La colección tiene una sola versión en todo el historial: el commit `5defb7ae` de V1.

### 1.2 Fixtures: sustitución autorizada

En un primer gate (07:54 UTC) se comprobó que los fixtures V1 ya no reproducían el escenario:

- **280 y 285 seguían en la infraestructura 52**, a donde los movió la propia ejecución V1 (historiales 286 y 287 abiertos).
- La ocupación de la infraestructura 47 era **49** en lugar de 48. El puesto extra lo ocupa el activo 290 `QAJE-TRF-CONC`, trasladado el 2026-09-10 a las 10:36Z (historial 288).

La ejecución se detuvo sin lanzar Newman. QA autorizó continuar con fixtures equivalentes (paquete §7.0 y §10–11). En la autorización, QA declaró que las referencias de §7.1/§7.3 a 280/285 y a la ocupación 48 quedan sustituidas.

| Subcaso / actor | V1 | V2 |
|---|---|---|
| TC-M02-136 / Productor | activo 280 `QAJE-IND-OUTLIER` | activo **292** `QAJE-TRF-OK` |
| TC-M02-136 / Administrador | activo 285 `QAJE-IND-1MED` | activo **299** `QAJE-IND-MACHO` |
| TC-M02-137 | ocupación de la 47 = 48 · 48 + 10 = 58 > 50 | ocupación de la 47 = **49** · **49 + 10 = 59 > 50** |

### 1.3 Datos: estado previo (solo lectura)

Gate del 2026-09-19 a las 08:06 UTC. BD con `SET default_transaction_read_only = on`: `member_qa` / `sgpmp_test` / `transaction_read_only = on`.

| Activo | Identificador | Tipo | Especie | Infraestructura | Estado | Cantidad | Uso |
|---:|---|---|---:|---:|---|---:|---|
| 294 | QAJE-TRF-REGLAS | INDIVIDUAL | 40 | **51** | ACTIVO | — | TC-134 y TC-135, ambos actores |
| 292 | QAJE-TRF-OK | INDIVIDUAL | 40 | **48** (historial 290 abierto) | ACTIVO | — | TC-136 Productor |
| 299 | QAJE-IND-MACHO | INDIVIDUAL | 40 | **48** (historial 246 abierto) | ACTIVO | — | TC-136 Administrador |
| 296 | (lote) | POBLACIONAL | 40 | **48** | ACTIVO | **10** | TC-137, ambos actores |

| Infra | Nombre | Tipo | Activa | Capacidad | Especie | Finca | Ocupación |
|---:|---|---|---|---:|---:|---:|---:|
| 47 | Corral QA JE Capacidad | Corral | ✅ | 50 | 40 | 57 | **49** |
| 48 | Corral QA JE Origen | Corral | ✅ | 1000 | NULL | 57 | 221 |
| 51 | Corral QA JE Destino OK | Corral | ✅ | 200 | 40 | 57 | 1 |
| 52 | Estanque QA JE Piscicola | **Estanque** | ✅ | 100 | NULL | 57 | 2 |
| 53 | Galpon QA JE Aves | Galpón | ✅ | 100 | **41** | 57 | 0 |

La finca 57 pertenece al usuario 35 (Productor). Línea base de dominio: `modulo2.movimientos` 26 filas (máximo `id_movimiento` 30); `modulo2.historial_infraestructura_activo` 365 filas (máximo `id_historial` 403).

### 1.4 Seguridad de C2 confirmada antes de ejecutar

- **Código** (`registrar_transferencia_use_case.py`): el control C2 (`es_tipo_compatible` → `BusinessRuleError INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA`, línea 146) se evalúa antes de cualquier escritura. El `commit` de la transferencia está en la línea 281.
- **Riesgo identificado:** `es_tipo_compatible` devuelve `True` si no hay reglas configuradas para el tipo de infraestructura. `member_qa` no tiene permiso de lectura sobre `modulo9.compatibilidades_tipo_area_especie`.
- **Verificación del comportamiento desplegado, solo con GET:** `GET /activos-biologicos/{292|299}/transferencias/disponibles` devolvió `[47, 51]` para ambos actores. Para estos activos, la 52 cumple finca, especie (NULL) y capacidad (2 + 1 ≤ 100). Su ausencia solo se explica porque `es_tipo_compatible('Estanque', 40)` es `False` en TEST. El gate quedó superado antes de lanzar ningún POST.

---

## 2. Ejecución V2

**Construcción controlada.** `EvaluacionV2/test_tc_m02_g80_v2.json` (hash `--no-filters` `55a880e3…`) es una copia byte a byte de V1 con reemplazos exactos. La cantidad de cada reemplazo se verificó por aserción al generar la copia.

| Reemplazo | Ocurrencias | Alcance |
|---|---:|---|
| `280` → `292` | 16 | URL, nombres, variable `origen_280`, aserciones de TC-136 Productor y su SETUP |
| `285` → `299` | 16 | Ídem, para TC-136 Administrador |
| `ocupacion actual 48` / regex `ocupacion actual: ?48` → `49` | 2 + 2 | TC-137, ambos actores |
| `la proyeccion 48 + 10 = 58` y `pm.expect(48 + …)` → `49 + 10 = 59` / `49 + …` | 2 + 2 | TC-137, ambos actores |
| Motivo `capacidad 50 y ocupacion 48` → `49` | 2 | Cuerpo de TC-137 |

`git diff --no-index` da 36 líneas añadidas y 36 eliminadas, todas dentro de ese alcance. **No cambian** TC-M02-134, TC-M02-135, el activo 294, el lote 296, los destinos 47/52/53, los HTTP ni `error_code` esperados, los criterios C1/C2/C3, los actores ni los endpoints.

**Ejecución única**, 2026-09-19, de 08:11:35 a 08:11:43 UTC:

```bash
newman run "$G/EvaluacionV2/test_tc_m02_g80_v2.json" -r cli,json,htmlextra \
  --reporter-json-export "$G/EvaluacionV2/Resultados/reporte_tc_m02_g80_v2.json" \
  --reporter-htmlextra-export "$G/EvaluacionV2/Resultados/reporte_tc_m02_g80_v2.html"
```

| Métrica | V1 | V2 |
|---|---:|---:|
| Peticiones | 27 | 27 (0 fallidas) |
| Aserciones | 151 | **146** |
| Aserciones fallidas | 6 | **0** |
| POST oficiales | 8 | 8 |

La diferencia de 5 aserciones está localizada en los dos GET de `disponibles` del SETUP (294: 5 → 3; 296: 5 → 2). Esas comprobaciones de atributos de los destinos 53/52/47 solo se ejecutan si el destino aparece en el listado, y en V2 ya no aparece (§8, OBS-G80-03). El resto de bloques tiene exactamente el mismo número de aserciones que V1.

---

## 3. TC-M02-134 — destino = origen (E-06)

| Actor | Activo | Origen → destino | V1 | V2 | Mensaje V2 | Δ ubicación | Evolución |
|---|---:|---|---|---|---|---:|---|
| Productor | 294 | 51 → 51 | 400 `DESTINO_IGUAL_ORIGEN` | **422** `DESTINO_IGUAL_ORIGEN` (9/9) | *La infraestructura destino debe ser diferente a la infraestructura origen del activo.* (`infraestructura_destino_id`) | 0 | **CORREGIDO** |
| Administrador | 294 | 51 → 51 | 400 `DESTINO_IGUAL_ORIGEN` | **422** `DESTINO_IGUAL_ORIGEN` (9/9) | idéntico | 0 | **CORREGIDO** |

La regla E-06 responde ahora con el 422 que exigen la ficha y el contrato. La verificación posterior (`GET /activos-biologicos/294`) confirma que el activo sigue en la 51.

---

## 4. TC-M02-135 — C1 especie (E-07)

| Actor | Activo | Origen → destino | V1 | V2 | Mensaje V2 | Δ | Evolución |
|---|---:|---|---|---|---|---:|---|
| Productor | 294 (especie 40) | 51 → 53 (Galpón, especie 41) | 422 `INCOMPATIBILIDAD_ESPECIE` | **422** `INCOMPATIBILIDAD_ESPECIE` (9/9) | *La infraestructura Galpon QA JE Aves no está habilitada para la especie del activo. Seleccione una infraestructura compatible con la especie.* | 0 | **SIN REGRESIÓN** |
| Administrador | 294 | 51 → 53 | 422 `INCOMPATIBILIDAD_ESPECIE` | **422** `INCOMPATIBILIDAD_ESPECIE` (9/9) | idéntico | 0 | **SIN REGRESIÓN** |

C1 se evalúa antes que C2, así que el rechazo de este subcaso sigue atribuyéndose a la especie, igual que en V1.

---

## 5. TC-M02-136 — C2 tipo de infraestructura (E-08)

| Actor | Activo | Origen → destino | V1 | V2 | Mensaje V2 | Δ ubicación / historial | Evolución |
|---|---|---|---|---|---|---|---|
| Productor | V1: 280 · **V2: 292** | 48 → 52 (Estanque) | **201**, movimiento 25, activo movido a la 52 | **422** `INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA` (8/8) | *La infraestructura Estanque QA JE Piscicola (tipo Estanque) no es compatible con la especie del activo. Seleccione una infraestructura de un tipo compatible.* | 0 / 0 | **CORREGIDO** |
| Administrador | V1: 285 · **V2: 299** | 48 → 52 (Estanque) | **201**, movimiento 26, activo movido a la 52 | **422** `INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA` (8/8) | idéntico | 0 / 0 | **CORREGIDO** |

El escenario mantiene el aislamiento de V1:

- la 52 no restringe especie, así que C1 no interviene;
- con capacidad 100 y ocupación 2, C3 tampoco interviene;
- origen 48 ≠ destino 52, así que E-06 no interviene.

La única regla incumplida es C2, y el sistema ahora la aplica y **no persiste nada**. Las verificaciones posteriores de la colección confirman que 292 y 299 siguen en la 48 y en estado ACTIVO.

---

## 6. TC-M02-137 — C3 capacidad (E-09)

| Actor | Lote | Destino | Capacidad | Ocupación | Proyección | V1 | V2 | Evolución |
|---|---:|---:|---:|---:|---|---|---|---|
| Productor | 296 (10) | 47 | 50 | V1: 48 · **V2: 49** | V1: 58 · **V2: 59** > 50 | 422 `CAPACIDAD_EXCEDIDA` | **422** `CAPACIDAD_EXCEDIDA` (12/12) | **SIN REGRESIÓN** |
| Administrador | 296 (10) | 47 | 50 | **49** | **59** > 50 | 422 `CAPACIDAD_EXCEDIDA` | **422** `CAPACIDAD_EXCEDIDA` (12/12) | **SIN REGRESIÓN** |

Mensaje V2: *La infraestructura Corral QA JE Capacidad no tiene capacidad disponible. Capacidad máxima: 50, ocupación actual: 49.* La ocupación que informa el sistema coincide con la calculada por `SELECT` en el gate. La regla C3 es la misma de V1; solo cambia el valor actual del fixture.

---

## 7. Persistencia de dominio PRE/POST

Consultas solo con `SELECT`: PRE a las 08:06 UTC y POST a las 08:12 UTC.

| Métrica | PRE | POST | Δ |
|---|---:|---:|---:|
| Ubicación 294 | 51 | 51 | 0 |
| Ubicación 292 | 48 | 48 | 0 |
| Ubicación 299 | 48 | 48 | 0 |
| Ubicación 296 (cantidad) | 48 (10) | 48 (10) | 0 |
| `modulo2.movimientos` filas / máximo | 26 / 30 | 26 / 30 | **0** |
| Movimientos nuevos de 292/294/296/299 | — | 0 | **0** |
| `modulo2.historial_infraestructura_activo` filas / máximo | 365 / 403 | 365 / 403 | **0** |
| Historiales de 292 / 294 / 296 / 299 | 3 / 4 / 1 / 1 | 3 / 4 / 1 / 1 | 0 |
| Ocupación 47 / 48 / 51 / 52 / 53 | 49 / 221 / 1 / 2 / 0 | 49 / 221 / 1 / 2 / 0 | **0** |

**Persistencia de dominio: V1 SÍ (TC-M02-136) → V2 NO.**

**Auditoría RF-52, que no es persistencia de dominio.** `modulo2.bitacora_auditoria_m02` registró exactamente 8 filas `RF48 / TRANSFERENCIA_RECHAZADA / RECHAZADO` entre 08:11:30 y 08:11:50Z, una por POST, con el actor y el `error_code` correctos:

- `DESTINO_IGUAL_ORIGEN` ×2 (294);
- `INCOMPATIBILIDAD_ESPECIE` ×2 (294);
- `INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA` (292 / usuario 35 y 299 / usuario 1);
- `CAPACIDAD_EXCEDIDA` ×2 (296).

Es la trazabilidad de rechazos que exige RF-52.

**Estado heredado de V1, no modificado:** 280 y 285 siguen en la 52 con los historiales 286/287 abiertos. Sigue pendiente la restauración que documentó V1, que corresponde a DBA / Implementación.

---

## 8. Reevaluación de hallazgos V1

### DEF-G80-01 — C2 no implementada (DIRECTO AL CASO, TC-M02-136)

- **V1:** `HTTP 201`. Se ejecutaron las transferencias 25 y 26 y los activos 280/285 quedaron en el Estanque. Severidad Severo, estado Abierto.
- **V2:** `HTTP 422 INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA` con ambos actores (fixtures equivalentes 292/299), sin movimiento, sin cambio de ubicación, sin historial nuevo y sin cambio de ocupación.
- **Evolución: CORREGIDO.** Afecta al veredicto de G80.

### DEF-G80-02 — E-06 responde 400 en vez de 422 (DIRECTO AL CASO, TC-M02-134)

- **V1:** `HTTP 400 DESTINO_IGUAL_ORIGEN`, un código no declarado en el contrato. Severidad Medio, estado Abierto.
- **V2:** `HTTP 422 DESTINO_IGUAL_ORIGEN` con ambos actores, mismo mensaje y mismo campo, sin persistencia.
- **Evolución: CORREGIDO.** Afecta al veredicto de G80.

### OBS-G80-03 — `GET /transferencias/disponibles` ofrecía destinos que el POST rechaza (COLATERAL / COMPLEMENTARIO)

> **OBS-G80-03 es un hallazgo colateral registrado durante V1. Se reevaluó para conservar trazabilidad V1↔V2, pero no forma parte de los criterios de aceptación de TC-M02-134/135/136/137 y su estado no determina por sí solo el veredicto funcional de G80.**

- **V1:** el listado solo excluía el origen. Devolvía 38 destinos para 294 y para 296, entre ellos 53 (incumple C1), 52 (incumple C2), 47 para el lote (incumple C3) y 34 infraestructuras de otras fincas.
- **V2:** solo GET, ejecutados por la propia colección en su SETUP, con el Productor.

| Activo | Destinos devueltos V2 | 53 (C1) | 52 (C2) | 47 (C3) | Otras fincas | Coherencia de lo devuelto |
|---|---|---|---|---|---:|---|
| 294 (INDIVIDUAL, origen 51) | **[47, 48]** | ✅ ausente | ✅ ausente | Aparece y es correcto: 49 + 1 = 50 ≤ 50 | **0** | 47 y 48 son Corrales de la finca 57, compatibles y con cupo |
| 296 (LOTE 10, origen 48) | **[51]** | ✅ ausente | ✅ ausente | ✅ ausente (49 + 10 > 50) | **0** | 51: especie 40, 1 + 10 ≤ 200 |

El listado ya aplica C1, C2, C3 y el alcance por finca, y solo ofrece destinos que el POST aceptaría. Los dos GET de 292/299 del gate (§1.4) devolvieron `[47, 51]`, un resultado coherente con la misma lógica.

- **Evolución: OBSERVACIÓN RESUELTA.** No afecta por sí sola al veredicto de G80.

---

## 9. Comparación V1 ↔ V2

| Subcaso | V1 | V2 | Evolución |
|---|---|---|---|
| TC-M02-134 Productor | 400 `DESTINO_IGUAL_ORIGEN` | 422 `DESTINO_IGUAL_ORIGEN` | **CORREGIDO** |
| TC-M02-134 Administrador | 400 `DESTINO_IGUAL_ORIGEN` | 422 `DESTINO_IGUAL_ORIGEN` | **CORREGIDO** |
| TC-M02-135 Productor | 422 `INCOMPATIBILIDAD_ESPECIE` | 422 `INCOMPATIBILIDAD_ESPECIE` | **SIN REGRESIÓN** |
| TC-M02-135 Administrador | 422 `INCOMPATIBILIDAD_ESPECIE` | 422 `INCOMPATIBILIDAD_ESPECIE` | **SIN REGRESIÓN** |
| TC-M02-136 Productor | 201 + transferencia persistida (activo 280) | Fixture equivalente 292: 422 `INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA`, Δ 0 | **CORREGIDO** |
| TC-M02-136 Administrador | 201 + transferencia persistida (activo 285) | Fixture equivalente 299: 422 `INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA`, Δ 0 | **CORREGIDO** |
| TC-M02-137 Productor | 422 `CAPACIDAD_EXCEDIDA` (ocupación 48) | 422 `CAPACIDAD_EXCEDIDA` (ocupación 49) | **SIN REGRESIÓN** |
| TC-M02-137 Administrador | 422 `CAPACIDAD_EXCEDIDA` (ocupación 48) | 422 `CAPACIDAD_EXCEDIDA` (ocupación 49) | **SIN REGRESIÓN** |

Persistencia de dominio: **V1: SÍ en TC-M02-136. V2: NO.**

| Hallazgo V1 | Relación con G80 | V1 | V2 | Evolución | Impacto en el veredicto de G80 |
|---|---|---|---|---|---|
| DEF-G80-01 | Directo — TC-M02-136 | Abierto: 201 y transferencia persistida | 422 `INCOMPATIBILIDAD_TIPO_INFRAESTRUCTURA`, Δ 0 | **CORREGIDO** | Sí |
| DEF-G80-02 | Directo — TC-M02-134 | Abierto: 400 | 422 `DESTINO_IGUAL_ORIGEN` | **CORREGIDO** | Sí |
| OBS-G80-03 | **Colateral / complementario** | Abierta: 38 destinos sin filtrar | Solo destinos compatibles, con cupo y de la finca | **OBSERVACIÓN RESUELTA** | **No por sí sola** |

---

## 10. Regresiones

No se identificaron regresiones. C1 y C3, que ya cumplían en V1, siguen cumpliendo con ambos actores. Las 146 aserciones pasaron.

---

## 11. Veredicto funcional de G80

# ✅ APROBADO — CORREGIDO / SIN REGRESIÓN

- TC-M02-134 → 422 ×2 (**CORREGIDO**)
- TC-M02-135 → 422 ×2 (**SIN REGRESIÓN**)
- TC-M02-136 → 422 ×2, sin persistencia (**CORREGIDO**)
- TC-M02-137 → 422 ×2 (**SIN REGRESIÓN**)
- Sin movimientos indebidos, sin cambios de ubicación, historial ni ocupación.

Evolución del caso: **RECHAZADO (V1) → APROBADO (V2)**. Se ejecutó con una variante equivalente por sustitución de fixtures (§1.2 y §2), porque la propia ejecución V1 alteró los datos originales.

---

## 12. Integridad

- ✅ **V1 intacta.** Los siguientes archivos coinciden con el blob de `HEAD` y conservan su fecha de modificación (2026-09-12):
  - `test_tc_m02_g80.json` (`--no-filters` `b0b4e0f5…`; blob `7f90039f…`);
  - `construir_coleccion.cjs` (blob `bb1a8e75…`);
  - `Resultados/TC-M02-G80_resultado.md` (blob `ef25804f…`);
  - `reporte_tc_m02_g80.json` (blob `991c8629…`);
  - `reporte_tc_m02_g80.html` (blob `332b241d…`).
- ✅ **`construir_coleccion.cjs` no se ejecutó.** La colección no se regeneró.
- ✅ **La variante V2 difiere de V1 solo en las referencias de fixtures autorizadas** (§2). No se cambiaron aserciones funcionales, códigos esperados ni criterios.
- ✅ **Newman se ejecutó una sola vez.** Solo se lanzaron los 8 POST oficiales, todos rechazados. No hubo POST de diagnóstico ni `curl`.
- ✅ **BD solo en lectura** (`transaction_read_only = on`): únicamente `SELECT`. No se restauraron 280/285, no se crearon ni modificaron fixtures y no se alteraron triggers.
- ✅ Llamadas adicionales solo de lectura: login y `GET …/transferencias/disponibles` de 292/299 en el gate de seguridad C2 (§1.4).
- ✅ **DEV no se usó.** No se modificó código productivo y no se hizo commit, push, merge, rebase ni deploy.
- ✅ No se crearon tickets.
- ✅ Artefactos V2:
  - `EvaluacionV2/test_tc_m02_g80_v2.json`;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g80_v2.json`;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g80_v2.html`;
  - este informe.
