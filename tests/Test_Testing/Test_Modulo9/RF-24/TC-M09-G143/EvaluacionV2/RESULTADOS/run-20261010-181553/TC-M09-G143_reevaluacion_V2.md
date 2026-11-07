# TC-M09-G143 — SEGUNDA EVALUACIÓN

**RF-24 v2.0 · CU05 Flujo F · Módulo 9 — Auditoría, integridad y control de infraestructura**

| | |
|---|---|
| RUN_ID | `run-20261010-181553` (único; no se creó otro RUN) |
| Ejecución | **2** — `REEJECUCION_COMPLETA_POST_FIX` |
| Casos | TC-M09-290 (TEST), TC-M09-291 (TEST), TC-M09-292 (LOCAL AISLADO) |
| Herramientas | **Newman** ejecutor de los eventos · **Pytest TEST** verificador de solo lectura · **Pytest LOCAL** orquestador del laboratorio |
| Rama QA | `qa/juan-esteban-segunda-evaluacion-rf24-v2.0` |
| HEAD QA | `1e3a3848f23ac514339abbf37a34c26bbfbd0ff8` |
| Referencia backend | `origin/test` `4f09cb6953843cbab06319000c14d1b30feb8a56` |
| POST manual de calibración VISION sobre A1 | **0** · Ingesta M03: **0** |

---

## DECISIÓN GENERAL ACTUAL

| Caso | Resultado vigente |
|---|---|
| **TC-M09-290** | **APROBADO** |
| **TC-M09-291** | **APROBADO** |
| **TC-M09-292** | **APROBADO** |
| **TC-M09-G143** | **APROBADO** |

**Evolución:** `RECHAZADO → APROBADO`

**PR #554 confirmado funcionalmente en TC-290** (disparo automático con datos insuficientes).
**PR #553 confirmado en TC-291**: `detalle.id_especie` ya viaja en los rechazos tempranos y la
observación histórica queda **CORREGIDA**. **Incidencia nueva: NO.**

---

## HISTORIAL DE EJECUCIONES

### EJECUCIÓN 1 — 2026-10-10

| Caso | Resultado |
|---|---|
| TC-M09-290 | **RECHAZADO** |
| TC-M09-291 | **APROBADO con observación** |
| TC-M09-292 | **APROBADO** |
| **TC-M09-G143** | **RECHAZADO** |

* **TC-290:** área 292, cámara 228, especie 78, finca 163, lote 793, alta **201**, 0
  observaciones VISION, **ninguna** calibración automática, línea base 404, **ninguna**
  auditoría RF-10 automática, más de **632 s** de observación. La integración M02→M09 no
  existía en el código de entonces. Se relacionó con la incidencia de G142 y **no** se abrió
  un ticket duplicado.
* **TC-291:** área 293 sin cámaras, POST VISION **422 `VISION_NO_DISPONIBLE`**, auditoría
  evento **48943** (tipo 29, fallido, MODULO9, Ingeniero id 4, IP presente, motivo correcto).
  Único desvío: **`detalle.id_especie = null`** pese a que el área tenía especie 78 — pérdida
  de identificación de la especie en los rechazos tempranos.
* **TC-292:** laboratorio `sgpmp-g143-local` / base `sgpmp_g143_lab` / rol `sgpmp_app_g143`
  sobre `modulo1.eventos`, L1 publicada, `REVOKE INSERT` efectivo, segundo cálculo **500
  `AUDITORIA_CALIBRACION_FALLIDA`**, L1 conservada, L2 no publicada, `GRANT` restaurado y
  laboratorio desmontado.
* Newman: 35 requests · 70 assertions · **4 failures** (3 de TC-290, 1 de la observación de
  TC-291) · 0 fallos de automatización. Pytest TEST 10/10. Pytest LOCAL 12/12.

Esas cifras son **históricas** y no se reutilizan como resultado actual.

### CORRECCIONES DE DESARROLLO

**PR #554** — *disparar la calibración visión automática desde el alta de lote y el cierre de
ciclo de M02.* Introduce `RecalibracionVisionPort`, `RecalibracionVisionM09Adapter` (sobre
`BackgroundTasks`, con sesión propia del usuario de servicio), los hooks en
`RegistrarActivoBiologicoUseCase` y `CerrarCicloUseCase`, y
`CalibrarVisionUseCase.execute_automatico` con `origen_disparo = AUTOMATICO`,
`id_usuario = None` y auditoría firmada por el usuario de servicio. No añade ningún endpoint:
el disparador **no** se busca en OpenAPI, se provoca el evento M02 y se observan sus
consecuencias.

**PR #553** — *auditar la especie del área en los rechazos tempranos de calibración visión.*
Separa la obtención del área de su validación, de modo que la variable del área ya no sigue
siendo `None` cuando se audita un rechazo lanzado dentro de la validación.

**Verificado por lectura en `origin/test` `4f09cb69`** (sin cambiar de rama):

