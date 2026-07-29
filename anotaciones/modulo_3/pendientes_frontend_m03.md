# Pendientes reportados por front-end — Triage M03 (Telemetría e IoT)

Este documento clasifica cada "cosa faltante / pendiente" que el equipo de front-end anotó al
integrar los prototipos contra el backend real del M03, y determina **de quién es la responsabilidad**
y **qué hay que hacer**. No implementa nada: es un triage para saber *dónde está el hueco*.

## Marco de responsabilidades (recordatorio)

Según `anotaciones/modulo_3/M03-SPLIT.md` (§1.1, piloto §3.3) nuestro equipo es **Dev (backend)**:

- **Dev-M03:** RF-53, RF-56, RF-57, RF-58, RF-59, RF-60, RF-61, RF-62, RF-63 (recepción, validación,
  almacenamiento, sync server-side del buffer, monitoreo, alertas, dispositivos, vinculación, calidad, auditoría).
- **AIOT (firmware/Edge):** **RF-54 (buffer local)** y **RF-55 (procesamiento Edge)** — *fuera de alcance Dev*.
- **Dependencias / otros módulos:** M01 (auth/RBAC), **M09** (catálogo I3P-1, umbrales, dispositivos RF-21/22),
  **M02** (activos biológicos), **M04** (inferencia IA), **M08** (reportes/exportación).

**Regla de este triage:** solo se marca como *tarea backend obligatoria de M03* lo que el RF exige y M03
no expuso. Lo que el prototipo pide de más se marca **FUERA-RF** (decisión de producto, no falta de backend).

Leyenda de tipo:
`BUG-DEV` bug en backend M03 · `BRECHA-RF-DEV` el RF lo exige y M03 no lo expuso ·
`DEP-Mxx` bloqueado por otro módulo no implementado · `AIOT` responsabilidad firmware/Edge ·
`FUERA-RF` el prototipo pidió más de lo que el RF exige.

---

## Veredicto por punto

