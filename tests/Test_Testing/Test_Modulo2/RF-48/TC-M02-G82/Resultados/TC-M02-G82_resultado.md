# RESULTADO — TC-M02-G82

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **APROBADO** |
| Subtipo | — |
| COBERTURA ACTORES | **COMPLETA** |
| CICLOS CONCURRENTES | **2/2** |
| POST OFICIALES | **4/4** |
| DISTRIBUCIÓN ESPERADA | ✅ `1×éxito + 1×409 E-01` en los dos ciclos |
| CONSISTENCIA FINAL | **CORRECTA** |
| Equipo responsable | — (aprobado). Queda una observación no bloqueante en §9. |

**Justificación:** en los dos ciclos, dos POST realmente simultáneos sobre el mismo activo hacia destinos distintos produjeron exactamente **una transferencia aceptada y un rechazo `409 / TRANSFERENCIA_CONCURRENTE`**. El activo quedó en una única ubicación —la del ganador—, con una sola asociación vigente, un solo movimiento nuevo, la ocupación del origen decrementada una vez, la del ganador incrementada una vez y la del perdedor **sin cambios**.

> **El ganador fue distinto en cada ciclo** —la petición A en el del Productor y la **B** en el del Administrador—, lo que confirma que el resultado no es determinista y que la prueba lo resuelve dinámicamente, tal como exige §1.H.

---

## 1. Identificación

- **Caso:** TC-M02-G82 · **Sub-caso:** TC-M02-142
- **RF:** RF-48 — Transferencia interna de activos biológicos · **CU:** CU10C
- **Tipo:** Seguridad — OWASP API6, Sensitive Business Flows
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** sin modificaciones sobre archivos versionados; solo artefactos de QA sin seguimiento
- **Fecha/hora:** 2026-09-10 — ciclo del Productor a las 10:36:10 UTC, ciclo del Administrador a las 10:36:34 UTC · duración total 54,6 s
- **Ambiente:** TEST desplegado, HTTPS — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Herramienta:** **Pytest** (`pytest test_tc_m02_g82.py --junitxml=…`), con `threading.Barrier` y `ThreadPoolExecutor`
- **Evidencia BD:** PostgreSQL TEST `158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, sesión abierta en modo `readonly`

---

## 2. Gate

| Verificación | Resultado |
|---|---|
| Repositorio | ✅ `https://github.com/Arekkazu/sgpmp-backend.git` |
| Rama | ✅ `qa/juan-esteban-m02` (no se cambió de rama) |
| HEAD | ✅ `41369ea` |
| HTTPS backend | ✅ `GET /openapi.json` → **HTTP 200** |
| PostgreSQL solo lectura | ✅ `SELECT 1;` responde con `member_qa` |
| OpenAPI | ✅ revisado; ver §2.1 |

### 2.1 Contrato revisado

`POST /activos-biologicos/{id_activo}/transferencias`

- Body: `infraestructura_origen_id` (int), `infraestructura_destino_id` (int), `fecha_transferencia` (date `YYYY-MM-DD`), `motivo_transferencia` (str). Los cuatro obligatorios.
- Respuestas declaradas: **`201, 401, 403, 404, 409, 422, 500`**.
- `409` declarado, y es el que la ficha exige para E-01. ✅
- `TransferenciaResponse` devuelve `id_movimiento`, `id_activo_biologico`, `infraestructura_origen`, `infraestructura_destino`, `fecha_transferencia`, `motivo_transferencia` y `mensaje`.
- Historial y ocupación se verifican por `SELECT` sobre `modulo2.movimientos`, `modulo2.historial_infraestructura_activo` y `modulo9.infraestructuras`.

> **Discrepancia documentada.** La ficha enuncia `HTTP 200` para la solicitud ganadora. El contrato declara **`201`** y el sistema devuelve **`201`**. Contrato e implementación coinciden entre sí; es el enunciado de la ficha el que difiere. La prueba exige el criterio sustantivo —**exactamente un éxito y exactamente un `409` E-01**— y comprueba además que el éxito llega con el código contractual `201`. Registrado como OBS-G82-01, sin efecto sobre el veredicto.

