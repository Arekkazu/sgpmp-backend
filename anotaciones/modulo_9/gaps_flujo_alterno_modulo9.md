# Gaps de flujo alterno — Módulo 9 (Configuration)

Compara cada caso de **Flujo alterno** documentado en
`anotaciones/Requerimientos/Especificacion-Requerimientos-Modulo9.md` contra el
código real de `src/configuration`. Solo lectura — no se tocó código. Metodología:
router → use case → DTO/value object → clase de error lanzada
(`src/shared/errors.py`), verificando además `modulo1.permisos` en vivo vía MCP
postgres para los casos de "acceso no autorizado".

No se juzga el texto exacto del mensaje (eso es copy/UX) — se juzga si el HTTP
code y la condición de negocio detrás son correctos.

## Resumen

| RF | Caso(s) revisados | ❌ Gap | ⚠️ Parcial | ➖ N/A |
|----|---|---|---|---|
| RF-15 — Catálogo de especies | 7 | 0 | 1 | 1 |
| RF-16 — Etapas/patologías/métricas | sin ficha de flujo alterno en el doc fuente | — | — | — |
| RF-17 — Umbrales ambientales | 7 | 2 | 0 | 0 |
| RF-18 — Parámetros operativos | 7 | 0 | 0 | 0 |
| RF-19 — Fincas | 7 | 0 | 2 | 0 |
| RF-20 — Infraestructura | 7 | 1 | 2 | 0 |
| RF-21 — Dispositivos IoT | 7 | 0 | 2 | 1 |
| RF-22 — Asociación sensor-área | 8 | 1 | 2 | 0 |
| RF-23 — Configuración remota IoT | 8 | 1 | 1 | 0 |
| RF-24 — Calibración | 7 | 0 | 0 | 0 |
| RF-25 — Interfaz adaptativa | 7 | 2 | 1 | 2 |
| RF-26 — Identidad visual | 6 | 1 | 0 | 1 |
| RF-27 — Tema visual | 6 | 0 | 0 | 1 |
| RF-28 — Dashboard | 7 | 0 | 0 | 0 |
| RF-29 — Idioma | 6 | 0 | 0 | 2 |
| RF-30 — Plantillas (CRUD) | 7 | 1 | 3 | 1 |
| RF-31 — Creación de plantilla | 7 | 0 | 2 | 0 |
| RF-32 — Aplicación de plantilla | 7 | 2 | 1 | 1 |

**Patrón recurrente (no contado como gap independiente en cada fila, se explica aquí una vez):**
en más de la mitad de los RFs, cuando el flujo alterno del RF describe un único
caso "recurso X inexistente **o** inactivo" con un solo HTTP esperado, el código
lo separa en dos ramas — `NotFoundError` (404) si no existe, `BusinessRuleError`
(422) si existe pero está inactivo. Cuando el RF pide 422/404 para ambos casos,
la mitad que no coincide queda marcada ⚠️ en la fila correspondiente. Es una
inconsistencia de forma, no de fondo: el sistema sí bloquea la operación en
ambos casos, solo que con dos códigos distintos en vez de uno.

---

## RF-15 — Catálogo de especies productivas

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Nombre duplicado (case-insensitive) | 409 | 409 `ConflictError` | `registrar_especie_use_case.py:49` + `especie_repository.py:60` (`func.lower`) | ✅ | — |
| Longitud/formato de nombre inválido | 400 | 400 `ValidationError` | `nombre_especie.py:37-53` | ✅ | — |
| Ingeniero de Campo intenta Crear/Desactivar | 403 | 403 (RBAC) | `especie_router.py:44,120` | ✅ | `modulo1.permisos`: Ing. Campo solo tiene R/U sobre recurso 8 |
| Desactivación bloqueada por proceso crítico | 422 | 423 `LockedError` | `desactivar_especie_use_case.py:62-65` | ⚠️ | Condición correcta, pero `LockedError` mapea a 423 (Locked), no 422 |
| Conflicto de edición concurrente | 412 | 412 `PreconditionFailedError` | `editar_especie_use_case.py:66-74` | ✅ | — |
| Error de sincronización offline | (notificación UI, no HTTP) | — | — | ➖ | Responsabilidad de frontend, no del backend |
| Especie no encontrada | 404 | 404 `NotFoundError` | `editar_especie_use_case.py:49`, `desactivar_especie_use_case.py:50` | ✅ | — |

