# RESULTADO — TC-M02-G93

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **RECHAZADO** |
| Subtipo | Además, 2 sub-casos **BLOQUEADOS**: `MÓDULO SIN SCOPE NO DISPONIBLE` y `M06 NO DISPONIBLE` |
| SUB-CASOS | 1 parcialmente aprobado · **1 con defecto** · **2 bloqueados** (de 3) |
| VARIANTES | 1 aprobada · **1 rechazada** · **2 bloqueadas** (de 4) |
| SOLICITUDES OFICIALES | **2/4** — las otras dos no son ejecutables sin fabricar precondiciones |
| ESCRITURAS TOTALES | **0** por parte de QA |
| Equipo responsable | **Desarrollo Backend** (defecto y desbloqueo de TC-M02-155 y TC-M02-157) |

**Justificación:** TC-M02-156-A se comporta según la ficha. **TC-M02-156-B falla: las fechas futuras se aceptan y el sistema devuelve `HTTP 200` con los datos consolidados completos**, en lugar del `400` exigido. TC-M02-155 y TC-M02-157 no pueden ejecutarse porque **el sistema no implementa el modelo de consumo que RF-50 describe**: no existe identidad de módulo consumidor ni scopes por `tipo_dato`, y M06 no es un principal autenticable.

| Variante | Regla | Esperado | Obtenido | Resultado |
|---|---|---:|---:|---|
| TC-M02-155 | scope insuficiente | 403 | — | ⛔ **BLOQUEADO** |
| TC-M02-156-A | `fecha_inicio > fecha_fin` | 400 | **400** | ✅ **APROBADO** |
| TC-M02-156-B | fechas futuras | 400 | **200 + datos** ❌ | ❌ **RECHAZADO** |
| TC-M02-157 | NIC-41 sin métricas PESO | 422 | — | ⛔ **BLOQUEADO** |

---

## 1. Identificación

- **Caso:** TC-M02-G93 · **Sub-casos:** TC-M02-155, TC-M02-156 (variantes A y B), TC-M02-157
- **RF:** RF-50 — Disponibilidad de datos para módulos analíticos · **CU:** CU12
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** sin modificaciones sobre archivos versionados; solo artefactos de QA sin seguimiento
- **Fecha/hora:** 2026-09-10, 20:46 UTC · duración de la ejecución 4,9 s
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

### 2.1 Contrato revisado

`GET /activos-biologicos/{id_activo}/datos-consolidados` — *«Exponer datos consolidados del activo biológico para módulos analíticos (CU12 - RF-50)»*

| Aspecto | Valor real |
|---|---|
| `tipo_dato` | query, opcional, `default = todos`. Valores documentados: **`eventos \| fases \| estado \| metricas \| todos`** |
| `fecha_inicio` / `fecha_fin` | query, opcionales, formato **`YYYY-MM-DD`** |
| Otros parámetros | `pagina` (≥1), `page_size` (1–100), cabecera `authorization` |
| Respuestas declaradas | **`200, 400, 401, 403, 404, 422`** — los tres códigos que exige el caso están declarados |
| Esquema de respuesta | `DatosConsolidadosResponse`: `historial_eventos`, `historial_fases`, `historico_estados`, `metricas_actuales`, paginación y `fecha_generacion` |
| **`securitySchemes`** | ❌ **no declarado** |
| **`security` global o del endpoint** | ❌ **no declarado** |
| Parámetro de módulo/scope/cliente | ❌ **ninguno** |

Las tres últimas filas son la evidencia contractual del bloqueo de TC-M02-155 y se afirman en la propia colección.

### 2.2 Mecanismo real de autorización y de validación (lectura de código)

```text
Router:  @router.get('/{id_activo}/datos-consolidados',
             dependencies=[Depends(require_permission(_RECURSO, 2))])   # recurso 29, accion 2 (Leer)
         usuario_actual: UsuarioActual = Depends(get_current_user)      # JWT de usuario

DTO (DatosConsolidadosDTO):
  · tipo_dato ∈ {eventos, fases, estado, metricas, todos}   → ValueError si no
  · pagina ≥ 1, page_size ∈ [1,100]                         → ValueError si no
  · fecha_inicio > fecha_fin                                → ValueError  ← TC-M02-156-A
  · ⚠ NINGUNA validacion de fecha futura                                 ← TC-M02-156-B
  Los ValueError se traducen a PARAMETROS_INVALIDOS → ValidationError → HTTP 400

Caso de uso (ConsultarDatosConsolidadosUseCase):
  1. activo existe                → ACTIVO_NO_ENCONTRADO (404)
  2. obtener_datos_consolidados(...)
  3. registrar bitacora RF50 DATOS_ANALITICOS_CONSULTADOS + commit
  ⚠ NINGUNA validacion de suficiencia de metricas PESO ni respuesta 422   ← TC-M02-157
```

