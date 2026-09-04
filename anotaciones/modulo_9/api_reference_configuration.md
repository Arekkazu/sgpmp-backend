# API Reference — `src/configuration/`

> Generado el 2026-07-16. Solo documentación — no subir al repositorio.
>
> **Todos los endpoints de este módulo requieren sesión activa.**
> El cliente debe enviar `Authorization: Bearer <token>` en cada request.
> No existe ningún endpoint público en `src/configuration/`.

---

## Prefijos de rutas

| Router | Prefijo | Tag Swagger |
|--------|---------|-------------|
| `especie_router.py` | `/configuracion/especies` | Especies |
| `finca_router.py` | `/configuracion/fincas` | Fincas |
| `infraestructura_router.py` | `/configuracion/infraestructuras` | Infraestructuras |
| `dispositivo_iot_router.py` | `/configuracion/dispositivos-iot` | Dispositivos IoT |
| `sensor_router.py` | `/configuracion/sensores` | Sensores |
| `ciclo_router.py` | `/configuracion/ciclos` | Ciclos Biológicos |
| `patologia_router.py` | `/configuracion/patologias` | Patologías |
| `metrica_router.py` | `/configuracion/metricas` | Métricas de Producción |
| `umbral_router.py` | `/configuracion/umbrales` | Umbrales Ambientales |
| `configuracion_global_router.py` | `/configuracion/parametros` | Parámetros Globales |
| `contexto_interfaz_router.py` | `/configuracion/interfaz` | Contexto de Interfaz |
| `identidad_visual_router.py` | `/configuracion/identidad-visual` | Identidad Visual |
| `tema_visual_router.py` | `/configuracion/personalizacion/tema` | Tema Visual |
| `preferencia_idioma_router.py` | `/configuracion/personalizacion/idioma` | Idioma |
| `dashboard_layout_router.py` | `/configuracion/personalizacion/dashboard` | Dashboard |
| `plantilla_router.py` | `/configuracion/plantillas` | Plantillas |

---

## Endpoints

### Especies — `/configuracion/especies`

> **Recurso RBAC:** `id_recurso = 8`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(8, C)` | Admin | `RegistrarEspecieUseCase` |
| `GET` | `/` | `(8, R)` | Admin, Prod, Vet, Ing, Cont | `ConsultarCatalogoUseCase` |
| `PATCH` | `/{id_especie}` | `(8, U)` | Admin, Vet, Ing | `EditarEspecieUseCase` |
| `PATCH` | `/{id_especie}/desactivar` | `(8, D)` | Admin | `DesactivarEspecieUseCase` |
| `PATCH` | `/{id_especie}/reactivar` | `(8, D)` | Admin | `ReactivarEspecieUseCase` |

#### `POST /configuracion/especies/` — Registrar especie

**Input `RegistrarEspecieDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nombre` | `str` | 3–50 chars, solo letras y espacios |
| `descripcion` | `str \| None` | Opcional, máx 255 chars |

**Response `EspecieResponse`:**

| Campo | Tipo |
|-------|------|
| `id_especie` | `int` |
| `nombre` | `str` |
| `descripcion` | `str \| None` |
| `es_activo` | `bool` |
| `fecha_creacion` | `datetime` |
| `fecha_actualizacion` | `datetime \| None` |

---

#### `GET /configuracion/especies/` — Catálogo de especies

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `solo_activas` | `bool` | `false` | Filtra solo registros activos |

**Response:** `list[EspecieResponse]`

---

#### `PATCH /configuracion/especies/{id_especie}` — Editar especie

**Input `EditarEspecieDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nombre` | `str` | 3–50 chars |
| `descripcion` | `str \| None` | Opcional, máx 255 chars |
| `fecha_actualizacion` | `datetime` | Control de concurrencia optimista (412 si no coincide) |

**Response:** `EspecieResponse`

---

### Fincas — `/configuracion/fincas`

> **Recurso RBAC:** `id_recurso = 9`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(9, C)` | Admin | `RegistrarFincaUseCase` |
| `GET` | `/` | `(9, R)` | Admin, Prod, Vet, Ing | `ConsultarFincasUseCase.listar` |
| `GET` | `/{id_finca}` | `(9, R)` | Admin, Prod, Vet, Ing | `ConsultarFincasUseCase.obtener` |
| `PATCH` | `/{id_finca}` | `(9, U)` | Admin | `EditarFincaUseCase` |
| `PATCH` | `/{id_finca}/desactivar` | `(9, D)` | Admin | `DesactivarFincaUseCase` |

#### `POST /configuracion/fincas/` — Registrar finca

**Input `RegistrarFincaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nombre` | `str` | Obligatorio, máx 55 chars |
| `ubicacion` | `UbicacionFincaDTO` | Ver abajo |
| `tamano_h` | `Decimal` | > 0 |
| `id_usuario` | `int \| None` | Opcional — asigna la finca a un usuario |

**`UbicacionFincaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `departamento` | `str` | — |
| `municipio` | `str` | — |
| `vereda` | `str` | — |
| `latitud` | `Decimal` | –90 a 90 |
| `longitud` | `Decimal` | –180 a 180 |

**Response `FincaResponse`:**

| Campo | Tipo |
|-------|------|
| `id_finca` | `int` |
| `nombre` | `str` |
| `ubicacion` | `UbicacionFincaResponse` (misma estructura) |
| `tamano_h` | `Decimal` |
| `es_activo` | `bool` |
| `fecha_creacion` | `datetime` |
| `fecha_actualizacion` | `datetime` |
| `id_usuario` | `int \| None` |

---

#### `GET /configuracion/fincas/` — Listar fincas

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `solo_activas` | `bool` | `false` | — |

**Response:** `list[FincaResponse]`

---

#### `PATCH /configuracion/fincas/{id_finca}` — Editar finca

**Input `EditarFincaDTO`:** mismos campos que `RegistrarFincaDTO` más:

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `fecha_actualizacion` | `datetime` | Control de concurrencia optimista (412 si no coincide) |

**Response:** `FincaResponse`

---

### Infraestructuras — `/configuracion/infraestructuras`

> **Recurso RBAC:** `id_recurso = 10`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(10, C)` | Admin | `RegistrarInfraestructuraUseCase` |
| `GET` | `/` | `(10, R)` | Admin, Prod, Vet, Ing | `ConsultarInfraestructurasUseCase.listar_por_finca` |
| `GET` | `/{id_infraestructura}` | `(10, R)` | Admin, Prod, Vet, Ing | `ConsultarInfraestructurasUseCase.obtener` |
| `PATCH` | `/{id_infraestructura}` | `(10, U)` | Admin | `EditarInfraestructuraUseCase` |
| `PATCH` | `/{id_infraestructura}/desactivar` | `(10, D)` | Admin | `DesactivarInfraestructuraUseCase` |

