# RESULTADO — TC-M02-G48

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **APROBADO** |
| Subtipo | — |
| COBERTURA ACTORES | COMPLETA |
| SUB-CASOS | 2/2 |
| PETICIONES OFICIALES | 6/6 |
| PERSISTENCIA INDEBIDA | NO |
| Equipo responsable | — (aprobado). Quedan tres observaciones no bloqueantes en §10. |

**Justificación en una frase:** con el ID oficial `99999` confirmado inexistente y tres activos `CERRADO` legítimos, los tres actores obtuvieron `HTTP 404 / ACTIVO_NO_ENCONTRADO` y `HTTP 409 / ESTADO_NO_PERMITE_EVENTOS` respectivamente, sin que se creara ningún activo ni ningún evento.

---

## 1. Identificación

- **Caso:** TC-M02-G48
- **Sub-casos:** TC-M02-304 (activo inexistente), TC-M02-305 (activo no ACTIVO)
- **RF:** RF-40 — Registro de eventos de crecimiento
- **CU:** CU06
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** sin modificaciones sobre archivos versionados; solo artefactos de QA sin seguimiento
- **Fecha/hora:** 2026-09-10, 09:34 UTC · duración de la ejecución 8,6 s
- **Ambiente:** TEST desplegado, HTTPS — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Herramienta:** Postman + Newman (`newman run test_tc_m02_g48.json`), reporteros `cli`, `json` y `htmlextra`
- **Evidencia BD:** PostgreSQL TEST `158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, solo lectura

---

## 2. Gate

| Verificación | Resultado |
|---|---|
| Repositorio | ✅ `https://github.com/Arekkazu/sgpmp-backend.git` |
| Rama | ✅ `qa/juan-esteban-m02` (no se cambió de rama) |
| HEAD | ✅ `41369ea` |
| HTTPS backend | ✅ `GET /openapi.json` → **HTTP 200** |
| PostgreSQL solo lectura | ✅ `SELECT 1;` responde con `member_qa` |
| OpenAPI | ✅ contrato revisado, con una discrepancia documentada en §2.1 |

### 2.1 Contrato revisado y discrepancia con la ficha

`POST /activos-biologicos/{id_activo}/eventos/crecimiento`:

- La ruta **existe** y está declarada en el contrato. Esto es requisito de la regla crítica de §4.1: descarta que un `404` pueda atribuirse a un endpoint mal escrito.
- Respuestas declaradas: **`201, 400, 401, 403, 404, 422`**.
- El `404` sí está declarado, con esquema `ErrorResponse` (`error_code`, `message`, `fields`, `timestamp`).

> ### ⚠ DISCREPANCIA DOCUMENTADA
>
> **El contrato OpenAPI no declara `409`**, pese a que la ficha de TC-M02-305 exige `HTTP 409 CONFLICT` y a que la implementación efectivamente lo devuelve (`ConflictError`, HTTP 409, en el caso de uso).
>
> No se cambió la expectativa: la aserción sigue exigiendo `409` conforme a la ficha, y el sistema lo cumple. Lo que falta es la **declaración** del código en el contrato. Registrado como OBS-G48-02, sin efecto sobre el veredicto.

### 2.2 Orden de validación del endpoint

Leído en `registrar_evento_crecimiento_use_case.py` para garantizar el aislamiento exigido por §11:

```text
1. obtener_por_id(id_activo) → None  →  NotFoundError  ACTIVO_NO_ENCONTRADO      (404)  ← TC-M02-304
2. activo.id_estado != ACTIVO        →  ConflictError  ESTADO_NO_PERMITE_EVENTOS (409)  ← TC-M02-305
3. fase productiva activa            →  SIN_FASE_ACTIVA
4. fecha del evento                  →  FECHA_FUTURA / fecha anterior
5. tipo_agregacion en INDIVIDUAL     →  AGREGACION_NO_PERMITIDA
6. tipo_medicion configurado         →  TIPO_MEDICION_NO_CONFIGURADO
7. valor dentro de rango             →  VALOR_FUERA_DE_RANGO
```

