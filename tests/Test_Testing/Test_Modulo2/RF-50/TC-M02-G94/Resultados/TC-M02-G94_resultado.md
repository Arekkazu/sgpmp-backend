# RESULTADO — TC-M02-G94

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **BLOQUEADO** |
| Subtipo | **CREDENCIAL M04 NO DISPONIBLE** + **MÓDULO DE CONTROL NO DISPONIBLE** |
| TC-M02-158 | ⛔ **BLOQUEADO** |
| TC-M02-164 | ✅ **APROBADO** |
| TC-M02-165 | ✅ **APROBADO** |
| Máximo requests M04 antes de 429 | **no medible** — M04 no existe como consumidor autenticable |
| Módulo de control afectado | no evaluable |
| POST/PUT produjeron cambios | **NO** |
| Datos expuestos sin autenticación | **NO** |
| Equipo responsable | **Desarrollo Backend** (desbloqueo de TC-M02-158 y observación OBS-G94-01) |

**Justificación:** los dos controles verificables se cumplen sin reservas. La API de exposición **rechaza POST y PUT con `HTTP 405` y `Allow: GET`**, antes incluso de mirar el cuerpo, y los datos de M02 quedan idénticos; sin credencial y con credencial inválida responde **`HTTP 401`** sin filtrar un solo dato del activo. En cambio **TC-M02-158 no puede ejecutarse**: exige M04 como consumidor autenticado y un segundo módulo de control, y el sistema no implementa identidades de módulo. Fabricar esa precondición está prohibido, de modo que el caso no puede declararse APROBADO.

> **Hallazgo asociado, no demostrado por ejecución:** el endpoint de exposición **no aplica ningún limitador de tasa**. El proyecto tiene un helper `rate_limit`, pero el router de activos biológicos no lo importa ni lo usa, y el contrato no declara `429`. Se registra como OBS-G94-01.

---

## 1. Identificación

- **Caso:** TC-M02-G94 · **Sub-casos:** TC-M02-158, TC-M02-164 (variantes A y B), TC-M02-165 (variantes A y B)
- **RF:** RF-50 — Disponibilidad de datos para módulos analíticos · **CU:** CU12
- **Tipo:** Seguridad — OWASP API4 / API1–API5 / API2
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** sin modificaciones sobre archivos versionados; solo artefactos de QA sin seguimiento
- **Fecha/hora:** 2026-09-10 — Pytest a las 20:57 UTC, Newman a las 20:58 UTC
- **Ambiente:** TEST desplegado, HTTPS — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Herramientas:** **Pytest** (TC-M02-164 y TC-M02-165) + **Postman/Newman** (evidencia de métodos y autenticación) + **k6** (script entregado, **no ejecutado**; ver §4)
- **Evidencia BD:** PostgreSQL TEST `158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, sesión abierta en modo `readonly`

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
| M04 autenticado | ❌ **no existe** |
| Módulo de control | ❌ **no existe** |

### 2.1 Contrato revisado

`/activos-biologicos/{id_activo}/datos-consolidados`

| Aspecto | Valor real |
|---|---|
| Métodos declarados | **únicamente `get`** — ni `post` ni `put` ni ningún otro |
| Respuestas del GET | `200, 400, 401, 403, 404, 422` |
| ¿`401` declarado? | ✅ sí — el que exige TC-M02-165 |
| ¿`405` declarado? | ❌ no, pero el enrutador lo devuelve por no existir el método (comportamiento correcto) |
| **¿`429` declarado?** | ❌ **no**, pese a que RF-50 fija 100 solicitudes/minuto |
| `securitySchemes` / `security` | ❌ **no declarados** |
| Parámetro de módulo, scope o cliente | ❌ **ninguno** |

Que la ruta declare **solo `get`** es evidencia contractual a favor de TC-M02-164 (V14): el contrato no expone escritura. Que **no declare `429`** es la primera señal de que el control de tasa de RF-50 no está implementado, y se afirma en la propia colección.

### 2.2 Mecanismo real de autenticación, autorización y tasa (lectura de código)

```text
Autenticación:  get_current_user  → JWT de USUARIO. No hay credenciales de servicio.
Autorización:   require_permission(recurso 29, acción 2) → por ROL del usuario.
Rate limiting:  el proyecto tiene src/shared/rate_limit.py, un limitador reutilizable…
                …pero activo_biologico_router.py NO lo importa ni lo usa.
