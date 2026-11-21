# RESULTADO — TC-M02-G81 (repetición con estrategia híbrida)

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| **VEREDICTO GLOBAL** | **RECHAZADO** |
| TC-M02-138 (TEST) | ✅ **APROBADO** — 2/2 actores |
| TC-M02-139 (TEST) | ⛔ **BLOQUEADO** — escenario no expresable por API |
| TC-M02-140 (TEST) | ❌ **RECHAZADO** — 2/2 actores |
| TC-M02-141 (LOCAL AISLADO) | ✅ **APROBADO** — 2/2 actores |
| Ejecuciones realizadas | **6 de 8** ideales (TC-139 ×2 bloqueado) |
| Escrituras de QA en TEST | **0** |
| Equipo responsable | **Desarrollo Backend** (DEF-G81-01) · **Desarrollo Backend / responsable funcional** (desbloqueo TC-139) |

**Justificación.** Las tres reglas verificables se comportan correctamente en cuanto al fondo: un activo no ACTIVO se rechaza con `409 ACTIVO_NO_ACTIVO`, una fecha futura se rechaza siempre y nunca llega a persistir, y el fallo transaccional revierte por completo las tres escrituras previas al `commit`. El rechazo del caso agrupado se debe a un único defecto de contrato: **TC-M02-140 responde `HTTP 400` en lugar del `422` que fija la ficha, y `400` ni siquiera está declarado en el OpenAPI de esa ruta**.

TC-M02-139 queda **BLOQUEADO** por gate contractual (§7): el DTO de transferencia no expone ningún campo de cantidad, de modo que "mover 40 de 100" no es expresable por la API y el sub-caso no puede ejecutarse sin inventar parámetros.

---

## 1. Identificación

- **Caso:** TC-M02-G81 (repetición híbrida)
- **RF:** RF-48 — Transferencia Interna de Activos Biológicos
- **Sub-casos:** TC-M02-138, TC-M02-139, TC-M02-140, TC-M02-141
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD_EVALUADO:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae`
- **Fecha:** 2026-09-10
- **Actores:** Productor (`m2m.nuevo@ejemplo.com`, usuario 35, rol 2) · Administrador (`admin@pecuaria.co`, usuario 1, rol 1)
- **Herramientas:** Postman + Newman (TEST) · Pytest + monkeypatch (LOCAL)

### 1.1 Gate global de código (§3)

| Verificación | Resultado |
|---|---|
| `git remote -v` | ✅ `https://github.com/Arekkazu/sgpmp-backend.git` |
| `git branch --show-current` | ✅ `qa/juan-esteban-m02` |
| `git rev-parse HEAD` | ✅ `41369ea` |
| `git status` (versionados) | ✅ Sin modificaciones — solo artefactos QA sin seguimiento |
| Backend TEST HTTPS | ✅ `GET /openapi.json` → **HTTP 200** |
| PostgreSQL TEST | ✅ `SELECT 1` con sesión `readonly=True` |

**El HEAD de la fase TEST y el de la fase LOCAL son el mismo `41369ea`** (nunca se cambió de rama ni se hizo checkout entre fases). Verificado antes y después de ambas fases.

---

# AMBIENTE TEST

Sub-casos ejecutados aquí: **TC-M02-138**, **TC-M02-139** (bloqueado), **TC-M02-140**.
**Ningún fault injection se ejecutó en TEST.**

## 2. Contrato vigente (§5.2)

`POST /activos-biologicos/{id_activo}/transferencias`

| Elemento | Valor real en OpenAPI |
|---|---|
| Campos del `RegistrarTransferenciaDTO` | `infraestructura_origen_id`, `infraestructura_destino_id`, `fecha_transferencia`, `motivo_transferencia` |
| Campo de cantidad / parcialidad | **NO EXISTE** |
| Formato de fecha | `string($date)` |
| Respuestas declaradas | `201, 401, 403, 404, 409, 422, 500` |
| **No declarada** | **`400`** |

## 3. Datos utilizados — solo lectura

