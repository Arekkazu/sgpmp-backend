# DISENO_Y_PRECONDICIONES — TC-M04-G088

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G088 (TC-M04-270, TC-M04-271, TC-M04-272)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Control de Tamaño de Payloads)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS
- **Estado Global:** [PENDIENTE_DEV] (Lógica de dominio implementada en repositorio SQLAlchemy; pendiente de exposición en router REST)
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico y Regla de Negocio de Truncamiento

| Subcaso | Tamaño de Payload | Comportamiento Esperado | Endpoint Real en Backend | Estado Técnico |
|---|---|---|---|---|
| **TC-M04-270** | 65,536 bytes (64 KB exacto) | Persistencia completa, HTTP 201/200, `es_payload_truncado=false`, Hash SHA-256 (64 hex) completo | `POST /prediccion/auditoria/eventos` (no expuesto en FastAPI router) | [PENDIENTE_DEV] |
| **TC-M04-271** | 65,537 bytes (64 KB + 1 B) | **NO rechazar por 4XX**, truncar a 64 KB, HTTP 201/200, `es_payload_truncado=true`, Hash sobre payload truncado | `POST /prediccion/auditoria/eventos` (no expuesto en FastAPI router) | [PENDIENTE_DEV] |
| **TC-M04-272** | 204,800 bytes (200 KB) | **NO rechazar por 4XX**, truncar a 64 KB, HTTP 201/200, `es_payload_truncado=true`, Hash sobre payload truncado | `POST /prediccion/auditoria/eventos` (no expuesto en FastAPI router) | [PENDIENTE_DEV] |

### Análisis de la Implementación Existente en Dominio/Infraestructura:
En el repositorio de infraestructura `src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py` (líneas 113–128) ya existe implementada la lógica:
- `_PAYLOAD_MAX_BYTES = 64 * 1024` (65,536 bytes).
- Serialización a UTF-8: `payload_json = json.dumps(evento.payload_evento, ensure_ascii=False)`.
- Si `len(payload_bytes) > self._PAYLOAD_MAX_BYTES`:
  - Se trunca a `self._PAYLOAD_MAX_BYTES`.
  - Se marca `es_payload_truncado = True`.
  - Se fuerza `severidad_evento = "WARNING"`.
- Se calcula SHA-256 sobre el contenido truncado y se almacena en `hash_evento`.
- **Conclusión de QA:** El dominio cumple fielmente el RF-73; únicamente falta el enrutamiento FastAPI en `src/prediction/infrastructure/routers/auditoria_m04_router.py`.

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-270** | `POST /prediccion/auditoria/eventos` | Body con payload de 65,536 B -> HTTP 201 Created o 200 OK, `es_payload_truncado: false`, `hash_evento: [hex-64]` | Equipo Backend Core / Módulo 4 |
| **TC-M04-271** | `POST /prediccion/auditoria/eventos` | Body con payload de 65,537 B -> HTTP 201 Created o 200 OK (NO 4XX), `es_payload_truncado: true`, `severidad_evento: "WARNING"` | Equipo Backend Core / Módulo 4 |
| **TC-M04-272** | `POST /prediccion/auditoria/eventos` | Body con payload de 204,800 B -> HTTP 201 Created o 200 OK (NO 4XX), `es_payload_truncado: true`, `severidad_evento: "WARNING"` | Equipo Backend Core / Módulo 4 |

### Ajustes Menores al Publicarse el Endpoint Real:
- El script ya contiene la generación matemática determinista de los payloads UTF-8:
  - TC-270: `{"data": "A" * 65525}` (longitud serializada total: 65,536 bytes).
  - TC-271: `{"data": "A" * 65526}` (longitud serializada total: 65,537 bytes).
  - TC-272: `{"data": "A" * 204789}` (longitud serializada total: 204,800 bytes).
- Si el endpoint responde 404/405, emite console.log con `[PENDIENTE_DEV]`. Al exponerse el endpoint, las aserciones validan el código de éxito (200/201), el flag de truncamiento y el regex del hash SHA-256 (`/^[a-f0-9]{64}$/`).

---

## 4. Limitaciones Técnicas y Defectos Conocidos Previstos

- **[LIMITACION API] Verificación de Log Técnico WARNING:**
  - El caso especifica emisión de log técnico con severidad WARNING al truncar el payload.
  - Al no haber endpoint de inspección de logs HTTP en vivo, se documenta mediante traza `[LIMITACION API]`.
- **[DEFECTO CONOCIDO] Rechazo HTTP 4XX por Tamaño:**
  - Si una capa intermedia (como un middleware HTTP o proxy inverso) rechaza la petición con 413 Payload Too Large o 422 en lugar de permitir que la capa de aplicación trunque el payload a 64 KB, el test asertará fallo explícito prefijado con `[DEFECTO CONOCIDO]`.

---

## 5. Estrategia de Sandbox y Teardown
- Generación de `run_id` aleatorio en pre-request de la colección.
- Inyección de cabeceras de aislamiento `X-Test-Run-Id` y `X-Sandbox-Secret`.
- Teardown garantizado vía `DELETE /test-control/runs/{{run_id}}` (200 OK con `Rollback exitoso`).
- Cero escrituras directas SQL en base de datos.