| # | Punto del front-end | Dueño | Tipo | Veredicto | Evidencia |
|---|---|---|---|---|---|
| 1 | [F8] No hay GET humanos para ingesta/buffer/edge/pipeline (solo POST de dispositivo) | AIOT + M03-Dev | AIOT / FUERA-RF | **No es falta de Dev.** Buffer (RF-54) y Edge (RF-55) son **AIOT**. La ingesta (RF-53) es POST de dispositivo por diseño; las lecturas humanas ya existen vía monitoreo/historial/calidad/auditoría. Ningún RF exige un GET humano del "pipeline crudo". | M03-SPLIT §1.1, §8 · routers `telemetria_router.py`, `evento_edge_router.py` (device-POST) · vistas DB `vw_m03_pipeline_inferencia`, `vw_m03_02_buffer_sincronizacion` existen pero no se exponen (cu02_gaps) |
| 2 | [F3] "Marcar / resolver mantenimiento" sin endpoint | **M03-Dev** | **BRECHA-RF-DEV** | **Falta real de backend.** RF-60 CA-7/CA-8 y Fase 5 exigen transición manual `EN_MANTENIMIENTO ↔ ACTIVO` por Ingeniero/Admin. El permiso RBAC (recurso 35, acción U) para Admin+Ing existe, pero **ningún router lo usa**; el job automático omite ese estado. **Hay que crear el endpoint + caso de uso.** | `estado_dispositivo_iot.py:38,40` (job omite EN_MANTENIMIENTO) · `estado_dispositivo_iot_repository.py:31` · `api_reference_m03…md` (perm 35,U sin endpoint) · RF-60 CA-7/CA-8 |
| 3 | [F3] No hay listado de dispositivos / tablero de flota con KPIs por estado | M03-Dev / M08 | FUERA-RF | **No es falta de Dev.** RF-60 define esas métricas de flota como salida **para M08**, no como endpoint humano de M03; RF-58 muestra **sensores**, no dispositivos. M09 ya expone el registro. Un tablero de KPIs por estado es trabajo nuevo opcional, no exigido por el RF. | Solo existen `GET /iot/dispositivos/{id}/estado` y `/historial` (`infraestructura_iot_router.py:76,106`) · M09 `GET /configuracion/dispositivos-iot` (`dispositivo_iot_router.py:86`) · RF-60 Salida "Métricas… para M08" |
| 4 | [F4] `GET /iot/monitoreo/historial/exportar` siempre 503 `M08_NO_DISPONIBLE` | M08 | DEP-M08 | **Dependencia, no bug.** RF-59 define el actor "Motor de Exportación **M08**". El 503 es un stub correcto. Tensión: RF-59 también describe el proceso de export dentro del propio RF → decisión de líderes (exportar en M03 o esperar M08). | `monitoreo_router.py:165-168` (raise `ServiceUnavailableError M08_NO_DISPONIBLE`) · cu04_gaps · RF-59 (actor M08) |
| 5 | [F6] `POST /iot/calidad/reevaluar` → 500 (`usuario_actual.email` no existe) | **M03-Dev** | **BUG-DEV** | **Bug real de backend.** El router pasa `usuario_actual.email`, pero `UsuarioActual` solo tiene `id_usuario/id_token/id_rol`. Lanza `AttributeError` → 500 en toda llamada autorizada (RBAC pasa; falla después). **Hay que corregirlo.** | `calidad_router.py:177` · `identity_access/infrastructure/dependencies.py:24-30` (dataclass sin `email`) · el use case `SolicitarReevaluacionUseCase` recibe `nombre_usuario: str` correctamente |
| 6 | [F4] Semáforo histórico llega GRIS (stub `UmbralHistoricoM09Adapter`) | **M09** | DEP-M09 | **Brecha de M09, no de M03.** RF-59 (Restr. 16) y RF-17 exigen umbrales **versionados** (`fecha_inicio_vigencia`, `fecha_fin_vigencia`, `version_umbral`). El modelo de M09 **no tiene versionado** (solo `es_activo` + `fecha_actualizacion`; editar sobrescribe en sitio). El stub de M03 es correcto hasta que M09 lo provea. | `umbral_historico_m09_adapter.py:21` (retorna `None`), inyectado en `monitoreo_router.py:222` · M09 `umbral_ambiental_model.py:39-52` (sin campos de vigencia) |
| 7 | [F5] Auto-vinculación siempre SIN_VINCULAR (stub `ActivoBiologicoStubAdapter`, M02) | M02 | DEP-M02 | **Dependencia, no bug.** RF-61 depende de M02 (activos biológicos, §8 fuera de alcance M03). Stub correcto. **Nota:** el commit reciente "Activos Biológicos… conexión front-end" sugiere que M02 ya existe → conviene cablear el adaptador real. | `activo_biologico_stub_adapter.py:18` (retorna `[]`), inyectado en `telemetria_router.py:54` y `vinculacion_router.py:27` · git log c1f6f79 |
| 8 | [F6] Parámetros de calidad fijos (stub `ParametrosCalidadStubAdapter`, M09) | **M09** | DEP-M09 | **Brecha / decisión de ownership.** RF-62 dice que k/M/N/umbral_drift son "configurables **desde M09**"; M09 no expone tabla ni endpoint (solo `frecuencia_muestreo` y `heartbeat`). Stub correcto interino. Decisión: agregarlos a M09 o mantenerlos como config propia de M03. | `parametros_calidad_stub_adapter.py:14-22` (k=3.0, M=5, N=20, umbral_drift=5.0…), inyectado en `telemetria_router.py:60`, `calidad_router.py:137,174` · M09 `configuracion_global_model.py:33-39` |
| 9 | [F1] No hay websockets/SSE → "tiempo real" es polling | M03-Dev | FUERA-RF | **Decisión de diseño válida.** RF-58 (Anexo A.6) modela niveles de degradación; el push es el Nivel 0 ideal pero el contrato **acepta polling** (Nivel 1/2/3). Restr. 10 pide lógica en backend y cliente simple. No hay mandato de WebSocket/SSE. SSE sería mejora opcional futura. | No hay endpoint websocket/SSE en `src/telemetry/` · solo `GET /iot/monitoreo/dashboard[/{id}]` (`monitoreo_router.py:51,85`) · RF-58 Anexo A.6 niveles |
| 10 | [F2] `GET /iot/alertas` filtra un solo `estado` (tabs multi-estado del prototipo) | M03-Dev | FUERA-RF | **No es falta de Dev.** RF-57 no exige filtro multi-estado; el `estado` único cumple el RF. Los tabs agrupados son decisión de UI. Mejora opcional: aceptar lista de estados (`estado IN`). | `alerta_router.py:108` (`estado: Optional[str]`) · `alerta_repository.py:152` (`== estado`) |
| 11 | [Varias] Selects de catálogo (sensor / infra / activo / especie) sin fuente | M09 + M02 | DEP-M09 / DEP-M02 | **Cross-module.** M09 ya expone **especie**, **infraestructura** (por finca) y **dispositivos**. **Sensor** solo por dispositivo (falta lista global — opcional en M09). **Activo biológico** es dominio de **M02**. M03 no es dueño de catálogos (§8: M09 los posee). | M09 `especie_router.py:66`, `infraestructura_router.py:68` (requiere `finca_id`), `dispositivo_iot_router.py:86` · sensores solo en `dispositivos-iot/{id}/sensores` |
| 12 | [Todas] Pruebas manuales E2E por fase | M03-Dev + AIOT | — | Tarea de validación, no de implementación. Coordinar por fase; en los flujos SPLIT (CU01/CU02) probar contra AIOT. | M03-SPLIT §3 |

