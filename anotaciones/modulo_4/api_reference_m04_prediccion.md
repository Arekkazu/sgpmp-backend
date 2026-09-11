# API Reference — `src/prediction/`

> Generado el 2026-07-23. Solo documentación — no subir al repositorio.
>
> **Todos los endpoints de este módulo requieren sesión activa** (`Authorization: Bearer <token>`), **con una única excepción**: `POST /prediccion/modelos` (registro interno de versión de modelo desde RF-71), que se autentica con la cabecera `X-RF71-Internal-Key` en lugar de JWT. Ver la sección siguiente para el detalle de cómo funciona esto.

---

## Sesión y RBAC — cómo funciona en este módulo

Este módulo no define ninguna lógica de autorización propia: reutiliza `get_current_user` (`src/identity_access/infrastructure/dependencies.py`) y `require_permission` (`src/shared/rbac.py`), igual que el resto del backend. Puntos importantes para entender el comportamiento real de los 20 endpoints:

### 1. Toda ruta con `require_permission(...)` exige sesión, aunque el handler no reciba `usuario_actual`

`require_permission(id_recurso, id_accion)` es una fábrica de dependencias que internamente depende de `get_current_user`:

```python
def dependency(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> None:
    ...
```

Esto significa que endpoints como `GET /prediccion/patologias` o `GET /prediccion/patologias/{id}` — cuyo handler **no** declara `usuario_actual` como parámetro porque no lo necesitan para su lógica — **igual exigen un Bearer token válido**, porque la dependencia de RBAC lo exige por debajo. FastAPI cachea las dependencias por request, así que si el mismo endpoint también declara `usuario_actual` explícitamente (para auditoría, por ejemplo), no se vuelve a verificar el token dos veces.

En la práctica: **no existe ningún endpoint público en `src/prediction/`**, salvo la excepción documentada en el punto 4.

### 2. Qué valida `get_current_user`

- Requiere el header `Authorization: Bearer <token>` → si falta, `401 TOKEN_REQUERIDO`.
- Decodifica el JWT: `sub` → `id_usuario`, `jti` → `id_token`, `rol` → `id_rol`.
- Verifica que el token no esté en la "blacklist" (`Tokens.fecha_uso IS NULL`) → si ya fue usado/revocado, `401 TOKEN_REVOCADO`.
- Verifica **inactividad de 30 minutos** contra `CuentasUsuarios.ultimo_acceso`: si se superó el umbral, cierra la sesión activa en `Sesiones`, marca el token como usado y responde `401 SESION_EXPIRADA_INACTIVIDAD`.
- Si todo es válido, actualiza `ultimo_acceso` y retorna `UsuarioActual(id_usuario, id_token, id_rol)`.

### 3. Qué valida `require_permission`

Con el `id_rol` ya resuelto por `get_current_user`, consulta `modulo1.permisos` filtrando por `(id_rol, id_recurso, id_accion, es_activo=true)`. Si no hay fila activa, responde `403 ACCESO_DENEGADO`. El use case **nunca** verifica roles — solo usa `usuario_actual.id_usuario` (y a veces `id_rol`) para auditoría o para filtros de negocio, nunca para decidir acceso.

### 4. La única excepción: `POST /prediccion/modelos`

Este endpoint no tiene `dependencies=[Depends(require_permission(...))]` ni `usuario_actual` — es el punto de entrada donde el pipeline interno de RF-71 (entrenamiento/validación offline de modelos) registra una nueva versión. Se protege con la cabecera `X-RF71-Internal-Key`, validada dentro del propio use case (`RegistrarVersionModeloUseCase._verificar_clave_interna`). No es una sesión de usuario — es un secreto compartido entre sistemas — y por eso **no aparece en la tabla de permisos RBAC**.

### 5. Adaptadores stub que aún no aplican control de acceso real

Tres dependencias cruzadas de este módulo todavía son stubs (`infrastructure/adapters/*_stub_adapter.py`) que devuelven valores "seguros por defecto" mientras el módulo real no se implementa:

| Adaptador | Método | Valor actual | Efecto |
|-----------|--------|--------------|--------|
| `ActivoBiologicoStubAdapter` | `activo_existe_y_accesible(id_activo, id_usuario, id_rol)` | Siempre `True` | `GET /prediccion/historial/{id_activo_biologico}` **no filtra hoy por finca/rol** — cualquier usuario autenticado con permiso `(42, R)` puede consultar el historial de cualquier activo biológico, exista o no y sea o no de su finca. |
| `ModeloActivoStubAdapter` | `tiene_modelos_activos(id_patologia)` | Siempre `False` | Editar/desactivar una patología nunca es bloqueada por "modelo en uso" (FA-07/FA-08 de RF-64 no se activan todavía). |
| `NodoEdgeStubAdapter` | `hay_nodos_activos(tipo_modelo)` | Siempre `True` | No documentado como endpoint directo, pero afecta validaciones internas de `ConfigurarMotorUseCase` relacionadas con modo `EDGE`. |

Esto no es un problema de RBAC (la sesión y el permiso sí se validan correctamente) sino de reglas de negocio adicionales que dependen de otros módulos (Activos Biológicos, IoT) aún no conectados.

---

## Prefijos de rutas

| Router | Prefijo | Tag Swagger |
|--------|---------|-------------|
| `patologia_m04_router.py` | `/prediccion/patologias` | Predicción M04 - Catálogo de Patologías |
| `motor_ia_router.py` | `/prediccion/motor-ia` | Predicción M04 - Motor de Inferencia IA |
| `historial_diagnostico_router.py` | `/prediccion/historial` | Predicción M04 - Historial Diagnóstico |
| `version_modelo_router.py` | `/prediccion/modelos` | Predicción M04 - Versiones de Modelos IA |
| `ota_router.py` | `/prediccion` (`/modelos/{id}/ota-status`, `/despliegues`) | Predicción M04 - OTA |
| `retroalimentacion_clinica_router.py` | `/prediccion/retroalimentacion` | Predicción M04 - Retroalimentación Clínica |
| `auditoria_m04_router.py` | `/prediccion/auditoria` | Predicción M04 - Auditoría RF-73 |

---

## Endpoints

### Catálogo de Patologías — `/prediccion/patologias`

> **Recurso RBAC:** `id_recurso = 18` (`patologias`) — RF-64 CU-01

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(18, C)` | Admin, Vet | `RegistrarPatologiaUseCase` |
| `GET` | `/` | `(18, R)` | Admin, Vet | `ConsultarPatologiasUseCase` |
| `GET` | `/{id_patologia}` | `(18, R)` | Admin, Vet | `ObtenerPatologiaUseCase` |
| `PATCH` | `/{id_patologia}` | `(18, U)` | Admin, Vet | `EditarPatologiaUseCase` |
| `PATCH` | `/{id_patologia}/desactivar` | `(18, D)` | Admin, Vet | `DesactivarPatologiaUseCase` |

#### `POST /prediccion/patologias/` — Registrar patología

**Input `RegistrarPatologiaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `nombre_patologia` | `str` | Único (case-insensitive) a nivel global |
| `especie_aplicable` | `str` | Default `"TODAS"`; debe ser una especie activa (verificado contra M09) |
| `variables_sensoricas_asociadas` | `list[int]` | Entre 2 y 6 ids; deben existir y estar activos en el catálogo I3P-1; la combinación debe ser única por especie |
| `descripcion_clinica` | `str` | Mínimo 50 caracteres tras `strip()` |

**Response `PatologiaM04Response`:**