Todos los fixtures son preexistentes en TEST. **No se creó, modificó ni eliminó ningún dato para fabricar precondiciones.**

| Uso | Activo | Estado | Origen (asociación vigente) | Destino |
|---|---|---|---|---|
| TC-138 / Productor | 284 `QAJE-TRF-NOACT` | INACTIVO (2) | 48 `Corral QA JE Origen` | 51 |
| TC-138 / Administrador | 288 `QAJE-CREC-CERRADO` | CERRADO (5) | 48 | 51 |
| TC-140 / Productor | 292 `QAJE-TRF-OK` | ACTIVO (1) | 48 | 51 |
| TC-140 / Administrador | 295 `QAJE-DAT-COMPL` | ACTIVO (1) | 48 | 51 |
| TC-139 (referencia) | 281 (POBLACIONAL) | ACTIVO, `cantidad_actual = 100` | 48 | — |

Destino **51 `Corral QA JE Destino OK`**: `es_activo = TRUE`, `id_especie = 40` (compatible con los activos, C1), `capacidad_maxima = 200`, ocupación previa **1** (C3 holgada). Confirmado además por `GET /transferencias/disponibles`, que lo lista como destino válido.

Ambos actores tienen el permiso `(recurso 29, acción 5)` activo:

```sql
SELECT u.id_usuario, u.correo_electronico, u.id_rol,
       EXISTS (SELECT 1 FROM modulo1.permisos p
                WHERE p.id_rol = u.id_rol AND p.id_recurso = 29 AND p.id_accion = 5) AS puede_transferir
  FROM modulo1.usuarios u
 WHERE u.correo_electronico IN ('m2m.nuevo@ejemplo.com','admin@pecuaria.co');
-- 35 | m2m.nuevo@ejemplo.com | 2 | true
--  1 | admin@pecuaria.co     | 1 | true
```

## 4. TC-M02-138 — activo no ACTIVO ✅ APROBADO

Esperado: `HTTP 409` / E-03 / "Solo se pueden transferir activos en estado ACTIVO".

| Actor | Activo | HTTP | `error_code` |
|---|---|---|---|
| Productor | 284 (INACTIVO) | **409** ✅ | `ACTIVO_NO_ACTIVO` ✅ |
| Administrador | 288 (CERRADO) | **409** ✅ | `ACTIVO_NO_ACTIVO` ✅ |

```json
{"error_code":"ACTIVO_NO_ACTIVO",
 "message":"El activo QAJE-TRF-NOACT se encuentra en estado INACTIVO. Solo se pueden transferir activos en estado ACTIVO.",
 "fields":[],"timestamp":"2026-09-10T22:38:38.845552+00:00"}
```

El rechazo proviene inequívocamente de E-03 y no de una causa posterior: se verificó que el `error_code` **no** es ninguno de `SIN_INFRAESTRUCTURA_ORIGEN`, `INFRAESTRUCTURA_ORIGEN_INCORRECTA`, `INFRAESTRUCTURA_DESTINO_INVALIDA`, `DESTINO_IGUAL_ORIGEN` ni `VAL_ENTRADA`. El resto del request era válido (origen coincidente con la asociación vigente, destino activo y compatible, fecha de hoy, motivo no vacío).

**Estado en BD tras las peticiones:** idéntico. Misma asociación (48), mismo origen, mismos contadores, mismo historial.

## 5. TC-M02-139 — transferencia parcial de lote ⛔ BLOQUEADO

**Subtipo: ESCENARIO DE TRANSFERENCIA PARCIAL NO EXPRESABLE POR API.**

El gate contractual de §7 se resolvió en el SETUP, antes de emitir ninguna petición:

```javascript
pm.test('GATE TC-M02-139: el DTO declara exactamente 4 campos, ninguno de cantidad', () => {
  pm.expect(campos).to.eql(['fecha_transferencia','infraestructura_destino_id',
                            'infraestructura_origen_id','motivo_transferencia']);
});
// PASA: no existe cantidad, parcial, unidades ni subconjunto en el esquema.
```

