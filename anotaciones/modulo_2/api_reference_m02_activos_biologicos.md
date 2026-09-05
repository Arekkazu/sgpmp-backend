# API Reference — `src/biological_assets/`

> Generado el 2026-07-22. Solo documentación — no subir al repositorio.
>
> **Todos los endpoints de este módulo requieren sesión activa.**
> El cliente debe enviar `Authorization: Bearer <token>` en cada request.
> No existe ningún endpoint público en `src/biological_assets/`.

---

## Prefijos de rutas

| Router | Prefijo | Tag Swagger |
|--------|---------|-------------|
| `activo_biologico_router.py` | `/activos-biologicos` | Activos Biológicos |

Es el único router del módulo (registrado en `main.py` como `activo_biologico_router`). Los 23 endpoints del módulo cuelgan de este único prefijo.

---

## Mecánica de RBAC en este módulo

### Cómo funciona `require_permission`

Cada endpoint declara `dependencies=[Depends(require_permission(id_recurso, id_accion))]`. Esa dependencia:

1. Se ejecuta **antes** del cuerpo del endpoint (FastAPI resuelve las dependencias en orden).
2. Consulta `modulo1.permisos` filtrando por `(id_rol_del_usuario, id_recurso, id_accion, es_activo=true)`.
3. Si no encuentra ninguna fila activa, lanza `AuthorizationError` (`code='ACCESO_DENEGADO'`) → HTTP **403**.
4. Si encuentra la fila, deja continuar la ejecución hacia el endpoint.

Esto implica que **sin un JWT válido no se llega ni siquiera a evaluar el permiso**: `require_permission` depende internamente de la misma resolución de sesión que `get_current_user`, así que un token ausente o inválido corta la petición con **401** antes de que el 403 de RBAC entre en juego. No hay ninguna ruta de este módulo que omita esa cadena.

### Los 3 recursos RBAC del módulo

| `id_recurso` | Nombre | Qué protege |
|---|---|---|
| **29** | `activos_biologicos` | Todas las operaciones sobre el activo biológico en sí: alta, consulta, edición, cambios de estado/fase, eventos, historial, transferencias, indicadores. Es, con diferencia, el recurso más usado del módulo (20 de los 23 endpoints). |
| **30** | `asociacion_sensor_activo` | Asociar un sensor IoT a un activo (`POST /{id_activo}/sensores`). Recurso separado porque sus reglas de actor son distintas a las del resto (ver tabla de permisos). |
| **31** | `bitacora_auditoria_m02` | Solo lectura de la bitácora de auditoría del módulo (`GET /auditoria`). Recurso de solo-R; no existe acción de escritura porque los registros de auditoría se generan automáticamente desde los demás use cases, nunca desde un endpoint dedicado. |

### Códigos de acción usados en este módulo

Mismos códigos estándar del proyecto (`modulo1.acciones`): **C**(1)=Crear, **R**(2)=Leer, **U**(3)=Actualizar, **D**(4)=Eliminar/Desactivar, **E**(5)=Ejecutar.

Particularidad de este módulo: la acción **E** no se reserva solo para "procesos especiales" — se reutiliza para cualquier operación que dispara una **transición de estado o de flujo** sobre el activo, aunque no sea un proceso especial formal:

- `PATCH /{id_activo}/estado` (cambio manual de estado) → E
- `POST /{id_activo}/fases` (avanzar/cambiar fase del ciclo productivo) → E
- `GET /{id_activo}/transferencias/disponibles` y `POST /{id_activo}/transferencias` → E

Mientras que **D** se reserva específicamente para el cierre de ciclo (`POST /{id_activo}/cierre`), que es la única operación "destructiva" (marca el activo como CERRADO/BAJA de forma difícilmente reversible).

### `UsuarioActual` — solo para auditoría, nunca para autorizar

`get_current_user` inyecta un `UsuarioActual` (`id_usuario, id_token, id_rol`) en casi todos los endpoints. Siguiendo la regla del proyecto, **ningún use case de este módulo verifica `id_rol`**: el `usuario_actual` se usa exclusivamente para poblar `id_usuario` en el activo/evento creado y para la bitácora de auditoría. La decisión de acceso ya quedó resuelta por `require_permission` antes de entrar al use case.

Nota sobre el trigger de BD: `trg_auditar_activo_biologico` exige `SET LOCAL app.usuario_id = ?` antes de cualquier INSERT/UPDATE sobre `modulo2.activos_biologicos`; el repositorio SQLAlchemy ejecuta esa sentencia al inicio de `guardar()`/`actualizar()` usando el `id_usuario` de la sesión JWT actual. Es decir, la sesión iniciada no solo protege el endpoint vía RBAC — es también la única fuente de `id_usuario` que llega hasta la capa de triggers de auditoría de la base de datos. Sin un usuario autenticado, ese trigger no tiene de dónde tomar el dato y la escritura fallaría.

### Nota sobre transferencias (posible restricción adicional no-RBAC)

`GET /{id_activo}/transferencias/disponibles` y `POST /{id_activo}/transferencias` exigen `(29, E)` por RBAC, y por tabla de permisos ese `E` lo tienen los 4 roles (Admin, Productor, Veterinario, Ingeniero). Sin embargo, `curls_m02_cu10_gestionar_transferencias_historial.md` documenta el error 403 como "rol sin permiso de ejecución **(solo admin y productor)**". Si ese comportamiento más restrictivo es real, no proviene de `modulo1.permisos` sino de una validación adicional dentro del use case — lo cual iría contra la regla del proyecto de no verificar roles en el use case. Vale la pena confirmarlo antes de asumir que Veterinario/Ingeniero pueden transferir activos en producción.

---

## Endpoints

### Registro y consulta general — recurso 29 (`activos_biologicos`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `POST` | `/` | `(29, C)` | Admin, Prod, Vet, Ing | `RegistrarActivoBiologicoUseCase` |
| `GET` | `/` | `(29, R)` | Admin, Prod, Vet, Ing | `ListarActivosUseCase` |
| `GET` | `/{id_activo}` | `(29, R)` | Admin, Prod, Vet, Ing | `ConsultarActivoUseCase` |
| `PATCH` | `/{id_activo}` | `(29, U)` | Admin, Prod, Ing | `ActualizarActivoIndividualUseCase` |

