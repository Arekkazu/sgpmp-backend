# RESULTADO — TC-M02-G47

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **APROBADO** |
| Subtipo | — |
| COBERTURA ACTORES | COMPLETA |
| EJECUCIONES OFICIALES | 3/3 |
| PERSISTENCIA | VERIFICADA |
| RENDERIZADO SEGURO | VERIFICADO |
| XSS EJECUTADO | NO |
| Equipo responsable | — (aprobado). Quedan observaciones no bloqueantes en §10. |

**Justificación en una frase:** los tres actores registraron el evento con el payload oficial (`HTTP 201`, `Δ = +1` exacto por actor), el texto quedó almacenado íntegro como dato y, en la vista real que lo presenta, se muestra codificado como texto sin crear ningún elemento `<script>`, sin ejecución y sin navegación a `evil.test`.

---

## 1. Identificación

- **Caso:** TC-M02-G47
- **Sub-caso:** TC-M02-089
- **RF:** RF-40 — Registro de eventos de crecimiento
- **CU:** CU06
- **Tipo:** Seguridad — ASVS V5.3 / OWASP API8
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **Commit HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae` — *Agrega variables jwt y cookie a enviroments de back*
- **Estado del árbol:** sin modificaciones a archivos versionados; solo artefactos de QA sin seguimiento
- **Fecha/hora:** 2026-09-10 — escrituras oficiales a las 08:33 UTC, verificación de renderizado a las 08:51 UTC
- **Ambiente:** TEST desplegado
  - Backend HTTPS: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
  - Frontend: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`
  - PostgreSQL: `158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, solo lectura
- **Herramienta:** **Pytest** (evidencia principal: API, persistencia y asociación) + Cypress sobre la infraestructura ya declarada en el repositorio, exclusivamente para el DOM de la vista

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
| Vista que renderiza `descripcion` identificada | ✅ `/activos-biologicos/{id}` → pestaña **Historial**, ver §2.2 |

### 2.1 Contrato revisado

`POST /activos-biologicos/{id_activo}/eventos/crecimiento`

- Obligatorios: `tipo_medicion`, `valor_medicion`, `unidad_medida`. `descripcion`, `fecha` y `tipo_agregacion` son opcionales.
- `descripcion`: `anyOf [string, null]`, **sin `maxLength` declarado**. El payload oficial (52 caracteres) cabe íntegro; no hubo que recortarlo ni adaptarlo, más allá de las comillas simples de Python que preservan el contenido literal.
- Respuesta de éxito: **201**, con `RegistrarEventoCrecimientoResponse.evento` → `EventoActivoResponse`, que expone `id_eventos`, `id_activo_biologico`, `id_usuario`, `fecha` y `descripcion`. Ese identificador es el que se usa para S2, S4 y S8.
- Endpoints de consulta disponibles: `GET /activos-biologicos/{id_activo}/historial` y `GET /activos-biologicos/{id_activo}/eventos`.

No se detectó ninguna discrepancia entre la ficha y el contrato para este caso.

### 2.2 Vista de renderizado (Paso 2, antes de crear los eventos)

La descripción del evento de crecimiento se presenta en:

```text
Ruta funcional:  /activos-biologicos/{id}  →  pestaña "Historial"
Componente:      SGPMP-FRONT-END-PWA/src/biological_assets/components/HistorialSection.tsx
Línea 121:       <td style={{ ...TD, color: 'var(--text-primary)' }}>{r.descripcion}</td>
Datos:           GET /activos-biologicos/{id}/historial  (registros con categoria = 'CRECIMIENTO')
```

La aplicación es una SPA React + Ionic servida por Vite: el HTML del servidor **no contiene** el dato, se inyecta en el DOM en tiempo de ejecución. Por eso la verificación se hizo sobre el DOM final y no sobre el HTML fuente (A13).

Como dato de contexto del diagnóstico, en todo `src/` del frontend no existe **ninguna** aparición de `dangerouslySetInnerHTML` ni de `innerHTML`. Esto explica el resultado, pero no lo sustituye: la evidencia que sustenta el veredicto es la observación directa del DOM descrita en §6.

---

## 3. Revisión previa — SOLO LECTURA

| Actor | Usuario | Activo | ACTIVO | Fase activa | Acceso legítimo |
|---|---|---:|---|---|---|
| Productor | `m2m.nuevo@ejemplo.com` (id 35, rol 2) | 279 `QAJE-CREC-OK` | ✅ | ✅ 1 fase | ✅ `GET /activos-biologicos/279` → 200 |
| Veterinario | `juan.carlos.qa133@sgpmp-test.com` (id 3, rol 3) | 311 `QAJE-CREC-OK-VET` | ✅ | ✅ 1 fase | ✅ `GET /activos-biologicos/311` → 200 |
| Ingeniero de campo | `ingeniero@pecuaria.co` (id 4, rol 4) | 312 `QAJE-CREC-OK-ING` | ✅ | ✅ 1 fase | ✅ `GET /activos-biologicos/312` → 200 |

Los tres activos son de tipo `INDIVIDUAL`, por lo que el payload omite legítimamente `tipo_agregacion`.

### 3.1 Inventario mínimo

| # | Pregunta | Resultado |
|---|---|---|
| D1 | ¿Qué activos están ACTIVO? | Los tres candidatos (279, 311, 312): `id_estado = 1 → ACTIVO`. |
| D2 | ¿Cuáles tienen fase productiva activa? | Los tres, con exactamente una fila `es_activa = true` en `modulo2.gestiones_fases`. |
| D3 | ¿Activo legítimo del Productor? | 279 `QAJE-CREC-OK`. |
| D4 | ¿Activo legítimo del Veterinario? | 311 `QAJE-CREC-OK-VET`. |
| D5 | ¿Activo legítimo del Ingeniero? | 312 `QAJE-CREC-OK-ING`. |
| D6 | ¿Fecha del último evento de cada candidato? | 279 → 2026-09-09 23:01Z · 311 → 2026-09-09 23:00Z · 312 → 2026-09-09 23:01Z. |
| D7 | ¿Combinación válida de medición/valor/unidad? | `PESO` + `250` + `kg`. `kg` es una de las unidades permitidas para `PESO` (`gr`, `kg`, `lb`), y la combinación produjo HTTP 201 en TC-M02-G43 sobre estos mismos activos. |
| D8 | ¿Los tres usuarios existen y están activos? | Sí (`id_estado_cuenta = 2`), con la salvedad de credencial de §3.2. Los tres logins devolvieron HTTP 200 y el `sub` del JWT coincide con 35, 3 y 4. |
| D9 | ¿Existe una vista real que muestre la `descripcion`? | Sí: `/activos-biologicos/{id}` → pestaña **Historial** (§2.2). |
| D10 | ¿Existe endpoint GET para observar `descripcion`? | Sí: `GET /activos-biologicos/{id}/historial`, que devuelve `descripcion` por registro. |

### 3.2 Salvedad de credenciales del Veterinario — resuelta sin crear datos

El paquete indica `juan.carlos@email.com` para el Veterinario. Ese correo **no existe** en `modulo1.usuarios` y su login devuelve `HTTP 401 / CREDENCIALES_INVALIDAS`.

La cuenta sí existe: es el usuario **id 3, rol 3 (Veterinario)**, cuyo correo vigente es `juan.carlos.qa133@sgpmp-test.com`, con la misma contraseña `Test1234!`. Es deriva de la credencial documentada, no falta de datos. Se usó el correo vigente; **no se creó ni modificó ninguna cuenta**. Registrado como OBS-G47-01.

### 3.3 Consultas de la revisión previa

```sql
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