El lote de la ficha sí existe (activo 281, `cantidad_actual = 100`), pero **no hay forma contractual de expresar "40 de 100"**.

### Por qué no se emitió igualmente la petición

Enviar un campo inventado (`"cantidad": 40`) habría sido **activamente peligroso**, no solo inútil. `BaseDTO` se define así:

```python
class BaseDTO(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)   # sin extra='forbid'
```

Pydantic **ignora silenciosamente** los campos desconocidos. La petición no habría sido rechazada: habría sido aceptada como una transferencia **total**, moviendo el lote completo de 100 unidades en el TEST compartido. Es decir, inventar el parámetro habría producido una escritura real y habría dado por "probado" un rechazo que nunca ocurrió. Por eso el sub-caso se bloquea sin ejecutar, conforme a §7 y a la prohibición 12 de §33.

**Equipo responsable de desbloquear:** Desarrollo Backend / responsable funcional — deben definir si RF-48 admite transferencia parcial y, en tal caso, exponer el campo en el contrato.

## 6. TC-M02-140 — fecha futura ❌ RECHAZADO

Esperado: `HTTP 422` / E-10. Fecha enviada: **2026-09-15** (hoy + 5 días, calculada en ejecución para que no caduque).

| Actor | Activo | HTTP esperado | HTTP obtenido | `error_code` |
|---|---|---|---|---|
| Productor | 292 | 422 | **400** ❌ | `VAL_ENTRADA` |
| Administrador | 295 | 422 | **400** ❌ | `VAL_ENTRADA` |

```json
{"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud",
 "fields":[{"field":"fecha_transferencia",
            "message":"Value error, La fecha de transferencia no puede ser posterior a la fecha actual."}],
 "timestamp":"2026-09-10T22:38:39.245069+00:00"}
```

### Aislamiento verificado (§8)

| Condición | Estado |
|---|---|
| Activo ACTIVO | ✅ ambos en estado 1 |
| Origen válido y coincidente con la asociación vigente | ✅ 48 |
| Destino válido, activo y distinto del origen | ✅ 51 |
| C1 (especie) | ✅ destino habilitado para especie 40 |
| C3 (capacidad) | ✅ 1/200 ocupado |
| Sin concurrencia | ✅ peticiones secuenciales, sin transferencia en progreso |
| Fecha futura | ❌ **única condición inválida** |

### Lo que sí funciona y lo que no

La regla de negocio **se cumple**: la fecha futura se rechaza siempre, el motivo comunicado es exacto y señala el campo correcto, y **no se produjo ninguna escritura**. Lo que falla es el contrato de la respuesta, en dos niveles:

1. El código es `400`, no el `422` que fija la ficha para E-10.
2. **`400` no figura entre las respuestas declaradas** de esta ruta en el OpenAPI (`201, 401, 403, 404, 409, 422, 500`). Un cliente generado a partir del contrato no contempla esa rama.

**Resultado: RECHAZADO** (ver DEF-G81-01).

## 7. Confirmación de no persistencia en TEST

| Contador | ANTES | DESPUÉS | Δ |
|---|---|---|---|
| `modulo2.movimientos` | 26 | 26 | **0** |
| `modulo2.historial_infraestructura_activo` | 255 | 255 | **0** |
| `modulo2.bitacora_auditoria_m02` (RF48) | 13 | 13 | **0** |
| `modulo2.activos_biologicos` | 259 | 259 | **0** |
| `modulo9.fincas` | 58 | 58 | **0** |
| Ocupación infra 48 (origen) | 221 | 221 | **0** |
| Ocupación infra 51 (destino) | 1 | 1 | **0** |

Estado por activo tras las cuatro peticiones oficiales:

| Activo | `id_estado` | `id_infraestructura` | Asociación vigente |
|---|---|---|---|
| 284 | 2 (sin cambio) | 48 | 48 |
| 288 | 5 (sin cambio) | 48 | 48 |
| 292 | 1 (sin cambio) | 48 | 48 |
| 295 | 1 (sin cambio) | 48 | 48 |