Middlewares:    main.py solo registra CORSMiddleware y RequestContextMiddleware.
```

Sobre el helper existente, según su propia documentación:

- limita **por usuario autenticado**, no por módulo;
- es un contador **en memoria y de un solo proceso**, no distribuido: con varias réplicas, el límite efectivo se multiplica;
- se aplica **endpoint por endpoint** como dependencia explícita (por ejemplo `rate_limit(10, 60, alcance="dispositivos_iot_registrar")`).

El endpoint de RF-50 no lo declara en ninguna de sus dependencias.

---

## 3. SETUP — SOLO LECTURA

**SQL writes: 0.** La sesión de Pytest abre PostgreSQL con `set_session(readonly=True)`, de modo que el propio servidor rechazaría cualquier escritura accidental.

| Campo | Valor |
|---|---|
| Activo | **279** `QAJE-CREC-OK` — ACTIVO, finca 57, infraestructura 48, especie 40 |
| Endpoint | `GET /activos-biologicos/279/datos-consolidados` |
| `tipo_dato` | `metricas` |
| **M04** | ❌ **no existe como principal autenticable** |
| Scope M04 | no aplica |
| **Módulo control** | ❌ **no existe** |
| Scope control | no aplica |
| Módulo TC-164 | consumidor real con acceso de lectura: usuario 35, rol Productor, permiso `(recurso 29, acción 2)` |
| GET de lectura previo | ✅ **HTTP 200** sobre el mismo activo y recurso, antes de los intentos de escritura |
| Mecanismo de autenticación | `Authorization: Bearer <JWT de usuario>` |
| Headers de rate limit | **ninguno** en las respuestas: no aparecen `RateLimit-*`, `X-RateLimit-*` ni `Retry-After` |
| Semántica de ventana observada | **no observable**: sin limitador, no hay ventana que documentar |

### 3.1 Inventario previo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿Qué activo se utilizará? | **279** `QAJE-CREC-OK`. |
| D2 | ¿Existe y tiene datos consolidados? | Sí: `GET` → 200 con `id_activo_biologico = 279` y la sección `metricas_actuales`. |
| D3 | ¿M04 tiene credencial válida? | **NO. M04 no existe.** → BLOQUEADO |
| D4 | ¿M04 tiene scope válido? | No aplica: no hay modelo de scopes. |
| D5 | ¿Qué módulo se usará como control? | **Ninguno disponible.** → BLOQUEADO |
| D6 | ¿Ese módulo tiene credencial/scope? | No aplica. |
| D7 | ¿Qué módulo se usará para TC-M02-164? | Consumidor real autorizado (usuario 35), con acceso de lectura confirmado. |
| D8 | ¿Su GET normal devuelve 200? | ✅ Sí, verificado antes de cada intento de escritura. |
| D9 | ¿Qué métodos documenta OpenAPI? | **Solo `GET`.** |
| D10 | ¿Qué mecanismo de autenticación usa la API? | JWT de usuario en `Authorization: Bearer`. No hay autenticación servicio a servicio. |
| D11 | ¿Qué headers de rate-limit existen? | **Ninguno.** |
| D12 | ¿Cómo observar pasivamente el reset de cuota? | **No es posible**: no hay cuota ni cabeceras que la expongan. |

### 3.2 Estado base para la verificación de integridad

```sql
SELECT es.nombre AS estado, ab.id_infraestructura, ab.id_especie, ab.descripcion,
       (SELECT count(*) FROM modulo2.eventos_activos ea
         WHERE ea.id_activo_biologico = ab.id_activo_biologico) AS n_eventos,
       (SELECT count(*) FROM modulo2.eventos_activos ea
          JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
         WHERE ea.id_activo_biologico = ab.id_activo_biologico) AS n_crecimiento,
       (SELECT count(*) FROM modulo2.gestiones_fases gf
         WHERE gf.id_activo_biologico = ab.id_activo_biologico) AS n_fases,
       (SELECT count(*) FROM modulo2.historial_infraestructura_activo h
         WHERE h.id_activo_biologico = ab.id_activo_biologico) AS n_historial
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos es ON es.id_estado_activo_biologico = ab.id_estado
WHERE ab.id_activo_biologico = 279;
```

| estado | infra | especie | descripción | eventos | crecimiento | fases | historial |
|---|---:|---:|---|---:|---:|---:|---:|
| ACTIVO | 48 | 40 | QAJE-CREC-OK | 4 | 4 | 1 | 1 |

---

## 4. TC-M02-158 — RATE LIMITING

### Resultado: ⛔ **BLOQUEADO — CREDENCIAL M04 NO DISPONIBLE** *(y, en la misma causa, MÓDULO DE CONTROL NO DISPONIBLE)*

**No se emitió ninguna solicitud de carga.**

### Precondición que falta

La matriz fija literalmente *«Precondición: M04 autenticado»*, y §6.6 exige además un segundo módulo autorizado —M06 u M08— para demostrar que el límite es **por módulo** y no global. Ninguno de los dos existe:

- la API autentica con **JWT de usuario** (`get_current_user`) y autoriza **por rol** (`require_permission(29, 2)`);
- el contrato no declara `securitySchemes`, ni `security`, ni ningún parámetro de módulo, scope o cliente;
- `information_schema` no devuelve ninguna tabla de módulos consumidores ni de scopes;
- en el código, `modulo_consumidor` existe únicamente como campo de auditoría con valor fijo `'modulo2'`.

Sin identidades de módulo no hay cuotas por módulo que medir, ni un control con el que comparar. §12 del paquete asigna a esta situación exactamente los subtipos `CREDENCIAL M04 NO DISPONIBLE` y `MÓDULO DE CONTROL NO DISPONIBLE`.

### Por qué no se sustituyó por una ráfaga con credencial de usuario

Habría sido técnicamente posible lanzar 101 GET con el token del consumidor, pero **no habría probado TC-M02-158** y sí habría tenido coste:

1. La ficha exige M04 y un módulo de control; una ráfaga con un usuario mediría, en el mejor de los casos, un límite **por usuario**, no el límite **por módulo** que RF-50 define. §18-A5 advierte expresamente contra interpretar un 429 de otro origen como cumplimiento per-módulo.
2. El sub-caso seguiría bloqueado igualmente, porque sin segundo módulo no puede verificarse el aislamiento (V7).
3. Cada GET exitoso de este endpoint **escribe una fila de auditoría** (§7.1). Una ráfaga de 101 solicitudes habría dejado ~101 registros en un ambiente TEST compartido, sin aportar evidencia concluyente.

Se optó por documentar el hueco con evidencia de contrato y de código, que es concluyente sobre la ausencia del limitador, y por entregar el script de k6 listo para ejecutarse cuando existan las credenciales.

### Sobre la herramienta

k6 **no está instalado** en la estación de QA. Es una limitación secundaria: aunque lo estuviera, el sub-caso seguiría bloqueado por la ausencia de M04. El artefacto `test_tc_m02_g94_rate_limit.js` se entrega completo —101 solicitudes, registro de secuencia, tiempos y cabeceras de cuota, umbral sobre `429` y consulta final con el módulo de control— y aborta con un mensaje explícito si no recibe ambas credenciales.

### Evidencia del hueco de control (no demostrado por ejecución)

```text
Contrato:  el GET de datos-consolidados declara 200, 400, 401, 403, 404, 422 — sin 429.
Respuestas: ninguna incluye RateLimit-*, X-RateLimit-* ni Retry-After.
Código:    src/shared/rate_limit.py existe y se usa en otros endpoints
           (p. ej. rate_limit(10, 60, alcance="dispositivos_iot_registrar")),
           pero activo_biologico_router.py NO lo importa ni lo aplica.
