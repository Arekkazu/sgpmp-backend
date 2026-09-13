# RESULTADO — TC-M02-G83

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **RECHAZADO** |
| Subtipo | — (todas las precondiciones existían; ningún bloqueo) |
| COBERTURA ACTORES | **COMPLETA** |
| SUB-CASOS | 1 aprobado · **2 rechazados** (de 3) |
| VARIANTES | 1 aprobada · **3 rechazadas** (de 4) |
| PETICIONES OFICIALES | **8/8** |
| PERSISTENCIA INDEBIDA | **NO** |
| Equipo responsable | **Desarrollo Backend** |

**Justificación:** las ocho peticiones fueron rechazadas por la regla correcta, con el `error_code` y el mensaje que corresponden a E-02, E-04 y E-05, y ninguna dejó cambios. Sin embargo, **tres de las cuatro variantes responden `HTTP 400` en lugar del `422` que exigen la matriz y el contrato**: solo TC-M02-306 devuelve el código previsto.

| Variante | Regla | HTTP esperado | HTTP obtenido | Resultado |
|---|---|---:|---:|---|
| TC-M02-306 | E-02 activo inexistente | 404 | **404** | ✅ **APROBADO** |
| TC-M02-307 | E-04 activo sin origen | 422 | **400** ⚠ | ❌ **RECHAZADO** |
| TC-M02-308-A | E-05 destino inexistente | 422 | **400** ⚠ | ❌ **RECHAZADO** |
| TC-M02-308-B | E-05 destino INACTIVO | 422 | **400** ⚠ | ❌ **RECHAZADO** |

> Es la **tercera aparición del mismo defecto** en RF-48: ya se reportó como DEF-G80-02 (E-06) y DEF-G81-01 (E-10). Con este caso queda confirmado que afecta a toda la familia de reglas señalizadas con `ValidationError`. Se consolida en DEF-G83-01 con el alcance completo.

---

## 1. Identificación

- **Caso:** TC-M02-G83 · **Sub-casos:** TC-M02-306, TC-M02-307, TC-M02-308 (variantes A y B)
- **RF:** RF-48 — Transferencia interna de activos biológicos · **CU:** CU10C
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** sin modificaciones sobre archivos versionados; solo artefactos de QA sin seguimiento
- **Fecha/hora:** 2026-09-10, 20:33 UTC · duración de la ejecución 9,1 s
- **Ambiente:** TEST desplegado, HTTPS — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Herramienta:** Postman + Newman, reporteros `cli`, `json` y `htmlextra`
- **Evidencia BD:** PostgreSQL TEST `158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, solo lectura

---

## 2. Gate

| Verificación | Resultado |
|---|---|
| Repositorio | ✅ `https://github.com/Arekkazu/sgpmp-backend.git` |
| Rama | ✅ `qa/juan-esteban-m02` (no se cambió de rama) |
| HEAD | ✅ `41369ea` |
| HTTPS | ✅ `GET /openapi.json` → **HTTP 200** |
| PostgreSQL solo lectura | ✅ `SELECT 1;` responde con `member_qa` |
| OpenAPI | ✅ revisado; ver §2.1 |

### 2.1 Contrato revisado y diferencia con la matriz

`POST /activos-biologicos/{id_activo}/transferencias`

| Aspecto | Valor real |
|---|---|
| Body | `infraestructura_origen_id` (int), `infraestructura_destino_id` (int), `fecha_transferencia` (date), `motivo_transferencia` (str) — los cuatro obligatorios |
| Nombre del campo destino | **`infraestructura_destino_id`** |
| Formato de fecha | `date`, `YYYY-MM-DD` |
| Respuestas declaradas | **`201, 401, 403, 404, 409, 422, 500`** |
| ¿Declara `404`? | ✅ sí — el que exige TC-M02-306 |
| ¿Declara `422`? | ✅ sí — el que exigen TC-M02-307 y TC-M02-308 |
| ¿Declara `400`? | ❌ **no** — y sin embargo es el código que devuelven tres de las cuatro variantes |

**Representación de los errores.** El contrato no nombra las etiquetas E-02, E-04 ni E-05; el sistema las materializa con `error_code` propios, que es la representación contractual equivalente y así se documenta:

| Etiqueta de la matriz | `error_code` real |
|---|---|
| E-02 | `ACTIVO_NO_ENCONTRADO` |
| E-04 | `SIN_INFRAESTRUCTURA_ORIGEN` |
| E-05 | `INFRAESTRUCTURA_DESTINO_INVALIDA` |

### 2.2 Orden real de validación (lectura de código)