#### `POST /configuracion/infraestructuras/` — Registrar infraestructura

**Input `RegistrarInfraestructuraDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nombre_infraestructura` | `str` | Obligatorio, máx 50 chars |
| `tipo_area` | `EnumTipoInfraestructura` | Enum de DB |
| `superficie` | `Decimal` | > 0 |
| `finca_id` | `int` | FK a finca |
| `descripcion_infraestructura` | `str \| None` | Opcional, máx 100 chars |

**Response `InfraestructuraResponse`:**

| Campo | Tipo |
|-------|------|
| `id_infraestructura` | `int` |
| `nombre_infraestructura` | `str` |
| `tipo_area` | `str` |
| `superficie` | `Decimal` |
| `id_finca` | `int` |
| `descripcion_infraestructura` | `str \| None` |
| `es_activo` | `bool` |
| `fecha_actualizacion` | `datetime \| None` |

---

#### `GET /configuracion/infraestructuras/` — Listar por finca

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `finca_id` | `int` | — | Requerido |
| `solo_activas` | `bool` | `false` | — |

**Response:** `list[InfraestructuraResponse]`

---

#### `PATCH /configuracion/infraestructuras/{id_infraestructura}` — Editar infraestructura

**Input `EditarInfraestructuraDTO`:** mismos campos que `RegistrarInfraestructuraDTO` más:

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `fecha_actualizacion` | `datetime \| None` | Control de concurrencia optimista |

**Response:** `InfraestructuraResponse`

---

### Dispositivos IoT — `/configuracion/dispositivos-iot`

> **Recurso RBAC:** `id_recurso = 11`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(11, C)` | Admin, Ing | `RegistrarDispositivoIotUseCase` |
| `GET` | `/` | `(11, R)` | Admin, Prod, Ing | `ConsultarDispositivosIotUseCase.listar` |
| `GET` | `/{id_dispositivo_iot}` | `(11, R)` | Admin, Prod, Ing | `ConsultarDispositivosIotUseCase.obtener` |
| `PATCH` | `/{id_dispositivo_iot}/desactivar` | `(11, D)` | Admin, Ing | `DesactivarDispositivoIotUseCase` |
| `POST` | `/{id_dispositivo_iot}/sensores` | `(11, C)` | Admin, Ing | `RegistrarSensorUseCase` |
| `GET` | `/{id_dispositivo_iot}/sensores` | `(11, R)` | Admin, Prod, Ing | `ConsultarSensoresUseCase.listar_por_dispositivo` |
| `POST` | `/{id_dispositivo_iot}/configurar` | `(11, U)` | Admin, Ing | `ConfigurarRemotamenteUseCase` |
| `GET` | `/{id_dispositivo_iot}/configuraciones` | `(11, R)` | Admin, Prod, Ing | `ConsultarConfiguracionesUseCase.listar_por_dispositivo` |

#### `POST /configuracion/dispositivos-iot/` — Registrar dispositivo

**Input `RegistrarDispositivoIotDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `serial` | `str` | Obligatorio, máx 50 chars, único |
| `descripcion` | `str` | Obligatorio, máx 100 chars |
| `id_infraestructura` | `int` | FK a infraestructura |
| `es_activo` | `bool` | Default `true` |

**Response `DispositivoIotResponse`:**

| Campo | Tipo |
|-------|------|
| `id_dispositivo_iot` | `int` |
| `serial` | `str` |
| `descripcion` | `str` |
| `id_infraestructura` | `int` |
| `es_activo` | `bool` |
| `fecha_creacion` | `datetime` |

---

#### `POST /configuracion/dispositivos-iot/{id_dispositivo_iot}/sensores` — Registrar sensor

**Input `RegistrarSensorDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nombre` | `str` | Obligatorio, máx 100 chars |
| `categoria` | `CategoriaSensor \| None` | `HUMEDAD`, `TEMPERATURA`, `OXIGENO`, `PH`, `AMONIACO`, `SALINIDAD`, `LUMINOSIDAD` |

**Response `SensorResponse`:**

| Campo | Tipo |
|-------|------|
| `id_sensores` | `int` |
| `nombre` | `str` |
| `id_dispositivo_iot` | `int` |
| `es_activo` | `bool` |
| `categoria` | `str \| None` |

---

#### `POST /configuracion/dispositivos-iot/{id_dispositivo_iot}/configurar` — Configurar remotamente

> Devuelve **202 Accepted** — la configuración queda encolada; se aplica cuando el dispositivo se conecte.

**Input `ConfigurarRemotamenteDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `frecuencia_captura` | `int` | ≥ 1 (minuto) |
| `intervalo_transmision` | `int` | ≥ `frecuencia_captura` |

**Response `ConfiguracionRemotaResponse` (HTTP 202):**

| Campo | Tipo |
|-------|------|
| `id_configuracion_remota` | `int` |
| `id_dispositivo_iot` | `int` |
| `frecuencia_captura` | `int` |
| `intervalo_transmision` | `int` |
| `estado` | `str` |
| `id_usuario` | `int \| None` |
| `fecha_creacion` | `datetime \| None` |
| `fecha_aplicacion` | `datetime \| None` |
| `mensaje` | `str \| None` |

---

### Sensores — `/configuracion/sensores`

> **Recurso RBAC:** `id_recurso = 12`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/{id_sensor}/asociar` | `(12, C)` | Admin, Ing | `AsociarSensorAreaUseCase` |
| `GET` | `/{id_sensor}/asociaciones` | `(12, R)` | Admin, Prod, Vet, Ing | `ConsultarAsociacionesUseCase.listar_por_sensor` |
| `POST` | `/{id_sensor}/calibrar` | `(12, C)` | Admin, Ing | `RegistrarCalibracionUseCase` |
| `GET` | `/{id_sensor}/calibraciones` | `(12, R)` | Admin, Prod, Vet, Ing | `ConsultarCalibracionesUseCase.listar_por_sensor` |

