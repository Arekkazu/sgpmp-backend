# TC-M09-G141 — SEGUNDA EVALUACIÓN

RF-24 v2.0 · CU05 Flujo F · Caso TC-M09-287 — reemplazo de la línea base VISION

| | |
|---|---|
| RUN_ID | `run-20261010-154601` |
| Ambiente | TEST — `https://api.inmero.co/back-sigab-test` |
| Rama | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` |
| Commit | `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| Herramienta | **Pytest + API HTTP real**; BD solo complementaria |
| Newman | NO APLICA |
| Fecha | 2026-10-10 |

---

## DECISIÓN GENERAL

**TC-M09-287: APROBADO · TC-M09-G141: APROBADO · INCIDENCIA REQUERIDA: NO.**

La secuencia que el caso exige quedó demostrada de punta a punta sobre el mismo par
(área, especie): **L1 vigente → ventana nueva W2 → segundo cálculo exitoso → L2 vigente**.

| | Antes del POST | Después del POST |
|---|---:|---:|
| Línea base vigente del área 289 | **11** (L1) | **13** (L2) |
| Valores | `densidad_actividad 10.0`, `tasa_movimiento 5.0` | `densidad_actividad 20.01`, `tasa_movimiento 8.01` |

Los doce criterios del §38 se cumplen, y pytest cerró con **14 de 14** en verde. No apareció
ninguno de los hallazgos que el paquete anticipaba: no hubo 409 `RECURSO_DUPLICADO` (§32), no
hubo un 2xx que dejara L1 vigente (§33) y L2 no salió con los valores de L1 (§34).

---

## BASELINE — PRIMERA EVALUACIÓN

RUN `run-20261007-102458`, abierto **solo en lectura** y sin modificar.

| Caso | Primera evaluación |
|---|---|
| TC-M09-287 | BLOQUEADO / NO VERIFICABLE |
| TC-M09-G141 | BLOQUEADO / NO VERIFICABLE |

Causa declarada entonces: TEST no publicaba la operación VISION, TC-M09-275 no había producido
una L1 verificable y no se ejecutó ningún POST funcional. **Esa causa no se heredó**: se verificó
el estado actual antes de decidir cualquier cosa.

---

## CAMBIO DE EJECUTABILIDAD

Los cuatro endpoints que la primera evaluación no encontró están **presentes** en TEST,
verificados contra `GET /openapi.json` antes de cualquier escritura:

| Endpoint | Estado |
|---|---|
| `POST /configuracion/calibraciones-vision` | **PRESENTE** |
| `GET /configuracion/calibraciones-vision` | **PRESENTE** |
| `GET /configuracion/calibraciones-vision/linea-base` | **PRESENTE** |
| `POST /iot/telemetria/vision` | **PRESENTE** |

Y existía una **L1 vigente y verificable**, de hecho varias. El grupo era ejecutable sin crear
ninguna calibración de setup.

---

## ENTORNO

| | |
|---|---|
| Backend | `https://api.inmero.co/back-sigab-test` |
| Actor funcional | **Ingeniero de Campo** (`ingeniero@pecuaria.co`, `id_usuario 4`) — único actor del caso |
| DEV / MAIN | no se usaron |
| BD | `158.69.200.27:5448` · `sgpmp_test` · `member_qa` · sesión READ ONLY, solo como contraste |

**N = 30**, leído de `ParametrosLineaBase.min_observaciones`
(`src/configuration/domain/entities/linea_base_vision.py`), con la comprobación de que el caso de
uso sigue tomando los parámetros por defecto (`parametros: ParametrosLineaBase =
ParametrosLineaBase()`). No se asumió en silencio y no se modificó nada en TEST.

```
git branch --show-current → qa/juan-esteban-segunda-evaluacion-rf24-v2.0
git rev-parse HEAD        → 1e3a3848f23ac514339abbf37a34c26bbfbd0ff8
```