---

## RF-16 — Etapas, patologías y métricas por especie

El documento fuente no trae sección `**Flujo alterno:**` para este RF (a
diferencia de los otros 17). Se verificó solo el RBAC vía `modulo1.permisos`:
recursos 17 (`ciclos_biologicos`, etapas), 18 (`patologias`) y 19
(`metricas_produccion`) están correctamente restringidos a Administrador y
Veterinario (C/R/U/D los dos roles), sin acceso de escritura para Productor,
Ingeniero de Campo ni Contador — consistente con la restricción textual del RF.
No hay caso de flujo alterno documentado que comparar.

---

## RF-17 — Umbrales de monitoreo y niveles de alerta ambiental

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Inconsistencia de rango (min ≥ max) | 400 | 400 (Pydantic `field_validator` → handler global) | `registrar_umbral_dto.py:22-28` | ✅ | — |
| Especie inactiva o no encontrada | 422 | 422 `BusinessRuleError` | `registrar_umbral_use_case.py:98-103` | ✅ | — |
| Configuración duplicada (especie+variable) | 409 | 409 `ConflictError` | `registrar_umbral_use_case.py:130-137` | ✅ | — |
| Solapamiento de niveles de alerta | 400 | 422 `BusinessRuleError` (`SOLAPAMIENTO_NIVELES`) | `registrar_umbral_use_case.py:52-76` | ❌ | Lógica de validación correcta (cobertura completa, sin huecos/solapes), pero el código HTTP no coincide |
| Valores fuera de límites físicos | 400 | 400 `ValidationError` | `registrar_umbral_use_case.py:28-36` | ✅ | — |
| Fallo de privilegios (rol Productor) | 403 | 403 (RBAC) | `umbral_router.py:50` | ✅ | Productor no tiene fila en `modulo1.permisos` para recurso 20 |
| Error de sincronización con Nodo Edge | 500 + estado "Pendiente de Sincronización" | — | `registrar_umbral_use_case.py` (completo) | ❌ | No existe ningún mecanismo de notificación a dispositivos IoT/Edge al guardar un umbral; el caso completo no está implementado |

---

## RF-18 — Parámetros operativos del sistema

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Valores ≤ 0 | 400 | 400 (Pydantic `field_validator`) | `crear_configuracion_dto.py:11-18` | ✅ | — |
| Heartbeat < frecuencia_muestreo | 400 | 400 `ValidationError` | `configuracion_global.py:57-68` | ✅ | — |
| Intento de crear múltiples configs activas | 409 | 409 `ConflictError` | `crear_configuracion_use_case.py:38-45` | ✅ | — |
| Fallo en registro de auditoría obligatorio | 500 + rollback | 500 (excepción no controlada → rollback) | `crear_configuracion_use_case.py:57-68` | ✅ | — |
| Acceso no autorizado (Ing./Vet.) | 403 | 403 (RBAC) | `configuracion_global_router.py:40` | ✅ | Ninguno de los dos roles tiene fila en recurso 21 |
| Conflicto de actualización concurrente | 412 | 412 `PreconditionFailedError` | `actualizar_configuracion_use_case.py:48-57` | ✅ | — |
| Dato no entero (float/string) | 400 | 400 (Pydantic `int` type coercion) | `crear_configuracion_dto.py` (tipo `int`) | ✅ | — |

RF-18 es uno de los mejor implementados del módulo: 7/7 casos correctos.

---