### 2.2 Mecanismo real de E-01 (lectura de código)

```python
# transferencia_repository.hay_transferencia_en_progreso
SELECT id_activo_biologico FROM modulo2.activos_biologicos
 WHERE id_activo_biologico = :id FOR UPDATE NOWAIT
```

El control de concurrencia es un **bloqueo exclusivo de fila con `NOWAIT`**: la primera transacción que llega bloquea la fila del activo; la segunda no espera, falla al adquirir el lock y el caso de uso lo traduce en `ConflictError / TRANSFERENCIA_CONCURRENTE` (409). Es el primer control de todo el flujo, por delante de E-02 y siguientes. Esta lectura explica el resultado; la evidencia que sustenta el veredicto es la ejecución de §4 y §5.

---

## 3. Revisión previa — SOLO LECTURA

Todos los recursos pertenecen a la **finca 57** (`Finca QA Juan Esteban`), cuyo `id_usuario` es 35 (Productor); el Administrador (usuario 1, rol 1) tiene alcance global. Ambos actores obtuvieron `HTTP 200` al consultar su activo.

| Actor | Activo | Origen | Destino A | C1/C2/C3 A | Destino B | C1/C2/C3 B | Acceso |
|---|---:|---:|---:|---|---:|---|---|
| Productor (35) | **290** `QAJE-TRF-CONC` | 48 | **47** | OK/OK/OK | **51** | OK/OK/OK | ✅ 200 |
| Administrador (1) | **294** `QAJE-TRF-REGLAS` | 51 | **48** | OK/OK/OK | **47** | OK/OK/OK | ✅ 200 |

**Cada actor usa un activo distinto**, como exige §1.E: cada ciclo produce una transferencia efectiva y compartir activo contaminaría el segundo escenario.

**Escrituras SETUP: 0.** La etapa se limitó a `SELECT` (sesión `readonly`), `GET /openapi.json`, `GET /activos-biologicos/{id}`, `GET .../transferencias/disponibles` y los dos `POST /sesiones/` de autenticación. **No se envió ningún POST de sondeo** para comprobar la ausencia de concurrencia previa: se verificó sobre la fila del activo, que estaría bloqueada si hubiera una operación en curso.

### 3.1 Validación previa de los dos destinos (§10)

| Regla | Productor · A = 47 | Productor · B = 51 | Admin · A = 48 | Admin · B = 47 |
|---|---|---|---|---|
| Distinto al origen | ✅ 47 ≠ 48 | ✅ 51 ≠ 48 | ✅ 48 ≠ 51 | ✅ 47 ≠ 51 |
| A ≠ B | ✅ 47 ≠ 51 | ✅ | ✅ 48 ≠ 47 | ✅ |
| Activo | ✅ `es_activo = true` | ✅ | ✅ | ✅ |
| Misma finca | ✅ 57 | ✅ 57 | ✅ 57 | ✅ 57 |
| **C1** especie | ✅ 40 = 40 | ✅ 40 = 40 | ✅ `id_especie` NULL | ✅ 40 = 40 |
| **C2** tipo | ✅ Corral | ✅ Corral | ✅ Corral | ✅ Corral |
| **C3** capacidad | ✅ 48 + 1 = 49 ≤ 50 | ✅ 2 + 1 ≤ 200 | ✅ 221 + 1 ≤ 1000 | ✅ 49 + 1 = 50 ≤ 50 |
| Aparece en GET disponibles | ✅ | ✅ | ✅ | ✅ |

Se descartaron deliberadamente como destinos la infraestructura **52** (`Estanque`, incumpliría C2) y la **53** (`Galpón QA JE Aves`, especie 41, incumpliría C1), para que ninguna otra causa de rechazo pudiera confundirse con E-01.

**Nota sobre el destino 47.** Su capacidad es 50 y su ocupación inicial 48. La prueba comprueba C3 **inmediatamente antes de cada ciclo** con la ocupación vigente: en el ciclo del Productor, `48 + 1 = 49 ≤ 50`; tras ganar 47 ese ciclo, en el del Administrador `49 + 1 = 50 ≤ 50`. C3 se cumplió en los dos casos y en ningún momento el escenario quedó al borde de convertirse en una prueba de E-09.