#### `POST /activos-biologicos/` — Registrar activo biológico

**Input `RegistrarActivoBiologicoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `tipo_activo` | `str` | Debe ser `'INDIVIDUAL'` o `'POBLACIONAL'` |
| `id_especie` | `int` | Obligatorio, FK a especie |
| `fecha_inicio_ciclo` | `date` | Obligatorio; no puede ser futura ni anterior a `1970-01-01` |
| `detalles_procedencia` | `str \| None` | Opcional |
| `origen_financiero` | `str` | Uno de `'compra','nacimiento','donacion','transferencia_interna'` |
| `costo_adquisicion` | `Decimal \| None` | Obligatorio y `> 0` si `origen_financiero` es `compra`/`donacion`; debe ser `None` si es `nacimiento` |
| `soporte_documental` | `str \| None` | Obligatorio si `origen_financiero` es `compra`/`donacion`; debe ser `None` si es `nacimiento` |
| `id_infraestructura` | `int` | Obligatorio |
| `atributos_dinamicos` | `dict \| None` | Opcional |
| `identificador` | `str \| None` | Obligatorio si `INDIVIDUAL`; prohibido si `POBLACIONAL` |
| `raza` | `str \| None` | Obligatorio si `INDIVIDUAL`; prohibido si `POBLACIONAL` |
| `sexo` | `str \| None` | Obligatorio si `INDIVIDUAL`; prohibido si `POBLACIONAL` |
| `fecha_nacimiento` | `datetime \| None` | Obligatorio si `INDIVIDUAL`; prohibido si `POBLACIONAL` |
| `peso_inicial` | `Decimal \| None` | Opcional |
| `cantidad_inicial` | `int \| None` | Obligatorio y `>0` si `POBLACIONAL`; prohibido si `INDIVIDUAL` |
| `peso_promedio_inicial` | `Decimal \| None` | Opcional |

Validadores de modelo: `validar_segun_tipo` (reglas INDIVIDUAL/POBLACIONAL de arriba), `validar_fecha_inicio_ciclo`, `validar_origen_financiero`.

**Response `ActivoBiologicoResponse`** (201):

| Campo | Tipo |
|-------|------|
| `id_activo_biologico` | `int` |
| `id_especie` | `int` |
| `tipo` | `str` |
| `identificador` | `str \| None` |
| `fecha_inicio_ciclo` | `date \| None` |
| `detalles_procedencia` | `str \| None` |
| `origen_financiero` | `str` |
| `costo_adquisicion` | `Decimal \| None` |
| `soporte_documental` | `str \| None` |
| `descripcion` | `str \| None` |
| `id_infraestructura` | `int` |
| `atributos_dinamicos` | `dict \| None` |
| `id_estado` | `int` |
| `nombre_estado` | `str \| None` |
| `id_usuario` | `int` |
| `fecha_creacion` | `datetime \| None` |
| `detalle_individual` | `DetalleIndividualResponse \| None` |
| `detalle_poblacional` | `DetallePoblacionalResponse \| None` |

**`DetalleIndividualResponse`:** `id_detalle: int \| None`, `raza: str`, `sexo: str`, `fecha_nacimiento: datetime`, `peso_inicial: Decimal \| None`, `fecha_creacion: datetime \| None`.

**`DetallePoblacionalResponse`:** `id_detalle: int \| None`, `cantidad_inicial: int`, `cantidad_actual: int \| None`, `peso_promedio_inicial: Decimal \| None`, `peso_promedio: Decimal \| None`, `biomasa_total: Decimal \| None`, `densidad: Decimal \| None`.

---

#### `GET /activos-biologicos/` — Listar activos biológicos (con filtros y paginación)

Endpoint de colección para el listado de activos. Ruta canónica **sin barra final**
(igual que `POST /`); `/activos-biologicos/` redirige 307 a `/activos-biologicos`.
Devuelve items con el mismo `ActivoBiologicoResponse` de `GET /{id_activo}` dentro de
un sobre paginado estilo módulo-2 (mismo shape que `/historial`).

**Query params** (todos opcionales):

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `tipo` | `str \| None` | — | `INDIVIDUAL` \| `POBLACIONAL` (case-insensitive, se normaliza a mayúsculas) |
| `id_especie` | `int \| None` | — | `≥1` |
| `id_estado` | `int \| None` | — | `≥1` |
| `id_infraestructura` | `int \| None` | — | `≥1` |
| `pagina` | `int` | `1` | `≥1` |
| `page_size` | `int` | `20` | `1–100` |

Sin filtros de fecha ni búsqueda por texto: los filtros son igualdad exacta por id +
`tipo`. `ListarActivosUseCase` es una lectura pura (sin `commit`, sin auditoría);
orden por `fecha_creacion DESC, id_activo_biologico DESC`.

**Response `ActivosPaginadosResponse`** (200):

| Campo | Tipo |
|-------|------|
| `total_registros` | `int` |
| `pagina_actual` | `int` |
| `total_paginas` | `int` |
| `registros_por_pagina` | `int` |
| `registros` | `list[ActivoBiologicoResponse]` |

Cada item de `registros` es un `ActivoBiologicoResponse` completo (ver `POST /` arriba).

**Errores** (body estándar `{ error_code, message, fields, timestamp }`):

| HTTP | `error_code` | Cuándo |
|------|--------------|--------|
| 401 | `TOKEN_REQUERIDO` / `TOKEN_REVOCADO` / `SESION_EXPIRADA_INACTIVIDAD` | Sin token, revocado o sesión expirada |
| 403 | `ACCESO_DENEGADO` | Rol sin permiso `(29, R)` (ej. Contador) |
| 400 | `PARAMETROS_INVALIDOS` | `tipo` fuera de `{INDIVIDUAL, POBLACIONAL}` |
| 400 | `VAL_ENTRADA` | `pagina`/`page_size`/`id_*` fuera de rango o no numérico |

> Nota: aunque la mayoría de endpoints de lectura del módulo declaran `422` en su
> tabla `responses`, los errores de parámetros de este módulo se traducen realmente a
> **400** (`ValidationError` de dominio y el handler de `RequestValidationError`
> ambos devuelven 400). Este endpoint declara `400` en su `responses` para reflejar
> el comportamiento real.

---

#### `GET /activos-biologicos/{id_activo}` — Consultar activo

Sin input adicional (path param `id_activo: int`).

**Response:** `ActivoBiologicoResponse` (mismo esquema de arriba).

---

#### `PATCH /activos-biologicos/{id_activo}` — Actualizar activo individual

**Input `ActualizarActivoIndividualDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `raza` | `str \| None` | Opcional |
| `sexo` | `str \| None` | Opcional |
| `fecha_nacimiento` | `datetime \| None` | Opcional |
| `peso_inicial` | `Decimal \| None` | Opcional |

