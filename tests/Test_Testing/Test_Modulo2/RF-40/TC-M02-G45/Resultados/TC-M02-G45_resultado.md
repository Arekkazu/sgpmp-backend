# RESULTADO — TC-M02-G45

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **APROBADO** |
| Subtipo | — |
| COBERTURA ACTORES | COMPLETA |
| SUB-CASOS | 2/2 |
| PETICIONES OFICIALES | 6/6 |
| PERSISTENCIA INDEBIDA | NO |
| Equipo responsable | — (aprobado). Queda una observación administrativa en §10. |

**Justificación en una frase:** los tres actores obtuvieron rechazo `HTTP 400` con el código exacto de la regla evaluada —`AGREGACION_NO_PERMITIDA` al enviar `tipo_agregacion` a un activo INDIVIDUAL y `TIPO_AGREGACION_REQUERIDO` al omitirlo en un activo POBLACIONAL— y la base de datos demuestra `Δ = 0` en los seis activos utilizados.

---

## 1. Identificación

- **Caso:** TC-M02-G45 (sub-casos TC-M02-085 y TC-M02-086)
- **RF:** RF-40 — Registro de eventos de crecimiento
- **CU:** CU06
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **Commit HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** sin modificaciones sobre archivos versionados; solo artefactos de QA sin seguimiento
- **Fecha/hora:** 2026-09-10, 09:12 UTC · duración de la ejecución 13,4 s
- **Ambiente:** TEST desplegado, HTTPS — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Herramienta:** Postman + Newman (`newman run test_tc_m02_g45.json`), reporteros `cli`, `json` y `htmlextra`
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
| OpenAPI | ✅ contrato revisado, ver §2.1 |

### 2.1 Contrato revisado y representación de `tipo_agregacion`

`POST /activos-biologicos/{id_activo}/eventos/crecimiento` — `RegistrarEventoCrecimientoDTO`:

- Obligatorios a nivel de esquema: `tipo_medicion`, `valor_medicion`, `unidad_medida`.
- `tipo_agregacion`: `anyOf [string, null]`, **sin `enum` declarado** y **no listado en `required`**.
- Respuestas declaradas: `201, 400, 401, 403, 404, 422`.

**Consecuencia para el diseño de la prueba:** el contrato no restringe sintácticamente el valor de `tipo_agregacion` ni su obligatoriedad. Ambas reglas de G45 son de **negocio**, no de esquema, y se resuelven en el caso de uso. Esto es coherente con la ficha, que no fija un código HTTP ni un mensaje literal para estos sub-casos.

### 2.2 D11 — ¿`PROMEDIO` es una representación válida de `tipo_agregacion`?

**Sí.** Verificado por tres vías independientes, sin escribir nada:

1. **Modelo:** `evento_crecimiento_model.py:30` declara `tipo_agregacion` como `String(55)` con el comentario *«Tipo de agregación (PROMEDIO, TOTAL, DENSIDAD) — solo para POBLACIONAL»*.
2. **Base de datos:** `modulo2.eventos_crecimeinto` **no tiene ninguna restricción `CHECK`** sobre la columna (las únicas restricciones son `chk_crecimiento_unidad_valida` y `chk_crecimiento_valor_positivo`), por lo que cualquier cadena es sintácticamente admisible.
3. **Datos existentes:** `SELECT DISTINCT tipo_agregacion` devuelve `PROMEDIO` entre los valores ya presentes.

Queda descartada la hipótesis **A2**: enviar `PROMEDIO` no prueba una validación de enum inexistente, sino exactamente la regla de coherencia que G45 evalúa.

---

## 3. Revisión previa — SOLO LECTURA

El alcance de cada actor se resuelve por finca: `AlcanceFincaAdapter` ejecuta `SELECT id_finca FROM modulo9.fincas WHERE id_usuario = :id_usuario`, y `activo_biologico_repository._pertenece_a_fincas` filtra los activos por la finca de su infraestructura. Un activo fuera de ese alcance devuelve **404**, no 403. La revisión se hizo enumerando exhaustivamente los activos dentro del alcance de cada actor, no probando candidatos sueltos.