Middleware: main.py solo registra CORSMiddleware y RequestContextMiddleware.
```

Registrado como **OBS-G94-01**. Queda **pendiente de confirmación empírica** cuando existan las credenciales de módulo; la ausencia del limitador sí está confirmada por lectura de código y de contrato.

**Equipo responsable de desbloquear: Desarrollo Backend** — debe proveer las identidades de módulo consumidor (M04 y un control) y aplicar el limitador al endpoint de exposición. **Implementación** solo si el modelo existiera y faltara habilitarlo en TEST, cosa que la evidencia descarta.

---

## 5. TC-M02-164 — SOLO LECTURA

### Estado BD ANTES

| estado | infra | especie | descripción | eventos | crecimiento | fases | historial |
|---|---:|---:|---|---:|---:|---:|---:|
| ACTIVO | 48 | 40 | QAJE-CREC-OK | 4 | 4 | 1 | 1 |

### Precondición — V9

El mismo consumidor ejecutó primero `GET /activos-biologicos/279/datos-consolidados?tipo_dato=metricas` → **HTTP 200** con `id_activo_biologico = 279`. Con esto, un `403`/`405` posterior **no puede atribuirse a falta de acceso** (hipótesis A8 descartada).

### POST — TC-M02-164-A

| Campo | Valor |
|---|---|
| Módulo | consumidor autorizado (usuario 35) |
| Endpoint | `POST /activos-biologicos/279/datos-consolidados` |
| Cuerpo | `{"qa_intento_escritura": true, "caso": "TC-M02-164-A"}` |
| **HTTP** | **405** |
| Cabecera `Allow` | **`GET`** |
| Mensaje | `{"detail":"Method Not Allowed"}` |
| Esperado | 403/405 ✅ |

### PUT — TC-M02-164-B

| Campo | Valor |
|---|---|
| Módulo | consumidor autorizado (usuario 35) |
| Endpoint | `PUT /activos-biologicos/279/datos-consolidados` |
| Cuerpo | `{"qa_intento_escritura": true, "caso": "TC-M02-164-B"}` |
| **HTTP** | **405** |
| Cabecera `Allow` | **`GET`** |
| Mensaje | `{"detail":"Method Not Allowed"}` |
| Esperado | 403/405 ✅ |

### Estado BD DESPUÉS

| estado | infra | especie | descripción | eventos | crecimiento | fases | historial |
|---|---:|---:|---|---:|---:|---:|---:|
| ACTIVO | 48 | 40 | QAJE-CREC-OK | 4 | 4 | 1 | 1 |

**Diferencias: ninguna.** La comparación se hace campo a campo entre los dos diccionarios, no por inspección visual.

**Cambios detectados: NO**

### Resultado: ✅ **APROBADO**

Las verificaciones V9 a V14 se cumplen. Dos matices que refuerzan el resultado:

1. **El rechazo es de método, no de cuerpo.** El `405` llega desde el enrutador con `Allow: GET`, antes de cualquier validación de entrada. §8.5 advierte que un `400`/`422` no demostraría solo lectura: aquí no se produjo ninguno, y así se afirma explícitamente en la prueba.
2. **El contrato es coherente con el comportamiento** (V14): la ruta declara únicamente `get`, de modo que no existe escritura expuesta ni siquiera documentalmente.

---

## 6. TC-M02-165 — AUTENTICACIÓN

| Variante | Credencial | HTTP esperado | HTTP obtenido | ¿Expuso datos? | Resultado |
|---|---|---:|---:|---|---|
| Sin credencial | **AUSENTE** | 401 | **401** | **NO** | ✅ **APROBADO** |
| Credencial inválida | **INVÁLIDA** (valor ficticio de prueba) | 401 | **401** | **NO** | ✅ **APROBADO** |

Respuestas obtenidas:

```json
// TC-M02-165-A — sin credencial
{"error_code":"TOKEN_REQUERIDO",
 "message":"Se requiere autenticación. Proporciona un token Bearer válido.",
 "fields":[],"timestamp":"2026-09-10T20:57:35.548857+00:00"}