Ninguna respuesta contenía `id_movimiento` ni el texto "Transferencia registrada exitosamente". El único `POST` no oficial fue `POST /sesiones/` (autenticación), que no modifica datos de negocio.

## 8. Resumen Newman (fase TEST)

**16 peticiones · 64 assertions · 60 correctas / 4 fallidas · 4.8 s.**

Las 4 fallas son el mismo defecto reproducido en los dos actores: `HTTP 422 esperado → 400 obtenido` y `400 no declarado en el contrato`. Todas las assertions de SETUP, TC-138 y verificación de no persistencia pasaron.

> **Corrección de la prueba.** La primera corrida arrojó 6 fallas: dos eran mías, no del producto. Había escrito `pm.expect(fecha_futura).to.be.above(fecha_hoy)` sobre cadenas ISO, y Chai exige un número o `Date` en `to.be.above`. Se corrigió comparando `new Date(...)` y se volvió a ejecutar. Clasificación: **ERROR DE APLICACIÓN DE LA PRUEBA**, sin efecto sobre el resultado sustantivo (el 400 se obtuvo en ambas corridas).

---

# AMBIENTE LOCAL AISLADO

Sub-caso ejecutado aquí: **TC-M02-141**, y solo aquí.

## 9. TC-M02-141 — Rollback ante fallo transaccional ✅ APROBADO

### 9.1 Justificación del ambiente

El escenario exige provocar deliberadamente un fallo dentro de la persistencia. No se ejecutó fault injection en TEST compartido para no afectar a otros equipos ni contaminar datos ajenos. §0 y §22 lo establecen expresamente.

### 9.2 Versión

- Rama: `qa/juan-esteban-m02`
- HEAD: `41369ea4ab3948eacb1ab9b2d0549310e285eeae`
- **¿Coincide con TEST?: SÍ** — es la misma copia de trabajo, sin cambio de rama entre fases.

### 9.3 Base local y preflight (§10.3)

| Campo | Valor real |
|---|---|
| Host | `127.0.0.1` |
| Puerto | `5455` |
| Database | `sgpmp_g81_local_test` |
| Servicio | Clúster PostgreSQL 18.3 **desechable**, creado con `initdb` en el directorio temporal de la sesión y arrancado con `pg_ctl` en un puerto libre |
| Esquema | `alembic upgrade head` → `6993cca9d95e (head)`, 381 tablas en `modulo1`…`modulo9` |
| **Confirmación de NO uso de `158.69.200.27:5448/sgpmp_test`** | **SÍ, confirmado** |

El clúster es propio del test: **no se tocó el servicio PostgreSQL del equipo ni su configuración**, no se requirieron privilegios de administrador y no se usó ninguna credencial remota.

El preflight está codificado en el propio archivo de prueba y aborta la sesión completa (`pytest.exit`) si el DSN o la conexión real apuntan al ambiente compartido. Además, `test_preflight_el_backend_no_apunta_al_test_compartido` comprueba el valor efectivo de `src.shared.database.DATABASE_URL`, que es la que usaría el código del producto (descarta A1):

```
127.0.0.1:5455/sgpmp_g81_local_test    →  host != 158.69.200.27  ✅
                                          port != 5448           ✅
                                          db   != sgpmp_test     ✅
```

### 9.4 Fixture (§12)

Creado exclusivamente en la base local desechable, con un sufijo alfabético distinto por ejecución:

| Elemento | Productor | Administrador |
|---|---|---|
| Activo | 15 | 16 |
| Estado | ACTIVO (1) | ACTIVO (1) |
| Origen | 37 | 39 |
| Destino | 38 | 40 |
| C1 (especie) | ✅ ambas infraestructuras habilitadas para la especie del activo | ✅ |
| C2 | ✅ mismo tipo (`Corral`) | ✅ |
| C3 (capacidad) | ✅ 100, ocupación 0 | ✅ |
| Fecha | hoy (válida) | hoy |
| Sin concurrencia | ✅ | ✅ |