Tres consecuencias, todas verificadas después por ejecución:

1. La autorización es **por rol sobre el recurso 29**, no por módulo ni por `tipo_dato`.
2. El orden de fechas sí se valida; **la fecha futura no**.
3. **No existe la regla NIC-41** de RF-50: el caso de uso no comprueba la suficiencia de métricas de peso ni tiene ninguna vía a `422`. El `422` que aparece en OpenAPI es el de validación automática de FastAPI, no una regla de negocio.

---

## 3. SETUP — SOLO LECTURA

**Escrituras SETUP: 0.** La etapa se limitó a `SELECT`, `GET /openapi.json`, `GET /activos-biologicos/{id}/datos-consolidados` (lectura) y un `POST /sesiones/` de autenticación.

### 3.1 Autorización de módulos

| Uso | Módulo | Credencial válida | `tipo_dato` | Scope |
|---|---|---|---|---|
| TC-155 | **no existe ningún módulo consumidor** | — | `metricas` | **el modelo de scopes no existe** |
| TC-156 | consumidor real autorizado: usuario 35 (rol Productor) | **SÍ** | `metricas` | autorizado por RBAC `(recurso 29, acción 2)` |
| TC-157 | **M06 no existe como principal autenticable** | — | valoración / NIC-41 | **no existe** |

**Búsqueda realizada para TC-M02-155 y TC-M02-157**, toda de solo lectura, antes de declarar los bloqueos:

```sql
-- No existe ningún catálogo de scopes ni de módulos consumidores
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_name ILIKE '%scope%'  OR table_name ILIKE '%modulo%'
   OR table_name ILIKE '%consumidor%' OR table_name ILIKE '%api_key%' OR table_name ILIKE '%client%';
--  modulo2 | vw_rf52_auditoria_acceso_modulos_analiticos   (vista de auditoría, no de scopes)
--  modulo7 | clientes_externos, permisos_clientes          (RF-101, clientes externos de M07)
```

- En `src/`, `modulo_consumidor` aparece **únicamente como campo de auditoría** (`String(30)`, con valor por defecto `'modulo2'`); no es una identidad ni participa en ninguna decisión de acceso.
- `modulo7.clientes_externos` y `modulo7.permisos_clientes` pertenecen a RF-101 y gobiernan clientes externos del módulo 7; el endpoint de RF-50 no los consulta: autentica con `get_current_user`, es decir con un JWT de **usuario**.
- El contrato no declara `securitySchemes`, ni `security`, ni ningún parámetro de módulo, scope o cliente.
- El endpoint concede acceso con el permiso `(recurso 29, acción 2)`, que ostentan 22 roles, **sin distinguir el `tipo_dato` solicitado**.

**Por qué no se sustituyó por una aproximación.** Existen roles sin el permiso `(29, 2)` —Contador, Supervisor y otros— y un usuario con uno de ellos recibiría `403`. Ese `403` **no demuestra TC-M02-155**: sería un rechazo del endpoint completo por rol, no del `tipo_dato` solicitado por un módulo con credencial válida, que es la regla que RF-50 define y que §5.4 exige verificar (*«scope para ese tipo_dato = NO»*). El propio paquete advierte en §18-A14 que un 403 procedente de otra regla no vale. Tampoco se retiró ningún scope, conforme a §5.5.

### 3.2 Activos

- **Activo TC-156:** **279** `QAJE-CREC-OK` — ACTIVO, finca 57, infraestructura 48, ciclo desde 2026-06-01. Acceso del consumidor confirmado con una consulta de referencia sin filtros que devolvió `HTTP 200`.
- **Activo del diagnóstico de TC-157:** el mismo 279.
- **Rango NIC-41 candidato:** **2026-06-01 a 2026-08-31** — válido, no futuro, `inicio ≤ fin` y **dentro del ciclo de vida** del activo.
- **Métricas PESO en ese rango:** **0**.

```sql
-- Todos los eventos de crecimiento del activo 279
SELECT ea.id_eventos, ea.fecha::date, ec.tipo_medicion, ec.valor_medicion, ec.unidad_medida
FROM modulo2.eventos_activos ea
JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico = 279 ORDER BY ea.fecha;
--  227 | 2026-09-09 | PESO | 250.00 | kg
--  228 | 2026-09-09 | PESO | 250.00 | kg
--  232 | 2026-09-09 | PESO | 250.00 | kg
--  234 | 2026-09-10 | PESO | 250.00 | kg

-- Métricas PESO dentro del rango candidato: ninguna
SELECT count(*) FROM modulo2.eventos_activos ea
JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico = 279 AND ec.tipo_medicion = 'PESO'
  AND ea.fecha::date BETWEEN '2026-06-01' AND '2026-08-31';   -- 0

-- Fecha actual del ambiente
SELECT current_date;   -- 2026-09-10
```

