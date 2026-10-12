# Correcciones de flujo alterno — Módulo 9 (Configuration)

Qué se hizo para cerrar los 11 ❌ de `gaps_flujo_alterno_modulo9.md`, por qué se hizo así y
qué cambia para quien consume la API. Rama `fix/gaps-flujo-alterno-m09` → PR a `fix/m09`.

**Sin migración de base de datos.** Ningún cambio toca el esquema: son clases de error,
una validación nueva sobre datos que ya se leían y un `SET LOCAL` por request. No hace
falta autorización de DBA para este PR.

---

## Resumen de una línea por gap

| # | RF | Caso del flujo alterno | Antes | Ahora |
|---|---|---|---|---|
| 1 | RF-17 | Solapamiento de niveles de alerta | 422 | **400** |
| 2 | RF-17 | Error de sincronización con Nodo Edge | no existía | **500** — ya lo había cerrado INC-M09-104-G29 |
| 3 | RF-20 | Tipo de área no reconocido | 422 | **400** |
| 4 | RF-22 | Área productiva inexistente **o inactiva** | 404 / 422 | **404** en ambos |
| 5 | RF-23 | Inconsistencia lógica de tiempos | 400 | **400** — falso positivo de la auditoría |
| 6 | RF-25 | Finca sin especies ni infraestructura | 200 | **204** |
| 7 | RF-25 | Timeout de carga de contexto (>2 s) | 503 / sin límite | **504** |
| 8 | RF-26 | Formato de logo no compatible | 400 | **415** |
| 9 | RF-32 | Incompatibilidad de esquema (legacy) | 412 | **422** |
| 10 | RF-32 | Referencias huérfanas en la plantilla | no se validaba | **400** |
| 11 | RF-32 | Conflicto de modificación concurrente | 412 | **409** |