#### `POST /configuracion/sensores/{id_sensor}/asociar` — Asociar sensor a área

**Input `AsociarSensorAreaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_dispositivo_iot` | `int` | — |
| `id_infraestructura` | `int` | — |
| `punto_instalacion` | `str` | Obligatorio, máx 100 chars |

**Response `SensorAreaResponse`:**

| Campo | Tipo |
|-------|------|
| `id_sensores_area_asociada` | `int` |
| `id_sensor` | `int` |
| `id_dispositivo_iot` | `int` |
| `id_infraestructura` | `int` |
| `punto_instalacion` | `str` |
| `tiene_estado` | `bool` |
| `fecha_asociacion` | `datetime` |
| `fecha_finalizacion` | `datetime \| None` |
| `id_usuario` | `int` |

---

#### `POST /configuracion/sensores/{id_sensor}/calibrar` — Registrar calibración

**Input `RegistrarCalibracionDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_dispositivo_iot` | `int` | — |
| `id_infraestructura` | `int` | — |
| `valor_referencia` | `Decimal` | > 0 |
| `fecha_calibracion` | `datetime` | — |
| `observaciones` | `str \| None` | Opcional |

**Response `CalibracionResponse`:**

| Campo | Tipo |
|-------|------|
| `id_calibracion` | `int` |
| `id_dispositivo_iot` | `int` |
| `id_sensor` | `int` |
| `valor_referencia` | `Decimal` |
| `fecha_calibracion` | `datetime` |
| `id_usuario` | `int` |
| `observaciones` | `str \| None` |

---

### Ciclos Biológicos — `/configuracion/ciclos`

> **Recurso RBAC:** `id_recurso = 17`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(17, C)` | Admin, Vet | `RegistrarCicloUseCase` |
| `GET` | `/` | `(17, R)` | Admin, Vet | `ConsultarCiclosUseCase` |
| `PATCH` | `/{id_ciclo_biologico}` | `(17, U)` | Admin, Vet | `EditarCicloUseCase` |
| `PATCH` | `/{id_ciclo_biologico}/desactivar` | `(17, D)` | Admin, Vet | `DesactivarCicloUseCase` |

#### `POST /configuracion/ciclos/` — Registrar ciclo

**Input `RegistrarCicloDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_especie` | `int` | FK a especie |
| `nombre` | `str` | 3–50 chars, letras/números/espacios/guiones/paréntesis |
| `descripcion` | `str \| None` | Opcional, máx 255 chars |
| `duracion_dias` | `int` | > 0 |

**Response `CicloBiologicoResponse`:**

| Campo | Tipo |
|-------|------|
| `id_ciclo_biologico` | `int` |
| `nombre` | `str` |
| `descripcion` | `str \| None` |
| `duracion_dias` | `int` |
| `id_especie` | `int` |
| `es_activo` | `bool` |
| `fecha_actualizacion` | `datetime \| None` |

---

#### `GET /configuracion/ciclos/` — Consultar ciclos por especie

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `id_especie` | `int` | — | Requerido |
| `solo_activas` | `bool` | `false` | — |

**Response:** `list[CicloBiologicoResponse]`

---

#### `PATCH /configuracion/ciclos/{id_ciclo_biologico}` — Editar ciclo

**Input `EditarCicloDTO`:** mismos campos que `RegistrarCicloDTO` más:

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `fecha_actualizacion` | `datetime \| None` | Control de concurrencia optimista |

**Response:** `CicloBiologicoResponse`

---

### Patologías — `/configuracion/patologias`

> **Recurso RBAC:** `id_recurso = 18`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(18, C)` | Admin, Vet | `RegistrarPatologiaUseCase` |
| `GET` | `/` | `(18, R)` | Admin, Vet | `ConsultarPatologiasUseCase` |
| `PATCH` | `/{id_patologia}` | `(18, U)` | Admin, Vet | `EditarPatologiaUseCase` |
| `PATCH` | `/{id_patologia}/desactivar` | `(18, D)` | Admin, Vet | `DesactivarPatologiaUseCase` |

#### `POST /configuracion/patologias/` — Registrar patología

**Input `RegistrarPatologiaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_especie` | `int` | FK a especie |
| `nombre` | `str` | 3–60 chars |
| `descripcion` | `str \| None` | Opcional, máx 255 chars |

**Response `PatologiaEspecieItemResponse`** (incluye la relación especie-patología):

| Campo | Tipo |
|-------|------|
| `id_especies_patologias` | `int` |
| `id_patologia` | `int` |
| `id_especie` | `int` |
| `nombre` | `str` |
| `descripcion` | `str \| None` |
| `es_activo` | `bool` |
| `fecha_actualizacion` | `datetime \| None` |

---

#### `GET /configuracion/patologias/` — Consultar patologías por especie

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `id_especie` | `int` | — | Requerido |
| `solo_activas` | `bool` | `false` | — |

**Response:** `list[PatologiaEspecieItemResponse]`

---

#### `PATCH /configuracion/patologias/{id_patologia}` — Editar patología

**Input `EditarPatologiaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nombre` | `str` | 3–60 chars |
| `descripcion` | `str \| None` | Opcional, máx 255 chars |
| `fecha_actualizacion` | `datetime \| None` | Control de concurrencia optimista |

**Response `PatologiaResponse`:**

| Campo | Tipo |
|-------|------|
| `id_patologia` | `int` |
| `nombre` | `str` |
| `descripcion` | `str \| None` |
| `es_activo` | `bool` |
| `fecha_actualizacion` | `datetime \| None` |

---

### Métricas de Producción — `/configuracion/metricas`