### 9.5 Validación positiva previa (§13)

Sobre un fixture **independiente** del que usa el fault injection, ambos actores ejecutaron una transferencia normal:

```
HTTP 201 · el activo pasó de origen a destino · asociación vigente = [destino] · n_movimientos +1
```

Esto demuestra que el escenario base es válido y que el flujo **llega a persistir**: un 500 posterior no puede atribuirse a C1/C2/C3, estado, permisos, fecha ni datos (descarta A3, A4, A5, A6).

### 9.6 Punto de fault injection (§14 y §15)

- **Clase / use case:** `RegistrarTransferenciaUseCase.execute`
- **Método parcheado:** `SqlAlchemyTransferenciaRepository.guardar`
- **Inicio real de la transacción:** la sesión SQLAlchemy inyectada por `get_db`; las escrituras comienzan dentro del bloque `try`
- **Punto de commit:** `self.db.commit()`, la última sentencia del `try`
- **Manejo de excepción:** `except Exception: self.db.rollback()` → auditoría `TRANSFERENCIA_FALLIDA` con su propio `commit` → `raise`

Orden real del bloque transaccional, leído del código fuente (sin modificarlo):

```text
a) UPDATE modulo2.historial_infraestructura_activo  (cierra la asociación origen)   OK
b) INSERT modulo2.historial_infraestructura_activo  (abre la asociación destino)    OK
c) SET LOCAL app.usuario_id + UPDATE activos_biologicos.id_infraestructura          OK
d) transferencia_repo.guardar(transferencia)        ← EXCEPCIÓN FORZADA AQUÍ
   self.db.commit()                                 ← nunca se alcanza
```

**Justificación de que el fallo ocurre después de escribir y antes del commit (descarta A7 y A8).** No se afirma por lectura del código: se comprueba en ejecución. El propio parche, antes de lanzar la excepción, consulta el estado **dentro de la transacción viva** usando la sesión del caso de uso:

```
dentro de la transaccion (antes del commit): infra=38 vigentes=[38]
```

El activo ya apuntaba al destino y la única asociación vigente ya era la del destino. Las tres escrituras se habían ejecutado; el `commit` no.

### 9.7 Mecanismo (§16 y §17)

`pytest` + `monkeypatch.setattr` sobre la clase real, con `TestClient` de FastAPI sobre el router auténtico (`activo_biologico_router`) y los handlers de error del producto (`register_error_handlers`). **Todo en el mismo proceso Python**, de modo que el parche afecta con certeza al código que atiende la petición (descarta A9). No se usó uvicorn en un proceso aparte.

La sesión de la aplicación es una `Session` real **sin savepoints**: el `commit()` y el `rollback()` observados son los del producto, no una simulación del arnés de pruebas.

**No se modificó código de producción.** El parche vive solo en el archivo de prueba y se revierte al terminar cada test.

### 9.8 Estado ANTES / DESPUÉS (§18 y §20)

Leído con una **conexión psycopg2 independiente** en autocommit sobre la misma base — no con la sesión de la aplicación. Si el rollback hubiera sido incompleto, esa conexión vería los datos a medio escribir (descarta A10).

**Productor** (activo 15, origen 37, destino 38):

| Elemento | ANTES | DESPUÉS | ¿Rollback correcto? |
|---|---|---|---|
| Infraestructura del activo | 37 | **37** | ✅ |
| Asociación vigente | `[37]` | **`[37]`** | ✅ destino no asociado |
| Filas de historial | 1 | **1** | ✅ no quedó asociación destino |
| Eventos de transferencia (`movimientos`) | 0 | **0** | ✅ ningún evento exitoso |
| Ocupación origen | 1 | **1** | ✅ |
| Ocupación destino | 0 | **0** | ✅ |
| Estado del activo | 1 | **1** | ✅ |

**Administrador** (activo 16, origen 39, destino 40):

