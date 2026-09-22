# Resumen Ejecutivo — Gaps de Flujo Alterno (Módulos 1, 9, 2)

Vista rápida de los 3 audits de solo lectura. Para el detalle caso por caso ver los documentos por
módulo; para el porqué estructural, ver `gaps_flujo_alterno_patron_transversal.md`.

> **Estado (2026-09-22): los 9 ❌ del Módulo 1 están corregidos** (rama
> `fix/gaps-flujo-alterno-m01` → PR a `fix/m01`). M9 y M2 siguen intactos. El detalle está en
> `modulo_1/gaps_flujo_alterno_modulo1.md` y en
> `modulo_1/gaps_flujo_alterno_m01_correcciones.md`.

## Números

| Módulo | RFs auditables | Casos revisados | ❌ Gaps | ❌ Pendientes hoy | ⚠️ Parciales |
|---|---:|---:|---:|---:|---:|
| M1 — Identity Access | 12 (+2 sin ficha) | 90 | 9 | **0** | 2 (+1 nuevo, ver abajo) |
| M9 — Configuration | 17 (+1 sin ficha) | 118 | 11 | 11 | 17 |
| M2 — Biological Assets | 17 (+3 sin ficha) | 104 | 16 | 16 | 5 |
| **Total** | **46** | **312** | **36** | **27** | **24** |

"❌ Gaps" es el hallazgo original de la auditoría; "Pendientes hoy" es lo que sigue abierto. El ⚠️
nuevo de M1 es la mitad del caso de RF-04 que no se pudo implementar (no existe catálogo de acciones
CRUD por recurso).

RFs sin ficha de flujo alterno en el documento fuente (no auditables contra una spec que no existe):
M1 RF-08/RF-09, M9 RF-16, M2 RF-35/RF-36/RF-37.

## Top 15 — más probables de romper una primera revisión de QA

Ordenado por severidad: primero funcionalidad ausente (la regla no se aplica en absoluto), luego
HTTP incorrecto en endpoints centrales (la regla sí se aplica, el código de estado no coincide).
Las filas marcadas ✅ ya están corregidas (las 6 del Módulo 1).

| # | Módulo · RF | Problema | Tipo |
|---|---|---|---|
| 1 | M2 · RF-49 | Sin validar compatibilidad de especie sensor↔activo; alerta de dispositivo offline hardcodeada a `None` | Funcionalidad ausente |
| 2 | M2 · RF-52 | `registro_incompleto` nunca se activa — un campo faltante se rechaza (400) en vez de aceptarse-con-advertencia; sin buffer de auditoría ni cola con prioridad | Funcionalidad ausente |
| 3 | ✅ M1 · RF-01 | "SMTP falla 3 veces → 503" es irreproducible: el correo se agenda tras el 201, sin reintentos reales | Funcionalidad ausente |
| 4 | M9 · RF-17 | Sin ningún mecanismo de sincronización a nodos Edge al guardar un umbral ambiental | Funcionalidad ausente |
| 5 | M2 · RF-50/RF-51 | Sin detección de valores físicamente imposibles (outliers) en indicadores ni datos consolidados | Funcionalidad ausente |
| 6 | M9 · RF-25 | Nunca devuelve 204 para finca sin catálogo configurado; sin 504 por timeout | Funcionalidad ausente |
| 7 | ✅ M1 · RF-11 | No existe el 410 por eliminación lógica concurrente que pide el RF | Funcionalidad ausente |
| 8 | ✅ M1 · RF-06 | Transición de estado inválida → 422 (RF pide 409); bloquear al último admin → 422 (RF pide 400) — endpoint de gestión de cuentas, de los más probados del módulo | HTTP incorrecto |
| 9 | ✅ M1 · RF-05 | Escalada de privilegios (enviar `id_rol`/`estado_usuario`) → 400 genérico de Pydantic en vez de 403, sin quedar auditado como exige el RF | HTTP incorrecto |
| 10 | M2 · RF-43 | 3 de 9 casos (fecha, cantidad, unidad) dan 400 donde el propio RF etiqueta "Error de validación — HTTP 422" | HTTP incorrecto |
| 11 | ✅ M1 · RF-03 | Editar (no eliminar) el rol Administrador → 422 en vez de 403 — inconsistente con el DELETE del mismo agregado, que sí da 403 | HTTP incorrecto |
| 12 | M9 · RF-32 | Incompatibilidad de esquema → 412 (RF pide 422); concurrencia → 412 (RF pide 409) — el propio RF-30 contradice a RF-32 en el mismo tipo de caso | HTTP incorrecto (RFs contradictorios entre sí) |
| 13 | ✅ M1 · RF-14 | Notificaciones de `LOGIN_FALLIDO` sí llegan a cuentas INACTIVAS, violando la regla de privacidad explícita del RF | Regla de negocio incorrecta |
| 14 | M2 · RF-44 | Fecha futura / motivo vacío → 400 (Pydantic), RF pide 422 en ambos | HTTP incorrecto |
| 15 | M9 · RF-26 | Formato de imagen inválido → 400, RF pide 415 (validación de contenido real con Pillow, solo el código HTTP no coincide) | HTTP incorrecto |

## Lo mejor de cada módulo (cero gaps, implementación calcada al RF)

- **M1:** RF-02 (autenticación), RF-07 (cambio de contraseña), RF-10 (auditoría), RF-12 (detalle de usuario).
- **M9:** RF-18 (parámetros operativos), RF-24 (calibración IoT), RF-27 (tema visual), RF-28 (dashboard), RF-29 (idioma).
- **M2:** RF-33 (registro de activos), RF-34 (asociación a infraestructura), RF-38 (cierre de ciclo), RF-45 (bajas), RF-48 (transferencia interna).

## Una idea, no 36: la causa raíz se concentra en dos patrones

De los 36 gaps ❌, la mayoría no son 36 fallas independientes — ver
`gaps_flujo_alterno_patron_transversal.md`:

- **Patrón "DTO vs. use case"** (la capa que valida no coincide con la clasificación 400/422/403 del
  RF): explica los gaps de M1·RF-05 (corregido), M9·RF-17/RF-20/RF-26, M2·RF-40/41/42/43/44/46.
- **Patrón "inexistente o inactivo"** (el RF pide un HTTP para ambos, el código separa 404/422):
  explica la mitad de los ⚠️ de M9 (9 de sus 17 RFs) y parte de M1·RF-05.

El resto (~15 gaps) es funcionalidad genuinamente ausente — no tiene un fix de una línea, requiere
diseño nuevo (buffer de auditoría, cola con prioridad, sync a Edge, detección de outliers, validación
cruzada de especie/sensor). Los dos de esa categoría que pertenecían a M1 (RF-01 SMTP→503 y RF-11
410 Gone) ya se implementaron.