```
execute(): area = self._obtener_area(dto, ids_fincas_permitidas)   ← #553
           observaciones = self._observaciones(area, ...)            ← lanza el rechazo
           except: auditar_rechazo_vision(..., id_especie=area.id_especie if area else None)
def _obtener_area(...)        ← separada de la validación
def execute_automatico(...)   ← #554, con VENTANA_DISPARO_AUTOMATICO = 7 días
_registrar_fallida(): extra={..., "origen_disparo": guardada.origen_disparo.value}
```

Ambos PR **PRESENTES**. `ParametrosLineaBase.min_observaciones` = **30**, sin cambios.

Mergeado no es desplegado: lo que sigue es la comprobación funcional contra TEST.

### EJECUCIÓN 2 — REEJECUCIÓN COMPLETA POST-FIX

| | |
|---|---|
| Fecha/hora | 2026-10-11 06:35–06:45 UTC (2026-10-11 01:35–01:45 −05:00) |
| TC-M09-290 | **APROBADO** |
| TC-M09-291 | **APROBADO** |
| TC-M09-292 | **APROBADO** |
| **TC-M09-G143** | **APROBADO** |

---

## PRECHECK DE AUTOMATIZACIÓN

| Comprobación | Resultado |
|---|---|
| Sintaxis e imports de JS (runner) y Python (los dos Pytest) | **PASS** |
| OpenAPI de TEST: rutas, métodos, campos y respuestas | **PASS** (`rutas_ausentes: []`) |
| `tamano` de auditoría dentro del contrato (máx 50) | **PASS** (se usa 50) |
| Campo real `resultado`; no se asume `exitoso` | **PASS** |
| Tipos de evento resueltos del catálogo | **PASS** — `CALIBRACION_RECHAZADA` **29**, `CALIBRACION_EXITOSA` **30** |
| Guardas de arrays antes de indexar | **PASS** |
| RBAC: Administrador M02 `[1,2,3,4,5]`, infraestructuras `[1,2,3,4]`; Ingeniero sensores `[1,2,3]` | **PASS** |
| Fincas compartidas por los dos actores | **PASS** (`[162, 163]` → elegida **163**) |
| Especie apta | **PASS** (78, densidad 50.0000, 0 métricas obligatorias) |
| La colección es dueña de sus sesiones; el runner no duplica logins ni inyecta tokens | **PASS** (2 logins, no son escrituras) |
| Guarda estática: 0 ingesta M03 y un único POST VISION, obligatoriamente sobre A2 | **PASS** |
| **Newman precheck** | 12 requests · 23 assertions · **0 failures** · **0 escrituras** |
| **AUTOMATION_PRECHECK** | **PASS** |
| **AUTORIZAR_RUN** | **SÍ** |

### Dos trampas del arnés corregidas antes de ejecutar

Ninguna tenía que ver con los casos, y las dos habrían arruinado el RUN:

1. **El sufijo del fixture se derivaba del `RUN_ID`.** Como la política es «mismo RUN, nueva
   ejecución», el nombre del área habría chocado con las áreas 292/293 de la ejecución 1 y la
   creación habría respondido **409**, tumbando todo lo demás en cascada. Ahora el sufijo
   lleva un sello propio de cada ejecución.
2. **El modo `run` abortaba siempre si ya existía el HTML oficial**, lo que obligaba a
   borrarlo a mano en cada reejecución. Ahora la reejecución se declara con
   `G143_SOBRESCRIBIR_OFICIAL=1`; sin esa variable aborta explicando la política.

---

## CUALIFICACIÓN DEL FIXTURE

| Elemento | Valor |
|---|---|
| Finca | **163** (activa, en el alcance de los dos actores) |
| Tipo de área | `Galpón` (del catálogo) |
| Especie | **78** «Aves Edicion Vyapvsmjtr» — activa, `MODELO_AVES`, POBLACIONAL, densidad 50.0000 |
| Métricas obligatorias del lote | **ninguna** (`[]`) |
| **A1_CURRENT** (TC-290) | **310** — activa, con cámara, **sin observaciones** |
| **C1_CURRENT** | **249** — CAMARA, activa, 30 fps, exclusiva de A1 (`dispositivos_a1 = [249]`) |
| **A2_CURRENT** (TC-291) | **311** — activa, **sin ninguna cámara** (`dispositivos_a2 = []`) |
| Sufijo del fixture | `20261011-063539` |

Áreas y cámara **nuevas**. No se reutilizaron las áreas 292/293 ni la cámara 228 de la
ejecución 1. No se tocaron los ciclos 54/11/21 que DBA preparó para G142: **TC-290 no exige
asignar fase ni cerrar el lote**, y el contrato de M02 no los pide para el alta.

---

## TC-M09-290 — DISPARO AUTOMÁTICO SIN OBSERVACIONES

### Snapshots PRE

