# API Reference — `src/telemetry/`

> Generado el 2026-07-23. **Actualizado 2026-07-27** (nuevo endpoint de
> mantenimiento RF-60 y corrección del bug de reevaluar RF-62). Solo
> documentación — no subir al repositorio.
>
> **Este módulo mezcla dos regímenes de autenticación distintos.** A diferencia
> de otros módulos (p. ej. `src/configuration/`) donde *todo* endpoint exige
> sesión de usuario, aquí conviven:
>
> 1. **Endpoints humanos** (dashboard, historial, alertas, calidad, auditoría,
>    vinculaciones, estado de dispositivos) → `Authorization: Bearer <jwt>` +
>    RBAC vía `require_permission(id_recurso, id_accion)`.
> 2. **Endpoints de ingesta de dispositivos IoT** (telemetría, visión, alertas
>    edge, eventos edge, heartbeat) → **sin JWT**. Los llama el broker MQTT,
>    no el nodo (D3 de `AIOT-DEV-03`): exigen su token de servicio
>    (`Authorization: Bearer`, variable `BROKER_SERVICE_TOKEN`, dependencia
>    `require_token_servicio_broker` de `src/shared/broker_auth.py`). Sin token
>    o con uno distinto → `401 TOKEN_SERVICIO_INVALIDO`; sin la variable
>    configurada → `503 TOKEN_SERVICIO_NO_CONFIGURADO`. El `serial` del body ya
>    no es credencial: es la identidad del nodo que el broker autenticó por
>    MQTT, y el use case exige que `device_id`/`sensor_id` le pertenezcan. El
>    broker no tiene `id_rol`, así que estos endpoints omiten
>    `require_permission` por diseño, no por descuido.
>
> Ver la sección **"Modos de autenticación"** más abajo para la lista exacta
> de qué exige qué, y **"Cómo funciona el RBAC en este módulo"** para la
> mecánica completa de sesión + permiso.

---

## Prefijos de rutas

| Router | Prefijo | Tag Swagger |
|--------|---------|-------------|
| `telemetria_router.py` | `/iot/telemetria` | Telemetría IoT - Ingesta |
| `alerta_router.py` | `/iot/alertas` | Telemetría IoT - Alertas |
| `evento_edge_router.py` | `/iot/eventos-edge` | Telemetría IoT - Eventos Edge |
| `infraestructura_iot_router.py` | `/iot` | Telemetría IoT - Infraestructura |
| `monitoreo_router.py` | `/iot/monitoreo` | Telemetría IoT - Monitoreo |
| `vinculacion_router.py` | `/iot/vinculaciones` | Telemetría IoT - Vinculaciones RF-61 |
| `calidad_router.py` | `/iot/calidad` | Telemetría IoT - Calidad RF-62 |
| `auditoria_iot_router.py` | `/iot/auditoria` | Telemetría IoT - Auditoría RF-63 |

Los 8 routers se registran sin prefijo/tag adicional en `main.py` — el prefijo
y el tag vienen ya definidos en cada `APIRouter(...)`.

---

## Cómo funciona el RBAC en este módulo

`require_permission(id_recurso, id_accion)` (`src/shared/rbac.py`) es una
fábrica de dependencias FastAPI. Internamente declara:

```python
def dependency(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> None:
    ...
```

**Esto es clave y no siempre es obvio leyendo el router**: aunque un endpoint
solo muestre `dependencies=[Depends(require_permission(33, 2))]` sin declarar
`usuario_actual` como parámetro propio, `require_permission` **ya está exigiendo
una sesión JWT activa** por sí solo, porque `get_current_user` es una
sub-dependencia suya. No hace falta declarar `get_current_user` aparte para que
la autenticación se aplique. En este módulo, de hecho, todos los endpoints
protegidos por RBAC sí vuelven a declarar `usuario_actual: UsuarioActual =
Depends(get_current_user)` como parámetro — pero es solo para poder leer
`id_usuario`/`id_rol` dentro del handler; FastAPI cachea la dependencia por
request, así que `get_current_user` **no se ejecuta dos veces** (no hay doble
query a DB).

### Qué exige `get_current_user` para considerar la sesión "activa"

(`src/identity_access/infrastructure/dependencies.py`)

1. Header `Authorization: Bearer <token>` presente → si falta, `401
   TOKEN_REQUERIDO`.
2. El JWT decodifica y valida firma vía `verify_token` (`src/shared/jwt.py`).
3. El `jti` del token (`id_token`) debe existir en `modulo1.tokens` **y no estar
   revocado** (`fecha_uso IS NULL`) → si está revocado o no existe, `401
   TOKEN_REVOCADO`.
4. **Timeout de inactividad de 30 minutos**: si `ahora - cuenta.ultimo_acceso >
   30 min`, la sesión se cierra de forma perezosa en ese mismo request
   (`Sesiones.es_activa = False`, se marca el token como usado) y se responde
   `401 SESION_EXPIRADA_INACTIVIDAD`. Si la sesión sigue vigente, se actualiza
   `cuenta.ultimo_acceso = ahora` (con su propio `commit()`) y la request
   continúa.

Solo si las 4 condiciones pasan, `get_current_user` retorna `UsuarioActual
(id_usuario, id_token, id_rol)`, y recién ahí `require_permission` puede
evaluar el permiso:

5. Se consulta `modulo1.permisos` filtrando por `(id_rol, id_recurso,
   id_accion, es_activo=True)`. Si no hay fila, `403 ACCESO_DENEGADO`.

En resumen: **un token válido pero de un rol sin el permiso da 403; un token
ausente, revocado o inactivo por 30+ min da 401 antes de siquiera llegar a
evaluar el permiso.** Para probar cualquier endpoint de este módulo marcado
como "JWT + RBAC" hace falta primero `POST /sesiones/` (login) y reutilizar el
`Authorization: Bearer <jwt>` resultante en cada request subsecuente dentro de
la ventana de 30 minutos.

### Modos de autenticación — tabla rápida

| Endpoint | Auth | Detalle |
|----------|------|---------|
| `POST /iot/telemetria` | Token de servicio del broker | `serial` en el body; `device_id`/`sensor_id` deben pertenecerle (`modulo9.dispositivos_iot`/`sensores`), verificado dentro del use case. Header opcional `X-Gateway-Id` (trazabilidad de gateway LoRaWAN). |
| `POST /iot/telemetria/batch` | Token de servicio del broker | Igual que arriba, por cada registro del lote (máx. 500). |
| `POST /iot/telemetria/vision` | Token de servicio del broker | Sobre D4 con serial y área autorizada, o lote compatible anterior. Ver DEV-07. |
| `POST /iot/alertas` | Token de servicio del broker | `serial` en el body; el router valida el dispositivo manualmente vía `DispositivoM09Adapter.obtener_dispositivo_activo`, lanzando `AuthenticationError` si es inválido/inactivo. |
| `POST /iot/eventos-edge` | Token de servicio del broker | `serial` en el body, verificado dentro del use case. Header opcional `X-Gateway-Id`. |
| `POST /iot/heartbeat` | Token de servicio del broker | `device_id` y `serial` en el body (antes headers `X-Device-*`), validados en `RecibirHeartbeatUseCase`. |
| Todos los demás (20 endpoints) | JWT + RBAC | `Authorization: Bearer <jwt>` + `require_permission(id_recurso, id_accion)` — ver detalle por router más abajo. |

