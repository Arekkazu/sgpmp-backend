# Patrones Transversales — Flujo Alterno (Módulos 1, 9, 2)

Síntesis de los tres audits de solo lectura (`anotaciones/modulo_1/gaps_flujo_alterno_modulo1.md`,
`anotaciones/modulo_9/gaps_flujo_alterno_modulo9.md`, `anotaciones/modulo_2/gaps_flujo_alterno_modulo2.md`).
> **Estado (2026-09-22):** los 9 ❌ del Módulo 1 están corregidos (rama `fix/gaps-flujo-alterno-m01`).
> Este documento conserva el diagnóstico estructural completo; las menciones a M1 se anotan con
> **(corregido en M1)** donde aplica. M9 y M2 siguen sin tocar.

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
| DTO/Pydantic → 400, RF pide 422/403 (falta subir) | M1 RF-05 **(corregido en M1)** | Escalada de privilegios (`extra="forbid"` en `EditarPerfilDTO`) rechazaba con 400 genérico de Pydantic antes de que el use case pudiera auditar el intento o lanzar `AuthorizationError`→403. El fix: declarar los campos críticos en el DTO propio para que el rechazo lo haga el use case |
| | M2 RF-40/41/42 (vía `_event_validations.py::validar_fecha_evento`, compartida) | Fecha de evento inválida da 422, RF pide 400 — pero aquí es al revés: **use case sube a 422 algo que el RF llama validación básica (400)** |
| | M2 RF-44 | Fecha futura / motivo vacío → 400 (Pydantic), RF pide 422 |
| | M2 RF-46 | Filtro de fecha inicio>fin → 400 (Pydantic), RF pide 422 |
| Use case/BusinessRuleError → 422, RF pide 400 (sobra) | M9 RF-17 | Solapamiento de niveles de alerta → 422, RF pide 400 |
| | M9 RF-20 | Tipo de área no reconocido → 422, RF pide 400 |
| | M2 RF-43 (caso inverso al de RF-40/41/42) | 3 de 9 casos (fecha, cantidad, unidad) usan `ValidationError`(400) donde el propio RF-43 etiqueta explícitamente "Error de validación — HTTP 422" |
| Código HTTP de familia distinta a la esperada | M9 RF-26 | Formato de imagen inválido → 400, RF pide 415 (Unsupported Media Type) |

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
  ambos, el código da 422 para "inactiva" — ahí sí es un ❌ franco, no solo un split.

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
eso lo deja en gap contra la letra de RF-32. Antes de tocar código aquí, vale más la pena que
Análisis unifique qué HTTP quiere el negocio para concurrencia en plantillas, porque los dos RF
fuente ya se contradicen entre sí.

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
| M9 | RF-17 | Sin ningún mecanismo de notificación/sincronización a nodos Edge al guardar un umbral ambiental |
| M9 | RF-25 | Nunca devuelve `204` para una finca sin catálogo configurado (siempre `200`); tampoco hay `504` por timeout de carga de contexto |
| M2 | RF-49 | Sin validación de compatibilidad de especie sensor↔activo (el puerto `SensorConsulta` ni siquiera tiene el campo); advertencia de dispositivo IoT offline hardcodeada a `None`, nunca se evalúa el heartbeat real |
| M2 | RF-50 / RF-51 | Sin detección de valores físicamente imposibles (outliers: peso negativo, etc.) en ningún punto de los indicadores zootécnicos ni de los datos consolidados |
| M2 | RF-52 | El flag `registro_incompleto` existe de punta a punta en el modelo de datos pero ningún use case lo activa nunca — un campo faltante se **rechaza** (400) en vez de aceptarse-con-advertencia, que es exactamente lo opuesto al principio de resiliencia que pide el RF. Tampoco existen el buffer/reintento de auditoría (E1), la cola con priorización (E3) ni la reconciliación RF-46↔RF-52 (E5) |

Estos son los hallazgos de mayor severidad real de toda la auditoría: en el Patrón 1/2/3 el sistema
sí aplica la regla y solo falla el código HTTP; aquí la regla de negocio no se aplica en absoluto.

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
   negocio, solo la clase de error. *Confirmado al corregir M1: los cinco casos de este tipo
   (RF-01 token, RF-03, RF-06 ×2 y RF-14) fueron exactamente eso.*
2. **Requiere alinear el propio corpus de RFs primero:** Patrón 3 (RF-30 vs RF-32 se contradicen).
3. **No es un bug, es documentación desactualizada del RF:** Patrón 4.
4. **Más caro, requiere diseño nuevo:** Patrón 5 — son features ausentes (buffer de auditoría, cola
   con prioridad, sync a Edge, detección de outliers, validación cruzada de especie), no fixes de
   una línea. *Los dos casos de M1 (RF-01 SMTP y RF-11 410) costaron más que un cambio de excepción
   pero no requirieron infraestructura nueva: bastó mover el envío del correo al request y leer el
   estado de la cuenta antes de editar.*