El escenario cumple la preferencia de §10: el activo **sí tiene pesos fuera del rango** (los cuatro de septiembre), de modo que la ausencia es específica del periodo solicitado y no de un activo vacío.

### 3.3 Inventario mínimo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿Qué módulo se usará para TC-M02-155? | **Ninguno: el modelo de módulos consumidores no existe.** → BLOQUEADO |
| D2 | ¿Qué `tipo_dato` está fuera de su scope? | No aplica: no hay scopes por `tipo_dato`. |
| D3 | ¿Cómo se comprobó que la credencial es válida? | Login `HTTP 200`, `sub` del JWT = 35, y una consulta de referencia al endpoint que devolvió `HTTP 200`. |
| D4 | ¿Qué módulo autorizado se usará para TC-M02-156? | Consumidor real autorizado: usuario 35 (Productor), con permiso `(29, 2)` y acceso legítimo al activo. |
| D5 | ¿Qué activo se usará en TC-M02-156? | **279** `QAJE-CREC-OK`. |
| D6 | ¿Qué formato de fechas exige OpenAPI? | **`YYYY-MM-DD`**, declarado en la descripción de ambos parámetros. |
| D7 | ¿Qué activo se usará en TC-M02-157? | 279 en el diagnóstico; el sub-caso oficial queda bloqueado por falta de M06. |
| D8 | ¿Qué rango válido se utilizará para M06? | 2026-06-01 a 2026-08-31. |
| D9 | ¿Cuántas métricas PESO existen en ese rango? | **0**, confirmado por `SELECT`. |
| D10 | ¿M06 tiene scope válido? | **M06 no existe como principal autenticable.** → BLOQUEADO |
| D11 | ¿Existe ciclo/fase/estado suficiente? | Sí: activo ACTIVO, con una fase productiva y ciclo iniciado el 2026-06-01. |
| D12 | ¿Qué DTO/error schema define OpenAPI? | Entrada por query; errores con `ErrorResponse` (`error_code`, `message`, `fields`, `timestamp`). |

---

## 4. TC-M02-155 — scope

- **Módulo:** —
- **`tipo_dato`:** `metricas`
- **Scope requerido:** consumo de `metricas` por un módulo analítico
- **Scope presente:** **no evaluable — el modelo no existe**
- **HTTP esperado:** 403
- **HTTP obtenido:** — *(no se ejecutó ninguna petición)*
- **¿Se expusieron datos?:** no aplica
- **Resultado:** ⛔ **BLOQUEADO — MÓDULO SIN SCOPE NO DISPONIBLE**

No se envió ninguna petición oficial. La precondición que exige §5.1 —un módulo consumidor autenticado, registrado, con credencial válida y **sin scope para el `tipo_dato` solicitado**— no puede satisfacerse porque el sistema no implementa ninguna de sus tres piezas: identidad de módulo, catálogo de scopes y evaluación por `tipo_dato`. No se retiró ningún permiso ni se fabricó ninguna credencial.

**Equipo responsable de desbloquear: Desarrollo Backend** — debe implementar el modelo de scopes por `tipo_dato` que RF-50 describe; **Implementación** solo si el modelo existiera y faltara configurarlo en TEST, cosa que la evidencia descarta.

---

## 5. TC-M02-156-A — inicio > fin

- **Módulo:** consumidor autorizado, usuario 35
- **Activo:** 279
- **`fecha_inicio`:** `2026-08-20`
- **`fecha_fin`:** `2026-08-10`
- **HTTP esperado:** 400
- **HTTP obtenido:** **400** ✅
- **Mensaje:**

```text
error_code: PARAMETROS_INVALIDOS
Parámetro inválido: 1 validation error for DatosConsolidadosDTO
Value error, La fecha de inicio (2026-08-20) no puede ser posterior a la fecha de fin (2026-08-10).
```

- **Resultado:** ✅ **APROBADO**

Las ocho verificaciones de §6.4 se cumplen: consumidor autorizado (ni 401 ni 403), activo existente (sin 404), `tipo_dato` válido, **solo el orden de fechas es inválido** —ambas fechas están en el pasado, comprobado por aserción—, `HTTP 400`, mensaje que identifica exactamente `fecha_inicio > fecha_fin` con los dos valores, **ninguna sección de datos consolidados en el cuerpo** y ninguna escritura.