| | Esperado | Obtenido |
|---|---|---|
| `GET calibraciones-vision?area_id=310` | 200, sin calibraciones | **200, `[]`** |
| `GET linea-base?area_id=310` | 404 | **404** |
| Auditoría previa del área | ninguna | **`[]`** |
| Observaciones VISION de C1 | **0** | **0** (ingesta M03 = 0 en todo el grupo) |
| `T_PRE_290` | — | 2026-10-11T06:36:10.080Z |

La cámara se dejó **activa** a propósito: una cámara inactiva haría que el cálculo
interpretara que VISION no aplica y el caso no se ejercitaría.

### Evento M02

| | Esperado | Obtenido |
|---|---|---|
| Actor | con permiso real en M02 | **Administrador** (recurso 29 con acciones 1–5) |
| `POST /activos-biologicos` | 201 | **201** |
| **ID_LOTE** | — | **807** |
| `tipo_activo` / área / especie | POBLACIONAL / 310 / 78 | **POBLACIONAL / 310 / 78** |
| `T_ALTA` | — | **2026-10-11T06:36:13.530Z** |
| Reintentos | 0 | **0** |

### Disparo automático observado (solo GET)

| | Esperado | Obtenido |
|---|---|---|
| Calibraciones nuevas | exactamente 1 | **1** |
| **AUTO_290_ID** | — | **21** |
| `origen_disparo` | AUTOMATICO | **AUTOMATICO** |
| `id_usuario` de la calibración | null | **null** |
| `estado` | FALLIDA | **FALLIDA** |
| `etapa_fallo` | FILTRADO | **FILTRADO** |
| `motivo` | insuficiencia de datos | **«0 observaciones válidas de 0 en la ventana; el mínimo es 30.»** |
| `linea_base` | null | **null** |
| `n_observaciones` / `n_validas` | 0 / 0 | **0 / 0** |
| `ventana_observacion` | 7 días hasta el evento | **2026-10-04T06:36:12 → 2026-10-11T06:36:12** |
| `observaciones` | relacionado con el lote | **«Disparo automático M02: nuevo lote 807»** |
| `GET linea-base` después | **404** | **404** |

Este es el punto fino del caso y se cumplió: con cámara activa y cero observaciones el
proceso **llega al cálculo** y falla en el FILTRADO con `LINEA_BASE_NO_CALCULADA`. No es
`VISION_NO_DISPONIBLE`, que sería un rechazo previo. No basta con que la línea base sea 404:
lo que se demuestra es el **intento automático fallido y su auditoría**.

### Auditoría RF-10 del intento automático

| Campo | Valor |
|---|---|
| `id_evento` | **50334** |
| `tipo_evento` | **29** `CALIBRACION_RECHAZADA` (resuelto del catálogo) |
| `resultado` | **fallido** |
| `modulo` | **MODULO9** |
| `id_usuario` / `nombre_usuario` | **132 / Servicio Sistema SGPMP** |
| `direccion_ip` | PRESENTE |
| `integridad_ok` | true |
| `fecha_evento` | 2026-10-11T06:36:12.861667Z (22 ms después del cálculo) |
| `detalle.operacion` | **CALIBRACION_VISION** |
| `detalle.origen_disparo` | **AUTOMATICO** |
| `detalle.codigo_http` / `codigo_error` | **422 / LINEA_BASE_NO_CALCULADA** |
| `detalle.id_calibracion_vision` | **21** |
| `detalle.id_infraestructura` / `id_especie` | **310 / 78** |
| `detalle.estado` / `etapa_fallo` | **FALLIDA / FILTRADO** |
| `detalle.motivo_etapa` | «0 observaciones válidas de 0 en la ventana; el mínimo es 30.» |

### Identidad del usuario — divergencia registrada, no resuelta por QA

| Campo | Valor | Lectura |
|---|---|---|
| `calibracion.id_usuario` | **null** | cumple la matriz: la acción es del Sistema |
| `auditoria.id_usuario` | **132** «Servicio Sistema SGPMP» | decisión de implementación |

La matriz redacta «usuario nulo» para el disparo automático. La implementación deja nulo el
`id_usuario` de la **calibración** y firma el evento RF-10 con el **usuario de servicio**,
porque `modulo1.eventos.id_usuario` no admite NULL. Son dos campos distintos. Queda
registrado así, sin modificar artificialmente la auditoría para que aparezca NULL, sin
reprobar el caso por esta decisión técnica y **sin declarar que ambos campos cumplen
literalmente la misma exigencia**. Corresponde contrastarlo con Desarrollo/Análisis.

Tampoco se exige IP de cliente para un evento originado por un proceso automático; la que
aparece es la que el backend registra, y se anota como presente.