| Campo | Tipo |
|-------|------|
| `id_patologia` | `int` |
| `nombre_patologia` | `str` |
| `especie_aplicable` | `str` |
| `descripcion_clinica` | `str` |
| `es_base` | `bool` |
| `es_activo` | `bool` |
| `version_catalogo` | `int` |
| `variables_sensoricas_asociadas` | `list[PatologiaVariableResponse]` (`id_variable_ambiental`, `peso_evidencia`, `es_variable_critica`) |
| `fecha_creacion_m04` | `datetime` |
| `fecha_actualizacion` | `datetime \| None` |

---

#### `GET /prediccion/patologias/` — Listar catálogo

**Query params:**

| Param | Tipo | Notas |
|-------|------|-------|
| `especie_aplicable` | `str \| None` | `"TODAS"` o `id_especie` |
| `solo_activas` | `bool \| None` | — |
| `solo_base` | `bool \| None` | — |

**Response `PatologiaM04ListResponse`:** `{ total: int, items: list[PatologiaM04Response] }`

---

#### `GET /prediccion/patologias/{id_patologia}` — Detalle

**Response:** `PatologiaM04Response`

---

#### `PATCH /prediccion/patologias/{id_patologia}` — Editar

**Input `EditarPatologiaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `nombre_patologia` | `str` | — |
| `descripcion_clinica` | `str` | — |
| `variables_sensoricas_asociadas` | `list[int]` | Debe seguir cumpliendo las reglas del catálogo I3P-1 |
| `fecha_actualizacion` | `datetime \| None` | Control de concurrencia optimista (412 si no coincide) |

**Reglas adicionales:** una patología con `es_base=true` **no puede editarse** (`422 PATOLOGIA_BASE_INMUTABLE`); si `ModeloActivoPort.tiene_modelos_activos` retorna `true` (hoy siempre `False` por el stub), se rechaza con `409 PATOLOGIA_EN_USO_POR_MODELO`.

**Response:** `PatologiaM04Response`

---

#### `PATCH /prediccion/patologias/{id_patologia}/desactivar` — Desactivar

Misma verificación de "modelo en uso" que editar. **Response:** `PatologiaM04Response`

---

### Motor de Inferencia IA — `/prediccion/motor-ia`

> **Recurso RBAC:** `id_recurso = 41` (`configuracion_motor_ia`) — RF-65 CU-02

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(41, C)` | Admin, Vet | `ConfigurarMotorUseCase` |
| `GET` | `/` | `(41, R)` | Admin, Vet, Ing | `ConsultarMotorUseCase.listar` |
| `GET` | `/{tipo_modelo}` | `(41, R)` | Admin, Vet, Ing | `ConsultarMotorUseCase.obtener_por_tipo` |

#### `POST /prediccion/motor-ia/` — Configurar motor (upsert por `tipo_modelo`)

> Devuelve **201** si crea una configuración nueva para ese `tipo_modelo`, **200** si actualiza una existente.