| id | identificador | tipo | estado | fases_activas | último_evento |
|---:|---|---|---|---:|---|
| 279 | QAJE-CREC-OK | INDIVIDUAL | ACTIVO | 1 | 2026-09-09 23:01:00+00 |
| 311 | QAJE-CREC-OK-VET | INDIVIDUAL | ACTIVO | 1 | 2026-09-09 23:00:00+00 |
| 312 | QAJE-CREC-OK-ING | INDIVIDUAL | ACTIVO | 1 | 2026-09-09 23:01:00+00 |

```sql
-- Cuentas y roles de los tres actores
SELECT u.id_usuario, u.correo_electronico, u.id_rol, r.nombre_rol, cu.id_estado_cuenta
FROM modulo1.usuarios u
JOIN modulo1.roles r ON r.id_rol = u.id_rol
LEFT JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
WHERE u.id_usuario IN (3, 4, 35);
```

| id_usuario | correo_electronico | id_rol | rol | estado_cuenta |
|---:|---|---:|---|---:|
| 3 | juan.carlos.qa133@sgpmp-test.com | 3 | Veterinario | 2 |
| 4 | ingeniero@pecuaria.co | 4 | Ingeniero de Campo | 2 |
| 35 | m2m.nuevo@ejemplo.com | 2 | Productor | 2 |