> **Nota sobre el mensaje.** El texto correcto va envuelto en la traza cruda de Pydantic (`1 validation error for DatosConsolidadosDTO … [type=value_error, input_value={…}] For further information visit https://errors.pydantic.dev/…`), que expone el nombre del DTO y el diccionario de entrada. Cumple el criterio de la matriz, pero conviene depurarlo: se registra como OBS-G93-03.

---

## 6. TC-M02-156-B — fechas futuras

- **Fecha actual observada:** **2026-09-10** (confirmada por `SELECT current_date` y por la cabecera `Date` del backend)
- **`fecha_inicio` futura:** **2026-09-11**
- **`fecha_fin` futura:** **2026-09-12**
- **¿`inicio < fin`?:** **SÍ** — aislamiento correcto respecto de la variante A
- **HTTP esperado:** 400
- **HTTP obtenido:** **200** ❌
- **Mensaje:** ninguno; el cuerpo es una respuesta de éxito completa
- **Resultado:** ❌ **RECHAZADO**

El sistema **aceptó un rango íntegramente futuro** y devolvió `DatosConsolidadosResponse` con las dieciséis propiedades del esquema, incluidas `historial_eventos`, `historial_fases`, `historico_estados` y `metricas_actuales`.

```json
"metricas_actuales": {
  "peso_actual": 250.0,
  "unidad_peso": "kg",
  "fecha_ultimo_peso": "2026-09-10",
  ...
},
"historial_eventos": [],
"total_registros": 0
```

Dos hechos sobre esa respuesta:

1. `historial_eventos` está vacío, coherente con un rango futuro.
2. **`metricas_actuales` devuelve un peso fechado el 2026-09-10, fuera del rango solicitado**, sin ningún indicador de que no pertenece al periodo. Se amplía en §7 y en OBS-G93-02.

De las ocho verificaciones de §7.4 se cumplen cuatro —módulo autorizado, activo existente, fechas realmente futuras y `inicio < fin`— y **fallan tres**: `HTTP 400`, motivo temporal y no exposición de datos. La octava, ausencia de escrituras, se cumple.

---

## 7. TC-M02-157 — NIC-41 sin peso

- **Consumidor:** **M06 — no disponible**
- **Activo:** 279 (en el diagnóstico)
- **Rango:** 2026-06-01 a 2026-08-31 — válido, no futuro, dentro del ciclo de vida
- **Scope:** no evaluable
- **Número de métricas PESO en rango:** **0**, confirmado por `SELECT`
- **HTTP esperado:** 422
- **HTTP obtenido:** — *(no se ejecutó como petición oficial)*
- **Resultado:** ⛔ **BLOQUEADO — M06 NO DISPONIBLE**

§3 del paquete prohíbe expresamente sustituir M06 por Administrador, Productor o M04, y el sistema no ofrece ningún principal que represente a M06: la autenticación es por usuario y la autorización por rol, sin identidad de módulo. Por eso **no se ejecutó la petición oficial**.

### 7.1 Diagnóstico complementario (no es el sub-caso oficial)

Para caracterizar el hueco sin sustituir a M06, se lanzó **una** consulta de solo lectura con el consumidor autorizado, claramente etiquetada como diagnóstica en `02-DIAGNOSTICO`:

```text
GET /activos-biologicos/279/datos-consolidados?tipo_dato=metricas
    &fecha_inicio=2026-06-01&fecha_fin=2026-08-31
→ HTTP 200
   metricas_actuales: { "peso_actual": 250.0, "unidad_peso": "kg", "fecha_ultimo_peso": "2026-09-10" }
   historial_eventos: []   ·   total_registros: 0
```

Con **cero métricas PESO en el rango solicitado**, el sistema responde `200` y entrega un `peso_actual` cuya fecha —2026-09-10— **queda fuera del rango pedido**. `historial_eventos` sí respeta el filtro; `metricas_actuales` no.

Esto no aprueba ni rechaza TC-M02-157, que sigue bloqueado, pero muestra que **aunque M06 existiera, el sub-caso no podría aprobarse**: la regla de suficiencia de métricas de peso no está implementada (§2.2) y no hay ninguna vía a `422`. Se registra como OBS-G93-02.

---

## 8. Confirmación de solo lectura

| Métrica | Valor |
|---|---|
| SQL writes ejecutados por QA | **0** |
| POST | **1** — únicamente `POST /sesiones/` de autenticación, que no crea datos de dominio |
| PUT | **0** |
| PATCH | **0** |
| DELETE | **0** |
| Cambios observados en datos de dominio | **0** |