**Input `ConfigurarMotorDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `tipo_modelo` | `str` | `ESPECIES_PEQUEÑAS`, `ESPECIES_MEDIANAS`, `ESPECIES_GRANDES`, `CONTAGIO` |
| `umbral_riesgo_alto` | `Decimal` | Entre 0.50 y 0.95 |
| `umbral_alerta_critica` | `Decimal` | — |
| `ventana_temporal_min` | `int` | — |
| `modo_ejecucion` | `str` | Default `"SERVIDOR"`; valores válidos `EDGE`, `SERVIDOR`, `HIBRIDO` |
| `w_factor_sanitario` | `Decimal` | Default `0.500` |
| `w_factor_ambiental` | `Decimal` | Default `0.300` |
| `w_factor_densidad` | `Decimal` | Default `0.200` |
| `id_version_modelo_activa` | `int \| None` | Opcional |
| `temp_min_config` / `temp_max_config` | `Decimal \| None` | Opcional |
| `hr_min_config` / `hr_max_config` | `Decimal \| None` | Opcional |
| `densidad_maxima_config` | `Decimal \| None` | Opcional |

**Response `ConfiguracionMotorIAResponse`:**

| Campo | Tipo |
|-------|------|
| `id_configuracion_motor` | `int` |
| `tipo_modelo` | `str` |
| `umbral_riesgo_alto` / `umbral_alerta_critica` | `Decimal` |
| `ventana_temporal_min` | `int` |
| `modo_ejecucion` | `str` |
| `id_version_modelo_activa` | `int \| None` |
| `config_version` | `int` |
| `w_factor_sanitario` / `w_factor_ambiental` / `w_factor_densidad` | `Decimal` |
| `temp_min_config` / `temp_max_config` / `hr_min_config` / `hr_max_config` / `densidad_maxima_config` | `Decimal \| None` |
| `es_activa` | `bool` |
| `id_usuario_responsable` | `int` |
| `fecha_creacion` | `datetime` |

---

#### `GET /prediccion/motor-ia/` — Listar configuraciones

**Response `ConfiguracionMotorIAListResponse`:** `{ total: int, items: list[ConfiguracionMotorIAResponse] }`

---

#### `GET /prediccion/motor-ia/{tipo_modelo}` — Obtener por tipo de modelo

**Response:** `ConfiguracionMotorIAResponse`

---

### Historial Diagnóstico — `/prediccion/historial`

> **Recurso RBAC:** `id_recurso = 42` (`historial_diagnostico`) — RF-67 CU-04
> ⚠️ El filtro de acceso por activo biológico (`ActivoBiologicoStubAdapter`) es un stub que siempre retorna `True` — ver sección de RBAC arriba.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/{id_activo_biologico}` | `(42, R)` | Admin, Prod, Vet | `ConsultarHistorialUseCase` |

#### `GET /prediccion/historial/{id_activo_biologico}` — Consultar historial (paginación por cursor)

**Query params:**

| Param | Tipo | Default | Restricciones |
|-------|------|---------|---------------|
| `fecha_inicio` | `date` | — | Requerido; no puede ser futuro ni posterior a `fecha_fin` |
| `fecha_fin` | `date` | — | Requerido; no puede ser futuro |
| `nivel_riesgo` | `int \| None` | — | 0–3 |
| `id_patologia` | `int \| None` | — | Filtra por patología del catálogo M04 |
| `incluir_alertas` | `bool` | `false` | Superpone alertas correlacionadas por `id_resultado_inferencia` |
| `cursor_paginacion` | `str \| None` | — | Token opaco basado en `(fecha_inferencia, id_resultado_inferencia)` |

**Response `HistorialDiagnosticoResponse`:**

| Campo | Tipo |
|-------|------|
| `eventos` | `list[EventoHistorialResponse]` (`id_evento`, `tipo_evento`, `id_activo_biologico`, `fecha_evento`, `id_resultado_inferencia`, `payload`) |
| `cursor_siguiente` | `str \| None` |
| `total_pagina` | `int` (máx. 50 por página) |

---

### Versiones de Modelos IA — `/prediccion/modelos`

> **Recurso RBAC:** `id_recurso = 43` (`version_modelo`) — RF-69 CU-05
> Máquina de estados: `EN_VALIDACION` → (auto-evaluación de métricas) → `APROBADO` / `RECHAZADO` → `ACTIVO` (vía `POST .../activar`) → `DEPRECADO`. `RECHAZADO` y `DEPRECADO` son terminales.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | **Sin RBAC** — protegido por `X-RF71-Internal-Key` | Ninguno (sistema RF-71) | `RegistrarVersionModeloUseCase` |
| `GET` | `/` | `(43, R)` | Admin, Vet | `ConsultarVersionesUseCase.listar` |
| `GET` | `/{id_version}` | `(43, R)` | Admin, Vet | `ConsultarVersionesUseCase.obtener_por_id` |
| `PATCH` | `/{id_version}/notas` | `(43, U)` | Admin, Vet | `RegistrarNotasVersionUseCase` |
| `POST` | `/{id_version}/activar` | `(43, E)` | Admin, Vet | `ActivarVersionModeloUseCase` |