### 3.2 Consultas de la revisión previa

```sql
-- Estado, tipo, origen, historial y asociaciones vigentes de los activos del caso
SELECT es.nombre AS estado, ab.tipo, ab.id_especie, ab.id_infraestructura,
       (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
         WHERE h.id_activo_biologico = ab.id_activo_biologico) AS n_historial,
       (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
         WHERE h.id_activo_biologico = ab.id_activo_biologico AND h.fecha_fin IS NULL) AS vigentes,
       (SELECT count(*) FROM modulo2.movimientos m
         WHERE m.id_activo_biologico = ab.id_activo_biologico) AS n_movimientos
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos es ON es.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico IN (290, 294);

-- Ocupación real de cada infraestructura, con la misma fórmula que usa el backend
SELECT COALESCE(SUM(CASE WHEN ab.tipo = 'INDIVIDUAL' THEN 1
                         ELSE COALESCE(dp.cantidad_actual, 0) END), 0)
FROM modulo2.activos_biologicos ab
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp
       ON dp.id_activo_biologico = ab.id_activo_biologico
WHERE ab.id_infraestructura = :id AND ab.id_estado NOT IN (5, 6);
```

| Infra | Nombre | Tipo | Activa | Capacidad | Especie | Ocupación inicial |
|---:|---|---|---|---:|---:|---:|
| 47 | Corral QA JE Capacidad | Corral | ✅ | 50 | 40 | 48 |
| 48 | Corral QA JE Origen | Corral | ✅ | 1000 | *NULL* | 221 |
| 51 | Corral QA JE Destino OK | Corral | ✅ | 200 | 40 | 2 |

Línea base global: **22 movimientos** (`max(id_movimiento) = 26`) y **251 filas** de historial.

### 3.3 Inventario mínimo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿Activos ACTIVO? | 15 bovinos INDIVIDUAL en la finca 57. Se usaron 290 y 294. |
| D2 | ¿Infraestructura origen actual? | 290 → 48 · 294 → 51, releídas justo antes de cada ciclo. |
| D3 | ¿Dos destinos activos y distintos en la misma finca? | Sí: {47, 51} para el Productor y {48, 47} para el Administrador. |
| D4–D6 | ¿Destino A cumple C1/C2/C3? | Sí en ambos ciclos. Ver §3.1. |
| D7–D9 | ¿Destino B cumple C1/C2/C3? | Sí en ambos ciclos. Ver §3.1. |
| D10 | ¿Ambos en GET `/transferencias/disponibles`? | Sí; afirmado por el test antes de liberar la barrera. |
| D11 | ¿Capacidad suficiente antes del inicio concurrente? | Sí; comprobada con la ocupación vigente en cada ciclo. |
| D12 | ¿Sin transferencia concurrente previa? | Sí: cada activo tenía exactamente **una** asociación vigente y su fila no estaba bloqueada. |
| D13 | ¿El Productor tiene acceso legítimo? | Sí: activo y destinos en la finca 57, cuyo `id_usuario` es 35. `GET` → 200. |
| D14 | ¿El Administrador tiene permisos? | Sí: `modulo1.permisos` confirma `(rol 1, recurso 29, acción 5)` activo. `GET` → 200. |
| D15 | ¿Escenario independiente por actor? | Sí: activos 290 y 294, distintos, con orígenes distintos. |

---

## 4. Ciclo Productor

### ANTES

| Dato | Valor |
|---|---|
| Activo | **290** `QAJE-TRF-CONC`, INDIVIDUAL, especie 40, **ACTIVO** |
| Origen | **48** `Corral QA JE Origen` |
| Destino A | **47** `Corral QA JE Capacidad` |
| Destino B | **51** `Corral QA JE Destino OK` |
| Ocupación origen (48) | **221** |
| Ocupación A (47) | **48** |
| Ocupación B (51) | **2** |
| Historial previo del activo | 1 fila |
| Asociaciones vigentes | **1** |
| Movimientos previos del activo | **0** |

### Sincronización