```text
E-01 concurrencia          → TRANSFERENCIA_CONCURRENTE          ConflictError    (409)
E-02 activo existe         → ACTIVO_NO_ENCONTRADO               NotFoundError    (404) ← TC-M02-306
E-03 activo ACTIVO         → ACTIVO_NO_ACTIVO                   ConflictError    (409)
E-04 origen vigente        → SIN_INFRAESTRUCTURA_ORIGEN         ValidationError  (400) ← TC-M02-307
     origen coincide       → INFRAESTRUCTURA_ORIGEN_INCORRECTA  ValidationError  (400)
E-05 destino existe/activo → INFRAESTRUCTURA_DESTINO_INVALIDA   ValidationError  (400) ← TC-M02-308 A y B
E-06 destino ≠ origen      → DESTINO_IGUAL_ORIGEN               ValidationError  (400)
E-07 C1 especie            → INCOMPATIBILIDAD_ESPECIE           BusinessRuleError (422)
E-09 C3 capacidad          → CAPACIDAD_EXCEDIDA                 BusinessRuleError (422)
```

Dos consecuencias, ambas relevantes para este caso:

1. **El aislamiento está garantizado por el orden.** E-02 es el segundo control del flujo y E-04 y E-05 preceden a E-06, E-07 y E-09. Recibir exactamente `ACTIVO_NO_ENCONTRADO`, `SIN_INFRAESTRUCTURA_ORIGEN` o `INFRAESTRUCTURA_DESTINO_INVALIDA` demuestra que el rechazo se produjo por la regla evaluada y no por otra.
2. **La causa del defecto queda a la vista.** Las reglas que la matriz espera en `422` están señalizadas con `ValidationError`, que la jerarquía de errores del proyecto asigna a `HTTP 400`; solo `BusinessRuleError` produce `422`.

Un detalle del modelo que conviene precisar: **E-04 no consulta la columna `activos_biologicos.id_infraestructura`**, sino la asociación vigente en `historial_infraestructura_activo` (`fecha_fin IS NULL`). Por eso el activo del sub-caso 307 puede tener valor en esa columna y aun así carecer de origen registrado.

---

## 3. SETUP — SOLO LECTURA

**Escrituras SETUP: 0.** La etapa se limitó a `SELECT`, `GET /openapi.json`, `GET /activos-biologicos/{id}`, `GET .../historial`, `GET .../transferencias/disponibles` y los dos `POST /sesiones/` de autenticación.

Todos los recursos pertenecen a la **finca 57** (`Finca QA Juan Esteban`), cuyo `id_usuario` es 35 (Productor); el Administrador (usuario 1, rol 1) tiene alcance global. Ambos actores obtuvieron `HTTP 200` sobre los dos activos utilizados.

### TC-M02-306

- **ID:** `99999`
- **¿Existe?:** **NO**
- **Evidencia:** `SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999;` → **0**. El mayor identificador real es 336. Además, `GET /activos-biologicos/99999` devuelve **404** con `error_code: ACTIVO_NO_ENCONTRADO` para los dos actores, comprobado inmediatamente antes de ejecutar. El ID oficial se usó **sin sustituirlo**.

### TC-M02-307

| Actor | Activo | Estado | ¿Origen vigente? | Acceso |
|---|---:|---|---|---|
| Productor | **287** `QAJE-TRF-SINORIG` | **ACTIVO** | **NO** | ✅ `GET` → 200 |
| Administrador | **287** `QAJE-TRF-SINORIG` | **ACTIVO** | **NO** | ✅ `GET` → 200 |

```sql
SELECT ab.id_activo_biologico, ab.identificador, es.nombre AS estado, ab.id_infraestructura,
       (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
         WHERE h.id_activo_biologico = ab.id_activo_biologico AND h.fecha_fin IS NULL) AS asoc_vigentes,
       (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
         WHERE h.id_activo_biologico = ab.id_activo_biologico) AS n_historial
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos es ON es.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico = 287;
--  287 | QAJE-TRF-SINORIG | ACTIVO | 48 | 0 | 0
```

El activo tiene `id_infraestructura = 48` en su fila, pero **cero filas de historial** y por tanto **cero asociaciones vigentes**, que es exactamente lo que evalúa E-04. Confirmado también por API: su historial no contiene ningún registro de categoría `INFRAESTRUCTURA`. Su identificador, `QAJE-TRF-SINORIG`, indica que es la semilla prevista para este escenario.

El payload envía `infraestructura_origen_id = 48`, una infraestructura real y activa, para que todo lo demás sea válido; E-04 se evalúa antes que la comprobación de coincidencia de origen.

### TC-M02-308-A

