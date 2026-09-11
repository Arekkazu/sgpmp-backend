# API Reference — `src/supplies/`

> Generado el 2026-08-02. Solo documentación — no subir al repositorio.
>
> **Todos los endpoints de este módulo requieren sesión activa** (`Authorization: Bearer <token>`). A diferencia de `src/prediction/` (M04), **no existe ninguna excepción de autenticación por clave interna** en `src/supplies/`: los 42 endpoints usan exclusivamente `require_permission(id_recurso, id_accion)` de `src/shared/rbac.py`.

---

## Sesión y RBAC — cómo funciona en este módulo

Este módulo reutiliza exactamente el mismo mecanismo que el resto del backend: `get_current_user` (`src/identity_access/infrastructure/dependencies.py`) y `require_permission` (`src/shared/rbac.py`).

### 1. Toda ruta con `require_permission(...)` exige sesión, aunque el handler no reciba `usuario_actual`

Igual que en M04: `require_permission(id_recurso, id_accion)` depende internamente de `get_current_user`, así que **todos** los endpoints exigen un Bearer token válido, incluso los que no declaran `usuario_actual: UsuarioActual = Depends(get_current_user)` en su firma porque no lo necesitan para su lógica (típicamente los `GET` de consulta simple y los 3 endpoints por router de los 4 paneles batch: `ejecutar`, `cola`, `fallos`). FastAPI cachea la dependencia por request, así que declarar `usuario_actual` explícitamente en el mismo endpoint no vuelve a verificar el token.

**En la práctica: no existe ningún endpoint público en `src/supplies/`.**

### 2. Qué valida `get_current_user`

- Requiere `Authorization: Bearer <token>` → si falta, `401 TOKEN_REQUERIDO`.
- Decodifica el JWT: `sub` → `id_usuario`, `jti` → `id_token`, `rol` → `id_rol`.
- Verifica que el token no esté en la "blacklist" (`Tokens.fecha_uso IS NULL`) → `401 TOKEN_REVOCADO` si ya fue usado/revocado.
- Verifica inactividad de 30 minutos contra `CuentasUsuarios.ultimo_acceso`: si se superó, cierra la sesión activa y responde `401 SESION_EXPIRADA_INACTIVIDAD`.
- Si es válido, actualiza `ultimo_acceso` y retorna `UsuarioActual(id_usuario, id_token, id_rol)`.

### 3. Qué valida `require_permission`

Con el `id_rol` resuelto, consulta `modulo1.permisos` filtrando por `(id_rol, id_recurso, id_accion, es_activo=true)`. Sin fila activa → `403 ACCESO_DENEGADO`. El use case **nunca** verifica roles — solo usa `usuario_actual.id_usuario` (y a veces `id_rol`, p. ej. para el alcance del Gestor de Granja en RF-81) para auditoría o filtros de negocio, nunca para decidir acceso.

### 4. Sin excepción de autenticación interna

Verificado (`grep -rn "Internal-Key" src/supplies/` sin resultados): a diferencia de `POST /prediccion/modelos` en M04, **ningún** endpoint de este módulo se salta RBAC con una cabecera de sistema. Todos pasan por sesión de usuario.

### 5. Adaptadores de dependencias cruzadas — todos reales, sin stubs

A diferencia de M04 (que documenta 3 adaptadores stub con valores "seguros por defecto"), en `src/supplies/infrastructure/adapters/` **todos** los adaptadores (`ActivoM02Adapter`, `CicloM02Adapter`, `AlcanceActivoM02Adapter`, `EstadoActivoM02Adapter`, `EventoSanitarioM02Adapter`, `PesajeM02Adapter`, `AlertaICAM03Adapter`, `ActivosBatchM02Adapter`, `NotificacionMedicamentoEmailAdapter`) son implementaciones reales que consultan `modulo2`/`modulo3` de verdad — no hay ningún valor hardcodeado esperando a que otro módulo se implemente.

La única pieza documentada como "interina" es el filtro de alcance por rol en `AlcanceActivoM02Adapter`, usado en el historial (RF-81): el rol **Gestor de Granja** (`id_rol=7`) solo puede ver activos que **él mismo registró** (`modulo2.activos_biologicos.id_usuario`); el resto de roles con permiso ven todo. Fuera de ese alcance → `403 ACCESO_DENEGADO`. Esto no es un stub sino una regla real contra la BD — la limitación es que **no existe todavía un modelo de "unidad productiva asignada a un usuario"** en ningún schema, así que la regla usa el campo de registro como sustituto hasta que ese modelo exista.

### 6. Roles del sistema en este módulo

Además de los 5 roles estándar (Admin, Productor, Veterinario, Ingeniero de Campo, Contador), este módulo introduce dos roles nuevos creados específicamente para RF-81:

| id_rol | Rol | Notas |
|--------|-----|-------|
| 7 | Gestor de Granja | Solo ve/opera sobre activos que él mismo registró (ver punto 5) |
| 8 | Revisor Fiscal | Acceso de solo lectura, orientado a auditoría/costos NIC-41 |

**Ingeniero de Campo y Supervisor no tienen ningún permiso activo en ninguno de los 11 recursos de este módulo** — a diferencia de M04, donde Ing. Campo sí tenía acceso a OTA y motor-ia.

---

## Notas de negocio transversales para el equipo de frontend

Antes de entrar a los endpoints, algunos conceptos y patrones que se repiten en varios CUs y que no son evidentes solo mirando los schemas:

### ¿Qué es ICA?

**Índice de Conversión Alimenticia** (RF-74): mide cuántos kg de alimento se necesitan por kg de peso ganado. Cuanto más bajo, más eficiente (`<2.0` EXCELENTE, `2.0–3.5` ACEPTABLE, `3.5–5.0` BAJA, `>5.0` CRÍTICA). Es 100% calculado por el backend — el frontend nunca debe tratar `ca_calculado`, `clasificacion_ca` ni `data_quality_score` como editables; no existen como campos de entrada en ningún DTO.

### ¿Qué es NIC-41?

**Norma Internacional de Contabilidad 41** (Agricultura, RF-79): exige valorar activos biológicos a su costo. Este módulo acumula los costos directos (ALIMENTO, MEDICAMENTO, SERVICIO_VETERINARIO, INSEMINACION) por instancia de ciclo productivo y genera "provisiones" — snapshots versionados, inmutables, con hash de integridad — que el futuro Módulo 6 (contabilidad, aún no implementado) usará para valoración contable. `hash_integridad`, `monto_provision` y `desglose_categoria` son siempre de solo lectura.

### `id_gestion_fases` vs `id_ciclo_productivo` — la distinción más importante en CU-05

- `id_ciclo_productivo` (`modulo9.ciclos_productivos`) es un **catálogo/plantilla reutilizable** (ej. "Ciclo de engorde 90 días") que puede estar activo simultáneamente para varios activos distintos.
- `id_gestion_fases` (`modulo2.gestiones_fases`) es la **instancia real** de ese ciclo para **un activo biológico específico** en un momento dado (con su propia `fecha_inicio`/`fecha_finalizacion`/`es_activa`).

**Toda la acumulación de costos, el acumulado (`AcumuladoCiclo`) y la provisión NIC-41 usan `id_gestion_fases` como clave — nunca `id_ciclo_productivo`.** Si el frontend necesita el acumulado del ciclo abierto de un activo, debe usar `GET /suministros/costeo-directo/acumulado/activo/{id_activo}` (resuelve la fase activa internamente); si ya conoce el `id_gestion_fases` (p. ej. tras el cierre del ciclo, cuando ya no hay fase activa), debe usar `GET .../acumulado/ciclo/{id_gestion_fases}`.

### Campos que el frontend nunca debe enviar ni tratar como editables

Calculados por triggers de PostgreSQL o servicios de dominio puros, nunca por input del cliente:

| Campo | Quién lo calcula |
|---|---|
| `costo_total` (consumo alimento) | Trigger BD, desde el catálogo `tipos_alimentos` |
| `costo_total_medicamento` | Trigger BD (`cantidad × costo_unitario_medicamento`) |
| `costo_registro` (costeo directo) | Calculado en Python en el use case (`cantidad × precio_unitario_resuelto`) — única entidad sin trigger |
| `acumulado_total_ciclo` / `acumulado_por_categoria` / `version_acumulado` | Trigger BD `trg_acumular_costo_ciclo` |
| `hash_integridad` (auditoría y provisión NIC-41) | Trigger BD (`pgcrypto.digest()`) |
| `ca_calculado` / `clasificacion_ca` / `data_quality_score` / `causa_no_calculo` | Servicio de dominio `CalculadoraICA` |
| `consumo_por_individuo_kg` / `dosis_por_individuo` | Use case, a partir de `cantidad_actual` del activo (M02), solo si es POBLACIONAL |
| `fecha_fin_retiro` | Use case (`fecha_aplicacion + periodo_retiro_dias`) |