Dos de los once no costaron trabajo nuevo (#2 y #5). Ver abajo por qué.

---

## Lo que cambia para el frontend

Ocho códigos HTTP cambian en endpoints ya en uso. **Ninguno** cambia el `error_code` de
negocio, así que un cliente que ramifique por `error_code` y no por status no se entera:

| Endpoint | Escenario | Antes → Ahora | `error_code` |
|---|---|---|---|
| `POST /configuracion/umbrales`<br>`PATCH /configuracion/umbrales/{id}` | niveles con hueco o solape | 422 → **400** | `SOLAPAMIENTO_NIVELES` |
| `POST /configuracion/infraestructuras`<br>`PATCH /configuracion/infraestructuras/{id}` | `tipo_area` fuera del catálogo | 422 → **400** | `TIPO_AREA_NO_RECONOCIDO` |
| `POST /configuracion/sensores/{id_sensor}/asociar` | área inactiva | 422 → **404** | `AREA_NO_DISPONIBLE` → `AREA_NO_ENCONTRADA` |
| `GET /configuracion/interfaz/contexto` | finca sin catálogo | 200 → **204** (sin cuerpo) | — |
| `GET /configuracion/interfaz/contexto` | carga > 2 s | 503 → **504** | `TIMEOUT_CONTEXTO_INTERFAZ` |
| `POST /configuracion/identidad-visual`<br>`PATCH /configuracion/identidad-visual/{id_finca}` | logo en formato no admitido | 400 → **415** | `FORMATO_IMAGEN_NO_PERMITIDO` |
| `POST /configuracion/plantillas/{id_plantilla}/aplicar` | snapshot legacy | 412 → **422** | `VERSION_SNAPSHOT_INCOMPATIBLE` |
| `POST /configuracion/plantillas/{id_plantilla}/aplicar` | especie destino modificada | 412 → **409** | `CONFLICTO_CONCURRENCIA` |

Dos avisos que sí requieren tocar el cliente:

- **`204` en el contexto de interfaz.** Un `204` no trae cuerpo: un cliente que haga
  `response.json()` sin mirar el status va a reventar. Solo ocurre cuando el usuario **sí**
  tiene finca pero esa finca no tiene **ni** especies **ni** áreas productivas; el usuario
  *sin* finca sigue recibiendo `200` con `id_finca: null`, que es el otro flujo alterno del
  RF (vista de bienvenida). Son dos pantallas distintas.
- **`AREA_NO_DISPONIBLE` desaparece** del endpoint de asociación de sensores (RF-22). Si el
  frontend lo tiene mapeado a un mensaje propio, ahora llega `AREA_NO_ENCONTRADA`. El código
  sigue existiendo en el registro de dispositivos IoT (RF-21), que no se tocó.

---

## Detalle por caso

### RF-17 — Solapamiento de niveles de alerta: 422 → 400

El RF lo llama "Error de semaforización ... HTTP 400: Bad Request", el mismo trato que le da
a la inconsistencia de rango `min >= max` que ya validaba el DTO en 400. El código lo lanzaba
como `BusinessRuleError`.

La lógica no cambió: los tres niveles siguen teniendo que cubrir exactamente
`[valor_min, valor_max]` sin huecos ni solapes. Solo cambió la clase de error en las tres
ramas de `_validar_rangos`, que registrar y editar comparten — un único punto, los dos
endpoints corregidos.

> `registrar_umbral_use_case.py:63-94`

### RF-17 — Sincronización con el Nodo Edge: ya estaba cerrado

La auditoría lo marcó como "no existe ningún mecanismo". Entre la auditoría y esta corrección
lo cerró **INC-M09-104-G29** (PR #385, ya en `dev`): `EdgeSincronizacionPort` propaga el
umbral post-commit, el estado de sincronización (`APLICADA` / `PENDIENTE` / `NO_CONF`) se
persiste, y el fallo responde 500 `FALLO_SINCRONIZACION_EDGE` como exige el RF. Se verificó
el código y no hizo falta tocar nada.

### RF-20 — Tipo de área no reconocido: 422 → 400

El RF lo clasifica como "Dato inválido ... HTTP 400". Se cambió `BusinessRuleError` por
`ValidationError` en registrar y editar.

**Por qué no bajó al DTO**, que es el camino natural a un 400 en esta arquitectura: el
catálogo de tipos de área es una tabla administrable (`modulo9.tipos_area`) y el propio RF
contempla ampliarla —"Consulte al Administrador para verificar o ampliar el catálogo"—, así
que no es un enum que Pydantic pueda validar sin consultar la DB.

> `registrar_infraestructura_use_case.py:52-65`, `editar_infraestructura_use_case.py:78-91`

### RF-22 — Área inexistente o inactiva: 404 en ambos casos

El RF describe **un** caso con **un** código y **un** mensaje. El código lo partía en dos
ramas (404 si no existe, 422 si está desactivada), de modo que el cliente veía dos contratos
para el mismo escenario del RF. Se unificaron en el 404, con el texto literal del RF.

Este es el único caso del patrón "inexistente o inactivo" que se tocó en todo el módulo. Los
otros nueve RFs que lo presentan están marcados ⚠️, no ❌, y con razón: ahí el RF pide 422 o
404 para ambos y el código acierta en una de las dos ramas. RF-22 va **al revés** que el resto
del módulo —pide 404 y el código daba 422 para la rama de "inactiva"—, que es justo lo que lo
convertía en gap franco. El caso homólogo de RF-21 (registro de dispositivo IoT) **no se
tocó**: ese RF pide 422 para ambos, no 404.

> `asociar_sensor_area_use_case.py:66-80`

### RF-23 — Inconsistencia lógica de tiempos: falso positivo

La auditoría lo marcó "no validado" tras leer `TipoDispositivoIot.verificar_rango`, que en
efecto solo compara cada parámetro contra su propio rango por tipo de hardware. Pero la regla
cruzada (`intervalo_transmision >= frecuencia_captura`) **siempre existió**, en el
`model_validator` del DTO, y ya respondía el 400 que pide el RF.

Lo único que se desviaba era el texto del mensaje, que ahora es el del RF. Se documentó en el
validador por qué la regla vive en el DTO y no en el use case: un `model_validator` sale por
`request_validation_error_handler`, que es el único camino a 400 sin un código de negocio
propio — exactamente lo que el RF pide aquí.

> `configurar_remotamente_dto.py:20-34`

### RF-25 — Finca sin catálogo: 204

El RF define el caso sobre **las dos cosas a la vez**: "no se han registrado especies (RF-15)
**ni** infraestructura (RF-20)". El read-model `ContextoInterfaz` solo sabía de especies, así
que se le sumó `tiene_infraestructura` (un `EXISTS` sobre `modulo9.infraestructuras` activas
de la finca) y la propiedad `finca_sin_catalogo` combina ambas.

Tres casos que **siguen siendo 200**, a propósito:
- finca con áreas pero sin especies,
- finca con especies pero sin áreas,
- usuario sin finca asociada — ese es el otro flujo alterno del RF, el de la vista de
  bienvenida, y tiene su propia pantalla.

La decisión de devolver 204 vive en el router, no en el use case: el código HTTP es contrato
de transporte, no de dominio. El use case sigue devolviendo el contexto completo.

> `contexto_interfaz.py:36-49`, `contexto_interfaz_router.py:49-54`

### RF-25 — Timeout de carga de contexto: 504

El RNF de rendimiento del RF fija "Tiempo de carga ≤ 2 segundos" y el flujo alterno pide 504
cuando se supera. No había ni límite ni mapeo: una BD lenta simplemente tardaba, y una caída
daba 503.

El presupuesto se impone **en el motor**, con `SET LOCAL statement_timeout = 2000` en la
transacción del request, en vez de medir el tiempo después de haberlo gastado. `SET LOCAL`
vive lo que vive la transacción y `get_db` la cierra al terminar, así que no se filtra a
otras peticiones que reusen la conexión del pool.

El repositorio traduce el SQLSTATE **57014** (`query_canceled`) a `GatewayTimeoutError`.
Cualquier otro `OperationalError` se relanza tal cual y sigue saliendo 503 por
`db_no_disponible_handler` — que es lo correcto para una BD caída, y lo que el Patrón 4 de
`gaps_flujo_alterno_patron_transversal.md` documenta como decisión de diseño del backend.

Verificado en vivo contra la BD de dev: con el presupuesto bajado a 50 ms, un `pg_sleep(1)`
sale como 504 `TIMEOUT_CONTEXTO_INTERFAZ`, no como 503.

> `contexto_interfaz_repository.py:17-47`

### RF-26 — Formato de logo no compatible: 400 → 415

El RF pide "HTTP 415: Unsupported Media Type". La validación de contenido ya era de las
mejores del módulo (Pillow real, coherencia entre el contenido y el Content-Type declarado,
rechazo de SVG con script), pero todos los rechazos salían como `ValidationError` → 400.

**Cambio transversal:** `src/shared/errors.py` no tenía ninguna clase para 415. Se agregó
`UnsupportedMediaTypeError`, documentando la frontera contra `ValidationError`: 415 es "este
tipo de archivo no se admite", 400 es "un dato mal formado dentro de un formato que sí se
acepta".

Los cinco rechazos con código `FORMATO_IMAGEN_NO_PERMITIDO` pasan a 415 —son la misma
condición del RF, la detecte el Content-Type declarado o el contenido real— para que un
código de negocio siga mapeando a un solo HTTP. **El límite de 2 MB se queda en 400**: el RF
no le asigna otro código y 413 habría sido inventar contrato.

> `errors.py:159-169`, `almacen_logos.py`

### RF-32 — Incompatibilidad de esquema: 412 → 422

Aquí la auditoría señaló una contradicción entre RFs: RF-30 pide 412 para este escenario y
RF-32 pide 422. La contradicción es menos profunda de lo que parecía — **el caso solo se
materializa al aplicar una plantilla, nunca al crearla**, y la propia auditoría ya había
marcado la fila homóloga de RF-30 como ➖ N/A por eso mismo. Como no queda ningún caso real
gobernado por el 412 de RF-30, se resolvió a favor de RF-32 sin esperar a que Análisis
unifique el corpus.

> `aplicar_plantilla_use_case.py:107-121`

### RF-32 — Referencias huérfanas: 400

Una plantilla guarda un snapshot congelado; nada impide que el catálogo maestro cambie
después. El snapshot se aplicaba directo, así que una referencia caída reventaba más abajo
como violación de FK (409/500) — y lo hacía **después** de haber desactivado ya los ciclos,
métricas, umbrales y patologías de la especie destino.

Ahora se verifica antes de tocar nada, y el rechazo deja la configuración anterior intacta.

**Qué se valida y qué no.** La única referencia del snapshot a un catálogo externo es
`id_variable_ambiental` de cada umbral. Ciclos, métricas y patologías viajan **por valor** y
se recrean bajo la especie destino: `vincular_desde_snapshot` inserta la patología por nombre
bajo `modulo9.especies_patologias`, no resuelve ningún FK contra un catálogo maestro de
patologías — el ejemplo que da el RF ("una patología que fue eliminada del catálogo maestro")
no tiene contraparte en este esquema. El use case recibe `VariableAmbientalRepository` para
hacer la revalidación.

> `aplicar_plantilla_use_case.py::_verificar_referencias`

### RF-32 — Conflicto de modificación concurrente: 412 → 409

El resto del módulo usa 412 para concurrencia optimista, tal como documenta `CLAUDE.md`, y
seguirá haciéndolo. RF-32 pide 409 explícitamente para su caso y es el único RF que gobierna
este endpoint, así que aquí manda su letra. **Es una excepción deliberada y local de un
endpoint, no un cambio de patrón del módulo** — conviene leerlo así antes de "corregirlo" de
vuelta por consistencia.

De paso se adoptó el mensaje del RF y se colapsó la doble rama de comparación de timestamps
en una sola variable, que es lo que ya hacía ilegible ese bloque.

> `aplicar_plantilla_use_case.py:137-158`

---

## Qué NO se tocó, y por qué

- **Los 17 ⚠️ parciales del módulo.** Casi todos son el patrón "inexistente o inactivo"
  (404/422 partido donde el RF pide uno solo). No son gaps de comportamiento: el sistema sí
  bloquea la operación en ambas ramas. Unificarlos habría sido un cambio de contrato en nueve
  RFs a la vez para ganar consistencia de forma, no corrección.
- **El 423 de RF-15** (desactivación bloqueada por proceso crítico, el RF pide 422). Está
  marcado ⚠️ y `LockedError`/423 es semánticamente más preciso que 422 para "bloqueado
  temporalmente".
- **El 405 por omisión de ruta** en RF-21 y RF-30/31. El código HTTP coincide con el RF; que
  salga porque la ruta no existe en vez de por una regla explícita es una observación de la
  auditoría, no un fallo de contrato.
- **Nada del broker MQTT** (`BROKER-MQTT-SGPMP`). Ninguno de los 11 gaps lo requiere: el
  único caso de RF-23 resultó ser un falso positivo y se resuelve en el DTO, antes de que se
  publique nada.

---

## Verificación

- `tests/configuration/test_gaps_flujo_alterno_m09.py` — una prueba por gap contra el texto
  del RF, cada una con su contraejemplo (la configuración válida que debe seguir pasando).
- Suite completa: `776 passed, 199 skipped`. Los 2 fallos de
  `tests/biological_assets/test_registrar_transferencia_use_case.py` son **previos** a esta
  rama y ajenos al Módulo 9 (verificado con `git stash` contra `fix/m09` limpio).
- El 504 de RF-25 y las consultas del contexto se probaron **en vivo** contra la BD de dev,
  no solo con fakes.
- `GET /openapi.json` confirma el contrato publicado: `204` en el contexto, `415` en
  identidad visual, y `400/404/409/422` (ya sin `412`) en aplicar plantilla.