| Actor | Activo INDIVIDUAL | ACTIVO | Fase activa | Acceso legítimo | Activo LOTE | ACTIVO | Fase activa | Acceso legítimo |
|---|---:|---|---|---|---:|---|---|---|
| Productor (usuario 35, finca 57) | **279** `QAJE-CREC-OK` | ✅ | ✅ 1 | ✅ GET → 200 | **281** | ✅ | ✅ 1 | ✅ GET → 200 |
| Veterinario (usuario 3, fincas 38 y 64) | **311** `QAJE-CREC-OK-VET` | ✅ | ✅ 1 | ✅ GET → 200 | **328** | ✅ | ✅ 1 | ✅ GET → 200 |
| Ingeniero de campo (usuario 4, finca 65) | **312** `QAJE-CREC-OK-ING` | ✅ | ✅ 1 | ✅ GET → 200 | **334** | ✅ | ✅ 1 | ✅ GET → 200 |

Ningún actor utilizó un recurso ajeno: cada uno de los seis activos pertenece a una finca cuyo `id_usuario` es el propio actor.

**Escrituras SETUP: 0.** La etapa se limitó a `SELECT`, `GET /openapi.json`, `GET /activos-biologicos/{id}`, `GET .../fases`, `GET .../historial` y los tres `POST /sesiones/` de autenticación, que no crean datos de dominio.

### 3.1 Inventario mínimo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿Cuántos activos existen y cuántos están ACTIVO? | Dentro del alcance de los tres actores: 20 INDIVIDUAL y 6 POBLACIONAL en estado ACTIVO, más 5 en estados CERRADO/BAJA/INACTIVO que quedan descartados. |
| D2 | ¿Cuáles son INDIVIDUAL? | Productor: 279, 280, 282, 285, 287, 289–295, 298, 299 (ACTIVO con fase). Veterinario: 311, 325, 326, 327. Ingeniero: 312, 332, 333, 335. |
| D3 | ¿Cuáles son LOTE/POBLACIONAL? | Productor: 281, 283, 296, 300. Veterinario: 328. Ingeniero: 334. Todos ACTIVO y con fase activa. |
| D4 | ¿Cuáles tienen fase productiva activa? | Los seis seleccionados tienen exactamente una fila `es_activa = true` en `modulo2.gestiones_fases`. |
| D5 | ¿Qué activos permiten un evento de crecimiento válido? | Los seis pertenecen a la especie 40, que tiene `PESO` / `kg` configurado en `modulo9.metricas_produccion` con `aplica_a_tipo_activo = 'AMBOS'`, `es_activo = true` y rango 0,1 – 2000. Las tres infraestructuras (48, 60, 61) están activas y tienen superficie declarada, requisito del cálculo poblacional. |
| D6 | ¿Existen y están activas las cuentas de los tres actores? | Sí (`id_estado_cuenta = 2`), con la salvedad de §3.3. Los tres logins devolvieron 200 y el `sub` del JWT coincide con 35, 3 y 4. |
| D7 | ¿Qué finca/unidad corresponde a cada actor? | Usuario 35 → finca 57 · usuario 3 → fincas 38 y 64 · usuario 4 → finca 65. |
| D8 | ¿Qué activo INDIVIDUAL pertenece legítimamente a cada actor? | 279, 311 y 312 respectivamente. |
| D9 | ¿Qué activo LOTE pertenece legítimamente a cada actor? | 281, 328 y 334 respectivamente. |
| D10 | ¿Fecha del último evento de cada activo candidato? | INDIVIDUAL 279, 311 y 312: 2026-09-10 08:33:36Z. POBLACIONAL 281, 328 y 334: sin eventos de crecimiento previos. |
| D11 | ¿`PROMEDIO` es representación válida de `tipo_agregacion`? | Sí — ver §2.2. |

### 3.2 Consultas de la revisión previa

```sql
-- Alcance de fincas de cada actor (el mismo SQL que usa AlcanceFincaAdapter)
SELECT id_usuario, id_finca, nombre FROM modulo9.fincas WHERE id_usuario IN (3, 4, 35);
```

| id_usuario | id_finca | nombre |
|---:|---:|---|
| 3 | 38 | Finca Prueba QA rhlzhbpd |
| 3 | 64 | Finca QA Veterinario Crecimiento |
| 4 | 65 | Finca QA Ingeniero Crecimiento |
| 35 | 57 | Finca QA Juan Esteban |