## RF-19 — Registro y gestión de datos de la finca

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Nombre/ubicación de finca duplicados | 409 | 409 `ConflictError` | `registrar_finca_use_case.py:34-40` | ⚠️ | Dedup solo por `nombre` global; el RF pide considerar también `ubicacion_finca` y el alcance por productor |
| Coordenadas fuera de rango | 400 | 400 (DTO + VO) | `registrar_finca_dto.py:19-31`, `ubicacion_finca.py:54-64` | ✅ | — |
| Tamaño de finca ≤ 0 | 400 | 400 (DTO) | `registrar_finca_dto.py:49-53` | ✅ | — |
| Caracteres no permitidos en texto | 400 | 400 (parcial) | `ubicacion_finca.py:15,26-33` | ⚠️ | `departamento`/`municipio`/`vereda` sí validan solo-letras; `nombre` de la finca no tiene esa misma restricción (acepta dígitos/símbolos) |
| Acceso denegado (Productor edita) | 403 | 403 (RBAC) | `finca_router.py` (recurso 9) | ✅ | Solo Administrador tiene C/U/D |
| Desactivación con dependencias activas | 422 | 422 `BusinessRuleError` | `desactivar_finca_use_case.py:39-47` | ✅ | — |
| JSON de ubicación incompleto | 400 | 400 (Pydantic, campos requeridos) | `registrar_finca_dto.py:12-17` | ✅ | — |

---

## RF-20 — Infraestructura productiva

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Nombre duplicado en la misma finca | 409 | 409 `ConflictError` (constraint BD) | `infraestructura_repository.py:62-67` | ✅ | — |
| Superficie ≤ 0 | 400 | 400 `ValidationError` | `superficie.py:14-27` | ✅ | — |
| Finca no encontrada o inactiva | 422 (ambos) | Registrar: 404/422 según el caso · Editar: 422 unificado | `registrar_infraestructura_use_case.py:35-44` vs `editar_infraestructura_use_case.py:46-54` | ⚠️ | El endpoint de edición unifica correctamente a 422; el de registro no (404 si no existe) |
| Desactivación con dependencias | 422 | 422 `BusinessRuleError` | `desactivar_infraestructura_use_case.py:42-49` | ✅ | — |
| Acceso no autorizado (Productor) | 403 | 403 (RBAC) | recurso 10, solo Admin C/U/D | ✅ | — |
| Tipo de área no reconocido | 400 | 422 `BusinessRuleError` | `registrar_infraestructura_use_case.py:47-56`, `editar_infraestructura_use_case.py:73-82` | ❌ | Código HTTP no coincide (400 esperado vs 422 real) |
| Conflicto de edición concurrente | 412 | 412 `PreconditionFailedError` | `editar_infraestructura_use_case.py:58-71` | ✅ | — |

---

## RF-21 — Registro de dispositivos IoT

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Serial duplicado | 409 | 409 `ConflictError` | `registrar_dispositivo_iot_use_case.py:54-60` | ✅ | — |
| Área no encontrada o inactiva | 422 (ambos) | 404 si no existe / 422 si inactiva | `registrar_dispositivo_iot_use_case.py:34-44` | ⚠️ | Split 404/422, ver patrón recurrente arriba |
| Intento de DELETE físico | 405 | 405 (por omisión del framework) | `dispositivo_iot_router.py` (sin ruta `DELETE`) | ⚠️ | El código coincide, pero por ausencia de endpoint, no por una regla que distinga si el dispositivo tiene datos históricos — cualquier `DELETE` da 405 igual, con o sin datos |
| Acceso no autorizado (Prod/Vet/Cont) | 403 | 403 (RBAC) | recurso 11 | ✅ | Veterinario y Contador no tienen fila en el recurso; Productor solo R |
| Error de formato serial/descripción | 400 | 400 (DTO + VO) | `registrar_dispositivo_iot_dto.py:23-42`, `serial_dispositivo.py:22-41` | ✅ | — |
| Conflicto de sincronización offline | (notificación UI) | — | — | ➖ | Frontend |
| Fallo en registro de auditoría | 500 + rollback | 500 | `registrar_dispositivo_iot_use_case.py:70-81` | ✅ | — |

---