### Patrón de idempotencia (Costeo Directo, RF-78)

`POST /suministros/costeo-directo` y su corrección exigen `id_idempotencia` (UUID) obligatorio. Si el cliente reenvía la misma request con el mismo `id_idempotencia` (ej. tras un timeout de red), el backend **no crea un registro duplicado**: devuelve el registro ya existente con `ya_procesado=true` y **status 200 en vez de 201**. Distinto de un reenvío con contenido idéntico pero `id_idempotencia` nuevo, que sí es rechazado como duplicado (`409 SUMINISTRO_DUPLICADO`).

### Patrón síncrono/asíncrono por volumen

Dos flujos deciden en el propio backend si procesar la petición al vuelo o encolarla:

- **Reporte de gastos (RF-77):** por activo puntual, asíncrono si el rango supera **366 días**; agregado (por infraestructura/especie), asíncrono si supera **183 días**. `POST /suministros/reportes-gastos/` responde **200** con `ReporteGastoResponse` en el caso síncrono, o **202** con `TrabajoReporteResponse` en el asíncrono — el frontend debe inspeccionar el status code, no un campo del body, para saber cuál llegó.
- **Historial (RF-81):** volumen `NIVEL_1` (≤10.000 registros por defecto) es síncrono; `NIVEL_3`/`NIVEL_4` (>10.000, o >50.000) **obligan** modo asíncrono — el endpoint síncrono lo rechaza con `422 CONSULTA_REQUIERE_MODO_ASINCRONO` (o `422 EXPORTACION_REQUIERE_MODO_ASINCRONO` en `/exportar`), y hay que usar `POST /suministros/historial/trabajos` en su lugar.

Ambos comparten el mismo ciclo de vida de trabajo: `PENDIENTE → EN_PROCESO → COMPLETADO | FALLIDO`, consultable por polling en `GET .../trabajos/{id_cola}`.

### `estado_registro` es unidireccional

`VALIDADO` → `ANULADO` es la única transición posible (consumo de alimento y medicamentos). No hay reactivación. Anular exige `justificacion_anulacion` de **20 a 255 caracteres**; intentar anular un registro ya `ANULADO` responde `409`.

### `origen_precio` siempre `MANUAL`

No existe integración M40 (pricing automático) en el sistema actual — `origen_precio` es siempre `"MANUAL"` en todo el módulo. Por eso `justificacion_precio` (20–500 caracteres) es **siempre obligatoria** al registrar costeo directo, y el filtro `origen_precio_filtro=M40_AUTOMATICO` del historial simplemente nunca devuelve resultados hoy.

---

## Prefijos de rutas

Los 11 routers, en el orden real de registro en `main.py` (imports líneas 48-60, `include_router` líneas 336-346):

| Router | Prefijo | Tag Swagger | Recurso RBAC |
|--------|---------|-------------|--------------|
| `consumo_alimento_router.py` | `/suministros/consumo-alimentos` | Suministros - Consumo de alimentos | 47 |
| `medicamento_router.py` | `/suministros/medicamentos` | Suministros - Medicamentos | 48 |
| `eficiencia_alimenticia_router.py` | `/suministros/eficiencia-alimenticia` | Suministros - Eficiencia Alimenticia (ICA) | 49 |
| `batch_ica_router.py` | `/suministros/eficiencia-alimenticia/batch` | Suministros - Batch ICA (RF-74) | 50 |
| `reporte_gastos_router.py` | `/suministros/reportes-gastos` | Suministros - Reporte de Gastos (RF-77) | 51 |
| `batch_reportes_gastos_router.py` | `/suministros/reportes-gastos/batch` | Suministros - Batch Reportes de Gastos (RF-77) | 53 |
| `historial_suministros_router.py` | `/suministros/historial` | Suministros - Historial de Suministros (RF-81) | 52 |
| `batch_historial_suministros_router.py` | `/suministros/historial/batch` | Suministros - Batch Historial de Suministros (RF-81) | 54 |
| `costeo_suministros_router.py` | `/suministros/costeo-directo` | Suministros - Costeo Directo (RF-78) | 55 |
| `provision_nic41_router.py` | `/suministros/nic41` | Suministros - Provisión NIC-41 (RF-79) | 56 |
| `auditoria_suministros_router.py` | `/suministros/auditoria` | Suministros - Auditoría del Módulo (RF-80) | 57 |

**Schedulers automáticos** (arrancados en `main.py` al startup, sin endpoint propio): `_ejecutar_batch_ica_diario` (03:00), `_revertir_retiros_vencidos_diariamente`, `_procesar_cola_reportes_gastos_periodicamente`, `_procesar_cola_historial_suministros_periodicamente`. Los 4 routers de "batch"/"trabajos" existen como **disparo manual y monitoreo** de estos mismos procesos — no son la única forma en que corren, son el panel de administración sobre ellos.

---

## Endpoints

### Consumo de Alimento — `/suministros/consumo-alimentos` (RF-75, CU-01)

> **Recurso RBAC:** `id_recurso = 47`

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case |
|--------|------|---------|--------------------|--------------------|----------|
| `POST` | `/` | `(47, C)` | Admin, Productor, Vet | Sí | `RegistrarConsumoAlimentoUseCase` |
| `POST` | `/{id_consumo}/anulacion` | `(47, D)` | Admin, Vet | Sí | `AnularConsumoAlimentoUseCase` |
| `GET` | `/` | `(47, R)` | Admin, Productor, Vet | No | `ConsultarConsumosUseCase` |

#### `POST /suministros/consumo-alimentos/` — Registrar consumo

**Input `RegistrarConsumoAlimentoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `id_activo_biologico` | `int` | `gt=0` |
| `id_tipo_alimento` | `int` | `gt=0` — id del catálogo `modulo5.tipos_alimentos` |
| `fecha_consumo` | `date` | requerido |
| `hora_suministro` | `time \| None` | opcional |
| `cantidad_alimento` | `Decimal` | `gt=0`, kg totales |
| `observaciones` | `str \| None` | máx. 60 caracteres |

**No se envía `costo_unitario`** — el trigger BD calcula `costo_total` desde el catálogo.

**Response `ConsumoAlimentoResponse`** (201):

| Campo | Tipo |
|-------|------|
| `id_consumo_alimeto` | `int` |
| `id_activo_biologico` | `int` |
| `id_tipo_alimento` | `int` |
| `tipo_alimento` | `str` |
| `tipo_unidad` | `str` |
| `cantidad_suministrada` | `Decimal` |
| `costo_unitario` | `Decimal \| None` |
| `costo_total` | `Decimal \| None` |
| `consumo_por_individuo_kg` | `Decimal \| None` |
| `observacion` | `str \| None` |
| `fecha_consumo` | `date \| None` |
| `hora_suministro` | `time \| None` |
| `estado_registro` | `str` |
| `id_usuario` | `int \| None` |
| `fecha_registro` | `datetime \| None` |
| `justificacion_anulacion` | `str \| None` |
| `fecha_hora_anulacion` | `datetime \| None` |

**Reglas adicionales:** activo debe existir (`404 ACTIVO_NO_ENCONTRADO`) y estar `ACTIVO` (`422 ACTIVO_ESTADO_INVALIDO`); debe existir ciclo productivo abierto (`422 CICLO_NO_ABIERTO`); `id_tipo_alimento` debe existir y estar activo (`422 TIPO_ALIMENTO_NO_ENCONTRADO`/`TIPO_ALIMENTO_INACTIVO`); `fecha_consumo` no futura (`400 FECHA_FUTURA`) ni anterior al inicio de la fase activa (`400 FECHA_ANTERIOR_A_FASE`); activo `POBLACIONAL` exige `cantidad_actual > 0` (`422 POBLACIONAL_SIN_CANTIDAD`) y calcula `consumo_por_individuo_kg`; duplicado exacto (activo+fecha+hora+tipo) entre `VALIDADO` → `409 CONSUMO_DUPLICADO`.

---

#### `POST /suministros/consumo-alimentos/{id_consumo}/anulacion` — Anular

**Input `AnularRegistroDTO`:** `justificacion_anulacion: str` (20–255 caracteres tras `strip()`, validado por VO `JustificacionAnulacion` → `400 JUSTIFICACION_INSUFICIENTE`/`JUSTIFICACION_MUY_LARGA`).

Solo válido sobre `estado_registro=VALIDADO`; ya `ANULADO` → `409 CONSUMO_YA_ANULADO`. Transición irreversible.

**Response:** `ConsumoAlimentoResponse` (200).

---

#### `GET /suministros/consumo-alimentos/` — Listar

**Query params:** `id_activo_biologico`, `fecha_desde`, `fecha_hasta`, `tipo_alimento`, `estado_registro` (`VALIDADO`\|`ANULADO`) — todos opcionales, sin paginación.

**Response `ConsultaConsumosResponse`:** `{ total: int, items: list[ConsumoAlimentoResponse] }`.

---

### Medicamentos — `/suministros/medicamentos` (RF-76, CU-01)

> **Recurso RBAC:** `id_recurso = 48`. Registro (C) y anulación (D) restringidos a Admin y Veterinario — Productor solo tiene lectura.

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case |
|--------|------|---------|--------------------|--------------------|----------|
| `POST` | `/` | `(48, C)` | Admin, Vet | Sí | `RegistrarMedicamentoUseCase` |
| `POST` | `/{id_medicamento}/anulacion` | `(48, D)` | Admin, Vet | Sí | `AnularMedicamentoUseCase` |
| `GET` | `/` | `(48, R)` | Admin, Productor, Vet | No | `ConsultarMedicamentosUseCase` |

#### `POST /suministros/medicamentos/` — Registrar aplicación

**Input `RegistrarMedicamentoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `id_activo_biologico` | `int` | `gt=0` |
| `nombre_medicamento` | `str` | 1–100 caracteres |
| `fecha_aplicacion` | `date` | requerido |
| `hora_aplicacion` | `time` | requerido |
| `via_administracion` | `str` | 1–20; validado en el use case contra VO `ViaAplicacion`: `ORAL`, `INTRAMUSCULAR`/`IM`, `INTRAVENOSA`/`IV`, `SUBCUTANEA`/`SC`, `TOPICA`, `INTRAMAMARIA` |
| `dosis_aplicada` | `Decimal` | `gt=0` |
| `unidad_dosis` | `str` | 1–20 |
| `periodo_retiro_dias` | `int` | default `0`, `ge=0` |
| `motivo_aplicacion` | `str` | 10–500 caracteres tras `strip()` |
| `costo_unitario` | `Decimal` | `gt=0` — **aquí sí se recibe manual** (a diferencia de consumo de alimento) |
| `nombre_veterinario` | `str` | 1–150 |
| `id_evento_sanitario` | `int \| None` | `gt=0`; debe pertenecer al mismo activo si se envía |
| `lote` | `str \| None` | máx. 60 |
| `fecha_vencimiento_lote` | `date \| None` | opcional |

**Response `RegistroMedicamentoResponse`** (201):

```
{ medicamento: MedicamentoResponse, fecha_fin_retiro_vigente: date | None, mensaje: str }
```

**`MedicamentoResponse`:** `id_registro_medicamento, id_activo_biologico, nombre_medicamento, via_aplicacion, unidad_dosis, cantidad, dosis_por_individuo, fecha_aplicacion, hora_aplicacion, periodo_retiro_dias, fecha_fin_retiro, costo_unitario_medicamento, costo_total_medicamento, motivo_aplicacion, id_evento_sanitario, nombre_veterinario, id_usuario, id_usuario_veterinario, estado_registro, fecha_registro, justificacion_anulacion, fecha_hora_anulacion`.

**Reglas adicionales:** activo debe existir y estar `ACTIVO` o `EN_TRATAMIENTO` (`422 ACTIVO_ESTADO_INVALIDO`); ciclo abierto obligatorio (`422 CICLO_NO_ABIERTO`); `fecha_aplicacion` no futura (`400 FECHA_FUTURA`) ni anterior al inicio del ciclo (`400 FECHA_ANTERIOR_A_CICLO`); `via_administracion` inválida → `400 VIA_ADMINISTRACION_INVALIDA`; `id_evento_sanitario` de otro activo → `422 EVENTO_SANITARIO_INVALIDO`; `POBLACIONAL` sin cantidad → `422 POBLACIONAL_SIN_CANTIDAD`; duplicado exacto (activo+nombre+fecha+hora) → `409 MEDICAMENTO_DUPLICADO`.

**Máquina de estados del activo (RF-44):** si hay período de retiro, el endpoint marca el activo `EN_TRATAMIENTO` en la **misma transacción** (rollback atómico si falla). `fecha_fin_retiro_vigente` es el `MAX(fecha_fin_retiro)` entre tratamientos `VALIDADO` — el activo permanece `EN_TRATAMIENTO` hasta que **todos** los retiros vencen. El scheduler diario (`_revertir_retiros_vencidos_diariamente`) revierte a `ACTIVO` automáticamente cuando corresponde; no hay endpoint manual para esto. Tras el `commit`, se notifica por email (best-effort) al Productor y, si el registrante fue Veterinario, también a él.

---

#### `POST /suministros/medicamentos/{id_medicamento}/anulacion` — Anular

Mismas reglas que anulación de consumo de alimento (`AnularRegistroDTO`, 20–255 caracteres, unidireccional). Ya `ANULADO` → `409 MEDICAMENTO_YA_ANULADO`.

**Response:** `MedicamentoResponse` (200).

---

#### `GET /suministros/medicamentos/` — Listar

**Query params:** `id_activo_biologico`, `fecha_desde`, `fecha_hasta`, `estado_registro` — opcionales.

**Response `ConsultaMedicamentosResponse`:** `{ total: int, items: list[MedicamentoResponse] }`.

---

### Eficiencia Alimenticia / ICA — `/suministros/eficiencia-alimenticia` (RF-74, CU-02)

> **Recurso RBAC:** `id_recurso = 49`

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case |
|--------|------|---------|--------------------|--------------------|----------|
| `POST` | `/calcular` | `(49, E)` | Admin, Productor, Vet | Sí | `CalcularICAUseCase` |
| `GET` | `/activos/{id_activo_biologico}/vigente` | `(49, R)` | Admin, Productor, Vet | No | `ConsultarICAVigenteUseCase` |
| `GET` | `/activos/{id_activo_biologico}/historial` | `(49, R)` | Admin, Productor, Vet | No | `ConsultarHistorialICAUseCase` |

#### `POST /suministros/eficiencia-alimenticia/calcular` — Calcular ICA (manual)

**Input `CalcularICADTO`:** `id_activo_biologico: int (gt=0)`, `periodo_evaluacion: PeriodoEvaluacion` (`SEMANAL`\|`MENSUAL`\|`POR_CICLO`).

**Fórmula:** `CA = alimento total consumido (kg) / ganancia de peso total (kg)`, truncado a 4 decimales. Clasificación: `<2.0` `EXCELENTE`, `2.0–3.5` `ACEPTABLE`, `3.5–5.0` `BAJA`, `>5.0` `CRITICA`. `data_quality_score = factores_presentes/4 × 100` (peso inicial, peso final, consumo>0, ganancia>0).

**Ventanas por `periodo_evaluacion`:** `SEMANAL` = últimos 7 días; `MENSUAL` = día 1 del mes en curso → hoy; `POR_CICLO` = inicio de la fase activa → hoy o cierre (sin fecha de inicio → `422 CICLO_SIN_FECHA_INICIO`).

**`CA_NO_CALCULABLE` no es un error HTTP** — responde **200** con `estado_resultado="CA_NO_CALCULABLE"` y `causa_no_calculo` poblado (`SIN_PESO_INICIAL` > `SIN_PESO_FINAL` > `SIN_REGISTROS_CONSUMO` > `POBLACION_INVALIDA` > `PESO_INVALIDO` > `PESO_SIN_VARIACION_POSITIVA`, en orden de precedencia).

**Reglas adicionales:** activo debe existir (`404 ACTIVO_NO_ENCONTRADO`) y estar `ACTIVO` (`422 ACTIVO_NO_ACTIVO`). Solo hay un resultado "vigente" por (activo, período) — al calcular uno nuevo, el anterior pasa a histórico (`es_vigente=false`). Si la clasificación es `CRITICA`, se genera una alerta en `modulo3.alertas` (`origen_evento="BACKEND"`).