```sql
-- Activos dentro del alcance de cada actor, por tipo, estado y fase activa
SELECT f.id_usuario AS actor, ab.tipo, e.nombre AS estado,
       (SELECT count(*) FROM modulo2.gestiones_fases gf
         WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa) AS fase_activa,
       count(*) AS n, array_agg(ab.id_activo_biologico ORDER BY ab.id_activo_biologico) AS ids
FROM modulo2.activos_biologicos ab
JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
JOIN modulo9.fincas f ON f.id_finca = i.id_finca
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = ab.id_estado
WHERE f.id_usuario IN (3, 4, 35)
GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3;
```

| actor | tipo | estado | fase_activa | ids |
|---:|---|---|---:|---|
| 3 | POBLACIONAL | ACTIVO | 1 | {328} |
| 3 | INDIVIDUAL | ACTIVO | 1 | {311, 325, 326, 327} |
| 4 | POBLACIONAL | ACTIVO | 1 | {334} |
| 4 | INDIVIDUAL | ACTIVO | 1 | {312, 332, 333, 335} |
| 35 | POBLACIONAL | ACTIVO | 1 | {281, 283, 296, 300} |
| 35 | INDIVIDUAL | ACTIVO | 1 | {279, 280, 282, 285, 287, 289, …, 299} |

*(La tabla omite las filas con `fase_activa = 0` y los estados CERRADO, BAJA e INACTIVO, descartados por no cumplir las precondiciones.)*

```sql
-- Métricas configuradas para la especie de los seis activos
SELECT id_especie, tipo_medicion, unidad_medida, aplica_a_tipo_activo, es_activo, valor_min, valor_max
FROM modulo9.metricas_produccion WHERE id_especie = 40 AND es_activo;
--  40 | PESO | kg | AMBOS | t | 0.1000 | 2000.0000

-- Infraestructuras de los seis activos (activas y con superficie)
SELECT id_infraestructura, id_finca, nombre, superficie, es_activo
FROM modulo9.infraestructuras WHERE id_infraestructura IN (48, 60, 61);
--  48 | 57 | Corral QA JE Origen               | 1000.00 | t
--  60 | 64 | Corral QA Veterinario Crecimiento |  100.00 | t
--  61 | 65 | Corral QA Ingeniero Crecimiento   |  100.00 | t

-- Detalle poblacional de los tres LOTE (base para cantidad_medida y nuevo_peso_promedio)
SELECT id_activo_biologico, cantidad_inicial, cantidad_actual, peso_promedio_inicial
FROM modulo2.detalles_activos_biologicos_poblacionales
WHERE id_activo_biologico IN (281, 328, 334);
--  281 | 100 | 100 | 25.0000
--  328 | 100 | 100 | 25.0000
--  334 | 100 | 100 | 25.0000

-- Línea base: conteos por activo y totales globales
SELECT count(*), max(id_eventos) FROM modulo2.eventos_activos;   -- 106 | 240
```

### 3.3 Salvedad de credenciales del Veterinario — resuelta sin crear datos

El paquete indica `juan.carlos@email.com`. Ese correo no existe en `modulo1.usuarios` y su login devuelve `HTTP 401 / CREDENCIALES_INVALIDAS`. La cuenta sí existe: usuario **id 3, rol 3 (Veterinario)**, correo vigente `juan.carlos.qa133@sgpmp-test.com`, misma contraseña. Es deriva de la credencial documentada, no falta de datos. Se usó el correo vigente; **no se creó ni modificó ninguna cuenta**. Registrado como OBS-G45-01.

### 3.4 Nota sobre el ambiente compartido

Entre la ejecución de TC-M02-G47 (08:33 UTC) y la línea base de este caso, el total global de `modulo2.eventos_activos` pasó de 104 a 106 por dos eventos semilla (ids 239 y 240, descripción `SEED-QAJE-RF40-*`) sobre los activos 325 y 332, ajenos a los seis de G45. TEST es un ambiente compartido, de modo que **la evidencia de no persistencia de este informe se apoya en los conteos por activo**, no en el contador global; el global se reporta solo como comprobación adicional.

---

## 4. Payloads base válidos