- **Activo:** **279** `QAJE-CREC-OK` — ACTIVO, especie 40, con asociación vigente en la infraestructura 48
- **Origen:** **48** `Corral QA JE Origen` — activa, capacidad 1000
- **ID destino inexistente:** **99999**
- **Confirmado inexistente:** **SÍ**

```sql
SELECT count(*) FROM modulo9.infraestructuras WHERE id_infraestructura = 99999;  -- 0
SELECT count(*), max(id_infraestructura) FROM modulo9.infraestructuras;          -- 44 | 61
```

Solo existen 44 infraestructuras y el mayor identificador es **61**, muy por debajo de 99999. La elección del ID se documenta aquí porque la matriz no lo fija.

### TC-M02-308-B

| Actor | Activo | Origen | Destino | Estado | C1 | C2 | C3 |
|---|---:|---:|---:|---|---|---|---|
| Productor | 279 | 48 | **50** `Corral QA JE Inactivo` | **INACTIVO** (`es_activo = false`) | OK | OK | OK |
| Administrador | 279 | 48 | **50** `Corral QA JE Inactivo` | **INACTIVO** (`es_activo = false`) | OK | OK | OK |

```sql
SELECT id_infraestructura, id_finca, nombre, tipo, es_activo, capacidad_maxima, id_especie
FROM modulo9.infraestructuras WHERE NOT es_activo;
--  10 | 1  | Invernadero Norte        | Invernadero | f | NULL | NULL
--  11 | 5  | Galpon Principal         | Galpón      | f | NULL | NULL
--  12 | 6  | Area Test Gap            | Corral      | f | NULL | NULL
--  49 | 57 | Corral QA JE Baja Logica | Corral      | f |   50 | NULL
--  50 | 57 | Corral QA JE Inactivo    | Corral      | f |   50 | NULL
```

Se eligió la **50** porque aísla E-05 limpiamente:

- **existe** y está **INACTIVA** — la única condición inválida;
- **≠ origen** (50 ≠ 48);
- **misma finca** que el activo (57);
- **C1 cumple**: `id_especie` NULL, sin restricción de especie;
- **C2 cumple**: es un `Corral`, tipo adecuado para un bovino INDIVIDUAL;
- **C3 cumple**: capacidad 50 con ocupación 0.

Se descartó la 49 porque, aunque también serviría, tiene ocupación 1 y la 50 es la semilla explícitamente nombrada para este escenario. Las infraestructuras 10, 11 y 12 quedaron descartadas por pertenecer a otras fincas.

### Inventario mínimo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿Existe activo 99999? | **NO** — 0 filas; `GET` → 404 con ambos actores. |
| D2 | ¿Activos ACTIVO sin origen vigente? | 10 en total; en la finca 57, el **287** `QAJE-TRF-SINORIG`. |
| D3 | ¿Activos ACTIVO con origen válido para 308? | Varios en la finca 57; se usó el **279** (origen vigente 48). |
| D4 | ¿Infraestructuras INACTIVAS? | 10, 11, 12 (otras fincas) y **49**, **50** en la finca 57. |
| D5 | ¿ID de infraestructura inexistente? | **99999**. |
| D6 | ¿Confirmado inexistente? | **SÍ** — 0 filas; máximo real 61. |
| D7 | ¿Destino INACTIVO ≠ origen? | Sí: 50 ≠ 48. |
| D8 | ¿Destino INACTIVO en la misma finca? | Sí, finca 57. |
| D9 | ¿C1/C2/C3 válidas para la variante INACTIVA? | Sí: especie NULL, tipo Corral, capacidad 50 con ocupación 0. |
| D10 | ¿El Productor tiene acceso legítimo? | Sí: activos y destinos en la finca 57, cuyo `id_usuario` es 35. `GET` → 200. |
| D11 | ¿El Administrador tiene permiso de transferencia? | Sí: `modulo1.permisos` confirma `(rol 1, recurso 29, acción 5)` activo. |
| D12 | ¿El resto de cada payload puede ser totalmente válido? | Sí: origen real y activo (48), destino válido (51) donde no es la variable bajo prueba, fecha de hoy y motivo no vacío. |

**Línea base:** 26 movimientos (`max(id_movimiento) = 30`) y 255 filas de historial.

---

## 4. TC-M02-306 — activo inexistente

| Actor | Esperado | Obtenido | Error | Persistencia | Resultado |
|---|---|---|---|---|---|
| Productor | 404 E-02 | **404** | `ACTIVO_NO_ENCONTRADO` | NO | **APROBADO** |
| Administrador | 404 E-02 | **404** | `ACTIVO_NO_ENCONTRADO` | NO | **APROBADO** |