Ningún endpoint de este módulo es "público" en el sentido de `configuration`
(cero autenticación): los 6 de arriba requieren igualmente probar la identidad
del dispositivo, solo que con un mecanismo distinto al JWT humano. Visión también exige ese token.

---

## Endpoints

### Ingesta — `/iot/telemetria`

> **DEV-05, 2026-10-17 — ingesta B+.** HTTP y el broker persisten mediante
> `modulo3.fn_ingesta_telemetria`, cuya firma se conserva. `201` confirma la
> persistencia RF-53; RF-61, RF-62 y el semáforo se procesan después del commit.
> Un fallo de estas etapas queda pendiente y se reintenta desde las filas
> confirmadas, sin exigir callback del broker. RF-63 registra la finalización
> de cada responsabilidad; una evaluación de calidad por sí sola no acredita
> la finalización de las otras etapas.
>
> La credencial HTTP actual se conserva hasta DEV-06. Los contratos DTO y de
> respuesta continúan vigentes. La bitácora de éxito de ingesta tiene un solo
> escritor: `trg_rf53_04_bitacora_persistida`. Los rechazos devueltos por la
> función se confirman para conservar su bitácora; la escritura de esa evidencia
> SQL requiere DB-02. Ver [diagnóstico y validación DEV-05](dev05_ingesta_bplus_postcommit.md).


