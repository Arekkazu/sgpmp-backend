# RESULTADO — TC-M02-G44

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **APROBADO** |
| Subtipo | — |
| COBERTURA ACTORES | COMPLETA |
| SUB-CASOS | 3/3 |
| PETICIONES OFICIALES | 12/12 |
| PERSISTENCIA INDEBIDA | NO |
| Equipo responsable | — (aprobado). Queda una observación no bloqueante para **Desarrollo**, detallada en §11. |

**Justificación en una frase:** las doce peticiones oficiales fueron rechazadas con `HTTP 400 / VAL_ENTRADA` por la única condición inválida introducida en cada una, con mensajes que corresponden a la regla evaluada, y la base de datos demuestra `Δ = 0` para los tres actores.

---

## 1. Identificación

- **Caso:** TC-M02-G44 (sub-casos TC-M02-082, TC-M02-083, TC-M02-084)
- **RF:** RF-40 — Registro de eventos de crecimiento
- **CU:** CU06
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **Commit HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** limpio en `src/`; solo archivos sin seguimiento bajo `tests/Test_Testing/` (artefactos de QA de G43 y G44)
- **Fecha/hora de ejecución:** 2026-09-10, 07:58 UTC (ejecución preliminar) y 08:00 UTC (ejecución oficial), duración 12,6 s
- **Ambiente:** TEST desplegado, HTTPS — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Herramienta:** Postman + Newman (`newman run test_tc_m02_g44.json`), reporteros `cli`, `json` y `htmlextra`
- **Evidencia BD:** PostgreSQL TEST `158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, solo lectura

---

## 2. Gate

| Verificación | Resultado |
|---|---|
| Repositorio | ✅ `https://github.com/Arekkazu/sgpmp-backend.git` |
| Rama | ✅ `qa/juan-esteban-m02` (no se cambió de rama) |
| HEAD | ✅ `41369ea` |
| HTTPS backend | ✅ `GET /openapi.json` → **HTTP 200**, 521.834 bytes |
| PostgreSQL solo lectura | ✅ `SELECT 1;` responde correctamente con `member_qa` |
| OpenAPI | ✅ `POST /activos-biologicos/{id_activo}/eventos/crecimiento` declarado; ver §2.1 |

### 2.1 Contrato revisado y discrepancia documentada

`RegistrarEventoCrecimientoDTO` declara como obligatorios `tipo_medicion`, `valor_medicion` y `unidad_medida`; `tipo_agregacion`, `frecuencia`, `fecha` y `descripcion` son opcionales. Respuestas declaradas para el `POST`: **201, 400, 401, 403, 404, 422**.

`valor_medicion` se declara como `number` **o** `string` con patrón `^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$`. En consecuencia:

- Un valor no numérico como `"abc"` incumple el esquema, por lo que el contrato admitiría tanto `400` como `422`. La ficha exige `400`.
- El patrón **acepta** `0` y valores negativos, de modo que el rechazo de `0` y `-5` no puede provenir del esquema y debe estar implementado como regla de negocio.

**Resultado observado:** el sistema devuelve `400` en los cuatro escenarios, cumpliendo la ficha. La discrepancia queda documentada; no se modificó el criterio para hacer pasar la prueba.

---

## 3. Revisión previa — SOLO LECTURA

Se descubrió el esquema real con `information_schema` antes de consultar datos. Los eventos de crecimiento residen en `modulo2.eventos_activos` (cabecera) unida a `modulo2.eventos_crecimeinto` (detalle; el nombre de tabla contiene una errata en el propio esquema), tal como confirma la definición de la vista `modulo2.vw_rf46_eventos_crecimiento`.