```sql
SELECT ab.id_activo_biologico, ab.identificador, es.nombre AS estado, ab.id_infraestructura,
       (SELECT count(*) FROM modulo2.eventos_activos ea
         WHERE ea.id_activo_biologico = ab.id_activo_biologico) AS n_eventos,
       (SELECT count(*) FROM modulo2.gestiones_fases gf
         WHERE gf.id_activo_biologico = ab.id_activo_biologico) AS n_fases
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos es ON es.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico = 279;
--  279 | QAJE-CREC-OK | ACTIVO | 48 | 4 | 1     (idéntico antes y después)

SELECT count(*) FROM modulo2.eventos_activos ea
JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico = 279 AND ec.tipo_medicion = 'PESO';   -- 4, sin cambios
```

No se modificaron activo, eventos, pesos, fases, estado, infraestructura, scopes ni permisos.

### 8.1 Auditoría del acceso — V18

RF-50 audita las consultas, y el endpoint lo hace: **el propio producto** escribió tres filas en `modulo2.bitacora_auditoria_m02` como parte de su comportamiento normal, una por cada consulta que devolvió `200`.

```sql
SELECT id_bitacora, rf_origen, tipo_evento, resultado, id_activo_biologico,
       id_usuario_responsable, modulo_consumidor, timestamp_evento
FROM modulo2.bitacora_auditoria_m02 WHERE rf_origen = 'RF50' ORDER BY id_bitacora DESC LIMIT 3;
--  1105 | RF50 | DATOS_ANALITICOS_CONSULTADOS | EXITOSO | 279 | 35 | modulo2 | 2026-09-10 20:46:38.80+00
--  1104 | RF50 | DATOS_ANALITICOS_CONSULTADOS | EXITOSO | 279 | 35 | modulo2 | 2026-09-10 20:46:38.45+00
--  1103 | RF50 | DATOS_ANALITICOS_CONSULTADOS | EXITOSO | 279 | 35 | modulo2 | 2026-09-10 20:46:37.90+00
```

Corresponden a la consulta de referencia del SETUP, a TC-M02-156-B y al diagnóstico. **TC-M02-156-A no generó registro**, porque el rechazo ocurre en el router antes de llegar al caso de uso: solo se auditan los accesos exitosos.

Dos precisiones:

1. **Estas escrituras no son de QA**: son del producto, previstas por RF-50, y QA no ejecutó ninguna sentencia de escritura.
2. El campo `modulo_consumidor` queda fijado a `'modulo2'` en todos los registros. La auditoría **no identifica qué módulo analítico consumió los datos**, lo que refuerza la conclusión del bloqueo de TC-M02-155: el sistema no maneja el concepto de módulo consumidor en ninguna capa, tampoco en la trazabilidad.

---

## 9. Diagnóstico

**¿Fue necesario? SÍ**, para TC-M02-156-B.

- **Sub-caso:** TC-M02-156-B. **Módulo:** consumidor autorizado, usuario 35. **Activo:** 279.
- **Esperado:** `HTTP 400` con motivo temporal de fecha futura.
- **Obtenido:** `HTTP 200` con `DatosConsolidadosResponse` completo.
- **Reproducibilidad:** el comportamiento es determinista y quedó confirmado dos veces en la misma corrida, con dos rangos distintos: el futuro (2026-09-11 a 2026-09-12) y el histórico del diagnóstico (2026-06-01 a 2026-08-31); ambos devolvieron `200`. La causa está además confirmada por lectura de código.

**Hipótesis descartadas (§18):**

| # | Hipótesis | Descarte |
|---|---|---|
| A1 | Token inválido o expirado | Login `200`, `sub` = 35, y la consulta de referencia del SETUP devolvió `200`. |
| A3 | `tipo_dato` no existe | `metricas` figura entre los valores documentados en el contrato; afirmado en el SETUP. |
| A4 | Activo no existe | `SELECT` y consulta de referencia: el activo 279 existe y responde. |
| A5 | Otro parámetro inválido | Solo se enviaron `tipo_dato`, `fecha_inicio` y `fecha_fin`; `pagina` y `page_size` quedaron en sus valores por defecto. |
| A6 | 156-B también tenía inicio > fin | **Descartada por aserción:** `2026-09-11 < 2026-09-12`. |
| A7 | Las fechas no eran realmente futuras | **Descartada por aserción** contra la fecha actual observada, 2026-09-10; ambas son posteriores. |
| A11 | El endpoint usa otro filtro o nombre | Los parámetros son los del contrato: `fecha_inicio` y `fecha_fin`, formato `YYYY-MM-DD`. |
| A12 | Variable Postman sin resolver | La URL final consta en el reporte JSON con las fechas resueltas. |
| A13 | La aserción esperaba un texto equivocado | La aserción que decide es el **código HTTP**, que la ficha fija en `400`; el sistema devolvió `200`, no un 400 con otro texto. |
| A14 | El resultado proviene de otra regla | No hubo rechazo alguno: la respuesta es un éxito con datos. |