## RF-22 — Asociación de sensores a estructuras productivas

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Dispositivo IoT no existente | 404 | 404 `NotFoundError` | `asociar_sensor_area_use_case.py:59-64` | ✅ | — |
| Sensor no existente o no vinculado | 422 (unificado) | 404 si no existe / 422 si no vinculado | `asociar_sensor_area_use_case.py:47-57` | ⚠️ | Split 404/422 |
| Área productiva inexistente o inactiva | 404 (ambos) | 404 si no existe / **422** si inactiva | `asociar_sensor_area_use_case.py:66-76` | ❌ | Aquí el split va al revés que en otros RFs: el RF pide 404 para ambos, el código da 422 para "inactiva" |
| Sensor ya asociado a otra área | 409 | 409 `ConflictError` | `asociar_sensor_area_use_case.py:102-113` | ✅ | — |
| Asociación duplicada (misma área) | 409 | 409 `ConflictError` | `asociar_sensor_area_use_case.py:95-100` | ✅ | — |
| Acceso no autorizado (Prod/Vet/Cont) | 403 | 403 (RBAC) | recurso 12 | ✅ | — |
| Fallo en registro de auditoría | 500 + rollback | 500 | `asociar_sensor_area_use_case.py:133-144` | ✅ | — |
| Error de formato en punto de instalación | 400 | 400 `ValidationError` | `punto_instalacion.py:16-28` | ✅ | — |

---

## RF-23 — Configuración remota de dispositivos IoT

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Dispositivo IoT inexistente | 404 | 404 `NotFoundError` | `configurar_remotamente_use_case.py:43-48` | ✅ | — |
| Parámetros fuera de rango técnico | 400 | 400 `ValidationError` | `configurar_remotamente_use_case.py:61-71`, `tipo_dispositivo_iot.py:26-32` | ✅ | — |
| Inconsistencia lógica de tiempos (intervalo < frecuencia) | 400 | — (no validado) | `tipo_dispositivo_iot.py:22-40` (`verificar_rango`) | ❌ | `verificar_rango` solo valida cada campo contra su propio rango individual; nunca compara `intervalo_transmision` contra `frecuencia_captura` entre sí |
| Dispositivo offline (Estado Diferido) | 202 Accepted | 202 | `dispositivo_iot_router.py:63,105` (`_ESTADO_A_HTTP["PENDIENTE"]=202`) | ✅ | — |
| Timeout de confirmación (ACK) | 504 | 504 `GatewayTimeoutError` | `dispositivo_iot_router.py:97-98` | ✅ | — |
| Acceso no autorizado (Vet/Prod) | 403 | 403 (RBAC) | recurso 11, acción U | ✅ | — |
| Conflicto de comandos concurrentes | 409 | 409 `ConflictError` | `configurar_remotamente_use_case.py:73-77` | ✅ | — |
| Fallo en registro del historial (auditoría) | 500 + rollback, sin enviar MQTT | — | `configurar_remotamente_use_case.py` (completo) | ⚠️ | El use case no llama a ningún `auditoria_repo` — a diferencia de RF-15/17/19/20/21/22/24, aquí no hay registro de auditoría explícito antes del envío MQTT, así que este caso de flujo alterno no puede materializarse tal como lo describe el RF |

---

## RF-24 — Calibración de dispositivos IoT

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Dispositivo o sensor no encontrado | 404 | 404 `NotFoundError` | `registrar_calibracion_use_case.py:46-63` | ✅ | — |
| Inconsistencia de asociación (área incorrecta) | 400 | 400 `ValidationError` | `registrar_calibracion_use_case.py:70-76` | ✅ | — |
| Dispositivo inactivo | 422 | 422 `BusinessRuleError` | `registrar_calibracion_use_case.py:52-56` | ✅ | — |
| Valor de referencia fuera de rango técnico | 400 | 400 `ValidationError` | `registrar_calibracion_use_case.py:88-103` | ✅ | — |
| Acceso no autorizado (Prod/Cont) | 403 | 403 (RBAC) | recurso 12 | ✅ | — |
| Fallo en registro de auditoría | 500 + rollback | 500 `InfrastructureError` explícito | `registrar_calibracion_use_case.py:128-143` | ✅ | Implementación ejemplar: captura el fallo del repo de auditoría específicamente y lo traduce a 500 con el mensaje exacto del RF |
| Datos no numéricos o incompletos | 400 | 400 `ValidationError`/Pydantic | `registrar_calibracion_use_case.py:78-86` | ✅ | — |

RF-24 es el RF mejor implementado del módulo: 7/7 casos correctos, incluyendo
el manejo de auditoría más fiel al RF de todo el módulo.