- **Método:** `threading.Barrier(2)` con dos workers de `ThreadPoolExecutor`; cada worker prepara su petición, espera en la barrera y solo entonces envía el `POST`. Cada worker usa su propia `requests.Session`.
- **Tiempos monotónicos, medidos desde la liberación de la barrera:**

| Petición | Inicio | Fin |
|---|---:|---:|
| A → destino 47 | 0,0040 s | 0,8302 s |
| B → destino 51 | 0,0036 s | 0,8110 s |

- **¿Se confirmó solapamiento?: SÍ.** Ventana de solapamiento real: **0,8070 s**. La aserción `inicio_A < fin_B and inicio_B < fin_A` se cumple; la corrida no fue secuencial.

### Respuestas

| Request | Destino | HTTP | Error/mensaje | Rol |
|---|---:|---:|---|---|
| A | 47 | **201** | `id_movimiento: 27` | **GANADOR** |
| B | 51 | **409** | `TRANSFERENCIA_CONCURRENTE` — *«Existe una operación de transferencia en progreso para el activo 290. Espere a que finalice e intente nuevamente.»* | **PERDEDOR** |

### DESPUÉS

| Dato | Valor |
|---|---|
| Destino ganador | **47** |
| Ubicación final | **47** |
| Asociaciones vigentes | **1**, apuntando a 47 |
| Eventos nuevos | **1** (movimiento 27) |
| Ocupación origen (48) | 221 → **220** (−1) |
| Ocupación ganador (47) | 48 → **49** (+1) |
| Ocupación perdedor (51) | 2 → **2** (**0**) |
| Auditoría | movimiento 27 presente en `vw_rf52_auditoria_transferencias_internas`, usuario 35 |

### V1–V12

| V | Resultado | Evidencia |
|---|---|---|
| V1 | ✅ | Un `201` y un `409`; exactamente un éxito y un conflicto. |
| V2 | ✅ | `id_infraestructura` del activo = 47 = destino ganador. |
| V3 | ✅ | Una única asociación vigente, y apunta a 47. No hay origen+destino ni doble destino. |
| V4 | ✅ | La asociación previa en 48 quedó cerrada exactamente una vez. |
| V5 | ✅ | Movimientos del activo: 0 → 1. |
| V6 | ✅ | Movimiento 27: activo 290, origen 48, destino 47, usuario 35, motivo *«TC-M02-142 concurrencia A»* — el del request ganador. |
| V7 | ✅ | Ocupación origen 221 → 220, una sola vez. |
| V8 | ✅ | Ocupación ganador 48 → 49, una sola vez. |
| V9 | ✅ | Ocupación perdedor 51 sin cambios (2 → 2). |
| V10 | ✅ | Cero movimientos con destino 51 por encima del `max(id_movimiento)` de la línea base. |
| V11 | ✅ | El movimiento 27 aparece en la vista de auditoría de RF-52 con el destino y el usuario correctos. |
| V12 | ✅ | Historial del activo 1 → 2 filas: la traza previa permanece intacta. |

---

## 5. Ciclo Administrador

### ANTES

| Dato | Valor |
|---|---|
| Activo | **294** `QAJE-TRF-REGLAS`, INDIVIDUAL, especie 40, **ACTIVO** |
| Origen | **51** `Corral QA JE Destino OK` |
| Destino A | **48** `Corral QA JE Origen` |
| Destino B | **47** `Corral QA JE Capacidad` |
| Ocupación origen (51) | **2** |
| Ocupación A (48) | **220** |
| Ocupación B (47) | **49** |
| Historial previo del activo | 2 filas |
| Asociaciones vigentes | **1** |
| Movimientos previos del activo | **1** |

### Sincronización

- **Método:** idéntico — `threading.Barrier(2)` y dos workers independientes.
- **Tiempos monotónicos desde la liberación de la barrera:**

| Petición | Inicio | Fin |
|---|---:|---:|
| A → destino 48 | 0,0012 s | 0,7221 s |
| B → destino 47 | 0,0011 s | 0,7297 s |

- **¿Se confirmó solapamiento?: SÍ.** Ventana de solapamiento real: **0,7209 s**.

### Respuestas