La ficha de G45 no fija `tipo_medicion`, `valor_medicion` ni `unidad_medida`. Se usó `PESO` / `kg`, la combinación configurada para la especie 40 con `aplica_a_tipo_activo = AMBOS`, idéntica para los dos tipos de activo, de modo que la medición no introduce ninguna variable adicional.

### 4.1 INDIVIDUAL

| Campo | Valor |
|---|---|
| activo | 279 · 311 · 312 según actor |
| `tipo_medicion` | `PESO` |
| `valor_medicion` | `250` (dentro del rango 0,1 – 2000) |
| `unidad_medida` | `kg` |
| `fecha` | instante actual menos 2 min (≈ 2026-09-10T09:12:2xZ): posterior al último evento y no futura |
| `tipo_agregacion` | **ausente en la base válida** |

Para **TC-M02-085** se añade únicamente `"tipo_agregacion": "PROMEDIO"`.

### 4.2 LOTE / POBLACIONAL

| Campo | Valor |
|---|---|
| activo | 281 · 328 · 334 según actor |
| `tipo_medicion` | `PESO` |
| `valor_medicion` | `26` (dentro del rango) |
| `unidad_medida` | `kg` |
| `nuevo_peso_promedio` | `26` |
| `cantidad_medida` | `100` (coincide con `cantidad_actual` del lote) |
| `fecha` | instante actual menos 2 min |
| `tipo_agregacion` válido en la base | **`PROMEDIO`** |

Para **TC-M02-086** se elimina únicamente `tipo_agregacion`; ningún otro dato cambia.

### 4.3 Por qué la base de LOTE incluye `nuevo_peso_promedio` y `cantidad_medida`

Es la diferencia que separa una prueba correcta de un falso aprobado. En el caso de uso, para activos `POBLACIONAL` las validaciones se evalúan **en este orden**:

```text
1. fase productiva activa            → SIN_FASE_ACTIVA
2. fecha del evento                  → FECHA_FUTURA / fecha anterior
3. tipo_agregacion en INDIVIDUAL     → AGREGACION_NO_PERMITIDA
4. tipo_medicion configurado         → TIPO_MEDICION_NO_CONFIGURADO
5. valor dentro de rango             → VALOR_FUERA_DE_RANGO
6. nuevo_peso_promedio presente      → NUEVO_PESO_REQUERIDO
7. cantidad_medida presente          → CANTIDAD_MEDIDA_REQUERIDA
8. tipo_agregacion presente          → TIPO_AGREGACION_REQUERIDO   ← regla de TC-M02-086
```

Omitir `nuevo_peso_promedio` o `cantidad_medida` habría desplazado el rechazo a los pasos 6 o 7, produciendo un `400` que **no** demuestra la regla de G45 (el caso descrito en §16.3 del paquete). Incluyéndolos, el rechazo obtenido es el del paso 8.

Esto además aporta una garantía adicional: recibir exactamente `TIPO_AGREGACION_REQUERIDO` **prueba que los siete controles anteriores pasaron**, es decir, que la petición era válida en todo lo demás. Es la comprobación más fuerte disponible sin ejecutar una escritura exitosa, que G45 no permite.

---

## 5. TC-M02-085 — INDIVIDUAL con `tipo_agregacion`

| Actor | Activo | Valor enviado de `tipo_agregacion` | Respuesta | Motivo del rechazo | ¿Persistió? | Resultado |
|---|---:|---|---|---|---|---|
| Productor | 279 | `PROMEDIO` | **HTTP 400** `AGREGACION_NO_PERMITIDA` | *El campo tipo_agregacion no aplica a activos de tipo INDIVIDUAL.* · `field: tipo_agregacion` | NO | **APROBADO** |
| Veterinario | 311 | `PROMEDIO` | **HTTP 400** `AGREGACION_NO_PERMITIDA` | idéntico | NO | **APROBADO** |
| Ingeniero de campo | 312 | `PROMEDIO` | **HTTP 400** `AGREGACION_NO_PERMITIDA` | idéntico | NO | **APROBADO** |

Verificaciones de la sección 13 cubiertas por aserción, para cada actor:

1. el activo es realmente `INDIVIDUAL` (comprobado por `GET` en SETUP y afirmado en la petición); ✅
2. la petición envía `tipo_agregacion = PROMEDIO` (afirmado sobre el cuerpo realmente enviado); ✅
3. los demás campos son válidos: `PESO`, valor positivo, `kg`, fecha con formato correcto; ✅
4. el sistema rechaza la petición (no 201, 4xx sin error de servidor); ✅
5. la respuesta identifica `tipo_agregacion` como no aplicable a `INDIVIDUAL`, y **no** menciona ninguna otra regla de RF-40 (`SIN_FASE_ACTIVA`, `FECHA_FUTURA`, `TIPO_MEDICION_NO_CONFIGURADO`, `VALOR_FUERA_DE_RANGO`); ✅
6. no se crea evento; ✅
7. `DESPUÉS = ANTES`. ✅

**Resultado TC-M02-085: APROBADO.**

---

## 6. TC-M02-086 — LOTE sin `tipo_agregacion`

| Actor | Activo | ¿Campo omitido? | Respuesta | Motivo del rechazo | ¿Persistió? | Resultado |
|---|---:|---|---|---|---|---|
| Productor | 281 | SÍ | **HTTP 400** `TIPO_AGREGACION_REQUERIDO` | *El campo tipo_agregacion es obligatorio para activos de tipo POBLACIONAL.* · `field: tipo_agregacion` | NO | **APROBADO** |
| Veterinario | 328 | SÍ | **HTTP 400** `TIPO_AGREGACION_REQUERIDO` | idéntico | NO | **APROBADO** |
| Ingeniero de campo | 334 | SÍ | **HTTP 400** `TIPO_AGREGACION_REQUERIDO` | idéntico | NO | **APROBADO** |

Verificaciones de la sección 13 cubiertas por aserción, para cada actor:

1. el activo es realmente `POBLACIONAL`; ✅
2. `tipo_agregacion` está efectivamente ausente del cuerpo enviado (afirmado con `to.not.have.property`); ✅
3. los demás campos son válidos e incluyen `nuevo_peso_promedio` y `cantidad_medida`, obligatorios para POBLACIONAL; ✅
4. el sistema rechaza la petición; ✅
5. la respuesta identifica `tipo_agregacion` como campo obligatorio, y **no** menciona `NUEVO_PESO_REQUERIDO`, `CANTIDAD_MEDIDA_REQUERIDA`, `SIN_FASE_ACTIVA`, `FECHA_FUTURA`, `TIPO_MEDICION_NO_CONFIGURADO` ni `VALOR_FUERA_DE_RANGO`; ✅
6. no se crea evento; ✅
7. `DESPUÉS = ANTES`. ✅

**Resultado TC-M02-086: APROBADO.**

---

## 7. Verificación BD

| Actor | Tipo activo | Activo | Conteo ANTES | Conteo DESPUÉS | Δ |
|---|---|---:|---:|---:|---:|
| Productor | INDIVIDUAL | 279 | 4 | 4 | **0** |
| Productor | LOTE | 281 | 0 | 0 | **0** |
| Veterinario | INDIVIDUAL | 311 | 2 | 2 | **0** |
| Veterinario | LOTE | 328 | 0 | 0 | **0** |
| Ingeniero de campo | INDIVIDUAL | 312 | 4 | 4 | **0** |
| Ingeniero de campo | LOTE | 334 | 0 | 0 | **0** |

Los conteos intermedios se verificaron petición a petición dentro de la colección: cada `POST` va seguido de un `GET /activos-biologicos/{id}/historial?page_size=100` que cuenta los registros de categoría `CRECIMIENTO` y afirma la igualdad con el conteo base. Las seis aserciones de no persistencia pasaron.

```sql
-- Conteo por activo, idéntico antes y después de las seis peticiones
SELECT ab.id_activo_biologico, ab.tipo,
       (SELECT count(*) FROM modulo2.eventos_activos ea
          JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
         WHERE ea.id_activo_biologico = ab.id_activo_biologico) AS eventos_crecimiento
FROM modulo2.activos_biologicos ab
WHERE ab.id_activo_biologico IN (279, 281, 311, 328, 312, 334)
ORDER BY ab.tipo DESC, 1;

-- Ninguna fila nueva por encima del máximo de la línea base
SELECT count(*) FROM modulo2.eventos_activos WHERE id_eventos > 240;          -- 0

-- Ningún evento con las descripciones de este caso
SELECT count(*) FROM modulo2.eventos_activos WHERE descripcion LIKE 'TC-M02-08%';  -- 0

-- Totales globales, sin cambios
SELECT count(*), max(id_eventos) FROM modulo2.eventos_activos;                -- 106 | 240
```