```text
El activo biológico con id 99999 no fue encontrado en el sistema.
```

Las ocho verificaciones de §10 se cumplen: `99999` confirmado inexistente antes del POST, actor autenticado y sin `403`, payload válido, `HTTP 404`, error E-02, mensaje que nombra el ID, ninguna transferencia creada y ninguna persistencia. Se comprobó además que el `404` **no proviene del enrutador**: el cuerpo trae `error_code` y no la forma `{"detail":"Not Found"}`, y el contrato declara la ruta.

**Resultado TC-M02-306: APROBADO.**

---

## 5. TC-M02-307 — activo ACTIVO sin infraestructura origen

| Actor | Activo | Esperado | Obtenido | Error | Cambios | Resultado |
|---|---:|---|---|---|---|---|
| Productor | 287 | 422 E-04 | **400** ⚠ | `SIN_INFRAESTRUCTURA_ORIGEN` | NO | **RECHAZADO** |
| Administrador | 287 | 422 E-04 | **400** ⚠ | `SIN_INFRAESTRUCTURA_ORIGEN` | NO | **RECHAZADO** |

```text
El activo QAJE-TRF-SINORIG no tiene una infraestructura origen registrada.
Asocie el activo a una infraestructura antes de realizar la transferencia.
```

De las diez verificaciones de §10 se cumplen nueve: el activo existe y está ACTIVO, no tiene origen vigente, el resto del payload es válido, el error es **E-04**, el mensaje identifica la ausencia de origen e invita a asociar el activo, no se creó transferencia, no apareció ninguna asociación automática y los contadores no cambiaron. **Falla la quinta:** `HTTP = 422` → se obtuvo `400`.

**Resultado TC-M02-307: RECHAZADO** por incumplimiento del código HTTP.

---

## 6. TC-M02-308-A — destino inexistente

| Actor | Activo | Destino inexistente | Esperado | Obtenido | Cambios | Resultado |
|---|---:|---:|---|---|---|---|
| Productor | 279 | **99999** | 422 E-05 | **400** ⚠ | NO | **RECHAZADO** |
| Administrador | 279 | **99999** | 422 E-05 | **400** ⚠ | NO | **RECHAZADO** |

```text
La infraestructura con id 99999 no existe o no está activa.
field: infraestructura_destino_id
```

De las diez verificaciones se cumplen nueve: activo ACTIVO, origen válido, destino confirmado inexistente, resto válido, error **E-05**, mensaje correspondiente, el activo sigue en origen, ninguna transferencia creada y **ninguna asociación al ID inexistente**. **Falla:** `HTTP = 422` → se obtuvo `400`.

**Resultado TC-M02-308-A: RECHAZADO** por incumplimiento del código HTTP.

---

## 7. TC-M02-308-B — destino existente pero INACTIVO

| Actor | Activo | Destino | Estado | Esperado | Obtenido | Cambios | Resultado |
|---|---:|---:|---|---|---|---|---|
| Productor | 279 | **50** | **INACTIVO** | 422 E-05 | **400** ⚠ | NO | **RECHAZADO** |
| Administrador | 279 | **50** | **INACTIVO** | 422 E-05 | **400** ⚠ | NO | **RECHAZADO** |

```text
La infraestructura con id 50 no existe o no está activa.
field: infraestructura_destino_id
```

De las doce verificaciones se cumplen once: activo ACTIVO, origen válido, destino existente, destino INACTIVO, destino ≠ origen, resto del escenario válido, error **E-05**, mensaje correspondiente al destino no activo, ninguna transferencia creada, asociaciones sin cambios y contadores sin cambios. **Falla:** `HTTP = 422` → se obtuvo `400`.

> **Observación de contenido.** El mensaje dice *«no existe o no está activa»*, sin distinguir cuál de los dos casos se dio. Es aceptable —la matriz enuncia literalmente esa misma frase para las dos variantes— y se menciona solo como nota: un mensaje que precisara el motivo ayudaría al usuario a corregir la entrada. No es un defecto ni afecta al veredicto.

**Resultado TC-M02-308-B: RECHAZADO** por incumplimiento del código HTTP.

---

## 8. No persistencia

| Actor | Variante | Ubicación | Historial | Asociación | Ocupación |
|---|---|---|---|---|---|
| Productor | 306 | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO |
| Productor | 307 | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO |
| Productor | 308-A | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO |
| Productor | 308-B | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO |
| Administrador | 306 | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO |
| Administrador | 307 | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO |
| Administrador | 308-A | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO |
| Administrador | 308-B | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO | SIN CAMBIO |