> **Recurso RBAC:** `id_recurso = 19`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(19, C)` | Admin, Vet | `RegistrarMetricaUseCase` |
| `GET` | `/` | `(19, R)` | Admin, Vet | `ConsultarMetricasUseCase` |
| `PATCH` | `/{id_metrica_produccion}` | `(19, U)` | Admin, Vet | `EditarMetricaUseCase` |
| `PATCH` | `/{id_metrica_produccion}/desactivar` | `(19, D)` | Admin, Vet | `DesactivarMetricaUseCase` |

#### `POST /configuracion/metricas/` — Registrar métrica

**Input `RegistrarMetricaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_especie` | `int` | FK a especie |
| `nombre` | `str` | 3–60 chars |
| `unidad_medida` | `str` | Obligatorio, máx 20 chars |
| `tipo_medicion` | `str` | `PESO`, `VOLUMEN`, `LONGITUD`, `CONTEO`, `OTRO` |
| `aplica_a_tipo_activo` | `str` | `INDIVIDUAL`, `LOTE`, `AMBOS` — default `AMBOS` |

**Response `MetricaProduccionResponse`:**

| Campo | Tipo |
|-------|------|
| `id_metrica_produccion` | `int` |
| `nombre` | `str` |
| `unidad_medida` | `str` |
| `tipo_medicion` | `str` |
| `aplica_a_tipo_activo` | `str` |
| `id_especie` | `int \| None` |
| `es_activo` | `bool` |
| `fecha_actualizacion` | `datetime \| None` |

---

#### `GET /configuracion/metricas/` — Consultar métricas por especie

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `id_especie` | `int` | — | Requerido |
| `solo_activas` | `bool` | `false` | — |

**Response:** `list[MetricaProduccionResponse]`

---

#### `PATCH /configuracion/metricas/{id_metrica_produccion}` — Editar métrica

**Input `EditarMetricaDTO`:** mismos campos que `RegistrarMetricaDTO` (sin `id_especie`) más:

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `fecha_actualizacion` | `datetime \| None` | Control de concurrencia optimista |

**Response:** `MetricaProduccionResponse`

---

### Umbrales Ambientales — `/configuracion/umbrales`

> **Recurso RBAC:** `id_recurso = 20`

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(20, C)` | Admin, Vet | `RegistrarUmbralUseCase` |
| `GET` | `/` | `(20, R)` | Admin, Vet | `ConsultarUmbralesUseCase` |
| `PATCH` | `/{id_umbral_ambiental}` | `(20, U)` | Admin, Vet | `EditarUmbralUseCase` |
| `PATCH` | `/{id_umbral_ambiental}/desactivar` | `(20, D)` | Admin, Vet | `DesactivarUmbralUseCase` |

#### `POST /configuracion/umbrales/` — Registrar umbral

**Input `RegistrarUmbralDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_especie` | `int` | FK a especie |
| `id_variable_ambiental` | `int` | FK a variable ambiental |
| `valor_min` | `Decimal` | — |
| `valor_max` | `Decimal` | > `valor_min` |
| `niveles` | `list[NivelDTO]` | Exactamente 3: `normal`, `precaucion`, `critico` |

**`NivelDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nivel` | `str` | `normal`, `precaucion`, `critico` |
| `limite_inferior` | `Decimal` | — |
| `limite_superior` | `Decimal` | > `limite_inferior` |

**Response `UmbralAmbientalResponse`:**

| Campo | Tipo |
|-------|------|
| `id_umbral_ambiental` | `int` |
| `id_especie` | `int` |
| `id_variable_ambiental` | `int` |
| `unidad_medida` | `str` |
| `valor_min` | `Decimal` |
| `valor_max` | `Decimal` |
| `es_activo` | `bool` |
| `fecha_actualizacion` | `datetime \| None` |
| `niveles` | `list[NivelAlertaResponse]` |

---

#### `GET /configuracion/umbrales/` — Consultar umbrales por especie

**Query params:**

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `id_especie` | `int` | — | Requerido |
| `solo_activas` | `bool` | `false` | — |

**Response:** `list[UmbralAmbientalResponse]`

---

#### `PATCH /configuracion/umbrales/{id_umbral_ambiental}` — Editar umbral

**Input `EditarUmbralDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `valor_min` | `Decimal` | — |
| `valor_max` | `Decimal` | > `valor_min` |
| `niveles` | `list[NivelDTO]` | Exactamente 3 |
| `fecha_actualizacion` | `datetime \| None` | Control de concurrencia optimista |

**Response:** `UmbralAmbientalResponse`

---

### Parámetros Globales — `/configuracion/parametros`

> **Recurso RBAC:** `id_recurso = 21` — **Solo Administrador.**
> Solo puede existir una configuración activa a la vez.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `POST` | `/` | `(21, C)` | Admin | `CrearConfiguracionUseCase` |
| `GET` | `/` | `(21, R)` | Admin | `ConsultarConfiguracionUseCase` |
| `PATCH` | `/{id_configuracion_global}` | `(21, U)` | Admin | `ActualizarConfiguracionUseCase` |

#### `POST /configuracion/parametros/` — Crear configuración global

**Input `CrearConfiguracionDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `frecuencia_muestreo` | `int` | > 0 |
| `heartbeat` | `int` | > 0 |

**Response `ConfiguracionGlobalResponse`:**

| Campo | Tipo |
|-------|------|
| `id_configuracion_global` | `int` |
| `frecuencia_muestreo` | `int` |
| `heartbeat` | `int` |
| `fecha_actualizacion` | `datetime` |
| `id_usuario` | `int` |
| `es_activo` | `bool` |

---

#### `PATCH /configuracion/parametros/{id_configuracion_global}` — Actualizar configuración

**Input `ActualizarConfiguracionDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `frecuencia_muestreo` | `int` | > 0 |
| `heartbeat` | `int` | > 0 |
| `fecha_actualizacion` | `datetime` | Control de concurrencia optimista |

**Response:** `ConfiguracionGlobalResponse`

---

### Contexto de Interfaz — `/configuracion/interfaz`

> **Recurso RBAC:** `id_recurso = 22` — **Todos los roles autenticados.**
> Endpoint de solo lectura que devuelve el estado contextual del usuario actual.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/contexto` | `(22, R)` | Admin, Prod, Vet, Ing, Cont | `ObtenerContextoUseCase` |

**Response `ContextoInterfazResponse`:**