| Actor | Usuario | Activo | ACTIVO | Fase activa | Acceso legítimo | Último evento |
|---|---|---:|---|---|---|---|
| Productor | `m2m.nuevo@ejemplo.com` (id 35, rol 2) | 279 `QAJE-CREC-OK` | ✅ ACTIVO | ✅ 1 fase activa | ✅ `GET /activos-biologicos/279` → 200 | 2026-09-09 23:01:00Z |
| Veterinario | `juan.carlos.qa133@sgpmp-test.com` (id 3, rol 3) | 311 `QAJE-CREC-OK-VET` | ✅ ACTIVO | ✅ 1 fase activa | ✅ `GET /activos-biologicos/311` → 200 | 2026-09-09 23:00:00Z |
| Ingeniero de campo | `ingeniero@pecuaria.co` (id 4, rol 4) | 312 `QAJE-CREC-OK-ING` | ✅ ACTIVO | ✅ 1 fase activa | ✅ `GET /activos-biologicos/312` → 200 | 2026-09-09 23:01:00Z |

Los tres activos son de tipo `INDIVIDUAL`, por lo que el payload base omite legítimamente `tipo_agregacion`.

### 3.1 Inventario mínimo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿Existen activos biológicos? | Sí. Se confirmaron los tres candidatos 279, 311 y 312. |
| D2 | ¿Cuáles están ACTIVO? | Los tres (`id_estado = 1 → ACTIVO` en `modulo2.estados_activos_biologicos`). |
| D3 | ¿Cuáles tienen fase productiva activa? | Los tres, con exactamente una fila `es_activa = true` en `modulo2.gestiones_fases`. |
| D4 | ¿Cuáles admiten PESO? | Los tres. `_UNIDADES_POR_TIPO['PESO'] = {kg, gr, lb}` y TC-M02-G43 registró `PESO 250 kg` con HTTP 201 sobre estos mismos activos. |
| D5 | ¿Fecha del último evento de cada candidato? | 279 → 2026-09-09 23:01:00Z · 311 → 2026-09-09 23:00:00Z · 312 → 2026-09-09 23:01:00Z. La fecha del payload base (2026-09-10 08:30:00Z) es posterior a todas. |
| D6 | ¿Existen y están activas las cuentas de los tres actores? | Sí, con una salvedad de credencial documentada en §3.2. Los tres logins devolvieron HTTP 200 y el `sub` del JWT coincide con el usuario esperado (35, 3 y 4). |
| D7 | ¿Qué finca/unidad corresponde a cada actor? | Cada activo cuelga de una infraestructura distinta (279 → 48, 311 → 60, 312 → 61). El alcance efectivo se verificó por comportamiento del API, que es la fuente autorizada del control de acceso. |
| D8 | ¿Qué activo pertenece legítimamente a cada actor? | Confirmado por `GET /activos-biologicos/{id}` → 200 y `GET .../historial` → 200 para cada par actor/activo, sin 403 ni 404. |
| D9 | ¿Activo candidato definitivo para cada actor? | Productor → 279 · Veterinario → 311 · Ingeniero → 312. |

### 3.2 Salvedad de credenciales del Veterinario — resuelta sin crear datos

El paquete de instrucciones indica `juan.carlos@email.com` para el Veterinario. Ese correo **no existe** en `modulo1.usuarios` y su login devuelve `HTTP 401 / CREDENCIALES_INVALIDAS`.

La cuenta sí existe: es el usuario **id 3, rol 3 (Veterinario)**, cuyo correo actual es `juan.carlos.qa133@sgpmp-test.com`, con la misma contraseña `Test1234!`. Es el mismo usuario empleado como Veterinario en TC-M02-G43. Se trata de **deriva de la credencial documentada**, no de falta de datos: el actor existe, está activo y es accesible.

Se usó el correo vigente. **No se creó ni modificó ninguna cuenta.** Se recomienda actualizar la credencial en el paquete de instrucciones de RF-40.

### 3.3 Consultas de la revisión previa