| Elemento | ANTES | DESPUÉS | ¿Rollback correcto? |
|---|---|---|---|
| Infraestructura del activo | 39 | **39** | ✅ |
| Asociación vigente | `[39]` | **`[39]`** | ✅ |
| Filas de historial | 1 | **1** | ✅ |
| Eventos de transferencia | 0 | **0** | ✅ |
| Ocupación origen | 1 | **1** | ✅ |
| Ocupación destino | 0 | **0** | ✅ |
| Estado del activo | 1 | **1** | ✅ |

**No existe persistencia parcial.** Las tres escrituras confirmadas dentro de la transacción desaparecieron por completo tras el rollback.

### 9.9 Ejecución

- Request: `POST /activos-biologicos/{id}/transferencias` con origen, destino, fecha de hoy y motivo válidos
- HTTP esperado: **500**
- HTTP obtenido: **500** ✅ (ambos actores)
- Excepción controlada: `RuntimeError('TC-M02-141 fault injection')`
- El cuerpo del 500 **no filtra** el detalle técnico de la excepción (verificado explícitamente)

### 9.10 Auditoría del fallo (§21)

- **Fallo registrado: SÍ**
- Evidencia: `modulo2.bitacora_auditoria_m02` con `rf_origen='RF48'` y `tipo_evento='TRANSFERENCIA_FALLIDA'` pasó de **0 a 1** para el activo, en ambos actores.

La auditoría **sobrevive al rollback** porque el caso de uso la escribe *después* de `self.db.rollback()` y la confirma con un `commit()` propio — no queda atrapada en la transacción revertida. Se verificó por separado que el evento de transferencia **exitoso** no existe (`movimientos` = 0), de modo que el registro de auditoría no se confunde con una transferencia realizada (descarta A11).

### 9.11 Veredicto del sub-caso

**APROBADO** para ambos actores. Se cumplen los 20 criterios de §23.

### 9.12 Resumen Pytest

**6 tests · 6 passed · 0 failed · 2.84 s**: 2 preflight de ambiente, 2 de validación positiva y 2 de fault injection (Productor y Administrador).

---

## 10. Cobertura de actores (§4)

| Sub-caso | Productor | Administrador | Ejecuciones |
|---|---|---|---|
| TC-M02-138 | ✅ | ✅ | 2 |
| TC-M02-139 | ⛔ bloqueado | ⛔ bloqueado | 0 |
| TC-M02-140 | ✅ | ✅ | 2 |
| TC-M02-141 | ✅ | ✅ | 2 |
| **Total** | | | **6 de 8 ideales** |

TC-M02-141 se ejecutó con **ambos actores**, sin reducir cobertura por decisión propia ni invocar la autorización de ejecución única prevista en §4. Las dos ejecuciones faltantes corresponden íntegramente al bloqueo de TC-M02-139.

---

## 11. Atribución de errores (§26)

| # | Hipótesis | Cómo se descartó |
|---|---|---|
| A1 | Backend local conectado a BD equivocada | Preflight imprime `127.0.0.1:5455/sgpmp_g81_local_test`; además se verifica `src.shared.database.DATABASE_URL` |
| A2 | HEAD local ≠ TEST | `git rev-parse HEAD` = `41369ea` antes y después de ambas fases; nunca se cambió de rama |
| A3 | Fixture inválido | SELECT previo + validación positiva con `HTTP 201` |
| A4 | Actor sin permisos | Permiso `(29,5)` confirmado por SQL para ambos roles; ninguna respuesta fue 403 |
| A5 | Destino falla C1/C2/C3 | Infraestructuras del fixture con misma especie, mismo tipo y capacidad 100 con ocupación 0; en TEST, destino confirmado por `/disponibles` |
| A6 | Fecha inválida | En TC-141 la fecha es la de hoy y el control positivo devolvió 201 |
| A7 | Fault injection antes de cualquier write | El parche leyó `infra=38, vigentes=[38]` dentro de la transacción: las tres escrituras ya existían |
| A8 | Fault injection después del commit | El parche está en el paso (d); el `commit()` es posterior en el mismo `try` y nunca se ejecutó |
| A9 | Monkeypatch no afecta a la app | `TestClient` en el mismo proceso; el 500 obtenido procede de la excepción inyectada |
| A10 | La consulta DESPUÉS usa otra BD | La verificación usa una conexión independiente al **mismo** DSN local |
| A11 | El "evento" observado es auditoría y no transferencia | Se cuentan por separado: `movimientos` = 0 y `bitacora TRANSFERENCIA_FALLIDA` = 1 |
| A12 | El test modifica el fixture fuera del use case | El seed ocurre antes de la foto ANTES; tras ella solo actúa el request HTTP |