```sql
-- Línea base global antes de las escrituras oficiales
SELECT count(*), max(id_eventos) FROM modulo2.eventos_activos;      -- 101 | 233
SELECT count(*) FROM modulo2.eventos_crecimeinto;                    -- 45
SELECT count(*) FROM modulo2.eventos_activos
 WHERE descripcion LIKE '%evil.test%';                               -- 0
```

**Escrituras SETUP: 0.** La etapa se limitó a `SELECT`, `GET /openapi.json`, `GET /activos-biologicos/{id}` y los tres `POST /sesiones/` de autenticación, que no crean datos de dominio.

---

## 4. Payload oficial

```html
<script>document.location="http://evil.test"</script>
```

**Confirmación: se utilizó el contenido funcional exacto de la ficha. SÍ.**

En Python se declara con comillas simples, de modo que ni el intérprete ni el serializador JSON alteran el contenido:

```python
PAYLOAD_XSS = '<script>document.location="http://evil.test"</script>'
```

El test comprueba explícitamente esta invariante antes de enviar (A1/A2/A11):

```python
assert cuerpo['descripcion'] == PAYLOAD_XSS
assert json.loads(json.dumps(cuerpo))['descripcion'] == PAYLOAD_XSS
```

El cuerpo realmente transmitido consta en la evidencia; en el JSON de la petición la cadena viaja escapada como valor (`\"`), que es la representación correcta del mismo contenido funcional.

### Payload base (única entrada especial: `descripcion`)

| Campo | Valor |
|---|---|
| `tipo_medicion` | `PESO` |
| `valor_medicion` | `250` |
| `unidad_medida` | `kg` |
| `fecha` | instante actual menos 2 min (2026-09-10T08:33:36Z); válida y posterior al último evento |
| `tipo_agregacion` | omitido — activos `INDIVIDUAL`, opcional en el contrato |
| `descripcion` | **payload oficial** |

---

## 5. Resultados API / Persistencia

| Actor | Activo | HTTP | Evento nuevo | Conteo ANTES→DESPUÉS | Descripción persistida | Resultado |
|---|---:|---:|---:|---|---|---|
| Productor | 279 | **201** | **234** | 3 → 4 (Δ = +1) | idéntica al payload | **APROBADO** |
| Veterinario | 311 | **201** | **235** | 1 → 2 (Δ = +1) | idéntica al payload | **APROBADO** |
| Ingeniero de campo | 312 | **201** | **236** | 3 → 4 (Δ = +1) | idéntica al payload | **APROBADO** |

Assertions cubiertas por Pytest (`reporte_tc_m02_g47.xml`, **21 tests, 21 aprobados**):

| Assertion | Verificación | Resultado |
|---|---|---|
| **S1** — petición válida | Todos los campos distintos de `descripcion` cumplen contrato: `PESO`, valor positivo, unidad compatible, sin `tipo_agregacion` en activo INDIVIDUAL, fecha posterior al último evento y no futura. | ✅ ×3 |
| **S2** — evento registrado | `HTTP 201` y `evento.id_eventos` entero utilizable. | ✅ ×3 |
| **S3** — persistencia | `Δ = +1` exacto por activo y fila presente en `eventos_crecimeinto`. | ✅ ×3 |
| **S4** — descripción asociada | `SELECT descripcion` del evento creado == payload, byte a byte. | ✅ ×3 |
| **S5** — no ejecución en API | `Content-Type: application/json`; el payload vuelve íntegro como **valor de cadena JSON**, nunca como marcado suelto. | ✅ ×3 |
| **S8** — asociación correcta | `id_usuario` e `id_activo_biologico` del evento coinciden con el actor y el activo usados. | ✅ ×3 |
| Aislamiento | Exactamente **un** evento con el payload por activo. | ✅ ×3 |