| Request | Destino | HTTP | Error/mensaje | Rol |
|---|---:|---:|---|---|
| A | 48 | **409** | `TRANSFERENCIA_CONCURRENTE` — *«Existe una operación de transferencia en progreso para el activo 294…»* | **PERDEDOR** |
| B | 47 | **201** | `id_movimiento: 28` | **GANADOR** |

> En este ciclo ganó la petición **B**, mientras que en el del Productor había ganado la **A**. El test no fijó ningún orden: identificó ganador y perdedor a partir de las respuestas, tal como exige §14 C4.

### DESPUÉS

| Dato | Valor |
|---|---|
| Destino ganador | **47** |
| Ubicación final | **47** |
| Asociaciones vigentes | **1**, apuntando a 47 |
| Eventos nuevos | **1** (movimiento 28) |
| Ocupación origen (51) | 2 → **1** (−1) |
| Ocupación ganador (47) | 49 → **50** (+1) |
| Ocupación perdedor (48) | 220 → **220** (**0**) |
| Auditoría | movimiento 28 presente en `vw_rf52_auditoria_transferencias_internas`, usuario 1 |

### V1–V12

| V | Resultado | Evidencia |
|---|---|---|
| V1 | ✅ | Un `201` y un `409`. |
| V2 | ✅ | `id_infraestructura` del activo = 47 = destino ganador (petición B). |
| V3 | ✅ | Una única asociación vigente, apuntando a 47. |
| V4 | ✅ | La asociación previa en 51 quedó cerrada exactamente una vez. |
| V5 | ✅ | Movimientos del activo: 1 → 2. |
| V6 | ✅ | Movimiento 28: activo 294, origen 51, destino 47, usuario 1, motivo *«TC-M02-142 concurrencia B»*. |
| V7 | ✅ | Ocupación origen 2 → 1, una sola vez. |
| V8 | ✅ | Ocupación ganador 49 → 50, una sola vez. |
| V9 | ✅ | Ocupación perdedor 48 sin cambios (220 → 220). |
| V10 | ✅ | Cero movimientos con destino 48 por encima del `max(id_movimiento)` de la línea base del ciclo. |
| V11 | ✅ | El movimiento 28 aparece en la auditoría de RF-52 con destino 47 y usuario 1. |
| V12 | ✅ | Historial del activo 2 → 3 filas: la traza previa permanece intacta. |

---

## 6. Invariantes finales

| Actor | 1 éxito | 1 E-01 | 1 ubicación | 1 evento nuevo | Δ origen | Δ ganador | Δ perdedor | Resultado |
|---|---|---|---|---|---:|---:|---:|---|
| Productor | ✅ | ✅ | ✅ | ✅ | **−1** | **+1** | **0** | **APROBADO** |
| Administrador | ✅ | ✅ | ✅ | ✅ | **−1** | **+1** | **0** | **APROBADO** |

Invariantes I1–I8 de §17, con `cantidad_transferida = 1` por tratarse de activos INDIVIDUAL:

```text
I1: successful_requests            = 1   ✅ en ambos ciclos
I2: concurrency_rejections         = 1   ✅ en ambos ciclos
I3: current_locations              = 1   ✅ en ambos ciclos
I4: new_successful_transfer_events = 1   ✅ en ambos ciclos
I5: origin_occupancy_delta         = -1  ✅ 221→220 y 2→1
I6: winner_occupancy_delta         = +1  ✅ 48→49 y 49→50
I7: loser_occupancy_delta          =  0  ✅ 51 sin cambios y 48 sin cambios
I8: loser_success_events           =  0  ✅ en ambos ciclos
```

### Verificación global independiente

```sql
SELECT id_movimiento, id_activo_biologico, id_infraestructura_origen, id_infraestructura_destino,
       id_usuario, left(motivo_transferencia, 42), fecha_registro
FROM modulo2.movimientos WHERE id_movimiento > 26 ORDER BY 1;
```