> **INC-M03-130-G16 / #685 — RF-53 y RF-62.** La ingesta marca
> `frecuencia_anomala` para un intervalo al vecino cronológico más cercano
> menor que 0,5 o mayor que 2 veces el muestreo configurado en M09; la primera
> lectura no se marca sin un vecino. Se conserva `frecuencia_muestreo_min`
> como snapshot del valor aplicado al insertar. La marca no rechaza la lectura
> ni modifica lecturas previas; `EVENTO_EDGE` no es periódico.
> El drift se consulta en `flags_detectados.posible_drift` de la evaluación
> vigente mediante `GET /iot/calidad/{id_telemetria}`. El campo inicial
> `telemetrias.posible_drift` no representa el resultado posterior de RF-62.
> Un `201` de ingesta puede preceder a la evaluación; no certifica ausencia
> de drift. Sin cambios en DTOs, respuestas, credenciales ni RBAC.
> Requiere la migración `c685130a0260`; ver el
> [diagnóstico de #685](inc_m03_130_g16_rf53_marcas_calidad.md).

| Método | Ruta | Auth | Use Case |
|--------|------|------|----------|
| `POST` | `/` | Broker (token de servicio) | `IngerirTelemetriaUseCase` |
| `POST` | `/batch` | Broker (token de servicio; `serial` por registro) | `SincronizarBufferUseCase` |
| `POST` | `/vision` | Broker (token de servicio) | `IngerirObservacionesVisionUseCase` |

#### `POST /iot/telemetria/vision` — Sobre D4 (DEV-07)

Acepta un objeto `serial`, `area_id`, `ventana_inicio`, `ventana_fin`,
`componentes`, `calidad`, `version_cascada`. Las fechas requieren zona y
`ventana_inicio < ventana_fin`; RF-53 actualizado define fin como captura.
`componentes` exige densidad `[0,1]`, dispersión y movimiento `≥0`, finitos.
`calidad` exige cobertura `[0,1]`, tracks enteros no negativos, fps finito no
negativo y el estado admitido por el catálogo SQL vigente. `version_cascada`
exige detector/seguimiento/métricas/anomalías como strings no vacíos.

Aliases de nombres equivalentes: `dispositivo_serial` y `indicadores_calidad`.
Se rechazan aliases contradictorios, campos adicionales y aptitud/índice
enviados por el cliente. Se conserva el lote anterior `device_id`, `serial`,
`area_id`, `observaciones`; no se mezcla silenciosamente con D4.

HTTP 201 devuelve el resultado existente y, para las nuevas observaciones,
ventana y versiones. El backend calcula aptitud; NIC41 siempre false. Los
reenvíos se cuentan como duplicados y no sobrescriben el registro original.
DB-03 mapea inicio a `fecha_inicio_ventana` y versiones a `json_version_cascada`.

**Compatibilidad pendiente:** esta adaptación conserva la fórmula heredada
y los estados SQL `CALIBRADA/DEGRADADA/SIN_DETECCION`. Los RF actualizados ya
definen otros estados, fórmula ponderada y campos adicionales. No se presenta
esta implementación como soporte completo de AIOT-SPEC-01; ver
`rf53_dev07_vision_d4.md` y la solicitud de compatibilidad correspondiente.

#### `POST /iot/telemetria` — Ingerir lectura de sensor (RF-53 Flujo A/B)

**Input `IngerirTelemetriaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `device_id` | `int` | `> 0` |
| `sensor_id` | `int` | `> 0` |
| `tipo_variable` | `str` | 2–40 chars, se normaliza a mayúsculas |
| `valor` | `Decimal` | — |
| `unidad` | `str` | 1–20 chars |
| `timestamp_captura` | `datetime` | — |
| `serial` | `str` | 1–100 chars — identidad del nodo, no credencial |
| `timestamp_envio` | `datetime \| None` | Opcional |
| `origen` | `str` | Default `TIEMPO_REAL` — enum `{TIEMPO_REAL, BUFFER_LOCAL, EDGE_AGREGADO}` |
| `frecuencia_muestreo` | `int \| None` | `> 0` |
| `valor_agregado` | `bool` | Default `false` |
| `ventana_agregacion` | `int \| None` | `> 0` |
| `latitud` / `longitud` | `Decimal \| None` | Opcional |
| `estado_conectividad` | `bool \| None` | Opcional |
| `nivel_bateria` | `Decimal \| None` | `0–100` |
| `calidad_senal_rssi` / `calidad_senal_snr` | `Decimal \| None` | Opcional |
| `checksum` | `str \| None` | Opcional |
| `categoria_variable` | `str \| None` | Opcional |

**Response `TelemetriaResponse` (201):**

| Campo | Tipo |
|-------|------|
| `id_telemetria` | `int` |
| `estado_calidad` | `str` |
| `timestamp_procesamiento` | `datetime` |
| `latencia_procesamiento_ms` | `int \| None` |

---

#### `POST /iot/telemetria/batch` — Sincronización de buffer (RF-53 Flujo C, máx. 500)

**Input `IngerirTelemetriaBatchDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `registros` | `list[IngerirTelemetriaDTO]` | 1–500 elementos |
| `idempotency_key` | `str \| None` | Opcional |

**Response `IngestaBatchResponse` (200):**

| Campo | Tipo |
|-------|------|
| `total` | `int` |
| `aceptados` | `int` |
| `rechazados` | `int` |
| `duplicados` | `int` |
| `detalle` | `list[ItemBatchResponse]` |

**`ItemBatchResponse`:** `sensor_id: int`, `timestamp_captura: datetime`, `estado: str`, `id_telemetria: int \| None`, `error: str \| None`

---

### Alertas — `/iot/alertas`

> **Recurso RBAC:** `id_recurso = 32` (`alertas_operativas`)

| Método | Ruta | Auth | Roles autorizados | Use Case |
|--------|------|------|--------------------|----------|
| `POST` | `/` | Dispositivo IoT | — (sin RBAC) | `GenararAlertaUseCase` |
| `GET` | `/` | JWT + RBAC `(32, R)` | Admin, Prod, Vet, Ing | `ConsultarAlertasUseCase.listar` |
| `GET` | `/{id_alerta}` | JWT + RBAC `(32, R)` | Admin, Prod, Vet, Ing | `ConsultarAlertasUseCase.obtener_detalle` |
| `PATCH` | `/{id_alerta}/estado` | JWT + RBAC `(32, U)` | Admin, Prod, Vet (**no Ing.**) | `ActualizarEstadoAlertaUseCase` |

> Nota RBAC: en `modulo1.permisos`, Ingeniero de Campo solo tiene la acción
> `R` sobre el recurso 32 — **no** tiene `U`. Es decir, Ingeniero puede leer
> alertas operativas pero no cambiarles el estado (eso es responsabilidad de
> Admin/Productor/Veterinario). Contador no tiene ningún permiso sobre este
> recurso.

#### `POST /iot/alertas` — Generar alerta desde evento (device-auth, FA-01–FA-08)

**Input `ProcesarEventoAlertaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `device_id` / `sensor_id` | `int` | `> 0` |
| `serial` | `str` | 1–100 chars — identidad del nodo, no credencial |
| `tipo_variable` | `str` | 2–50 chars, mayúsculas |
| `valor` | `Decimal` | — |
| `unidad` | `str` | 1–20 chars |
| `timestamp_evento` | `datetime` | — |
| `estado_dato` | `str` | 2–30 chars — enum `{LECTURA_VALIDA, FUERA_DE_RANGO, ERROR_CALIBRACION}` |
| `severidad_edge` | `str` | 2–20 chars — enum `{LEVE, MODERADO, CRITICO}` |
| `origen_evento` | `str` | 2–20 chars — enum `{EDGE, BACKEND, IA}` |
| `id_evento_edge_computing` / `id_telemetria` / `id_paquete_inferencia` | `int \| None` | Trazabilidad — al menos uno se espera, no forzado a nivel de DTO |
| `reglas_activadas` | `list[str]` | Default `[]` |
| `tipo_alerta_ia` / `severidad_ia` | `str \| None` | `severidad_ia` comparte el enum `{LEVE, MODERADO, CRITICO}` |
| `probabilidad_ia` | `Decimal \| None` | `0–1` |
| `correlacion_variables` / `metadata_evento` | `dict \| None` | Opcional |

**Response `ResultadoGeneracionAlertaSchema` (201):**

| Campo | Tipo |
|-------|------|
| `es_duplicado` | `bool` |
| `id_alerta` | `int \| None` |
| `tipo_alerta` | `str \| None` |
| `severidad` | `str \| None` |
| `alerta_existente_id` | `int \| None` |
| `motivo_descarte` | `str \| None` |

---

#### `GET /iot/alertas` — Listar alertas

**Query params (todos opcionales salvo paginación):** `estado`, `severidad`, `tipo_alerta`, `id_sensor: int`, `id_activo_biologico: int`, `origen_evento`, `fecha_desde` / `fecha_hasta: datetime`, `pagina: int (≥1, default 1)`, `por_pagina: int (1–200, default 50)`.

**Response `ListaAlertasSchema`:** `total`, `pagina`, `por_pagina`, `items: list[AlertaSchema]`

**`AlertaSchema`:**

| Campo | Tipo |
|-------|------|
| `id_alerta` | `int` |
| `tipo_alerta` | `str` |
| `severidad` | `str` |
| `estado_alerta` | `str` |
| `origen_evento` | `str` |
| `tipo_variable` | `str` |
| `valor` | `Decimal \| None` |
| `unidad` | `str \| None` |
| `fecha_evento` / `fecha_generacion` | `datetime` |
| `fecha_registro` / `fecha_notificacion` / `fecha_atencion` / `fecha_resolucion` / `fecha_vencimiento` / `ultima_ocurrencia` | `datetime \| None` |
| `frecuencia_evento` | `int` — default `1` |
| `reglas_activas` | `list[Any]` — default `[]` |
| `contexto_activo_biologico` / `metadato_evento` | `dict \| None` |
| `accion_sugerida` / `motivo_descarte` / `diagnostico` / `conflicto_resolucion` / `severidad_edge_original` / `severidad_ia` | `str \| None` |
| `tiene_inferencia_no_disponible` / `tiene_contexto_incompleto` / `tiene_generada_por_reevaluacion` | `bool` — default `False` |
| `id_sensor` / `id_dispositivo_ioit` / `id_activo_biologico` / `id_infraestructura` / `id_evento_edge_computing` / `id_telemetria` / `id_paquete_inferencia` / `id_usuario_atencion` / `id_usuario_resolucion` / `referencia_alerta_original` | `int \| None` |

---

#### `GET /iot/alertas/{id_alerta}` — Detalle con historial de estados

**Response `AlertaDetalleSchema`:** `AlertaSchema` + `historico_estados: list[HistoricoEstadoAlertaSchema] = []`

**`HistoricoEstadoAlertaSchema`:** `id_historico_estado_alerta: int \| None`, `id_alerta: int`, `estado_anterior: str`, `estado_nuevo: str`, `fecha_cambio: datetime`, `id_usuario: int \| None`, `motivo: str \| None`

---

#### `PATCH /iot/alertas/{id_alerta}/estado` — Actualizar estado de alerta

**Input `ActualizarEstadoAlertaDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nuevo_estado` | `str` | 2–30 chars — enum `{EN_ATENCION, RESUELTA, DESCARTADA, VENCIDA}`, se normaliza a mayúsculas |
| `motivo` | `str \| None` | Opcional, máx. 500 chars |

**Response:** `AlertaSchema`

---

### Eventos Edge — `/iot/eventos-edge`

| Método | Ruta | Auth | Use Case |
|--------|------|------|----------|
| `POST` | `/` | Broker (token de servicio) | `RecibirEventoEdgeUseCase` |

#### `POST /iot/eventos-edge` — Procesar evento de edge computing (RF-56)

**Input `RecibirEventoEdgeDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `device_id` / `sensor_id` | `int` | — |
| `serial` | `str` | 1–100 chars — identidad del nodo, no credencial |
| `clasificacion_rf55` | `str` | Enum `{NORMAL, DESVIACION_SIMPLE, DESVIACION_COMPUESTA, ERROR_CONFIGURACION}` |
| `severidad` | `str \| None` | Enum `{LEVE, MODERADO, CRITICO}` |
| `variables_involucradas` | `list[VariableInvolucradaDTO]` | Ver abajo |
| `timestamp_captura` / `timestamp_procesamiento_edge` | `datetime` | Normalizados a UTC; procesamiento mayor o igual a captura (INC-M03-110-G42) |
| `origen` | `str` | Default `TIEMPO_REAL` — enum `{TIEMPO_REAL, BUFFER_LOCAL}` |
| `estado_conectividad` | `bool` | — |
| `metadata_edge` | `dict \| None` | Opcional |
| `version_modelo_objetivo` | `str \| None` | Opcional |

**`VariableInvolucradaDTO`:** `tipo_variable: str`, `valor: Decimal`, `unidad: str`, `timestamp_captura: datetime \| None`

**Response `EventoEdgeResponse`:**

| Campo | Tipo |
|-------|------|
| `id_evento_edge_computing` | `int` |
| `clasificacion_rf55` | `str` |
| `severidad` | `str \| None` |
| `estado_conectividad` | `bool` |
| `fecha_captura` | `datetime` |
| `fecha_procesamiento` | `datetime` |
| `paquete_inferencia_estado` | `str \| None` |

**DEV-17 / P7:** con `MotorInferenciaStubAdapter`, una desviación válida devuelve
`201` con `paquete_inferencia_estado = PENDIENTE`. El paquete está persistido,
con `intento_envios = 0`; el 201 confirma recepción/procesamiento, no entrega a IA.
`NORMAL` y `ERROR_CONFIGURACION` conservan el estado `null` (sin paquete).
Solo una confirmación positiva de un adaptador integrado permite `ENVIADO`.
La reconsolidación del mismo `id_evento_edge_computing` recupera su paquete
existente sin reenviarlo. No se define una nueva API de consulta o reintentos.

**INC-M03-110-G42 / RF-55 CA-13:** si el procesamiento es anterior a la captura,
se responde `400 ORDEN_TEMPORAL_INVALIDO`, asociado al campo
`timestamp_procesamiento_edge`. No se persiste el evento ni se genera un paquete;
el rechazo sigue el registro existente `EVENTO_EDGE_RECHAZADO` de RF-56 E1.
Se permite igualdad por precisión del reloj, según decisión confirmada por el usuario.
La respuesta `201` expone `fecha_captura` y `fecha_procesamiento` del evento
persistido: son los instantes recibidos, normalizados a UTC, no la hora del servidor.
Se conservan los rechazos existentes `TIMESTAMP_FUTURO` y `TIMESTAMP_EXPIRADO`.
Esta respuesta permite observar ambos tiempos durante la recepción; no agrega un
GET histórico ni demuestra su generación en el firmware Edge.

---

### Infraestructura IoT — `/iot`

| Método | Ruta | Auth | Recurso RBAC | Roles autorizados | Use Case |
|--------|------|------|--------------|--------------------|----------|
| `POST` | `/heartbeat` | Broker (token de servicio) | — | — | `RecibirHeartbeatUseCase` |
| `GET` | `/dispositivos/{id_dispositivo_iot}/estado` | JWT + RBAC `(35, R)` | 35 | Admin, Prod, Vet, Ing | `ObtenerEstadoDispositivoUseCase` |
| `GET` | `/dispositivos/{id_dispositivo_iot}/historial` | JWT + RBAC `(35, R)` | 35 | Admin, Prod, Vet, Ing | *(sin use case — llama al repositorio directo desde el router)* |
| `PATCH` | `/dispositivos/{id_dispositivo_iot}/mantenimiento` | JWT + RBAC `(35, U)` | 35 | **Solo Admin, Ing** | `AplicarMantenimientoDispositivoUseCase` |
| `GET` | `/alertas-tecnicas` | JWT + RBAC `(36, R)` | 36 | **Solo Admin, Ing** | `ConsultarAlertasUseCase.listar` (filtro `tipo_alerta='TECNICA'` fijo) |
| `PATCH` | `/alertas-tecnicas/{id_alerta}/estado` | JWT + RBAC `(36, U)` | 36 | **Solo Admin, Ing** | `ActualizarEstadoAlertaUseCase` |

> Nota RBAC: el recurso 36 (`alertas_tecnicas_iot`) solo tiene permisos
> asignados a Administrador e Ingeniero de Campo — Productor, Veterinario y
> Contador reciben `403` en ambos endpoints. Tiene sentido: las alertas
> técnicas son de infraestructura/dispositivos, no de manejo biológico.
>
> El recurso 35 (`infraestructura_iot`) tiene acción `U` asignada a Admin e
> Ingeniero en `modulo1.permisos`. Desde 2026-07-27 la consume el endpoint
> `PATCH /iot/dispositivos/{id}/mantenimiento` (transición manual
> `EN_MANTENIMIENTO ↔ ACTIVO`, RF-60 CA-7/CA-8). Las transiciones *automáticas*
> por conectividad las sigue aplicando `EvaluarEstadoDispositivosUseCase` (job
> periódico), que por diseño ignora `EN_MANTENIMIENTO` y no pisa la transición
> manual.

#### `POST /iot/heartbeat` — Recibir heartbeat de dispositivo (RF-60)

> **DEV-05:** el endpoint conserva autenticación y persistencia. El trigger
> registra contacto/reconexión; el procesador común a HTTP y MQTT aplica el
> buffer y las alertas técnicas después del commit. `A` y `L` representan
> buffer activo/lleno. El estado de mantenimiento se conserva.
> Batería/RSSI requieren los umbrales oficiales pendientes de Análisis/DEV-14;
> mientras no estén publicados en M09, su etapa queda pendiente con
> `PARAMETROS_HEARTBEAT_NO_DISPONIBLES`, sin perder el heartbeat ni su estado de buffer.


**Headers requeridos:** `Authorization: Bearer <BROKER_SERVICE_TOKEN>`. `device_id` y `serial` van en el body.

**Input `HeartbeatDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `device_id` | `int` | `> 0` |
| `serial` | `str` | 1–100 chars — `device_id` debe pertenecerle |
| `tipo_mensaje` | `str` | 1–30 chars |
| `nivel_bateria_pct` | `Decimal \| None` | `0–100` |
| `calidad_senal_rssi` / `calidad_senal_snr` | `Decimal \| None` | Opcional |
| `estado_local_buffer` | `str \| None` | Máx. 1 char — `'I'`=INACTIVO, `'A'`=ACTIVO, `'L'`=LLENO |
| `datos_pendientes_buffer` | `int` | Default `0`, `≥ 0` |
| `version_firmware` | `str \| None` | Máx. 50 chars |
| `coordenadas` | `Any \| None` | Opcional |
| `fecha_registro` | `datetime` | — |
| `reloj_sincronizado` | `bool` | Default `false` |
| `sensores_operativos` | `list[object] \| None` | Opcional; objetos `{sensor: string no vacío, operativo: boolean estricto}`. `[]` no indica fallo. Nombre físico DB-03: `json_sensores_operativos` |
| `temperatura_dispositivo` | `Decimal \| None` | Opcional; número JSON finito en °C, representable por `NUMERIC(5,2)` de DB-03 |

**Response `HeartbeatReciboSchema`:** `id_heartbeat`, `id_dispositivo_iot`, `tipo_mensaje`, `nivel_bateria_pct: Decimal \| None`, `calidad_senal_rssi/snr: Decimal \| None`, `estado_local_buffer`, `datos_pendientes_buffer: int`, `version_firmware`, `coordenadas: Any \| None`, `fecha_registro: datetime`, `fecha_recepcion: datetime`, `reloj_sincronizado: bool`

DEV-12 agrega a esa respuesta `sensores_operativos` y `temperatura_dispositivo`,
ambos nullable. HTTP 200 confirma persistencia; las alertas se evalúan después
del commit por el mismo worker que procesa los INSERT del broker.
`SENSOR_FISICO_FALLIDO` conserva los identificadores fallidos y el `id_heartbeat`
en metadata. Temperatura y firmware tienen etapas independientes: si falta su
política M09/FW-06, quedan pendientes con evidencia RF-63 y sin una alerta
ficticia. Requiere desplegar previamente DB-03 `65541db23c71`.

---

#### `GET /iot/dispositivos/{id_dispositivo_iot}/estado` — Estado actual + historial reciente

**Query:** `limite_historial: int` (1–100, default 20)

**Response `EstadoDispositivoDetalleSchema`:** `estado: EstadoDispositivoIoTSchema`, `historial: list[HistoricoTransicionSchema]`

**`EstadoDispositivoIoTSchema`:** `id_estado_dispositivo_iot`, `id_dispositivo_iot`, `estado_actual`, `fecha_ultimo_contacto: datetime \| None`, `id_ultimo_heartbeat: int \| None`, `tiempo_sin_contacto: int \| None` (segundos desde `fecha_ultimo_contacto`, calculados al responder — INC-M09-70-G29), `causa_primaria: str \| None`, `causas_secundarias: Any \| None`, `fecha_ultima_actualizacion: datetime`

**`HistoricoTransicionSchema`:** `id_transaccion`, `id_dispositivo_iot`, `estado_anterior`, `estado_nuevo`, `causa_primaria: str \| None`, `causa_secundaria: Any \| None`, `id_usuario_responsable: int \| None`, `notas: str \| None`, `fecha_transicion: datetime`

---

#### `GET /iot/dispositivos/{id_dispositivo_iot}/historial` — Historial completo de transiciones

**Query:** `limite: int` (1–200, default 50)

**Response:** `list[HistoricoTransicionSchema]`

---

#### `PATCH /iot/dispositivos/{id_dispositivo_iot}/mantenimiento` — Transición manual de mantenimiento (RF-60 CA-7/CA-8)

Pone el dispositivo `EN_MANTENIMIENTO` o lo devuelve a `ACTIVO` por acción manual
de un Administrador o Ingeniero de Campo. **Solo Admin e Ing** (`require_permission(35, U)`).

**Input `AplicarMantenimientoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `nuevo_estado` | `str` | 2–30 chars — enum `{EN_MANTENIMIENTO, ACTIVO}`, se normaliza a mayúsculas |
| `motivo` | `str \| None` | Opcional, máx. 500 chars |

**Response (200):** `EstadoDispositivoIoTSchema` (el estado ya actualizado).

**Errores:**

| HTTP | `code` | Cuándo |
|------|--------|--------|
| 401 | `TOKEN_*` | Sin JWT válido |
| 403 | `ACCESO_DENEGADO` | Rol distinto de Admin/Ing |
| 404 | `ESTADO_DISPOSITIVO_NO_ENCONTRADO` | No existe estado registrado para el dispositivo |
| 422 | `ESTADO_SIN_CAMBIO` | `nuevo_estado` igual al estado actual (no-op) |

> **Notas de implementación (RF-60):**
> - `causa_primaria` queda **`NULL`**: el enum PG `enum_causa_inactividad` no
>   contempla un valor de "mantenimiento". Lo *manual* se distingue por
>   `id_usuario_responsable` (no nulo) en el histórico y por el evento de
>   auditoría RF-63.
> - El histórico (`historico_transiciones_dispositivos`) lo inserta el **trigger
>   de BD** `trg_rf60_02_log_transicion_estado` al actualizar el estado — el use
>   case **no** inserta la fila (evita duplicados). Ese trigger fija
>   `notas = 'Transición automática de estado operativo'`; el `motivo` humano se
>   conserva en la bitácora RF-63 (`accion_detallada.motivo` +
>   `descripcion`), evento `TRANSICION_MANTENIMIENTO_MANUAL`.
> - El histórico es **append-only** (triggers `no_update` / `no_delete`).

---

#### `GET /iot/alertas-tecnicas` y `PATCH /iot/alertas-tecnicas/{id_alerta}/estado`

Reutilizan `ListaAlertasSchema` / `AlertaSchema` / `ActualizarEstadoAlertaDTO` —
ver sección **Alertas** arriba. Las diferencias son el recurso RBAC (`36` en vez
de `32`) y el ámbito (`AmbitoAlerta`, RF-60 D-09 — DEV-13): `/iot/alertas-tecnicas`
solo lista y gestiona alertas `tipo_alerta='TECNICA'`, y `/iot/alertas` las excluye
del listado, del detalle y del PATCH. Una alerta del otro ámbito responde
`404 ALERTA_NO_ENCONTRADA`, igual que una de otra finca.

---

### Monitoreo — `/iot/monitoreo`

> **Recursos RBAC:** `id_recurso = 33` (`monitoreo_telemetria`, dashboard) y
> `id_recurso = 34` (`historial_telemetria`, historial/exportación)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `GET` | `/dashboard` | `(33, R)` | Admin, Prod, Vet, Ing | `ObtenerDashboardUseCase` |
| `GET` | `/dashboard/{id_infraestructura}` | `(33, R)` | Admin, Prod, Vet, Ing | `ObtenerDashboardUseCase` |
| `GET` | `/historial` | `(34, R)` | Admin, Prod, Vet, Ing, Cont | `ConsultarHistorialUseCase` |
| `GET` | `/historial/exportar` | `(34, E)` | Admin, Prod, Vet, Cont (**no Ing.**) | *(stub — ver Notas)* |

#### `GET /iot/monitoreo/dashboard[/{id_infraestructura}]` — Dashboard en tiempo real (RF-58)

**Query:** `id_infraestructura: int \| None` (solo en la variante sin path param), `pagina: int (≥1, default 1)`, `por_pagina: int (1–50, default 50)`.

**Response `DashboardResponseSchema`:** `total`, `pagina`, `por_pagina`, `resumen_unidades: list[ResumenUnidadSchema]`, `sensores: list[EstadoSensorSchema]`

**`ResumenUnidadSchema`:** `id_infraestructura`, `nombre_infraestructura`, `id_finca`, `nombre_finca`, `total_sensores`, `sensores_online`, `sensores_sin_senal`, `sensores_con_error`, `estado_general`, `alertas_activas_count`, `ultimo_dato_recibido: datetime \| None`

**`EstadoSensorSchema`:** `id_sensor`, `id_dispositivo_iot`, `nombre_sensor`, `tipo_variable`, `categoria_variable`, `ultimo_valor: Decimal \| None`, `ultima_unidad`, `ultimo_timestamp_captura`, `estado_semaforo`, `estado_calidad`, `estado_desviacion`, `estado_conectividad`, `tiempo_sin_reporte_min`, `dato_desactualizado = False`, `id_alerta`, `severidad_alerta`, `tendencia`, `id_infraestructura`, `nombre_infraestructura`, `id_finca`, `nombre_finca`, `nivel_bateria_pct: Decimal \| None`, `calidad_senal_rssi/snr: Decimal \| None`

> Nota de negocio (no RBAC): para el rol Productor (`id_rol=2`),
> `ObtenerDashboardUseCase` fuerza a `None` los campos de batería y señal
> (`nivel_bateria_pct`, `calidad_senal_rssi`, `calidad_senal_snr`) — es una
> regla de negocio aplicada en el use case según `id_rol_usuario`, no un
> segundo chequeo de RBAC.

---

#### `GET /iot/monitoreo/historial` — Historial de lecturas con filtros (RF-59)

**Query:** `fecha_inicio` / `fecha_fin: date` (requeridos), `sensor_id: int`, `tipo_variable`, `categoria_variable`, `id_infraestructura: int`, `especie`, `estado_dato` (`LECTURA_VALIDA`/`FUERA_DE_RANGO`/`ERROR_CALIBRACION`), `origen_dato` (`TIEMPO_REAL`/`BUFFER_LOCAL`/`EDGE_AGREGADO`), `incluir_alertas: bool = false`, `pagina: int (default 1)`, `por_pagina: int (1–500, default 100)`, `orden: str = 'DESC'` (`ASC`/`DESC`, valida y da `400 ORDEN_INVALIDO` si no).

**Response `HistorialPageSchema`:** `total`, `pagina`, `por_pagina`, `paginas_totales`, `filtros_aplicados: dict`, `rango_real_datos: dict`, `items: list[LecturaHistoricaSchema]`, `estadisticas: list[ResumenEstadisticoSchema]`

**`LecturaHistoricaSchema`:** `id_telemetria`, `id_sensor`, `nombre_sensor`, `id_variable`, `tipo_variable`, `categoria_variable`, `valor`/`valor_ajustado: Decimal \| None`, `unidad_medida`, `timestamp_captura`, `estado_calidad`, `estado_semaforo_historico`, `origen_dato`, `id_infraestructura`/`infraestructura`/`finca` (`str \| None`), `id_activo_biologico`/`especie` (`\| None`), `id_alerta: int \| None`, `nivel_bateria_pct`/`calidad_senal_rssi`/`calidad_senal_snr` (`Decimal \| None`)

**`ResumenEstadisticoSchema`:** `tipo_variable`, `valor_minimo`/`valor_maximo`/`valor_promedio: Decimal \| None`, `total_lecturas: int`, `pct_dentro_rango`/`pct_fuera_rango: float \| None`, `total_alertas_en_periodo = 0`

---

#### `GET /iot/monitoreo/historial/exportar` — Exportar historial (RF-59) — **stub pendiente M08**

**Query:** igual que `/historial` (sin `incluir_alertas`/`orden`), `formato: str` (`PDF`/`EXCEL`) requerido.

Este endpoint **siempre responde 503**: valida que exista al menos un filtro
adicional (`FA-11`, si no → `400 EXPORTAR_SIN_FILTROS`), y si pasa la
validación, lanza incondicionalmente `ServiceUnavailableError
M08_NO_DISPONIBLE` — la exportación real depende del módulo M08 (aún no
implementado). No hay `response_model` (retorno `None`).

---

### Vinculaciones — `/iot/vinculaciones`

> **Recurso RBAC:** `id_recurso = 37` (`vinculaciones_lecturas`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `GET` | `/` | `(37, R)` | Admin, Prod, Vet, Ing | `ListarVinculacionesUseCase` |
| `GET` | `/{id_vinculacion_lectura}` | `(37, R)` | Admin, Prod, Vet, Ing | *(sin use case — repositorio directo)* |
| `PATCH` | `/{id}/resolver` | `(37, U)` | **Solo Admin, Ing** | `ResolverVinculacionUseCase` |
| `POST` | `/{id}/corregir` | `(37, U)` | **Solo Admin, Ing** | `CorregirVinculacionUseCase` |

> Nota RBAC: igual que en Alertas Técnicas, la acción `U` sobre este recurso
> solo está asignada a Admin e Ingeniero — Productor y Veterinario pueden
> **leer** vinculaciones pero no resolverlas/corregirlas.

#### `GET /iot/vinculaciones` — Listar vinculaciones

**Query:** `id_telemetria: int`, `estado_vinculacion`, `mecanismo_vinculacion`, `id_infraestructura: int`, `fecha_desde`/`fecha_hasta: datetime`, `pagina: int (default 1)`, `por_pagina: int (1–200, default 50)` — todos opcionales salvo paginación.

**Response `ListaVinculacionesSchema`:** `total`, `pagina`, `por_pagina`, `items: list[VinculacionLecturaSchema]`

**`VinculacionLecturaSchema`:** `id_vinculacion_lectura`, `id_telemetria`, `modelo_manejo`, `id_activo_biologico: int \| None`, `id_infraestructura`, `fecha_inicio_vinculacion`, `fecha_fin_vinculacion: datetime \| None`, `mecanismo_vinculacion`, `estado_vinculacion`, `id_usuario: int \| None`, `motivo_correccion: str \| None`, `id_vinculacion_reemplazada: int \| None`, `fecha_creacion`

---

#### `PATCH /iot/vinculaciones/{id}/resolver` — Resolver vinculación ambigua (RF-61-C)

**Input `ResolverVinculacionDTO`:** `id_activo_biologico: int`, `modelo_manejo: str` (sin restricciones de formato a nivel de DTO)

**Response:** `VinculacionLecturaSchema`

---

#### `POST /iot/vinculaciones/{id}/corregir` — Corregir vinculación existente (RF-61-C)

**Input `CorregirVinculacionDTO`:** `id_activo_biologico: int`, `modelo_manejo: str`, `motivo: str` (5–500 chars)

**Response:** `VinculacionLecturaSchema`

---

### Calidad de telemetría — `/iot/calidad`

> **Recurso RBAC:** `id_recurso = 38` (`calidad_telemetria`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `GET` | `/` | `(38, R)` | Admin, Prod, Vet, Ing, Cont | `ConsultarCalidadUseCase.listar` |
| `GET` | `/{id_telemetria}` | `(38, R)` | Admin, Prod, Vet, Ing, Cont | `ConsultarCalidadUseCase.get` |
| `POST` | `/{id_telemetria}/evaluar` | `(38, E)` | **Solo Admin, Ing** | `EvaluarCalidadTelemetriaUseCase` |
| `POST` | `/reevaluar` | `(38, E)` | **Solo Admin, Ing** | `SolicitarReevaluacionUseCase` |

#### `GET /iot/calidad` — Listar evaluaciones de calidad (RF-62)

DEV-02: por defecto devuelve una evaluación vigente no superada por lectura,
fuente oficial de `apto_para_ia` y `apto_para_nic41` escalares. El estado
`SUPERADA` explícito permite consultar el histórico. Las columnas de aptitud
de `modulo3.telemetrias` están obsoletas y no deben consumirse.

**Query:** `id_sensor: int`, `clasificacion`, `fecha_desde`/`fecha_hasta: datetime`, `estado_evaluacion`, `pagina: int (default 1)`, `por_pagina: int (1–200, default 50)`.

**Response `ListaCalidadSchema`:** `total`, `pagina`, `por_pagina`, `items: list[TelemetriaCalidadSchema]`

**`TelemetriaCalidadSchema`:** `id_evaluacion: UUID`, `id_telemetria`, `id_sensor`, `timestamp_evaluacion`, `indice_calidad: int \| None`, `clasificacion_calidad`, `apto_para_ia: bool`, `apto_para_nic41: bool`, `flags_detectados: dict`, `version_limites_fisicos_aplicada: str \| None`, `parametros_aplicados: dict`, `parametros_calibracion_aplicados: dict \| None`, `estado_evaluacion`, `motivo_reevaluacion: str \| None`, `id_evaluacion_superada: UUID \| None`, `version_evaluacion: int \| None`, `fecha_creacion: datetime \| None`

---

#### `POST /iot/calidad/{id_telemetria}/evaluar` — Evaluar calidad de una lectura puntual

> Nota de implementación: el router ejecuta un `SELECT` SQL crudo contra
> `modulo3.telemetrias` para obtener la fila antes de invocar el use case —
> se lista como hallazgo en Notas adicionales, no afecta el contrato RBAC.

**Response:** `TelemetriaCalidadSchema`

---

#### `POST /iot/calidad/reevaluar` — Solicitar reevaluación masiva (RF-62 FA-08)

**Input `SolicitarReevaluacionDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `id_sensor` | `int` | `> 0` |
| `fecha_desde` / `fecha_hasta` | `datetime` | — |
| `causa_documentada` | `str` | 10–1000 chars |
| `parametros_correctos` | `dict \| None` | Opcional |

**Response `ReevaluacionResponseSchema`:** `evaluaciones_superadas: int`, `evaluaciones_creadas: int`

> ✅ **Bug corregido (2026-07-27).** Antes el router llamaba a
> `...execute(..., nombre_usuario=usuario_actual.email)`, pero `UsuarioActual`
> no tiene atributo `email` → `AttributeError` → 500 en cada llamada. Ahora el
> router resuelve el nombre real desde el módulo de identidad
> (`SqlAlchemyUsuarioRepository(db).obtener_detalle(id_usuario)` →
> `f"{nombre} {apellidos}"`) y lo pasa como `nombre_usuario` (fallback al
> `id_usuario` si no hay detalle). El use case `SolicitarReevaluacionUseCase` no
> cambió de firma.

---

### Auditoría IoT — `/iot/auditoria`

> **Recurso RBAC:** `id_recurso = 39` (`bitacora_auditoria_iot`)

| Método | Ruta | Permiso | Roles autorizados | Use Case |
|--------|------|---------|--------------------|----------|
| `GET` | `/` | `(39, R)` | Admin, Ing, Cont | `ConsultarBitacoraIotUseCase.listar` |
| `GET` | `/exportar` | `(39, E)` | **Solo Admin, Cont** | `ConsultarBitacoraIotUseCase.listar` (reutilizado) |
| `GET` | `/{id_evento}` | `(39, R)` | Admin, Ing, Cont | `ConsultarBitacoraIotUseCase.get` |
| `POST` | `/verificar-integridad` | `(39, E)` | **Solo Admin, Cont** | `VerificarIntegridadBitacoraUseCase` |

> Nota RBAC: Productor y Veterinario no tienen ningún permiso sobre este
> recurso (403 en los 4 endpoints). Ingeniero de Campo puede leer (`R`) pero
> no tiene `E` — no puede exportar ni verificar integridad, solo Admin y
> Contador pueden.

#### `GET /iot/auditoria` — Listar eventos de auditoría (RF-63)

**Query:** `fecha_desde`/`fecha_hasta: datetime`, `tipo_evento`, `severidad_log`, `clasificacion_registro`, `entidad_afectada_id`, `resultado`, `pagina: int (default 1)`, `por_pagina: int (1–200, default 50)`.

**Response `ListaAuditoriaIotSchema`:** `total`, `pagina`, `por_pagina`, `items: list[EventoAuditoriaIotSchema]`

**`EventoAuditoriaIotSchema`:** `id_evento: UUID`, `id_usuario: int \| None`, `nombre_usuario: str \| None`, `tipo_evento`, `modulo`, `descripcion: str \| None`, `resultado`, `direccion_ip: str \| None`, `user_agent: str \| None`, `id_sesion: UUID \| None`, `fecha_hora`, `accion_detallada: dict \| None`, `entidad_afectada_tipo`/`entidad_afectada_id` (`\| None`), `severidad_log`, `hash_integridad`, `clasificacion_registro`, `retencion_aplicable: int`, `registro_incompleto: bool`, `timestamp_registro: datetime \| None`

> `componente_origen` es un campo interno de la entidad `EventoAuditoriaIot`
> que se excluye deliberadamente del schema de respuesta.

---

#### `GET /iot/auditoria/exportar` — Exportar bitácora (CSV/JSON)

**Query:** igual que `/`, más `formato: str = 'json'` (patrón `^(json|csv)$`).

**Response:** `StreamingResponse` (sin `response_model` — CSV o JSON según `formato`).

---

#### `GET /iot/auditoria/{id_evento}` — Detalle de un evento

**Path:** `id_evento: UUID`

**Response:** `EventoAuditoriaIotSchema`

---

#### `POST /iot/auditoria/verificar-integridad` — Verificar integridad SHA-256 (RF-63 FA-11)

**Query:** `fecha_desde`/`fecha_hasta: datetime` (opcionales — si se omiten, verifica todo el rango disponible).

**Response `VerificacionIntegridadSchema`:** `total_verificados: int`, `comprometidos: int`, `ids_comprometidos: list[str]`

---

## Tabla de permisos RBAC usados

> Datos extraídos de `modulo1.permisos` (vía MCP postgres, DB `sgpmp`).
> Acciones: `C`=1 Crear, `R`=2 Leer, `U`=3 Actualizar, `D`=4 Eliminar, `E`=5 Ejecutar.

| `id_recurso` | Recurso | Admin | Productor | Veterinario | Ing. Campo | Contador |
|---|---|---|---|---|---|---|
| 32 | `alertas_operativas` | R,U | R,U | R,U | R | — |
| 33 | `monitoreo_telemetria` | R | R | R | R | — |
| 34 | `historial_telemetria` | R,E | R,E | R,E | R | R,E |
| 35 | `infraestructura_iot` | R,U | R | R | R,U | — |
| 36 | `alertas_tecnicas_iot` | R,U | — | — | R,U | — |
| 37 | `vinculaciones_lecturas` | R,U | R | R | R,U | — |
| 38 | `calidad_telemetria` | R,E | R | R | R,E | R |
| 39 | `bitacora_auditoria_iot` | R,E | — | — | R | R,E |

Ningún recurso de este módulo tiene permisos `C` (Crear) ni `D`
(Eliminar/Desactivar) asignados a ningún rol — coherente con que los
registros de telemetría/alertas/vinculaciones/auditoría se generan
automáticamente desde la ingesta de dispositivos, no por creación manual de
un usuario.

---

## Use Cases — resumen de firmas

| Clase | Método(s) — parámetros principales |
|-------|--------------------------------------|
| `IngerirTelemetriaUseCase` | `execute(dto: IngerirTelemetriaDTO, gateway_id: str \| None = None) → ResultadoIngesta` |
| `SincronizarBufferUseCase` | `execute(dto: IngerirTelemetriaBatchDTO, gateway_id: str \| None = None) → dict` (`total, aceptados, rechazados, duplicados, detalle`) |
| `GenararAlertaUseCase` | `execute(dto: ProcesarEventoAlertaDTO, id_activo_biologico=None, contexto_activo_biologico=None, id_dispositivo_ioit=None, id_infraestructura=None) → ResultadoGeneracionAlerta` |
| `ConsultarAlertasUseCase` | `listar(estado=None, severidad=None, tipo_alerta=None, id_sensor=None, id_activo_biologico=None, origen_evento=None, fecha_desde=None, fecha_hasta=None, pagina=1, por_pagina=50) → tuple[list[Alerta], int]`; `obtener_detalle(id_alerta: int) → tuple[Alerta, list[HistoricoEstadoAlerta]]` |
| `ActualizarEstadoAlertaUseCase` | `execute(id_alerta: int, dto: ActualizarEstadoAlertaDTO, id_usuario: int) → Alerta` |
| `RecibirEventoEdgeUseCase` | `execute(dto: RecibirEventoEdgeDTO, gateway_id: str \| None = None) → ResultadoEventoEdge` |
| `ConsolidarEnviarPaqueteUseCase` | `execute(evento: EventoEdgeComputing) → PaqueteInferencia \| None` — uso interno, llamado por `RecibirEventoEdgeUseCase`, no expuesto por un router |
| `RecibirHeartbeatUseCase` | `execute(dto: HeartbeatDTO) → Heartbeat` |
| `ObtenerEstadoDispositivoUseCase` | `execute(id_dispositivo_iot: int, limite_historial: int = 20) → ResultadoEstadoDispositivo` |
| `EvaluarEstadoDispositivosUseCase` | `execute() → int` — job periódico (máquina de estados de dispositivos), no invocado por ningún router |
| `AplicarMantenimientoDispositivoUseCase` | `execute(id_dispositivo_iot: int, dto: AplicarMantenimientoDTO, id_usuario: int, nombre_usuario: str) → EstadoDispositivoIoT` — transición manual `EN_MANTENIMIENTO ↔ ACTIVO` (RF-60 CA-7/CA-8); el histórico lo escribe el trigger de BD, el use case emite auditoría RF-63 |
| `ListarVinculacionesUseCase` | `execute(id_telemetria=None, estado_vinculacion=None, mecanismo_vinculacion=None, id_infraestructura=None, fecha_desde=None, fecha_hasta=None, pagina=1, por_pagina=50) → tuple[list[VinculacionLectura], int]` |
| `ResolverVinculacionUseCase` | `execute(id_vinculacion_lectura: int, dto: ResolverVinculacionDTO, id_usuario: int) → VinculacionLectura` |
| `CorregirVinculacionUseCase` | `execute(id_vinculacion_lectura: int, dto: CorregirVinculacionDTO, id_usuario: int) → VinculacionLectura` |
| `VincularLecturaActivoUseCase` | `execute(id_telemetria: int, id_infraestructura: int, timestamp_captura: datetime) → VinculacionLectura` — uso interno, llamado desde `IngerirTelemetriaUseCase` (auto-vinculación RF-61-A) |
| `ConsultarCalidadUseCase` | `get(id_telemetria: int) → TelemetriaCalidad`; `listar(id_sensor=None, clasificacion=None, fecha_desde=None, fecha_hasta=None, estado_evaluacion=None, pagina=1, por_pagina=50) → tuple[list[TelemetriaCalidad], int]` |
| `EvaluarCalidadTelemetriaUseCase` | `execute(id_telemetria: int, id_sensor: int, id_variable: int, valor: Decimal, valor_ajustado: Decimal \| None, timestamp_captura: datetime, estado_calidad_rf53: str, parametros_calibracion: dict \| None, tipo_variable: str \| None = None) → TelemetriaCalidad` |
| `SolicitarReevaluacionUseCase` | `execute(dto: SolicitarReevaluacionDTO, id_usuario: int, nombre_usuario: str) → ResultadoReevaluacion` (`evaluaciones_superadas`, `evaluaciones_creadas`) |
| `ConsultarBitacoraIotUseCase` | `get(id_evento: UUID) → EventoAuditoriaIot`; `listar(fecha_desde=None, fecha_hasta=None, tipo_evento=None, severidad_log=None, clasificacion_registro=None, entidad_afectada_id=None, resultado=None, pagina=1, por_pagina=50) → tuple[list[EventoAuditoriaIot], int]` |
| `RegistrarEventoAuditoriaIotUseCase` | `execute(tipo_evento, resultado, componente_origen, severidad_log=INFO, descripcion=None, entidad_afectada_tipo=None, entidad_afectada_id=None, accion_detallada=None, id_usuario=None, nombre_usuario=None, id_sesion=None, direccion_ip=None, registro_incompleto=False) → None` — uso interno (auditoría best-effort desde otros use cases), no expuesto por un router |
| `VerificarIntegridadBitacoraUseCase` | `execute(fecha_desde: datetime \| None = None, fecha_hasta: datetime \| None = None) → ResultadoVerificacion` |
| `ObtenerDashboardUseCase` | `execute(id_infraestructura: int \| None, pagina: int, por_pagina: int, id_rol_usuario: int) → tuple[list[EstadoSensorActual], list[ResumenUnidadProductiva], int]` |
| `ConsultarHistorialUseCase` | `execute(filtros: FiltrosHistorial) → tuple[list[LecturaHistorica], list[ResumenEstadistico], int, dict]` |

---

## Notas adicionales

- **`GET /iot/monitoreo/historial/exportar` es un stub permanente**: siempre
  responde `503 M08_NO_DISPONIBLE` tras pasar la validación de filtros — la
  exportación real depende del módulo M08, aún no implementado.
- **Dos endpoints saltan la capa de use case**: `GET
  /iot/dispositivos/{id}/historial` y `GET /iot/vinculaciones/{id}` llaman al
  repositorio SQLAlchemy directamente desde el router. Es una inconsistencia
  con el resto del módulo (que sí pasa por use cases), no afecta el
  comportamiento de RBAC.
- **`POST /iot/calidad/{id_telemetria}/evaluar`** ejecuta un `SELECT` SQL
  parametrizado directamente en el router antes de invocar el use case.
- **Bug corregido (2026-07-27)**: `POST /iot/calidad/reevaluar` ya no usa
  `usuario_actual.email` (inexistente en `UsuarioActual`); el router resuelve el
  nombre real vía `SqlAlchemyUsuarioRepository.obtener_detalle`. Ver detalle en
  la sección de Calidad.
- **Adaptadores stub que afectan el comportamiento observable** (no son
  errores, son dependencias cruzadas pendientes de otros módulos):
  - `ActivoBiologicoStubAdapter` (M02) — siempre retorna `[]`, por lo que el
    auto-vinculado RF-61-A siempre resuelve `SIN_VINCULAR`.
  - `UmbralHistoricoM09Adapter` — siempre retorna `None`, el semáforo
    histórico de RF-59 queda en `GRIS` por defecto.
  - `MotorInferenciaStubAdapter` (M04) — señala `MotorInferenciaNoIntegradoError`;
    RF-56 conserva el paquete persistido en `PENDIENTE`, con cero intentos.
  - `ParametrosCalidadStubAdapter` (M09) — parámetros de evaluación de
    calidad fijos (`k=3.0, M=5, N=20, umbral_drift=5.0, ...`).
- Para probar cualquier endpoint "JWT + RBAC" de este documento: `POST
  /sesiones/` primero, y reutilizar el `Authorization: Bearer <jwt>` dentro de
  los 30 minutos de inactividad permitidos (ver sección "Cómo funciona el
  RBAC" arriba).