| Campo | Tipo | Notas |
|-------|------|-------|
| `id_usuario` | `int` | — |
| `nombre_completo` | `str` | — |
| `id_rol` | `int` | — |
| `nombre_rol` | `str` | — |
| `id_finca` | `int \| None` | Finca activa asignada al usuario |
| `finca_activa` | `str \| None` | Nombre de la finca |
| `departamento` | `str \| None` | Departamento de la finca |
| `especies_configuradas` | `list[str]` | Especies asociadas a la finca |
| `modulos_autorizados` | `list[str]` | Recursos con permiso R para el rol |

---

### Identidad Visual — `/configuracion/identidad-visual`

> **Recurso RBAC:** `id_recurso = 23` — **Solo Administrador.**
> Los endpoints usan `multipart/form-data` para incluir el archivo de logo.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/{id_finca}` | `(23, R)` | Admin | `ObtenerIdentidadVisualUseCase` |
| `POST` | `/` | `(23, C)` | Admin | `GuardarIdentidadVisualUseCase` |
| `PATCH` | `/{id_finca}` | `(23, U)` | Admin | `ActualizarIdentidadVisualUseCase` |

#### `POST /configuracion/identidad-visual/` — Crear identidad visual

**Input `GuardarIdentidadVisualDTO` + archivo (multipart/form-data):**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_finca` | `int` | — |
| `primary_color` | `str` | Patrón `#[0-9A-Fa-f]{6}` |
| `secondary_color` | `str` | Patrón `#[0-9A-Fa-f]{6}` |
| `org_display_name` | `str` | 1–50 chars |
| `logo` | `UploadFile \| None` | Opcional — imagen del logo |

**Response `IdentidadVisualResponse`:**

| Campo | Tipo |
|-------|------|
| `id_identidad_visual` | `int` |
| `id_finca` | `int` |
| `id_usuario` | `int` |
| `logo_path` | `str \| None` |
| `primary_color` | `str` |
| `secondary_color` | `str` |
| `org_display_name` | `str` |
| `version` | `int \| None` |
| `fecha_creacion` | `datetime \| None` |

---

#### `PATCH /configuracion/identidad-visual/{id_finca}` — Actualizar identidad visual

**Input `ActualizarIdentidadVisualDTO` + archivo (multipart/form-data):**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `primary_color` | `str` | Patrón `#[0-9A-Fa-f]{6}` |
| `secondary_color` | `str` | Patrón `#[0-9A-Fa-f]{6}` |
| `org_display_name` | `str` | 1–50 chars |
| `version` | `int` | Control de concurrencia optimista |
| `logo` | `UploadFile \| None` | Opcional |

**Response:** `IdentidadVisualResponse`

---

### Tema Visual — `/configuracion/personalizacion/tema`

> Dos recursos RBAC:
> - `id_recurso = 24` (`tema_visual`) — tema personal de cada usuario
> - `id_recurso = 27` (`configuracion_ui_global`) — tema global (solo Admin)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/` | `(24, R)` | Admin, Prod, Vet, Ing, Cont | `ObtenerTemaResueltoUseCase` |
| `PATCH` | `/` | `(24, U)` | Admin, Prod, Vet, Ing, Cont | `GuardarTemaPersonalUseCase` |
| `GET` | `/global` | `(27, R)` | Admin | — (consulta directa al repo) |
| `PATCH` | `/global` | `(27, U)` | Admin | `GuardarTemaGlobalUseCase` |

#### `PATCH /configuracion/personalizacion/tema/` — Guardar tema personal

**Input `GuardarTemaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `theme_mode` | `int` | `1` = Claro, `2` = Oscuro, `3` = Automático |

**Response `TemaResueltoResponse`** (para GET) / **`TemaVisualResponse`** (para PATCH):

**`TemaResueltoResponse`:**

| Campo | Tipo | Notas |
|-------|------|-------|
| `theme_mode` | `int` | Tema resuelto (personal > global > default) |
| `fuente` | `str` | `"personal"`, `"global"`, `"default"` |
| `id_tema_visual` | `int \| None` | — |

**`TemaVisualResponse`:**

| Campo | Tipo |
|-------|------|
| `id_tema_visual` | `int` |
| `id_usuario` | `int` |
| `theme_mode` | `int` |
| `es_global` | `bool` |
| `fecha_actualizacion` | `datetime \| None` |

---

### Idioma — `/configuracion/personalizacion/idioma`

> Dos recursos RBAC:
> - `id_recurso = 26` (`preferencia_idioma`) — idioma personal de cada usuario
> - `id_recurso = 27` (`configuracion_ui_global`) — idioma global (solo Admin)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/` | `(26, R)` | Admin, Prod, Vet, Ing, Cont | `ObtenerIdiomaResueltoUseCase` |
| `PATCH` | `/` | `(26, U)` | Admin, Prod, Vet, Ing, Cont | `GuardarIdiomaPersonalUseCase` |
| `GET` | `/global` | `(27, R)` | Admin | `ObtenerIdiomaGlobalUseCase` |
| `PATCH` | `/global` | `(27, U)` | Admin | `GuardarIdiomaGlobalUseCase` |

#### `PATCH /configuracion/personalizacion/idioma/` — Guardar idioma personal

**Input `GuardarIdiomaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `locale_code` | `str` | **Solo `"es-CO"` o `"en-US"`.** Cualquier otro valor → `400 IDIOMA_NO_DISPONIBLE`. Reforzado en BD por `chk_pref_idioma_locale_code` |
| `version_perfil` | `int \| None` | Versión de perfil que devolvió el `GET`. Si se envía y no coincide con `modulo1.usuarios.version` → `409 CONFLICTO_PERFIL_MODIFICADO`. Omitirla salta la comprobación |

**Errores:**

| HTTP | `error_code` | Cuándo |
|------|--------------|--------|
| 400 | `IDIOMA_NO_DISPONIBLE` | `locale_code` fuera de la lista blanca |
| 403 | `ACCESO_DENEGADO` | Sin el permiso RBAC. En `/global` el mensaje es el específico del RF-29 |
| 404 | `PREFERENCIA_IDIOMA_NO_ENCONTRADA` | La fila desapareció entre la lectura y la escritura |
| 409 | `CONFLICTO_PERFIL_MODIFICADO` | `version_perfil` desfasada |
| 500 | `ERROR_PERSISTENCIA_IDIOMA` | Fallo de infraestructura al guardar |