> **Nota metodológica.** Un `201` no demuestra por sí solo ausencia de XSS. Aquí solo acredita la primera dimensión de la ficha —almacenamiento sin rechazo—; la segunda se verifica en §6.

---

## 6. Verificación de renderizado

**Vista verificada:** pestaña **Historial** del detalle de activo
**URL/ruta funcional:** `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io/activos-biologicos/{id}` → botón `Historial`
**Cómo se localizó el evento:** sesión iniciada por la interfaz con las credenciales de cada actor → entrada «Activos biológicos» del menú lateral → apertura del activo → pestaña Historial → fila de categoría `CRECIMIENTO` con fecha 2026-09-10 cuyo texto contiene `evil.test`. El dato procede del mismo `GET /activos-biologicos/{id}/historial` verificado en S5, de modo que su origen queda confirmado (A12).

| Actor | Evento | ¿Texto visible? | ¿Escapado/codificado? | ¿Se creó script ejecutable? | ¿Hubo navegación? | Resultado |
|---|---:|---|---|---|---|---|
| Productor | 234 | SÍ, literal y completo | SÍ (`&lt;script&gt;`) | NO | NO | **APROBADO** |
| Veterinario | 235 | SÍ, literal y completo | SÍ (`&lt;script&gt;`) | NO | NO | **APROBADO** |
| Ingeniero de campo | 236 | SÍ, literal y completo | SÍ (`&lt;script&gt;`) | NO | NO | **APROBADO** |

Comprobaciones ejecutadas sobre el DOM real, no sobre el HTML servido (`verificar_render_tc_m02_g47.cy.js`, **3 tests, 3 aprobados**):

| # | Comprobación | Evidencia |
|---|---|---|
| **S7** | `celda.textContent === '<script>document.location="http://evil.test"</script>'` | El contenido se presenta completo, como texto. |
| **S7** | `celda.innerHTML` contiene `&lt;script&gt;` y **no** contiene `<script>` | El marcado quedó codificado como entidades HTML. |
| **S6** | `celda.querySelector('script') === null` y `celda.children.length === 0` | El payload no generó ningún nodo elemento. |
| **S6** | Ningún `<script>` del documento tiene `evil.test` en su contenido ni en su `src` | No se inyectó script en ninguna parte de la página. |
| **S6** | `location.hostname` sigue siendo el del frontend y `pathname` sigue en `/activos-biologicos/{id}` | No hubo navegación causada por el payload. |
| **S6** | Intercepción activa sobre `hostname: 'evil.test'` con **0 peticiones registradas** | No salió ninguna petición hacia el dominio del atacante. |
| **S6** | Lista de excepciones no capturadas vacía | Ninguna ejecución ni error provocado por el contenido. |
| — | Tras mostrar el contenido se cambia a «Ficha integral» y se vuelve a «Historial»: la celda sigue visible | La vista continúa funcional. |

![Historial del activo 279 mostrando la descripción como texto plano](render_seguro_historial.png)

En la captura, la última fila (`2026-09-10`, categoría `CRECIMIENTO`) muestra `<script>document.location="http://evil.test"</script>` como texto legible dentro de la columna «Descripción», con la aplicación íntegra y operativa alrededor.

**Cumplimiento del principio I:** en ningún momento se navegó deliberadamente a `evil.test`, no se desactivó ninguna protección del navegador y no se modificó el frontend. La intercepción del dominio es una barrera preventiva que además sirve de detector: si el payload se hubiera ejecutado, la petición habría quedado registrada.

---

## 7. Evidencia BD

```sql
-- Los tres eventos oficiales
SELECT ea.id_eventos, ea.id_activo_biologico, ea.id_usuario, ea.fecha,
       ec.tipo_medicion, ec.valor_medicion, ec.unidad_medida, ea.descripcion
FROM modulo2.eventos_activos ea
JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
WHERE ea.id_eventos IN (234, 235, 236) ORDER BY 1;
```

