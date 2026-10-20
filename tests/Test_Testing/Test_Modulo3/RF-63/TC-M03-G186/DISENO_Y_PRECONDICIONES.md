# DISENO_Y_PRECONDICIONES — TC-M03-G185

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M03-G186 (TC-M03-354)
- **Módulo:** Módulo 3 — Telemetría, Infraestructura IoT y Bitácora de Auditoría
- **Requisito Funcional:** RF-63 (Bitácora de Auditoría IoT) / OWASP API Security Top 10 — API4: Unrestricted Resource Consumption
- **Nivel de Automatización:** Automatizado vía Newman / Postman Collection (v2.1)
- **Entorno:** Backend TEST (`https://api.inmero.co/back-sigab-test`) bajo Sandbox Transaccional (`ENABLE_TEST_SANDBOX=true`)

---

## 2. Diagnóstico Técnico del Endpoint de Exportación
- **Ruta de Código:** `src/telemetry/infrastructure/routers/auditoria_iot_router.py:84`
  - Método: `GET /iot/auditoria/exportar?formato={json|csv}`
  - Implementación interna: invoca `ExportarBitacoraIotUseCase`, el cual pagina internamente hasta un tope de `por_pagina=10000` pero no exige parámetros temporales obligatorios (`fecha_desde`, `fecha_hasta`).
  - **Ausencia de Rate Limiting:** No existe middleware de limitación de tasa (HTTP 429) por usuario o IP en este endpoint.
  - Esto representa un hallazgo documentado como `[HALLAZGO OWASP API4] Consumo irrestricto de recursos`.

---

## 3. Estrategia de Prueba y Subcasos
1. **Exportación sin Filtros Temporales (JSON):**
   - Evalúa si el backend impone límite, devuelve stream completo o falla.
   - En sandbox devuelve la bitácora activa (rango pequeño).
   - Aserción de no-degradación y registro de política con `console.log`.
2. **Exportación de Rango Amplio (CSV):**
   - Filtro amplio: `fecha_desde=2020-01-01T00:00:00Z&fecha_hasta=2026-10-18T23:59:59Z`.
   - Se valida generación de cabecera CSV sin error 500.
3. **Escenario de Volumen Masivo (>10,000 eventos):**
   - Marcado formalmente como `[BLOQUEADO]` por limitación de timeout del sandbox transaccional (180 s).
4. **Ráfaga de 5 Peticiones Consecutivas en <60 segundos:**
   - 5 requests consecutivos de exportación JSON/CSV con token de Administrador.
   - Se observa si el backend aplica throttling (429) o responde 200 en todas.
   - En ambos casos se registra la métrica de tiempo y código recibido.
5. **Verificación de No-Degradación Posterior:**
   - `GET /iot/auditoria` inmediato tras la ráfaga.
   - Se exige HTTP 200 con tiempo de respuesta <2000 ms.

---

## 4. Teardown y Limpieza
- Pre-request genera `run_id = "test-" + {{$guid}}`.
- Último request: `DELETE /test-control/runs/{{run_id}}` (200 OK "Rollback exitoso").
- Duración total estimada: ~10 segundos.