// TC-M02-165-B — credencial inválida
{"error_code":"TOKEN_INVALIDO",
 "message":"El token es inválido o ha expirado.",
 "fields":[],"timestamp":"2026-09-10T20:57:36.240894+00:00"}
```

Verificaciones V15 a V18:

- **V15 / V16:** ambas variantes responden `401`. Se comprueba además que **no** es `403`: el paquete separa autenticación de autorización, y el escenario de módulo autenticado sin scope pertenece a G93.
- **V17 — no exposición:** ninguna respuesta incluye `historial_eventos`, `historial_fases`, `historico_estados`, `metricas_actuales`, `infraestructura_asociada`, `fase_productiva_activa`, `especie`, `estado_actual` ni `identificador`; tampoco aparece la cadena `QAJE-CREC-OK` en el cuerpo, y el tamaño de la respuesta es el de un error genérico. Los mensajes son seguros: indican qué falta sin revelar nada del recurso.
- **V18 — request válido en todo lo demás:** misma ruta, mismo activo existente y mismo `tipo_dato` que la consulta que devuelve `200` con credencial válida. La única variable es la credencial.
- **A11 descartada:** para la variante sin credencial se construyó una sesión limpia con `headers.clear()` y se afirma que la petición realmente enviada **no lleva `Authorization`**; la colección Postman tampoco define autenticación heredable a nivel de colección.
- **A12 descartada:** la credencial inválida es un valor ficticio inequívoco (`qa.credencial.invalida.tc-m02-165-b`), no un secreto real alterado.

### Resultado: ✅ **APROBADO**

---

## 7. Confirmación de integridad

| Métrica | Valor |
|---|---|
| SQL writes ejecutados por QA | **0** |
| Escrituras reales generadas por POST/PUT | **0** |
| Cambios de activo | **0** |
| Cambios de eventos | **0** |
| Cambios de métricas | **0** |
| Cambios de fases / historial | **0** |
| Cambios de scopes o configuración | **0** |

```sql
-- Estado del activo: idéntico antes y después de las cuatro peticiones
--  ACTIVO | 48 | 40 | QAJE-CREC-OK | 4 eventos | 4 crecimiento | 1 fase | 1 historial

