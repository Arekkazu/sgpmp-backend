# TC-M09-G140 — SEGUNDA EVALUACIÓN

**RF-24 v2.0 · CU05 Flujo F · Módulo 9 — Línea base por visión: etapas 1, 2 y 3**

| | |
|---|---|
| RUN lógico vigente | `run-20261010-150013` (no se creó un RUN nuevo) |
| Ejecuciones del grupo | **3** |
| Carpetas de RESULTADOS | **una sola**: `run-20261010-150013`. Los artefactos de la ejecución 1 (`run-20261010-141449`) y la corrida de diagnóstico (`run-diagnostico-20261010-142600`) se consolidaron en este informe y se eliminaron por decisión de QA (2026-10-11) para evitar ambigüedad sobre cuál es el RUN vigente |
| Casos | TC-M09-284 (TEST), TC-M09-285 (TEST), TC-M09-286 (LOCAL AISLADO) |
| Herramienta | Pytest + `requests` contra TEST · Pytest en proceso + `TestClient` + PostgreSQL local para TC-286. Newman: **NO APLICA** |
| Rama QA | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` |
| HEAD QA | `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| `origin/test` | `c4612dae6d8f0601488b94a3635f6592aa640686` |

Este informe es la historia completa de la segunda evaluación del grupo, no solo de la
ejecución vigente.

---

## DECISIÓN GENERAL ACTUAL

| Caso | Resultado vigente |
|---|---|
| **TC-M09-284** | **APROBADO** |
| **TC-M09-285** | **APROBADO** |
| **TC-M09-286** | **APROBADO** |
| **TC-M09-G140** | **APROBADO** |