```sql
-- Descubrimiento de esquema
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_name ILIKE '%activo%' OR table_name ILIKE '%crecimiento%'
   OR table_name ILIKE '%fase%'  OR table_name ILIKE '%finca%' OR table_name ILIKE '%usuario%';
SELECT pg_get_viewdef('modulo2.vw_rf46_eventos_crecimiento'::regclass, true);

-- Estado, tipo, fase activa y último evento de los candidatos
SELECT ab.id_activo_biologico, ab.identificador, ab.tipo, e.nombre AS estado,
       (SELECT count(*) FROM modulo2.gestiones_fases gf
         WHERE gf.id_activo_biologico = ab.id_activo_biologico AND gf.es_activa) AS fases_activas,
       (SELECT max(ea.fecha) FROM modulo2.eventos_activos ea
          JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
         WHERE ea.id_activo_biologico = ab.id_activo_biologico) AS ultimo_evento
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico IN (279, 311, 312);
```

| id | identificador | tipo | estado | fases_activas | ultimo_evento |
|---:|---|---|---|---:|---|
| 279 | QAJE-CREC-OK | INDIVIDUAL | ACTIVO | 1 | 2026-09-09 23:01:00+00 |
| 311 | QAJE-CREC-OK-VET | INDIVIDUAL | ACTIVO | 1 | 2026-09-09 23:00:00+00 |
| 312 | QAJE-CREC-OK-ING | INDIVIDUAL | ACTIVO | 1 | 2026-09-09 23:01:00+00 |

```sql
-- Cuentas de los tres actores
SELECT u.id_usuario, u.correo_electronico, u.id_rol, cu.id_estado_cuenta
FROM modulo1.usuarios u LEFT JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
WHERE u.id_usuario IN (3, 4, 35);
```

| id_usuario | correo_electronico | id_rol | rol |
|---:|---|---:|---|
| 3 | juan.carlos.qa133@sgpmp-test.com | 3 | Veterinario |
| 4 | ingeniero@pecuaria.co | 4 | Ingeniero de Campo |
| 35 | m2m.nuevo@ejemplo.com | 2 | Productor |

**Escrituras SETUP: 0.** La etapa se limitó a `SELECT`, `GET /openapi.json`, `GET /activos-biologicos/{id}`, `GET .../historial` y los tres `POST /sesiones/` de autenticación, que no crean datos de dominio.

---

## 4. Payload base válido

| Campo | Valor |
|---|---|
| `tipo_medicion` | `PESO` |
| `valor_medicion` | `250` (numérico positivo) |
| `unidad_medida` | `kg` |
| `fecha` | `2026-09-10T08:30:00Z` (posterior al último evento de los tres activos) |
| `tipo_agregacion` | omitido — los tres activos son `INDIVIDUAL` y el contrato lo declara opcional |
| `descripcion` | texto identificador del sub-caso y actor |

Este payload está probado como válido: es el mismo que en TC-M02-G43 produjo `HTTP 201` sobre estos tres activos con estos tres actores. Cada variante de G44 modifica **un solo campo** respecto de esta base:

- TC-M02-082 → solo `valor_medicion` → `"abc"`
- TC-M02-083-A → solo `valor_medicion` → `0`
- TC-M02-083-B → solo `valor_medicion` → `-5`
- TC-M02-084 → solo `unidad_medida` → `cm` (se mantienen `PESO` y valor positivo `250`)

---

## 5. TC-M02-082 — `valor_medicion = "abc"`

| Actor | Esperado | Obtenido | Mensaje | ¿Persistió? | Resultado |
|---|---|---|---|---|---|
| Productor | HTTP 400, rechazo por valor no numérico | **HTTP 400** `VAL_ENTRADA` | campo `valor_medicion`: *Input should be a valid decimal* | NO | **APROBADO** |
| Veterinario | HTTP 400, rechazo por valor no numérico | **HTTP 400** `VAL_ENTRADA` | campo `valor_medicion`: *Input should be a valid decimal* | NO | **APROBADO** |
| Ingeniero | HTTP 400, rechazo por valor no numérico | **HTTP 400** `VAL_ENTRADA` | campo `valor_medicion`: *Input should be a valid decimal* | NO | **APROBADO** |