**TC-M09-290: APROBADO** — los trece criterios del §19 se cumplen: alta válida, cámara
activa, cero observaciones, intento automático real, calibración FALLIDA en FILTRADO, origen
AUTOMATICO, usuario de calibración nulo, motivo de insuficiencia, línea base no publicada,
auditoría FALLIDO, correlación con el evento M02 (por `id_calibracion_vision`, motivo y
tiempo) y **cero** POST manuales VISION sobre A1.

### Diagnóstico de la integración

| | |
|---|---|
| Referencia analizada | `origin/test 4f09cb69` |
| `hook_en_el_alta_m02` | **PRESENTE** |
| `hook_en_el_cierre_m02` | **PRESENTE** |
| Archivos de M02 que mencionan la recalibración | puerto, adaptador, los dos casos de uso y el router |
| Conclusión | el mecanismo M02 → M09 existe en la referencia desplegada (PR #554) |

Este diagnóstico se corrigió en esta ejecución, y conviene decirlo: antes leía el **working
tree** de la rama QA y llevaba la conclusión escrita a mano («sigue sin existir ningún
mecanismo M02 → M09»). Como ese árbol se quedó sin el PR #554, la primera pasada produjo un
artefacto que se contradecía: el veredicto decía «disparo SÍ» y el diagnóstico, en el mismo
archivo, «hook AUSENTE». Ahora analiza `origin/test`, que es lo que TEST despliega, y deriva
la conclusión de los hallazgos.

---

## TC-M09-291 — RECHAZO MANUAL POR AUSENCIA DE CÁMARA

### Precondición y snapshot PRE

| | Esperado | Obtenido |
|---|---|---|
| A2 | área nueva, activa, AVES, MODELO_AVES, POBLACIONAL | **311** |
| **Cámaras de A2** | **0** | **0** (`dispositivos_a2 = []`) |
| Historial VISION de A2 | sin calibraciones | **`[]`** |
| `GET linea-base` | 404 | **404** |
| `T_PRE_291` | — | 2026-10-11T06:36:30.514Z |

La precondición del caso es la **ausencia de cámara**, no la ausencia de observaciones, y se
verificó por GET.

### POST manual

Actor: **Ingeniero de campo** (`ingeniero@pecuaria.co`), resuelto por su sesión real —
`id_usuario` **4**, «Valentina López Herrera»—, no asumido del histórico. Una sola ejecución,
sin reintento.

| | Esperado | Obtenido |
|---|---|---|
| HTTP | **422** | **422** |
| `error_code` | `VISION_NO_DISPONIBLE` | **`VISION_NO_DISPONIBLE`** |
| `fields` | `area_id` | **`["area_id"]`** |
| Mensaje | contractual vigente | **idéntico** |
| Ventana enviada | ISO-8601 válida y actual | 2026-10-11T00:36:32Z → 2026-10-11T04:36:32Z |

> Calibración por visión no disponible: El área 311 no cuenta con observaciones de cámara
> aptas o no tiene un modelo poblacional asignado. Verifique las cámaras (RF-21/22) y la
> configuración del área (RF-20).

### Auditoría RF-10 del rechazo

Consultada por el Administrador, filtrando por tipo 29, operación `CALIBRACION_VISION`, área
311 y ventana de ±1 minuto alrededor del intento. **Exactamente un** evento correlacionable.

| Campo | Esperado | Obtenido |
|---|---|---|
| `id_evento` | — | **50336** |
| `resultado` | fallido | **fallido** |
| `modulo` | MODULO9 | **MODULO9** |
| `id_usuario` / `nombre_usuario` | el Ingeniero | **4 / Valentina López Herrera** |
| `direccion_ip` | presente | **PRESENTE** |
| `user_agent` | — | PRESENTE |
| `fecha_evento` | dentro de la ventana | **2026-10-11T06:36:31.531190Z — SÍ** |
| `integridad_ok` | — | **true** |
| `categoria` / `estado` | — | MODIFICACION / PROCESADO |
| `detalle.operacion` | CALIBRACION_VISION | **CALIBRACION_VISION** |
| `detalle.id_infraestructura` | 311 | **311** |
| `detalle.codigo_http` / `codigo_error` | 422 / `VISION_NO_DISPONIBLE` | **422 / `VISION_NO_DISPONIBLE`** |
| `detalle.motivo` | el mensaje del rechazo | **idéntico** |
| **`detalle.id_especie`** | **78** | **78** |

La IP no se comparó contra la IP pública de la máquina QA: con proxies o balanceadores por
medio esa comparación no significa nada. Se verificó su presencia y su coherencia con el
contrato.

### Verificación del PR #553

| | Ejecución 1 | Ejecución 2 |
|---|---|---|
| `detalle.id_especie` | **null** | **78** |

**La observación histórica queda CORREGIDA.** El fix está desplegado en TEST y se comprobó
sobre un área nueva, sin cambiar el HTTP esperado ni el mensaje del rechazo.

### Postcondiciones

| | Esperado | Obtenido |
|---|---|---|
| Línea base nueva | no | **404** |
| Calibración EXITOSA | ninguna | **historial total 0** |
| Auditoría FALLIDO | existe | **50336** |

**TC-M09-291: APROBADO**, ya **sin** observación pendiente.

---

## TC-M09-292 — ROLLBACK SI FALLA LA AUDITORÍA

### Fuente del backend local

| | |
|---|---|
| **`LOCAL_SOURCE_SHA`** | **`4f09cb6953843cbab06319000c14d1b30feb8a56`** (= `origin/test`) |
| Mecanismo | `git archive origin/test` → directorio **fuera** del árbol de trabajo → build y volumen `/app` |
| Archivo importado | `/app/src/configuration/application/use_cases/sensores/calibrar_vision_use_case.py` |
| PR #553 (área separada de su validación) | **SÍ** |
| PR #554 (`execute_automatico`) | **SÍ** |
| PR #550 (`none_as_null` efectivo en el tipo de SQLAlchemy) | **SÍ** |
| Veredicto | **PASS** |

El compose monta en `/app` el árbol desde el que se lo invoca, y el working tree de la rama QA
se quedó sin los tres PR. Si el laboratorio se hubiera levantado sobre él, TC-292 habría
validado código viejo sin avisar. Se comprueba sobre el código **realmente importado** —el
texto del archivo y el `none_as_null` del tipo en memoria—, no sobre un `.env` ni una
variable.

### Guarda de aislamiento

| | |
|---|---|
| Host / puerto / base | `db` / `5432` / **`sgpmp_g143_lab`** |
| `current_database` | sgpmp_g143_lab |
| Owner | `postgres` |
| Marcas de `158.69.200.27`, `api.inmero.co`, `sgpmp_test`, `sgpmp_dev` en el compose o el entorno | **NINGUNA** |
| Residuos previos de contenedores o volúmenes | **0** · puerto 55443 libre |
| Veredicto | **PASS** |

No se dio por buena una variable que dijera LOCAL: se consultó el destino real de la conexión.

### Migraciones y roles

| | |
|---|---|
| `alembic upgrade head` | **PASS** — cabeza **`5c2e8a1f7d39`** (*RF-24 v2.0: restaurar la política RLS de UPDATE de lineas_base_vision*) |
| Tablas | `modulo1.eventos`, `modulo3.observaciones_vision`, `modulo9.calibraciones_vision`, `modulo9.lineas_base_vision` **presentes** |
| Rol propietario | `postgres` |
| **Rol de aplicación** | **`sgpmp_app_g143`** — `rolsuper false`, `rolcanlogin true`, `rolcreatedb false`, `rolcreaterole false` |
| Owner de `modulo1.eventos` | `postgres` → el rol de aplicación **no** es owner |
| `INSERT` inicial | **true** |

La cabeza de Alembic **no** es la histórica `00c60ae92735`: se resolvió del código actual, como
pedía el §28.

Sobre `BYPASSRLS`: el rol de aplicación lo lleva a propósito, porque el laboratorio mide
privilegios **de tabla**, no políticas de fila, y queda documentado. No sustituye a una
configuración de permisos válida: la prueba demuestra una revocación efectiva del privilegio
`INSERT` de tabla, verificada antes y durante.

### Fixture local y control positivo L1

| | |
|---|---|
| Origen | sintético, sembrado por SQL en la base local y exclusiva |
| Finca / área / especie | 1 / 1 / 12 — `MODELO_AVES`, POBLACIONAL |
| Cámara | 1 — CAMARA, activa, 30 fps |
| Ingeniero local | usuario 4, `ingeniero.g143.lab@laboratorio-g143.co` |
| `N` | **30** (`ParametrosLineaBase.min_observaciones`) |

| Control positivo | Esperado | Obtenido |
|---|---|---|
| Ventana W1 | 2026-07-01T00:00 → 06:00Z | ✔ |
| Lote de observaciones | 30 aptas, 0 duplicadas | **30 / 30 / 0**, índices 100 |
| Vectores | — | `densidad 10.0`, `tasa 5.0` |
| HTTP | 2xx | **201** |
| `estado` | EXITOSA | **EXITOSA** |
| **`L1_CALIBRACION_ID`** | — | **1** |
| **`L1_VALORES`** | — | **`{densidad_actividad: 10.01, tasa_movimiento: 5.01}`** |
| `GET linea-base` | apunta a L1 | **200 → 1** |
| Línea base en BD | L1 | **1** |
| Auditoría EXITOSA | existe | **1 evento VISION** |

El control positivo pasó, así que la conservación de L1 es comprobable: no se puede verificar
que L1 se conserve si L1 nunca existió.

### Ventana W2

| | |
|---|---|
| Ventana | 2026-07-10T00:00 → 06:00Z, **disjunta** de W1 |
| Lote | **30 / 30 / 0 duplicadas**, 30 aptas |
| Vectores | `densidad 25.0`, `tasa 9.0` — **distintos** de W1 a propósito |
| Elegibilidad | produciría una L2 distinguible de L1 |

### Snapshot PRE

| | |
|---|---|
| Línea base por API | 200 → **1** |
| Historial por API | `[1]` |
| Calibraciones en BD | `[{1, EXITOSA}]` |
| Línea base en BD | `{id_linea_base_vision 1, id_calibracion_vision 1, valores 10.01/5.01}` |
| Eventos VISION en BD | **1** |

La comparación posterior se hizo contra estos datos congelados, no contra valores recordados.

### Inyección del fallo

| | |
|---|---|
| Sentencia | `REVOKE INSERT ON TABLE modulo1.eventos FROM sgpmp_app_g143` |
| Ejecutada por | el **owner**, nunca el backend |
| `INSERT` PRE | **true** |
| `INSERT` DURANTE | **false** |
| Backend conectado como | **`sgpmp_app_g143`** (verificado desde su propia DSN) |

La denegación fue real: si el rol hubiera conservado `INSERT` por otro grant o privilegio
efectivo, la inyección sería inválida y el POST objetivo no se habría ejecutado.

### POST objetivo

Una sola vez, como Ingeniero local, con la ventana W2.

| | Obtenido |
|---|---|
| HTTP | **500** |
| `error_code` | **`AUDITORIA_CALIBRACION_FALLIDA`** |
| Mensaje | «Error de integridad: No se pudo garantizar la trazabilidad de la calibración. El ajuste no ha sido aplicado; por favor, intente de nuevo.» |
| Informa fallo de trazabilidad | **SÍ** |

La ficha de RF-24 no fija el HTTP exacto para esta variante VISION, así que se registra el
código obtenido sin inventar un requisito contractual nuevo: el criterio central es la
integridad y el rollback.

### Restauración

| | |
|---|---|
| Sentencia | `GRANT INSERT ON TABLE modulo1.eventos TO sgpmp_app_g143` |
| Garantía | `try/finally` — se ejecuta pase lo que pase con el POST o las assertions |
| `INSERT` POST | **true** |

### Postcondiciones de rollback

| Criterio | Esperado | Obtenido |
|---|---|---|
| `L1_FINAL_ID == L1_PRE_ID` | SÍ | **1 == 1** |
| Valores de L1 | iguales | **`{10.01, 5.01}`** idénticos |
| L2 publicada | NO | **NO** |
| Calibración W2 confirmada | NO | **NO** |
| Historial | igual | **PRE `[1]` → POST `[1]`** |
| Eventos VISION | sin éxito falso para W2 | **1 → 1** |
| BD PRE vs POST | idénticas | **idénticas** (calibraciones, línea base y eventos) |
| `INSERT` restaurado | true | **true** |

No se exige un evento RF-10 FALLIDO de W2: la escritura de auditoría es precisamente el
recurso que se denegó.

**TC-M09-292: APROBADO.**

### Desmontaje

| | |
|---|---|
| Contenedores del laboratorio | **0** |
| Volumen `sgpmp_g143_local_pgdata` | **eliminado** |
| Imágenes del laboratorio | **eliminadas** |
| Snapshot de `origin/test` | **eliminado** del disco |
| Impacto sobre TEST / DEV / MAIN | **NINGUNO** |

---

## BD TEST COMPLEMENTARIA

| | |
|---|---|
| Rol en la matriz | evidencia **complementaria**; no es compuerta |
| Usuario | `member_qa`, sesión **READ ONLY** · DML **0** |
| `modulo3.observaciones_vision` / `modulo9.calibraciones_vision` / `modulo9.lineas_base_vision` | **sin SELECT** |
| `modulo1.eventos` | **con SELECT** |
| **`BD_TEST_COMPLEMENTARIA`** | **NO DISPONIBLE POR PERMISOS** (para las tablas VISION) |

No se intentó escalar privilegios ni modificar políticas RLS. Las postcondiciones se
comprobaron por API, y en el informe no se presenta ninguna lectura de API como si fuera un
SELECT.

---

## RESULTADO NEWMAN ACTUAL

| | |
|---|---|
| Requests | **35** |
| Assertions | **90** |
| Failures | **0** |
| Script errors | **0** |
| Failures de producto | **0** |
| Failures de automatización | **0** |
| Presupuesto | alta M02 **1** · POST VISION **1** (solo A2) · **ingesta M03 0** · GET 27 · PATCH restauración 1 · logins 2 · reintentos **0** |
| HTML | `newman/newman-TC-M09-G143.html` |

Las assertions de TC-290 se reforzaron al contrato completo antes de ejecutar: en la ejecución
1 solo comprobaban que apareciera una calibración AUTOMATICO sin usuario, y ahora exigen
además `estado FALLIDA`, `etapa_fallo FILTRADO`, `linea_base` nula, el motivo de
insuficiencia, área y especie, cero observaciones válidas, una sola calibración por evento, y
en la auditoría el tipo del catálogo, `resultado fallido`, `modulo`, `origen_disparo`,
`codigo_error`, `codigo_http`, `id_especie`, `estado`, `etapa_fallo`, `motivo_etapa` y la
correlación por `id_calibracion_vision`. Las 20 assertions nuevas salen de ahí.

## RESULTADO PYTEST TEST

| | |
|---|---|
| Collected | **10** · Passed **10** · Failed **0** · Skipped **0** · Errors **0** |
| POST funcionales emitidos | **0** (alta 0, calibración 0, telemetría 0, fixtures 0) |
| Archivo | `pytest-test.xml` |

Dos defectos propios aparecieron y se corrigieron durante esta ejecución, los dos del arnés y
ninguno del producto:

* **El veredicto de TC-290 solo recalculaba**, sin comprobar el contrato: con el disparo
  funcionando o roto habría dado el mismo `10 passed`. Ahora afirma todo lo descrito arriba y
  falla si algo no se cumple.
* **El registro de auditoría del verificador podaba el detalle** y descartaba
  `id_calibracion_vision`, `origen_disparo`, `estado` y `etapa_fallo`, de modo que la primera
  pasada reforzada falló diciendo que no había evento correlacionado con la calibración 21,
  cuando Newman ya lo había encontrado. Era el registro, no el producto.

## RESULTADO PYTEST LOCAL

| | |
|---|---|
| Collected | **13** · Passed **13** · Failed **0** · Skipped **0** · Errors **0** |
| Archivo | `pytest-local.xml` |

El control número 13 es nuevo: `test_01b_fuente_del_backend_local`, que verifica y traza qué
código corre el laboratorio.

---

## COMPARACIÓN EJECUCIÓN 1 VS EJECUCIÓN 2

| Criterio | Ejecución 1 | Ejecución 2 |
|---|---|---|
| TC-290 alta M02 | 201 (lote 793) | **201 (lote 807)** |
| TC-290 observaciones | 0 | **0** |
| TC-290 calibración automática | **ninguna** | **21** |
| TC-290 `origen_disparo` | — | **AUTOMATICO** |
| TC-290 `id_usuario` calibración | — | **null** |
| TC-290 estado / etapa | — | **FALLIDA / FILTRADO** |
| TC-290 línea base | 404 | **404** (correcto: no se publica) |
| TC-290 auditoría FALLIDO | **ninguna** | **50334** |
| TC-290 resultado | **RECHAZADO** | **APROBADO** |
| TC-291 HTTP / error | 422 / `VISION_NO_DISPONIBLE` | **422 / `VISION_NO_DISPONIBLE`** |
| TC-291 auditoría | 48943 | **50336** |
| TC-291 `detalle.id_especie` | **null** | **78** |
| TC-291 resultado | APROBADO **con observación** | **APROBADO** |
| TC-292 rollback | APROBADO | **APROBADO** |
| TC-292 cabeza Alembic | `00c60ae92735` | **`5c2e8a1f7d39`** |
| Newman | 35 / 70 / **4 failures** | **35 / 90 / 0 failures** |
| Pytest TEST | 10 / 10 | **10 / 10** (con assertions de contrato) |
| Pytest LOCAL | 12 / 12 | **13 / 13** |
| **TC-M09-G143** | **RECHAZADO** | **APROBADO** |

---

## ESTADO DE INCIDENCIAS

| Incidencia | Estado |
|---|---|
| Integración M02 → M09 (compartida con G142) | **CORREGIDA.** Ya la cerró la reejecución de TC-M09-G142 (RUN `run-20261010-173402`, ejecución 2), que aprobó sus dos casos: TC-M09-288 (alta → calibración automática 19) y TC-M09-289 (cierre de ciclo → calibración automática 20). TC-290 **añade** una tercera demostración del mismo disparador, la del alta con datos insuficientes, y no deja nada pendiente |
| `detalle.id_especie` nulo en rechazos tempranos (PR #553) | **CORREGIDA** y verificada en TC-291 |
| Integridad transaccional de la publicación de línea base | **sin incidencia**: el rollback funciona |
| **Incidencia nueva** | **NO** |

Queda **un punto abierto que no es un defecto y no se resuelve desde QA**: la divergencia
entre la redacción matricial («usuario nulo» para el disparo automático) y la implementación,
que deja nulo el `id_usuario` de la calibración y firma el evento RF-10 con el usuario de
servicio porque `modulo1.eventos.id_usuario` no admite NULL. Para contraste con
Desarrollo/Análisis. Clasificación propuesta: **question**, severity **Minor**, priority
**Low**.

---

## RESTAURACIÓN

**TEST**

| | |
|---|---|
| Cámara **249** desactivada por API | **HTTP 200** |
| Áreas 310 y 311 | conservadas — RF-20 no publica eliminación; quedan como dato QA trazable |
| Lote 807 | conservado |
| Calibración 21, auditorías 50334 y 50336 | **conservadas** (evidencia) |
| SQL DML en TEST por QA | **0** |

**LOCAL**: laboratorio desmontado por completo (contenedores, volumen, imágenes y snapshot).

---

## EVIDENCIAS

```
TC-M09-G143/EvaluacionV2/
├── automation/
│   ├── TC-M09-G143.postman_collection.json         (ejecutor de TC-290 y TC-291)
│   ├── TC-M09-G143.precheck.postman_collection.json
│   ├── run-g143-v2.cjs                             (runner + guardas estáticas)
│   ├── test_g143_test.py                           (verificador TEST, solo lectura)
│   ├── test_g143_local.py                          (orquestador LOCAL de TC-292)
│   ├── docker-compose.g143-local.yml
│   └── init-roles.g143-local.sql
└── RESULTADOS/
    └── run-20261010-181553/
        ├── TC-M09-G143_reevaluacion_V2.md          (este informe)
        ├── evidencia-test.json
        ├── evidencia-local.json
        ├── newman-resumen.json
        ├── pytest-test.xml
        ├── pytest-local.xml
        ├── backend-local.log
        ├── automation_manifest.json
        └── newman/newman-TC-M09-G143.html
```

No se creó otro RUN, ni informe V3, ni artefactos `post-fix`, `retry` o `final`. No se tocó
ningún archivo de G139, G140 ni G142.

| Seguridad | |
|---|---|
| Contraseñas / JWT / Bearer / `Authorization` / cookies / `refresh_token` persistidos | **NO** |
| Serial y `access_key` de la cámara | **NO** (redactados por patrón) |
| DSN con contraseña | **NO** (solo versiones sanitizadas) |
| Credenciales de PostgreSQL | **NO** (llegan por entorno al proceso) |
| Coincidencias de secretos en el RUN | **0** (verificado por grep) |
| GRANT/REVOKE en TEST o DEV | **NINGUNO** (solo en la base local y exclusiva) |
| Comandos git de escritura | **NINGUNO** (solo `fetch`, `rev-parse`, `show`, `grep`, `archive`, `status`, `branch`) |

---

## CONCLUSIÓN

Los tres casos del grupo aprueban, y los dos que dependían de correcciones lo hacen por la
razón correcta.

**TC-290 es el resultado que cambia.** El alta del lote **807** en un área con cámara activa y
**cero** observaciones provocó, sin ninguna llamada manual, la calibración **21**: origen
**AUTOMATICO**, `id_usuario` nulo, estado **FALLIDA** en etapa **FILTRADO**, motivo «0
observaciones válidas de 0 en la ventana; el mínimo es 30.», sin publicar línea base —el área
sigue en 404— y con el evento RF-10 **50334** que registra `LINEA_BASE_NO_CALCULADA`, origen
AUTOMATICO, la especie 78 y la propia calibración. Es el escenario fino del caso: con la
cámara activa el proceso **llega al cálculo** y falla por datos insuficientes, en lugar de
quedarse en un `VISION_NO_DISPONIBLE` previo.

**TC-291 pierde su observación.** `detalle.id_especie` pasó de `null` a **78** sobre un área
nueva, con el mismo 422 y el mismo mensaje contractual de antes. El PR #553 está desplegado y
funciona.

**TC-292 sigue sosteniéndose**, ahora sobre la referencia desplegada: con el backend conectado
como un rol que no es superusuario ni dueño de `modulo1.eventos`, el `REVOKE INSERT` fue una
denegación real —verificada en `false` antes de disparar— y el segundo cálculo respondió 500
`AUDITORIA_CALIBRACION_FALLIDA` sin aplicar nada: L1 siguió vigente con sus valores intactos,
no apareció L2, no quedó la calibración de W2 y la base quedó idéntica evento por evento. El
`GRANT` se restauró en `try/finally`.

Tres cosas que conviene no pasar por alto. La primera: el arnés traía dos trampas ajenas a los
casos —el sufijo derivado del `RUN_ID` y la guarda que bloqueaba toda reejecución— que se
corrigieron antes de ejecutar. La segunda: el verificador de Pytest de TC-290 solo recalculaba
el veredicto, así que habría dado `10 passed` tanto con el disparo funcionando como roto;
ahora comprueba el contrato y falla si no se cumple. La tercera: su diagnóstico de integración
leía el working tree de la rama QA, que no tiene el PR #554, y llevaba la conclusión escrita a
mano; produjo un artefacto que se contradecía a sí mismo antes de que lo corrigiera para leer
`origin/test`.

**TC-M09-G143: APROBADO.** Sin incidencia nueva. El resultado RECHAZADO de la ejecución 1 se
conserva íntegro en el historial de este informe, junto con la observación de TC-291 que ahora
queda cerrada.