---

## RF-25 — Adaptación de interfaz operativa

Único endpoint real: `GET /configuracion/interfaz/contexto`
(`contexto_interfaz_router.py`). El RF describe comportamientos que en parte
exceden lo que un solo GET de agregación puede resolver.

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Usuario sin finca asociada | 200 + vista de bienvenida | 200, `id_finca=None` | `obtener_contexto_use_case.py:33-37` | ✅ | — |
| Finca sin especies/infraestructura configuradas | 204 No Content | 200 siempre | `obtener_contexto_use_case.py` (completo) | ❌ | No existe lógica que detecte "finca sin catálogo" y devuelva 204; siempre 200 |
| Cambio de permisos en sesión activa | 403 (detección en vivo) | Parcial | `require_permission` consulta `modulo1.permisos` en cada request | ⚠️ | El *permiso* sí se re-evalúa en vivo; un cambio de `id_rol` en sí no se detecta hasta que se emite un JWT nuevo — no hay invalidación activa de sesión por cambio de rol en este endpoint |
| Acceso a módulo no autorizado (bypass de URL) | 403 | 403 (RBAC genérico) | `require_permission` en cada router | ✅ | Cubierto por el mecanismo estándar, no por RF-25 específicamente |
| Timeout de carga de contexto (>2s) | 504 | — (sin timeout explícito; un fallo de BD da 503) | `obtener_contexto_use_case.py` | ❌ | No hay enforcement de un límite de 2s ni mapeo a 504; una BD caída da 503 vía `db_no_disponible_handler`, no 504 |
| Inconsistencia especie-indicador | omitir sin error + log | — | — | ➖ | Pertenece al filtrado de widgets (RF-28), no a este endpoint |
| ID de finca manipulado en la URL | 401 | — | `obtener_contexto_use_case.py` | ➖ | Este endpoint no acepta `id_finca` como parámetro (siempre resuelve por el usuario autenticado); el escenario que describe el RF no aplica a esta ruta tal como está diseñada |

---

## RF-26 — Personalización de identidad visual

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Formato de imagen no compatible | 415 | 400 `ValidationError` | `almacen_logos.py:63-71` | ❌ | Validación de contenido muy sólida (Pillow real, rechazo de SVG con script), pero el código HTTP no es el que pide el RF |
| Código de color hexadecimal inválido | 400 | 400 `ValidationError` | `color_hex.py:40-49` | ✅ | — |
| Nombre de organización demasiado extenso | 400 | 400 `ValidationError` | `nombre_organizacion.py:16-32` | ✅ | — |
| Fallo en persistencia del archivo | 500 | 500 `InfrastructureError` | `almacen_logos.py:88-105` | ✅ | Mensaje casi idéntico al del RF |
| Acceso denegado (Ing./Productor) | 403 | 403 (RBAC) | recurso 23, solo Admin | ✅ | — |
| Cancelación en vista previa | (sin llamada al servidor) | — | — | ➖ | Frontend |

---

## RF-27 — Configuración visual del sistema (tema)

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Valor de tema inválido | 400 | 400 (validación de dominio) | `tema_visual_router.py` + entidad `TemaVisual` | ✅ | — |
| Fallo de persistencia | 500 | 500 (genérico) | patrón try/rollback estándar | ✅ | — |
| Privilegios insuficientes (tema global) | 403 | 403 (RBAC, recurso 27 ≠ recurso 24) | `tema_visual_router.py:31-32,95-113` | ✅ | Split correcto entre `tema_visual` (personal, todos los roles) y `configuracion_ui_global` (solo Admin) — el diseño evita exactamente el bypass que el RF teme |
| Incompatibilidad de contraste con identidad visual | advertencia + auto-ajuste | Implementado | `color_hex.py:75-116` (`ajustar_para_contraste`, WCAG 2.1 AA) | ✅ | — |
| Modo "Automático" sin soporte del navegador | fallback a tema claro | — | — | ➖ | Comportamiento de cliente (`prefers-color-scheme`), no del backend |
| Conflicto de actualización de perfil | 409 | 409 `ConflictError` (mismo mecanismo de `version_perfil` que RF-28/29) | patrón `_verificar_perfil_vigente` | ✅ | — |