---

## Lo único que Dev-M03 debe construir / corregir (exigido por el RF)

Todo lo demás de la tabla es dependencia externa, AIOT, o fuera del RF. Estas dos son las únicas
brechas atribuibles al backend M03. **✅ Ambas implementadas el 2026-07-27** — ver
`anotaciones/modulo_3/implementacion_dev_m03_rf60_rf62.md` y el `api_reference_m03…md` actualizado.

### A. Endpoint de mantenimiento — RF-60 (punto #2) — ✅ RESUELTO

- **Falta:** transición manual `EN_MANTENIMIENTO ↔ ACTIVO` por Ingeniero/Administrador.
- **Ya disponible:** enum `estado_dispositivo` con `EN_MANTENIMIENTO` (SPLIT §6); permiso RBAC
  (recurso 35, acción U) para Admin+Ing; la entidad `estado_dispositivo_iot.py` ya acepta la
  transición (`aplicar_transicion`); el job periódico ya la respeta (no la pisa).
- **Por hacer:** router `PATCH /iot/dispositivos/{id}/mantenimiento` (o equivalente) + caso de uso que
  aplique/limpie `EN_MANTENIMIENTO`, registre la transición en `historico_transiciones_dispositivos`
  y emita auditoría RF-63. Reutilizar el patrón de `EvaluarEstadoDispositivosUseCase` y de los routers
  con `require_permission(35, 3)`.
- **Aceptación:** RF-60 CA-7 (a mantenimiento por acción manual) y CA-8 (retorno a ACTIVO tras resolución).
- **Implementado:** `PATCH /iot/dispositivos/{id}/mantenimiento` (`require_permission(35, 3)`) +
  `AplicarMantenimientoDispositivoUseCase`. El histórico lo escribe el trigger de BD
  `trg_rf60_02_log_transicion_estado` (el use case no duplica); `causa_primaria` queda NULL
  (el enum no tiene valor de mantenimiento); se emite auditoría RF-63 con el nombre del actor.

### B. Fix del bug de reevaluar — RF-62 (punto #5) — ✅ RESUELTO

- **Bug:** `src/telemetry/infrastructure/routers/calidad_router.py:177` usa `usuario_actual.email`,
  atributo inexistente en `UsuarioActual` → `AttributeError` → 500 en cada llamada.
- **Por hacer (a decidir en implementación):** resolver el nombre/correo por `id_usuario` desde el
  módulo de identidad, o pasar un identificador ya disponible como `nombre_usuario`. El use case
  `SolicitarReevaluacionUseCase.execute(..., nombre_usuario: str)` ya es correcto; el fix es solo en el router.
- **Aceptación:** RF-62 FA-08 (re-evaluación registra `usuario_responsable` en RF-63).
- **Implementado:** el router resuelve el nombre real vía
  `SqlAlchemyUsuarioRepository(db).obtener_detalle(id_usuario)` → `f"{nombre} {apellidos}"`; el use
  case no cambió de firma. Ya no hay `AttributeError`/500.