Validador `al_menos_un_campo`: al menos uno de los 4 campos debe venir con valor (si no, 422).

**Response:** `ActivoBiologicoResponse`

---

### Estado y ciclo de vida — recurso 29 (`activos_biologicos`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `PATCH` | `/{id_activo}/estado` | `(29, E)` | Admin, Prod, Vet, Ing | `CambiarEstadoUseCase` |
| `POST` | `/{id_activo}/cierre` | `(29, D)` | Admin, Prod, Vet | `CerrarCicloUseCase` |
| `POST` | `/{id_activo}/fases` | `(29, E)` | Admin, Prod, Vet, Ing | `CambiarFaseUseCase` |
| `GET` | `/{id_activo}/fases` | `(29, R)` | Admin, Prod, Vet, Ing | `ConsultarHistorialFasesUseCase` |

#### `PATCH /activos-biologicos/{id_activo}/estado` — Cambiar estado

**Input `CambiarEstadoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `estado_nuevo` | `str` | Uno de `ACTIVO, INACTIVO, EN_TRATAMIENTO, AISLADO, CERRADO, BAJA` |
| `fecha_cambio_estado` | `date` | No puede ser futura |
| `motivo_cambio` | `str` | No vacío (stripped) |

`estado_nuevo` se traduce internamente a `id_estado_nuevo` vía `{'ACTIVO':1,'INACTIVO':2,'EN_TRATAMIENTO':3,'AISLADO':4,'CERRADO':5,'BAJA':6}`. La transición se valida contra la máquina de estados — ver [Máquina de estados](#máquina-de-estados-estadoactivo) más abajo.

**Response `CambioEstadoResponse`:**

| Campo | Tipo |
|-------|------|
| `id_activo_biologico` | `int` |
| `estado_anterior` | `int` |
| `estado_nuevo` | `int` |
| `historial` | `HistoricoEstadoResponse` |

**`HistoricoEstadoResponse`:** `id_historico: int \| None`, `id_activo_biologico: int`, `id_estado_anterior: int`, `nombre_estado_anterior: str \| None`, `id_estado_nuevo: int`, `nombre_estado_nuevo: str \| None`, `fecha_cambio: datetime`, `motivo_cambio: str \| None`, `modulo_origen: str`, `id_usuario: int`.

---

#### `POST /activos-biologicos/{id_activo}/cierre` — Cerrar ciclo productivo

**Input `CerrarCicloDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `fecha_cierre` | `date` | No puede ser futura |
| `motivo_cierre` | `str` | No vacío (stripped) |
| `descripcion_cierre` | `str \| None` | Opcional |

**Response `CierreActivoResponse`** (200):

| Campo | Tipo |
|-------|------|
| `id_activo_biologico` | `int` |
| `estado` | `str` |
| `fecha_cierre` | `date` |
| `motivo_cierre` | `str` |
| `fase_finalizada` | `bool` |

---

#### `POST /activos-biologicos/{id_activo}/fases` — Cambiar fase del ciclo productivo

**Input `CambiarFaseDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_ciclo_productiva` | `int` | Obligatorio |
| `motivo_cambio` | `str \| None` | Opcional |
| `fecha_inicio` | `datetime \| None` | Opcional |

**Response `GestionFaseResponse`** (201):

| Campo | Tipo |
|-------|------|
| `id_gestion_fases` | `int \| None` |
| `id_activo_biologico` | `int` |
| `id_ciclo_productiva` | `int` |
| `nombre_ciclo` | `str` |
| `nombre_fase_actual` | `str \| None` |
| `paso_actual` | `int \| None` |
| `total_pasos` | `int \| None` |
| `fecha_inicio` | `datetime` |
| `fecha_finalizacion` | `datetime \| None` |
| `es_activa` | `bool` |
| `motivo_cambio` | `str \| None` |

---

#### `GET /activos-biologicos/{id_activo}/fases` — Historial de fases

Sin input adicional.

**Response `HistorialFasesResponse`:** `id_activo_biologico: int`, `fases: list[GestionFaseResponse]`.

---

### Eventos biológicos — recurso 29 (`activos_biologicos`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `GET` | `/{id_activo}/eventos` | `(29, R)` | Admin, Prod, Vet, Ing | `ConsultarEventosUseCase` |
| `POST` | `/{id_activo}/eventos/crecimiento` | `(29, C)` | Admin, Prod, Vet, Ing | `RegistrarEventoCrecimientoUseCase` |
| `POST` | `/{id_activo}/eventos/baja` | `(29, C)` | Admin, Prod, Vet, Ing | `RegistrarEventoBajaUseCase` |
| `POST` | `/{id_activo}/eventos/sanitario` | `(29, C)` | Admin, Prod, Vet, Ing | `RegistrarEventoSanitarioUseCase` |
| `POST` | `/{id_activo}/eventos/productivo` | `(29, C)` | Admin, Prod, Vet, Ing | `RegistrarEventoProductivoUseCase` |
| `POST` | `/{id_activo}/eventos/reproductivo` | `(29, C)` | Admin, Prod, Vet, Ing | `RegistrarEventoReproductivoUseCase` |

> `ConsultarEventosUseCase` lanza `BusinessRuleError` si el activo no es de tipo `POBLACIONAL` — este endpoint de historial de eventos "en lote" solo aplica a lotes.