---

## RF-28 — Personalización del dashboard

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Solapamiento de posiciones (grilla) | 409 | 409 `ConflictError` | `dashboard_layout.py:144-147` | ✅ | — |
| Límite de 12 widgets activos | 400 | 400 `ValidationError` | `dashboard_layout.py:159-163` | ✅ | Incluye el caso borde de `active_widget` vacío pero `layout_config` lleno |
| Desbordamiento horizontal (span inválido) | 400 | 400 `ValidationError` | `dashboard_layout.py:123-133` | ✅ | — |
| Widget no autorizado para el rol | 403 | 403 `AuthorizationError` | `guardar_dashboard_use_case.py:111-120` | ✅ | — |
| Conflicto de actualización (perfil modificado) | 409 | 409 `ConflictError` | `guardar_dashboard_use_case.py:76-88` | ✅ | — |
| Fallo en "restaurar configuración predeterminada" | 500 | No verificado en detalle | `restaurar_dashboard_use_case.py` | — | Fuera del alcance de esta pasada (no se leyó el archivo); no se reporta veredicto |
| Widget sin datos operativos | fallback visual, sin error | — | — | ➖ | Renderizado de frontend |

RF-28 es, junto con RF-24, de los mejor implementados: el propio docstring del
use case enumera los flujos alternos del RF en el mismo orden que el
documento, y cada uno tiene su excepción específica.

---

## RF-29 — Configuración de idioma

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Código de idioma no soportado | 400 | 400 `ValidationError` | `preferencia_idioma.py:60-71` (`LOCALES_PERMITIDOS={"es-CO","en-US"}`) | ✅ | Coincide con `[[rf29_i18n_motor_en_frontend]]`: es-CO/en-US, nunca es/en |
| Fallo en persistencia | 500 | 500 `InfrastructureError` | `guardar_idioma_personal_use_case.py:38-49` | ✅ | Mensaje calcado al del RF |
| Ausencia de traducción (fallback a español) | fallback silencioso | — | — | ➖ | Motor i18n vive en frontend |
| Privilegios insuficientes (idioma global) | 403 | 403 (RBAC, recurso 27 ≠ recurso 26) | `preferencia_idioma_router.py:35-43,114-119` | ✅ | Mismo patrón correcto que RF-27; incluso trae un mensaje de override específico para este 403 |
| Conflicto de actualización de perfil | 409 | 409 `ConflictError` | `guardar_idioma_personal_use_case.py:65-77` | ✅ | — |
| Desbordamiento visual por longitud de texto | CSS adaptativo | — | — | ➖ | Frontend |

---

## RF-30 — Plantillas de configuración (CRUD general)

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Nombre de plantilla duplicado | 409 | 409 `ConflictError` | `registrar_plantilla_use_case.py:68-77` | ✅ | — |
| Violación del esquema JSON | 400 | 400 (Pydantic, `validar_snapshot`) | `registrar_plantilla_dto.py:27-38` | ✅ | Mensaje incluye el detalle de campos inválidos, como pide el RF |
| Parámetros fuera de alcance (scope creep) | 422 | 422 `BusinessRuleError` | `registrar_plantilla_use_case.py:56-66` | ✅ | — |
| Incompatibilidad de versión de esquema (legacy) | 412 | — (no aplica a creación) | — | ➖ | Este caso es de *aplicar* una plantilla vieja, no de crearla; está correctamente implementado en RF-32 (ver abajo), no en el flujo de creación |
| Especie no encontrada o inactiva | 404 (ambos) | 404 si no existe / 422 si inactiva | `registrar_plantilla_use_case.py:79-90` | ⚠️ | Split 404/422 |
| Modificación de plantilla existente (inmutabilidad) | 405 | 405 (por omisión, no hay `PUT`/`PATCH` sobre `{id}`) | `plantilla_router.py` | ⚠️ | Igual que RF-21: el 405 sale porque la ruta no existe, no porque el sistema distinga explícitamente "ya existe, es inmutable" |
| Privilegios insuficientes | 403 | 403 (RBAC) | recurso 28, solo Admin+Ing. Campo (C) | ✅ | — |