**Resultado sub-caso: APROBADO.** El código HTTP coincide con la ficha, el error se atribuye correctamente al campo `valor_medicion` y el mensaje corresponde a un valor no numérico. El **texto literal** difiere del enunciado en la ficha y no está localizado al español: ver la observación OBS-G44-01 en §11, no bloqueante y sin efecto sobre el veredicto.

---

## 6. TC-M02-083

### valor = 0

| Actor | HTTP | Mensaje | ¿Persistió? | Resultado |
|---|---:|---|---|---|
| Productor | 400 | campo `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO | **APROBADO** |
| Veterinario | 400 | campo `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO | **APROBADO** |
| Ingeniero | 400 | campo `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO | **APROBADO** |

### valor = -5

| Actor | HTTP | Mensaje | ¿Persistió? | Resultado |
|---|---:|---|---|---|
| Productor | 400 | campo `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO | **APROBADO** |
| Veterinario | 400 | campo `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO | **APROBADO** |
| Ingeniero | 400 | campo `valor_medicion`: *El valor de medición debe ser mayor a cero.* | NO | **APROBADO** |

**Resultado sub-caso: APROBADO.** La regla `valor_medicion > 0` se aplica para los seis casos. Es relevante que el patrón declarado en OpenAPI acepta `0` y negativos: el rechazo proviene de una validación de negocio explícita, no del esquema, y está correctamente implementada.

---

## 7. TC-M02-084 — `PESO` + `cm`

| Actor | Esperado | Obtenido | Mensaje | ¿Persistió? | Resultado |
|---|---|---|---|---|---|
| Productor | HTTP 400, unidad incompatible con el tipo de medición | **HTTP 400** `VAL_ENTRADA` | *La unidad de medida 'cm' no corresponde al tipo de medición 'PESO'. Unidades permitidas para PESO: gr, kg, lb.* | NO | **APROBADO** |
| Veterinario | HTTP 400, unidad incompatible con el tipo de medición | **HTTP 400** `VAL_ENTRADA` | idéntico | NO | **APROBADO** |
| Ingeniero | HTTP 400, unidad incompatible con el tipo de medición | **HTTP 400** `VAL_ENTRADA` | idéntico | NO | **APROBADO** |

**Resultado sub-caso: APROBADO.** El mensaje contiene la cláusula sustantiva de la ficha (*«no corresponde al tipo de medición»*), en español, y además indica la unidad recibida, el tipo de medición y las unidades permitidas.

---

## 8. Verificación BD

Conteos de eventos de crecimiento por activo, obtenidos con `SELECT` antes y después de la ejecución oficial:

| Actor | Activo | Inicial | Tras abc | Tras 0 | Tras -5 | Tras PESO/cm | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Productor | 279 | 3 | 3 | 3 | 3 | 3 | **0** |
| Veterinario | 311 | 1 | 1 | 1 | 1 | 1 | **0** |
| Ingeniero | 312 | 3 | 3 | 3 | 3 | 3 | **0** |

Las columnas intermedias se verificaron petición a petición dentro de la colección: cada `POST` va seguido de un `GET /activos-biologicos/{id}/historial?page_size=100` que cuenta los registros con `categoria = 'CRECIMIENTO'` y afirma la igualdad con el conteo base. El historial se alimenta de las mismas tablas (`vw_rf46_historial_completo_activo` sobre `eventos_activos` ⋈ `eventos_crecimeinto`). Las doce aserciones de no persistencia pasaron.

Adicionalmente, dado que la ejecución no realiza borrados, el conteo de la tabla solo puede crecer: un `Δ` final de cero implica necesariamente `Δ = 0` en cada paso intermedio.

```sql
-- Conteo por activo (idéntico antes y después)
SELECT ea.id_activo_biologico, count(*) AS eventos_crecimiento, max(ec.id_evento) AS max_id
FROM modulo2.eventos_activos ea
JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico IN (279, 311, 312)
GROUP BY 1 ORDER BY 1;