---

## Bloqueos externos (no son falta de Dev-M03)

| Dueño | Bloqueo | Para desbloquear |
|---|---|---|
| **M09** | Umbrales sin versionado temporal → semáforo histórico GRIS (RF-59, punto #6) | Añadir `fecha_inicio_vigencia/fecha_fin_vigencia/version_umbral` al modelo de umbrales + endpoint "umbral vigente en timestamp"; luego cablear `UmbralHistoricoM09Adapter`. |
| **M09** | Sin parámetros de calidad configurables (RF-62, punto #8) | Tabla/endpoint de k/M/N/umbral_drift en M09, **o** decisión de que vivan en M03; luego reemplazar `ParametrosCalidadStubAdapter`. |
| **M09** | Sin catálogo global de sensores (punto #11) | Opcional: `GET /configuracion/sensores`. Especie/infra/dispositivos ya existen. |
| **M02** | Activos biológicos → vinculación SIN_VINCULAR (RF-61, punto #7) | Cablear `ActivoBiologicoStubAdapter` al M02 real (posiblemente ya disponible tras el commit reciente). |
| **M04** | Motor de inferencia (RF-56) | Reemplazar `MotorInferenciaStubAdapter` cuando exista M04. |
| **M08** | Exportación de historial (RF-59, punto #4) | Implementar export real o confirmar que se difiere a M08. |
| **AIOT** | RF-54 (buffer local) y RF-55 (procesamiento Edge) | Fuera de alcance Dev por completo (M03-SPLIT §8). Los paneles de "Fase 8" que leen buffer/edge crudo dependen de AIOT, no de nosotros. |

---

## Fuera del RF (decisión de producto, no falta de backend)

El prototipo pidió estas capacidades por encima de lo que exige el RF. No son deuda del backend; si se
quieren, son alcance nuevo a priorizar con líderes:

- **Tablero de flota de dispositivos con KPIs por estado** (Activos/Sin señal/Buffer/Inactivo/Mantenimiento):
  RF-60 lo define para M08; el dato existe en `estados_dispositivos_iot` pero no se agrega en un endpoint M03.
- **Filtro multi-estado en `GET /iot/alertas`** (tabs "Activas y en atención" / "Historial"): RF-57 solo
  exige filtro por un `estado`. Mejora opcional: aceptar `estado IN (...)`.
- **Tiempo real por WebSocket/SSE:** RF-58 acepta polling como degradación válida. SSE sería mejora futura.
- **Paneles humanos de lectura de ingesta/buffer/edge/pipeline (Fase 8):** no son endpoints humanos exigidos
  por el RF; buffer/edge son AIOT. Si se quisiera observabilidad, se podrían exponer las vistas DB existentes
  (`vw_m03_pipeline_inferencia`, `vw_m03_02_buffer_sincronizacion`) — opcional.

---

## Observación adicional (contrato AIOT↔Dev, a validar)

El Anexo A.3 / M03-SPLIT §4.2 define `POST /api/v1/iot/buffer/sync/confirm` (Dev→AIOT, ACK por
`buffer_sequence_id`). El backend implementa la sync de buffer como `POST /iot/telemetria/batch`.
Verificar si `batch` cubre ese contrato o si falta el endpoint nombrado. Es un contrato hacia AIOT
(no afecta al front-end), pero es un ítem Dev a confirmar con los líderes.

---

## Resumen de responsabilidad (para reportar)

- **Le faltó al backend Dev-M03 (2):** endpoint de mantenimiento RF-60 (#2) y bug de reevaluar RF-62 (#5). **✅ Ambas resueltas el 2026-07-27** (ver `implementacion_dev_m03_rf60_rf62.md`).
- **Es de M09 (backend, otro módulo):** umbrales versionados (#6) y parámetros de calidad (#8); opcional catálogo de sensores (#11).
- **Depende de otros módulos no implementados:** M02 vinculación (#7), M04 inferencia, M08 exportación (#4).
- **Es de AIOT (no Dev):** buffer/edge de la Fase 8 (#1) y todo RF-54/RF-55.
- **El prototipo pidió más de lo que exige el RF:** tablero de flota (#3), filtro multi-estado (#10), websocket/SSE (#9), paneles Fase 8 (#1).