-- Ningún permiso modificado hoy
SELECT count(*) FROM modulo1.permisos WHERE fecha_actualizacion::date = current_date;   -- 0
```

### 7.1 Escrituras del producto, no de QA

`modulo2.bitacora_auditoria_m02` pasó de **8** a **10** filas con `rf_origen = 'RF50'`. Las dos nuevas corresponden a los dos `GET` de lectura que devolvieron `200` —el de Pytest y el de la colección— y **las escribió el producto** al auditar los accesos exitosos, conforme a RF-50.

Es una distinción importante: **QA no ejecutó ninguna sentencia de escritura** y los cuatro intentos negativos no generaron ningún registro. Los rechazos `405` y `401` **no se auditan**, porque el flujo se corta antes de llegar al caso de uso.

---

## 8. Diagnóstico

**¿Fue necesario? NO** para los sub-casos ejecutados: TC-M02-164 y TC-M02-165 pasaron todas sus verificaciones a la primera, en las dos herramientas, sin ninguna desviación.

**SÍ** para caracterizar el bloqueo de TC-M02-158, cuyo análisis se recoge en §4. Hipótesis de §18 aplicables:

| # | Hipótesis | Resolución |
|---|---|---|
| A1 | M04 no estaba autorizado | **No aplica: M04 no existe.** Verificado en contrato, código y base de datos. |
| A2 | Request base inválido | Descartada: el `GET` de referencia devuelve `200`. |
| A3 | Cuota parcialmente consumida | No aplica: no hay cuota. Ninguna respuesta expone cabeceras de tasa. |
| A5 | El 429 vendría de un proxy global | No aplica: no se observó ningún 429 porque no se emitió carga. |
| A7 | POST/PUT apuntaron a ruta incorrecta | Descartada: la URL se afirma en la prueba y coincide con la del `GET` que devuelve 200. |
| A8 | El 403 sería por scope y no por método | Descartada: el mismo consumidor obtuvo `200` en `GET`, y el rechazo fue `405` con `Allow: GET`. |
| A9 | El 405 vendría de otro endpoint | Descartada: la cabecera `Allow: GET` corresponde a esta misma ruta, que el contrato declara solo con `get`. |
| A10 | El 400/422 sería por cuerpo antes que por método | Descartada: no hubo ningún 400 ni 422; se afirma explícitamente. |
| A11 | La variante sin token heredó una cabecera | Descartada: sesión limpia y aserción sobre la petición realmente enviada. |
| A12 | El token «inválido» era válido | Descartada: valor ficticio inequívoco. |
| A13 | El 401 contendría datos por logging | Descartada: cuerpo revisado campo a campo y por tamaño. |
| A14 | La BD cambió por tráfico ajeno | No aplica: no hubo ningún cambio que atribuir. |
| A15 | k6 generaría reintentos | No aplica: no se ejecutó. |

---

## 9. VEREDICTO FINAL

# ⛔ BLOQUEADO

**con TC-M02-164 y TC-M02-165 APROBADOS**

**Justificación:** el gate se completó, la base de datos se revisó primero y en solo lectura, y el SETUP no realizó ninguna escritura. Los dos controles verificables **se cumplen sin reservas**: la API de exposición es efectivamente de solo lectura —`405` con `Allow: GET` para POST y PUT, con integridad intacta— y exige autenticación —`401` sin credencial y con credencial inválida, sin exponer ningún dato—. Pero **TC-M02-158 no puede verificarse**: su precondición oficial, M04 autenticado más un módulo de control, no existe en el sistema, y fabricarla está prohibido. Como **BLOQUEADO nunca equivale a APROBADO** y el sub-caso es obligatorio, el caso agrupado queda bloqueado.

### BLOQ-G94-01 — TC-M02-158 no ejecutable

```text
Subtipo: CREDENCIAL M04 NO DISPONIBLE + MÓDULO DE CONTROL NO DISPONIBLE
Sub-caso: TC-M02-158