**Clasificación de TC-M02-140: DEFECTO DEL SISTEMA.** Precondición correctamente aislada, comportamiento del producto discrepante del contrato.
**Clasificación de TC-M02-141: sin desviación.**

---

## 12. VEREDICTO FINAL

# ❌ RECHAZADO

Con **TC-M02-139 BLOQUEADO**. TC-M02-138 y TC-M02-141 **APROBADOS**.

---

### DEF-G81-01 — La fecha futura se rechaza con 400 en lugar de 422, y 400 no está en el contrato

| Campo | Valor |
|---|---|
| Sub-caso | TC-M02-140 |
| Ambiente | TEST compartido |
| Actores | Productor (usuario 35) y Administrador (usuario 1) — reproducido en ambos |
| Activos | 292 `QAJE-TRF-OK` y 295 `QAJE-DAT-COMPL` |
| Origen / destino | 48 → 51 (válidos, compatibles, con capacidad) |
| Precondición | Activo ACTIVO, todo el request válido salvo la fecha |
| Esperado | `HTTP 422` con E-10 |
| Obtenido | `HTTP 400` con `error_code: VAL_ENTRADA` |
| Evidencia API | `Resultados/reporte_tc_m02_g81_test.html` — assertions "HTTP 422 (ficha E-10)" y "el codigo declarado esta entre los del contrato", fallidas en ambos actores |
| Evidencia BD | Cero escrituras: `movimientos` 26 → 26, `historial` 255 → 255 |
| Categoría | `HTTP_COM` / contrato |
| **Severidad** | **Medio** |
| Tiempo máximo | 2 días hábiles |
| **Fecha límite** | **2026-09-14** |
| **Equipo responsable** | **Desarrollo Backend** |
| Causa raíz | La regla vive en el validador del DTO (`RegistrarTransferenciaDTO.validar_fecha`), no en el caso de uso. Pydantic la convierte en `RequestValidationError` y `request_validation_error_handler` responde siempre `400 VAL_ENTRADA`. Las reglas equivalentes que sí viven en el caso de uso (E-03) devuelven correctamente su código de dominio |
| Impacto | Un consumidor que siga el contrato no contempla `400` en esta ruta y puede tratarlo como error inesperado en vez de como entrada corregible. La regla de negocio sí se aplica y no hay riesgo de datos: la transferencia nunca se ejecuta |
| Reproducibilidad | 100 % — 2/2 actores, 2/2 corridas |

> **Nota de alcance.** El mismo mecanismo afecta a toda validación declarada en un DTO de esta familia, no solo a E-10. Conviene decidir de forma unificada si estas reglas deben migrar al caso de uso (para emitir 422 con su código de dominio) o si el contrato debe declarar `400`.

---

### BLOQUEO — TC-M02-139

| Campo | Valor |
|---|---|
| **Subtipo** | **ESCENARIO DE TRANSFERENCIA PARCIAL NO EXPRESABLE POR API** |
| Ambiente | TEST compartido |
| Precondición faltante | Un campo contractual para expresar la cantidad a transferir |
| Evidencia | `RegistrarTransferenciaDTO` declara exactamente 4 campos y ninguno es de cantidad; el esquema no contiene `cantidad`, `parcial`, `unidades` ni `subconjunto` |
| Por qué impide ejecutar | Sin campo de cantidad no puede expresarse "40 de 100". Enviar uno inventado sería peor que inútil: `BaseDTO` no declara `extra='forbid'`, así que Pydantic lo ignoraría y la petición se ejecutaría como transferencia **total** del lote de 100 — una escritura real en TEST y un falso positivo de rechazo |
| **Equipo responsable de desbloquear** | **Desarrollo Backend / responsable funcional** |
| Acción necesaria | Definir si RF-48 admite transferencia parcial de lotes. Si la admite, exponer el campo en el contrato y su regla de rechazo; si no la admite, retirar TC-M02-139 de la matriz o reformularlo como validación de campo desconocido |