No se ejecutó `add`, `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, `stash`, `switch`
ni `checkout`.

---

## PRECHECK

| Comprobación | Resultado |
|---|---|
| VISION (POST y GET de calibraciones y línea base) | **PRESENTE** |
| M03 (`POST /iot/telemetria/vision`) | **PRESENTE** |
| Ingeniero (login + `GET /sesiones/me/permisos`) | **PASS** |
| N resuelto | **30** |
| BD complementaria | **NO DISPONIBLE** |
| Failures de automatización | **0** |
| **AUTORIZAR_RUN** | **SÍ** |

---

## ORÁCULO

El oráculo principal son los endpoints oficiales, en este orden:

1. `GET /configuracion/calibraciones-vision/linea-base?area_id=289` **antes** del segundo
   cálculo → captura la vigencia PRE;
2. `POST /configuracion/calibraciones-vision` — **una sola vez**;
3. `GET /configuracion/calibraciones-vision/linea-base?area_id=289` **después** → captura la
   vigencia POST;
4. `GET /configuracion/calibraciones-vision?area_id=289` como evidencia complementaria de la
   calibración L2.

La ingesta se verifica con la respuesta de `POST /iot/telemetria/vision`: `total`, `aceptadas`,
`duplicadas` y, por observación, `indice_calidad`, `clasificacion_calidad` y `apto_para_ia`.

---

## LÍNEA BASE L1 PRE

**Resolución dinámica.** No se asumió ningún ID histórico. Se listaron las fincas del Ingeniero
(`[1, 65, 85, 117, 141, 162, 163]`), y de cada una sus áreas activas —10 en total—; se filtraron
las que tienen especie y un `tipo_modelo_asignado` del paradigma POBLACIONAL, y a cada candidata
se le consultó la línea base vigente:

| Área | Nombre | Especie | Modelo | `GET linea-base` | Vigente |
|---:|---|---:|---|---:|---:|
| **289** | `QA-G140-A1P-20261010-150013` | 41 | MODELO_AVES | **200** | **11** |
| 288 | `QA-G140-A1-20261010-150013` | 41 | MODELO_AVES | 200 | 12 |
| 279 | `QA-G137-AREA-20261010-105849` | 41 | MODELO_AVES | 200 | 8 |
| 278 | `QA-G137-AREA-20261010-105259` | 41 | MODELO_AVES | 200 | 2 |
| 268 | `QA-G31-AREA-1008170709` | 109 | MODELO_ACUICULTURA | 404 | — |
| 161 | `Area Activa Ingeniero` | 81 | MODELO_AVES | 200 | 1 |

Se eligió la **289**, la más reciente, con un criterio determinista (id descendente): es un área
QA de esta campaña, con una sola calibración en su historial, de modo que el antes y el después
quedan limpios y no se toca dato compartido más antiguo.

### A1 y L1

| | |
|---|---|
| **A1** | área **289** — `QA-G140-A1P-20261010-150013`, activa, finca **163** |
| Especie | **41** |
| `tipo_modelo_asignado` | **MODELO_AVES** → paradigma **POBLACIONAL** |
| Accesible para el Ingeniero | sí (es quien la lista y quien ejecuta) |
| **L1** | `id_calibracion_vision` **11** |
| L1 valores | `densidad_actividad 10.0`, `tasa_movimiento 5.0` |
| L1 `componentes_no_calibrables` | `[]` |
| L1 `fecha_publicacion` | `2026-10-10T20:00:21.614029Z` |
| Fuente de L1 | **REUTILIZADA** — no se creó ninguna calibración de setup |

Conforme al §14, no se exigió que L1 siguiera siendo el id creado originalmente por
TC-M09-275: lo que el caso necesita es una L1 vigente y verificable, y la 11 lo es.

### Historial PRE

| | |
|---|---|
| `GET /configuracion/calibraciones-vision?area_id=289` | total **1** → `[11]` |
| L1 en el historial | **sí** |
| Ventana usada por L1 | `2026-06-03T00:00:00Z` → `2026-06-03T06:00:00Z` |

---

## FIXTURE W2

### Ventana

| | |
|---|---|
| **W2_START** | `2026-06-18T00:00:00Z` |
| **W2_END** | `2026-06-18T06:00:00Z` |
| Último fin conocido del área | `2026-06-03T06:00:00Z` (la ventana de L1) |
| Posterior a la ventana de L1 | **sí**, 15 días después |
| Solapamientos con ventanas ya usadas | **ninguno** (comprobado contra todas las del historial) |
| Cerrada y en el pasado | **sí** |

La ventana no se fijó a mano: se calcula a partir del último `fin` que el historial del área
declara, más 15 días, a medianoche y con 6 horas de duración, y se verifica que no se solape con
ninguna ventana previa y que esté cerrada.

### Cámara

| | |
|---|---|
| Cámara usada | **225**, nueva y exclusiva del RUN |
| Categoría / estado | CAMARA · activa al ingerir |
| fps nominal | 30 |
| Resolución | 1920x1080 |
| Área | 289 |
| Serial / `access_key` | **solo en memoria**; en los artefactos va redactado |

En el área no había ninguna cámara activa: las de los grupos anteriores quedaron inactivas en
sus restauraciones y RF-21 no publica reactivación. Se registró una por el endpoint oficial, sin
tocar estado por SQL. Que sea **recién creada** es además lo que da el aislamiento de W2 sin
depender de la BD: una cámara nueva no puede tener observaciones anteriores, así que el
`duplicadas = 0` de la ingesta es concluyente.

### Observaciones

| | |
|---|---|
| Enviadas | **30** (= N), una cada 5 minutos desde `W2_START` |
| Calidad | `cobertura_ventana 1.0000`, `n_tracks 20`, `n_tracks_perdidos 0`, `fps_efectivo 30.00`, `estado_calibracion CALIBRADA` |
| Vectores objetivo | `densidad_actividad 20.0`, `tasa_movimiento 8.0` |
| Variación | determinista, `(i % 3) · 0.01`; sin aleatoriedad |

Los vectores se eligieron **después** de leer `L1_VALORES` y a propósito lejos de ellos
(10.0 → 20.0 y 5.0 → 8.0), para que L2 no pueda coincidir con L1 por construcción del dataset.
Los componentes son los mismos dos que declara L1, de modo que la comparación final es
componente a componente.

### Ingesta M03

| | |
|---|---|
| HTTP | **201** |
| `total` / `aceptadas` | 30 / **30** |
| **`duplicadas`** | **0** |
| Aptas | **30** |
| `indice_calidad` observados | `[100]` |
| `clasificacion_calidad` | `APTO` en las 30 |

`apto_para_ia` no se envía: lo deriva M03 y se comprobó en la respuesta, observación por
observación. Si alguna hubiera quedado no apta, la calibración no se habría ejecutado.

---

## TC-M09-287 — SEGUNDO CÁLCULO

### Snapshot PRE, inmediatamente antes del POST

| | |
|---|---|
| `PRE_BASELINE_ID` | **11** |
| `PRE_ESPECIE_ID` | 41 |
| `PRE_LINEA_BASE` | `densidad_actividad 10.0`, `tasa_movimiento 5.0` |
| `PRE_FECHA_PUBLICACION` | `2026-10-10T20:00:21.614029Z` |
| Historial PRE | `[11]` |
| Coincide con L1 | **sí** — la vigencia no cambió entre la resolución de L1 y el POST |

### POST objetivo

```json
{
  "modo_calibracion": "VISION",
  "area_id": 289,
  "ventana_observacion": {"inicio": "2026-06-18T00:00:00Z", "fin": "2026-06-18T06:00:00Z"},
  "observaciones": "QA TC-M09-287 reemplazo línea base",
  "fecha_calibracion": "2026-10-10T20:46:07+00:00"
}
```

Ejecutado **una sola vez**, por el Ingeniero.

| | |
|---|---|
| HTTP | **201** |
| **`L2_CAL_ID`** | **13** |
| Estado | **EXITOSA** |
| `etapa_fallo` | `null` |
| `especie_id` | **41** (el mismo par que L1) |
| `n_observaciones` | 30 |
| `n_observaciones_validas` | **30** ( ≥ N = 30 ) |
| `iteraciones` | 1 |
| `origen_disparo` | MANUAL |
| `id_usuario` | 4 |
| `linea_base` | `densidad_actividad 20.01`, `tasa_movimiento 8.01` |

---

## LÍNEA BASE L2 POST

`GET /configuracion/calibraciones-vision/linea-base?area_id=289`

| | |
|---|---|
| HTTP | **200** |
| `id_calibracion_vision` | **13** |
| `especie_id` | 41 |
| `linea_base` | `densidad_actividad 20.01`, `tasa_movimiento 8.01` |
| `fecha_publicacion` | `2026-10-10T20:46:07.794993Z` |

---

## COMPARACIÓN L1 → L2

| Criterio | Valor |
|---|---|
| `L1_ID` | **11** |
| `L2_ID` | **13** |
| `L1_VALORES` | `densidad_actividad 10.0`, `tasa_movimiento 5.0` |
| `L2_VALORES` | `densidad_actividad 20.01`, `tasa_movimiento 8.01` |
| PRE vigente | **11** |
| POST vigente | **13** |
| `L1 != L2` | **SÍ** |
| `GET linea-base` apunta a L2 | **SÍ** |
| `POST.linea_base == GET.linea_base` | **SÍ** |
| L1 ya no vigente | **SÍ** |
| Valores de L2 distintos de L1 | **SÍ** |
| **Reemplazo confirmado** | **SÍ** |

Que los valores además cambien es lo que descarta la lectura perezosa: no estamos viendo el
mismo baseline con otra fecha, sino una línea base recalculada con otras observaciones.

---

## HISTORIAL

`GET /configuracion/calibraciones-vision?area_id=289`

| | |
|---|---|
| Total | **2** → `[13, 11]` |
| **L2 en el historial** | **SÍ**, estado **EXITOSA**, 30/30, 1 iteración, ventana `2026-06-18T00:00:00Z` → `06:00:00Z` |
| L1 conservada en el historial | **SÍ** |

La conservación de L1 **no** es criterio de aprobación (§29 y §39): se registra como evidencia.
Tampoco se exigió su eliminación física, ni su desaparición del historial, ni ningún ID concreto.
Lo único que se comprobó es la vigencia: PRE = L1, POST = L2.

---

## BD COMPLEMENTARIA

**NO DISPONIBLE.**

| Tabla | `has_table_privilege(member_qa, …, 'SELECT')` |
|---|---|
| `modulo3.observaciones_vision` | **false** |
| `modulo9.calibraciones_vision` | **false** |
| `modulo9.lineas_base_vision` | **false** |

Se intentó el contraste de `modulo9.lineas_base_vision` para el par (289, 41) y de la
calibración 13, y quedó registrado el error literal del motor. Conforme al §4 y al §30: **no** se
bloqueó, **no** se saltó el caso, **no** se canceló el POST y **no** se marcó error funcional.
Tampoco se presentó ninguna lectura de la API como si fuera un `SELECT`: cada dato de este
informe dice de dónde sale.

La BD no contradice a la API — simplemente no fue consultable. Sigue siendo deseable un
`GRANT SELECT` a `member_qa` (o al rol `rol_qa`) sobre las tres tablas para poder añadir el
contraste; es una **limitación de acceso QA**, con responsable **DBA / Implementación**, y **no
genera incidencia funcional**.

---

## RESULTADO PYTEST

```
pytest automation/test_g141_v2.py -v
14 tests · 14 passed · 0 failed · 0 errors · 0 skipped · 8.00 s
```

| | |
|---|---|
| Collected | 14 |
| Passed | **14** |
| Failed | **0** |
| Errors | **0** |
| `pytest.xml` | en este RUN |

### Presupuesto funcional

| Operación | Presupuesto | Ejecutados | Reintentos |
|---|---:|---:|---:|
| `POST /configuracion/calibraciones-vision` (objetivo) | 1 | **1** | **0** |
| `POST /configuracion/calibraciones-vision` (setup de L1) | 1 | **0** | 0 |
| `POST /iot/telemetria/vision` | 2 | **1** | 0 |

Verificado por contador dentro de la automatización, que aborta si se intenta repetir un POST ya
respondido. No hizo falta ningún POST de setup porque L1 se reutilizó.

### Criterios del §38

| # | Criterio | Cumple |
|---:|---|---|
| 1 | L1 vigente PRE verificable por API | **sí** |
| 2 | W2 posterior y con ≥ N observaciones aptas | **sí** |
| 3 | Ingesta con `aceptadas = esperadas` y `duplicadas = 0` | **sí** |
| 4 | POST del segundo cálculo 2xx | **sí** (201) |
| 5 | Estado EXITOSA | **sí** |
| 6 | Se obtiene `L2_CAL_ID` | **sí** (13) |
| 7 | `GET linea-base` POST = `L2_CAL_ID` | **sí** |
| 8 | `L2_CAL_ID != L1_ID` | **sí** |
| 9 | La API ya no presenta L1 como vigente | **sí** |
| 10 | Valores del GET L2 iguales a los del POST | **sí** |
| 11 | L2 aparece en el historial | **sí** |
| 12 | La BD, si está disponible, no contradice la API | **sí** (no disponible; sin contradicción) |

---

## INCIDENCIA

**INCIDENCIA REQUERIDA: NO.**

El segundo cálculo reemplazó la línea base vigente del par (área, especie) como la ficha
describe. No se abre nada.

Descartados explícitamente los supuestos que el paquete anticipaba:

- **§32 — 409 `RECURSO_DUPLICADO`:** no ocurrió. El reemplazo funcionó en el primer intento, sin
  cambiar de área, sin borrar L1 y sin inventar otra pareja. (Esto es coherente con la corrección
  del 409 que se validó en TC-M09-G137: la política RLS de `UPDATE` sobre
  `modulo9.lineas_base_vision` sigue en su sitio.)
- **§33 — 2xx que no reemplaza:** no ocurrió; `GET linea-base` pasó de 11 a 13.
- **§34 — L2 con los valores de L1:** no ocurrió; los valores cambiaron de
  `{10.0, 5.0}` a `{20.01, 8.01}`, como el dataset de W2 pretendía.
- **§35 — el defecto de G139/G140:** no afecta a este caso y no se bloqueó nada por él. Ese
  defecto está en la ruta de persistencia de calibraciones **no exitosas**
  (`INC-RF24-VISION-NO-EXITOSA`), y TC-M09-287 requiere una calibración EXITOSA, que es
  precisamente la ruta que sí funciona.
- **Falta de SELECT de QA:** limitación de ambiente, no incidencia funcional.

---

## EVIDENCIAS

`tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G141/EvaluacionV2/`

```
automation/
  test_g141_v2.py