Las dos reglas de G48 son **los dos primeros controles**, por delante de toda regla de G44, G45 y G46. Esto tiene una consecuencia probatoria directa: recibir exactamente `ACTIVO_NO_ENCONTRADO` o `ESTADO_NO_PERMITE_EVENTOS` demuestra que el rechazo se produjo **por la regla que G48 evalúa** y no por ninguna otra precondición, que es justamente lo que advierten §4.1 y §4.2.

---

## 3. Revisión previa — SOLO LECTURA

### TC-M02-304

- **ID oficial:** `99999`
- **¿Existe en BD?:** **NO**
- **Resultado SELECT:** `SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999;` → **0 filas**
- **Comprobación complementaria:** el mayor identificador realmente existente es **336**, sobre un total de **259** activos; `99999` queda muy por encima del rango asignado.
- **Comprobación por API, con cada actor:** `GET /activos-biologicos/99999` → **404** con `error_code: ACTIVO_NO_ENCONTRADO`.
- **¿Precondición válida?:** **SÍ.** El ID oficial se usó sin sustituirlo.

### TC-M02-305

La ficha da prioridad al estado `CERRADO`. **Los tres actores tienen un activo `CERRADO` legítimo**, de modo que **no fue necesario recurrir a la alternativa `BAJA`** que la ficha admite.

| Actor | Activo | Identificador | Tipo | Estado | Finca/unidad | Acceso legítimo |
|---|---:|---|---|---|---|---|
| Productor (usuario 35) | **288** | `QAJE-CREC-CERRADO` | INDIVIDUAL | **CERRADO** (`id_estado = 5`) | finca 57 · infra 48 | ✅ `GET` → 200 |
| Veterinario (usuario 3) | **329** | `QAJE-RF40-CERRADO-VET` | INDIVIDUAL | **CERRADO** (`id_estado = 5`) | finca 64 · infra 60 | ✅ `GET` → 200 |
| Ingeniero de campo (usuario 4) | **336** | `QAJE-RF40-CERRADO-ING` | INDIVIDUAL | **CERRADO** (`id_estado = 5`) | finca 65 · infra 61 | ✅ `GET` → 200 |

Ningún actor usó un recurso ajeno: cada activo pertenece a una finca cuyo `id_usuario` es el propio actor, según `SELECT id_finca FROM modulo9.fincas WHERE id_usuario = :id`, que es el mismo criterio que aplica `AlcanceFincaAdapter`. Esto satisface la restricción 15: ningún `403` intervino en la interpretación de los resultados.

**Escrituras SETUP: 0.** La etapa se limitó a `SELECT`, `GET /openapi.json`, `GET /activos-biologicos/{id}`, `GET .../historial` y los tres `POST /sesiones/` de autenticación, que no crean datos de dominio.

### 3.1 Inventario mínimo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿El ID 99999 existe? Debe ser NO. | **NO.** 0 filas en `modulo2.activos_biologicos`; `GET` → 404 con los tres actores. |
| D2 | ¿Qué activos existen en estado CERRADO? | Dentro del alcance de los tres actores: **288** (Productor), **329** (Veterinario), **336** (Ingeniero). |
| D3 | ¿Qué activos existen en estado BAJA? | **286** `QAJE-IND-BAJA`, del Productor. No fue necesario usarlo: existía un CERRADO para los tres actores. |
| D4 | ¿Qué activo no ACTIVO pertenece legítimamente al Productor? | 288 (CERRADO). También 286 (BAJA) y 284 (INACTIVO). |
| D5 | ¿Qué activo no ACTIVO pertenece legítimamente al Veterinario? | 329 (CERRADO). |
| D6 | ¿Qué activo no ACTIVO pertenece legítimamente al Ingeniero? | 336 (CERRADO). |
| D7 | ¿Existen y están activas las cuentas de los tres actores? | Sí, con la salvedad de §3.3. Los tres logins devolvieron 200 y el `sub` del JWT coincide con 35, 3 y 4. |
| D8 | ¿Qué finca/unidad tiene cada actor? | Usuario 35 → finca 57 · usuario 3 → fincas 38 y 64 · usuario 4 → finca 65. |
| D9 | ¿Qué combinación válida de medición/valor/unidad se utilizará? | `PESO` / `250` / `kg`. Los tres activos son de la especie 40, que tiene `PESO`/`kg` configurado en `modulo9.metricas_produccion` con `aplica_a_tipo_activo = 'AMBOS'` y rango 0,1 – 2000. |
| D10 | ¿Qué fecha válida puede enviarse sin introducir otra condición negativa? | El instante actual menos 2 minutos: no futura (el backend rechaza con `FECHA_FUTURA`) y posterior a cualquier evento previo. Los tres activos CERRADO no tienen ningún evento de crecimiento previo. |
| D11 | ¿Qué exige `tipo_agregacion` según el tipo de cada activo? | Los tres son `INDIVIDUAL`, en los que `tipo_agregacion` **no aplica** (`AGREGACION_NO_PERMITIDA`). Por eso el payload lo **omite**. Para `99999`, al no existir el activo no hay tipo asociado; se usó el mismo payload, de modo que el ID es la única diferencia entre ambos sub-casos. |