| id_movimiento | activo | origen | destino | usuario | motivo | fecha_registro |
|---:|---:|---:|---:|---:|---|---|
| 27 | 290 | 48 | 47 | 35 | TC-M02-142 concurrencia A | 2026-09-10 10:36:10.978+00 |
| 28 | 294 | 51 | 47 | 1 | TC-M02-142 concurrencia B | 2026-09-10 10:36:34.791+00 |

```sql
SELECT count(*), max(id_movimiento) FROM modulo2.movimientos;   -- 24 | 28   (antes 22 | 26)
```

| Métrica global | Antes | Después | Δ |
|---|---:|---:|---:|
| `modulo2.movimientos` — filas | 22 | 24 | **+2** — exactamente uno por ciclo |
| Ocupación infra 47 | 48 | **50** | +2, los dos ganadores |
| Ocupación infra 48 | 221 | **220** | −1, salida del activo 290 |
| Ocupación infra 51 | 2 | **1** | −1, salida del activo 294 |

Las cuatro peticiones oficiales produjeron **exactamente dos escrituras**, las de los dos ganadores. Ninguna de las dos rechazadas dejó rastro.

---

## 7. Diagnóstico

**¿Fue necesario? NO.**

No hubo desviación: la ejecución fue única y los dos ciclos pasaron todas sus verificaciones a la primera. Ninguna aserción falló, no apareció ningún `HTTP 500` ni ningún `403`, y el estado final es íntegramente consistente.

Las hipótesis de §20 quedaron descartadas de forma preventiva y están sostenidas por las aserciones del propio test:

| # | Hipótesis | Cómo se descartó |
|---|---|---|
| A1 | Las solicitudes fueron secuenciales | Barrera común y tiempos monotónicos: ventanas de solapamiento de **0,807 s** y **0,721 s**. La aserción de solapamiento es bloqueante: si no hubiera habido concurrencia real, el test habría fallado en lugar de aprobar. |
| A2 | Un destino no cumplía C1 | Comprobado por `SELECT` antes de cada ciclo: 47 y 51 con especie 40 (igual a la del activo) y 48 con `id_especie` NULL. |
| A3 | Un destino no cumplía C2 | Los cuatro destinos usados son de tipo `Corral`; se descartaron deliberadamente el Estanque 52 y el Galpón 53. |
| A4 | Un destino no cumplía C3 | Recalculada la ocupación con la fórmula del backend justo antes de cada ciclo: 49 ≤ 50, 3 ≤ 200, 222 ≤ 1000 y 50 ≤ 50. |
| A5 | Destino = origen | Afirmado en la validación previa de los dos destinos. |
| A6 | A y B eran iguales | Afirmado: 47 ≠ 51 y 48 ≠ 47. |
| A7 | Activo no ACTIVO | `SELECT` y `GET` previos: ambos ACTIVO. |
| A8 | Actor sin permiso legítimo | `sub` del JWT verificado contra 35 y 1; permiso `(29, 5)` activo para ambos roles; ningún `403`. |
| A9 | Fecha futura o incorrecta | Se envió la fecha de hoy en las cuatro peticiones; ninguna respuesta mencionó la fecha. |
| A10 | A y B tenían distinto campo inválido | Los dos payloads de cada ciclo son idénticos salvo el destino, y ambos constan en la evidencia. |
| A11 | Variable equivocada | Los payloads realmente enviados se registran en `evidencia_g82.json`. |
| A12 | Se reutilizó un activo ya transferido | El origen se relee de base de datos inmediatamente antes de cada ciclo, no se codifica. |
| A13 | La aserción exigía que ganara A | **Descartada por construcción:** ganador y perdedor se determinan a partir de las respuestas. De hecho ganó A en un ciclo y B en el otro. |
| A14 | Historial consultado antes de terminar ambas | Las verificaciones solo se ejecutan tras `future.result()` de los dos workers. |
| A15 | Contadores con modelo incorrecto | La ocupación se calcula con la misma consulta que usa `infraestructura_m09_adapter`. |
| A16 | El 409 no era E-01 | Afirmado `error_code == 'TRANSFERENCIA_CONCURRENTE'` y que el mensaje contiene *«transferencia en progreso»*. |

---

## 8. VEREDICTO FINAL

# ✅ APROBADO

**Justificación:**

