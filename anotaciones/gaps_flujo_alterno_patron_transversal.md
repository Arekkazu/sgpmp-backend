# Patrones Transversales — Flujo Alterno (Módulos 1, 9, 2)

Síntesis de los tres audits de solo lectura (`anotaciones/modulo_1/gaps_flujo_alterno_modulo1.md`,
`anotaciones/modulo_9/gaps_flujo_alterno_modulo9.md`, `anotaciones/modulo_2/gaps_flujo_alterno_modulo2.md`).
> **Estado (2026-09-23):** están corregidos los 9 ❌ del Módulo 1 (rama `fix/gaps-flujo-alterno-m01`),
> los 11 ❌ del Módulo 9 (rama `fix/gaps-flujo-alterno-m09`) y 16 de los 18 ❌ del Módulo 2, más sus
> 4 ⚠️ (rama `fix/gaps-flujo-alterno-m02`). Este documento conserva el diagnóstico estructural
> completo; las menciones ya resueltas se anotan con **(corregido)**. **Lo único abierto en los tres
> módulos es M2·RF-52 E3 y E5** (ver Patrón 5). Los ⚠️ de M9 se dejaron deliberadamente como están:
> ver la nota al final del Patrón 2.

No es un cuarto listado de gaps por RF — es la lectura arquitectónica de por qué los mismos tipos
de gap aparecen repetidos en los tres módulos, cada uno implementado por equipos/PRs distintos, sin
que compartan código entre sí. Eso descarta que sea casualidad: es un patrón de cómo el equipo
interpreta "regla de negocio" vs. "validación de formato" al escribir un endpoint nuevo.

---

## Patrón 1 — La capa que valida no coincide con la clasificación del RF (400 vs 422/403)

**Causa raíz:** en este backend, un `@field_validator` de Pydantic en el DTO SIEMPRE termina en
`HTTP 400` vía `request_validation_error_handler` (`src/shared/error_handlers.py`) — sin importar
qué tan "de negocio" sea la regla que ese validator implementa. Un `BusinessRuleError`/`FlowError`
lanzado **dentro del use case** da `422`. La elección de dónde vive la validación —DTO o
use case— determina el HTTP final, y esa elección no siempre coincide con lo que el RF pide.

Cuando el equipo lo hace bien, lo documenta explícito en el código. Ejemplo en Módulo 2
(`registro/registrar_activo_use_case.py`, comentario en `_validar_origen_financiero`):

> *"vive aquí ... para que el rechazo sea BusinessRuleError -> 422, como exige el RF, y no un 400
> genérico de RequestValidationError"*

Ese comentario existe en RF-33 y RF-48 de Módulo 2 — y esos dos RF, junto con RF-34/45/49, son
justamente los que auditan en cero gaps de código HTTP.

**El patrón es bidireccional** — no siempre falta subir de 400 a 422; a veces sobra:

| Dirección | Dónde aparece | Ejemplo |
|---|---|---|
| DTO/Pydantic → 400, RF pide 422/403 (falta subir) | M1 RF-05 **(corregido)** | Escalada de privilegios (`extra="forbid"` en `EditarPerfilDTO`) rechazaba con 400 genérico de Pydantic antes de que el use case pudiera auditar el intento o lanzar `AuthorizationError`→403. El fix: declarar los campos críticos en el DTO propio para que el rechazo lo haga el use case |
| | M2 RF-40/41/42 (vía `_event_validations.py::validar_fecha_evento`, compartida) **(corregido)** | Fecha de evento inválida daba 422, RF pide 400 — aquí era al revés: **el use case subía a 422 algo que el RF llama validación básica (400)**. Un solo cambio de clase de error en la función compartida corrigió los tres RF |
| | M2 RF-44 **(corregido)** | Fecha futura / motivo vacío → 400 (Pydantic), RF pide 422. Las dos reglas, y el rechazo de CERRADO/BAJA (E-07), pasaron del DTO al use case; el DTO solo rechaza un estado que no existe |
| | M2 RF-46 **(corregido)** | Filtro de fecha inicio>fin → 400 (Pydantic), RF pide 422. El `model_validator` salió del DTO y el use case lo rechaza antes de cualquier consulta, como pide el RF |
| Use case/BusinessRuleError → 422, RF pide 400 (sobra) | M9 RF-17 **(corregido)** | Solapamiento de niveles de alerta → 422, RF pide 400. El fix fue literalmente cambiar `BusinessRuleError` por `ValidationError` en `_validar_rangos`, que registrar y editar comparten |
| | M9 RF-20 **(corregido)** | Tipo de área no reconocido → 422, RF pide 400. La validación se quedó en el use case: el catálogo de tipos es tabla administrable, no enum, así que no puede bajar al DTO |
| | M2 RF-43 (caso inverso al de RF-40/41/42) **(corregido)** | 3 de 9 casos (fecha, cantidad, unidad) usaban `ValidationError`(400) donde el propio RF-43 etiqueta "Error de validación — HTTP 422". La cantidad ≤ 0 además salió del DTO |
| Código HTTP de familia distinta a la esperada | M9 RF-26 **(corregido)** | Formato de imagen inválido → 400, RF pide 415. Requirió agregar `UnsupportedMediaTypeError` a `src/shared/errors.py`: la jerarquía compartida no tenía ninguna clase para 415 |