- **Atribución: DEFECTO DEL PRODUCTO.**
- **Causa raíz: confirmada por QA.** `DatosConsolidadosDTO` valida `tipo_dato`, `pagina`, `page_size` y el orden `fecha_inicio > fecha_fin`, pero **no incluye ninguna comprobación de fecha futura**. Ninguna otra capa la suple.

---

## 10. VEREDICTO FINAL

# ❌ RECHAZADO

**con 2 de los 3 sub-casos adicionalmente BLOQUEADOS**

**Justificación:** el gate se completó y el caso se ejecutó sin una sola escritura de QA. TC-M02-156-A cumple la ficha íntegramente. **TC-M02-156-B revela un defecto confirmado**: las fechas futuras no se validan y el endpoint entrega datos consolidados. TC-M02-155 y TC-M02-157 no pueden ejecutarse porque el sistema **no implementa el modelo de consumo por módulos con scopes que RF-50 describe**, y fabricar esa precondición está prohibido.

### DEF-G93-01 — Las fechas futuras se aceptan y devuelven datos

```text
TC-M02-G93 / TC-M02-156-B — RECHAZADO

Módulo consumidor: consumidor autorizado real (usuario 35, rol Productor), con permiso
  (recurso 29, acción 2) y acceso legítimo al activo. No existe identidad de módulo en el sistema.
Activo: 279 QAJE-CREC-OK · ACTIVO · finca 57
tipo_dato: metricas
Filtros: fecha_inicio = 2026-09-11, fecha_fin = 2026-09-12

Precondiciones confirmadas:
- credencial válida y consulta de referencia previa con HTTP 200;
- activo existente y accesible;
- tipo_dato válido según el contrato;
- fecha_inicio < fecha_fin, para aislar exclusivamente la condición futura;
- ambas fechas posteriores a la fecha actual del ambiente (2026-09-10), verificada por
  SELECT current_date y por la cabecera Date del backend. No se modificó ningún reloj.

Esperado:
  HTTP 400 BAD REQUEST con un motivo que identifique la validación temporal de fecha futura,
  sin exponer datos consolidados.

Obtenido:
  HTTP 200 OK con DatosConsolidadosResponse completo: historial_eventos, historial_fases,
  historico_estados, metricas_actuales, paginación y fecha_generacion.

Evidencia API: reporte Newman, petición «TC-M02-156-B»; tres aserciones fallidas
  (código HTTP, motivo temporal y no exposición de datos).
Evidencia BD: SELECT current_date = 2026-09-10; el activo 279 no sufrió cambios.
¿Se expusieron datos?: SÍ — la respuesta incluye las cinco secciones de datos del activo.
Categoría: VAL_ENTRADA.
Severidad: Medio.
Tiempo máximo: 2 días hábiles.
Fecha límite: 2026-09-14.
Equipo responsable: Desarrollo Backend.
Causa raíz: confirmada por QA — DatosConsolidadosDTO valida tipo_dato, paginación y el orden
  de las fechas, pero no comprueba que el rango no sea futuro; ninguna otra capa lo suple.
Impacto: un módulo analítico puede consultar periodos que aún no han ocurrido y recibir una
  respuesta de éxito. El historial llega vacío, pero metricas_actuales entrega un peso fechado
  fuera del rango, de modo que el consumidor no puede distinguir «sin datos en el periodo» de
  «datos válidos del periodo». RF-50 lo define como consulta inválida.
Reproducibilidad: determinista; confirmado con dos rangos distintos en la misma corrida y
  corroborado por lectura de código.
```

### BLOQ-G93-02 — TC-M02-155 no ejecutable: no existe el modelo de módulos con scopes