| id_eventos | activo | autor | fecha | tipo | valor | unidad | descripcion |
|---:|---:|---:|---|---|---:|---|---|
| 234 | 279 | 35 | 2026-09-10 08:33:36+00 | PESO | 250.00 | kg | `<script>document.location="http://evil.test"</script>` |
| 235 | 311 | 3 | 2026-09-10 08:33:36+00 | PESO | 250.00 | kg | `<script>document.location="http://evil.test"</script>` |
| 236 | 312 | 4 | 2026-09-10 08:33:36+00 | PESO | 250.00 | kg | `<script>document.location="http://evil.test"</script>` |

Por actor queda confirmado: **evento nuevo** (234/235/236), **responsable** correcto (35/3/4), **activo** correcto (279/311/312), **descripción** idéntica al payload y **+1 exacto**.

```sql
-- Totales: exactamente 3 escrituras, ni una más
SELECT count(*), max(id_eventos) FROM modulo2.eventos_activos;   -- 104 | 236   (antes 101 | 233)
SELECT count(*) FROM modulo2.eventos_crecimeinto;                 -- 48         (antes 45)
SELECT count(*) FROM modulo2.eventos_activos
 WHERE descripcion LIKE '%evil.test%';                            -- 3          (antes 0)
```

| Métrica global | Antes | Después | Δ |
|---|---:|---:|---:|
| `modulo2.eventos_activos` — filas | 101 | 104 | **+3** |
| `modulo2.eventos_activos` — `max(id_eventos)` | 233 | 236 | **+3** |
| `modulo2.eventos_crecimeinto` — filas | 45 | 48 | **+3** |
| Eventos con el payload oficial | 0 | 3 | **+3** |

El incremento global coincide exactamente con las tres ejecuciones oficiales: no hubo ninguna otra escritura.

La base de datos no ejecuta JavaScript; esta evidencia acredita **persistencia**, y la de §6 acredita **renderizado seguro**. Son dimensiones distintas y ambas están cubiertas.

---

## 8. Diagnóstico

**¿Fue necesario? SÍ** — dos veces, en ambos casos sobre la propia automatización, nunca sobre el producto.

### 8.1 Primera desviación — fecha futura en el payload de prueba

- **Actor:** los tres. **Evento:** ninguno, no llegó a crearse.
- **Esperado:** `HTTP 201`.
- **Obtenido:** `HTTP 422 / FECHA_FUTURA` — *«La fecha del evento no puede ser posterior a la fecha actual.»*
- **Reproducción:** 3/3, idéntica para los tres actores.
- **Hipótesis A1–A14:** descartadas A1, A2, A3, A4, A5, A7, A8, A9, A10 y A11 (payload íntegro y verificado por aserción, activos ACTIVO con fase activa confirmados por `SELECT`, medición válida, tokens correctos con `sub` verificado, acceso legítimo confirmado por `GET` → 200). **Confirmada A6:** la fecha fija que había codificado, `2026-09-10T09:15:00Z`, era posterior a la hora del servidor (08:34 UTC).
- **Atribución: ERROR DE APLICACIÓN DE LA PRUEBA.**
- **Causa raíz:** confirmada por QA — constante de fecha codificada por delante del reloj del servidor.
- **Corrección:** solo sobre el artefacto Pytest. La fecha pasa a calcularse al inicio de la sesión como *ahora menos dos minutos* (margen para desviación de reloj), y se añadió una aserción en S1 que impide volver a enviar una fecha futura. Reejecutado: **21/21 aprobados**.
- **Impacto en los datos:** ninguno. `SELECT` confirmó tras el fallo que el total seguía en 101 filas y `max(id_eventos)` en 233: **el intento fallido no persistió nada** (comportamiento correcto del producto).

### 8.2 Segunda desviación — pérdida de sesión al recargar la página en la comprobación de renderizado

- **Actor:** los tres. **Escenario:** navegación hacia la vista de detalle.
- **Esperado:** llegar a la pestaña Historial con la sesión abierta.
- **Obtenido:** la aplicación regresaba a `/login`.
- **Hipótesis A1–A14:** **confirmada A14 en su variante de artefacto de prueba.** El access token vive **solo en memoria** (`tokenStore`, sin `localStorage`), por diseño del frontend. Mi primera versión de la especificación usaba `cy.visit()` después del login, lo que recarga la página y descarta el token.
- **Atribución: ERROR DE APLICACIÓN DE LA PRUEBA.**
- **Causa raíz:** confirmada por QA — recarga de página en un cliente cuyo token es en memoria.
- **Corrección:** solo sobre el artefacto Cypress. Toda la navegación posterior al login ocurre dentro de la SPA, mediante clics reales. Reejecutado: **3/3 aprobados**.