| Métrica global | Antes | Después | Δ |
|---|---:|---:|---:|
| `modulo2.eventos_activos` — filas | 106 | 106 | **0** |
| `modulo2.eventos_activos` — `max(id_eventos)` | 240 | 240 | **0** |
| Eventos con descripción de G45 | 0 | 0 | **0** |

Ninguna de las seis peticiones oficiales creó un registro.

---

## 8. Diagnóstico

**¿Fue necesario? NO.**

No hubo desviación: la ejecución fue única y las 106 aserciones pasaron a la primera. Los seis rechazos llegaron con el código de negocio exacto de la regla evaluada, sin ningún `HTTP 500`, sin ningún `403` y sin persistencia. La carpeta `02-DIAGNOSTICO` de la colección quedó deliberadamente vacía.

Las hipótesis de la sección 15 se descartaron de forma preventiva, antes de ejecutar, y quedan sostenidas por las aserciones:

| # | Hipótesis | Cómo se descartó |
|---|---|---|
| A1 | Activo clasificado incorrectamente | Tipo confirmado en BD y por `GET`; afirmado en cada petición (`tipo === 'INDIVIDUAL'` / `'POBLACIONAL'`). |
| A2 | `PROMEDIO` no pertenece al enum real | No existe enum ni `CHECK`; `PROMEDIO` es el valor documentado en el modelo y ya presente en los datos (§2.2). |
| A3 | Otra condición inválida en el payload | Cuerpo realmente enviado afirmado campo a campo contra la base válida. |
| A4 | Falta otro campo obligatorio no relacionado | Para POBLACIONAL se incluyeron `nuevo_peso_promedio` y `cantidad_medida` (§4.3). |
| A5 | Medición/unidad inválida | `PESO`/`kg` configurado para la especie 40 con `aplica_a_tipo_activo = AMBOS`; valores dentro del rango 0,1 – 2000. |
| A6 | Activo no ACTIVO | `SELECT` y `GET` confirman estado ACTIVO en los seis. |
| A7 | Activo sin fase activa | Exactamente una fase `es_activa = true` por activo, verificada por `SELECT` y por `GET .../fases`. |
| A8 | Fecha inválida | Fecha calculada como *ahora menos dos minutos*: posterior al último evento y no futura. Ningún rechazo mencionó `FECHA_FUTURA`. |
| A9 | Token incorrecto o acceso ilegítimo | `sub` del JWT afirmado contra 35, 3 y 4; los seis activos pertenecen a fincas del propio actor; ningún `403` ni `404`. |
| A10 | Postman envió u omitió `tipo_agregacion` al revés | Afirmado sobre `pm.request.body.raw`: presente con `PROMEDIO` en TC-M02-085, ausente en TC-M02-086. |
| A11 | Assertion incorrecta | Las aserciones exigen el código y el campo de la regla evaluada, y además **excluyen explícitamente** los códigos de las demás reglas de RF-40. |
| A12 | Artefacto Newman | No aplica: no hubo desviación que reproducir. Los cuerpos enviados y recibidos constan íntegros en el reporte JSON. |

---

## 9. VEREDICTO FINAL

# ✅ APROBADO

**Justificación:**