---

## 13. Declaración de cumplimiento

- ✅ El backend local **nunca** apuntó a `158.69.200.27:5448/sgpmp_test`; verificado por preflight codificado y por `src.shared.database.DATABASE_URL`.
- ✅ No se ejecutaron migraciones ni seeds contra TEST: `alembic upgrade head` corrió exclusivamente sobre `127.0.0.1:5455/sgpmp_g81_local_test`.
- ✅ No se modificó ningún dato de TEST (0 escrituras; siete contadores idénticos antes y después).
- ✅ No se detuvo PostgreSQL de TEST, no se reiniciaron contenedores y no se cortó la red del ambiente.
- ✅ No se introdujo código de fault injection en producción: el parche vive solo en el archivo de prueba y se revierte al terminar cada test.
- ✅ No hubo `commit`, `push`, `merge`, `rebase` ni `deploy`. No se cambió de rama.
- ✅ No se simuló el rollback fallando antes de una escritura: se demostró en ejecución que las tres escrituras existían dentro de la transacción.
- ✅ No se consideró el `HTTP 500` como prueba suficiente: la aprobación se sostiene en el estado ANTES/DESPUÉS leído por una conexión independiente.
- ✅ Se declara explícitamente que **TC-M02-141 se ejecutó en LOCAL AISLADO**, y en ninguna parte se presenta como ejecutado contra TEST.
- ✅ No se mezclaron datos locales y de TEST en la misma evidencia: las secciones están separadas y los identificadores de cada ambiente son distintos.
- ✅ No se declaró ningún defecto sin descartar antes fallo del test o del fixture (§26 completo). El único error de prueba detectado se corrigió y se documentó.
- ✅ Ningún hallazgo queda con severidad, fecha límite o responsable pendientes.

---

## 14. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G81/
├── construir_coleccion.cjs              generador determinista de la colección
├── test_tc_m02_g81.json                 colección Postman (fase TEST)
├── test_tc_m02_g81_rollback.py          Pytest + monkeypatch (fase LOCAL)
└── Resultados/
    ├── reporte_tc_m02_g81_test.html     Newman htmlextra
    ├── reporte_tc_m02_g81_test.json     Newman JSON
    ├── reporte_tc_m02_g81_rollback.xml  JUnit XML
    └── TC-M02-G81_resultado.md          este informe
```

| Fase | Resultado |
|---|---|
| TEST (Newman) | 16 peticiones · 64 assertions · **60 correctas / 4 fallidas** |
| LOCAL (Pytest) | 6 tests · **6 passed / 0 failed** |

### Reproducción de la fase LOCAL

```bash
# clúster desechable en un puerto libre, sin tocar el PostgreSQL del equipo
initdb -D <tmp>/pg_g81 -U postgres --auth-host=trust
pg_ctl -D <tmp>/pg_g81 -o "-p 5455 -c listen_addresses=127.0.0.1" start
createdb -p 5455 -U postgres sgpmp_g81_local_test

export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5455/sgpmp_g81_local_test
export TC_G81_DSN="$DATABASE_URL"
python -m alembic upgrade head
python -m pytest tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G81 -p no:cacheprovider \
  --junitxml=tests/Test_Testing/Test_Modulo2/RF-48/TC-M02-G81/Resultados/reporte_tc_m02_g81_rollback.xml
```

El clúster local se detuvo y se eliminó al terminar la ejecución; no persiste ningún dato de la fase LOCAL.