#### `GET /activos-biologicos/{id_activo}/eventos` — Historial de eventos (solo POBLACIONAL)

**Response `HistorialEventosResponse`:** `id_activo_biologico: int`, `total: int`, `eventos: list[EventoActivoResponse]` — ver [`EventoActivoResponse`](#eventoactivoresponse--composición) más abajo.

---

#### `POST /activos-biologicos/{id_activo}/eventos/crecimiento` — Registrar evento de crecimiento

**Input `RegistrarEventoCrecimientoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `tipo_medicion` | `str` | Uno de `PESO, TALLA, BIOMASA` |
| `valor_medicion` | `Decimal` | `> 0` |
| `unidad_medida` | `str` | Debe pertenecer al conjunto válido para `tipo_medicion`: `PESO→{kg,gr,lb}`, `TALLA→{cm,m}`, `BIOMASA→{kg/m2}` |
| `tipo_agregacion` | `str \| None` | Opcional (solo aplica a POBLACIONAL) |
| `frecuencia` | `str \| None` | Opcional (solo aplica a POBLACIONAL) |
| `nuevo_peso_promedio` | `Decimal \| None` | Opcional; `>0` si se envía |
| `cantidad_medida` | `int \| None` | Opcional; `>0` si se envía |
| `fecha` | `datetime \| None` | Opcional |
| `descripcion` | `str \| None` | Opcional |

**Response `RegistrarEventoCrecimientoResponse`** (201): `evento: EventoActivoResponse`, `fase_avanzada: bool = False` (indica si el registro disparó un avance automático de fase).

---

#### `POST /activos-biologicos/{id_activo}/eventos/baja` — Registrar baja

**Input `RegistrarEventoBajaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `tipo_baja` | `str` | Uno de `muerte, venta, sacrificio, perdida, descarte_sanitario` |
| `fecha_baja` | `date` | Obligatorio |
| `motivo_baja` | `str` | No vacío (stripped) |
| `cantidad_afectada` | `int \| None` | Solo para LOTE (baja parcial); `None` = baja total; `>0` si se envía |

**Response:** `EventoActivoResponse` (201).

---

#### `POST /activos-biologicos/{id_activo}/eventos/sanitario` — Registrar evento sanitario

**Input `RegistrarEventoSanitarioDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `tipo` | `str` | Uno de `VACUNACION, TRATAMIENTO, DIAGNOSTICO, CONTROL_PREVENTIVO` |
| `diagnostico` | `str \| None` | Obligatorio si `tipo=DIAGNOSTICO` |
| `medicamento` | `str \| None` | Obligatorio (junto con `dosis`) si `tipo` en `{VACUNACION,TRATAMIENTO}` |
| `dosis` | `Decimal \| None` | Ver regla anterior |
| `unidad_dosis` | `str \| None` | Opcional |
| `frecuencia` | `int \| None` | Obligatorio (junto con `duracion`) si `tipo=TRATAMIENTO` |
| `duracion` | `int \| None` | Obligatorio si `tipo=TRATAMIENTO` |
| `observaciones` | `str \| None` | Obligatorio si `tipo=CONTROL_PREVENTIVO` |
| `fecha` | `datetime \| None` | Opcional |
| `descripcion` | `str \| None` | Opcional |
| `solicitar_estado` | `'EN_TRATAMIENTO' \| 'AISLADO' \| None` | Solo permitido si `tipo` en `{TRATAMIENTO, CONTROL_PREVENTIVO}` |

Validador `validar_campos_por_tipo` aplica todas las reglas condicionales de arriba.

**Response `RegistrarEventoSanitarioResponse`** (201): `evento: EventoActivoResponse`, `cambio_estado: HistoricoEstadoResponse \| None` (si `solicitar_estado` disparó un cambio de estado).

---

#### `POST /activos-biologicos/{id_activo}/eventos/productivo` — Registrar evento productivo

**Input `RegistrarEventoProductivoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `tipo_producto` | `str` | No vacío (stripped, normalizado a mayúsculas) |
| `cantidad_producida` | `Decimal` | `> 0` |
| `unidad_medida` | `str` | No vacío (stripped) |
| `fecha_evento` | `date` | Obligatorio |
| `condiciones_produccion` | `str \| None` | Opcional |
| `observaciones` | `str \| None` | Opcional |

**Response:** `EventoActivoResponse` (201).

---

#### `POST /activos-biologicos/{id_activo}/eventos/reproductivo` — Registrar evento reproductivo

**Input `RegistrarEventoReproductivoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `categoria` | `Literal['servicio','inseminacion','diagnostico','parto','aborto','nacimiento']` | Obligatorio |
| `resultado` | `Literal['exitoso','fallido']` | Obligatorio |
| `fecha` | `datetime \| None` | Opcional |
| `id_padre` | `int \| None` | `Field(gt=0)` |
| `id_madre` | `int \| None` | `Field(gt=0)` |
| `numero_crias` | `int` | `Field(default=0, ge=0)` |
| `descripcion` | `str \| None` | Opcional |

**Response `RegistrarEventoReproductivoResponse`** (201): `evento: EventoActivoResponse`.

---

### `EventoActivoResponse` — composición

Todas las respuestas de eventos anteriores usan (directa o envuelta) este schema:

| Campo | Tipo |
|-------|------|
| `id_eventos` | `int` |
| `id_activo_biologico` | `int` |
| `fecha` | `datetime` |
| `descripcion` | `str \| None` |
| `id_usuario` | `int \| None` |
| `crecimiento` | `EventoCrecimientoResponse \| None` |
| `baja` | `EventoBajaResponse \| None` |
| `sanitario` | `EventoSanitarioResponse \| None` |
| `productivo` | `EventoProductivoResponse \| None` |
| `reproductivo` | `EventoReproductivoResponse \| None` |

Solo uno de los 5 sub-objetos viene poblado según el tipo de evento; los demás son `null`.

- **`EventoCrecimientoResponse`:** `tipo_medicion, valor_medicion, unidad_medida, tipo_agregacion=None, frecuencia=None, nuevo_peso_promedio=None, cantidad_medida=None`.
- **`EventoBajaResponse`:** `cantidad_afectada: int, tipo: str, motivo_baja: str \| None`.
- **`EventoSanitarioResponse`:** `tipo, diagnostico, medicamento, dosis, unidad_dosis, frecuencia, duracion, observaciones` (todos opcionales salvo `tipo`).
- **`EventoProductivoResponse`:** `cantidad: Decimal, id_metrica_produccion: int, id_ciclo_productivo: int, condiciones: str \| None, tipo_producto: str \| None=None, unidad_medida: str \| None=None`.
- **`EventoReproductivoResponse`:** `categoria: str, resultado: str, numero_cria: int, id_padre: int \| None, id_madre: int \| None`.

---

### Infraestructura, historial y transferencias — recurso 29 (`activos_biologicos`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `GET` | `/{id_activo}/infraestructura` | `(29, R)` | Admin, Prod, Vet, Ing | `ConsultarAsociacionUseCase` |
| `GET` | `/{id_activo}/historial` | `(29, R)` | Admin, Prod, Vet, Ing | `ConsultarHistorialUseCase` |
| `GET` | `/{id_activo}/ficha-integral` | `(29, R)` | Admin, Prod, Vet, Ing | `ConsultarFichaIntegralUseCase` |
| `GET` | `/{id_activo}/transferencias/disponibles` | `(29, E)` | Admin, Prod, Vet, Ing¹ | `RegistrarTransferenciaUseCase.listar_infraestructuras_disponibles` |
| `POST` | `/{id_activo}/transferencias` | `(29, E)` | Admin, Prod, Vet, Ing¹ | `RegistrarTransferenciaUseCase.execute` |

> ¹ Ver la [nota sobre transferencias](#nota-sobre-transferencias-posible-restricción-adicional-no-rbac) — el RBAC en DB habilita a los 4 roles, pero la documentación de curls (CU10) sugiere que en la práctica solo Admin y Productor logran transferir.

#### `GET /activos-biologicos/{id_activo}/infraestructura` — Consultar asociación a infraestructura

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `tipo_consulta` | `Literal['ACTIVA','HISTORIAL']` | `'ACTIVA'` | `ACTIVA` devuelve solo la asociación vigente; `HISTORIAL` devuelve la lista completa |

**Response `ConsultaAsociacionResponse`:**

| Campo | Tipo |
|-------|------|
| `tipo_consulta` | `str` |
| `id_activo_biologico` | `int` |
| `asociacion_activa` | `AsociacionInfraestructuraResponse \| None` |
| `historial` | `list[AsociacionInfraestructuraResponse] \| None` |

**`AsociacionInfraestructuraResponse`:** `id_historial: int, id_activo_biologico: int, id_infraestructura: int, nombre_infraestructura: str, tipo_infraestructura: str, fecha_inicio: datetime, fecha_fin: datetime \| None`.

---

#### `GET /activos-biologicos/{id_activo}/historial` — Historial consolidado del activo

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `fecha_inicio` | `date \| None` | — | Opcional |
| `fecha_fin` | `date \| None` | — | Opcional; debe ser `>= fecha_inicio` |
| `categoria_evento` | `str \| None` | — | Uno de `ESTADO, FASE, EVENTO_BIOLOGICO, CRECIMIENTO, SANITARIO, REPRODUCTIVO, PRODUCTIVO, BAJA, TRANSFERENCIA` (uppercased antes de validar) |
| `pagina` | `int` | `1` | `≥1` |
| `page_size` | `int` | `20` | `1–100` |

**Response `HistorialActivoResponse`:**

| Campo | Tipo |
|-------|------|
| `id_activo_biologico` | `int` |
| `total_registros` | `int` |
| `pagina_actual` | `int` |
| `total_paginas` | `int` |
| `registros_por_pagina` | `int` |
| `registros` | `list[RegistroHistorialResponse]` |

**`RegistroHistorialResponse`:** `categoria: str, fecha_evento: datetime, descripcion: str, detalle_especifico: dict, usuario_responsable: str, modulo_origen: str`.

---

#### `GET /activos-biologicos/{id_activo}/ficha-integral` — Ficha integral del activo

Sin query params.

**Response `FichaIntegralResponse`:**

| Campo | Tipo |
|-------|------|
| `id_activo_biologico` | `int` |
| `identificador` | `str \| None` |
| `tipo` | `str` |
| `especie` | `str` |
| `fecha_registro` | `date \| None` |
| `dias_en_sistema` | `int \| None` |
| `estado_actual` | `str` |
| `infraestructura_asociada` | `str \| None` |
| `fase_productiva_activa` | `str \| None` |
| `raza` | `str \| None` |
| `sexo` | `str \| None` |
| `fecha_nacimiento` | `date \| None` |
| `peso_actual` | `Decimal \| None` |
| `unidad_peso` | `str \| None` |
| `fecha_ultimo_peso` | `date \| None` |
| `cantidad_actual` | `int \| None` |
| `biomasa_total` | `Decimal \| None` |
| `densidad` | `Decimal \| None` |
| `eventos_sanitarios` | `list[dict]` |
| `eventos_productivos` | `list[dict]` |
| `eventos_crecimiento` | `list[dict]` |
| `eventos_reproductivos` | `list[dict]` |
| `indicadores` | `list[dict]` |
| `advertencias` | `list[str]` |

Si el activo está en `CERRADO`/`BAJA` con fase activa, o si las vistas subyacentes no devuelven datos, `advertencias` explica la inconsistencia en vez de fallar con error.

---

#### `GET /activos-biologicos/{id_activo}/transferencias/disponibles` — Infraestructuras destino compatibles

Sin query params. Excluye la infraestructura actual del activo; solo incluye infraestructuras activas.

**Response:** `list[InfraestructuraDisponibleResponse]` — `id_infraestructura: int, nombre: str, tipo: str, capacidad_maxima: int \| None, id_especie: int \| None`.

---

#### `POST /activos-biologicos/{id_activo}/transferencias` — Registrar transferencia interna

**Input `RegistrarTransferenciaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `infraestructura_origen_id` | `int` | Obligatorio |
| `infraestructura_destino_id` | `int` | Obligatorio |
| `fecha_transferencia` | `date` | No puede ser posterior a hoy |
| `motivo_transferencia` | `str` | No vacío (stripped) |

**Response `TransferenciaResponse`** (201): `id_movimiento: int \| None, id_activo_biologico: int, infraestructura_origen: str, infraestructura_destino: str, fecha_transferencia: datetime, motivo_transferencia: str, mensaje: str`.

---

### Sensores IoT — recurso 30 (`asociacion_sensor_activo`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `POST` | `/{id_activo}/sensores` | `(30, C)` | Admin, Ing | `AsociarSensorActivoUseCase` |

> Solo lectura (`R`) para Productor y Veterinario sobre este recurso — no aparece ningún endpoint `GET` dedicado en este router para consultarlo directamente (la lectura de asociaciones de sensor se expone desde el módulo `configuration`).

#### `POST /activos-biologicos/{id_activo}/sensores` — Asociar sensor IoT al activo

**Input `AsociarSensorActivoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `tipo_activo` | `Literal['INDIVIDUAL','LOTE']` | Obligatorio |
| `tipo_asociacion` | `Literal['DIRECTA','AMBIENTAL','POBLACIONAL']` | Obligatorio |
| `dispositivo_iot_id` | `int` | Obligatorio |
| `sensor_id` | `int` | Obligatorio |
| `id_infraestructura` | `int` | Obligatorio |
| `fecha_inicio` | `datetime \| None` | Opcional |
| `fecha_fin` | `datetime \| None` | Opcional |
| `motivo` | `str \| None` | Opcional; vacío se normaliza a `None` |

Una segunda llamada con el mismo `sensor_id` + activo cierra la asociación anterior (marca `SUPERADA`) y crea una nueva.

**Response `AsociacionSensorActivoResponse`** (201):

| Campo | Tipo |
|-------|------|
| `id_asociacion_activo_sensor` | `int` |
| `id_activo_biologico` | `int` |
| `tipo_activo` | `str` |
| `tipo_asociacion` | `str` |
| `dispositivo_iot_id` | `int` |
| `sensor_id` | `int` |
| `id_infraestructura` | `int` |
| `fecha_inicio` | `datetime` |
| `fecha_fin` | `datetime \| None` |
| `estado_asociacion` | `str` |
| `motivo` | `str \| None` |
| `advertencia` | `str \| None` |

---

### Indicadores y datos consolidados — recurso 29 (`activos_biologicos`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `GET` | `/{id_activo}/indicadores` | `(29, R)` | Admin, Prod, Vet, Ing | `ConsultarIndicadoresUseCase` |
| `GET` | `/{id_activo}/datos-consolidados` | `(29, R)` | Admin, Prod, Vet, Ing | `ConsultarDatosConsolidadosUseCase` |

#### `GET /activos-biologicos/{id_activo}/indicadores` — Consultar indicadores zootécnicos

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `fecha_inicio` | `date \| None` | — | Opcional |
| `fecha_fin` | `date \| None` | — | Opcional; debe ser `>= fecha_inicio` |
| `tipo_indicador` | `str` | `'TODOS'` | Uno de `CRECIMIENTO, PRODUCCION, SANITARIO, EFICIENCIA, TODOS` |

**Response `IndicadoresActivoResponse`:** `id_activo_biologico: int, tipo_activo: str, indicadores: list[IndicadorZootecnicoResponse], advertencias: list[str]`.

**`IndicadorZootecnicoResponse`:** `tipo: str, valor: Decimal \| None, unidad: str, periodo_inicio: date \| None, periodo_fin: date \| None, variables_usadas: dict, fecha_calculo: datetime, disponible: bool`.

---

#### `GET /activos-biologicos/{id_activo}/datos-consolidados` — Datos consolidados del activo

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `tipo_dato` | `str` | `'todos'` | Uno de `eventos, fases, estado, metricas, todos` (lowercased) |
| `fecha_inicio` | `date \| None` | — | Opcional |
| `fecha_fin` | `date \| None` | — | Opcional |
| `pagina` | `int` | `1` | `≥1` |
| `page_size` | `int` | `20` | `1–100` |

**Response `DatosConsolidadosResponse`:**

| Campo | Tipo |
|-------|------|
| `id_activo_biologico` | `int` |
| `identificador` | `str \| None` |
| `tipo_activo` | `str` |
| `especie` | `str` |
| `estado_actual` | `str` |
| `infraestructura_asociada` | `str \| None` |
| `fase_productiva_activa` | `str \| None` |
| `historial_eventos` | `list[dict]` |
| `historial_fases` | `list[dict]` |
| `historico_estados` | `list[dict]` |
| `metricas_actuales` | `dict` |
| `total_registros` | `int` |
| `pagina_actual` | `int` |
| `total_paginas` | `int` |
| `registros_por_pagina` | `int` |
| `fecha_generacion` | `datetime` |

---

### Auditoría — recurso 31 (`bitacora_auditoria_m02`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `GET` | `/auditoria` | `(31, R)` | Admin, Prod, Vet, Cont | `ConsultarBitacoraUseCase` |

> Único endpoint de solo-lectura sobre este recurso; nótese que **Ingeniero de Campo no tiene acceso** (no aparece en `modulo1.permisos` para `id_recurso=31`), a diferencia del resto de endpoints del módulo donde Ingeniero sí participa.

#### `GET /activos-biologicos/auditoria` — Consultar bitácora de auditoría

**Query params** (construyen `ConsultarBitacoraDTO`):

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `rf_origen` | `str \| None` | — | Opcional, ej. `RF40`, `RF45` |
| `tipo_evento` | `str \| None` | — | Opcional |
| `id_activo_biologico` | `int \| None` | — | Opcional |
| `clasificacion_biologica` | `str \| None` | — | Opcional, ej. `TRANSFORMACION_BIOLOGICA` |
| `resultado` | `str \| None` | — | Opcional, ej. `EXITOSO`, `FALLIDO` |
| `severidad_log` | `str \| None` | — | Opcional, ej. `INFO`, `ERROR` |
| `fecha_inicio` | `datetime \| None` | — | Opcional, ISO-8601 UTC |
| `fecha_fin` | `datetime \| None` | — | Opcional, ISO-8601 UTC |
| `pagina` | `int` | `1` | `≥1` |
| `page_size` | `int` | `20` | `1–100` |

**Response `BitacoraAuditoriaResponse`:**

| Campo | Tipo |
|-------|------|
| `total_registros` | `int` |
| `pagina_actual` | `int` |
| `total_paginas` | `int` |
| `registros_por_pagina` | `int` |
| `registros` | `list[EventoAuditoriaResponse]` |

**`EventoAuditoriaResponse`:** `id_bitacora: int, id_evento: str, rf_origen: str, tipo_evento: str, clasificacion_biologica: str, id_activo_biologico: int \| None, tipo_activo: str \| None, timestamp_evento: datetime, timestamp_registro: datetime, resultado: str, descripcion: str \| None, detalle_tecnico: dict \| None, id_usuario_responsable: int \| None, modulo_consumidor: str \| None, severidad_log: str, id_evento_correlacionado: str \| None, hash_integridad: str, registro_incompleto: bool`.

`hash_integridad` se calcula en Python (SHA-256) antes del INSERT — no hay trigger de DB para esto. Errores al registrar auditoría se absorben (`except Exception: pass`) para no bloquear la operación principal que originó el evento.

---

## Máquina de estados (`EstadoActivo`)

`CambiarEstadoUseCase` valida toda transición contra `TRANSICIONES_VALIDAS` (`domain/value_objects/estado_activo.py`):

| Estado (`id`) | Puede transicionar a |
|---|---|
| `ACTIVO` (1) | `INACTIVO, EN_TRATAMIENTO, AISLADO, CERRADO, BAJA` |
| `INACTIVO` (2) | `ACTIVO, EN_TRATAMIENTO, CERRADO, BAJA` |
| `EN_TRATAMIENTO` (3) | `ACTIVO, INACTIVO, AISLADO, CERRADO, BAJA` |
| `AISLADO` (4) | `ACTIVO, INACTIVO, EN_TRATAMIENTO, CERRADO, BAJA` |
| `CERRADO` (5) | `BAJA` (único destino) |
| `BAJA` (6) | — (estado terminal, sin transiciones) |

Los estados que **permiten registrar eventos** (`_ESTADOS_PERMITEN_EVENTOS` en `_event_validations.py`) son únicamente `ACTIVO`, `EN_TRATAMIENTO` y `AISLADO` (ids 1, 3, 4). Cualquier evento (`crecimiento/baja/sanitario/productivo/reproductivo`) sobre un activo en `INACTIVO`, `CERRADO` o `BAJA` responde `409 ESTADO_NO_PERMITE_EVENTOS`.

---

## Tabla de permisos RBAC usados

> Datos extraídos de `modulo1.permisos` (consulta directa vía MCP postgres, base `sgpmp`). Acciones: C=1 Crear, R=2 Leer, U=3 Actualizar, D=4 Eliminar/Desactivar, E=5 Ejecutar.

| `id_recurso` | Recurso | Admin | Productor | Veterinario | Ing. Campo | Contador |
|---|---|---|---|---|---|---|
| 29 | `activos_biologicos` | C,R,U,D,E | C,R,U,D,E | C,R,D,E | C,R,U,E | — |
| 30 | `asociacion_sensor_activo` | C,R | R | R | C,R | — |
| 31 | `bitacora_auditoria_m02` | R | R | R | — | R |

Notas:
- **Veterinario** no tiene `U` sobre `activos_biologicos` (no puede usar `PATCH /{id_activo}`, sí puede `PATCH /{id_activo}/estado` que es `E`).
- **Ingeniero de Campo** no tiene `D` sobre `activos_biologicos` (no puede cerrar ciclo, `POST /{id_activo}/cierre`), y no tiene ningún permiso sobre `bitacora_auditoria_m02`.
- **Contador** solo tiene acceso de lectura a la bitácora de auditoría (`31, R`); no participa en ninguna otra operación del módulo.
- **Productor** y **Veterinario** solo tienen `R` sobre `asociacion_sensor_activo` — no pueden crear asociaciones sensor-activo, solo Admin e Ingeniero.

---

## Use Cases — resumen de firmas

| Clase | `execute()` (u otro método público) — parámetros principales |
|-------|--------------------------------------|
| `RegistrarActivoBiologicoUseCase` | `(dto: RegistrarActivoBiologicoDTO, usuario: UsuarioActual) → ActivoBiologico` |
| `ConsultarActivoUseCase` | `(id_activo: int, usuario: UsuarioActual \| None = None) → ActivoBiologico` |
| `ActualizarActivoIndividualUseCase` | `(id_activo: int, dto: ActualizarActivoIndividualDTO, usuario: UsuarioActual) → ActivoBiologico` |
| `CambiarEstadoUseCase` | `(id_activo: int, dto: CambiarEstadoDTO, usuario: UsuarioActual) → HistoricoEstado` |
| `CerrarCicloUseCase` | `(id_activo: int, dto: CerrarCicloDTO, usuario: UsuarioActual) → HistoricoEstado` |
| `CambiarFaseUseCase` | `(id_activo: int, dto: CambiarFaseDTO, usuario: UsuarioActual) → GestionFase` |
| `ConsultarHistorialFasesUseCase` | `(id_activo: int) → list[GestionFase]` |
| `ConsultarEventosUseCase` | `(id_activo: int) → list[EventoActivo]` |
| `RegistrarEventoCrecimientoUseCase` | `(id_activo: int, dto: RegistrarEventoCrecimientoDTO, usuario: UsuarioActual) → tuple[EventoActivo, bool]` |
| `RegistrarEventoBajaUseCase` | `(id_activo: int, dto: RegistrarEventoBajaDTO, usuario: UsuarioActual) → EventoActivo` |
| `RegistrarEventoSanitarioUseCase` | `(id_activo: int, dto: RegistrarEventoSanitarioDTO, usuario: UsuarioActual) → tuple[EventoActivo, HistoricoEstado \| None]` |
| `RegistrarEventoProductivoUseCase` | `(id_activo: int, dto: RegistrarEventoProductivoDTO, usuario: UsuarioActual) → EventoActivo` |
| `RegistrarEventoReproductivoUseCase` | `(id_activo: int, dto: RegistrarEventoReproductivoDTO, usuario: UsuarioActual) → EventoActivo` |
| `ConsultarAsociacionUseCase` | `(id_activo: int, tipo_consulta: str, usuario: UsuarioActual \| None = None) → HistorialInfraestructura \| list[HistorialInfraestructura] \| None` |
| `ConsultarHistorialUseCase` | `(id_activo: int, dto: ConsultarHistorialDTO, usuario: UsuarioActual) → PaginaHistorial` |
| `ConsultarFichaIntegralUseCase` | `(id_activo: int, usuario: UsuarioActual) → FichaIntegral` |
| `RegistrarTransferenciaUseCase.listar_infraestructuras_disponibles` | `(id_activo: int, usuario: UsuarioActual) → list[dict]` |
| `RegistrarTransferenciaUseCase.execute` | `(id_activo: int, dto: RegistrarTransferenciaDTO, usuario: UsuarioActual) → Transferencia` |
| `AsociarSensorActivoUseCase` | `(id_activo: int, dto: AsociarSensorActivoDTO, usuario_actual: UsuarioActual) → AsociacionSensorActivo` |
| `ConsultarIndicadoresUseCase` | `(id_activo: int, dto: ConsultarIndicadoresDTO, usuario: UsuarioActual) → ResultadoIndicadores` |
| `ConsultarDatosConsolidadosUseCase` | `(id_activo: int, dto: DatosConsolidadosDTO, usuario: UsuarioActual) → DatosConsolidados` |
| `ConsultarBitacoraUseCase` | `(dto: ConsultarBitacoraDTO) → tuple[list[EventoAuditoria], int]` |

---

## Entidades de dominio (`domain/entities/activo_biologico.py`)

Todas son `@dataclass`, salvo `ActivoBiologico` que además define `__eq__`/`__hash__` propios por `id_activo_biologico`.

| Entidad | Atributos clave |
|---|---|
| `ActivoBiologico` | `id_especie, tipo, origen_financiero, id_infraestructura, id_estado, id_usuario`, + opcionales (`identificador, fecha_inicio_ciclo, costo_adquisicion, soporte_documental, detalle_individual, detalle_poblacional`, …). Métodos de conducta: `crear()`, `actualizar_detalle_individual()`, `cambiar_estado()`, `aplicar_evento_baja()`, `aplicar_evento_crecimiento()`. |
| `DetalleIndividual` | `raza, sexo, fecha_nacimiento`, + `peso_inicial` opcional |
| `DetallePoblacional` | `cantidad_inicial, cantidad_actual`, + `peso_promedio, biomasa_total, densidad` opcionales |
| `EventoActivo` | `id_activo_biologico, fecha, id_usuario` + composición opcional de `crecimiento/baja/sanitario/productivo/reproductivo` |
| `EventoCrecimiento`, `EventoBaja`, `EventoSanitario`, `EventoProductivo`, `EventoReproductivo` | sub-eventos, ver tablas de Response arriba |
| `HistoricoEstado` | `id_activo_biologico, id_estado_anterior, id_estado_nuevo, fecha_cambio, modulo_origen, id_usuario` |
| `GestionFase` | `id_activo_biologico, id_ciclo_productiva, nombre_ciclo, fecha_inicio, es_activa, id_usuario` |
| `HistorialInfraestructura` | `id_historial, id_activo_biologico, id_infraestructura, nombre_infraestructura, tipo_infraestructura, fecha_inicio, fecha_fin` |
| `Transferencia` | `id_activo_biologico, id_infraestructura_origen, id_infraestructura_destino, nombre_infra_origen, nombre_infra_destino, fecha_transferencia, motivo_transferencia, id_usuario` |
| `RegistroHistorial` / `PaginaHistorial` | usados por `ConsultarHistorialUseCase` |
| `FichaIntegral` | usada por `ConsultarFichaIntegralUseCase` |
| `IndicadorZootecnico` / `ResultadoIndicadores` | usados por `ConsultarIndicadoresUseCase` |
| `DatosConsolidados` / `SeccionDatosConsolidados` | usados por `ConsultarDatosConsolidadosUseCase` |
| `AsociacionSensorActivo` | `id_activo_biologico, tipo_activo, tipo_asociacion, dispositivo_iot_id, sensor_id, id_infraestructura, id_usuario, fecha_inicio, estado_asociacion='ACTIVA'` |
| `EventoAuditoria` | `rf_origen, tipo_evento, clasificacion_biologica, timestamp_evento, resultado='EXITOSO', severidad_log='INFO', modulo_consumidor='modulo2'` |

### Value objects / enums (`domain/value_objects/`)

- **`EstadoActivo(IntEnum)`**: `ACTIVO=1, INACTIVO=2, EN_TRATAMIENTO=3, AISLADO=4, CERRADO=5, BAJA=6` + `TRANSICIONES_VALIDAS` (ver máquina de estados arriba).
- **`OrigenFinanciero(str, Enum)`**: `COMPRA, NACIMIENTO, DONACION, TRANSFERENCIA_INTERNA`.
- **`TipoActivo(str, Enum)`**: `INDIVIDUAL, POBLACIONAL`.

Estos VOs son el vocabulario canónico, pero varios DTOs validan contra conjuntos de strings inline en vez de importar el Enum directamente (mismo efecto, doble fuente de verdad a tener en cuenta si se refactoriza).

---

## Concurrencia optimista

Este módulo **no implementa** el patrón de concurrencia optimista (`fecha_actualizacion`/`version` + `PreconditionFailedError` 412) que sí usa `src/configuration/`. Ninguna entidad de `biological_assets` expone ese campo de control en sus DTOs de edición — `PATCH /{id_activo}` y `PATCH /{id_activo}/estado` no piden un timestamp/versión previo del cliente.