```text
Subtipo: MÓDULO SIN SCOPE NO DISPONIBLE
Sub-caso: TC-M02-155

Qué precondición falta: un módulo consumidor interno, registrado y autenticable, cuya
  credencial sea válida pero que carezca del scope para el tipo_dato solicitado.

Evidencia:
- el contrato no declara securitySchemes, ni security global o por endpoint, ni ningún
  parámetro de módulo, scope o cliente (aserciones del SETUP sobre el contrato vivo);
- el endpoint autoriza con require_permission(recurso 29, acción 2) sobre el rol del usuario,
  sin distinguir el tipo_dato solicitado;
- information_schema no devuelve ninguna tabla de scopes ni de módulos consumidores;
  modulo7.clientes_externos y permisos_clientes pertenecen a RF-101 y no intervienen aquí;
- en el código, modulo_consumidor existe solo como campo de auditoría con valor fijo 'modulo2'.

Por qué impide ejecutar: sin identidad de módulo ni scopes por tipo_dato, no hay forma de
  construir «credencial válida + scope ausente». Un 403 obtenido con un rol sin el permiso
  (29,2) probaría el control de acceso al endpoint completo, no la regla de RF-50, y §18-A14
  advierte expresamente contra esa confusión. Retirar scopes está prohibido por §5.5.

Equipo responsable de desbloquearlo: Desarrollo Backend (implementar el modelo de scopes por
  tipo_dato que RF-50 describe). Implementación solo si el modelo existiera y faltara
  habilitarlo en TEST, cosa que la evidencia descarta.
Acción necesaria: definir e implementar identidad de módulo consumidor y scopes por tipo_dato,
  y volver a ejecutar el sub-caso.
```

### BLOQ-G93-03 — TC-M02-157 no ejecutable: M06 no es un consumidor autenticable

```text
Subtipo: M06 NO DISPONIBLE
Sub-caso: TC-M02-157

Qué precondición falta: M06 como consumidor autenticado con scope de valoración/NIC-41.
  §3 prohíbe expresamente sustituirlo por Administrador, Productor o M04.

Evidencia: la misma de BLOQ-G93-02 — la autenticación del endpoint es por usuario y la
  autorización por rol; no existe ningún principal que represente a M06.

Hallazgo adicional: los datos exigidos por la precondición SÍ existen (activo 279 con un rango
  válido, no futuro, dentro de su ciclo y con 0 métricas PESO, teniendo pesos fuera del rango),
  de modo que el bloqueo no es por falta de datos. Pero el diagnóstico de §7.1 muestra que,
  aun con M06 disponible, el sub-caso no podría aprobarse: la regla de suficiencia de métricas
  de peso no está implementada y el caso de uso no tiene ninguna vía a 422. Ver OBS-G93-02.

Equipo responsable de desbloquearlo: Desarrollo Backend.
Acción necesaria: proveer la identidad de M06 con su scope e implementar la validación NIC-41
  de RF-50; después, reejecutar el sub-caso.
```

---

## 11. Datos para Registro de Errores

### DEF-G93-01 — Fechas futuras aceptadas en `datos-consolidados`

- **ID sugerido:** DEF-G93-01
- **Descripción:** `GET /activos-biologicos/{id}/datos-consolidados` acepta un rango íntegramente futuro (`fecha_inicio` y `fecha_fin` posteriores a la fecha actual, con `inicio < fin`) y responde `HTTP 200` con los datos consolidados del activo. RF-50 y la matriz definen la consulta a fechas futuras como inválida, con `HTTP 400`.
- **RF:** RF-50 · **Caso/sub-caso:** TC-M02-G93 / TC-M02-156-B · **Actor:** consumidor autorizado (usuario 35)
- **Categoría:** `VAL_ENTRADA` · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Medio** · **Tiempo máximo:** 2 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-14** · **Estado:** Abierto
- **Evidencia:** [reporte_tc_m02_g93.json](reporte_tc_m02_g93.json) y [reporte_tc_m02_g93.html](reporte_tc_m02_g93.html), petición «TC-M02-156-B»; `SELECT current_date` de §3.2.
- **Causa raíz:** confirmada por QA — `DatosConsolidadosDTO` no valida que el rango no sea futuro.

### OBS-G93-02 — `metricas_actuales` ignora el filtro temporal y RF-50 no valida la suficiencia NIC-41

- **ID sugerido:** OBS-G93-02
- **Descripción:** con un rango válido y **cero métricas PESO dentro de él**, el endpoint responde `200` y entrega `metricas_actuales.peso_actual = 250.0` con `fecha_ultimo_peso = 2026-09-10`, **fuera del rango solicitado**. `historial_eventos` sí respeta el filtro y llega vacío. Además, el caso de uso no implementa ninguna validación de suficiencia de métricas de peso ni ninguna vía a `422`, que es lo que RF-50 exige para las consultas críticas de NIC-41.
- **RF:** RF-50 · **Caso/sub-caso:** TC-M02-G93 / TC-M02-157 — sustenta el bloqueo, no lo resuelve · **Actor:** consumidor autorizado (el sub-caso oficial exige M06)
- **Categoría:** `FLUJO` / integridad analítica · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Severo** — un consumidor de valoración financiera puede tomar un peso ajeno al periodo como si perteneciera a él, sin ninguna señal · **Tiempo máximo:** 1 día hábil · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-11** · **Estado:** Abierto
- **Evidencia:** petición de `02-DIAGNOSTICO` con el rango 2026-06-01 a 2026-08-31; `SELECT` que confirma 0 métricas PESO en ese rango y 4 fuera de él; lectura del caso de uso.
- **Causa raíz:** **causa raíz no confirmada por QA** en cuanto a la intención. El campo se llama `metricas_actuales`, de modo que devolver la métrica más reciente podría ser deliberado; lo que sí está confirmado es que **no existe la regla de RF-50** que debería rechazar la consulta cuando el rango carece de las métricas de peso necesarias. Corresponde a Desarrollo decidir si se filtra el campo por rango, si se señala explícitamente que la métrica es ajena al periodo o si se implementa el `422` previsto.