Qué precondición falta:
  · M04 como consumidor autenticado, exigido literalmente por la matriz;
  · un segundo módulo autorizado (M06 u M08) como control, necesario para demostrar
    que el límite de 100 req/min es POR MÓDULO y no global (V7).

Evidencia:
  · el contrato no declara securitySchemes, ni security, ni parámetro alguno de módulo,
    scope o cliente (aserciones de la colección sobre el contrato vivo);
  · la API autentica con JWT de usuario (get_current_user) y autoriza por rol
    (require_permission(recurso 29, acción 2));
  · information_schema no devuelve ninguna tabla de módulos consumidores ni de scopes;
  · en el código, modulo_consumidor es solo un campo de auditoría con valor fijo 'modulo2';
  · ninguna respuesta del endpoint expone cabeceras RateLimit-*, X-RateLimit- ni Retry-After.

Por qué impide ejecutar: sin identidades de módulo no hay cuota por módulo que medir ni
  control con el que comparar. Una ráfaga con credencial de usuario mediría, como mucho, un
  límite por usuario —§18-A5 advierte contra confundirlo con el límite per-módulo— y dejaría
  ~101 filas de auditoría en un TEST compartido sin resolver el bloqueo.

Limitación secundaria: k6 no está instalado en la estación de QA. Aunque lo estuviera, el
  sub-caso seguiría bloqueado por la ausencia de M04.