#### `POST /prediccion/modelos` — Registro interno (multipart/form-data, sin sesión de usuario)

**Header requerido:** `X-RF71-Internal-Key: <clave>` (verificada dentro del use case; si falta o no coincide → `403`).

**Input `RegistrarVersionModeloDTO`** (form fields + archivo):

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `tipo_modelo` | `str` (Form) | `ESPECIES_PEQUEÑAS`, `ESPECIES_MEDIANAS`, `ESPECIES_GRANDES`, `CONTAGIO` |
| `hash_artefacto_sha256` | `str` (Form) | Debe coincidir con el SHA-256 real del archivo subido |
| `dataset_entrenamiento_hash` | `str` (Form) | — |
| `metricas_validacion` | `str` (Form, JSON) | Debe incluir: `f1_score_global`, `recall_clase_riesgo_alto`, `precision_global`, `accuracy`, `roc_auc_score`, `recall_por_clase`, `matriz_confusion` |
| `fecha_entrenamiento` | `datetime` (Form) | — |
| `compatibilidad_variables` | `str` (Form, JSON list) | Validado contra catálogo I3P-1 |
| `id_proceso_rf71` | `UUID` (Form) | — |
| `version_referencia` | `int \| None` (Form) | Opcional |
| `archivo_modelo` | `UploadFile` (File) | Máx. 500 MB; formato detectado por magic bytes: `ONNX` o `TENSORFLOW_SAVED_MODEL` |

**Evaluación automática:** al registrar, se auto-asigna `APROBADO` si `f1_score ≥ 0.80` **y** `recall_clase_riesgo_alto ≥ 0.85`; en caso contrario, `RECHAZADO` (con `detalle_validacion` explicando los defectos).

**Response:** `VersionModeloResponse`

---

#### `GET /prediccion/modelos/` — Listar versiones

**Query params:**

| Param | Tipo | Default | Restricciones |
|-------|------|---------|---------------|
| `tipo_modelo` | `str \| None` | — | — |
| `estado` | `str \| None` | — | `EN_VALIDACION`, `APROBADO`, `RECHAZADO`, `ACTIVO`, `DEPRECADO` |
| `limit` | `int` | `20` | 1–100 |
| `offset` | `int` | `0` | ≥ 0 |

**Response `VersionModeloListResponse`:** `{ total: int, items: list[VersionModeloResponse] }`

**`VersionModeloResponse`:** incluye `id_version_modelo`, `nombre_version`, `tipo_modelo`, `estado_version`, `formato_artefacto`, `tamanio_artefacto_bytes`, `hash_artefacto_sha256`, `dataset_entrenamiento_hash`, `id_proceso_rf71`, `version_referencia`, métricas (`f1_score`, `recall_clase_riesgo_alto`, `precision_modelo`, `accuracy`, `roc_auc_score`, `recall_por_clase`, `matriz_confusion`), `compatibilidad_variables`, `notas_validacion`, `detalle_validacion`, `esta_produccion`, `fecha_entrenamiento`, `fecha_registro`, `fecha_despliegue`.

---

#### `GET /prediccion/modelos/{id_version}` — Obtener por id

**Response:** `VersionModeloResponse`

---

#### `PATCH /prediccion/modelos/{id_version}/notas` — Registrar notas de validación clínica

**Input `RegistrarNotasVersionDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `notas_validacion` | `str` | No vacío tras `strip()` |

**Response:** `VersionModeloResponse`

---

#### `POST /prediccion/modelos/{id_version}/activar` — Activar versión (atómico)

Solo válido desde estado `APROBADO` y con `notas_validacion` ya registradas (si faltan → `422 NOTAS_VALIDACION_REQUERIDAS`). Transiciones desde `DEPRECADO`/`RECHAZADO` → `422 TRANSICION_ESTADO_INVALIDA` (son terminales). Al activar: `estado_version = ACTIVO`, `esta_produccion = true`, `fecha_despliegue = now()`.

**Response:** `VersionModeloResponse`

---

### OTA — `/prediccion/modelos/{id_version}/ota-status`, `/prediccion/despliegues`

> **Recurso RBAC:** `id_recurso = 44` (`ota_status`) — RF-70 CU-06

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/modelos/{id_version}/ota-status` | `(44, R)` | Admin, Ing | `ConsultarOtaStatusUseCase` |
| `GET` | `/despliegues` | `(44, R)` | Admin, Ing | `ListarDesplieguesUseCase` |