Tras cada petición, la colección relee el activo y afirma que conserva su estado y su ubicación; para TC-M02-306 relee además `GET /activos-biologicos/99999` y comprueba que sigue devolviendo 404. Verificación final independiente en base de datos:

```sql
SELECT ab.id_activo_biologico, ab.identificador, es.nombre AS estado, ab.id_infraestructura,
       (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
         WHERE h.id_activo_biologico = ab.id_activo_biologico) AS n_historial,
       (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
         WHERE h.id_activo_biologico = ab.id_activo_biologico AND h.fecha_fin IS NULL) AS vigentes,
       (SELECT count(*) FROM modulo2.movimientos m
         WHERE m.id_activo_biologico = ab.id_activo_biologico) AS n_movimientos
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos es ON es.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico IN (279, 287);
```

| activo | identificador | estado | infra | historial | vigentes | movimientos |
|---:|---|---|---:|---:|---:|---:|
| 279 | QAJE-CREC-OK | ACTIVO | 48 | 1 | 1 | **0** |
| 287 | QAJE-TRF-SINORIG | ACTIVO | 48 | **0** | **0** | **0** |

El activo 287 **sigue sin ninguna asociación**: el rechazo no creó una automáticamente, que es justamente la verificación 9 de TC-M02-307.

```sql
-- No se creó el activo ni la infraestructura inexistentes
SELECT count(*) FROM modulo2.activos_biologicos  WHERE id_activo_biologico  = 99999;  -- 0
SELECT count(*) FROM modulo9.infraestructuras    WHERE id_infraestructura   = 99999;  -- 0

-- Ningún movimiento hacia los destinos inválidos
SELECT count(*) FROM modulo2.movimientos WHERE id_infraestructura_destino IN (99999, 50);  -- 0

-- Totales sin cambios respecto de la línea base
SELECT count(*), max(id_movimiento) FROM modulo2.movimientos;                    -- 26 | 30
SELECT count(*), max(id_historial)  FROM modulo2.historial_infraestructura_activo; -- 255 | 291

-- La infraestructura 50 sigue inactiva: la prueba no la reactivó
SELECT id_infraestructura, es_activo FROM modulo9.infraestructuras WHERE id_infraestructura = 50;  -- 50 | f
```

| Métrica | Antes | Después | Δ |
|---|---:|---:|---:|
| `modulo2.movimientos` — filas | 26 | 26 | **0** |
| `modulo2.movimientos` — `max(id_movimiento)` | 30 | 30 | **0** |
| `historial_infraestructura_activo` — filas | 255 | 255 | **0** |
| Activo 99999 | no existe | no existe | **0** |
| Infraestructura 99999 | no existe | no existe | **0** |
| Infraestructura 50 | inactiva | inactiva | **0** |

**Ninguna de las ocho peticiones dejó rastro.**

---

## 9. Diagnóstico

**¿Fue necesario? SÍ**, para las tres variantes rechazadas, que comparten una única causa.

- **Variantes:** TC-M02-307, TC-M02-308-A y TC-M02-308-B. **Actores:** los dos, con resultado idéntico.
- **Esperado:** `HTTP 422` con E-04 y E-05.
- **Obtenido:** `HTTP 400` con los `error_code` correctos (`SIN_INFRAESTRUCTURA_ORIGEN` e `INFRAESTRUCTURA_DESTINO_INVALIDA`), los mensajes previstos, el campo señalado y sin persistencia.
- **Reproducibilidad: 3/3** para TC-M02-308-B — Productor, Administrador y una repetición diagnóstica con `curl` sobre HTTPS que devolvió el mismo `400` sin alterar nada (`max(id_movimiento)` siguió en 30 y el activo 279 en la infraestructura 48). Las otras dos variantes son 2/2, un actor cada uno.

**Hipótesis descartadas (§14):**