**Response `ResultadoICAResponse`:**

| Campo | Tipo |
|-------|------|
| `id_resultado_ica` | `int \| None` |
| `id_activo_biologico` | `int` |
| `periodo_evaluacion` | `str` |
| `fecha_inicio_periodo` / `fecha_fin_periodo` | `date` |
| `estado_resultado` | `str` (`CALCULADO`\|`CA_NO_CALCULABLE`) |
| `es_vigente` | `bool` |
| `intento` | `int` |
| `alimento_consumido_total_kg` | `Decimal \| None` |
| `ganancia_peso_kg` | `Decimal \| None` |
| `ca_calculado` | `Decimal \| None` |
| `clasificacion_ca` | `str \| None` |
| `data_quality_score` | `int` |
| `causa_no_calculo` | `str \| None` |
| `tipo_calculo` | `str` |
| `id_usuario` | `int \| None` |
| `fecha_calculo` | `datetime \| None` |

---

#### `GET /suministros/eficiencia-alimenticia/activos/{id_activo_biologico}/vigente` — Consultar ICA vigente

**Query param:** `periodo: PeriodoEvaluacion` — **requerido**.

**Response `ConsultaVigenteResponse`:** `{ id_activo_biologico, periodo_evaluacion, tiene_resultado: bool, mensaje: str | None, resultado: ResultadoICAResponse | None }`. Sin resultado aún → **200** con `tiene_resultado=false` (no 404).

---

#### `GET /suministros/eficiencia-alimenticia/activos/{id_activo_biologico}/historial` — Historial ICA

**Query param:** `periodo: PeriodoEvaluacion | None` — opcional (sin filtrar por período si se omite).

**Response `HistorialICAResponse`:** `{ id_activo_biologico, total: int, items: list[ResultadoICAResponse] }`.

---

### Batch ICA — `/suministros/eficiencia-alimenticia/batch` (RF-74, panel admin)

> **Recurso RBAC:** `id_recurso = 50`. Da acceso también a Productor (intencional: opera el panel de su propia granja).

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case |
|--------|------|---------|--------------------|--------------------|----------|
| `POST` | `/ejecutar` | `(50, E)` | Admin, Productor | Sí | `EjecutarBatchICAUseCase.ejecutar` |
| `POST` | `/{id_ejecucion}/interrumpir` | `(50, E)` | Admin, Productor | Sí | `InterrumpirBatchICAUseCase` |
| `POST` | `/activos/{id_activo_biologico}/reintentar` | `(50, E)` | Admin, Productor | Sí | `ReintentarICAManualUseCase` |
| `GET` | `/estado` | `(50, R)` | Admin, Productor | No | repo directo — últimas 20 ejecuciones |
| `GET` | `/cola` | `(50, R)` | Admin, Productor | No | repo directo — pendientes |
| `GET` | `/fallos` | `(50, R)` | Admin, Productor | No | repo directo — no resueltos |

**Máquina de estados `EjecucionBatchICA`:** `EN_EJECUCION → COMPLETADO | INTERRUMPIDO` (terminal). Transición inválida (ej. interrumpir algo que ya terminó) → `422 BATCH_NO_EN_EJECUCION`.

#### `POST /batch/ejecutar` — Disparar corrida manual

**Input `EjecutarBatchDTO`:** `solo_cola: bool = False` (`true` reactiva solo activos ya encolados, sin barrer todos los `ACTIVO`).

**Reglas:** rechaza si la configuración está desactivada (`422 BATCH_DESACTIVADO`) o si ya hay una corrida en curso (`409 BATCH_EN_CURSO`). Prioriza activos con ICA `CRITICA` vigente, luego antigüedad de ciclo. Excedentes sobre el límite configurado se encolan; si se excede la ventana horaria configurada, se interrumpe cooperativamente preservando pendientes en cola. Reintentos con backoff configurable (`[2,4,6]` min por defecto); al agotarlos, se registra en `FalloCalculoICA`.

**Response:** `EstadoBatchResponse` — `id_ejecucion, estado, tipo_disparo, hora_inicio, hora_fin, hora_corte, cantidad_activos_total, cantidad_activos_procesados, cantidad_activos_pendientes, cantidad_fallidos, causa_interrupcion, num_workers, limite_configurado`.

---

#### `POST /batch/{id_ejecucion}/interrumpir` — Interrumpir corrida en curso

**Input `InterrumpirBatchDTO`:** `motivo: str | None`.

Solo válido si `estado=EN_EJECUCION` (`422 BATCH_NO_EN_EJECUCION` si no); `id_ejecucion` inexistente → `404 EJECUCION_NO_ENCONTRADA`.

**Response:** `EstadoBatchResponse`.

---

#### `POST /batch/activos/{id_activo_biologico}/reintentar` — Reintento manual

Sin body. Recalcula los 3 períodos (`SEMANAL`, `MENSUAL`, `POR_CICLO`) con `tipo_calculo=REINTENTO_MANUAL`; si un período falla por regla de negocio se omite sin abortar el resto. Éxito marca el `FalloCalculoICA` abierto como resuelto (`tipo_resolucion="MANUAL"`).

**Response:** `HistorialICAResponse` (los resultados recién calculados).

---

#### `GET /batch/estado` / `GET /batch/cola` / `GET /batch/fallos`

Sin query params. Responses: `list[EstadoBatchResponse]`; `ColaICAResponse` (`{ total, items: [{id_cola, id_activo_biologico, prioridad, estado, motivo, fecha_encolado}] }`); `FallosICAResponse` (`{ total, items: [{id_fallo, id_activo_biologico, periodo_evaluacion, causa_fallo, intentos, resuelto, timestamp_ultimo_intento}] }`).

---

### Reporte de Gastos Acumulados — `/suministros/reportes-gastos` (RF-77, CU-04)

> **Recurso RBAC:** `id_recurso = 51`. Contador solo tiene `R` (no puede generar, solo consultar).

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case |
|--------|------|---------|--------------------|--------------------|----------|
| `POST` | `/` | `(51, E)` | Admin, Productor | Sí | `GenerarReporteGastosUseCase` |
| `GET` | `/historial` | `(51, R)` | Admin, Productor, Cont | Sí | `ListarHistorialReportesUseCase` |
| `GET` | `/trabajos/{id_cola}` | `(51, R)` | Admin, Productor, Cont | No | `ConsultarEstadoTrabajoReporteUseCase` |
| `GET` | `/{id_reporte_gasto_acumulado}` | `(51, R)` | Admin, Productor, Cont | No | `ConsultarReporteGastosUseCase` |

#### `POST /suministros/reportes-gastos/` — Generar reporte (sync 200 / async 202)