#### `GET /prediccion/modelos/{id_version}/ota-status` — Estado OTA de una versión

**Query params:** `id_dispositivo` (`int \| None`), `estado` (`str \| None`: `EXITOSO`, `FALLIDO`, `PENDIENTE`, `SIN_CAMBIOS`, `EN_PROCESO`).

**Response `OtaStatusResponse`:** `{ id_version_modelo: int, despliegues: list[DespliegueOtaResponse], total: int }`

---

#### `GET /prediccion/despliegues` — Listar despliegues con filtros

**Query params:** `id_version`, `id_dispositivo`, `estado` (opcionales), `limit` (default 20, máx. 100), `offset` (default 0).

**Response `DespliegueOtaListResponse`:** `{ total: int, items: list[DespliegueOtaResponse] }`

**`DespliegueOtaResponse`:** incluye `id_despliegue_ota`, `id_version_modelo`, `id_dispositivo_iot`, `tipo_modelo`, `modo_distribucion`, `estado_despliegue`, `hash_modelo_sha256`, `resultado_validacion_hash`, `id_version_modelo_anterior`, `rollback_ejecutado`, `intentos_descarga`, `max_reintentos`, `tamano_modelo_bytes`, `tamano_descargado_bytes`, `duracion_proceso_ms`, `ventana_inicio`, `ventana_fin`, `nivel_bateria_al_inicio`, `fecha_inicio`, `fecha_fin`, `motivo_fallo`.

---

### Retroalimentación Clínica — `/prediccion/retroalimentacion`

> **Recurso RBAC:** `id_recurso = 45` (`retroalimentacion_clinica`) — RF-72 CU-08
> ⚠️ **Hallazgo:** `modulo1.permisos` tiene también permiso `R` activo para Admin y Veterinario sobre este recurso, pero **no existe ningún endpoint `GET` implementado** en este router — solo `POST`. El permiso de lectura queda reservado para un futuro endpoint de consulta.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(45, C)` | Vet | `RegistrarRetroalimentacionUseCase` |

#### `POST /prediccion/retroalimentacion/` — Registrar retroalimentación clínica

**Input `RegistrarRetroalimentacionDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `id_resultado_inferencia` | `UUID` | Debe existir un resultado de inferencia con ese id |
| `id_activo_biologico` | `int` | Debe coincidir con el activo del resultado de inferencia referenciado |
| `estado_retroalimentacion` | `str` | `CORRECTO`, `PARCIAL`, `INCORRECTO`, `SIN_EVENTO` |
| `diagnosticos_reales` | `list[int] \| None` | Máx. 3; **obligatorio** si `estado` es `PARCIAL` o `INCORRECTO`; cada id debe ser una patología activa del catálogo M04 |
| `observaciones_clinicas` | `str \| None` | Opcional |
| `fuente_diagnostico` | `str \| None` | `OBSERVACION_DIRECTA`, `LABORATORIO`, `HISTORIAL_CLINICO`, `OTRO` |

**Reglas de negocio:** ventana de **90 días** desde `fecha_inferencia` (vencida → `422 FUERA_DE_VENTANA_TEMPORAL`); unicidad por `(id_resultado_inferencia, id_usuario_veterinario)` (`409 RETROALIMENTACION_DUPLICADA`); si hay diagnóstico requerido sin `fuente_diagnostico`, se marca `es_fuente_desconocida=true`; si otro veterinario ya registró retroalimentación contradictoria para el mismo resultado, se marca `es_conflicto_retroalimentacion=true` (no bloquea el registro).