### OBS-G93-03 — El mensaje de error expone la traza cruda de Pydantic

- **ID sugerido:** OBS-G93-03
- **Descripción:** el rechazo de TC-M02-156-A devuelve el texto correcto envuelto en la traza de Pydantic: *«Parámetro inválido: 1 validation error for DatosConsolidadosDTO … [type=value_error, input_value={'tipo_dato': 'metricas', …}] For further information visit https://errors.pydantic.dev/2.13/v/value_error»*. Expone el nombre interno del DTO, el diccionario de entrada y una URL externa.
- **RF:** RF-50 · **Caso/sub-caso:** TC-M02-G93 / TC-M02-156-A · **Actor:** consumidor autorizado
- **Categoría:** `HTTP_COM` / calidad del mensaje · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Bajo** — el código y el contenido sustantivo son correctos; es ruido de implementación filtrado al cliente · **Tiempo máximo:** 3 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-15** · **Estado:** Abierto
- **Impacto en el caso:** ninguno. TC-M02-156-A se aprueba.
- **Causa raíz:** confirmada por QA — el router captura `ValueError` y concatena `str(exc)`, que en Pydantic 2 incluye la traza completa, en lugar de extraer solo `errors()[0]['msg']` como sí hace en la rama de `_PydanticValidationError`.

---

## 12. Declaración de cumplimiento

- ✅ No se modificó código fuente. Los archivos de `src/` solo se leyeron para conocer el mecanismo de autorización y las validaciones.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama. El árbol no tiene modificaciones sobre archivos versionados.
- ✅ **No hubo SQL de escritura.** Todas las sentencias fueron `SELECT` con el usuario `member_qa`.
- ✅ **SETUP = 0 escrituras.**
- ✅ **Caso principal = 0 escrituras de QA.** Las cuatro consultas oficiales y diagnósticas son `GET`. El único `POST` fue el de autenticación. Las tres filas de bitácora que aparecieron las escribió **el producto** al auditar los accesos exitosos, conforme a RF-50.
- ✅ **No se crearon ni modificaron scopes** ni permisos: `modulo1.permisos` no registra cambios con fecha de hoy.
- ✅ **No se crearon ni eliminaron eventos PESO:** el activo 279 conserva sus 4 métricas y sigue teniendo 0 dentro del rango de diagnóstico.
- ✅ **No se modificaron fechas del sistema.** Las fechas futuras se calcularon contra la fecha observada del ambiente.
- ✅ Cada variante aisló una sola condición: en 156-A ambas fechas son pasadas y solo el orden es inválido; en 156-B `inicio < fin` y ambas futuras.
- ✅ No se usaron escenarios de otros casos ni se sustituyó a M06.
- ✅ No se aceptó ningún 4xx genérico como aprobación: cada respuesta se verificó por código, por contenido y por exclusión de otras causas.
- ✅ No se inventaron resultados: todo procede del reporte de Newman o de una consulta `SELECT` reproducible.

---

## 13. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-50/TC-M02-G93/
├── construir_coleccion.cjs        generador determinista de la colección
├── test_tc_m02_g93.json           colección Postman (00-SETUP-LECTURA, 01-CASO-PRINCIPAL, 02-DIAGNOSTICO)
└── Resultados/
    ├── reporte_tc_m02_g93.html    reporte Newman (htmlextra)
    ├── reporte_tc_m02_g93.json    reporte Newman (json), con URLs y cuerpos de respuesta
    └── TC-M02-G93_resultado.md    este informe
```

Un solo HTML, un solo JSON, un solo informe. No se generaron `.log` separados.

**Ejecución:** 6 peticiones · 6 scripts de prueba · **31 aserciones, 3 fallidas** · 4,9 s · **2 peticiones oficiales de 4**, más una diagnóstica claramente etiquetada. Las 3 aserciones fallidas son exactamente la evidencia de DEF-G93-01; las otras dos solicitudes oficiales corresponden a los sub-casos bloqueados.