### 8.3 Observación colateral registrada durante 8.2

En la traza de aquella primera versión fallida se vio un `POST /sesiones/refresh` → **HTTP 500**. Comprobado después directamente contra el backend, el endpoint responde correctamente `HTTP 401` tanto sin cookie (`REFRESH_TOKEN_REQUERIDO`) como con cookie inválida (`REFRESH_TOKEN_INVALIDO`). No se ha podido reproducir el 500 fuera del contexto de Cypress. Queda registrado como OBS-G47-03 con **causa raíz no confirmada por QA**; es ajeno al alcance de G47 y no afecta al veredicto.

**Ninguno de los dos diagnósticos convirtió una ejecución fallida en aprobada.** Las tres ejecuciones oficiales que sustentan este informe se realizaron con los artefactos ya corregidos, y ninguna aserción sobre almacenamiento, persistencia, asociación o renderizado falló en ningún momento.

---

## 9. VEREDICTO FINAL

# ✅ APROBADO

**Justificación:**

1. Gate completo: repositorio, rama, HEAD `41369ea`, backend HTTPS en 200 y PostgreSQL accesible en solo lectura.
2. La base de datos se revisó primero y en modo exclusivamente de lectura; **0 escrituras en SETUP**.
3. Existen recursos legítimos para los tres actores, hallados sin crear ni modificar nada.
4. Se probaron **Productor, Veterinario e Ingeniero de campo** con recurso legítimo cada uno.
5. Se ejecutaron las **3 peticiones oficiales**, todas con `HTTP 201`, el éxito que declara el contrato.
6. Cada evento quedó asociado al actor correcto (usuarios 35, 3 y 4) y a su activo (279, 311 y 312).
7. La BD demuestra **`+1` exacto por actor** y `+3` global, sin ninguna otra escritura.
8. `descripcion` quedó almacenada **como dato**, byte a byte idéntica al payload oficial.
9. La API recupera el contenido íntegro como valor de cadena JSON, sirviendo `application/json`.
10. Se identificó la vista real que presenta la descripción y se verificó sobre su **DOM final**.
11. En la vista, el contenido se presenta **codificado/escapado**: `&lt;script&gt;`, sin nodos hijo.
12. **No se ejecutó el script**: ningún `<script>` derivado del payload en todo el documento, ninguna excepción no capturada.
13. **No hubo navegación** causada por el payload y **cero peticiones** hacia `evil.test`.
14. La vista siguió funcional tras mostrar el contenido inyectado.
15. No quedó ninguna dimensión obligatoria sin verificar.

El sistema cumple el resultado esperado de la ficha: **almacena el texto sin ejecutarlo y lo presenta escapado, sin XSS almacenado**, para los tres actores de RF-40.

---

## 10. Datos para Registro de Errores

No se detectó ningún defecto de seguridad ni ningún fallo dentro del alcance de G47. Se registran observaciones ajenas al veredicto.


### OBS-G47-01 — El listado de activos solo muestra la primera página, sin control de paginación

- **Descripción:** `GET /activos-biologicos` devuelve `total_registros: 22` y `total_paginas: 2` para el Productor, pero `RegistryView` renderiza únicamente la primera página y **no expone ningún control de paginación**; el buscador filtra solo sobre los registros ya cargados. En consecuencia, el activo 279 —legítimo, ACTIVO y accesible por API para ese actor— no tiene fila que pulsar en la interfaz.
- **RF / Caso:** hallazgo colateral, **fuera del alcance de G47** · **Actor:** Productor (afecta a cualquier actor con más de una página de activos)
- **Evidencia:** respuesta del listado con `total_paginas: 2`; `RegistryView.tsx` muestra el contador de registros pero no renderiza el componente `Paginacion` que sí existe en `biological_assets/components/Paginacion.tsx`.
- **Categoría:** Funcional / Frontend · **Equipo responsable:** **Desarrollo Frontend**
- **Severidad:** Medio — afectación parcial con alternativa clara (la ruta directa `/activos-biologicos/{id}` sí funciona) · **Tiempo máximo:** 2 días hábiles · **Fecha detección:** 2026-09-10 · **Fecha límite:** 2026-09-14 · **Estado:** Abierto
- **Impacto de seguridad:** ninguno.
- **Impacto en el caso:** ninguno sobre el veredicto. Para el Productor, la vista se alcanzó navegando por el **mismo router de la SPA y a la misma ruta que empuja la propia vista de listado** (`/activos-biologicos/279`), sin recargar la página y sin alterar ninguna protección. La celda inspeccionada es exactamente la misma que ven los otros dos actores, cuyo acceso sí se hizo pulsando la fila.
- **Causa raíz:** confirmada por QA — el componente de paginación existe en el módulo pero no se usa en `RegistryView`.