1. Gate completo: repositorio, rama `qa/juan-esteban-m02`, HEAD `41369ea`, backend HTTPS en 200 y PostgreSQL accesible en solo lectura.
2. La base de datos se revisó primero, con la sesión abierta en modo `readonly`; **0 escrituras en SETUP**.
3. Productor y Administrador tienen cada uno un escenario **independiente** y completo, con activos distintos.
4. Cada ciclo dispuso de **dos destinos válidos y distintos**, ambos con C1, C2 y C3 cumplidas y ambos presentes en `GET /transferencias/disponibles`.
5. Se demostró **concurrencia real**: barrera común y solapamiento temporal de 0,807 s y 0,721 s, medido con reloj monotónico.
6. Se ejecutaron **2 ciclos oficiales y 4 POST**.
7. Cada ciclo produjo **exactamente `1 × éxito + 1 × 409`**; ni `200+200` ni `409+409`.
8. Cada `409` corresponde a **E-01** (`TRANSFERENCIA_CONCURRENTE`), con el mensaje de operación en progreso.
9. El ganador se determinó **dinámicamente**, y de hecho fue distinto en cada ciclo.
10. El activo quedó **exclusivamente** en el destino ganador, con una sola asociación vigente.
11. Existe **exactamente un movimiento nuevo** por ciclo, con origen, destino, usuario y motivo del request ganador.
12. El **destino perdedor no cambió** en ninguno de los dos ciclos.
13. La ocupación del origen bajó una sola vez y la del ganador subió una sola vez.
14. **No hay doble asociación, doble evento ni contadores incoherentes.**
15. El historial previo de cada activo permanece intacto.
16. Las dos transferencias exitosas quedan auditadas en `vw_rf52_auditoria_transferencias_internas`.
17. No quedó ninguna verificación obligatoria pendiente. No se invadió ningún escenario de E-02 a E-11 ni la transferencia parcial de lote.

El control de concurrencia de RF-48 —`SELECT … FOR UPDATE NOWAIT` sobre la fila del activo— **cumple el resultado esperado de TC-M02-142 para los dos actores**.

---

## 9. Datos para Registro de Errores

No se detectó ningún defecto. Se registra una observación documental.

### OBS-G82-01 — La ficha enuncia `HTTP 200` y el sistema responde `201`

- **ID sugerido:** OBS-G82-01
- **Descripción:** el resultado esperado de TC-M02-142 enuncia `HTTP 200` para la solicitud ganadora. El contrato OpenAPI declara **`201`** como respuesta de éxito de `POST /activos-biologicos/{id_activo}/transferencias`, y el sistema devuelve **`201`** con el cuerpo `TransferenciaResponse`. Contrato e implementación coinciden entre sí; es el enunciado de la ficha el que difiere.
- **RF:** RF-48 · **Caso/sub-caso:** TC-M02-G82 / TC-M02-142 · **Actor:** ambos
- **Categoría:** documentación del caso · **Equipo responsable:** **Responsable QA** (redacción de la ficha), con confirmación de **Desarrollo Backend** de que `201` es el código previsto
- **Severidad:** **Bajo** — no afecta al comportamiento ni al criterio sustantivo del caso · **Tiempo máximo:** 3 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-15** · **Estado:** Abierto
- **Evidencia:** respuestas de los movimientos 27 y 28 en `evidencia_g82.json`; `responses` del endpoint en `GET /openapi.json`.
- **Impacto en el caso:** ninguno. La prueba exige el criterio sustantivo —exactamente un éxito y un `409` E-01— y verifica además que el éxito llega con el código contractual `201`. No se relajó ninguna comprobación.
- **Causa raíz:** confirmada por QA — la ficha enuncia un código distinto del que declara el contrato.

### Nota operativa — ambiente TEST compartido

No es un hallazgo del producto, pero condiciona la lectura de los contadores globales. Antes de este caso, a las 09:47 UTC, otra sesión creó los movimientos **23** y **24** sobre los activos 292 y 294, ajenos a esta ejecución. Por eso la evidencia de este informe se apoya en **deltas por activo y por infraestructura**, y en la identificación de los movimientos por `motivo_transferencia` e `id_usuario`, y no solo en los totales globales.