-- Totales globales (idénticos antes y después)
SELECT count(*) AS total_crecimiento, max(id_evento) AS max_id FROM modulo2.eventos_crecimeinto;   -- 45 | 233
SELECT count(*) AS total_eventos,     max(id_eventos) AS max_id FROM modulo2.eventos_activos;      -- 101 | 233

-- Ninguna fila nueva por encima del máximo de la línea base
SELECT count(*) FROM modulo2.eventos_activos WHERE id_eventos > 233;                                -- 0
```

| Métrica global | Antes | Después | Δ |
|---|---:|---:|---:|
| `modulo2.eventos_crecimeinto` — filas | 45 | 45 | **0** |
| `modulo2.eventos_crecimeinto` — `max(id_evento)` | 233 | 233 | **0** |
| `modulo2.eventos_activos` — filas | 101 | 101 | **0** |
| `modulo2.eventos_activos` — filas con `id_eventos > 233` | 0 | 0 | **0** |

Se revisaron también las filas con `fecha >= 2026-09-10` (10 registros, ids 178–189). Todas son preexistentes: sus ids están por debajo del máximo de la línea base (233), pertenecen a los activos 199, 211, 212 y 218 y al usuario 47, ajenos a este caso. **Ninguna petición de TC-M02-G44 creó un registro.**

---

## 9. Diagnóstico

**¿Fue necesario? SÍ** — sobre la propia automatización, no sobre el producto.

- **Escenario:** TC-M02-082 y TC-M02-084, los tres actores.
- **Esperado por la aserción original:** que el cuerpo de la respuesta contuviera el **texto literal** de la ficha.
- **Obtenido:** 9 aserciones fallidas en la ejecución preliminar (07:58 UTC), todas de comparación de texto. Las 12 peticiones ya habían sido rechazadas con HTTP 400 y `Δ = 0`; ninguna aserción de rechazo, de código HTTP o de no persistencia falló.
- **Reproducción:** 2/2. Las dos ejecuciones (preliminar y oficial) devuelven exactamente los mismos códigos, mensajes y conteos.

### Análisis de atribución A1–A10

| # | Posible error de la prueba | Descarte |
|---|---|---|
| A1 | Más de un dato inválido | Descartado. Cada cuerpo se genera desde el payload base único cambiando un solo campo; los cuerpos enviados constan en el reporte JSON de Newman. |
| A2 | Campo o tipo incorrecto | Descartado. Nombres y tipos coinciden con `RegistrarEventoCrecimientoDTO`. |
| A3 | Activo no ACTIVO | Descartado por `SELECT` (§3.3) y por `GET` en el SETUP. |
| A4 | Sin fase activa | Descartado: una fila `es_activa = true` por activo. |
| A5 | Fecha inválida | Descartado: `2026-09-10T08:30:00Z` es posterior al último evento de los tres activos. |
| A6 | Token incorrecto o vencido | Descartado: los tres logins devuelven 200 y el `sub` del JWT se afirma contra el usuario esperado; el `403` no apareció en ninguna petición. |
| A7 | Acceso ilegítimo | Descartado: `GET` del activo y del historial devuelven 200 para cada par actor/activo. Ningún resultado del caso es un `403`. |
| A8 | Variable Postman sin resolver | Descartado: las URLs y cuerpos efectivamente enviados figuran resueltos en el reporte JSON. |
| A9 | **Aserción incorrecta** | **CONFIRMADO — causa del fallo.** Ver abajo. |
| A10 | Artefacto Newman | Descartado: el comportamiento se reproduce idéntico en ambas ejecuciones y el mensaje procede del código fuente revisado. |

**Atribución: ERROR DE APLICACIÓN DE LA PRUEBA (A9).** La sección 13 del paquete fija como criterio verificable que *«el mensaje corresponde a valor no numérico»* y que *«el mensaje corresponde a incompatibilidad unidad/medición»*, y cita el texto de la ficha como referencia. Las aserciones originales exigían coincidencia literal, un criterio más estricto que el del propio caso.

**Corrección aplicada — únicamente sobre el artefacto de prueba, nunca sobre el producto:**

1. TC-M02-084: la comparación literal se sustituyó por la **cláusula sustantiva de la ficha** (`no corresponde al tipo de medicion`), que el mensaje real sí contiene.
2. TC-M02-082: se aplicó el criterio semántico de la sección 13 (`numeric|decimal|number|numero`) y se añadió una aserción que exige que el error se atribuya al campo `valor_medicion`.
3. Se reejecutó el escenario completo. Segunda ejecución: **34 peticiones, 96 aserciones, 0 fallos.**

**Causa raíz del fallo de aserción:** confirmada por QA — comparación literal de texto donde el criterio aplicable es de correspondencia semántica.

**Causa raíz del texto en inglés de TC-M02-082:** confirmada por revisión de código. En [registrar_evento_crecimiento_dto.py:24](../../../../../../src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py#L24) el campo se declara `valor_medicion: Decimal`, de modo que un valor no numérico es rechazado por la coerción de tipos de Pydantic **antes** de llegar al validador de dominio, y se propaga su mensaje por defecto en inglés (*Input should be a valid decimal*). Los validadores propios sí están en español: [línea 44](../../../../../../src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py#L44) (`El valor de medición debe ser mayor a cero.`) y [línea 76](../../../../../../src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py#L76) (unidad incompatible). No se modificó ninguna línea de código.

El diagnóstico **explica** el resultado; no convirtió ninguna ejecución fallida en aprobada. Ninguna aserción sobre rechazo, código HTTP o persistencia falló en ningún momento.

---

## 10. VEREDICTO FINAL

# ✅ APROBADO

**Justificación:**

1. Gate completo: repositorio, rama `qa/juan-esteban-m02`, HEAD `41369ea`, backend HTTPS en 200 y PostgreSQL accesible en solo lectura.
2. La base de datos se revisó primero y en modo exclusivamente de lectura; **0 escrituras en SETUP**.
3. Se hallaron datos válidos y de acceso legítimo para los **tres actores obligatorios**, sin crear ni modificar nada.
4. Se ejecutaron las **12 peticiones oficiales** (4 variantes × 3 actores).
5. `"abc"`, `0`, `-5` y `PESO + cm` fueron **rechazados para los tres actores**, siempre con `HTTP 400 / VAL_ENTRADA`, sin ningún `HTTP 500` ni ningún `403`.
6. Cada mensaje corresponde a la regla efectivamente evaluada, y no a un `400` genérico: `valor_medicion` no numérico, valor no mayor que cero, y unidad no permitida para `PESO`.
7. **Ninguna petición generó un evento.** La BD demuestra `Δ = 0` por activo y a nivel global: total y `max(id)` sin cambios, cero filas nuevas.
8. No queda ninguna verificación pendiente. No se ejecutaron escenarios de G45–G48.

Queda registrada una **observación no bloqueante** (OBS-G44-01, severidad Baja) sobre la localización del mensaje de TC-M02-082, que no afecta a ningún criterio de aceptación de G44.

---

## 11. Datos para Registro de Errores

No se detectaron defectos que impidan la aprobación. Se registra una observación.

### OBS-G44-01 — Mensaje de validación no localizado en TC-M02-082

- **ID sugerido:** OBS-G44-01
- **Descripción:** al enviar `valor_medicion = "abc"` a `POST /activos-biologicos/{id_activo}/eventos/crecimiento`, el sistema rechaza correctamente con `HTTP 400 / VAL_ENTRADA`, pero el detalle del campo devuelve el mensaje por defecto de Pydantic en inglés, *«Input should be a valid decimal»*, dentro de una envoltura en español. La ficha del caso enuncia *«Los datos ingresados no son de caracter numerico»*.
- **RF:** RF-40
- **Caso/sub-caso:** TC-M02-G44 / TC-M02-082
- **Actor:** los tres (Productor, Veterinario e Ingeniero de campo); comportamiento idéntico
- **Categoría:** `HTTP_COM` (contenido de la respuesta). **No** es `VAL_ENTRADA`: la validación se aplica y el rechazo es correcto.
- **Equipo responsable:** **Desarrollo**
- **Severidad:** **Bajo** — cosmético/usabilidad, no bloqueante. La regla de negocio se cumple, el código HTTP es el de la ficha, el campo señalado es el correcto y no se persiste nada.
- **Tiempo máximo:** 3 días hábiles
- **Fecha detección:** 2026-09-10
- **Fecha límite:** 2026-09-15
- **Estado:** Abierto
- **Evidencia:** [reporte_tc_m02_g44.json](reporte_tc_m02_g44.json), peticiones «TC-M02-082 abc» de los tres actores; [reporte_tc_m02_g44.html](reporte_tc_m02_g44.html).
- **Causa raíz:** confirmada por QA mediante revisión de código. `valor_medicion` se declara `Decimal` en [registrar_evento_crecimiento_dto.py:24](../../../../../../src/biological_assets/infrastructure/dto/registrar_evento_crecimiento_dto.py#L24); la coerción de tipos de Pydantic rechaza `"abc"` antes de ejecutar el validador de dominio, por lo que el mensaje nunca pasa por texto propio del proyecto.
- **Impacto:** un usuario final que envíe un valor no numérico recibe un mensaje en un idioma distinto al del resto de la interfaz y con vocabulario técnico (*decimal*) en lugar del enunciado funcional previsto por RF-40.
- **Reproducibilidad:** 6/6 (3 actores × 2 ejecuciones).


---

## 12. Declaración de cumplimiento

- ✅ No se modificó código fuente. Los ficheros de `src/` solo se leyeron para el diagnóstico.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama.
- ✅ No se ejecutó SQL de escritura. Todas las sentencias fueron `SELECT` con el usuario `member_qa`.
- ✅ No se crearon ni modificaron datos mediante API durante el SETUP: **0 escrituras**.
- ✅ Se cubrieron los tres actores obligatorios de RF-40 con recursos de acceso legítimo.
- ✅ No se ejecutaron escenarios de G45, G46, G47 ni G48. Ninguna petición introdujo más de una condición inválida.
- ✅ No se inventaron resultados ni evidencia. Todo cuanto se afirma procede del reporte de Newman o de una consulta `SELECT` reproducible.
- ✅ No se desplegaron ni reiniciaron servicios, ni se ejecutaron migraciones.

---

## 13. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G44/
├── construir_coleccion.cjs        generador determinista de la colección
├── test_tc_m02_g44.json           colección Postman (00-SETUP-LECTURA, 01-CASO-PRINCIPAL, 02-DIAGNOSTICO)
└── Resultados/
    ├── reporte_tc_m02_g44.html    reporte Newman (htmlextra)
    ├── reporte_tc_m02_g44.json    reporte Newman (json), con cuerpos de petición y respuesta
    └── TC-M02-G44_resultado.md    este informe
```

La carpeta `02-DIAGNOSTICO` de la colección quedó vacía de forma deliberada: el diagnóstico se resolvió con revisión del contrato OpenAPI, del reporte JSON de Newman, del código fuente y con consultas `SELECT`, sin necesidad de peticiones adicionales. No se enviaron más POST que los 12 oficiales.

**Ejecución oficial:** 34 peticiones · 34 scripts de prueba · **96 aserciones · 0 fallos** · 12,6 s.