---

## 11. Declaración de cumplimiento

- ✅ No se modificó código fuente, ni del backend ni del frontend. Los archivos de `src/` solo se leyeron para identificar la vista y para el diagnóstico.
- ✅ No hubo `git commit` ni `git push`. Tampoco `merge`, `rebase`, `reset` ni cambio de rama. El árbol no tiene modificaciones sobre archivos versionados.
- ✅ No se ejecutó SQL de escritura. La conexión de Pytest se abre explícitamente con `set_session(readonly=True)`, de modo que el propio servidor rechazaría cualquier escritura accidental.
- ✅ No se crearon ni modificaron datos durante el SETUP: **0 escrituras**.
- ✅ **Las únicas escrituras fueron los 3 POST oficiales del caso principal**, confirmado por el incremento global exacto de +3 filas.
- ✅ Se probó el payload exacto indicado por TC-M02-089, sin sustituirlo ni alterar su contenido funcional.
- ✅ Se cubrieron los tres actores obligatorios; no se usó Administrador como sustituto.
- ✅ Cada actor utilizó un recurso dentro de su alcance legítimo, confirmado por `GET` → 200 y por `POST` → 201.
- ✅ No se ejecutaron escenarios de G43, G44, G45, G46 ni G48. No se introdujo ninguna segunda condición inválida.
- ✅ No se desactivaron protecciones del navegador ni del frontend, y no se navegó a `evil.test`; las peticiones a ese dominio se interceptaron de forma preventiva y se contabilizaron en cero.
- ✅ No se inventaron resultados. Todo lo afirmado procede del reporte JUnit, del reporte de Cypress, de la captura de pantalla o de una consulta `SELECT` reproducible.
- ✅ No se ejecutaron migraciones ni se desplegaron o reiniciaron servicios.

---

## 12. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G47/
├── test_tc_m02_g47.py                    automatizacion Pytest (herramienta principal)
├── verificar_render_tc_m02_g47.cy.js     comprobacion del DOM de la vista (S6/S7)
└── Resultados/
    ├── reporte_tc_m02_g47.xml            JUnit XML consolidado — 21 tests, 21 aprobados
    ├── evidencia_g47.json                identificadores, conteos y respuestas de los 3 actores
    ├── render_seguro_historial.png       captura de la vista con la descripcion escapada
    └── TC-M02-G47_resultado.md           este informe
```

Comandos de reejecución:

```bash
# Evidencia principal (Pytest). Atencion: cada ejecucion crea 3 eventos nuevos.
pytest -q test_tc_m02_g47.py --junitxml=Resultados/reporte_tc_m02_g47.xml

# Dimension de renderizado (no escribe nada; solo lee la vista)
npx cypress run --spec "tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G47/verificar_render_tc_m02_g47.cy.js"
```

Cypress se ejecutó con la configuración ya declarada en el repositorio (`cypress.config.cjs`, cuyo `specPattern` es `tests/Test_Testing/**/*.cy.js`) y con las dependencias que `package.json` ya declaraba, instaladas sin modificar el lockfile. En este equipo la variable de entorno `ELECTRON_RUN_AS_NODE=1` impide arrancar el navegador de Cypress; debe anularse antes de ejecutar.

**Resumen de ejecución:** Pytest **21/21 aprobados**; Cypress **3/3 aprobados**; **3 escrituras oficiales**, ninguna otra.
