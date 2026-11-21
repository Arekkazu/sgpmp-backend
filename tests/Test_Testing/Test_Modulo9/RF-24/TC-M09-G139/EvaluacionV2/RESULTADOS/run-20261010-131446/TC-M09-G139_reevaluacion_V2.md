# TC-M09-G139 — SEGUNDA EVALUACIÓN

**RF-24 v2.0 · CU05 Flujo F · Módulo 9 — Calibración por visión (modalidad VISION)**

| | |
|---|---|
| RUN_ID | `run-20261010-131446` (único; no se creó un RUN nuevo) |
| Ejecuciones dentro del RUN | **2** |
| Ambiente decisorio | TEST — `https://api.inmero.co/back-sigab-test` |
| Herramienta oficial | Pytest + `requests` (HTTP real). BD complementaria por SELECT. Newman: **NO APLICA** |
| Rama QA | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` |
| HEAD QA | `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| `origin/test` | `c4612dae6d8f0601488b94a3635f6592aa640686` |
| Casos | TC-M09-282, TC-M09-283 (corridas N y N−1) |

Este informe **no** representa solo la ejecución vigente: es la historia completa de la
segunda evaluación del grupo.

---

## DECISIÓN GENERAL ACTUAL

| Caso | Resultado vigente |
|---|---|
| **TC-M09-282** | **APROBADO** |
| **TC-M09-283** (corridas N y N−1) | **APROBADO** |
| **TC-M09-G139** | **APROBADO** |