**Lectura para quien corrija esto después:** no hay una regla global "subir todo a 422" ni "bajar
todo a 400" — cada RF define su propia semántica y dos RFs del mismo módulo (RF-40/41/42 vs RF-43
en M2) la definen en direcciones opuestas para el mismo tipo de caso (fecha inválida). Cualquier fix
tiene que ir caso por caso contra el texto del RF, no por convención de capa.

---

## Patrón 2 — "Inexistente o inactivo" es un solo caso en el RF, dos códigos en el código

Cuando el RF describe un único caso de flujo alterno ("recurso X inexistente **o** inactivo" → un
solo HTTP), el código casi siempre lo separa en dos ramas reales: `NotFoundError`(404) si el
registro no existe, `BusinessRuleError`(422) si existe pero está desactivado. Es consistente en casi
todo Módulo 9 — **9 de sus 17 RFs auditables** lo presentan (RF-15, RF-19, RF-20, RF-21, RF-22,
RF-23, RF-25, RF-30, RF-31, RF-32) — y aparece también en Módulo 1 (RF-05, correo de cuenta
ELIMINADA sigue bloqueando el registro como si estuviera activa; ese sub-caso sigue abierto porque
liberarlo exige índice único parcial, migración y decisión de negocio sobre reutilizar el correo de
una cuenta eliminada).

No es un bug de "la regla no se aplica" — en todos los casos el sistema **sí** bloquea la
operación, solo que con dos HTTP distintos en vez de uno. La dirección del mismatch varía:

- La mayoría de los RFs de M9 piden el mismo código para ambos sub-casos y el sistema los separa
  (⚠️ parcial en la mitad del caso).
- M9 RF-22 (área productiva inexistente/inactiva) va al revés de lo esperado: el RF pide 404 para
  ambos, el código da 422 para "inactiva" — ahí sí era un ❌ franco, no solo un split. **(corregido:
  las dos ramas responden 404 con el mensaje del RF.)**

**Por qué los ⚠️ de M9 se dejaron intactos al corregir el módulo:** son exactamente esto —el mismo
split, con el sistema bloqueando bien la operación en ambas ramas— y no un fallo de comportamiento.
Tocarlos habría sido un cambio de contrato de nueve RFs a la vez, para ganar consistencia de forma y
no corrección. Solo se corrigió RF-22, que la auditoría marcó ❌ precisamente porque va en la
dirección contraria al resto del módulo.

**Causa raíz probable:** `NotFoundError` es el resultado natural de un `repo.obtener_by_id()` que
devuelve `None`; `BusinessRuleError` es el resultado natural de validar `entidad.estado == activo`
una vez que la entidad ya se obtuvo. Son dos líneas de código consecutivas casi siempre escritas por
la misma persona en el mismo use case — el patrón se repite porque es la forma más natural de
escribir la validación en Python, no por descuido puntual.

---

## Patrón 3 — Concurrencia optimista: el propio corpus de RFs no es consistente entre sí

`PreconditionFailedError` (412) es el mecanismo estándar de concurrencia optimista documentado en
`CLAUDE.md` y aplicado de forma idéntica en los tres módulos (`fecha_actualizacion` /
`version_perfil`). Cuando el RF llama a este caso "conflicto de edición/actualización concurrente",
el código da 412 y coincide (M1 RF-05, M9 RF-15/18/20/23).

El problema aparece en Módulo 9 cuando dos RFs sobre el **mismo tipo de operación** (aplicar una
plantilla de configuración) piden HTTP distintos para el mismo escenario:

- **RF-30** (creación/gestión de plantillas): "incompatibilidad de versión de esquema" → 412.
- **RF-32** (aplicación de plantilla): el mismo escenario de incompatibilidad de esquema → **422**;
  y el conflicto de modificación concurrente propiamente dicho → **409**, no 412.