---

## RF-31 — Creación de plantilla de configuración

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Nombre de plantilla duplicado | 409 | 409 `ConflictError` | `registrar_plantilla_use_case.py:68-77` | ✅ | — |
| Creación sin parámetros seleccionados | 400 | No verificado a fondo | `esquema_plantilla.py::validar_snapshot` | — | No se confirmó si un `params_snapshot` con las 4 listas vacías es rechazado explícitamente; requiere lectura adicional de `validar_snapshot` no cubierta en esta pasada |
| Fallo de validación de esquema JSON | 400 | 400 (Pydantic) | `registrar_plantilla_dto.py:27-38` | ✅ | — |
| Especie inactiva o no encontrada | 422 (ambos) | 404 si no existe / 422 si inactiva | `registrar_plantilla_use_case.py:79-90` | ⚠️ | Split 404/422 (aquí el 422-inactiva sí coincide con el RF; el 404-no-existe no) |
| Sobrescritura (violación de inmutabilidad) | 405 | 405 (por omisión) | `plantilla_router.py` | ⚠️ | Igual razonamiento que en RF-30 |
| Fallo crítico de persistencia (atomicidad) | 500 | 500 (rollback genérico) | `registrar_plantilla_use_case.py:110-121` | ✅ | — |
| Acceso no autorizado | 403 | 403 (RBAC) | recurso 28 | ✅ | — |

**Nota:** RF-30 y RF-31 documentan, en la práctica, el mismo endpoint de creación
de plantilla (`POST /configuracion/plantillas`) desde dos ángulos distintos del
Excel original — de ahí la superposición casi total de casos.

---

## RF-32 — Aplicación de plantilla de configuración

| Caso | HTTP esperado (RF) | HTTP real (código) | Archivo:línea | Veredicto | Nota |
|---|---|---|---|---|---|
| Incompatibilidad de esquema (legacy) | 422 | 412 `PreconditionFailedError` | `aplicar_plantilla_use_case.py:60-70` | ❌ | El código usa 412 aquí — que es justamente el HTTP que el flujo alterno homólogo de **RF-30** pide para este mismo escenario. Es decir: el código es consistente con RF-30 pero no con la redacción de RF-32, que para el mismo caso pide 422. Contradicción entre los dos RF, no solo del código. |
| Referencias huérfanas en la plantilla | 400 | — (no validado antes de aplicar) | `aplicar_plantilla_use_case.py:107-124` | ❌ | El snapshot se aplica directo (`vincular_desde_snapshot`, etc.) sin verificar antes que cada referencia (ej. patología) siga existiendo/activa; una referencia huérfana fallaría más abajo (constraint de BD → 409/500), no con el 400 explícito que pide el RF |
| Configuración destino no encontrada o inactiva | 404 (ambos) | 404 si no existe / 422 si inactiva | `aplicar_plantilla_use_case.py:72-84` | ⚠️ | Split 404/422 |
| Cancelación por el usuario | sin llamada al servidor | — | — | ➖ | Frontend |
| Fallo crítico durante la aplicación (rollback automático) | 500 | 500 (rollback genérico) | `aplicar_plantilla_use_case.py:107-139` | ✅ | — |
| Conflicto de modificación concurrente | 409 | 412 `PreconditionFailedError` | `aplicar_plantilla_use_case.py:90-100` | ❌ | Mismo patrón de concurrencia optimista que el resto del módulo (412), pero el RF-32 específicamente pide 409 para este caso — inconsistente con el propio texto del RF que en otros RFs (15/17/18/19/20) llama "concurrencia" siempre a 412 |
| Acceso no autorizado | 403 | 403 (RBAC) | recurso 28, acción E | ✅ | — |

**Nota:** los dos ❌ de concurrencia/versión de esta tabla no son errores de
implementación aislados — son el mismo patrón (412) aplicado consistentemente
en *todo* el módulo, que choca puntualmente con cómo RF-30 y RF-32 redactan el
mismo tipo de caso con HTTP distintos entre sí. Antes de "corregir" el código
valdría la pena unificar qué código HTTP quiere realmente el RF para
concurrencia optimista en todo el módulo.