RESULTADOS/run-20261010-154601/
  TC-M09-G141_reevaluacion_V2.md
  evidencia.json
  automation_manifest.json
  pytest.xml
```

El script no se copia dentro del RUN; el manifiesto lleva su ruta, su función y su SHA-256, más
el SHA-256 de cada artefacto.

### Restauración

| | |
|---|---|
| Cámara 225 | **desactivada**, HTTP 200, verificado `es_activo = false` |
| Pendientes | **0** |
| L2 (calibración 13) | **conservada** — es resultado funcional válido de la prueba |
| Línea base vigente | **conservada** (apunta a 13) |
| SQL DML en TEST | **0** |

### Seguridad

| | |
|---|---|
| Credenciales persistidas | **NO** |
| Serial / `access_key` de cámara | **NO** — redactado por patrón, solo en memoria |
| JWT / `Authorization` / cookies | **NO** |
| DSN con contraseña | **NO** |
| Baseline de la primera evaluación modificada | **NO** |

Un `grep` de la contraseña de los actores, la de la BD de QA, el prefijo de un JWT portador y el
patrón de serial de cámara sobre los artefactos del RUN devuelve **0 coincidencias** (los
literales no se transcriben aquí, para no reintroducirlos).

---

## CONCLUSIÓN

El bloqueo de la primera evaluación está resuelto y el caso quedó demostrado sin ambigüedad.

Había varias líneas base VISION vigentes en TEST, así que se reutilizó una —la del área 289,
calibración **11**, con `{densidad_actividad 10.0, tasa_movimiento 5.0}`— en lugar de fabricar un
setup innecesario. Sobre esa misma área y especie se construyó una ventana nueva y posterior, con
una cámara recién creada y 30 observaciones aptas cuyos vectores se eligieron deliberadamente
lejos de los de L1; la ingesta reportó 30 de 30 aceptadas y **cero duplicadas**, que es lo que
acredita que la ventana estaba limpia sin necesidad de consultar la base.

El segundo cálculo respondió **201 EXITOSA** con la calibración **13**, 30 de 30 observaciones
válidas y convergencia en una iteración. Inmediatamente después, `GET linea-base` dejó de
devolver la 11 y devolvió la **13**, con exactamente los valores que había devuelto el POST y
claramente distintos de los de L1. La 13 figura en el historial como EXITOSA y la 11 se conserva
ahí como registro, sin que eso fuera requisito.

La BD de QA sigue sin `SELECT` sobre las tablas de VISION, de modo que el contraste
complementario no se pudo hacer. Con la matriz de este grupo eso no bloquea nada y se documentó
como limitación de acceso; todo lo que este informe afirma sobre vigencia y persistencia viene de
los endpoints oficiales del producto.

**TC-M09-287: APROBADO · TC-M09-G141: APROBADO · Incidencia: NO.**