Equipo responsable de desbloquearlo: Desarrollo Backend.
Acción necesaria: proveer identidades de módulo consumidor con credenciales de servicio
  (M04 y al menos un módulo de control) y aplicar el limitador de tasa al endpoint de
  exposición; después, ejecutar test_tc_m02_g94_rate_limit.js, que se entrega listo.
```

---

## 10. Datos para Registro de Errores

No se detectó ningún defecto en los sub-casos verificables. Se registra una observación de seguridad y una discrepancia contractual.

### OBS-G94-01 — El endpoint de exposición de RF-50 no aplica ningún límite de tasa

- **ID sugerido:** OBS-G94-01
- **Descripción:** RF-50 fija **100 solicitudes por minuto y por módulo**, con `HTTP 429` al excederlo. El endpoint `GET /activos-biologicos/{id}/datos-consolidados` **no declara ninguna dependencia de limitación de tasa**: su única dependencia es `require_permission(29, 2)`. El proyecto dispone de un limitador reutilizable (`src/shared/rate_limit.py`), aplicado a otros endpoints, que además limita **por usuario** y no por módulo, y es un contador en memoria de un solo proceso. `main.py` solo registra `CORSMiddleware` y `RequestContextMiddleware`. Ninguna respuesta expone cabeceras de cuota y el contrato no declara `429`.
- **RF:** RF-50 · **Caso/sub-caso:** TC-M02-G94 / TC-M02-158 — sustenta el bloqueo, no lo resuelve
- **Categoría:** `RATE_LIMIT` / Seguridad · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Severo** — sin control de tasa, un consumidor puede saturar la API analítica; RF-50 lo define como control obligatorio y §20 pide no tratarlo como cosmético. No se eleva a Crítico porque no hay pérdida ni corrupción de datos y el acceso sigue exigiendo autenticación y autorización.
- **Tiempo máximo:** 1 día hábil · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-11** · **Estado:** Abierto
- **Evidencia:** aserciones del bloque `00-SETUP-LECTURA` sobre el contrato vivo (429 no declarado, sin `securitySchemes`); lectura de `activo_biologico_router.py`, `src/shared/rate_limit.py` y `main.py`; ausencia de cabeceras de cuota en todas las respuestas observadas.
- **Estado de la comprobación:** **la ausencia del limitador está confirmada por contrato y por código; no se demostró por ejecución**, porque el sub-caso está bloqueado y una ráfaga con credencial de usuario no probaría el límite por módulo. Queda pendiente de confirmación empírica cuando existan las credenciales de M04.
- **Causa raíz:** confirmada por QA — el limitador se aplica endpoint por endpoint como dependencia explícita y el de RF-50 no lo declara. Falta además el modelo de módulo consumidor sobre el que RF-50 quiere aplicar la cuota.

### OBS-G94-02 — El contrato no declara `429` ni el mecanismo de autenticación

- **ID sugerido:** OBS-G94-02
- **Descripción:** el contrato del endpoint declara `200, 400, 401, 403, 404, 422`, sin `429`, pese a que RF-50 define el límite de tasa. Tampoco declara `securitySchemes` ni `security`, de modo que un cliente generado a partir del contrato no sabría cómo autenticarse ni contemplaría el rechazo por cuota. El `405` que devuelve el enrutador tampoco está documentado, aunque en ese caso el comportamiento es correcto.
- **RF:** RF-50 · **Caso/sub-caso:** TC-M02-G94, transversal
- **Categoría:** `HTTP_COM` / documentación del contrato · **Equipo responsable:** **Desarrollo Backend**
- **Severidad:** **Medio** — no afecta al comportamiento observado, pero deja el contrato incompleto para los consumidores que RF-50 pretende habilitar · **Tiempo máximo:** 2 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** **2026-09-14** · **Estado:** Abierto
- **Evidencia:** aserciones del `00-SETUP-LECTURA` en [reporte_tc_m02_g94_newman.html](reporte_tc_m02_g94_newman.html).
- **Causa raíz:** confirmada por QA — el decorador del endpoint enumera `400, 401, 403, 404` y la aplicación no define esquemas de seguridad en OpenAPI.

---

## 11. Declaración de cumplimiento

- ✅ No se modificó código fuente. Los archivos de `src/` y `main.py` solo se leyeron para identificar los mecanismos de autenticación, autorización y limitación de tasa.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama. El árbol no tiene modificaciones sobre archivos versionados.
- ✅ **No hubo SQL de escritura.** La conexión se abre con `set_session(readonly=True)`.
- ✅ **SETUP = 0 escrituras.**
- ✅ **No se modificó la configuración de rate limiting**, ni se aumentó ningún límite.
- ✅ **No se resetearon contadores de cuota** en base de datos, caché ni ningún otro medio.
- ✅ **No se reiniciaron servicios** para limpiar cuota, ni se cortó conectividad, ni se modificó el reloj del servidor.
- ✅ **No se crearon tokens ni scopes**, ni se modificaron permisos: `modulo1.permisos` no registra cambios con fecha de hoy.
- ✅ **Los únicos POST/PUT fueron los dos intentos oficiales de TC-M02-164**, más los `POST /sesiones/` de autenticación, que no crean datos de dominio.
- ✅ **Se verificó que esos intentos no persistieran cambios**, comparando campo a campo el estado del activo, sus eventos, métricas, fases e historial antes y después.
- ✅ No se generó carga masiva: no se emitió ninguna ráfaga.
- ✅ **No se expusieron secretos en el informe**: la credencial inválida es un valor ficticio y no se transcribe ningún token real.
- ✅ No se generaron logs innecesarios: un artefacto de evidencia por herramienta.
- ✅ No se inventaron resultados: todo procede del reporte JUnit, del reporte Newman, de `evidencia_g94.json` o de una consulta `SELECT` reproducible.

---

## 12. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-50/TC-M02-G94/
├── test_tc_m02_g94_rate_limit.js   script k6 de TC-M02-158 — ENTREGADO, NO EJECUTADO
├── test_tc_m02_g94_security.py     Pytest de TC-M02-164 y TC-M02-165
├── construir_coleccion.cjs         generador determinista de la colección
├── test_tc_m02_g94.json            colección Postman
└── Resultados/
    ├── reporte_tc_m02_g94_pytest.xml   JUnit XML — 5 tests, 5 aprobados
    ├── reporte_tc_m02_g94_newman.html  reporte Newman — 31 aserciones, 0 fallos
    ├── evidencia_g94.json              respuestas, cabeceras y fotos de integridad
    └── TC-M02-G94_resultado.md         este informe
```

**No se entrega `reporte_tc_m02_g94_k6.json`**: TC-M02-158 quedó bloqueado y el script no se ejecutó. Fabricar un reporte vacío o simulado sería inventar evidencia.

Un artefacto por herramienta, sin logs por request ni por consulta.

**Ejecución:** Pytest **5/5 aprobados** en 10,2 s · Newman **7 peticiones, 31 aserciones, 0 fallos** · **4 peticiones negativas oficiales** (TC-M02-164 A/B y TC-M02-165 A/B) · **0 escrituras de QA** · integridad del activo idéntica antes y después.