### 3.2 Consultas de la revisión previa

```sql
-- D1: el ID oficial 99999 no corresponde a ningún activo real
SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999;   -- 0
SELECT max(id_activo_biologico), count(*) FROM modulo2.activos_biologicos;           -- 336 | 259

-- D2-D6: activos no ACTIVO dentro del alcance legítimo de cada actor
SELECT f.id_usuario AS actor, f.id_finca, ab.id_activo_biologico AS activo,
       ab.identificador, ab.tipo, e.nombre AS estado, ab.id_especie
FROM modulo2.activos_biologicos ab
JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
JOIN modulo9.fincas f          ON f.id_finca = i.id_finca
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = ab.id_estado
WHERE f.id_usuario IN (3, 4, 35) AND e.nombre <> 'ACTIVO'
ORDER BY f.id_usuario, e.nombre, ab.id_activo_biologico;
```

| actor | finca | activo | identificador | tipo | estado |
|---:|---:|---:|---|---|---|
| 3 | 64 | 329 | QAJE-RF40-CERRADO-VET | INDIVIDUAL | **CERRADO** |
| 4 | 65 | 336 | QAJE-RF40-CERRADO-ING | INDIVIDUAL | **CERRADO** |
| 35 | 57 | 286 | QAJE-IND-BAJA | INDIVIDUAL | BAJA |
| 35 | 57 | 288 | QAJE-CREC-CERRADO | INDIVIDUAL | **CERRADO** |
| 35 | 57 | 284 | QAJE-TRF-NOACT | INDIVIDUAL | INACTIVO |

```sql
-- Línea base: conteos y totales antes de las seis peticiones
SELECT count(*) FROM modulo2.eventos_activos WHERE id_activo_biologico = 99999;      -- 0
SELECT ab.id_activo_biologico, e.nombre AS estado,
       (SELECT count(*) FROM modulo2.eventos_activos ea
          JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
         WHERE ea.id_activo_biologico = ab.id_activo_biologico) AS eventos_crecimiento
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico IN (288, 329, 336);
--  288 | CERRADO | 0
--  329 | CERRADO | 0
--  336 | CERRADO | 0
SELECT count(*), max(id_eventos) FROM modulo2.eventos_activos;                        -- 106 | 240
```

### 3.3 Salvedad de credenciales del Veterinario — resuelta sin crear datos

El paquete indica `juan.carlos@email.com`. Ese correo no existe en `modulo1.usuarios` y su login devuelve `HTTP 401 / CREDENCIALES_INVALIDAS`. La cuenta sí existe: usuario **id 3, rol 3 (Veterinario)**, correo vigente `juan.carlos.qa133@sgpmp-test.com`, misma contraseña. Es deriva de la credencial documentada, no falta de datos. Se usó el correo vigente; **no se creó ni modificó ninguna cuenta**. Registrado como OBS-G48-01.

---

## 4. Payload base válido

Idéntico en los seis casos: la **única diferencia entre las peticiones es el activo destino**, que es exactamente lo que G48 evalúa.

| Campo | Valor |
|---|---|
| `tipo_medicion` | `PESO` |
| `valor_medicion` | `250` (positivo y dentro del rango 0,1 – 2000 de la especie 40) |
| `unidad_medida` | `kg` (unidad permitida para `PESO`) |
| `fecha` | instante actual menos 2 min (≈ 2026-09-10T09:34:4xZ): válida y no futura |
| `descripcion` | texto identificador del sub-caso y actor |
| `tipo_agregacion` | **omitido** — no aplica a activos INDIVIDUAL |
| demás campos | ninguno más es obligatorio para INDIVIDUAL según el contrato |