**Response `RetroalimentacionClinicaResponse`:**

| Campo | Tipo |
|-------|------|
| `id_retroalimentacion` | `UUID` |
| `id_resultado_inferencia` | `UUID` |
| `id_activo_biologico` | `int` |
| `estado_retroalimentacion` | `str` |
| `diagnosticos_reales` | `list[int] \| None` |
| `fuente_diagnostico` | `str \| None` |
| `es_fuente_desconocida` | `bool` |
| `es_conflicto_retroalimentacion` | `bool` |
| `observaciones_clinicas` | `str \| None` |
| `id_usuario_veterinario` | `int` |
| `fecha_retroalimentacion` | `datetime` |
| `estado_registro` | `str` |

---

### Auditoría M04 — `/prediccion/auditoria`

> **Recurso RBAC:** `id_recurso = 46` (`auditoria_m04`) — RF-73 CU-09
> A diferencia de la auditoría de `src/configuration/` (accesible en lectura a todos los roles), **este recurso es exclusivo del rol Administrador** tanto para lectura como para exportación.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/` | `(46, R)` | Admin | `ConsultarAuditoriaM04UseCase.listar` |
| `GET` | `/exportar` | `(46, E)` | Admin | `ExportarAuditoriaM04UseCase.exportar` |
| `GET` | `/{id_evento}` | `(46, R)` | Admin | `ConsultarAuditoriaM04UseCase.obtener_por_id` |

#### `GET /prediccion/auditoria/` — Listar bitácora con filtros

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `tipo_evento` | `str \| None` | — | — |
| `fecha_desde` / `fecha_hasta` | `datetime \| None` | — | — |
| `id_usuario` | `int \| None` | — | Actor usuario |
| `id_sistema` | `str \| None` | — | Actor sistema (p. ej. proceso RF-71) |
| `id_referencia` | `str \| None` | — | Id de entidad referenciada |
| `severidad_evento` | `str \| None` | — | `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `pagina` | `int` | `1` | ≥ 1 |
| `por_pagina` | `int` | `50` | 1–200 |

**Response `AuditoriaM04ListResponse`:** `{ total: int, pagina: int, por_pagina: int, items: list[EventoAuditoriaM04Response] }`

**`EventoAuditoriaM04Response`:** `id_evento` (UUID), `tipo_evento`, `modulo`, `fecha_evento`, `tipo_actor` (`USUARIO`/`SISTEMA`), `correlacion_id`, `payload_evento`, `es_payload_truncado`, `severidad_evento`, `origen_registro`, `id_usuario`, `id_sistema`, `id_referencia`, `entidad_referencia`, `resultado_operacion`, `codigo_error`, `descripcion_error`, `origen_dato`, `version_modelo`, `latencia_ms`, `hash_evento`.

---

#### `GET /prediccion/auditoria/exportar` — Exportar CSV/JSON

**Query params:** los mismos filtros que el listado, más `formato` (`json` por defecto o `csv`).

**Response:** `StreamingResponse` con `Content-Disposition: attachment` (`auditoria_m04.csv` o `.json`).

---

#### `GET /prediccion/auditoria/{id_evento}` — Detalle de evento

**Response:** `EventoAuditoriaM04Response`

---

## Tabla de permisos RBAC usados

> Datos extraídos en vivo de `modulo1.permisos` (DB `sgpmp`) el 2026-07-23. Acciones: C=1 Crear, R=2 Leer, U=3 Actualizar, D=4 Eliminar, E=5 Ejecutar.

