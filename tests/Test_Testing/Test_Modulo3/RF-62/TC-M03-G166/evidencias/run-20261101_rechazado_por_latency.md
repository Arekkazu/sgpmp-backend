# Informe de Ejecución Reintento 2: Rechazado por Latencia — TC-M03-G166

**Fecha:** 2026-11-01  
**Caso:** TC-M03-G166 (RF-62 v2.0 / RF-57 / RF-63)  
**Ambiente:** TEST (`https://www.api.inmero.co/api-sgpmp-test`)  
**Veredicto Oficial:** **RECHAZADO_POR_LATENCY**  
**INC Asociado:** `INC-M03-G166-LATENCY` (Defecto Crítico de Infraestructura / Backend)  

---

## 1. Resumen Ejecutivo
Se ejecutó el **Reintento 2** de `TC-M03-G166` con aceptación explícita de riesgo por `LATENCY` abierto.
La ejecución colapsó en la fixture de inicialización `contexto_g166` durante la ingesta secuencial de 41 lecturas de telemetría a través de `POST /iot/telemetria`, arrojando `requests.exceptions.ReadTimeout` tras agotar el timeout elevado de 45 segundos.

---

## 2. Métricas de Ejecución
- **Duración total:** 197.49 segundos (~3 min 17s).
- **Total testcases:** 106
- **Passed:** 0
- **Failed / Error en setup:** 101
- **XFailed (justificados RF-57):** 5 (`test_efectos_rf57_alerta_tecnica_emitida[5, 9, 10, 19, 20]`)
- **Skipped:** 0
- **Veredicto consolidado:** RECHAZADO

---

## 3. Detalle Técnico del Fallo
- **Llamada afectada:** `POST /iot/telemetria`
- **Ubicación en código:** `test_tc_m03_g166.py:223` dentro de `contexto_g166`.
- **Excepción capturada:**
  ```text
  TimeoutError: The read operation timed out
  requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='www.api.inmero.co', port=443): Read timed out. (read timeout=45)
  ```
- **Causa raíz confirmada:**
  1. `pool_size` en `src/shared/database.py:60-63` permanece en el valor por defecto de SQLAlchemy (`5`).
  2. Los triggers `trg_aux_01_telemetria_contacto_dispositivo` y `trg_rf58_01_cache_estado_sensor` sobre `modulo3.telemetrias` bloquean concurrentemente las mismas filas sin aislamiento por advisory locks, agotando las conexiones y congelando la respuesta del servidor más allá de 45s.

---

## 4. Subcasos Afectados
- **TC-M03-309** (R=4, R=5, R=9): TIMEOUT (bloqueado en fixture setup).
- **TC-M03-310** (R=10, R=19): TIMEOUT (bloqueado en fixture setup).
- **TC-M03-311** (R=20): TIMEOUT (bloqueado en fixture setup).
- **RF-57 xfail**: 5 registrados como XFAIL.

---

## 5. Garantía Zero-Pollution
Al capturar la excepción en `test_tc_m03_g166.py:321-325`, el bloque `except` emitió de inmediato `DELETE test-control/runs/{run_id}` para abortar y revertir la transacción del sandbox, garantizando cero contaminación en la base de datos de test.

---

## 6. Acciones Requeridas para Desbloqueo (Dev / DevOps)
No se debe reintentar hasta que Desarrollo aplique el paquete de remediación documentado en `INC-M03-G166-LATENCY.md`:
1. `src/shared/database.py`: configurar `pool_size=15`, `max_overflow=10`, `pool_timeout=30`, `IDLE_TIMEOUT_SECONDS=60`.
2. Advisory lock por `id_sensor`/`id_dispositivo` en los triggers de telemetría.