Aislamiento verificado por aserción sobre el cuerpo realmente enviado en cada una de las seis peticiones (`pm.request.body.raw`), incluida la comprobación de que `tipo_agregacion` **no** está presente. No se introdujo fecha anterior, fase inválida, unidad incompatible, valor negativo, `tipo_agregacion` incorrecto ni XSS.

---

## 5. TC-M02-304 — activo inexistente

| Actor | ID | HTTP esperado | HTTP obtenido | Mensaje | ¿Persistió? | Resultado |
|---|---:|---:|---:|---|---|---|
| Productor | 99999 | 404 | **404** | `ACTIVO_NO_ENCONTRADO` — *El activo biológico con id 99999 no existe.* | NO | **APROBADO** |
| Veterinario | 99999 | 404 | **404** | idéntico | NO | **APROBADO** |
| Ingeniero de campo | 99999 | 404 | **404** | idéntico | NO | **APROBADO** |

Verificaciones de la sección 14 cubiertas por aserción, para cada actor:

1. `99999` fue confirmado inexistente **antes** de ejecutar (`GET` → 404 con `ACTIVO_NO_ENCONTRADO`, por cada actor); ✅
2. el actor está autenticado (cabecera `Authorization: Bearer …` verificada en la petición real); ✅
3. el payload es válido y la URL apunta realmente a `/activos-biologicos/99999/eventos/crecimiento`; ✅
4. `HTTP = 404`; ✅
5. el mensaje corresponde a activo inexistente: contiene *«no existe»* y el propio ID `99999`; ✅
6. el error corresponde **realmente** a activo inexistente y no a una ruta incorrecta: el cuerpo trae `error_code: ACTIVO_NO_ENCONTRADO` y **no** la forma `{"detail":"Not Found"}` con que responde el enrutador ante una ruta desconocida, y el contrato declara la ruta (§2.1); ✅
7. no se persiste ningún evento; ✅
8. no se crea ni modifica ningún activo: tras cada POST, `GET /activos-biologicos/99999` sigue devolviendo 404. ✅

**Sobre el mensaje de la ficha.** La ficha enuncia *«El activo biológico no existe»*; el sistema devuelve *«El activo biológico con id 99999 no existe.»*. Es la misma afirmación con el identificador concreto añadido: cumple el criterio y aporta precisión diagnóstica.

**Resultado TC-M02-304: APROBADO.**

---

## 6. TC-M02-305 — activo no ACTIVO

| Actor | Activo | Estado | HTTP esperado | HTTP obtenido | Mensaje | ¿Persistió? | Resultado |
|---|---:|---|---:|---:|---|---|---|
| Productor | 288 | **CERRADO** | 409 | **409** | `ESTADO_NO_PERMITE_EVENTOS` — *El activo no se encuentra en estado ACTIVO. Estado actual: CERRADO. …* | NO | **APROBADO** |
| Veterinario | 329 | **CERRADO** | 409 | **409** | idéntico | NO | **APROBADO** |
| Ingeniero de campo | 336 | **CERRADO** | 409 | **409** | idéntico | NO | **APROBADO** |

Mensaje completo devuelto en los tres casos:

```text
El activo no se encuentra en estado ACTIVO. Estado actual: CERRADO.
Los eventos de crecimiento solo se pueden registrar sobre activos en estado ACTIVO.
```

Verificaciones de la sección 14 cubiertas por aserción, para cada actor:

1. el activo existe (`GET` → 200 con su identificador esperado); ✅
2. el estado real es `CERRADO`, confirmado por `SELECT` (`id_estado = 5`) y por `GET` (`nombre_estado: "CERRADO"`); ✅
3. el actor tiene acceso legítimo: el activo está en su propia finca y el `GET` devolvió 200; ningún `403` intervino; ✅
4. todos los demás datos del request son válidos, con `tipo_agregacion` ausente por tratarse de un activo INDIVIDUAL; ✅
5. `HTTP = 409`; ✅
6. el mensaje corresponde a activo no ACTIVO: `error_code: ESTADO_NO_PERMITE_EVENTOS`, contiene *«no se encuentra en estado ACTIVO»* e identifica el estado real `CERRADO`. Se comprobó además que **no** menciona ninguna otra regla de RF-40 (`SIN_FASE_ACTIVA`, `FECHA_FUTURA`, `TIPO_MEDICION_NO_CONFIGURADO`, `VALOR_FUERA_DE_RANGO`, `AGREGACION_NO_PERMITIDA`, `TIPO_AGREGACION_REQUERIDO`, `ACTIVO_NO_ENCONTRADO`); ✅
7. no se crea evento; ✅
8. `DESPUÉS = ANTES`. ✅

**Sobre el mensaje de la ficha.** La ficha enuncia *«El activo no se encuentra en estado ACTIVO»*; el sistema devuelve esa frase literal y añade el estado actual y la regla aplicable. Cumple el criterio con precisión adicional.

**Resultado TC-M02-305: APROBADO.**

---

## 7. Verificación BD

### TC-M02-304

- **Activo 99999 sigue inexistente:** **SÍ** — `SELECT count(*) … WHERE id_activo_biologico = 99999` → **0**, igual que antes.
- **Eventos asociados a 99999:** **0**, igual que antes.
- **No se creó ningún activo:** el total sigue en **259** y el `max(id_activo_biologico)` en **336**.

```sql
SELECT count(*) FROM modulo2.activos_biologicos WHERE id_activo_biologico = 99999;   -- 0
SELECT count(*) FROM modulo2.eventos_activos    WHERE id_activo_biologico = 99999;   -- 0
SELECT count(*), max(id_activo_biologico) FROM modulo2.activos_biologicos;           -- 259 | 336
```

### TC-M02-305

| Actor | Activo | Conteo ANTES | Conteo DESPUÉS | Δ |
|---|---:|---:|---:|---:|
| Productor | 288 | 0 | 0 | **0** |
| Veterinario | 329 | 0 | 0 | **0** |
| Ingeniero de campo | 336 | 0 | 0 | **0** |

Los conteos se verificaron dos veces: dentro de la colección, con un `GET .../historial` posterior a cada POST que afirma la igualdad con el conteo base, y en la base de datos al cerrar la ejecución.

```sql
SELECT ab.id_activo_biologico, e.nombre AS estado,
       (SELECT count(*) FROM modulo2.eventos_activos ea
          JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
         WHERE ea.id_activo_biologico = ab.id_activo_biologico) AS eventos_crecimiento
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico IN (288, 329, 336);
--  288 | CERRADO | 0     329 | CERRADO | 0     336 | CERRADO | 0

-- Ninguna fila nueva y ningún cambio en los totales
SELECT count(*), max(id_eventos) FROM modulo2.eventos_activos;             -- 106 | 240
SELECT count(*) FROM modulo2.eventos_activos WHERE id_eventos > 240;       -- 0
```

| Métrica global | Antes | Después | Δ |
|---|---:|---:|---:|
| `modulo2.eventos_activos` — filas | 106 | 106 | **0** |
| `modulo2.eventos_activos` — `max(id_eventos)` | 240 | 240 | **0** |
| `modulo2.activos_biologicos` — filas | 259 | 259 | **0** |
| Eventos asociados a `99999` | 0 | 0 | **0** |

Los tres activos utilizados siguen en estado `CERRADO`: la prueba no alteró ningún estado.

---

## 8. Diagnóstico

**¿Fue necesario? NO.**

No hubo desviación: la ejecución fue única y las 88 aserciones pasaron a la primera. Los seis rechazos llegaron con el código HTTP de la ficha y el código de negocio de la regla evaluada, sin ningún `HTTP 500`, sin ningún `403` y sin persistencia. La carpeta `02-DIAGNOSTICO` de la colección quedó deliberadamente vacía.

Las hipótesis de la sección 16 se descartaron de forma preventiva y quedan sostenidas por las aserciones:

| # | Hipótesis | Cómo se descartó |
|---|---|---|
| A1 | `99999` sí existe | `SELECT` → 0 filas, y `GET` → 404 con cada actor inmediatamente antes de cada POST. |
| A2 | Se envió otro ID por variable Postman | La URL va literal en la colección, sin variables, y se afirma sobre `pm.request.url` que contiene `/activos-biologicos/99999/eventos/crecimiento`. |
| A3 | El activo de TC-M02-305 está realmente ACTIVO | `SELECT` (`id_estado = 5`) y `GET` (`nombre_estado: "CERRADO"`), afirmado antes del POST. |
| A4 | El actor no tiene acceso legítimo al activo no ACTIVO | Los tres activos están en fincas cuyo `id_usuario` es el propio actor; `GET` → 200 en los tres. Ningún `403`. |
| A5 | Payload con otra condición inválida | Cuerpo realmente enviado afirmado campo a campo, incluida la ausencia de `tipo_agregacion`. |
| A6 | Fecha inválida | Fecha calculada como *ahora menos dos minutos*: no futura y posterior a cualquier evento previo. Ninguna respuesta mencionó `FECHA_FUTURA`. |
| A7 | Medición/unidad/valor inválidos | `PESO`/`kg` configurado para la especie 40 (`AMBOS`, rango 0,1 – 2000); valor 250 dentro del rango. |
| A8 | `tipo_agregacion` incorrecto | Los tres activos son INDIVIDUAL y el campo se omite, que es lo correcto según TC-M02-G45. |
| A9 | Token incorrecto o vencido | `sub` del JWT afirmado contra 35, 3 y 4; cabecera `Authorization` verificada en cada POST oficial. |
| A10 | Assertion esperaba código equivocado | Se exigieron los códigos de la ficha (404 y 409) y, además, el `error_code` de negocio correspondiente. La discrepancia del contrato sobre el 409 se documentó sin alterar la expectativa (§2.1). |
| A11 | El 404 proviene de ruta incorrecta y no de activo inexistente | El contrato declara la ruta; el cuerpo trae `error_code: ACTIVO_NO_ENCONTRADO` y **no** el `{"detail":"Not Found"}` del enrutador; el mensaje nombra el ID 99999. Aserción explícita. |
| A12 | Artefacto Newman/Postman | No aplica: no hubo desviación que reproducir. Los cuerpos enviados y recibidos constan íntegros en el reporte JSON. |

---

## 9. VEREDICTO FINAL

# ✅ APROBADO

**Justificación:**

1. Gate completo: repositorio, rama `qa/juan-esteban-m02`, HEAD `41369ea`, backend HTTPS en 200 y PostgreSQL accesible en solo lectura.
2. La base de datos se revisó primero y en modo exclusivamente de lectura; **0 escrituras en SETUP**.
3. **`99999` está confirmado como inexistente**, por `SELECT` y por `GET` con cada actor. Se usó el ID oficial sin sustituirlo.
4. Existen recursos no ACTIVO legítimos para los tres actores, todos en estado **CERRADO**, el escenario prioritario de la ficha; no hizo falta la alternativa `BAJA`.
5. Se probaron **Productor, Veterinario e Ingeniero de campo**; no se usó Administrador como sustituto ni un recurso ajeno.
6. Se ejecutaron las **6 peticiones oficiales** (2 sub-casos × 3 actores).
7. **TC-M02-304 devolvió `404` para los tres actores.**
8. El mensaje de TC-M02-304 corresponde a activo inexistente (`ACTIVO_NO_ENCONTRADO`, nombra el ID 99999) y **no** a una ruta incorrecta.
9. **TC-M02-305 devolvió `409` para los tres actores.**
10. El mensaje de TC-M02-305 corresponde a activo no ACTIVO (`ESTADO_NO_PERMITE_EVENTOS`, identifica el estado real `CERRADO`) y no invoca ninguna otra regla de RF-40.
11. Ningún rechazo persistió un evento; no se creó ningún activo ni se alteró ningún estado.
12. La BD demuestra `Δ = 0` en los tres activos y en los totales globales.
13. No quedó ninguna verificación obligatoria sin ejecutar. No se invadió G43, G44, G45, G46 ni G47.

---

## 10. Datos para Registro de Errores

No se detectó ningún defecto dentro del alcance de G48. Se registran observaciones.



### OBS-G48-01 — El POST de crecimiento no aplica el filtro de alcance por finca que sí aplica la consulta