**Input `GenerarReporteGastosDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `fecha_inicio_reporte` | `date` | requerido |
| `fecha_fin_reporte` | `date` | requerido |
| `tipo_periodo` | `GranularidadDesglose` | default `CICLO_COMPLETO`; valores `SEMANAL`, `MENSUAL`, `CICLO_COMPLETO` |
| `activo_biologico_id` | `int \| None` | `gt=0`; `None` = reporte agregado |
| `id_infraestructura` | `int \| None` | `gt=0` |
| `id_especie` | `int \| None` | `gt=0` |
| `categorias_incluidas` | `list[CategoriaGasto] \| None` | `ALIMENTACION`, `MEDICACION`; `None` = ambas |

**Umbral síncrono/asíncrono:** activo puntual asíncrono si el rango supera **366 días**; agregado (sin `activo_biologico_id`) asíncrono si supera **183 días**. Si el umbral se supera y hay demasiados trabajos concurrentes → `429 LIMITE_CONCURRENCIA_EXCEDIDO`.

**Reglas adicionales:** `fecha_inicio > fecha_fin` → `400 RANGO_FECHAS_INVALIDO`; `fecha_fin` futura → `400 FECHA_FIN_FUTURA`; sin `activo_biologico_id` ni `id_infraestructura`/`id_especie` → `400 REPORTE_SIN_ALCANCE`; activo inexistente → `404 ACTIVO_NO_ENCONTRADO`; activo sin `fecha_inicio_ciclo` → `422 ACTIVO_SIN_CICLO`; `fecha_inicio` anterior al ciclo → `400 FECHA_INICIO_ANTERIOR_CICLO`.

**El endpoint no fija `response_model`** — el handler decide el status en runtime: si el resultado requiere procesamiento async, fuerza `response.status_code = 202` y retorna `TrabajoReporteResponse`; si no, retorna `ReporteGastoResponse` (200 implícito).

**Response `ReporteGastoResponse`** (caso síncrono):

| Campo | Tipo |
|-------|------|
| `id_reporte_gasto_acumulado` | `int \| None` |
| `id_activo_biologico` / `id_infraestructura` / `id_especie` | `int \| None` |
| `fecha_inicio` / `fecha_fin` | `date` |
| `tipo_periodo` | `str` |
| `gasto_total_acumulado` | `Decimal` |
| `gasto_promedio_individuo` | `Decimal \| None` (solo POBLACIONAL; `None` si `cantidad_actual=0`) |
| `causa_no_calculable_promedio` | `str \| None` |
| `sin_datos` | `bool` |
| `desglose_categorias` | `list[{categoria, subtotal, num_registros, porcentaje}]` |
| `desglose_temporal` | `list[{etiqueta, fecha_inicio, fecha_fin, monto}]` |
| `registros_sin_costo` | `list[{categoria, id_origen, fecha, descripcion}]` |
| `tendencia` | `{gasto_periodo_actual, gasto_periodo_anterior, variacion_porcentual, estado, nota} \| None` |
| `fecha_generacion` | `datetime \| None` |

`tendencia.estado`: `CALCULADA`, `SIN_BASE_COMPARATIVA` (período anterior=0, actual>0), o `SIN_MOVIMIENTO` (ambos=0).

**Response `TrabajoReporteResponse`** (caso asíncrono, 202): `{ id_cola: int | None, estado: str, fecha_solicitud: datetime | None, mensaje: str }`.

---

#### `GET /suministros/reportes-gastos/historial` — Historial de reportes generados

**Query param:** `limite: int = 20` (`ge=1, le=100`).

**Response `HistorialReportesResponse`:** `{ total: int, items: list[ReporteGastoResponse] }`.

---

#### `GET /suministros/reportes-gastos/trabajos/{id_cola}` — Estado de trabajo (polling)

**Response `EstadoTrabajoReporteResponse`:** `{ id_cola, estado, fecha_solicitud, fecha_procesado, intento, reporte: ReporteGastoResponse | None }` — `reporte` viene poblado solo cuando `estado=COMPLETADO`.

---

#### `GET /suministros/reportes-gastos/{id_reporte_gasto_acumulado}` — Obtener reporte por id

**Response:** `ReporteGastoResponse`.

---

### Batch Reportes de Gastos — `/suministros/reportes-gastos/batch` (RF-77, panel admin)

> **Recurso RBAC:** `id_recurso = 53`. Espejo del recurso 50: Admin + Productor.

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Retorna |
|--------|------|---------|--------------------|--------------------|---------|
| `POST` | `/ejecutar` | `(53, E)` | Admin, Productor | No | `{"trabajos_procesados": int}` |
| `GET` | `/cola` | `(53, R)` | Admin, Productor | No | `{"total", "items": [{id_cola, estado, fecha_solicitud}]}` |
| `GET` | `/fallos` | `(53, R)` | Admin, Productor | No | `{"total", "items": [{id_fallo, id_cola, causa_fallo, intentos, timestamp_ultimo_intento}]}` |

Estos 3 endpoints **no declaran `response_model`** — retornan `dict` planos, no schemas Pydantic.

---

### Historial de Suministros — `/suministros/historial` (RF-81, CU-04)

> **Recurso RBAC:** `id_recurso = 52` — el único recurso del módulo abierto a los 6 roles (Admin, Productor, Vet, Cont, Gestor de Granja, Rev. Fiscal), todos con R y E.

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case | Status |
|--------|------|---------|--------------------|--------------------|----------|--------|
| `GET` | `/` | `(52, R)` | Admin, Productor, Vet, Cont, Gestor Granja, Rev. Fiscal | Sí | `ConsultarHistorialSuministrosUseCase` | 200 |
| `GET` | `/exportar` | `(52, R)` | (los mismos 6) | Sí | `ExportarHistorialSincronoUseCase` | 200, `StreamingResponse` CSV |
| `POST` | `/trabajos` | `(52, E)` | (los mismos 6) | Sí | `SolicitarTrabajoHistorialUseCase` | **202** |
| `GET` | `/trabajos/{id_cola}` | `(52, R)` | (los mismos 6) | No | `ConsultarEstadoTrabajoHistorialUseCase` | 200 |
| `GET` | `/trabajos/{id_cola}/descargar` | `(52, R)` | (los mismos 6) | No | `DescargarResultadoTrabajoHistorialUseCase` | 200, `StreamingResponse` CSV |

#### `GET /suministros/historial/` y `GET /suministros/historial/exportar`

**Query params** (idénticos; `exportar` omite `pagina`/`registros_por_pagina`):

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `id_activo_biologico` | `int` | — | **requerido**, `gt=0` |
| `id_ciclo_productivo` | `int \| None` | — | `gt=0` |
| `fecha_inicio_filtro` / `fecha_fin_filtro` | `date \| None` | — | — |
| `tipo_suministro_filtro` | `TipoSuministroFiltro` | `TODOS` | `ALIMENTO`, `MEDICAMENTO`, `SERVICIO_VETERINARIO`, `INSEMINACION`, `TODOS` |
| `origen_precio_filtro` | `OrigenPrecioFiltro` | `TODOS` | `MANUAL`, `M40_AUTOMATICO`, `TODOS` |
| `costo_min` / `costo_max` | `Decimal \| None` | — | `ge=0` |
| `pagina` | `int` | `1` | solo en `GET /`, `ge=1` |
| `registros_por_pagina` | `int` | `50` | solo en `GET /`, `ge=1, le=200` |

> ⚠️ `tipo_suministro_filtro=SERVICIO_VETERINARIO` o `INSEMINACION` está aceptado en el contrato pero **siempre devuelve 0 resultados** — no existen tablas origen para esos tipos en `modulo5` todavía. No es un bug, es una limitación documentada.

**Reglas adicionales:** volumen `NIVEL_3`/`NIVEL_4` (>10.000 registros por defecto) → `422 CONSULTA_REQUIERE_MODO_ASINCRONO` en `GET /`, o `422 EXPORTACION_REQUIERE_MODO_ASINCRONO` en `/exportar` (umbral de exportación 10.000); filtros incoherentes (fechas/costos) → `422 COMBINACION_FILTROS_INVALIDA`; `id_ciclo_productivo` que no pertenece al activo → `422 CICLO_NO_PERTENECE_AL_ACTIVO`; activo inexistente → `404 ACTIVO_NO_ENCONTRADO`; fuera del alcance del Gestor de Granja → `403 ACCESO_DENEGADO`. Toda consulta/exportación registra auditoría no bloqueante (`CONSULTA_HISTORIAL_EJECUTADA`/`EXPORTACION_HISTORIAL_GENERADA`) — si falla, no afecta la respuesta ya construida.

**Response `HistorialSuministroListResponse`** (`GET /`): `{ items: list[LineaHistorialResponse], resumen: ResumenHistorialResponse }`.

**`LineaHistorialResponse`:** `id_registro_suministro, id_activo_biologico, id_ciclo_productivo, tipo_suministro, descripcion, fecha_aplicacion, cantidad, unidad_medida, precio_unitario, costo_registro, origen_precio, tipo_operacion, observacion, fecha_registro, nombre_activo, especie, nombre_ciclo, estado_ciclo` (los últimos 4 opcionales — vienen de M02, `None` si no responde).

**`ResumenHistorialResponse`:** `total_registros_filtrados, monto_total_filtrado, desglose_por_tipo_suministro: dict, desglose_por_ciclo: dict, pagina_actual, total_paginas, datos_contexto_no_disponibles: bool, datos_actualizados_hasta: datetime, nivel_volumen: int`.

`GET /exportar` retorna `StreamingResponse` CSV (`Content-Disposition: attachment`) en vez del JSON anidado.

---

#### `POST /suministros/historial/trabajos` — Encolar trabajo pesado

**Input `SolicitarTrabajoHistorialDTO`:** mismos filtros que arriba, más `tipo_trabajo: TipoTrabajoHistorial` (`CONSULTA_PESADA`\|`EXPORTACION`) y `registros_por_pagina: int = 50 (ge=1, le=200)`.

**Reglas adicionales:** límite de concurrencia por tipo (`limite_concurrencia_exportaciones` default 3, `limite_concurrencia_consultas` default 5) → `429 LIMITE_EXPORTACIONES_EXCEDIDO` / `LIMITE_CONCURRENCIA_EXCEDIDO`.

**Response `TrabajoHistorialResponse`** (siempre 202): `{ id_cola: int | None, tipo_trabajo: str, estado: str, fecha_solicitud: datetime | None, mensaje: str }`.

---

#### `GET /suministros/historial/trabajos/{id_cola}` — Estado de trabajo

**Response `EstadoTrabajoHistorialResponse`:** `{ id_cola, tipo_trabajo, estado, fecha_solicitud, fecha_procesado, intento, total_registros: int | None }`.

---

#### `GET /suministros/historial/trabajos/{id_cola}/descargar` — Descargar resultado

Solo trabajos `tipo_trabajo=EXPORTACION` ya `COMPLETADO` (`422 TRABAJO_NO_COMPLETADO` si no). Archivo retenido 72h (sin limpieza automática implementada aún). **Response:** `StreamingResponse` CSV.

---

### Batch Historial de Suministros — `/suministros/historial/batch` (RF-81, panel admin)

> **Recurso RBAC:** `id_recurso = 54` — **exclusivo Administrador** (el panel muestra cola/fallos de *otros* usuarios, incluido el Gestor de Granja; se evita filtrar visibilidad cruzada entre unidades productivas).

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Retorna |
|--------|------|---------|--------------------|--------------------|---------|
| `POST` | `/ejecutar` | `(54, E)` | Admin | No | `{"trabajos_procesados": int}` |
| `GET` | `/cola` | `(54, R)` | Admin | No | `{"total", "items": [{id_cola, tipo_trabajo, estado, fecha_solicitud}]}` |
| `GET` | `/fallos` | `(54, R)` | Admin | No | `{"total", "items": [{id_fallo, id_cola, causa_fallo, intentos, timestamp_ultimo_intento}]}` |

---

### Costeo Directo — `/suministros/costeo-directo` (RF-78, CU-05)

> **Recurso RBAC:** `id_recurso = 55`. Solo cubre `SERVICIO_VETERINARIO` e `INSEMINACION` — ALIMENTO/MEDICAMENTO **nunca** pasan por aquí, se acumulan automáticamente vía triggers desde RF-75/76.

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case | Status |
|--------|------|---------|--------------------|--------------------|----------|--------|
| `POST` | `/` | `(55, C)` | Admin, Productor, Vet | Sí | `RegistrarSuministroDirectoUseCase` | **201**, o **200 si `ya_procesado`** |
| `POST` | `/{id_registro_original}/correccion` | `(55, U)` | Admin, Cont | Sí | `RegistrarCorreccionSuministroUseCase` | **201**, o **200 si `ya_procesado`** |
| `GET` | `/acumulado/activo/{id_activo_biologico}` | `(55, R)` | Admin, Productor, Vet, Cont, Rev. Fiscal | No | `ConsultarAcumuladoCicloUseCase.por_activo` | 200 |
| `GET` | `/acumulado/ciclo/{id_gestion_fases}` | `(55, R)` | Admin, Productor, Vet, Cont, Rev. Fiscal | No | `ConsultarAcumuladoCicloUseCase.por_gestion_fase` | 200 |

#### `POST /suministros/costeo-directo/` — Registrar suministro directo

**Input `RegistrarSuministroDirectoDTO`:**

| Campo | Tipo | Restricciones |
|-------|------|----------------|
| `id_activo_biologico` | `int` | `gt=0` |
| `tipo_suministro` | `Literal["SERVICIO_VETERINARIO","INSEMINACION"]` | solo estos 2 valores |
| `cantidad` | `Decimal` | `gt=0` |
| `unidad_medida` | `str` | 1–20 |
| `precio_unitario` | `Decimal` | `gt=0` — siempre manual |
| `fecha_aplicacion` | `date` | requerido |
| `justificacion_precio` | `str` | 20–500 — siempre obligatoria (no hay integración M40) |
| `id_idempotencia` | `UUID` | **obligatorio** — ver patrón de idempotencia arriba |
| `observacion` | `str \| None` | máx. 500 |

**Orden de validación:** idempotencia primero (si `id_idempotencia` ya existe, devuelve el registro existente con **200** y `ya_procesado=true`, sin repetir el resto de validaciones) → ciclo activo obligatorio (`422 CICLO_NO_ACTIVO`) → `fecha_aplicacion` dentro del rango del ciclo y no futura (`400 FECHA_FUERA_DE_RANGO` / `400 FECHA_FUTURA_NO_PERMITIDA`) → deduplicación por contenido exacto con `id_idempotencia` distinto (`409 SUMINISTRO_DUPLICADO`) → cálculo de `costo_registro = cantidad × precio_unitario` en Python → persistencia con reintentos (hasta 3, backoff 1/3/5 s) ante fallo técnico; agotados → error de infraestructura (`REGISTRO_FALLIDO`, registrado en auditoría).

**Response `RegistroSuministroDirectoResponse`:**

| Campo | Tipo |
|-------|------|
| `id_registro_suministro` | `UUID \| None` |
| `id_activo_biologico` | `int` |
| `id_ciclo_productivo` | `int` |
| `id_gestion_fases` | `int` |
| `tipo_suministro` | `str` |
| `cantidad` | `Decimal` |
| `unidad_medida` | `str` |
| `precio_unitario_resuelto` | `Decimal` |
| `costo_registro` | `Decimal` |
| `origen_precio` | `str` (siempre `"MANUAL"`) |
| `fecha_aplicacion` | `date` |
| `naturaleza_costo` | `str` (`MANTENIMIENTO`\|`INVERSION`) |
| `justificacion_precio` | `str \| None` |
| `observacion` | `str \| None` |
| `tipo_operacion` | `str` (`REGISTRO`\|`CORRECCION`) |
| `id_registro_original` | `UUID \| None` |
| `motivo_correccion` | `str \| None` |
| `id_idempotencia` | `UUID` |
| `fecha_registro` | `datetime \| None` |

---

#### `POST /suministros/costeo-directo/{id_registro_original}/correccion` — Corregir registro

`id_registro_original` va en la URL. **Acepta corregir cualquier tipo de suministro**, incluidos los originados por RF-75/76 — mitigación para reflejar manualmente una anulación de esos flujos, que no dispara reversión automática del acumulado.

**Input `RegistrarCorreccionSuministroDTO`:** `cantidad_corregida: Decimal (gt=0)`, `precio_unitario_corregido: Decimal (gt=0)`, `justificacion_precio: str (20–500)`, `motivo_correccion: str (20–500)`, `id_idempotencia: UUID`.

**Reglas adicionales:** `id_registro_original` inexistente → `404 REGISTRO_ORIGINAL_NO_ENCONTRADO`; corregir una corrección (no un `REGISTRO` original) → `422 CORRECCION_SOBRE_CORRECCION`; lee el acumulado con lock explícito (`SELECT ... FOR UPDATE`) y valida que el delta no lo deje negativo (`422 ACUMULADO_NEGATIVO`, determinístico, no se reintenta); bajo contención real, tras 3 reintentos → `409 CONFLICTO_CONCURRENCIA`.

**Response:** `RegistroSuministroDirectoResponse` (201, o 200 si `ya_procesado`).

---

#### `GET /suministros/costeo-directo/acumulado/activo/{id_activo_biologico}` y `.../acumulado/ciclo/{id_gestion_fases}`

`por_activo` resuelve la fase activa del activo internamente; sin ciclo activo → `404 CICLO_NO_ACTIVO`. Si el acumulado aún no existe (sin suministros registrados) → `404 ACUMULADO_NO_ENCONTRADO`.

**Response `AcumuladoCicloResponse`:** `id_activo_biologico, id_ciclo_productivo, id_gestion_fases, acumulado_total_ciclo: Decimal, acumulado_por_categoria: dict[str, Decimal], version_acumulado: int, estado: str, fecha_ultima_actualizacion: datetime | None`.

---

### Provisión NIC-41 — `/suministros/nic41` (RF-79, CU-05)

> **Recurso RBAC:** `id_recurso = 56`. Nota: aquí la corrección usa acción **E** (Ejecutar) — a diferencia del recurso 55 (costeo directo) donde la corrección usa **U**; cada recurso define su propia convención de acción.

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case | Status |
|--------|------|---------|--------------------|--------------------|----------|--------|
| `POST` | `/ciclo/{id_gestion_fases}/consolidar` | `(56, E)` | Admin, Cont | Sí | `ConsolidarCicloUseCase` | 201 |
| `POST` | `/ciclo/{id_gestion_fases}/consolidar-manual` | `(56, E)` | Admin, Cont | Sí | `GenerarProvisionManualUseCase` | 201 |
| `POST` | `/{id_provision}/correccion` | `(56, E)` | Admin, Cont | Sí | `CorregirProvisionUseCase` | 201 |
| `GET` | `/{id_provision}` | `(56, R)` | Admin, Productor, Cont, Rev. Fiscal | No | `ConsultarProvisionUseCase` | 200 |
| `GET` | `/ciclo/{id_gestion_fases}/versiones` | `(56, R)` | Admin, Productor, Cont, Rev. Fiscal | No | `ListarVersionesProvisionUseCase` | 200 |

#### `POST /suministros/nic41/ciclo/{id_gestion_fases}/consolidar` — Cierre oficial de ciclo

Exige que la fase esté cerrada: `gestiones_fases.es_activa=False` **y** `fecha_finalizacion` presente → si no, `409 CICLO_ACTIVO`. Es la única verificación de "ciclo cerrado" porque no existe un hook de M02 que notifique el cierre a M05 (RF-41 no implementado). Sin acumulado → `422 SIN_INFORMACION_ACUMULADA`. `id_gestion_fases` inexistente → `404 CICLO_NO_ENCONTRADO`.

**Response `ProvisionNic41Response`:**

| Campo | Tipo |
|-------|------|
| `id_provision` | `int \| None` |
| `id_activo_biologico` | `int` |
| `id_ciclo_productivo` / `id_gestion_fases` | `int \| None` |
| `modalidad` | `str` (siempre `"CONSOLIDADO"` en este módulo) |
| `monto_provision` | `Decimal` |
| `desglose_categoria` | `dict[str, Decimal]` |
| `lista_registros` | `list[dict]` (página actual) |
| `total_registros` | `int` (total real, no de la página) |
| `version_reporte` | `int` |
| `id_reporte_anterior` | `int \| None` |
| `motivo_correccion` | `str \| None` |
| `es_reporte_potencialmente_incompleto` | `bool` |
| `estado` | `str` |
| `hash_integridad` | `str \| None` |
| `fecha_generacion` | `datetime \| None` |
| `fecha_entrega_m06` | `datetime \| None` |

**Inmutabilidad:** cada versión es append-only; `"SUPERADO"` es un estado derivado (existe una versión posterior), nunca una columna mutada — mutarla invalidaría el `hash_integridad` calculado por trigger.

---

#### `POST /suministros/nic41/ciclo/{id_gestion_fases}/consolidar-manual` — Provisión ad-hoc

Para auditorías/recálculos — **no exige cierre de ciclo**, por lo que **siempre** marca `es_reporte_potencialmente_incompleto=true` (un ciclo activo puede recibir más suministros después del snapshot). Comparte la misma cadena de versiones (`version_reporte`/`id_reporte_anterior`) que la consolidación oficial.

**Response:** `ProvisionNic41Response`.

---

#### `POST /suministros/nic41/{id_provision}/correccion` — Corregir provisión

**Input `CorregirProvisionDTO`:** `motivo_correccion: str (20–500)`.

Genera `version_reporte = N+1` con `id_reporte_anterior` apuntando a la versión corregida, recalculando desde el estado actual de `registro_suministro`/`acumulado_ciclo` — nunca hace `UPDATE` sobre la fila original. `id_provision` inexistente → `404 PROVISION_NO_ENCONTRADA`.

**Response:** `ProvisionNic41Response`.

---

#### `GET /suministros/nic41/{id_provision}` — Obtener provisión

**Query params:** `pagina: int = 1 (ge=1)`, `por_pagina: int = 50 (ge=1, le=200)` — pagina `lista_registros` **en memoria**; `total_registros` siempre refleja el total real.

**Response:** `ProvisionNic41Response`.

---

#### `GET /suministros/nic41/ciclo/{id_gestion_fases}/versiones` — Cadena de versiones

**Response `ListaVersionesProvisionResponse`:** `{ total: int, versiones: list[ProvisionNic41Response] }` (en este listado, `lista_registros` de cada versión suele venir vacía — solo metadatos).

---

### Auditoría del Módulo — `/suministros/auditoria` (RF-80, CU-06)

> **Recurso RBAC:** `id_recurso = 57`. A diferencia de `auditoria_m04` (exclusivo Admin), aquí también acceden Contador y Revisor Fiscal — coherente con la orientación de RF-80 al control financiero/fiscal.

| Método | Ruta | Permiso | Roles autorizados | `usuario_actual` | Use Case |
|--------|------|---------|--------------------|--------------------|----------|
| `GET` | `/` | `(57, R)` | Admin, Cont, Rev. Fiscal | Sí | `ConsultarAuditoriaSuministrosUseCase.listar` |
| `GET` | `/exportar` | `(57, E)` | Admin, Cont, Rev. Fiscal | Sí | `ExportarAuditoriaSuministrosUseCase.exportar` |
| `GET` | `/{id_auditoria_suministro}` | `(57, R)` | Admin, Cont, Rev. Fiscal | Sí | `ConsultarAuditoriaSuministrosUseCase.obtener_por_id` |

Ningún endpoint de este router tiene DTO de input (todos son `GET` con query params).

#### `GET /suministros/auditoria/` — Listar bitácora

**Query params:** `tipo_operacion: str|None` (texto libre — la columna real mezcla los 8 valores de negocio del módulo con 4 genéricos de triggers DML), `id_usuario: int|None`, `fecha_desde/fecha_hasta: datetime|None`, `entidad_afectada: str|None`, `id_activo_biologico: int|None (gt=0)`, `id_ciclo_productivo: int|None (gt=0)`, `resultado: str|None` (`EXITOSO`\|`FALLIDO`\|`RECHAZADO`), `clasificacion_registro: str|None` (`NIC41`\|`TECNICO`), `pagina: int=1 (ge=1)`, `registros_por_pagina: int=50 (ge=1, le=200)`.

Valores posibles de `tipo_operacion` (negocio): `SUMINISTRO_REGISTRADO`, `SUMINISTRO_CORREGIDO`, `REGISTRO_FALLIDO`, `CONFLICTO_CONCURRENCIA`, `CICLO_CONSOLIDADO`, `PROVISION_INCREMENTAL_ENTREGADA`, `PROVISION_INCREMENTAL_FALLIDA`, `REPORTE_COSTOS_GENERADO`, `CONSULTA_HISTORIAL_EJECUTADA`, `EXPORTACION_HISTORIAL_GENERADA` (más `INSERT`/`UPDATE`/`DELETE`/`SELECT` genéricos de otros triggers DML).

**Response `AuditoriaSuministrosListResponse`:** `{ total, pagina, registros_por_pagina, items: list[EventoAuditoriaSuministroResponse] }`.

**`EventoAuditoriaSuministroResponse`:** `id_auditoria_suministro, entidad_afectada, tipo_operacion, id_usuario, resultado, fecha_evento, datos_anteriores: dict|None, datos_nuevos: dict|None, ip_origen, id_sesion, fecha_emision, id_activo_biologico, id_ciclo_productivo, costo_afectado: Decimal|None, origen_precio, clasificacion_registro, retencion_aplicable, hash_integridad, registro_incompleto: bool|None, detalle_causa, numero_reintentos: int|None, fecha_intentos: list[datetime]|None, id_gestion_fases`.

**Nota:** consultar/exportar esta bitácora **no genera un nuevo evento de auditoría** (a diferencia de RF-81, que sí se auto-audita).

---

#### `GET /suministros/auditoria/exportar` — Exportar

**Query params:** los mismos filtros (sin paginación) + `formato: str = "csv"` (`pattern="^(csv|xlsx|pdf)$"`). Formato inválido → `400 FORMATO_EXPORTACION_INVALIDO`. Límite duro de 10.000 registros por exportación (sin modo asíncrono aquí — el volumen de esta tabla es órdenes de magnitud menor que el de historial de RF-81).

**Response:** `StreamingResponse` con `Content-Disposition: attachment` — soporta **CSV, XLSX (vía `openpyxl`) y PDF (vía `reportlab`)**, a diferencia de la auditoría de M04 que solo exporta JSON/CSV.

---

#### `GET /suministros/auditoria/{id_auditoria_suministro}` — Detalle de evento

**Response:** `EventoAuditoriaSuministroResponse`.

---

## Tabla de permisos RBAC usados

> Extraída en vivo de `modulo1.permisos` (DB `sgpmp`) el 2026-08-01. Acciones: C=1 Crear, R=2 Leer, U=3 Actualizar, D=4 Eliminar/Desactivar, E=5 Ejecutar. Todas las filas listadas están `es_activo=true`.

| `id_recurso` | Recurso | Admin | Productor | Veterinario | Contador | Gestor Granja | Rev. Fiscal |
|---|---|---|---|---|---|---|---|
| 47 | `consumo_alimentos` | C,R,D | C,R | C,R,D | — | — | — |
| 48 | `medicamentos` | C,R,D | R | C,R,D | — | — | — |
| 49 | `eficiencia_alimenticia` | R,E | R,E | R,E | — | — | — |
| 50 | `administracion_batch_ica` | R,E | R,E | — | — | — | — |
| 51 | `reporte_gastos_suministros` | R,E | R,E | — | R | — | — |
| 52 | `historial_suministros` | R,E | R,E | R,E | R,E | R,E | R,E |
| 53 | `administracion_batch_reportes_gastos` | R,E | R,E | — | — | — | — |
| 54 | `administracion_batch_historial_suministros` | R,E | — | — | — | — | — |
| 55 | `costeo_directo_suministros` | C,R,U | C,R | C,R | R,U | — | R |
| 56 | `provision_nic41` | R,E | R | — | R,E | — | R |
| 57 | `bitacora_auditoria_suministros` | R,E | — | — | R,E | — | R,E |

**Ingeniero de Campo y Supervisor no tienen ningún permiso activo** en ninguno de los 11 recursos de este módulo.

**No hay gaps de RBAC pendientes** para este módulo: las 42 combinaciones `(id_recurso, id_accion)` usadas por los routers ya existen y están activas en `modulo1.permisos`. Las asimetrías notadas (Contador con `U` pero sin `C` en el recurso 55; Productor con acceso a los paneles batch 50/53; recurso 54 exclusivo Admin) son decisiones de diseño documentadas en `anotaciones/modulo_5/cu04_gaps_bd_rf77_rf81.md`, no bugs.

---

## Use Cases — resumen de firmas

| Clase | Método(s) principal(es) — parámetros |
|-------|----------------------------------------|
| `RegistrarConsumoAlimentoUseCase` | `execute(dto: RegistrarConsumoAlimentoDTO, usuario_actual: UsuarioActual) → ConsumoAlimento` |
| `AnularConsumoAlimentoUseCase` | `execute(id_consumo: int, dto: AnularRegistroDTO, usuario_actual: UsuarioActual) → ConsumoAlimento` |
| `ConsultarConsumosUseCase` | `execute(*, id_activo_biologico, fecha_desde, fecha_hasta, tipo_alimento, estado_registro) → list[ConsumoAlimento]` |
| `RegistrarMedicamentoUseCase` | `execute(dto: RegistrarMedicamentoDTO, usuario_actual: UsuarioActual) → ResultadoRegistroMedicamento` |
| `AnularMedicamentoUseCase` | `execute(id_medicamento: int, dto: AnularRegistroDTO, usuario_actual: UsuarioActual) → Medicamento` |
| `ConsultarMedicamentosUseCase` | `execute(*, id_activo_biologico, fecha_desde, fecha_hasta, estado_registro) → list[Medicamento]` |
| `RevertirRetirosVencidosUseCase` | `ejecutar() → int` (scheduler diario, sin endpoint) |
| `CalcularICAUseCase` | `execute(*, id_activo_biologico, periodo, tipo_calculo, id_usuario=None, intento=1) → ResultadoICA` |
| `ConsultarICAVigenteUseCase` | `execute(id_activo_biologico, periodo) → ResultadoICA \| None` |
| `ConsultarHistorialICAUseCase` | `execute(id_activo_biologico, periodo=None) → list[ResultadoICA]` |
| `EjecutarBatchICAUseCase` | `async ejecutar(*, tipo_disparo="AUTOMATICO", id_usuario=None, solo_cola=False) → EjecucionBatchICA` |
| `InterrumpirBatchICAUseCase` | `execute(id_ejecucion, id_usuario, motivo=None) → EjecucionBatchICA` |
| `ReintentarICAManualUseCase` | `execute(id_activo_biologico, id_usuario) → list[ResultadoICA]` |
| `GenerarReporteGastosUseCase` | `execute(filtros: FiltrosReporteGasto, id_usuario) → ReporteGasto \| TrabajoReporteGasto`; `generar_forzado(...)` (worker) |
| `ListarHistorialReportesUseCase` | `execute(id_usuario, limite=20) → list[ReporteGasto]` |
| `ConsultarEstadoTrabajoReporteUseCase` | `execute(id_cola) → EstadoTrabajoReporte` |
| `ConsultarReporteGastosUseCase` | `execute(id_reporte_gasto_acumulado) → ReporteGasto` |
| `ProcesarColaReportesGastosUseCase` | `async ejecutar() → int` (worker) |
| `ConsultarHistorialSuministrosUseCase` | `execute(filtros, *, id_usuario, id_rol) → ResultadoConsultaHistorial`; `consultar_forzado(...)` (worker) |
| `ExportarHistorialSincronoUseCase` | `execute(filtros, *, id_usuario, id_rol) → tuple[contenido, nombre_archivo, total]`; `exportar_forzado(...)` (worker) |
| `SolicitarTrabajoHistorialUseCase` | `execute(tipo_trabajo, filtros, id_usuario, id_rol) → TrabajoHistorialSuministro` |
| `ConsultarEstadoTrabajoHistorialUseCase` | `execute(id_cola) → EstadoTrabajoHistorial` |
| `DescargarResultadoTrabajoHistorialUseCase` | `execute(id_cola) → tuple[contenido_csv, nombre_archivo]` |
| `ProcesarColaHistorialSuministrosUseCase` | `async ejecutar() → int` (worker) |
| `RegistrarSuministroDirectoUseCase` | `execute(dto: RegistrarSuministroDirectoDTO, usuario_actual) → ResultadoRegistroDirecto` |
| `RegistrarCorreccionSuministroUseCase` | `execute(id_registro_original: UUID, dto: RegistrarCorreccionSuministroDTO, usuario_actual) → ResultadoRegistroDirecto` |
| `ConsultarAcumuladoCicloUseCase` | `por_activo(id_activo_biologico) → AcumuladoCiclo`; `por_gestion_fase(id_gestion_fases) → AcumuladoCiclo` |
| `ConsolidarCicloUseCase` | `execute(id_gestion_fases, usuario_actual) → ProvisionNic41` |
| `GenerarProvisionManualUseCase` | `execute(id_gestion_fases, usuario_actual) → ProvisionNic41` |
| `CorregirProvisionUseCase` | `execute(id_provision, motivo_correccion: str, usuario_actual) → ProvisionNic41` |
| `ConsultarProvisionUseCase` | `execute(id_provision) → ProvisionNic41` |
| `ListarVersionesProvisionUseCase` | `execute(id_gestion_fases) → list[ProvisionNic41]` |
| `ConsultarAuditoriaSuministrosUseCase` | `listar(filtros: FiltrosAuditoriaSuministro) → tuple[list[EventoAuditoriaSuministroConsulta], int]`; `obtener_por_id(id_auditoria_suministro) → EventoAuditoriaSuministroConsulta` |
| `ExportarAuditoriaSuministrosUseCase` | `exportar(filtros, *, formato) → tuple[bytes, media_type, filename]` |

---

## Ejemplos de payload reales

Este documento describe contrato y reglas; para ejemplos de request/response verificados (incluyendo catálogos de error completos por escenario), usar los archivos de curl ya existentes en `anotaciones/modulo_5/`:

| Archivo | CU cubierto |
|---|---|
| `curls_m05_cu01_suministros.md` | RF-75/RF-76 — Consumo de Alimento y Medicamentos |
| `curls_m05_cu02_eficiencia_alimenticia.md` | RF-74 — ICA + panel batch |
| `curls_m05_cu04_reporte_gastos_historial.md` | RF-77 + RF-81 — Reporte de Gastos e Historial |
| `curls_m05_cu05_costeo_nic41.md` | RF-78/RF-79 — Costeo Directo y Provisión NIC-41 |
| `curls_m05_cu06_auditoria.md` | RF-80 — Auditoría del módulo |