| # | Hipótesis | Descarte |
|---|---|---|
| A1 | 99999 sí existe | `SELECT` → 0 filas y `GET` → 404 inmediatamente antes de cada POST; afirmado en la colección. |
| A2 | La URL no envió 99999 | Afirmado sobre `pm.request.url`, que contiene `/activos-biologicos/99999/transferencias`. |
| A3 | El activo de 307 sí tenía origen | 0 filas de historial y 0 asociaciones vigentes por `SELECT`; el historial por API no muestra ningún registro de infraestructura. |
| A4 | El activo de 307 no estaba ACTIVO | `SELECT` y `GET` previos: `nombre_estado = ACTIVO`. |
| A5 | El destino «inexistente» sí existe | `SELECT` → 0 filas; solo hay 44 infraestructuras y el máximo es 61. |
| A6 | El destino «inactivo» está ACTIVO | `SELECT` → `es_activo = false`; además no figura en `/transferencias/disponibles`, que solo lista activas. |
| A7 | El destino INACTIVO también falla C1 | Descartada: `id_especie` NULL, sin restricción de especie. |
| A8 | También falla C2 | Descartada: es un `Corral`, tipo adecuado para un bovino INDIVIDUAL. |
| A9 | También falla C3 | Descartada: capacidad 50 con ocupación 0. |
| A10 | Destino = origen | Descartada: 50 ≠ 48, 99999 ≠ 48 y 51 ≠ 48; afirmado en cada petición. |
| A11 | Fecha futura | Se envió la fecha de hoy; ninguna respuesta mencionó la fecha. |
| A12 | Actor o token incorrecto | `sub` del JWT afirmado contra 35 y 1; ningún `403`. |
| A13 | Recurso fuera de alcance | Todo en la finca 57; `GET` → 200 con los dos actores. |
| A14 | Variable Postman incorrecta | Los cuerpos y URLs realmente enviados constan en el reporte JSON. |
| A15 | **Assertion incorrecta** | **Descartada:** la matriz exige `422` para E-04 y E-05, y el contrato declara `201, 401, 403, 404, 409, 422, 500` **sin `400`**. Las dos fuentes coinciden en contra del código obtenido. |
| A16 | Artefacto Newman | Descartada por la reproducción con `curl`. |

- **Atribución: DEFECTO DEL PRODUCTO**, limitado al código HTTP. La lógica de negocio es correcta en las tres variantes.
- **Causa raíz: confirmada por QA.** E-04 y E-05 se señalizan con `ValidationError`, que la jerarquía de errores del proyecto asigna a `HTTP 400`; solo `BusinessRuleError` produce `422`. Es el mismo mecanismo que ya produjo DEF-G80-02 (E-06) y DEF-G81-01 (E-10).

---

## 10. VEREDICTO FINAL

# ❌ RECHAZADO

**Justificación:** el gate se completó, el SETUP no realizó ninguna escritura y las cuatro precondiciones oficiales existían en TEST sin necesidad de fabricar nada: `99999` confirmado inexistente como activo y como infraestructura, un activo ACTIVO realmente sin origen y una infraestructura existente pero inactiva que aísla E-05. Se ejecutaron las **8 peticiones oficiales** con ambos actores; las ocho fueron rechazadas por la regla correcta, con el `error_code` y el mensaje previstos, y **ninguna dejó cambios**. Sin embargo, **tres de las cuatro variantes incumplen el código HTTP exigido por la matriz y declarado por el contrato**.

### DEF-G83-01 — E-04 y E-05 devuelven HTTP 400 en lugar de 422

```text
TC-M02-G83 / TC-M02-307, TC-M02-308-A y TC-M02-308-B — RECHAZADO

Actores: Productor (usuario 35) y Administrador (usuario 1). Resultado idéntico en ambos.

Variante TC-M02-307
  Activo: 287 QAJE-TRF-SINORIG · ACTIVO · sin asociación vigente de infraestructura
  Origen enviado: 48 Corral QA JE Origen (real y activa)
  Destino: 51 Corral QA JE Destino OK (real, activa, distinta del origen, C1/C2/C3 OK)
  Precondición: el activo existe, está ACTIVO y no tiene origen registrado.

Variante TC-M02-308-A
  Activo: 279 QAJE-CREC-OK · ACTIVO · asociación vigente en 48
  Origen: 48 · Destino: 99999, confirmado inexistente (44 infraestructuras, máximo 61)

Variante TC-M02-308-B
  Activo: 279 QAJE-CREC-OK · ACTIVO · asociación vigente en 48
  Origen: 48 · Destino: 50 Corral QA JE Inactivo, existente pero es_activo = false,
  distinto del origen, misma finca 57, C1 OK (especie NULL), C2 OK (Corral),
  C3 OK (capacidad 50, ocupación 0).

Payload: en las tres variantes, origen real y activo, destino según la variante,
  fecha de hoy y motivo no vacío. Ninguna otra condición inválida.

Esperado:
  HTTP 422 UNPROCESSABLE ENTITY con E-04 (TC-M02-307) y E-05 (TC-M02-308 A y B),
  sin cambios en ubicación, asociación, historial ni ocupación.

Obtenido:
  HTTP 400 BAD REQUEST en las tres variantes, con los error_code correctos
  (SIN_INFRAESTRUCTURA_ORIGEN e INFRAESTRUCTURA_DESTINO_INVALIDA), los mensajes
  previstos por la matriz y el campo infraestructura_destino_id señalado donde aplica.
  La regla de negocio se aplica bien; lo que incumple es el código HTTP, que además
  no está declarado en el contrato de este endpoint.

Persistencia: NO. SELECT confirma 0 movimientos nuevos, 0 filas de historial nuevas,
  el activo 287 sigue sin asociación, el activo 279 sigue en la infraestructura 48,
  no se creó el activo ni la infraestructura 99999 y la infraestructura 50 sigue inactiva.

Reproducibilidad: 3/3 en TC-M02-308-B (dos actores más repetición con curl sobre HTTPS);
  2/2 en TC-M02-307 y TC-M02-308-A.
Atribución: DEFECTO DEL PRODUCTO, limitado al código HTTP.
Causa raíz: confirmada por QA — E-04 y E-05 se señalizan con ValidationError, que la
  jerarquía de errores del proyecto asigna a HTTP 400, mientras que las reglas resueltas
  con BusinessRuleError responden 422. El contrato OpenAPI declara 201, 401, 403, 404,
  409, 422 y 500, y no incluye 400.
Categoría: HTTP_COM.
Equipo responsable: Desarrollo Backend.
Severidad: Medio.
Tiempo máximo: 2 días hábiles.
Fecha límite: 2026-09-14.
Impacto: un cliente construido a partir del contrato no contempla un 400 en este endpoint
  y trataría estos rechazos como errores inesperados en vez de como validaciones de negocio.
  Con este caso, el alcance confirmado del defecto abarca E-04, E-05, E-06 y E-10, es decir
  cuatro de las reglas de RF-48; queda por confirmar INFRAESTRUCTURA_ORIGEN_INCORRECTA,
  que comparte el mismo mecanismo pero no se ha probado.
```