**`INC-RF24-VISION-NO-EXITOSA`: CORREGIDA** (PR #550) · **Incidencia nueva: NO**

**Evolución del grupo:** `BLOQUEADO / RECHAZADO → RECHAZADO → APROBADO`

Los resultados anteriores se conservan íntegros en el historial de ejecuciones y no fueron
eliminados. No hubo regresiones: TC-284 y TC-285 mantienen el APROBADO de la ejecución 2.

---

## HISTORIAL DE EJECUCIONES

### EJECUCIÓN 1 — EVALUACIÓN INICIAL

| | |
|---|---|
| RUN | `run-20261010-141449` — carpeta ya eliminada; su resultado queda consolidado aquí |
| TC-M09-284 | **BLOQUEADO** |
| TC-M09-285 | **BLOQUEADO** |
| TC-M09-286 | **RECHAZADO** |
| **TC-M09-G140** | **RECHAZADO** |

TC-284 y TC-285 quedaron bloqueados por una precondición de acceso QA/DBA: la matriz de
entonces exigía el oráculo de BD y `member_qa` no tenía SELECT sobre las tablas VISION. No
se ejecutó ningún POST.

TC-286 destapó el defecto. Con `max_iteraciones = 1` el algoritmo hizo lo correcto —el
cálculo terminó en **NO_CONVERGIDA / REFINAMIENTO** tras 1 iteración— pero al persistirlo:

| Criterio | Esperado | Obtenido en la ejecución 1 |
|---|---|---|
| HTTP | 422 | **400** |
| error_code | `LINEA_BASE_NO_CALCULADA` | **`VALOR_NO_PERMITIDO`** |
| field | — | `calibracion_vision_resultado_coherente` |
| Calibración persistida | NO_CONVERGIDA / REFINAMIENTO | **no se persistió** |
| Auditoría RF-10 del intento | FALLIDO | **no quedó** |
| Línea base previa | conservada | **conservada (sin daño de datos)** |

### EJECUCIÓN 2 — REEJECUCIÓN PARCIAL

| | |
|---|---|
| RUN lógico | `run-20261010-150013` |
| TC-M09-284 | **APROBADO** |
| TC-M09-285 | **APROBADO** |
| TC-M09-286 | **NO REEJECUTADO** — conservó RECHAZADO |
| **TC-M09-G140** | **RECHAZADO** |
| Pytest TEST | 16 collected · 16 passed · 0 failed · 0 skipped · 0 errors |

QA autorizó reejecutar solo TC-284 y TC-285, con la BD de TEST como verificación
complementaria en lugar de precondición bloqueante.

### CORRECCIÓN DE DESARROLLO — PR #550

| | |
|---|---|
| PR | **#550** |
| Archivo | `src/configuration/infrastructure/models/calibracion_vision_model.py` |
| Cambio | `mapped_column(JSONB)` → **`mapped_column(JSONB(none_as_null=True))`** |
| Objetivo | que el `None` de Python se persista como **SQL NULL** y no como el valor JSON `'null'` |
| Alcance declarado | TC-M09-283 y **TC-M09-286** |
| Efecto buscado | permitir la persistencia correcta de las calibraciones **FALLIDA** y **NO_CONVERGIDA** |
| Autorización de reejecución | líder de Desarrollo |

Verificación por lectura, sin cambiar de rama (`git show`, sin `checkout`, `switch`,
`merge` ni `rebase`):

```
origin/test = c4612dae6d8f0601488b94a3635f6592aa640686
origin/test:…/calibracion_vision_model.py
  → json_linea_base: Mapped[Optional[dict]] = mapped_column(JSONB(none_as_null=True))
```

* **Fix presente en `origin/test`: SÍ**
* **Fix presente en el working tree de la rama QA: NO** — esa línea sigue siendo
  `mapped_column(JSONB)`

Esa segunda comprobación es la que determinó cómo se montó el laboratorio de TC-286, y se
explica en la sección correspondiente.

### EJECUCIÓN 3 — REEJECUCIÓN COMPLETA POST-FIX

| | |
|---|---|
| RUN lógico | `run-20261010-150013` (el mismo; **no** se creó otro) |
| Fecha/hora | 2026-10-11 01:01–01:10 UTC (2026-10-10 20:01–20:10 −05:00) |
| Tipo | `REEJECUCION_COMPLETA_POST_FIX` · autorizada por el líder de Desarrollo |
| Grupo completo reejecutado | **SÍ** (284, 285 y 286) |
| TC-M09-284 | **APROBADO** |
| TC-M09-285 | **APROBADO** |
| TC-M09-286 | **APROBADO** |
| **TC-M09-G140** | **APROBADO** |

---

## PRECHECK DE AUTOMATIZACIÓN

Esta ejecución incorporó un precheck obligatorio del arnés, **antes de crear fixtures y
antes de cualquier POST**. Nació de un fallo real de la reejecución de G139: la consulta de
auditoría pedía `tamano=100` cuando el contrato admite 50, y eso se descubrió cuando los
POST ya estaban hechos y no se podían repetir.

| Comprobación | Resultado |
|---|---|
| Sintaxis Python e imports del arnés y del oráculo | **PASS** |
| OpenAPI de TEST (`GET /openapi.json`) | **PASS** (200) |
| Los 15 endpoints que usa el arnés están publicados | **PASS** |
| Cuerpos requeridos cubiertos por lo que el arnés envía | **PASS** |
| Query params obligatorios (`area_id` en los dos GET de VISION) | **PASS** |
| Límites min/max de paginación de `GET /auditoria/` | **PASS** |
| `tamano` dentro del contrato | **PASS** — contrato: min 1, **max 50**, default 20; el arnés usa **50** |
| Campos del esquema de respuesta que el arnés lee | **PASS** (11 campos, todos declarados) |
| El esquema **no** declara `exitoso`; el resultado va en `resultado` | **PASS** |
| Autotest del oráculo (percentiles, medianas, descarte, winsorización, cambio relativo, epsilon, max_iteraciones) | **PASS** |
| Independencia del oráculo (sin imports del producto) | **PASS** |
| Ventanas: `start < end`, cerradas en el pasado, disjuntas entre sí y de las ejecuciones anteriores | **PASS** |
| Rutas del RUN y escritura de artefactos | **PASS** |
| Sanitización (token y contraseña redactados) | **PASS** |
| **AUTOMATION_PRECHECK** | **PASS** |
| **AUTORIZAR_POSTS** | **SÍ** |

**El precheck sirvió para lo que se diseñó.** En su primera pasada falló con:

```
el arnés usa endpoints que TEST no publica:
  GET /configuracion/infraestructuras/{infraestructura_id}
  PATCH /configuracion/dispositivos-iot/{dispositivo_id}/desactivar
```

Eran dos plantillas de ruta que yo había escrito de memoria; las reales son
`{id_infraestructura}` y `{id_dispositivo_iot}`. Se corrigió el arnés y se repitió el
precheck hasta PASS. **No se consumió ningún POST funcional**, porque el precheck corre
antes de la compuerta que los autoriza (§13 y §67).

El autotest del oráculo verifica contra valores calculados a mano: `p50` de `[1,2,3,4]` =
2.5, `p25` de `[10,20]` = 12.5, mediana par e impar, y con `[1..10]` → `p5 = 1.45`,
`p95 = 9.55`, descarte deja 8 valores (2 a 9) y winsorización deja 10 recortados a los
bordes. Además comprueba que, con `max_iteraciones = 1`, el oráculo declara
`NO_CONVERGIDA / REFINAMIENTO` para el dataset de TC-286.

---

## PRECHECK TEST

| Comprobación | Resultado |
|---|---|
| `POST`/`GET /configuracion/calibraciones-vision` | PRESENTE |
| `GET /configuracion/calibraciones-vision/linea-base` | PRESENTE |
| `POST /iot/telemetria/vision` | PRESENTE |
| Ingeniero de Campo (`ingeniero@pecuaria.co`) | **PASS** |
| Administrador (`administador.dev@gmail.com`) | **PASS** |
| Finca activa compartida por los dos actores | **PASS** (resuelta por intersección) |
| **AUTORIZAR_TEST** | **SÍ** |

No se persiste ninguna contraseña ni token: llegan por entorno y el sanitizador redacta
cabeceras `Authorization`, tokens y seriales antes de escribir cualquier artefacto.

---

## PARÁMETROS VIGENTES

Leídos de nuevo del código, y **también de `origin/test`**, que es el build que TEST
ejecuta: si difirieran, el oráculo quedaría congelado con parámetros que no son los del
producto bajo prueba.

| Parámetro | Working tree QA | `origin/test` | Usado en el laboratorio TC-286 |
|---|---|---|---|
| `min_observaciones` (N) | 30 | 30 | 30 |
| `cobertura_minima` | 0.5 | 0.5 | 0.5 |
| `tracks_minimos` | 1 | 1 | 1 |
| `min_datos_componente` | 10 | 10 | 10 |
| `epsilon` | 0.01 | 0.01 | 0.01 |
| `max_iteraciones` | 10 | 10 | **1** |

**Coinciden árbol y `origin/test`: SÍ.** `max_iteraciones = 1` existe **solo** en el
laboratorio local; TEST no se modificó.

Fuente: `ParametrosLineaBase` en
`src/configuration/domain/entities/linea_base_vision.py`. El router construye
`CalibrarVisionUseCase` sin pasar `parametros`, así que el valor por defecto es el vigente.

---

## FIXTURE TEST ACTUAL

Fixture **nuevo** de esta ejecución. No se reutilizaron las áreas 288/289 ni las cámaras
223/224 de la ejecución 2.

| Elemento | Valor |
|---|---|
| Finca | **163** (activa y visible para los dos actores) |
| Tipo de área | `Galpón` (resuelto del catálogo) |
| Especie | **41**, `MODELO_AVES`, paradigma POBLACIONAL |
| **A1_CURRENT** | **294** — `QA-G140-A1-20261011-010124`, activa |
| **A1_PRIMA_CURRENT** | **295** — `QA-G140-A1P-20261011-010124`, activa |
| **CAM_K_CURRENT** | **246** — CAMARA, activa, 30 fps, en el área 294 |
| **CAM_KM_CURRENT** | **247** — CAMARA, activa, 30 fps, en el área 295 |

Las áreas las creó el **Administrador**: el Ingeniero de Campo no tiene acción Crear sobre
infraestructuras (recurso 10 solo con acción 2, Leer). Esto evita repetir el 403 de
fixture que ya se encontró antes. Después se comprobó por GET que el Ingeniero —actor de
los tres POST funcionales— ve ambas áreas: **HTTP 200** en las dos.

Ventanas nuevas, cerradas, pasadas y disjuntas, también de las de la ejecución 2 (01, 03 y
05 de junio):

| Ventana | Inicio | Fin |
|---|---|---|
| `WINDOW_284_K_CURRENT` | 2026-06-11T00:00:00Z | 2026-06-11T06:00:00Z |
| `WINDOW_284_KM_CURRENT` | 2026-06-13T00:00:00Z | 2026-06-13T06:00:00Z |
| `WINDOW_285_CURRENT` | 2026-06-15T00:00:00Z | 2026-06-15T06:00:00Z |

Las cámaras son nuevas, así que ninguna observación histórica puede caer dentro de esas
ventanas: se exigió **`duplicadas = 0`** en los tres lotes y se cumplió.

---

## TC-M09-284 — EJECUCIÓN ACTUAL

**Etapa 1: las observaciones no aptas deben quedar completamente fuera del cálculo.**

### Ingesta

| | A1 (294) — solo K | A1' (295) — K + M |
|---|---|---|
| HTTP | **201** | **201** |
| total | 40 | **50** |
| aceptadas | 40 | 50 |
| duplicadas | **0** | **0** |
| aptas | **40** | **40** |
| no aptas | 0 | **10** |
| `indice_calidad` devuelto | 100 | **3 y 100** |

* **K** = 40 observaciones aptas con valores conocidos (`densidad_actividad` 10.0 + jitter
  determinístico, `tasa_movimiento` 5.0 + jitter), todas con cobertura 1.0, 20 tracks,
  0 perdidos y `CALIBRADA`.
* **M** = 10 observaciones inequívocamente no aptas con valores extremos
  (`densidad_actividad ≈ 1000`, `tasa_movimiento ≈ 500`, es decir **≈ 100 × la mediana de
  K**), con cobertura 0.1, 0 tracks y `SIN_DETECCION`.

`apto_para_ia` no se envió en ningún caso: lo calculó M03 con las cuatro dimensiones de
RF-62.

### Calibraciones

Actor: Ingeniero de Campo. Una sola ejecución por área, 0 reintentos.

| | K (área 294) | K+M (área 295) |
|---|---|---|
| HTTP | **201** | **201** |
| `CAL_284_*_CURRENT` | **16** | **17** |
| `estado` | **EXITOSA** | **EXITOSA** |
| `etapa_fallo` | null | null |
| `n_observaciones` | 40 | **50** |
| `n_observaciones_validas` | **40** | **40** |
| `iteraciones` | 1 | 1 |
| `origen_disparo` | MANUAL | MANUAL |

El dato decisivo está en la última fila de arriba: en K+M el backend contó **50
observaciones** y solo **40 válidas**. Las 10 no aptas entraron en la ventana y fueron
excluidas en el filtrado.

### Comparación de líneas base

| Componente | `BASE_K` (cal. 16) | `BASE_KM` (cal. 17) |
|---|---|---|
| `densidad_actividad` | **10.0** | **10.0** |
| `tasa_movimiento` | **5.0** | **5.0** |

**`BASE_K == BASE_KM`: SÍ**, componente por componente. Y las dos coinciden con el oráculo
independiente en **ambas** lecturas admitidas (DESCARTE y WINSORIZACIÓN), que para este
dataset dan el mismo resultado porque las M quedan fuera en la Etapa 1, antes del recorte.

### Postcondición por API

| | K | K+M |
|---|---|---|
| Historial del área | `[16]` — PASS | `[17]` — PASS |
| `GET linea-base` | 200, vigente **16** | 200, vigente **17** |
| Valores de la línea base vigente | `{10.0, 5.0}` | `{10.0, 5.0}` |

Cada área apunta a su propia calibración.

**TC-M09-284: APROBADO** — K tiene 40 aptas (≥ N), K+M contiene esas mismas 40 aptas más
10 no aptas, ambas calibraciones son EXITOSA, las válidas son 40 en las dos, las líneas
base quedaron persistidas y son idénticas.

---

## TC-M09-285 — EJECUCIÓN ACTUAL

**Etapas 2 y 3: recorte p5/p95 y refinamiento iterativo.**

### Dataset deliberadamente discriminante

40 observaciones aptas con distribución asimétrica: 20 valores de `densidad_actividad` en
1.0 y luego 2.0, 3.0, … 21.0 (y `tasa_movimiento` = 10 × ese valor).

| | HTTP | total | aceptadas | duplicadas | aptas |
|---|---|---|---|---|---|
| Lote | **201** | 40 | 40 | **0** | **40** |

### Oráculo congelado ANTES del POST

| Componente | p5 | p95 | n tras descarte |
|---|---|---|---|
| `densidad_actividad` | 1.0 | 19.05 | 38 |
| `tasa_movimiento` | 10.0 | 190.5 | 38 |

| Componente | `ORACLE_DESCARTE` | `ORACLE_WINSORIZACION` |
|---|---|---|
| `densidad_actividad` | **1.0** | **1.5** |
| `tasa_movimiento` | **10.0** | **15.0** |

**`ORACULOS_DISCRIMINAN`: SÍ** — las dos lecturas difieren en los dos componentes, así que
el caso distingue de verdad entre ellas. Esto se verificó, y se dejó registrado en la
evidencia, **antes** de ejecutar el producto; después del POST no se recalculó ni se tocó
el oráculo.

### Resultado del POST objetivo

Actor: Ingeniero de Campo. Una sola ejecución, 0 reintentos.

| | Esperado | Obtenido |
|---|---|---|
| HTTP | 2xx (ref. 201) | **201** |
| `CAL_285_CURRENT_ID` | — | **18** |
| `estado` | EXITOSA | **EXITOSA** |
| `etapa_fallo` | null | **null** |
| `n_observaciones` / `n_validas` | 40 / 40 | **40 / 40** |
| `iteraciones` | ≤ `max_iteraciones` (10) | **1** |

### Coincidencia componente por componente

| Componente | Producto | DESCARTE | WINSORIZACIÓN | Coincide con |
|---|---|---|---|---|
| `densidad_actividad` | **1.0** | **1.0** | 1.5 | **DESCARTE** |
| `tasa_movimiento` | **10.0** | **10.0** | 15.0 | **DESCARTE** |

**`INTERPRETACION_OBSERVADA`: DESCARTE.** El producto elimina los valores fuera de
`[p5, p95]` en lugar de recortarlos al borde. Es una de las dos lecturas que la matriz
admite, y es consistente con lo observado en la ejecución 2.

### Postcondición por API

| | |
|---|---|
| Historial del área 294 | `[18, 16]` — contiene la calibración 18 |
| `GET linea-base` | 200, vigente **18**, valores `{densidad 1.0, tasa 10.0}` |

**TC-M09-285: APROBADO.**

---

## ORÁCULO INDEPENDIENTE

`EvaluacionV2/automation/oracle_g140.py` implementa las tres etapas desde cero. Verificado
estáticamente en el precheck: **no importa** `calcular_linea_base`, `recortar_p5_p95`,
`mediana`, `percentil` ni ningún módulo `src.configuration...` o `src.telemetry...`. Si lo
hiciera dejaría de ser un oráculo y sería un espejo del producto.

Calcula por sí mismo el percentil (interpolación lineal, método tipo 7), la mediana, los
límites p5/p95, las dos lecturas de recorte, el refinamiento iterativo, el cambio relativo
por componente, la convergencia contra epsilon y el agotamiento de `max_iteraciones`.

---

## LABORATORIO LOCAL

Aquí está la decisión técnica más importante de esta ejecución.

**El problema.** El fix del PR #550 está en `origin/test`, pero **no** en el working tree
de la rama QA. El laboratorio monta el árbol del repositorio en `/app`, y ese volumen
sustituye el contenido de la imagen: si se hubiera levantado como en la ejecución 1, el
backend local habría ejecutado el código **viejo** y TC-286 habría vuelto a dar 400 por
infraestructura, no por el producto.

**La solución, sin tocar la rama QA.** Se exportó `origin/test` con `git archive` a un
directorio **fuera del working tree**, se copiaron allí los ficheros de `automation/`, y
el laboratorio se levantó desde esa copia de solo lectura. Sin `checkout`, sin `switch`,
sin `merge`, sin `rebase` y sin modificar un solo archivo del repositorio.

| | |
|---|---|
| **`LOCAL_SOURCE_SHA`** | **`c4612dae6d8f0601488b94a3635f6592aa640686`** (= `origin/test`) |
| Mecanismo | `git archive origin/test` → directorio externo → build y volumen `/app` |
| Archivo realmente importado | `/app/src/configuration/infrastructure/models/calibracion_vision_model.py` |
| Línea importada | `json_linea_base: Mapped[Optional[dict]] = mapped_column(JSONB(none_as_null=True))` |
| **Fix en el texto del archivo importado** | **SÍ** |
| **`none_as_null` efectivo en el tipo de SQLAlchemy** | **`True`** |
| Veredicto | **PASS** |

La segunda comprobación es la que de verdad cierra el asunto: no se leyó solo el texto del
archivo, se le preguntó al propio modelo cargado en memoria cómo serializa esa columna. Si
cualquiera de las dos hubiera fallado, el caso se detenía antes de empezar.

### Precheck y guarda de aislamiento

| Comprobación | Resultado |
|---|---|
| Docker disponible | **PASS** (29.6.2) |
| Puerto 55440 libre antes de levantar | **PASS** |
| `docker compose config` válido | **PASS** |
| Sin marcas de ambiente compartido en el compose | **PASS** (0 coincidencias) |
| PostgreSQL healthy | **PASS** (PostgreSQL 18.6, volumen exclusivo creado desde cero) |
| Backend arrancado sobre la app real (`TestClient`) | **PASS** |
| Migraciones | **PASS** — `alembic upgrade head` → **`5c2e8a1f7d39`** |
| Tablas VISION presentes | **PASS** |
| `GET`/`POST` VISION y M03 VISION disponibles en local | **PASS** |
| Roles del laboratorio correctos | **PASS** |

**Guarda de seguridad (§47):**

| | |
|---|---|
| DB host / port / name | `db` / `5432` / **`sgpmp_g140_lab`** |
| `current_user` / `current_database` | `postgres` / `sgpmp_g140_lab` |
| Backend | `TestClient` en proceso (sin puertos publicados) |
| `158.69.200.27`, `sgpmp_test`, `sgpmp_dev`, `api.inmero.co` en la DSN o el entorno | **NINGUNA** |
| Veredicto | **PASS** |

### `max_iteraciones = 1`

Se reutilizó el mecanismo ya probado, sin inventar uno nuevo: se sustituye **en memoria**
el valor por defecto del parámetro `parametros` de `CalibrarVisionUseCase.__init__`
(`__defaults__`), tras comprobar que la firma del caso de uso no cambió, y se revierte al
cerrar la sesión. No se editó `linea_base_vision.py`, no se bifurcó el algoritmo y no se
mockeó ningún repositorio: el router sigue construyendo el caso de uso real.

Evidencia objetiva de que la instancia que calculó estaba operando con 1:

| | |
|---|---|
| `max_iteraciones` efectivo leído del caso de uso | **1** |
| `epsilon` efectivo | **0.01** (sin cambios) |
| Resto de umbrales | sin cambios respecto de los vigentes |
| `iteraciones` en la fila persistida | **1** |
| `motivo` de la fila | **«Sin convergencia tras 1 iteraciones (ε = 1%).»** |

El propio producto declara el 1 en el motivo. No se asumió por el nombre del test.

---

## TC-M09-286 — EJECUCIÓN ACTUAL

**El refinamiento no converge dentro del máximo de iteraciones.**

### Fixture local

Sintético, sembrado por SQL en la base local y exclusiva. Nada copiado de TEST o DEV.

| | |
|---|---|
| Finca / Área A1_LOCAL | 1 / **1** (activa) |
| Especie | **12**, `MODELO_AVES`, paradigma POBLACIONAL |
| Cámara | **1** — CAMARA, activa, 30 fps |
| Actor | Ingeniero local (usuario 4, rol 4), login **PASS** |

### Control positivo: línea base previa L1

| | Esperado | Obtenido |
|---|---|---|
| Lote W1 | 30 aptas, 0 duplicadas | **30 / 30 / 0** |
| Conteo por SELECT | 30 total, 30 aptas | **30 / 30** |
| HTTP | 201 | **201** |
| `estado` | EXITOSA | **EXITOSA** |
| **`CAL_L1_ID` / `L1_ID`** | — | **1** |
| **`L1_VALORES`** | — | **`{densidad_actividad: 10.0, tasa_movimiento: 5.0}`** |
| `GET linea-base` apunta a L1 | SÍ | **SÍ** |
| Línea base vigente en BD | L1 | **1** |

El control positivo pasó, así que la no convergencia posterior es atribuible al caso y no
al laboratorio.

### Oráculo congelado ANTES del POST objetivo

Dataset W2: 30 observaciones aptas con distribución diseñada para que el refinamiento mueva
la mediana más que epsilon.

| | |
|---|---|
| N | 30 |
| `epsilon` | **0.01** (1 %) |
| `max_iteraciones` | **1** |
| Mediana inicial | `densidad_actividad` **4.5** · `tasa_movimiento` **45.0** |
| Mediana tras la iteración 1 | `densidad_actividad` **4.0** · `tasa_movimiento` **40.0** |
| **Cambio relativo máximo** | **0.111111… (11.1111 %)** |
| Criterio | cambio ≥ epsilon → no converge |
| **11.1111 % ≥ 1 %** | **SÍ** |
| **Resultado esperado** | **NO_CONVERGIDA / REFINAMIENTO** |

Estos valores se guardaron en la evidencia antes del POST y no se modificaron después de
observar al producto. Coinciden con las propiedades que la ejecución 1 ya había observado,
pero fueron recalculadas por el oráculo, no copiadas.

### Snapshot PRE

| | |
|---|---|
| Lote W2 | **30 / 30 / 0 duplicadas**, 30 aptas |
| Conteo por SELECT | 30 total, 30 aptas |
| `L1_PRE_ID` | **1** |
| `L1_PRE_VALORES` | `{10.0, 5.0}` |

### POST objetivo

Actor: Ingeniero local. Una sola vez, **sin reintento**.

| | Esperado | Obtenido |
|---|---|---|
| HTTP | **422** | **422** |
| error_code | `LINEA_BASE_NO_CALCULADA` | **`LINEA_BASE_NO_CALCULADA`** |
| Mensaje contractual | literal | **idéntico** |

> No se pudo calcular la línea base: datos insuficientes o sin convergencia para el área 1
> y especie 12. Se conserva la línea base vigente anterior.

**El 400 `VALOR_NO_PERMITIDO` no reapareció.**

### Historial tras el 422

| | Esperado | Obtenido |
|---|---|---|
| Calibraciones nuevas | exactamente 1 | **1** |
| **`CAL_286_CURRENT_ID`** | — | **2** |
| `estado` | NO_CONVERGIDA | **NO_CONVERGIDA** |
| `etapa_fallo` | REFINAMIENTO | **REFINAMIENTO** |
| `linea_base` | null | **null** |
| `n_observaciones` | ≥ N | **30** |
| `n_observaciones_validas` | ≥ N | **30** |
| `iteraciones` | 1 | **1** |
| `motivo` | agotamiento del máximo | **«Sin convergencia tras 1 iteraciones (ε = 1%).»** |

### Línea base tras el intento

| | |
|---|---|
| `GET linea-base` | **200**, `id_calibracion_vision` = **1** |
| Valores | `{densidad_actividad: 10.0, tasa_movimiento: 5.0}` — **idénticos** |
| Línea base vigente en BD | **1** |
| `L1_PRE_ID == L1_POST_ID` | **SÍ** |

La calibración NO_CONVERGIDA **no** se publicó como línea base.

### Auditoría RF-10 del intento

| Campo | Esperado | Obtenido |
|---|---|---|
| `id_evento` | — | **3** |
| `tipo_evento` | CALIBRACION_RECHAZADA | **29** |
| `resultado` | fallido | **fallido** |
| `modulo` | MODULO9 | **MODULO9** |
| `detalle.operacion` | CALIBRACION_VISION | **`CALIBRACION_VISION`** |
| `detalle.codigo_http` | 422 | **422** |
| `detalle.codigo_error` | `LINEA_BASE_NO_CALCULADA` | **`LINEA_BASE_NO_CALCULADA`** |
| `detalle.id_calibracion_vision` | 2 | **2** |
| `detalle.estado` | NO_CONVERGIDA | **NO_CONVERGIDA** |
| `detalle.etapa_fallo` | REFINAMIENTO | **REFINAMIENTO** |
| `detalle.motivo_etapa` | no nulo | **«Sin convergencia tras 1 iteraciones (ε = 1%).»** |
| `detalle.id_infraestructura` / `id_especie` | 1 / 12 | **1 / 12** |
| `id_usuario` / `direccion_ip` | — | 4 / **PRESENTE** |
| `fecha_evento` | — | 2026-10-11T01:08:52.029897Z |

Se comprobó explícitamente que el item **no** trae un campo `exitoso`: el resultado viaja
en `resultado`, como marca el contrato real.

**TC-M09-286: APROBADO** — los doce criterios del §74 se cumplen.

---

## SQL NULL — VERIFICACIÓN LOCAL

Aquí sí se pudo mirar la fila directamente, porque la base es local y controlada:

```sql
SELECT estado, etapa_fallo, json_linea_base IS NULL,
       cantidad_observaciones, cantidad_observaciones_validas, iteraciones, motivo
FROM modulo9.calibraciones_vision WHERE id_calibracion_vision = 2;
```

| Campo | Esperado | Obtenido |
|---|---|---|
| `estado` | NO_CONVERGIDA | **NO_CONVERGIDA** |
| `etapa_fallo` | REFINAMIENTO | **REFINAMIENTO** |
| **`json_linea_base IS NULL`** | **true** | **true** |
| `cantidad_observaciones` | 30 | **30** |
| `cantidad_observaciones_validas` | 30 | **30** |
| `iteraciones` | 1 | **1** |
| `motivo` | no nulo | «Sin convergencia tras 1 iteraciones (ε = 1%).» |

Esto es la prueba directa del PR #550: el `None` de Python llegó a PostgreSQL como **SQL
NULL**, la rama del CHECK para `estado <> 'EXITOSA'` se cumplió y el INSERT fue aceptado.
En la ejecución 1 esa misma fila era rechazada porque `json_linea_base` llevaba el valor
JSON `'null'`, y `'null'::jsonb IS NULL` es false.

---

## HISTORIAL DE CALIBRACIONES

**TEST** — `GET /configuracion/calibraciones-vision`

| Área | ID | Estado | n_obs | n_válidas | Iter. | Caso |
|---|---|---|---|---|---|---|
| 294 | **18** | EXITOSA | 40 | 40 | 1 | TC-M09-285 |
| 294 | **16** | EXITOSA | 40 | 40 | 1 | TC-M09-284 (K) |
| 295 | **17** | EXITOSA | 50 | **40** | 1 | TC-M09-284 (K+M) |

**LOCAL** — base `sgpmp_g140_lab`

| Área | ID | Estado | Etapa | n_obs | n_válidas | Iter. | Caso |
|---|---|---|---|---|---|---|---|
| 1 | **2** | NO_CONVERGIDA | REFINAMIENTO | 30 | 30 | **1** | TC-M09-286 (objetivo) |
| 1 | **1** | EXITOSA | — | 30 | 30 | 1 | TC-M09-286 (control L1) |

No se borró ninguna calibración ni observación: son evidencia trazable.

---

## LÍNEAS BASE

| Ambiente | Área | Vigente | Valores |
|---|---|---|---|
| TEST | 294 | **18** | `{densidad_actividad: 1.0, tasa_movimiento: 10.0}` |
| TEST | 295 | **17** | `{densidad_actividad: 10.0, tasa_movimiento: 5.0}` |
| LOCAL | 1 | **1** (L1, conservada) | `{densidad_actividad: 10.0, tasa_movimiento: 5.0}` |

En el área 294 la línea base pasó de 16 a 18 porque la calibración de TC-285 fue exitosa:
eso es el comportamiento correcto de publicación. En LOCAL, en cambio, la línea base no se
movió, que es justamente el criterio de integridad de TC-286.

---

## AUDITORÍA RF-10

| Caso | Ambiente | `id_evento` | tipo | `resultado` | `codigo_http` | `codigo_error` |
|---|---|---|---|---|---|---|
| TC-M09-286 (intento) | LOCAL | **3** | 29 | fallido | 422 | `LINEA_BASE_NO_CALCULADA` |

TC-284 y TC-285 son calibraciones exitosas y la matriz del grupo no exige verificar su
evento de auditoría; el contrato de RF-10 para la ruta exitosa ya quedó verificado en
G139 (evento 48976). Lo que este grupo tenía pendiente era el evento del **intento
fallido**, que en la ejecución 1 no existía y ahora sí.

El contrato real del endpoint se validó en el precheck antes de usarlo: `tamano` admite
**50** como máximo y el item expone **`resultado`**, no `exitoso`.

---

## BD TEST COMPLEMENTARIA

| | |
|---|---|
| Rol en la matriz | verificación complementaria cuando esté disponible |
| Conexión | `member_qa`, sesión **READ ONLY** |
| DML ejecutado | **0** |
| **`BD_COMPLEMENTARIA`** | **NO DISPONIBLE POR PERMISOS QA** |

`has_table_privilege('member_qa', …, 'SELECT')`:

| Tabla | SELECT |
|---|---|
| `modulo3.observaciones_vision` | **FAIL** |
| `modulo9.calibraciones_vision` | **FAIL** |
| `modulo9.lineas_base_vision` | **FAIL** |

No bloqueó nada: la herramienta oficial de TC-284 y TC-285 es Pytest + API, y los oráculos
de API son suficientes para el veredicto. El backend reporta `n_observaciones` y
`n_observaciones_validas` por ventana, que es exactamente el conteo que la Etapa 1
produce, y las cámaras nuevas garantizan ventanas limpias (`duplicadas = 0`).

Para TC-286 esto no fue una limitación: la base local se consultó directamente por SELECT,
que es donde la verificación del SQL NULL realmente hacía falta.

---

## RESULTADO PYTEST TEST

| | |
|---|---|
| Collected | **17** |
| Passed | **17** |
| Failed | **0** |
| Skipped | **0** |
| Errors | **0** |
| Failures de producto | **0** |
| Failures de automatización | **0** |
| Archivo | `pytest-test.xml` |

Presupuesto consumido: `POST /iot/telemetria/vision` **3 lotes** ·
`POST /configuracion/calibraciones-vision` **3** · reintentos **0**.

## RESULTADO PYTEST LOCAL

| | |
|---|---|
| Collected | **13** |
| Passed | **13** |
| Failed | **0** |
| Skipped | **0** |
| Errors | **0** |
| Failures de producto | **0** |
| Failures de automatización | **0** |
| Archivo | `pytest-local.xml` |

Presupuesto consumido: 2 lotes M03 (W1 y W2) · 2 calibraciones (control L1 y objetivo) ·
reintentos **0**.

El único fallo de automatización de toda la ejecución ocurrió en el **precheck**, antes de
cualquier escritura, y se corrigió allí mismo: por diseño, no llegó a ningún artefacto
oficial.

---

## COMPARACIÓN PRE-FIX VS POST-FIX

### TC-M09-286

| Criterio | PRE-FIX (ejecución 1) | POST-FIX (ejecución 3) |
|---|---|---|
| `max_iteraciones` | 1 | **1** |
| Oráculo | NO_CONVERGIDA | **NO_CONVERGIDA** |
| Etapa | REFINAMIENTO | **REFINAMIENTO** |
| HTTP | **400** | **422** |
| error_code | `VALOR_NO_PERMITIDO` | **`LINEA_BASE_NO_CALCULADA`** |
| Mensaje contractual literal | NO | **SÍ** |
| Persistencia | **NO** | **SÍ (id 2)** |
| Estado en historial | NO REGISTRADA | **NO_CONVERGIDA** |
| `etapa_fallo` | NO REGISTRADA | **REFINAMIENTO** |
| `json_linea_base IS NULL` | no llegó a persistir | **true** |
| `iteraciones` | 1 en el cálculo | **1, también persistido** |
| Auditoría FALLIDO | **NO** | **SÍ (evento 3)** |
| L1 conservada | SÍ | **SÍ** |
| **TC-286** | **RECHAZADO** | **APROBADO** |

### Cadena causal

| | PRE-FIX | POST-FIX |
|---|---|---|
| Python | `None` | `None` |
| SQLAlchemy (`none_as_null`) | `False` → JSON `'null'::jsonb` | **`True` → SQL NULL** |
| `ck_calibracion_vision_resultado_coherente` | **falla** | **acepta** |
| Respuesta HTTP | 400 `VALOR_NO_PERMITIDO` | **422 `LINEA_BASE_NO_CALCULADA`** |
| Historial y auditoría | no quedan | **quedan** |

**FIX #550 CONFIRMADO EN TC-286: SÍ.**

### Comparación del grupo

| Caso | Ejecución 1 | Ejecución 2 | Ejecución 3 |
|---|---|---|---|
| TC-M09-284 | BLOQUEADO | APROBADO | **APROBADO** |
| TC-M09-285 | BLOQUEADO | APROBADO | **APROBADO** |
| TC-M09-286 | RECHAZADO | RECHAZADO heredado | **APROBADO** |
| **TC-M09-G140** | **RECHAZADO** | **RECHAZADO** | **APROBADO** |

---

## ESTADO DE INCIDENCIA

| | |
|---|---|
| Incidencia | **`INC-RF24-VISION-NO-EXITOSA`** |
| Estado | **CORREGIDA** |
| PR | **#550** |
| Responsable | Desarrollo |
| Type / Severity / Priority | bug / Important / High |
| **Incidencia nueva** | **NO** |

La corrección es completa, no parcial: se restauró el contrato (422 con el mensaje
literal), la trazabilidad en el historial (NO_CONVERGIDA / REFINAMIENTO con motivo e
iteraciones), la auditoría RF-10 del intento y la persistencia como **SQL NULL** verificada
directamente en la base. La integridad de la línea base vigente, que nunca estuvo
comprometida, se mantiene. No se abre ticket duplicado y no apareció ningún defecto nuevo
del producto.

El mismo fix ya se había confirmado por el otro lado en TC-M09-283 (grupo G139), con el
estado FALLIDA / FILTRADO. Las dos ramas de persistencia no exitosa quedan cubiertas.

---

## RESTAURACIÓN

**TEST**

| | |
|---|---|
| Cámara **246** desactivada por API | **HTTP 200** |
| Cámara **247** desactivada por API | **HTTP 200** |
| Pendientes | ninguno |
| Áreas 294 y 295 | conservadas — RF-20 no publica eliminación; quedan como dato QA trazable |
| Calibraciones / líneas base / observaciones borradas | **0** |
| SQL DML en TEST | **0** |

**LOCAL**

| | |
|---|---|
| Contenedores | **0** (detenidos y eliminados) |
| Volumen `sgpmp_g140_local_pgdata` | **eliminado** |
| Imágenes del laboratorio | **eliminadas** |
| Puerto 55440 | **liberado** |
| Snapshot de `origin/test` | **eliminado** del disco |
| Impacto sobre TEST / DEV / MAIN | **NINGUNO** |

El laboratorio no se reutiliza para otro grupo.

---

## EVIDENCIAS

```
TC-M09-G140/EvaluacionV2/
├── automation/
│   ├── test_g140_test.py              (TC-284 y TC-285 contra TEST — 17 controles)
│   ├── test_g140_local.py             (TC-286 en laboratorio LOCAL — 13 controles)
│   ├── oracle_g140.py                 (oráculo independiente de las tres etapas)
│   ├── docker-compose.g140-local.yml  (definición del laboratorio)
│   └── init-roles.g140-local.sql      (roles que esperan las migraciones)
└── RESULTADOS/
    └── run-20261010-150013/           (RUN LÓGICO VIGENTE — el único)
        ├── TC-M09-G140_reevaluacion_V2.md   (este informe)
        ├── evidencia-test.json
        ├── pytest-test.xml
        ├── evidencia-local.json
        ├── pytest-local.xml
        ├── backend-local.log
        └── automation_manifest.json
```

**Una sola carpeta de resultados.** El §3 del paquete pedía conservar `run-20261010-141449`
como antecedente histórico, y así se hizo durante toda la ejecución: no se modificó ni se
reutilizó como resultado vigente. Terminada la ejecución 3, QA decidió dejar únicamente el
RUN oficial, de modo que esa carpeta y la corrida de diagnóstico
`run-diagnostico-20261010-142600` se eliminaron. Lo que contenían está recogido en este
informe: el 400 `VALOR_NO_PERMITIDO` de la ejecución 1 con su campo del constraint y la
ausencia de persistencia y de auditoría, y la causa raíz que salió del diagnóstico con
`log_statement = 'all'`. Las dos evidencias JSON de este RUN siguen refiriéndose a
`run-20261010-141449` en su `historial_ejecuciones` porque se generaron durante la
ejecución, antes de ese borrado; esas referencias son trazabilidad del resultado anterior,
no rutas a un directorio existente.

No se crearon artefactos `-post-fix`, `-retry`, `-rerun` ni `-final`, ni un informe V3, ni
un RUN adicional. Los scripts no se copian dentro del RUN: el manifest guarda su ruta,
función y SHA-256, con `execution_number_group: 3`.

`backend-local.log` permite seguir la secuencia del laboratorio: el `201 Created` del
lote W1, el `201` de la calibración de control, el `201` del lote W2 y el **`422
Unprocessable Entity`** del POST objetivo, seguido de los GET de verificación.

| Seguridad | |
|---|---|
| Contraseñas / JWT / `Authorization` / cookies / `refresh_token` persistidos | **NO** |
| Serial y `access_key` de las cámaras | **NO** (redactados por patrón, solo en memoria) |
| DSN con contraseña | **NO** (solo la versión sanitizada) |
| `backend-local.log` saneado | **SÍ** (0 coincidencias de secretos) |
| SQL DML en TEST | **0** |
| DML en el laboratorio local | solo la siembra del fixture, autorizada en base local y exclusiva |
| Artefactos de la ejecución 1 y de la corrida de diagnóstico | **ELIMINADOS** por decisión de QA el 2026-10-11, una vez consolidado su contenido en este informe. No se modificó ninguno antes de borrarlo |
| Baseline de la primera evaluación | **NO MODIFICADA** |
| Comandos git de escritura | **NINGUNO** (solo `fetch`, `rev-parse`, `show`, `archive`, `status`, `branch`) |

---

## CONCLUSIÓN

La corrección del PR #550 funciona en la rama que la contiene, y TC-M09-286 lo demuestra en
las cuatro dimensiones que el caso exige: el HTTP contractual (422
`LINEA_BASE_NO_CALCULADA` con el mensaje literal), la trazabilidad (calibración **2** en
estado **NO_CONVERGIDA**, etapa **REFINAMIENTO**, 30/30 observaciones, **1** iteración y el
motivo que declara el agotamiento del máximo), la persistencia correcta (`json_linea_base
IS NULL` = **true**, verificado por SELECT directo en la base local) y la integridad (la
línea base **1** sigue vigente con sus valores intactos, y la NO_CONVERGIDA no se
publicó). El evento RF-10 **3** registra el intento como `fallido` con todo su detalle.

El oráculo independiente había predicho el resultado antes del POST, con el cálculo
congelado en la evidencia: mediana 4.5 → 4.0, cambio relativo **11.1111 %** frente a un
epsilon del **1 %**, y con `max_iteraciones = 1` eso significa no convergencia. El producto
hizo exactamente eso.

Las etapas 1 y 2/3 siguen correctas y sin regresiones. En TC-M09-284 las 10 observaciones
no aptas con valores 100 veces mayores entraron en la ventana —el backend contó 50
observaciones y 40 válidas— y **no movieron la línea base ni un decimal**: `BASE_K` y
`BASE_KM` son idénticas. En TC-M09-285 el dataset discriminaba entre las dos lecturas
admitidas y el producto coincidió componente por componente con **DESCARTE**, con 1
iteración de un máximo de 10.

Una nota sobre cómo se montó TC-286, porque importa para interpretar el resultado: el fix
no está en el working tree de la rama QA, solo en `origin/test`. Si el laboratorio se
hubiera levantado como la primera vez, habría ejecutado el código viejo y el 400 habría
reaparecido por infraestructura, no por el producto. Se construyó desde un snapshot de solo
lectura de `origin/test` fuera del árbol de trabajo, y antes de empezar el caso se verificó
dos veces —el texto del archivo importado y el `none_as_null` efectivo del tipo de
SQLAlchemy— que el backend local corría el fix. `LOCAL_SOURCE_SHA` =
`c4612dae6d8f0601488b94a3635f6592aa640686`.

**TC-M09-G140: APROBADO.** Los tres casos aprueban. `INC-RF24-VISION-NO-EXITOSA` queda
**CORREGIDA**, sin incidencia nueva. Los resultados RECHAZADO de las ejecuciones 1 y 2 se
conservan en el historial de este informe y en `historial_ejecuciones` de las evidencias.

Un detalle que conviene que Desarrollo tenga presente: el fix vive en `origin/test` y la
rama QA no lo tiene. Todo lo que se valide en un laboratorio local a partir de ahora
necesita esa misma precaución, o se estará probando código viejo sin darse cuenta.