**Incidencia original:** **CORREGIDA** (PR #550) · **Incidencia nueva:** **NO**

**Evolución del grupo:** `BLOQUEADO → RECHAZADO → APROBADO`

El resultado anterior RECHAZADO se conserva en el historial de ejecuciones y no fue
eliminado. No se observaron regresiones: TC-M09-282 y la corrida N mantienen el
resultado APROBADO que ya tenían en la ejecución 1.

---

## HISTORIAL DE EJECUCIONES

### EJECUCIÓN 1 — SEGUNDA EVALUACIÓN INICIAL

| | |
|---|---|
| RUN | `run-20261010-131446` |
| Fecha/hora | 2026-10-10 13:15 (−05:00) |
| Fixture | área **279**, cámara **222**, ventanas 01/02/03 de septiembre |
| TC-M09-282 | **APROBADO** |
| TC-M09-283 — N | **APROBADO** (HTTP 201, calibración **8** EXITOSA, línea base publicada) |
| TC-M09-283 — N−1 | **RECHAZADO** |
| TC-M09-283 | **RECHAZADO** |
| **TC-M09-G139** | **RECHAZADO** |
| Pytest | 22 collected · 17 passed · **1 failed** · 4 skipped · 0 errors |

**Defecto observado en la corrida N−1** (N = 30, N−1 = 29):

| Criterio | Esperado | Obtenido |
|---|---|---|
| HTTP | 422 | **400** |
| error_code | `LINEA_BASE_NO_CALCULADA` | **`VALOR_NO_PERMITIDO`** |
| field | — | `calibracion_vision_resultado_coherente` |
| Calibración en historial | FALLIDA / etapa FILTRADO | **no quedó ninguna** |
| Auditoría RF-10 del intento | FALLIDO | **no quedó** |
| Línea base vigente de N | conservada | conservada (**sin daño de datos**) |

**Causa raíz** (confirmada por Desarrollo): `json_linea_base` estaba declarado como
`mapped_column(JSONB)`. SQLAlchemy convierte por defecto el `None` de Python en
`'null'::jsonb`, y `'null'::jsonb IS NULL` es **false**. El constraint
`ck_calibracion_vision_resultado_coherente` exige, para las calibraciones no EXITOSA,
`json_linea_base IS NULL AND etapa_fallo IS NOT NULL`, así que PostgreSQL rechazaba el
INSERT y el 422 contractual se degradaba a 400.

> Nota de trazabilidad honesta: en el informe de la ejecución 1 concluí que «el build
> desplegado en TEST escribe una fila distinta» de la que produce el código de la rama.
> Esa hipótesis era incorrecta y así quedó corregido en el grupo G140, cuyo laboratorio
> local reprodujo el 400 con el código de la rama: el problema estaba en el mapeo ORM,
> no en un desfase de despliegue.

### CORRECCIÓN DE DESARROLLO — PR #550

| | |
|---|---|
| PR | **#550** |
| Archivo | `src/configuration/infrastructure/models/calibracion_vision_model.py` |
| Cambio | `mapped_column(JSONB)` → **`mapped_column(JSONB(none_as_null=True))`** |
| Objetivo | que `None` se persista como **SQL NULL** y no como JSON `'null'` |
| Alcance declarado | TC-M09-283 y TC-M09-286 |
| Migración | no requiere · el CHECK no cambia · corrige únicamente el mapeo ORM |
| Autorización de reejecución | líder de Desarrollo |

**Verificación en el repositorio** (solo lectura; sin `checkout`, `switch`, `merge` ni
`rebase`):

```
git show origin/test:src/configuration/infrastructure/models/calibracion_vision_model.py
→ json_linea_base: Mapped[Optional[dict]] = mapped_column(JSONB(none_as_null=True))
```

* `origin/test` = `c4612dae6d8f0601488b94a3635f6592aa640686`
* **Fix presente en `origin/test`: SÍ**

La presencia del fix en Git no prueba que TEST tenga ese build. La evidencia decisoria
es la ejecución HTTP real, que es la que sigue.

### EJECUCIÓN 2 — REEJECUCIÓN COMPLETA POST-FIX

| | |
|---|---|
| Fecha/hora | 2026-10-11 00:17–00:19 UTC (2026-10-10 19:17 −05:00) |
| Tipo | `REEJECUCION_COMPLETA_POST_FIX` |
| Autorizado por | líder de Desarrollo |
| Grupo completo reejecutado | **SÍ** (TC-282, N y N−1) |
| Nuevo RUN creado | **NO** |
| Fixture | área **279** reutilizada, cámara **245 nueva**, ventanas 11/12/13 de septiembre |
| TC-M09-282 | **APROBADO** |
| TC-M09-283 — N | **APROBADO** |
| TC-M09-283 — N−1 | **APROBADO** |
| **TC-M09-G139** | **APROBADO** |

---

## PRECHECK ACTUAL

| Comprobación | Resultado |
|---|---|
| `GET /openapi.json` | **200** |
| `POST /configuracion/calibraciones-vision` | PRESENTE |
| `GET /configuracion/calibraciones-vision` | PRESENTE |
| `GET /configuracion/calibraciones-vision/linea-base` | PRESENTE |
| `POST /iot/telemetria/vision` | PRESENTE |
| `GET /auditoria/` | PRESENTE |
| Ingeniero de Campo (`ingeniero@pecuaria.co`) | **PASS** |
| Administrador (`administador.dev@gmail.com`) | **PASS** |
| Fixture preparable | **PASS** |
| Fix presente en `origin/test` | **SÍ** |
| BD complementaria | **PARCIAL** (ver sección BD) |
| **AUTORIZAR_RUN** | **SÍ** |

No se persiste ninguna contraseña ni token: las credenciales llegan por entorno y el
sanitizador redacta cualquier cabecera `Authorization`, token o serial antes de escribir
un artefacto.

---

## FIXTURE ACTUAL

| Elemento | Valor |
|---|---|
| Finca | **163** |
| Área A1 | **279** — `QA-G137-AREA-20261010-105849` |
| `es_activo` | true |
| Especie | **41** (AVES) |
| `tipo_modelo_asignado` | `MODELO_AVES` |
| Paradigma | POBLACIONAL |
| Alcance | visible para el Ingeniero de Campo |
| Cámaras preexistentes | 214 (inactiva), 221 (inactiva), **222 (inactiva)** |
| **Cámara C1 de esta ejecución** | **245** — categoría CAMARA, `es_activo` true, 1920x1080, **30 fps nominal**, asociada al área 279 |

**Aislamiento.** La cámara **222** de la ejecución 1 **no se reutilizó** (§22). Las tres
cámaras previas del área estaban inactivas antes de empezar, de modo que la 245 fue la
**única cámara activa** del área durante toda la ejecución, y es el área la fuente que
consulta `POST /configuracion/calibraciones-vision`. La cámara se registró en esta
ejecución, así que no puede tener observaciones anteriores: las tres ventanas estaban
necesariamente vacías, lo que además confirman los `duplicadas = 0` de los tres lotes.
No se desactivó ningún recurso ajeno para facilitar la prueba.

**Ventanas nuevas, cerradas, pasadas y disjuntas** — y disjuntas también de las de la
ejecución 1:

| Ventana | Inicio | Fin |
|---|---|---|
| `WINDOW_282_CURRENT` | 2026-09-11T00:00:00Z | 2026-09-11T02:00:00Z |
| `WINDOW_283_N_CURRENT` | 2026-09-12T00:00:00Z | 2026-09-12T04:00:00Z |
| `WINDOW_283_N_MINUS_1_CURRENT` | 2026-09-13T00:00:00Z | 2026-09-13T04:00:00Z |
| *(ejecución 1: 01, 02 y 03 de septiembre — no reutilizadas)* | | |

---

## VALOR N

| | |
|---|---|
| Fuente | `ParametrosLineaBase.min_observaciones` en `src/configuration/domain/entities/linea_base_vision.py` |
| Inyección | `CalibrarVisionUseCase(parametros: ParametrosLineaBase = ParametrosLineaBase())` — valores por defecto, verificado en el código vigente |
| **N_ACTUAL** | **30** |
| **N_MINUS_1** | **29** |
| Confirmación en runtime | el motivo de la calibración FALLIDA lo declara: *«29 observaciones válidas de 29 en la ventana; el mínimo es 30.»* |

Otros umbrales vigentes: `cobertura_minima = 0.5`, `tracks_minimos = 1`,
`min_datos_componente = 10`, `epsilon = 0.01`, `max_iteraciones = 10`.

N se volvió a leer antes de ejecutar; no se asumió silenciosamente.

---

## TC-M09-282 — EJECUCIÓN ACTUAL

**Ventana con observaciones presentes pero CERO aptas para IA.**

### Datos ingeridos (`POST /iot/telemetria/vision`)

| | |
|---|---|
| HTTP | **201** |
| total / aceptadas / duplicadas | **10 / 10 / 0** |
| Calidad enviada | `cobertura_ventana = 0.1000`, `n_tracks = 0`, `n_tracks_perdidos = 10`, `fps_efectivo = 0.00`, `estado_calibracion = SIN_DETECCION` |
| `indice_calidad` devuelto | **3** en las diez |
| `clasificacion_calidad` | `NO_APTO` en las diez |
| `apto_para_ia` | **false** en las diez |

`apto_para_ia` no se envió: lo calculó M03 a partir de las cuatro dimensiones de RF-62.

### Conteos de la ventana

| Total | Aptas | No aptas |
|---|---|---|
| 10 | **0** | 10 |

### PRE / POST

| | PRE | POST |
|---|---|---|
| Línea base vigente | **8** | **8** (sin cambio) |
| Historial de calibraciones | `[8, 7, 6, 4]` | `[8, 7, 6, 4]` (sin cambio) |

### Resultado del POST objetivo

Actor: **Ingeniero de Campo**. Una sola ejecución, 0 reintentos.

| | Esperado | Obtenido |
|---|---|---|
| HTTP | 422 | **422** |
| error_code | `VISION_NO_DISPONIBLE` | **`VISION_NO_DISPONIBLE`** |
| Línea base nueva | no | **no** |
| Línea base vigente previa | conservada | **conservada (8)** |
| Calibración de cálculo en historial | no se exige | **no quedó** |

El rechazo ocurre en precondiciones, antes de crear la calibración, así que el historial
no cambia. La matriz no exige persistir una FALLIDA aquí.

### Auditoría RF-10

| Campo | Valor |
|---|---|
| `id_evento` | **48975** |
| `tipo_evento` | 29 `CALIBRACION_RECHAZADA` |
| `resultado` | **fallido** |
| `modulo` | MODULO9 |
| `id_usuario` | 4 |
| `direccion_ip` | PRESENTE |
| `detalle.codigo_http` | **422** |
| `detalle.codigo_error` | **`VISION_NO_DISPONIBLE`** |
| `detalle.motivo` | idéntico al mensaje de la respuesta |
| `integridad_ok` | true |
| `fecha_evento` | 2026-10-11T00:18:02.063028Z |

**TC-M09-282: APROBADO** — existen observaciones, aptas = 0, HTTP 422
`VISION_NO_DISPONIBLE`, la línea base no cambia y la auditoría del rechazo existe y es
correcta.

---

## TC-M09-283 — N — EJECUCIÓN ACTUAL

**Exactamente N = 30 observaciones aptas.**

### Datos ingeridos

| | |
|---|---|
| HTTP | **201** |
| total / aceptadas / duplicadas | **30 / 30 / 0** |
| Calidad enviada | `cobertura_ventana = 1.0000`, `n_tracks = 20`, `n_tracks_perdidos = 0`, `fps_efectivo = 30.00` (= fps nominal), `estado_calibracion = CALIBRADA` |
| `indice_calidad` | **100** en las treinta |
| Aptas | **30** |
| Vector | determinístico con jitter determinístico pequeño (`densidad_actividad` 12.00–12.02, `tasa_movimiento` 0.80–0.82) |
| Filtro Etapa 1 | cobertura 1.0 ≥ 0.5 y 20 tracks ≥ 1 → **todas pasan** |

### PRE

| | |
|---|---|
| Línea base vigente | **8** |
| Historial | `[8, 7, 6, 4]` |

### Resultado del POST objetivo

Actor: **Ingeniero de Campo**. Una sola ejecución, 0 reintentos.

| | Esperado | Obtenido |
|---|---|---|
| HTTP | 2xx (ref. 201) | **201** |
| `estado` | EXITOSA | **EXITOSA** |
| `etapa_fallo` | null | **null** |
| `n_observaciones` | 30 | **30** |
| `n_observaciones_validas` | 30 | **30** |
| `linea_base` | no nula | **`{densidad_actividad: 12.01, tasa_movimiento: 0.81}`** |
| `origen_disparo` | MANUAL | **MANUAL** |
| `especie_id` | 41 | **41** |
| Iteraciones | — | 1 |

**`CAL_N_CURRENT_ID` = 14**

### Postcondición

| | |
|---|---|
| Historial POST | `[14, 8, 7, 6, 4]` — contiene 14 con estado **EXITOSA** |
| `GET linea-base` | **200**, `id_calibracion_vision = 14` |
| **`BASELINE_N_CURRENT_ID`** | **14** |

### Auditoría RF-10

| Campo | Valor |
|---|---|
| `id_evento` | **48976** |
| `tipo_evento` | 30 `CALIBRACION_EXITOSA` |
| `resultado` | **exitoso** |
| `modulo` | MODULO9 |
| `id_usuario` | 4 · `direccion_ip` PRESENTE · `integridad_ok` true |
| `detalle.operacion` | `CALIBRACION_VISION` |
| `detalle.id_calibracion_vision` | **14** |
| `detalle.estado` | EXITOSA · `etapa_fallo` null |
| `detalle.n_observaciones_validas` | 30 |

**TC-M09-283 — corrida N: APROBADO.**

---

## TC-M09-283 — N−1 — EJECUCIÓN ACTUAL

**Exactamente N−1 = 29 observaciones aptas. Este es el caso que dirigía el PR #550.**

### Datos ingeridos

| | |
|---|---|
| HTTP | **201** |
| total / aceptadas / duplicadas | **29 / 29 / 0** |
| `indice_calidad` | **100** en las veintinueve |
| Aptas | **29** |

### PRE

| | |
|---|---|
| Línea base vigente | **14** (= `BASELINE_N_CURRENT_ID`) ✔ |
| Historial | `[14, 8, 7, 6, 4]` |
| `T_BEFORE_N_MINUS_1` | 2026-10-11T00:18:04.642663Z |

### Resultado del POST objetivo

Actor: **Ingeniero de Campo**. Una sola ejecución, **0 reintentos** (el 400 de la
ejecución 1 no se reintentó entonces y aquí tampoco se repitió el POST).

| | Esperado | Obtenido |
|---|---|---|
| HTTP | 422 | **422** |
| error_code | `LINEA_BASE_NO_CALCULADA` | **`LINEA_BASE_NO_CALCULADA`** |
| Mensaje | literal del contrato | **idéntico** |

Mensaje obtenido, carácter por carácter:

> No se pudo calcular la línea base: datos insuficientes o sin convergencia para el área
> 279 y especie 41. Se conserva la línea base vigente anterior.

**El defecto anterior (400 `VALOR_NO_PERMITIDO`, field
`calibracion_vision_resultado_coherente`) NO reapareció.**

### Historial tras el 422

| | Esperado | Obtenido |
|---|---|---|
| Nueva calibración | existe | **sí, exactamente 1** |
| **`CAL_N_MINUS_1_CURRENT_ID`** | — | **15** |
| `estado` | FALLIDA | **FALLIDA** |
| `etapa_fallo` | FILTRADO | **FILTRADO** |
| `linea_base` | null | **null** |
| `n_observaciones` | 29 | **29** |
| `n_observaciones_validas` | 29 | **29** |
| `motivo` | no nulo | **«29 observaciones válidas de 29 en la ventana; el mínimo es 30.»** |
| `origen_disparo` | — | MANUAL |
| `id_usuario` | — | 4 |
| Historial POST | — | `[15, 14, 8, 7, 6, 4]` |

### Línea base tras N−1

| | |
|---|---|
| `GET linea-base` | **200**, `id_calibracion_vision` = **14** |
| Valores | `{densidad_actividad: 12.01, tasa_movimiento: 0.81}` — **idénticos** a los de N |
| Baseline N conservada | **SÍ** |

La calibración FALLIDA **no** reemplazó la línea base de N.

### Auditoría RF-10

`T_AFTER_N_MINUS_1` = 2026-10-11T00:18:04.970661Z. Consulta del Administrador con
ventana 00:12:04 → 00:23:04 (holgura de un minuto a cada lado del intento), tipos de
evento resueltos del catálogo (`GET /auditoria/catalogo/tipos-evento`): 29
`CALIBRACION_RECHAZADA`, 30 `CALIBRACION_EXITOSA`.

| Campo | Esperado | Obtenido |
|---|---|---|
| `id_evento` | — | **48977** |
| `tipo_evento` | CALIBRACION_RECHAZADA | **29** |
| `resultado` | FALLIDO | **fallido** |
| `modulo` | MODULO9 | **MODULO9** |
| `detalle.operacion` | CALIBRACION_VISION | **`CALIBRACION_VISION`** |
| `detalle.codigo_http` | 422 | **422** |
| `detalle.codigo_error` | `LINEA_BASE_NO_CALCULADA` | **`LINEA_BASE_NO_CALCULADA`** |
| `detalle.id_calibracion_vision` | 15 | **15** |
| `detalle.estado` | FALLIDA | **FALLIDA** |
| `detalle.etapa_fallo` | FILTRADO | **FILTRADO** |
| `detalle.motivo_etapa` | no nulo | **«29 observaciones válidas de 29 en la ventana; el mínimo es 30.»** |
| `detalle.id_infraestructura` / `id_especie` | 279 / 41 | **279 / 41** |
| `id_usuario` / `nombre_usuario` | — | 4 / Valentina López Herrera |
| `direccion_ip` / `user_agent` | presentes | **PRESENTE / PRESENTE** |
| `fecha_evento` | dentro de la ventana del intento | **2026-10-11T00:18:04.292213Z — SÍ** |
| `integridad_ok` | — | **true** |

**TC-M09-283 — corrida N−1: APROBADO.** Y con ello **TC-M09-283: APROBADO**, porque
ambas corridas aprueban.

---

## HISTORIAL DE CALIBRACIONES

`GET /configuracion/calibraciones-vision?area_id=279`

| ID | Estado | Etapa | n_obs | n_válidas | Procedencia |
|---|---|---|---|---|---|
| **15** | FALLIDA | FILTRADO | 29 | 29 | **ejecución 2 — TC-M09-283 N−1** |
| **14** | EXITOSA | — | 30 | 30 | **ejecución 2 — TC-M09-283 N (línea base vigente)** |
| 8 | EXITOSA | — | 30 | 30 | ejecución 1 — TC-M09-283 N |
| 7 | EXITOSA | — | — | — | G137 |
| 6 | EXITOSA | — | — | — | G137 |
| 4 | EXITOSA | — | — | — | G137 |

No se borró ninguna calibración ni observación: la EXITOSA de N y la FALLIDA de N−1 son
evidencia esperada del grupo.

---

## LÍNEA BASE

| Momento | `id_calibracion_vision` | Valores |
|---|---|---|
| Antes de TC-282 | 8 | `{densidad_actividad: 12.01, tasa_movimiento: 0.81}` |
| Tras TC-282 (422) | 8 | sin cambio |
| **Tras la corrida N (201)** | **14** | `{densidad_actividad: 12.01, tasa_movimiento: 0.81}` |
| **Tras la corrida N−1 (422)** | **14** | **sin cambio** |

`componentes_no_calibrables: []` en ambos casos. La sustitución 8 → 14 es el
comportamiento correcto de una calibración exitosa (la publicación de línea base ya se
validó en el grupo G141) y la no-sustitución tras el 422 es el criterio de integridad de
este caso.

---

## AUDITORÍA RF-10

Los tres intentos quedaron auditados, cada uno con el resultado que le corresponde:

| Caso | `id_evento` | tipo | `resultado` | `codigo_http` | `codigo_error` |
|---|---|---|---|---|---|
| TC-M09-282 | **48975** | 29 | fallido | 422 | `VISION_NO_DISPONIBLE` |
| TC-M09-283 N | **48976** | 30 | exitoso | — | — |
| TC-M09-283 N−1 | **48977** | 29 | fallido | 422 | `LINEA_BASE_NO_CALCULADA` |

**Corrección de automatización respecto de la ejecución 1.** En la ejecución 1 leí un
campo `exitoso` del item de `GET /auditoria/`, que **no existe** en el contrato: el
resultado viaja en **`resultado`** (`exitoso` / `fallido`, en minúsculas) y la IP en
**`direccion_ip`**. Leerlo devolvía `null` y daba la impresión falsa de que la auditoría
no registraba el resultado. La suite ya usa el contrato real y los ids de tipo se
resuelven del catálogo en lugar de asumirse.

---

## BD COMPLEMENTARIA

La falta de SELECT no bloquea G139 (§19) y no bloqueó nada: el veredicto se construyó
con los oráculos de API, que son suficientes (§20).

| | |
|---|---|
| Conexión | PostgreSQL 18.4, usuario `member_qa`, sesión **READ ONLY** |
| DML ejecutado | **0** |

`has_table_privilege` para `member_qa`:

| Tabla | SELECT |
|---|---|
| `modulo1.eventos` | ✔ |
| `modulo9.dispositivos_iot` | ✔ |
| `modulo9.infraestructuras` | ✔ |
| `modulo3.observaciones_vision` | ✘ |
| `modulo9.calibraciones_vision` | ✘ |
| `modulo9.lineas_base_vision` | ✘ |

**`SQL_NULL_CONFIRMADO_BD`: NO VERIFICABLE POR PERMISOS.** `member_qa` no puede leer
`modulo9.calibraciones_vision` (`permission denied for table calibraciones_vision`), así
que no se pudo inspeccionar directamente `json_linea_base IS NULL`,
`cantidad_observaciones` ni `cantidad_observaciones_validas` de la fila 15.

**El fix sí quedó verificado funcionalmente por API**, y de forma concluyente: la fila 15
existe en el historial con `estado = FALLIDA` y `etapa_fallo = FILTRADO`. Esa combinación
solo puede estar persistida si el motor aceptó el INSERT, y
`ck_calibracion_vision_resultado_coherente` solo lo acepta cuando `json_linea_base IS
NULL` es verdadero. Es decir: la propia existencia de la fila 15 demuestra que `None`
llegó a la base como **SQL NULL** y no como JSON `'null'`. En la ejecución 1, con el
mismo escenario, el INSERT fue rechazado por ese mismo constraint.

Los conteos por ventana se obtuvieron del propio producto con trazabilidad equivalente:
la cámara 245 es nueva (ninguna observación previa posible) y única activa del área, los
tres lotes declararon `duplicadas = 0`, y el backend reportó `n_observaciones` y
`n_observaciones_validas` por ventana (10/0 aptas, 30/30, 29/29).

---

## RESULTADO PYTEST ACTUAL

`RESULTADOS/run-20261010-131446/pytest.xml` (sobrescrito con esta ejecución):

| | |
|---|---|
| Collected | **22** |
| Passed | **20** |
| Failed | **1** |
| Skipped | **1** |
| Errors | **0** |

**El único fallo es de MI automatización, no del producto, y no afecta a ningún
veredicto.** `test_21_auditoria_rf10` pedía `tamano=100` en la consulta de auditoría y
`GET /auditoria/` admite **50** como máximo, de modo que respondió `400 VAL_ENTRADA`
(field `tamano`: *«Input should be less than or equal to 50»*) antes de leer un solo
evento. `test_22`, que dependía de él, quedó en SKIPPED.

Qué se hizo con eso, y qué no:

* El límite **ya está corregido** en `test_g139_v2.py` (`tamano=50`).
* **No se repitió ningún POST.** El paquete prohíbe repetir un POST que ya recibió
  respuesta (§47) y fija el presupuesto en 3 calibraciones y 3 lotes (§46), que quedó
  agotado y correcto. Las verificaciones posteriores solo pueden hacerse con GET o SELECT
  de solo lectura.
* La auditoría se completó con `automation/cierre_lectura_g139.py`, que reconstruye el
  estado desde `evidencia.json` y **vuelve a ejecutar los mismos oráculos de la suite**
  (`test_21_auditoria_rf10` y `test_22_cuadro_y_cierre`, importados, no reescritos): **0
  POST adicionales, 0 lotes M03 adicionales, 0 DML**.
* **No se maquilló `pytest.xml`.** Refleja la ejecución real de la suite. Si QA necesita
  un `pytest.xml` con `FAILED = 0` según §53, eso requiere volver a emitir los 3 POST
  objetivo con ventanas nuevas, lo que excede el presupuesto de §46 y choca con §47: no
  lo hice por iniciativa propia y queda a tu decisión autorizarlo.

Comparativa del detalle técnico:

| | Ejecución 1 | Ejecución 2 |
|---|---|---|
| Failed por el producto | **1** (`test_18`: 400 en vez de 422) | **0** |
| Failed por la automatización | 0 | **1** (`test_21`: `tamano`) |
| Skipped | 4 (dependían del fallo del producto) | 1 (dependía del fallo de automatización) |

### Presupuesto funcional de la ejecución 2

| Operación | Presupuesto | Ejecutado |
|---|---|---|
| `POST /configuracion/calibraciones-vision` | 3 | **3** |
| `POST /iot/telemetria/vision` | 3 lotes | **3** |
| Reintentos | 0 | **0** |

---

## COMPARACIÓN PRE-FIX VS POST-FIX

### Cadena causal, explícita

| | PRE-FIX (ejecución 1) | POST-FIX (ejecución 2) |
|---|---|---|
| Python | `None` | `None` |
| SQLAlchemy | → JSON `'null'::jsonb` | → **SQL NULL** |
| `ck_calibracion_vision_resultado_coherente` | **falla** (`'null'::jsonb IS NULL` = false) | **acepta** |
| Persistencia de la FALLIDA | no ocurre | **ocurre** |
| Respuesta HTTP | **400 `VALOR_NO_PERMITIDO`** | **422 `LINEA_BASE_NO_CALCULADA`** |
| Historial | no disponible | **disponible (id 15)** |
| Auditoría RF-10 | no queda | **queda (evento 48977)** |

### Tabla obligatoria

| Criterio | Ejecución 1 PRE-FIX | Ejecución 2 POST-FIX |
|---|---|---|
| TC-282 | APROBADO | **APROBADO** |
| N | 30 | **30** |
| N HTTP | 201 | **201** |
| N estado | EXITOSA | **EXITOSA** |
| N baseline | Publicada (id 8) | **Publicada (id 14)** |
| N−1 HTTP | 400 | **422** |
| N−1 error | `VALOR_NO_PERMITIDO` | **`LINEA_BASE_NO_CALCULADA`** |
| N−1 mensaje contractual literal | NO | **SÍ** |
| N−1 historial FALLIDA | NO | **SÍ (id 15)** |
| N−1 etapa FILTRADO | NO | **SÍ** |
| N−1 `json_linea_base` | JSON `'null'` (INSERT rechazado) | **SQL NULL (fila aceptada; `linea_base` null por API)** |
| N−1 auditoría FALLIDO | NO | **SÍ (evento 48977)** |
| Baseline N conservada | SÍ | **SÍ** |
| Pytest failed (producto) | 1 | **0** |
| G139 | RECHAZADO | **APROBADO** |
| Incidencia | ABIERTA | **CORREGIDA** |

**FIX #550 CONFIRMADO FUNCIONALMENTE: SÍ.**

---

## ESTADO DE INCIDENCIA

| | |
|---|---|
| Incidencia original | **CORREGIDA** |
| Incidencia nueva | **NO** |
| Ticket duplicado | no se abre |
| PR que corrige | **#550** |

El defecto se corrigió por completo, no parcialmente: se restauró el contrato (422 con el
mensaje literal), la trazabilidad en el historial (FALLIDA / FILTRADO con motivo) y la
auditoría RF-10 del intento, y se mantuvo la integridad de la línea base vigente. No
apareció ningún defecto nuevo del producto.

**Desvío menor ya conocido, no atribuible a este grupo.** El evento 48975 (rechazo
`VISION_NO_DISPONIBLE` de TC-282) llega con `detalle.id_especie = null`, porque en
`CalibrarVisionUseCase.execute` la variable del área todavía vale `None` cuando se audita
un rechazo lanzado dentro de `_validar`. Ya quedó registrado como observación menor en
TC-M09-G143 y no es criterio de ninguno de los casos de G139: el resto del detalle viaja
completo. Se menciona por trazabilidad, no se duplica aquí.

---

## RESTAURACIÓN

| | |
|---|---|
| Cámara **245** desactivada por API (`PATCH .../desactivar`) | **HTTP 200** |
| Verificación por GET | `es_activo = false` ✔ |
| Pendientes | ninguno |
| Observaciones, calibraciones y línea base | **conservadas** (evidencia trazable) |
| SQL DML en TEST | **0** |

---

## EVIDENCIAS

```
TC-M09-G139/EvaluacionV2/
├── automation/
│   ├── test_g139_v2.py          (suite oficial, 22 controles)
│   └── cierre_lectura_g139.py   (cierre de solo lectura: 0 POST, 0 DML)
└── RESULTADOS/
    └── run-20261010-131446/
        ├── TC-M09-G139_reevaluacion_V2.md   (este informe)
        ├── evidencia.json                   (ejecución vigente + historial_ejecuciones)
        ├── pytest.xml                       (resultado técnico de la ejecución 2)
        └── automation_manifest.json         (SHA-256, execution_number 2)
```

No se crearon artefactos `-post-fix`, `-retry`, `-rerun`, `-final` ni un RUN adicional.
No hay HTML ni colección de Newman: no aplica a este grupo.

| Seguridad | |
|---|---|
| Contraseñas / JWT / `Authorization` / cookies / `refresh_token` persistidos | **NO** |
| Serial y `access_key` de la cámara | **NO** (redactados por patrón; solo en memoria durante la ejecución) |
| DSN con contraseña | **NO** |
| Coincidencias de secretos en `RESULTADOS/` | **0** (verificado por grep) |
| Archivos de la primera evaluación (`RESULTADOS/run-20261007-101924/`) | **NO MODIFICADOS** |
| Comandos git de escritura | **NINGUNO** (solo `fetch`, `rev-parse`, `show`, `status`, `branch`) |

---

## CONCLUSIÓN

La corrección del PR #550 funciona y está desplegada en TEST. En la reejecución completa,
la corrida N−1 devuelve el **422 `LINEA_BASE_NO_CALCULADA`** del contrato con el mensaje
literal, deja la calibración **15** en estado **FALLIDA** y etapa **FILTRADO** con su
motivo, registra el evento RF-10 **48977** con resultado `fallido`, y **conserva** la
línea base **14** publicada por la corrida N con sus valores intactos. El 400
`VALOR_NO_PERMITIDO` no reapareció.

El límite mínimo de observaciones queda demostrado por ambos lados en la misma ejecución y
sobre ventanas nuevas y disjuntas: con **30** aptas se publica la línea base; con **29**
no se publica, no se sustituye la vigente y el rechazo queda informado y trazado. TC-M09-282
y la corrida N mantienen su resultado APROBADO, así que la corrección no introdujo
regresiones.

**TC-M09-G139: APROBADO.** Incidencia original **CORREGIDA**, sin incidencia nueva. El
resultado RECHAZADO de la ejecución 1 se conserva íntegro en el historial de este mismo
informe.

Queda una sola cosa en manos de QA: `pytest.xml` registra un fallo de automatización mío
(el límite `tamano` de la consulta de auditoría, ya corregido en la suite), cuya
verificación se completó por GET sin emitir ningún POST adicional. Si se requiere el
artefacto técnico con `FAILED = 0`, hace falta autorización expresa para volver a emitir
los tres POST objetivo, porque el presupuesto de §46 y la prohibición de reintentos de
§47 no lo permiten por iniciativa de QA.