| `id_recurso` | Recurso | Admin | Productor | Veterinario | Ing. Campo | Contador |
|---|---|---|---|---|---|---|
| 18 | `patologias` | C,R,U,D | — | C,R,U,D | — | — |
| 41 | `configuracion_motor_ia` | C,R | — | C,R | R | — |
| 42 | `historial_diagnostico` | R | R | R | — | — |
| 43 | `version_modelo` | R,U,E | — | R,U,E | — | — |
| 44 | `ota_status` | R | — | — | R | — |
| 45 | `retroalimentacion_clinica` | R | — | C,R | — | — |
| 46 | `auditoria_m04` | R,E | — | — | — | — |

**No hay gaps de RBAC pendientes** para este módulo: los 7 recursos y todas las combinaciones (rol, recurso, acción) usadas por los routers ya existen y están activas en `modulo1.permisos`.

---

## Use Cases — resumen de firmas

| Clase | Método(s) principal(es) — parámetros |
|-------|----------------------------------------|
| `RegistrarPatologiaUseCase` | `execute(dto: RegistrarPatologiaDTO, id_usuario: int) → PatologiaM04` |
| `ConsultarPatologiasUseCase` | `execute(especie_aplicable, solo_activas, solo_base) → list[PatologiaM04]` |
| `ObtenerPatologiaUseCase` | `execute(id_patologia: int) → PatologiaM04` |
| `EditarPatologiaUseCase` | `execute(id_patologia: int, dto: EditarPatologiaDTO, id_usuario: int) → PatologiaM04` |
| `DesactivarPatologiaUseCase` | `execute(id_patologia: int, id_usuario: int) → PatologiaM04` |
| `ConfigurarMotorUseCase` | `execute(dto: ConfigurarMotorDTO, id_usuario: int) → tuple[ConfiguracionMotorIA, bool]` (bool = `es_nueva`) |
| `ConsultarMotorUseCase` | `listar() → list[ConfiguracionMotorIA]`; `obtener_por_tipo(tipo_modelo: str) → ConfiguracionMotorIA` |
| `ConsultarHistorialUseCase` | `execute(id_activo_biologico, fecha_inicio, fecha_fin, nivel_riesgo, id_patologia, incluir_alertas, cursor_paginacion, id_usuario, id_rol) → PaginaHistorial` |
| `RegistrarVersionModeloUseCase` | `execute(dto: RegistrarVersionModeloDTO, internal_key: str \| None) → VersionModelo` |
| `ConsultarVersionesUseCase` | `listar(tipo_modelo, estado, limit, offset, id_usuario) → tuple[list[VersionModelo], int]`; `obtener_por_id(id_version, id_usuario) → VersionModelo` |
| `RegistrarNotasVersionUseCase` | `execute(id_version: int, dto: RegistrarNotasVersionDTO, id_usuario: int) → VersionModelo` |
| `ActivarVersionModeloUseCase` | `execute(id_version: int, id_usuario: int) → VersionModelo` |
| `ConsultarOtaStatusUseCase` | `execute(id_version, id_dispositivo, estado, id_usuario) → tuple[int, list[DespliegueOta]]` |
| `ListarDesplieguesUseCase` | `execute(id_version, id_dispositivo, estado, limit, offset, id_usuario) → tuple[list[DespliegueOta], int]` |
| `RegistrarRetroalimentacionUseCase` | `execute(dto: RegistrarRetroalimentacionDTO, id_usuario_veterinario: int) → RetroalimentacionClinica` |
| `ConsultarAuditoriaM04UseCase` | `listar(tipo_evento, fecha_desde, fecha_hasta, id_usuario, id_sistema, id_referencia, severidad_evento, pagina, por_pagina, id_usuario_consultor) → tuple[list[EventoAuditoriaM04], int]`; `obtener_por_id(id_evento: UUID, id_usuario_consultor: int) → EventoAuditoriaM04` |
| `ExportarAuditoriaM04UseCase` | `exportar(tipo_evento, fecha_desde, fecha_hasta, id_usuario, id_sistema, id_referencia, severidad_evento, formato, id_usuario_exportador) → tuple[str \| bytes, str, str]` (contenido, media_type, filename) |