---

## 11. Datos para Registro de Errores

### DEF-G83-01 — La familia de errores `ValidationError` de RF-48 responde 400 y no 422

- **ID sugerido:** DEF-G83-01
- **Descripción:** las reglas E-04 (`SIN_INFRAESTRUCTURA_ORIGEN`) y E-05 (`INFRAESTRUCTURA_DESTINO_INVALIDA`, en sus dos variantes: destino inexistente y destino inactivo) rechazan correctamente y con el mensaje previsto, pero responden `HTTP 400`. La matriz exige `422` y el contrato OpenAPI no declara `400` para este endpoint.
- **RF:** RF-48 · **Caso/sub-caso:** TC-M02-G83 / TC-M02-307, TC-M02-308-A y TC-M02-308-B · **Actor:** Productor y Administrador (ambos)
- **Categoría:** `HTTP_COM` · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Medio** · **Tiempo máximo:** 2 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-14** · **Estado:** Abierto
- **Evidencia:** [reporte_tc_m02_g83.json](reporte_tc_m02_g83.json) y [reporte_tc_m02_g83.html](reporte_tc_m02_g83.html), las seis peticiones afectadas; reproducción con `curl` en §9; consultas `SELECT` de §8.
- **Causa raíz:** confirmada por QA — `ValidationError` → 400 frente a `BusinessRuleError` → 422.
- **Consolidación:** este hallazgo **engloba** los previamente reportados como **DEF-G80-02** (E-06 `DESTINO_IGUAL_ORIGEN`) y **DEF-G81-01** (E-10 fecha futura, validada en el DTO). Se recomienda resolverlos de forma conjunta con una única decisión sobre el mapeo de errores de RF-48:

| Regla | `error_code` | HTTP actual | HTTP esperado | Caso que lo detectó |
|---|---|---:|---:|---|
| E-04 | `SIN_INFRAESTRUCTURA_ORIGEN` | 400 | 422 | **G83 / TC-M02-307** |
| — | `INFRAESTRUCTURA_ORIGEN_INCORRECTA` | 400 | 422 *(presunto)* | no probado |
| E-05 | `INFRAESTRUCTURA_DESTINO_INVALIDA` | 400 | 422 | **G83 / TC-M02-308 A y B** |
| E-06 | `DESTINO_IGUAL_ORIGEN` | 400 | 422 | G80 / TC-M02-134 |
| E-10 | *(validación del DTO)* | 400 | 422 | G81 / TC-M02-140 |
| E-02 | `ACTIVO_NO_ENCONTRADO` | 404 | 404 | ✅ correcto |
| E-03 | `ACTIVO_NO_ACTIVO` | 409 | 409 | ✅ correcto |
| E-01 | `TRANSFERENCIA_CONCURRENTE` | 409 | 409 | ✅ correcto |
| E-07 | `INCOMPATIBILIDAD_ESPECIE` | 422 | 422 | ✅ correcto |
| E-09 | `CAPACIDAD_EXCEDIDA` | 422 | 422 | ✅ correcto |