El código implementó el patrón 412 de forma consistente con RF-30 y con el resto del módulo, pero
eso lo dejaba en gap contra la letra de RF-32.

**Cómo se resolvió (2026-09-22):** a favor de RF-32, pero **solo en el endpoint de aplicación**. La
contradicción es menos profunda de lo que parecía: el caso de incompatibilidad de esquema no se
materializa al *crear* una plantilla, únicamente al *aplicarla* —la propia auditoría ya había
marcado la fila homóloga de RF-30 como ➖ N/A por eso—, así que no queda ningún caso real gobernado
por el 412 de RF-30. El resto del módulo conserva 412 para concurrencia optimista, tal como
documenta `CLAUDE.md`; esta es una excepción deliberada y local de un endpoint, no un cambio de
patrón. Si Análisis llega a unificar el corpus, lo que hay que revisar es el texto de RF-32, no
volver a tocar el código.

---

## Patrón 4 — Decisión de diseño sistémica que ningún RF anticipó: BD caída = 503, no 500

En los tres módulos, una caída de conectividad a PostgreSQL se traduce siempre a `HTTP 503` vía
`db_no_disponible_handler` (`src/shared/error_handlers.py`), aplicado globalmente sin importar el
endpoint. Varios RFs (M1 RF-13, por ejemplo) piden literalmente `500` para ese escenario.

Semánticamente 503 es más correcto que 500 para "el servicio de datos no está disponible" — es una
decisión de diseño consistente en todo el backend, no un descuido por módulo. Se documenta aquí para
que no se lea como 3 gaps independientes: es 1 decisión aplicada 3+ veces.

---

## Patrón 5 — Funcionalidad genuinamente ausente (no es cuestión de código HTTP)

Estos no son mismatches de HTTP con lógica correcta debajo — es lógica que el RF pide y que no
existe en ningún punto del código, por lo que ni siquiera hay un HTTP "equivocado" que reportar:

| Módulo | RF | Qué falta |
|---|---|---|
| M1 | RF-01 **(corregido)** | El caso "SMTP falla 3 veces → 503" era arquitectónicamente irreproducible: el correo se agendaba con `BackgroundTasks` **después** del `201`. Ahora se despacha dentro del request con `NotificacionService` y el fallo del canal EMAIL se traduce a 503 |
| M1 | RF-11 **(corregido)** | No existía ningún `410 Gone` por eliminación lógica concurrente. Ahora `EditarPerfilUseCase` lo emite cuando la cuenta objetivo está en ELIMINADO |
| M9 | RF-17 **(corregido)** | No existía notificación/sincronización a nodos Edge al guardar un umbral. Lo cerró INC-M09-104-G29 (PR #385) entre la auditoría y la corrección del módulo: `EdgeSincronizacionPort` propaga post-commit y el estado de sincronización se persiste |
| M9 | RF-25 **(corregido)** | Nunca devolvía `204` para una finca sin catálogo (siempre `200`) ni `504` por timeout. El 204 exigió sumar `tiene_infraestructura` al read-model —el RF lo define sobre especies **e** infraestructura a la vez—; el 504 se impone de verdad con `SET LOCAL statement_timeout = 2000` y la traducción del SQLSTATE `57014`, no midiendo después de esperar de más |
| M9 | RF-32 **(corregido)** | El snapshot se aplicaba sin revalidar sus referencias: una variable ambiental eliminada reventaba abajo como violación de FK, y después de haber desactivado ya la configuración de la especie destino. Ahora se verifica antes de tocar nada |
| M2 | RF-49 **(corregido)** | No había validación de compatibilidad de especie sensor↔activo ni aviso de dispositivo desconectado. Los dos los cerraron PRs posteriores a la auditoría (#354 y #377) antes de corregir el módulo: la auditoría quedó desactualizada, no hizo falta tocar código |
| M2 | RF-50 / RF-51 **(corregido)** | No había detección de valores físicamente imposibles. RF-51 ya detectaba el outlier de ganancia de peso (PR #271), pero lo respondía con el 422 genérico: ahora da 500, y la división por cero da 409, con una `causa_no_disponible` explícita en el indicador. RF-50 cancela la exportación (500) si una métrica es negativa. El 422 de NIC 41 de RF-50 ya lo había cerrado el PR #424 |
| M2 | RF-52 E1/E2 **(corregido)** | El flag `registro_incompleto` existía de punta a punta pero nada lo activaba. Ahora el repositorio, único punto por el que pasan todos los emisores, persiste el evento marcado y con la causa, sin rechazarlo. El archivo de fallback se volvió un buffer que se recupera en orden cronológico al volver la bitácora y deja registrado el periodo de indisponibilidad |
| M2 | RF-52 E3/E5 **(abierto)** | Falta la cola con prioridad bajo alta carga (E3) y la reconciliación RF-46↔RF-52 (E5). No son solo código: E3 necesita que Análisis defina qué es "alta carga" (y decidir si la bitácora pasa a ser asíncrona, como pide la restricción 3 del RF); E5 necesita una llave de cruce que hoy no existe, porque ninguna entrada de la bitácora guarda el `id_evento` que registró |

Estos son los hallazgos de mayor severidad real de toda la auditoría: en el Patrón 1/2/3 el sistema
sí aplica la regla y solo falla el código HTTP; aquí la regla de negocio no se aplica en absoluto.
Tras corregir los tres módulos, de este patrón solo quedan M2·RF-52 E3 y E5.

---

## Patrón 6 (positivo) — Lo que SÍ está resuelto de forma uniforme en los tres módulos

Vale la pena registrarlo porque explica por qué la mayoría de los RFs de RBAC salen ✅ sin
excepción en los tres audits:

- **RBAC vía `require_permission` en el router**, nunca en el use case, tal como exige `CLAUDE.md`
  — verificado en vivo contra `modulo1.permisos` en M9 y M1, sin una sola desviación encontrada en
  los tres módulos.
- **Comentarios en código que citan el RF explícitamente** cuando la validación vive en el lugar
  correcto (M2 RF-33/45/48/49, M9 RF-24) — son los mismos RF que después auditan en cero gaps. La
  correlación sugiere que cuando el desarrollador tuvo el texto del RF a la vista al escribir el
  use case, el HTTP terminó coincidiendo; cuando no, no.
- **Auditoría bloqueante antes de negar acceso** (M1 RF-10/RF-12, M2 RF-52-E4): el sistema registra
  el intento denegado en la bitácora *antes* de devolver el 403, patrón repetido igual en ambos
  módulos sin coordinación aparente entre equipos.

---

## Resumen para priorizar (si en algún momento se decide corregir)

1. **Más barato de arreglar, más ruido en QA:** Patrón 1 y 2. Son cambios de una línea (qué
   excepción se lanza) en use cases ya escritos y probados en su lógica — el fix no toca reglas de
   negocio, solo la clase de error. *Confirmado dos veces: los cinco casos de M1 (RF-01 token,
   RF-03, RF-06 ×2 y RF-14) y los cuatro de M9 (RF-17, RF-20, RF-22, RF-26) fueron exactamente eso.
   La única excepción fue RF-26, que además necesitó una clase nueva en la jerarquía compartida
   porque 415 no existía en ella.*
2. **Requiere alinear el propio corpus de RFs primero:** Patrón 3 (RF-30 vs RF-32 se contradicen).
   *Resuelto en M9 sin esperar a Análisis, al comprobar que el caso en disputa solo se materializa
   en uno de los dos endpoints — ver la nota del Patrón 3.*
3. **No es un bug, es documentación desactualizada del RF:** Patrón 4.
4. **Más caro, requiere diseño nuevo:** Patrón 5 — son features ausentes (buffer de auditoría, cola
   con prioridad, detección de outliers, validación cruzada de especie), no fixes de una línea.
   *Los de M1 (RF-01 SMTP y RF-11 410), los de M9 (RF-17 sync a Edge, RF-25 204/504, RF-32
   referencias huérfanas) y los de M2 (outliers de RF-50/51, RF-52 E1/E2) ya se implementaron;
   ninguno requirió infraestructura nueva: el buffer de E1 reutilizó el archivo de fallback que ya
   existía. Lo que queda —M2·RF-52 E3/E5— sí la requiere, además de decisiones de Análisis.*

**Lección que dejan las dos correcciones:** de los 20 ❌ cerrados entre M1 y M9, uno (M9·RF-23) era
un falso positivo de la auditoría —la regla existía, en el `model_validator` del DTO, donde el audit
no miró— y otro (M9·RF-17, sync a Edge) ya se había cerrado por una vía independiente antes de
empezar. Conviene releer el código antes de estimar los 16 ❌ que quedan en M2.

**Confirmado en M2 (2026-09-23):** tres de sus ❌ (RF-49 ×2 y RF-50 NIC 41) ya los habían cerrado
PRs de la línea `fix/m02-fixes` posteriores a la auditoría, y la tabla resumen del propio audit de M2
estaba mal sumada (eran 18 ❌ y 4 ⚠️, no 16 y 5).
