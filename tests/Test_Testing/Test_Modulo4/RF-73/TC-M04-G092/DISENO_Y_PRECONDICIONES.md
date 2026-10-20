# DISENO_Y_PRECONDICIONES — TC-M04-G092

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G092 (TC-M04-285, TC-M04-286, TC-M04-287)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Trazabilidad Causal con correlacion_id)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS (SOLO DISEÑO Y CONSTRUCCIÓN)
- **Estado Global:** [PENDIENTE_DEV] (Eslabones productores de eventos en M04 y conectores transversales M03/M06 en desarrollo)
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico y Cadena Causal de Eventos

| Subcaso | Flujo / Operación | Validación de Auditoría | Estado de Productores | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-285** | Inferencia (RF-66) -> Alerta (RF-57) -> Retroalimentación (RF-72) | 3 eventos comparten el mismo `correlacion_id` y orden cronológico ASC | Productores REST en desarrollo (`POST /prediccion/auditoria/eventos`) | [PENDIENTE_DEV] |
| **TC-M04-286** | Cadena completa RF-56 -> RF-66 -> RF-57 -> RF-72 | Reconstrucción causal mediante `id_referencia` enlazando al evento anterior | Generación de enlaces causales en desarrollo | [PENDIENTE_DEV] |
| **TC-M04-287** | Correlación multisistema (M03 + M04 + M06) | Mismo `correlacion_id` propagado entre telemetría IoT, predicción y contabilidad | Conexión transversal multisistema en desarrollo | [PENDIENTE_DEV] |

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-285** | Productores M04 (`POST /prediccion/auditoria/eventos`) | Emisión automática de eventos de auditoría con `correlacion_id` inyectado en la cabecera / payload | Equipo Backend Core / Módulo 4 |
| **TC-M04-285** | Filtro query `correlacion_id` en `GET /prediccion/auditoria` | `GET /prediccion/auditoria?correlacion_id={uuid}` retornando únicamente eventos de la correlación | Equipo Backend Core / Módulo 4 |
| **TC-M04-286** | Generador de enlaces causales (`id_referencia`) | Cada evento emitido debe propagar el UUID del evento predecesor en `id_referencia` | Equipo Backend Core / Módulo 4 |
| **TC-M04-287** | Bus transversal o endpoints de consulta federada M03/M06 | Inyección y propagación de `X-Correlation-Id` en solicitudes que cruzan M03 (RF-63), M04 (RF-73) y M06 (RF-94) | Equipos M03, M04 y M06 / Arquitectura |

### Ajustes Menores al Publicarse los Productores Reales:
- Los scripts ya integran el pipeline completo: pre-request inyecta un `correlacion_id` UUID dinámico compartido.
- Si los productores aún no existen o retornan 404/405, las aserciones registran trazas `[PENDIENTE_DEV]` informando el estado sin generar falsos positivos. En cuanto los endpoints productores se activen, la cadena se valida automáticamente.

---

## 4. Limitaciones Técnicas y Supuestos

- **Propagación de correlacion_id:**
  - El campo `correlacion_id` está tipificado como `UUID` tanto en la base de datos PostgreSQL (`modulo4.eventos_auditoria_m04`) como en el esquema Pydantic `EventoAuditoriaM04Response`.
  - El script genera un UUID v4 estricto para garantizar conformidad con el tipo de datos del backend.
- **Cero Simulación con DML:**
  - En estricto cumplimiento de las directrices arquitectónicas, no se insertan registros sintéticos en PostgreSQL para forzar la cadena de correlación. Todo el flujo se diseña a través de las interfaces REST oficiales.

---

## 5. Estrategia de Sandbox y Teardown
- Generación de `run_id` aleatorio en pre-request de colección (`test-{{$guid}}`).
- Inyección de cabeceras de aislamiento `X-Test-Run-Id` y `X-Sandbox-Secret`.
- Teardown con `DELETE /test-control/runs/{{run_id}}` (200 OK con `Rollback exitoso`).
- Cero escrituras directas SQL en base de datos.