### OBS-G83-02 — El mensaje de E-05 no distingue entre destino inexistente e inactivo

- **ID sugerido:** OBS-G83-02
- **Descripción:** las dos variantes de E-05 devuelven el mismo texto, *«La infraestructura con id N no existe o no está activa»*, sin precisar cuál de los dos casos se dio. Coincide con el enunciado literal de la matriz, de modo que **no es un incumplimiento**; se registra como sugerencia de mejora: distinguir ambos motivos ayudaría al usuario a corregir la entrada.
- **RF:** RF-48 · **Caso/sub-caso:** TC-M02-G83 / TC-M02-308 · **Actor:** ambos
- **Categoría:** usabilidad del mensaje · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Bajo** · **Tiempo máximo:** 3 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-15** · **Estado:** Abierto
- **Impacto en el caso:** ninguno. No afecta al veredicto.
- **Causa raíz:** confirmada por QA — un único `ValidationError` cubre las dos condiciones en `obtener_activa`.

### Nota operativa — ambiente TEST compartido

Entre TC-M02-G82 y este caso, los totales globales pasaron de 24 a 26 movimientos y de 251 a 255 filas de historial por actividad de **otra sesión de QA**, ajena a esta ejecución. Por eso la evidencia de no persistencia se apoya en **deltas por activo** y en consultas dirigidas (movimientos hacia los destinos inválidos, existencia de los IDs 99999), además de en los totales tomados inmediatamente antes y después de la corrida.

---

## 12. Declaración de cumplimiento

- ✅ No se modificó código fuente. Los archivos de `src/` solo se leyeron para conocer el orden de validación y el mapeo de errores.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama. El árbol no tiene modificaciones sobre archivos versionados.
- ✅ No hubo SQL de escritura. Todas las sentencias fueron `SELECT` con el usuario `member_qa`.
- ✅ **SETUP = 0 escrituras.**
- ✅ **No se borró ningún activo** para fabricar TC-M02-306: el ID 99999 nunca existió y el total de activos no cambió.
- ✅ **No se removió ninguna asociación** para fabricar TC-M02-307: el activo 287 ya carecía de historial de infraestructura, y sigue igual.
- ✅ **No se desactivó ninguna infraestructura** para fabricar TC-M02-308-B: la 50 ya estaba inactiva, y sigue inactiva.
- ✅ **Los IDs inexistentes fueron comprobados** por `SELECT` y por `GET` antes de usarse; no se sustituyó ningún ID oficial.
- ✅ No se introdujo fecha futura, C1/C2/C3 inválidas, destino igual al origen ni ninguna otra condición negativa: cada petición aisló una sola causa de rechazo.
- ✅ No se aceptó ningún 404/422 como aprobación sin confirmar la regla: cada respuesta se verificó por `error_code`, por mensaje y por exclusión explícita de las demás reglas de RF-48.
- ✅ Productor y Administrador cubiertos en las cuatro variantes; ninguno recibió `403`.
- ✅ Ninguna petición dejó persistencia parcial.
- ✅ No se generó ningún `.log` por consulta.
- ✅ No se inventaron resultados: todo procede del reporte de Newman, de la reproducción con `curl` o de una consulta `SELECT` reproducible.

---

## 13. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G83/
├── construir_coleccion.cjs        generador determinista de la colección
├── test_tc_m02_g83.json           colección Postman (00-SETUP-LECTURA, 01-CASO-PRINCIPAL, 02-DIAGNOSTICO)
└── Resultados/
    ├── reporte_tc_m02_g83.html    reporte Newman (htmlextra)
    ├── reporte_tc_m02_g83.json    reporte Newman (json), con cuerpos de petición y respuesta
    └── TC-M02-G83_resultado.md    este informe
```

Un solo HTML, un solo JSON, un solo informe. No se generaron logs independientes por actor ni por consulta. La carpeta `02-DIAGNOSTICO` quedó vacía: el diagnóstico se resolvió con el contrato, el reporte JSON, la lectura de código, una reproducción con `curl` y consultas `SELECT`.

**Ejecución:** 24 peticiones · 24 scripts de prueba · **134 aserciones, 6 fallidas** · 9,1 s · **8 peticiones oficiales**. Las 6 aserciones fallidas son exactamente las del código HTTP en las tres variantes rechazadas, dos por variante; todas las demás —códigos de error, mensajes, aislamiento y no persistencia— pasaron.