- **ID sugerido:** OBS-G48-03
- **Descripción:** las rutas de **consulta** de activos resuelven el alcance del usuario y lo propagan (`obtener_por_id(id_activo, ids_fincas_permitidas=_ids_fincas_alcance(...))`), de modo que un activo de otra finca devuelve 404. La ruta de **registro de evento de crecimiento** protege con RBAC (`require_permission`) pero llama a `obtener_por_id(id_activo)` **sin** `ids_fincas_permitidas`. Sobre el papel, un usuario con permiso de creación podría registrar eventos sobre activos fuera de su finca.
- **RF:** RF-40 · **Caso/sub-caso:** hallazgo colateral, **fuera del alcance de G48**
- **Estado de la comprobación:** **no verificado por QA.** Comprobarlo exigiría enviar un POST sobre un activo ajeno al actor, que queda fuera de las seis peticiones oficiales y que la restricción 15 desaconseja dentro de este caso. Se reporta como observación de lectura de código, no como defecto confirmado.
- **Categoría:** `AUTORIZACION` (por confirmar) · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Medio**, asignada de forma provisional hasta que Desarrollo confirme si la asimetría es intencional (por ejemplo, si RF-25 solo define alcance por finca para lectura). Si se confirma que un actor puede escribir fuera de su finca, la severidad debe reevaluarse al alza.
- **Tiempo máximo:** 2 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** 2026-09-14 · **Estado:** Abierto
- **Evidencia:** `activo_biologico_router.py` líneas 666–690 (endpoint de crecimiento, sin `_ids_fincas_alcance`) frente a las líneas 279, 417 y 497 (rutas de consulta, con alcance); `registrar_evento_crecimiento_use_case.py` línea 44.
- **Impacto en el caso:** ninguno. Los seis activos utilizados pertenecen a la finca del propio actor, por lo que la cobertura de G48 se cumplió con recursos legítimos en todos los casos.
- **Causa raíz:** **causa raíz no confirmada por QA.**

---

## 11. Declaración de cumplimiento

- ✅ No se modificó código fuente. Los archivos de `src/` solo se leyeron para conocer el orden de validación y la resolución del alcance por finca.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama. El árbol no tiene modificaciones sobre archivos versionados.
- ✅ No se ejecutó SQL de escritura. Todas las sentencias fueron `SELECT` con el usuario `member_qa`.
- ✅ No se crearon ni modificaron datos durante el SETUP: **0 escrituras**.
- ✅ **No se eliminó ningún activo** para fabricar la inexistencia de `99999`: el ID nunca existió y el total de activos permanece en 259.
- ✅ **No se cambió el estado de ningún activo** para fabricar TC-M02-305: 288, 329 y 336 ya estaban CERRADO y siguen estándolo.
- ✅ Se utilizó `99999` únicamente después de confirmarlo inexistente, y **no se sustituyó por otro ID**.
- ✅ Se probaron los tres actores obligatorios y cada uno usó un recurso de su propia finca.
- ✅ Ninguna petición introdujo más de una condición inválida.
- ✅ No se ejecutaron escenarios de G43, G44, G45, G46 ni G47.
- ✅ No se inventaron resultados ni evidencia: todo procede del reporte de Newman o de una consulta `SELECT` reproducible.
- ✅ No se ejecutaron migraciones ni se desplegaron o reiniciaron servicios.

---

## 12. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G48/
├── construir_coleccion.cjs        generador determinista de la colección
├── test_tc_m02_g48.json           colección Postman (00-SETUP-LECTURA, 01-CASO-PRINCIPAL, 02-DIAGNOSTICO)
└── Resultados/
    ├── reporte_tc_m02_g48.html    reporte Newman (htmlextra)
    ├── reporte_tc_m02_g48.json    reporte Newman (json), con cuerpos de petición y respuesta
    └── TC-M02-G48_resultado.md    este informe
```

Un solo HTML, un solo JSON, un solo informe. No se generó ningún `.log` por actor ni por consulta.

**Ejecución:** 25 peticiones · 25 scripts de prueba · **88 aserciones · 0 fallos** · 8,6 s · **6 peticiones oficiales**, ninguna con persistencia.