**Response `IdiomaResueltoResponse`** (para GET) / **`PreferenciaIdiomaResponse`** (para PATCH):

**`IdiomaResueltoResponse`:**

| Campo | Tipo | Notas |
|-------|------|-------|
| `locale_code` | `str` | Idioma resuelto (personal > global > `es-CO`) |
| `fuente` | `str` | `"personal"`, `"global"`, `"defecto"` — ojo, es `"defecto"`, no `"default"` |
| `id_preferencia_idioma` | `int \| None` | — |
| `version_perfil` | `int \| None` | El cliente la devuelve en el siguiente `PATCH` |

**`PreferenciaIdiomaResponse`:**

| Campo | Tipo |
|-------|------|
| `id_preferencia_idioma` | `int` |
| `id_usuario` | `int` |
| `locale_code` | `str` |
| `es_por_defecto` | `bool` |
| `fecha_actualizacion` | `datetime \| None` |
| `version_perfil` | `int \| None` |

---

### Dashboard — `/configuracion/personalizacion/dashboard`

> **Recurso RBAC:** `id_recurso = 25` — **Todos los roles autenticados.**
> Además, cada widget se filtra por el permiso `R` de **su propio recurso**
> (`modulo9.widgets.id_recurso`), así que dos roles con el mismo permiso sobre el dashboard ven
> catálogos distintos.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/` | `(25, R)` | Admin, Prod, Vet, Ing, Cont | `ObtenerDashboardUseCase` |
| `GET` | `/widgets` | `(25, R)` | Admin, Prod, Vet, Ing, Cont | `ObtenerCatalogoWidgetsUseCase` |
| `GET` | `/datos` | `(25, R)` | Admin, Prod, Vet, Ing, Cont | `ObtenerDatosDashboardUseCase` |
| `PATCH` | `/` | `(25, U)` | Admin, Prod, Vet, Ing, Cont | `GuardarDashboardUseCase` |
| `POST` | `/restaurar` | `(25, U)` | Admin, Prod, Vet, Ing, Cont | `RestaurarDashboardUseCase` |

#### `PATCH /configuracion/personalizacion/dashboard/` — Guardar layout

**Input `GuardarDashboardDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `layout_config` | `list[WidgetConfigDTO]` | Ver abajo. Máx. 12 con `visible: true` |
| `active_widget` | `list[str]` | Claves de `modulo9.widgets`. Máx. 12, sin repetir |
| `version_perfil` | `int \| None` | Opcional. La del último `GET`; si no coincide → 409 |

**`WidgetConfigDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_widget` | `int` | Debe existir en `modulo9.widgets` y ser legible por el rol |
| `posicion_fila` | `int` | 1–3 |
| `posicion_columna` | `int` | 1–4 |
| `span_columnas` | `int` | 1–2. `posicion_columna + span - 1` no puede pasar de 4 |
| `visible` | `bool` | `false` libera la celda y no cuenta para el límite |
| `orden` | `int` | ≥ 0 |

**Response `DashboardLayoutResponse`:**

| Campo | Tipo |
|-------|------|
| `id_dashboard_layout` | `int \| None` |
| `id_usuario` | `int` |
| `grid` | `list[WidgetConfigResponse]` |
| `active_widget` | `list[str]` |
| `fecha_actualizacion` | `datetime \| None` |
| `version_perfil` | `int \| None` |

**Errores del `PATCH`** (todos los flujos alternos del RF-28):

| HTTP | `error_code` | Cuándo |
|------|--------------|--------|
| 400 | `VAL_ENTRADA` | Fila, columna, span u orden fuera de rango (Pydantic) |
| 400 | `DESBORDE_HORIZONTAL` | Span 2 en la columna 4 |
| 400 | `LIMITE_WIDGETS_ALCANZADO` | Más de 12 activos en `layout_config` o `active_widget` |
| 400 | `ACTIVE_WIDGET_DUPLICADO` | `active_widget` repite una clave |
| 400 | `WIDGET_INEXISTENTE` | `id_widget` fuera del catálogo |
| 400 | `ACTIVE_WIDGET_INEXISTENTE` | Clave fuera del catálogo |
| 403 | `ACCESO_DENEGADO` | Rol sin permiso `U` sobre `dashboard_layout` |
| 403 | `WIDGET_NO_AUTORIZADO` | Widget de un módulo que el rol no lee |
| 409 | `SOLAPAMIENTO_WIDGETS` | Celda ocupada, o dentro del rango de expansión de otro |
| 409 | `CONFLICTO_PERFIL_MODIFICADO` | `version_perfil` desfasada |

#### `GET /configuracion/personalizacion/dashboard/widgets` — Catálogo por rol

**Response `list[WidgetCatalogoResponse]`:** `id_widget`, `clave`, `nombre`, `grupo`,
`span_predeterminado`.

#### `GET /configuracion/personalizacion/dashboard/datos` — Datos de los widgets visibles

**Response `list[WidgetDatosResponse]`:** `id_widget`, `clave`, `nombre`, `posicion_fila`,
`posicion_columna`, `span_columnas`, `orden`, `sin_datos`, `mensaje`, `datos`.

Un widget sin fuente configurada, o cuya fuente no devolvió filas, llega con `sin_datos: true` y
`mensaje` con el texto del RF; conserva su posición en la grilla.

#### `POST /configuracion/personalizacion/dashboard/restaurar` — Restaurar

Aplica la fila de `modulo9.dashboard_layouts_default` del rol del usuario. Si el rol no tiene una
(rol creado después de la migración `a7f3c92e4d18`) responde `500 RESTAURACION_SIN_DEFAULT` sin
escribir nada.

---

### Plantillas — `/configuracion/plantillas`

> **Recurso RBAC:** `id_recurso = 28`
> Solo Admin e Ingeniero de Campo tienen acceso.

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|-------------------|----------|
| `GET` | `/` | `(28, R)` | Admin, Ing | `ConsultarPlantillasUseCase.listar_plantillas` |
| `POST` | `/` | `(28, C)` | Admin, Ing | `RegistrarPlantillaUseCase` |
| `GET` | `/{id_plantilla}` | `(28, R)` | Admin, Ing | `ConsultarPlantillasUseCase.obtener_plantilla` |
| `POST` | `/{id_plantilla}/aplicar` | `(28, E)` | Admin, Ing | `AplicarPlantillaUseCase` |
| `GET` | `/historial` | `(28, R)` | Admin, Ing | `ConsultarPlantillasUseCase.listar_historial` |