### Cambio de estado esperado

Las dos transferencias ganadoras **son el resultado correcto** del caso, no un efecto colateral: §1.I exige que una de las dos solicitudes se complete. Se detallan para trazabilidad:

| Activo | Identificador | Estaba en | Quedó en | Movimiento | Actor |
|---:|---|---:|---:|---:|---|
| 290 | QAJE-TRF-CONC | 48 `Corral QA JE Origen` | 47 `Corral QA JE Capacidad` | 27 | Productor (35) |
| 294 | QAJE-TRF-REGLAS | 51 `Corral QA JE Destino OK` | 47 `Corral QA JE Capacidad` | 28 | Administrador (1) |

Tras el caso, la infraestructura 47 queda con ocupación **50 sobre una capacidad de 50**. Conviene tenerlo presente: cualquier prueba posterior que use 47 como destino incumplirá C3 (E-09), lo cual es correcto pero puede confundirse con un fallo si no se revisa la ocupación primero.

---

## 10. Declaración de cumplimiento

- ✅ No se modificó código fuente. Los archivos de `src/` solo se leyeron para conocer el mecanismo de E-01 y la fórmula de ocupación.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama. El árbol no tiene modificaciones sobre archivos versionados.
- ✅ No se ejecutó SQL de escritura. La conexión de Pytest se abre con `set_session(readonly=True)`, de modo que el propio servidor rechazaría cualquier escritura accidental.
- ✅ **SETUP realizó 0 escrituras.** No se envió ningún POST de sondeo.
- ✅ **Las únicas escrituras fueron los 4 POST oficiales de concurrencia**, de los cuales el sistema aceptó exactamente 2, uno por ciclo. El incremento global de `modulo2.movimientos` es exactamente +2.
- ✅ Se utilizaron **dos destinos válidos y distintos por ciclo**, ambos con C1, C2 y C3 cumplidas; se descartaron deliberadamente el Estanque 52 y el Galpón 53 para no introducir otra causa de rechazo.
- ✅ **Las solicitudes fueron realmente concurrentes**, liberadas desde una `threading.Barrier` común y con solapamiento temporal demostrado. No se usó ningún `sleep` entre A y B.
- ✅ **No se forzó cuál request debía ganar:** el ganador se determina a partir de las respuestas, y fue distinto en cada ciclo.
- ✅ Se verificó el estado final por API y por base de datos, no solo por los códigos HTTP.
- ✅ Se cubrieron Productor y Administrador, cada uno con un activo independiente.
- ✅ No se provocó ninguna caída de infraestructura ni se usó activo CERRADO o BAJA, destino igual al origen, destino incompatible, destino sin capacidad ni fecha futura.
- ✅ No se generaron logs innecesarios: un solo XML, un solo JSON de evidencia y un solo informe.
- ✅ No se inventaron resultados: todo procede del reporte JUnit, de `evidencia_g82.json` o de una consulta `SELECT` reproducible.

---

## 11. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G82/
├── test_tc_m02_g82.py            automatizacion Pytest (herramienta principal)
└── Resultados/
    ├── reporte_tc_m02_g82.xml    JUnit XML consolidado — 2 tests, 2 aprobados
    ├── evidencia_g82.json        payloads, respuestas, tiempos monotonicos y estados ANTES/DESPUES
    └── TC-M02-G82_resultado.md   este informe
```

Comando de reejecución:

```bash
pytest -q test_tc_m02_g82.py --junitxml=Resultados/reporte_tc_m02_g82.xml
```

> **Antes de reejecutar**, revisar que los activos 290 y 294 tengan un origen con dos destinos válidos disponibles: tras esta ejecución ambos están en la infraestructura 47, cuya ocupación es 50 sobre 50. El propio test lo comprueba y fallaría en el SETUP —sin escribir nada— si las precondiciones ya no se cumplieran.

**Ejecución:** 2 ciclos concurrentes · **4 POST oficiales** · **2 tests, 2 aprobados** · 54,6 s · solapamiento demostrado de 0,807 s y 0,721 s · exactamente 2 escrituras aceptadas.