1. Gate completo: repositorio, rama `qa/juan-esteban-m02`, HEAD `41369ea`, backend HTTPS en 200 y PostgreSQL accesible en solo lectura.
2. La base de datos se revisó primero y en modo exclusivamente de lectura; **0 escrituras en SETUP**.
3. El **Productor** tiene INDIVIDUAL (279) y LOTE (281) legítimos.
4. El **Veterinario** tiene INDIVIDUAL (311) y LOTE (328) legítimos.
5. El **Ingeniero de campo** tiene INDIVIDUAL (312) y LOTE (334) legítimos.
6. Se probaron los tres actores; no se usó Administrador como sustituto ni un recurso ajeno.
7. Se ejecutaron las **6 peticiones oficiales** (2 sub-casos × 3 actores).
8. Los tres INDIVIDUALES **rechazaron** `tipo_agregacion` con `HTTP 400 / AGREGACION_NO_PERMITIDA`.
9. Los tres LOTES **rechazaron** la ausencia de `tipo_agregacion` con `HTTP 400 / TIPO_AGREGACION_REQUERIDO`.
10. Cada rechazo correspondió **a la regla evaluada**: el código de negocio nombra `tipo_agregacion`, el campo señalado es `tipo_agregacion`, y se comprobó por aserción que ninguna respuesta invoca otra regla de RF-40.
11. Ninguna petición generó evento; la BD demuestra `Δ = 0` en los seis activos y cero filas nuevas.
12. No quedó ninguna verificación obligatoria sin ejecutar. No se invadió G43, G44, G46, G47 ni G48.

---

## 10. Datos para Registro de Errores

No se detectó ningún defecto dentro del alcance de G45. Se registra una observación administrativa.

### OBS-G45-01 — Credencial desactualizada del Veterinario en el paquete de instrucciones

- **ID sugerido:** OBS-G45-01
- **Descripción:** el paquete indica `juan.carlos@email.com` para el actor Veterinario. Ese correo no existe en `modulo1.usuarios` y su login devuelve `HTTP 401 / CREDENCIALES_INVALIDAS`. El usuario correspondiente es el id 3 (rol 3, Veterinario), cuyo correo vigente es `juan.carlos.qa133@sgpmp-test.com`, con la misma contraseña `Test1234!`.
- **RF:** RF-40 · **Caso/sub-caso:** TC-M02-G45 (afecta igualmente a G44 y G47) · **Actor:** Veterinario
- **Categoría:** documentación del caso · **Equipo responsable:** **Responsable QA**
- **Severidad:** Bajo · **Tiempo máximo:** 3 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** 2026-09-15 · **Estado:** Abierto
- **Evidencia:** `SELECT` sobre `modulo1.usuarios` (§3.2) y respuesta 401 del login con el correo documentado.
- **Impacto en el caso:** ninguno. La cobertura del actor se completó con la cuenta vigente, sin crear ni modificar datos.
- **Causa raíz:** confirmada por QA — el correo de la cuenta fue cambiado en TEST después de redactarse el paquete.

---

## 11. Declaración de cumplimiento

- ✅ No se modificó código fuente. Los archivos de `src/` solo se leyeron para conocer el orden de validación y la representación de `tipo_agregacion`.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama. El árbol no tiene modificaciones sobre archivos versionados.
- ✅ No se ejecutó SQL de escritura. Todas las sentencias fueron `SELECT` con el usuario `member_qa`.
- ✅ No se crearon ni modificaron datos mediante API durante el SETUP: **0 escrituras**.
- ✅ No se cambió ningún activo de INDIVIDUAL a LOTE ni viceversa.
- ✅ Se probaron los tres actores obligatorios y cada uno usó recursos de su propia finca.
- ✅ Ninguna petición introdujo más de una condición inválida.
- ✅ No se ejecutaron escenarios de G43, G44, G46, G47 ni G48.
- ✅ No se inventaron resultados ni evidencia: todo procede del reporte de Newman o de una consulta `SELECT` reproducible.
- ✅ No se ejecutaron migraciones ni se desplegaron o reiniciaron servicios.

---

## 12. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G45/
├── construir_coleccion.cjs        generador determinista de la colección
├── test_tc_m02_g45.json           colección Postman (00-SETUP-LECTURA, 01-CASO-PRINCIPAL, 02-DIAGNOSTICO)
└── Resultados/
    ├── reporte_tc_m02_g45.html    reporte Newman (htmlextra)
    ├── reporte_tc_m02_g45.json    reporte Newman (json), con cuerpos de petición y respuesta
    └── TC-M02-G45_resultado.md    este informe
```

Un solo HTML, un solo JSON, un solo informe. No se generó ningún `.log` por actor ni por consulta.

**Ejecución:** 34 peticiones · 34 scripts de prueba · **106 aserciones · 0 fallos** · 13,4 s · **6 peticiones oficiales**, ninguna con persistencia.
