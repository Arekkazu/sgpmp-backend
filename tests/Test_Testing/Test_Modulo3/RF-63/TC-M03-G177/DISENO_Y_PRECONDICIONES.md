# TC-M03-G177: Consulta Básica y Detalle de Bitácora de Auditoría IoT (RF-63)

## 1. Identificación y Objetivos
- **Caso Maestro:** TC-M03-G177
- **Requisito Funcional:** RF-63 (Bitácora de Auditoría IoT y Trazabilidad de Decisiones Automatizadas)
- **Subcasos Evaluados:**
  - **TC-M03-336:** Listado sin filtros, validación de paginación (`pagina=1`, `por_pagina=50` por defecto, máximo 200, 422 en >200), estructura completa de 11 campos base RF-10 + 8 campos extensión IoT + `timestamp_registro`, invariante `modulo === 'M03'`, no exposición de `componente_origen`.
  - **TC-M03-337:** Detalle de evento puntual por `id_evento` (UUID), integridad del payload, validación de formato SHA-256 en `hash_integridad` (64 hex), verificación de integridad de bitácora en backend (`POST /iot/auditoria/verificar-integridad`), respuestas 404 (UUID inexistente) y 422 (UUID malformado).
- **Herramienta de Ejecución:** Newman + reporter htmlextra.
- **Entorno de Ejecución:** Sandbox transaccional (`ENABLE_TEST_SANDBOX=true`, rollback automático con `DELETE /test-control/runs/{{run_id}}`).

---

## 2. Diagnóstico Técnico y Verificación de Código

| Elemento | Ubicación en Código / Estado | Detalle |
|---|---|---|
| Router Auditoría IoT | [auditoria_iot_router.py:38](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/auditoria_iot_router.py#L38) | Montado bajo `/iot/auditoria` |
| `GET /iot/auditoria` | [auditoria_iot_router.py:49](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/auditoria_iot_router.py#L49) | Listar con paginación y filtros; RBAC `(39, 2)` |
| `GET /iot/auditoria/{id_evento}` | [auditoria_iot_router.py:146](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/auditoria_iot_router.py#L146) | Detalle por UUID; RBAC `(39, 2)` |
| `POST /iot/auditoria/verificar-integridad` | [auditoria_iot_router.py:165](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/auditoria_iot_router.py#L165) | Re-calcula SHA-256 de todos los registros; RBAC `(39, 5)` |
| Schema EventoAuditoria | [bitacora_auditoria_iot_schema.py:10](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/schema/bitacora_auditoria_iot_schema.py#L10) | `EventoAuditoriaIotSchema` con 20 campos totales |
| Repositorio SQL | [bitacora_auditoria_iot_repository.py:21](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/repositories/bitacora_auditoria_iot_repository.py#L21) | Persistencia en `modulo3.bitacora_auditoria_iot` |

---

## 3. Matriz de Campos Expuestos vs. Contrato

El esquema `EventoAuditoriaIotSchema` expone exactamente los siguientes campos:

### 11 Campos Base RF-10
1. `id_evento` (UUID)
2. `id_usuario` (Optional[int]) — nulo en eventos automáticos del sistema
3. `nombre_usuario` (Optional[str])
4. `tipo_evento` (str)
5. `modulo` (str) — siempre `"M03"` en esta vista técnica
6. `descripcion` (Optional[str])
7. `resultado` (str)
8. `direccion_ip` (Optional[str])
9. `user_agent` (Optional[str])
10. `id_sesion` (Optional[UUID])
11. `fecha_hora` (datetime ISO-8601 UTC) — `[INCONSISTENCIA CONTRATO]`: equivale a `timestamp_evento` documentado en el caso de prueba pero no expuesto con ese nombre en Swagger.

### 8 Campos Extensión IoT
12. `accion_detallada` (Optional[dict]) — payload JSON
13. `entidad_afectada_tipo` (Optional[str])
14. `entidad_afectada_id` (Optional[str])
15. `severidad_log` (str: `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
16. `hash_integridad` (str: SHA-256 de 64 caracteres hex)
17. `clasificacion_registro` (str: `NIC41` o `TECNICO`)
18. `retencion_aplicable` (int: 5 años para NIC41, 1 año para TECNICO)
19. `registro_incompleto` (bool: flag para registros ambiguos o degradados)

### Metadato de Persistencia
20. `timestamp_registro` (Optional[datetime])

### Invariantes de Seguridad y Diseño
- `componente_origen` **NO** se expone en ninguna respuesta HTTP (`EventoAuditoriaIotSchema` omite intencionalmente este campo interno de enrutamiento).

---

## 4. Estrategia de Generación de Eventos por API (Regla CERO DML)
Dado que la bitácora RF-63 es de solo lectura y está prohibida toda escritura directa vía SQL `/test-control/query`, los eventos se generan orgánicamente a través de endpoints reales:
1. `POST /configuracion/fincas` -> `POST /infraestructuras` -> `POST /dispositivos-iot` -> `POST /sensores`: Creación de catálogo sintético dentro del sandbox.
2. `POST /iot/telemetria/batch`: Ingesta de 20 lecturas pasadas espaciadas 10 min (600 s) entre sí. El motor de ingesta dispara automáticamente `EvaluarCalidadTelemetriaUseCase`, generando eventos de auditoría `EVALUACION_CALIDAD_COMPLETADA` (clasificación `NIC41`, retención 5 años).
3. `PATCH /iot/dispositivos/{id}/mantenimiento`: Transición manual a estado `MANTENIMIENTO`, emitiendo `TRANSICION_MANTENIMIENTO_MANUAL` (clasificación `TECNICO`, retención 1 año).
4. `POST /iot/calidad/reevaluar`: Solicitud explícita de reevaluación por rango de fechas, emitiendo `REEVALUACION_CALIDAD_SOLICITADA` (clasificación `NIC41`, retención 5 años).

---

## 5. Hallazgos, Discrepancias y Limitaciones Registradas
1. `[INCONSISTENCIA CONTRATO]`: El caso de prueba especifica `timestamp_evento`, pero el contrato Swagger y el schema Pydantic exponen `fecha_hora`. La suite aserta sobre `fecha_hora`.
2. `[LIMITACION API / AUDITORIA]`: La función interna `_calcular_hash` incluye `componente_origen` en el cálculo de SHA-256, pero dicho campo no es devuelto al cliente HTTP en `EventoAuditoriaIotSchema`. Por ende, un cliente que recalcule SHA-256 usando únicamente los campos recibidos obtendrá un hash divergente a menos que conozca `componente_origen`. La verificación canónica de integridad se valida mediante `POST /iot/auditoria/verificar-integridad` y validando que el hash tenga 64 hex (`/^[0-9a-f]{64}$/`).
3. `[LIMITACION API]`: El endpoint `GET /iot/auditoria` no expone parámetros de ordenamiento (`orden=asc|desc`); el repositorio aplica orden fijo por `fecha_hora.desc()`.
