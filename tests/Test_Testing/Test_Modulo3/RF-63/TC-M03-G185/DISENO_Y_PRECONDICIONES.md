# DISENO_Y_PRECONDICIONES — TC-M03-G185

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M03-G185 (TC-M03-353)
- **Módulo:** Módulo 3 — Telemetría, Infraestructura IoT y Bitácora de Auditoría
- **Requisito Funcional:** RF-63 (Bitácora de Auditoría IoT) / OWASP API Security Top 10 — API1: Broken Object Level Authorization (BOLA)
- **Nivel de Automatización:** Automatizado vía Newman / Postman Collection (v2.1)
- **Entorno:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional (`ENABLE_TEST_SANDBOX=true`)

---

## 2. Diagnóstico Técnico del Modelo y Endpoints
- **Modelo de Auditoría:** `BitacoraAuditoriaIotModel` (`src/telemetry/infrastructure/models/bitacora_auditoria_iot_model.py:14`).
  - Columnas: `id_evento`, `timestamp_evento`, `tipo_evento`, `severidad_log`, `clasificacion_registro`, `id_usuario`, `entidad_afectada_id`, `datos_antes`, `datos_despues`, `firma_hmac`, `ip_origen`.
  - **Ausencia de Atributo de Finca:** El modelo NO posee columna `id_finca`. Por ende, el aislamiento cross-farm queda formalmente marcado como `[BLOQUEADO]` por inexistencia del atributo en el esquema de datos.
- **Caso de Uso:** `ConsultarBitacoraIotUseCase.get(id_evento)` (`src/telemetry/application/use_cases/bitacora_iot/consultar_evento_auditoria_use_case.py`):
  - No aplica filtros por rol del llamador sobre la clasificación (`TECNICO`, `NIC41`). Tanto CONTADOR consultando un evento técnico como INGENIERO consultando un evento NIC41 reciben respuesta HTTP 200 en lugar del esperado 403/404.
  - Esto constituye un hallazgo de autorización documentado como `[DEFECTO BOLA]`.

---

## 3. Subcasos Evaluados
1. **Setup por API (Zero DML):**
   - Transición de mantenimiento manual vía `POST /iot/mantenimiento/sensores/{id_sensor}/transicion` para generar evento con clasificación `TECNICO`.
   - Generación de evento con clasificación `NIC41` o alternativo mediante API real dentro del sandbox.
2. **Subcaso (a): CONTADOR accede a Evento TECNICO:**
   - Endpoint: `GET /iot/auditoria/{id_evento_tecnico}` con token de Contador.
   - Esperado teórico: 403/404.
   - Observado: 200 OK -> Registrado como `[DEFECTO BOLA]`.
3. **Subcaso (b): INGENIERO DE CAMPO accede a Evento NIC41:**
   - Endpoint: `GET /iot/auditoria/{id_evento_rf53}` con token de Ingeniero.
   - Esperado teórico: 403/404.
   - Observado: 200 OK -> Registrado como `[DEFECTO BOLA]`.
4. **Subcaso (c): Filtrado por entidad fuera de alcance:**
   - Endpoint: `GET /iot/auditoria?entidad_afectada_id={random_uuid}`.
   - Se valida lista vacía `[]` con HTTP 200.
5. **Subcaso (d): Enumeración de UUIDs Ficticios:**
   - 10 UUIDs v4 aleatorios consultados por Contador e Ingeniero.
   - Aserción de HTTP 404 uniforme sin divulgar existencia de recursos.
6. **Subcaso (e): ADMINISTRADOR Acceso Total:**
   - Validación de acceso pleno a ambos eventos con HTTP 200.
7. **Aislamiento Entre Fincas:**
   - Marcado formalmente como `[BLOQUEADO]` por limitación del modelo de datos de RF-63.

---

## 4. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~12 segundos.