#### `POST /configuracion/plantillas/` — Crear plantilla

**Input `RegistrarPlantillaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `template_name` | `str` | 3–50 chars |
| `id_especie` | `int` | Especie origen del snapshot |
| `params_snapshot` | `dict[str, Any]` | Snapshot de ciclos, patologías, métricas, umbrales |

**Response `PlantillaResponse`:**

| Campo | Tipo |
|-------|------|
| `id_plantilla` | `int` |
| `id_especie` | `int` |
| `id_usuario` | `int` |
| `template_name` | `str` |
| `params_snapshot` | `dict[str, Any]` |
| `version` | `int` |
| `fecha_creacion` | `datetime` |

---

#### `POST /configuracion/plantillas/{id_plantilla}/aplicar` — Aplicar plantilla

**Input `AplicarPlantillaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_especie_destino` | `int` | Especie destino donde se aplica la plantilla |
| `fecha_actualizacion_especie_destino` | `datetime \| null` | Control de concurrencia sobre la especie destino (`fecha_actualizacion`, no `fecha_creacion`; puede ser `null` si la especie nunca fue editada) |

**Response `AplicacionPlantillaResponse`:**

| Campo | Tipo |
|-------|------|
| `id_aplicacion_plantilla` | `int` |
| `id_plantilla` | `int` |
| `id_usuario` | `int` |
| `target_config` | `dict[str, Any]` |
| `before_snapshot` | `dict[str, Any] \| None` |
| `after_snapshot` | `dict[str, Any] \| None` |
| `fecha_aplicacion` | `datetime \| None` |

---

## Tabla de permisos RBAC usados

> Datos extraídos de `modulo1.permisos`. Acciones: C=1 Crear, R=2 Leer, U=3 Actualizar, D=4 Eliminar, E=5 Ejecutar.

| `id_recurso` | Recurso | Admin | Productor | Veterinario | Ing. Campo | Contador |
|---|---|---|---|---|---|---|
| 8 | `especies` | C,R,U,D | R | R,U | R,U | R |
| 9 | `fincas` | C,R,U,D | R | R | R | — |
| 10 | `infraestructuras` | C,R,U,D | R | R | R | — |
| 11 | `dispositivos_iot` | C,R,U,D | R | — | C,R,U,D | — |
| 12 | `sensores` | C,R,U | R | R | C,R,U | — |
| 17 | `ciclos_biologicos` | C,R,U,D | — | C,R,U,D | — | — |
| 18 | `patologias` | C,R,U,D | — | C,R,U,D | — | — |
| 19 | `metricas_produccion` | C,R,U,D | — | C,R,U,D | — | — |
| 20 | `umbrales_ambientales` | C,R,U,D | — | C,R,U,D | — | — |
| 21 | `configuraciones_globales` | C,R,U | — | — | — | — |
| 22 | `contexto_interfaz` | R | R | R | R | R |
| 23 | `identidad_visual` | C,R,U | — | — | — | — |
| 24 | `tema_visual` | R,U | R,U | R,U | R,U | R,U |
| 25 | `dashboard_layout` | R,U | R,U | R,U | R,U | R,U |
| 26 | `preferencia_idioma` | R,U | R,U | R,U | R,U | R,U |
| 27 | `configuracion_ui_global` | R,U | — | — | — | — |
| 28 | `plantillas` | C,R,E | — | — | C,R,E | — |

---

## Use Cases — resumen de firmas

| Clase | `execute()` — parámetros principales |
|-------|--------------------------------------|
| `RegistrarEspecieUseCase` | `(dto: RegistrarEspecieDTO, usuario: UsuarioActual) → Especie` |
| `ConsultarCatalogoUseCase` | `(solo_activas: bool) → list[Especie]` |
| `EditarEspecieUseCase` | `(id_especie: int, dto: EditarEspecieDTO, usuario: UsuarioActual) → Especie` |
| `DesactivarEspecieUseCase` | `(id_especie: int, usuario: UsuarioActual) → Especie` |
| `ReactivarEspecieUseCase` | `(id_especie: int, usuario: UsuarioActual) → Especie` |
| `RegistrarFincaUseCase` | `(dto: RegistrarFincaDTO, usuario: UsuarioActual) → Finca` |
| `ConsultarFincasUseCase.listar` | `(id_usuario_filtro, solo_activas) → list[Finca]` |
| `ConsultarFincasUseCase.obtener` | `(id_finca: int, id_usuario_filtro) → Finca` |
| `EditarFincaUseCase` | `(id_finca: int, dto: EditarFincaDTO, usuario: UsuarioActual) → Finca` |
| `DesactivarFincaUseCase` | `(id_finca: int, usuario: UsuarioActual) → Finca` |
| `RegistrarInfraestructuraUseCase` | `(dto: RegistrarInfraestructuraDTO, usuario: UsuarioActual) → Infraestructura` |
| `ConsultarInfraestructurasUseCase.listar_por_finca` | `(finca_id: int, usuario, solo_activas) → list[Infraestructura]` |
| `ConsultarInfraestructurasUseCase.obtener` | `(id: int) → Infraestructura` |
| `EditarInfraestructuraUseCase` | `(id: int, dto: EditarInfraestructuraDTO, usuario: UsuarioActual) → Infraestructura` |
| `DesactivarInfraestructuraUseCase` | `(id: int, usuario: UsuarioActual) → Infraestructura` |
| `RegistrarDispositivoIotUseCase` | `(dto: RegistrarDispositivoIotDTO, usuario: UsuarioActual) → DispositivoIot` |
| `ConsultarDispositivosIotUseCase.listar` | `(usuario, solo_activos) → list[DispositivoIot]` |
| `ConsultarDispositivosIotUseCase.obtener` | `(id: int, usuario) → DispositivoIot` |
| `DesactivarDispositivoIotUseCase` | `(id: int, usuario: UsuarioActual) → DispositivoIot` |
| `RegistrarSensorUseCase` | `(id_dispositivo: int, dto: RegistrarSensorDTO, usuario: UsuarioActual) → Sensor` |
| `ConsultarSensoresUseCase.listar_por_dispositivo` | `(id_dispositivo: int) → list[Sensor]` |
| `ConfigurarRemotamenteUseCase` | `(id_dispositivo: int, dto: ConfigurarRemotamenteDTO, usuario: UsuarioActual) → ConfiguracionRemota` |
| `ConsultarConfiguracionesUseCase.listar_por_dispositivo` | `(id_dispositivo: int) → list[ConfiguracionRemota]` |
| `AsociarSensorAreaUseCase` | `(id_sensor: int, dto: AsociarSensorAreaDTO, usuario: UsuarioActual) → SensorArea` |
| `ConsultarAsociacionesUseCase.listar_por_sensor` | `(id_sensor: int) → list[SensorArea]` |
| `RegistrarCalibracionUseCase` | `(id_sensor: int, dto: RegistrarCalibracionDTO, usuario: UsuarioActual) → Calibracion` |
| `ConsultarCalibracionesUseCase.listar_por_sensor` | `(id_sensor: int) → list[Calibracion]` |
| `RegistrarCicloUseCase` | `(dto: RegistrarCicloDTO, usuario: UsuarioActual) → CicloBiologico` |
| `ConsultarCiclosUseCase` | `(id_especie: int, solo_activas: bool) → list[CicloBiologico]` |
| `EditarCicloUseCase` | `(id: int, dto: EditarCicloDTO, usuario: UsuarioActual) → CicloBiologico` |
| `DesactivarCicloUseCase` | `(id: int, usuario: UsuarioActual) → CicloBiologico` |
| `RegistrarPatologiaUseCase` | `(dto: RegistrarPatologiaDTO, usuario: UsuarioActual) → EspeciePatologia` |
| `ConsultarPatologiasUseCase` | `(id_especie: int, solo_activas: bool) → list[EspeciePatologia]` |
| `EditarPatologiaUseCase` | `(id: int, dto: EditarPatologiaDTO, usuario: UsuarioActual) → Patologia` |
| `DesactivarPatologiaUseCase` | `(id: int, usuario: UsuarioActual) → Patologia` |
| `RegistrarMetricaUseCase` | `(dto: RegistrarMetricaDTO, usuario: UsuarioActual) → MetricaProduccion` |
| `ConsultarMetricasUseCase` | `(id_especie: int, solo_activas: bool) → list[MetricaProduccion]` |
| `EditarMetricaUseCase` | `(id: int, dto: EditarMetricaDTO, usuario: UsuarioActual) → MetricaProduccion` |
| `DesactivarMetricaUseCase` | `(id: int, usuario: UsuarioActual) → MetricaProduccion` |
| `RegistrarUmbralUseCase` | `(dto: RegistrarUmbralDTO, usuario: UsuarioActual) → UmbralAmbiental` |
| `ConsultarUmbralesUseCase` | `(id_especie: int, solo_activas: bool) → list[UmbralAmbiental]` |
| `EditarUmbralUseCase` | `(id: int, dto: EditarUmbralDTO, usuario: UsuarioActual) → UmbralAmbiental` |
| `DesactivarUmbralUseCase` | `(id: int, usuario: UsuarioActual) → UmbralAmbiental` |
| `CrearConfiguracionUseCase` | `(dto: CrearConfiguracionDTO, usuario: UsuarioActual) → ConfiguracionGlobal` |
| `ConsultarConfiguracionUseCase` | `() → ConfiguracionGlobal \| None` |
| `ActualizarConfiguracionUseCase` | `(id: int, dto: ActualizarConfiguracionDTO, usuario: UsuarioActual) → ConfiguracionGlobal` |
| `ObtenerContextoUseCase` | `(usuario: UsuarioActual) → ContextoInterfaz` |
| `ObtenerIdentidadVisualUseCase` | `(id_finca: int) → IdentidadVisual \| None` |
| `GuardarIdentidadVisualUseCase` | `(dto, logo_bytes, logo_content_type, usuario: UsuarioActual) → IdentidadVisual` |
| `ActualizarIdentidadVisualUseCase` | `(id_finca: int, dto, logo_bytes, logo_content_type, usuario: UsuarioActual) → IdentidadVisual` |
| `ObtenerTemaResueltoUseCase` | `(usuario: UsuarioActual) → dict` |
| `GuardarTemaPersonalUseCase` | `(dto: GuardarTemaDTO, usuario: UsuarioActual) → TemaVisual` |
| `GuardarTemaGlobalUseCase` | `(dto: GuardarTemaDTO, usuario: UsuarioActual) → TemaVisual` |
| `ObtenerIdiomaResueltoUseCase` | `(usuario: UsuarioActual) → dict` |
| `GuardarIdiomaPersonalUseCase` | `(dto: GuardarIdiomaDTO, usuario: UsuarioActual) → PreferenciaIdioma` |
| `GuardarIdiomaGlobalUseCase` | `(dto: GuardarIdiomaDTO, usuario: UsuarioActual) → PreferenciaIdioma` |
| `ObtenerDashboardUseCase` | `(usuario: UsuarioActual) → DashboardLayout` |
| `GuardarDashboardUseCase` | `(dto: GuardarDashboardDTO, usuario: UsuarioActual) → DashboardLayout` |
| `RestaurarDashboardUseCase` | `(usuario: UsuarioActual) → DashboardLayout` |
| `ConsultarPlantillasUseCase.listar_plantillas` | `() → list[Plantilla]` |
| `ConsultarPlantillasUseCase.obtener_plantilla` | `(id_plantilla: int) → Plantilla \| None` |
| `ConsultarPlantillasUseCase.listar_historial` | `() → list[AplicacionPlantilla]` |
| `RegistrarPlantillaUseCase` | `(dto: RegistrarPlantillaDTO, usuario: UsuarioActual) → Plantilla` |
| `AplicarPlantillaUseCase` | `(id_plantilla: int, dto: AplicarPlantillaDTO, usuario: UsuarioActual) → AplicacionPlantilla` |
