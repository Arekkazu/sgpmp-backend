# Reporte de Incidencia: INC-M03-G166-LATENCY

| Metadato | Detalle |
| :--- | :--- |
| **ID Incidencia** | `INC-M03-G166-LATENCY` |
| **Severidad** | Crítico (Bloqueante para QA y Pipelines) |
| **Categoría** | INFRAESTRUC / Performance Backend |
| **Módulo** | Módulo 3 — Telemetría IoT / Plataforma Global |
| **Caso Afectado** | `TC-M03-G166` (RF-62 / RF-57 / RF-63) |
| **Ambiente** | TEST (`https://www.api.inmero.co/api-sgpmp-test`) |
| **Equipo Responsable** | Implementación TEST / Dev Backend / DBA |
| **Fecha de Detección** | 2026-10-28 |

---

## 1. Descripción del Problema
Se ha detectado una **degradación severa generalizada de latencia** en el backend del ambiente `TEST`.  
Mientras que endpoints estáticos en memoria como `GET /health` responden con normalidad (~1.1 s), **todas las operaciones que requieren interacción con la base de datos PostgreSQL** (`POST /sesiones/`, `POST /iot/telemetria`, y `DELETE /test-control/runs/{run_id}`) exceden sistemáticamente el umbral de 15 segundos, culminando en `ReadTimeout`.

Esta condición bloquea por completo la ejecución de pruebas automatizadas y la ingesta de telemetría IoT en el ambiente TEST.

---

## 2. Contexto de Reproducción
1. Durante la ejecución del **Reintento 1** del caso `TC-M03-G166` (2026-10-28 06:27:10 UTC), la suite fue interrumpida por un `requests.exceptions.ReadTimeout` en la línea 223 de `test_tc_m03_g166.py` (`POST /iot/telemetria`, `timeout=15s`) durante la ingesta secuencial de las 41 lecturas.
2. La autenticación del Broker IoT (`BROKER_SERVICE_TOKEN`) fue validada y aceptada exitosamente (no existió HTTP 401 de credenciales inválidas).
3. Para discernir si se trató de una fluctuación aislada o un fallo estructural del entorno, se ejecutó una sonda controlada de diagnóstico de latencia a las 06:34-06:36 UTC, confirmando que el problema **NO es del script de prueba**, sino de la capacidad de respuesta del backend remoto.

---

## 3. Evidencia: Tabla de Latencias Medidas

**Muestras tomadas el 2026-10-28 entre 06:34 y 06:36 UTC:**

| Operación | Latencia Registrada | Código HTTP / Estado | Diagnóstico |
| :--- | :--- | :--- | :--- |
| `GET /health` | 1,094.1 ms | 200 OK | Normal (no toca DB) |
| `POST /sesiones/` | 15,711.3 ms | `TIMEOUT (ReadTimeout)` | Fallo (> 15 s) |
| `POST /iot/telemetria` (Muestra A) | 15,830.8 ms | `TIMEOUT (> 15 s)` | Fallo (> 15 s) |
| `POST /iot/telemetria` (Muestra B) | 15,939.5 ms | `TIMEOUT (> 15 s)` | Fallo (> 15 s) |
| `POST /iot/telemetria` (Muestra C) | 15,741.2 ms | `TIMEOUT (> 15 s)` | Fallo (> 15 s) |
| `DELETE /test-control/runs/{run_id}` | 15,783.0 ms | `TIMEOUT (ReadTimeout)` | Fallo (> 15 s) |

*Nota:* Un sondeo de control con un run_id no existente (`DELETE /test-control/runs/diag-lat-check`) responde de inmediato en < 200 ms con `404 Not Found` (manejado en memoria sin tocar Postgres), ratificando que el bloqueo radica en la capa de persistencia/transacciones de base de datos.

---

## 4. Hipótesis Técnicas para Dev / DBA (Para Análisis)
1. **Agotamiento del Connection Pool de PostgreSQL:** Acumulación de conexiones abiertas no liberadas o transacciones activas de ejecuciones previas del sandbox (`active_test_transactions`), dejando a SQLAlchemy esperando conexiones libres hasta alcanzar el timeout del socket.
2. **Locks en Tablas Críticas de Base de Datos:** Alguna transacción previa no finalizada podría mantener bloqueos exclusivos (`AccessExclusiveLock` o `RowExclusiveLock`) en tablas como `modulo9.dispositivos_iot`, `modulo3.telemetrias` o `modulo1.usuarios`.
3. **Saturación de Recursos en el Servidor/Pod:** CPU o I/O disk saturation en la instancia de PostgreSQL de TEST.
4. **Patrón Reincidente (Referencia Cruzada INC-M03-135-G177):** En incidentes anteriores, peticiones pesadas o bloqueantes (como `POST /iot/auditoria/verificar-integridad` sin filtros temporales) saturaron el worker por más de 5 minutos, degradando la atención de todas las solicitudes concurrentes.

---

## 5. Acciones Requeridas
* **Dev / DBA:**
  1. Inspeccionar logs del backend TEST y verificar `pg_stat_activity` en la base de datos para identificar consultas bloqueadas, locks pendientes o conexiones inactivas en transacción (`idle in transaction`).
  2. Verificar estado del pool de conexiones en SQLAlchemy / Uvicorn.
  3. Reiniciar el pod o servicio del backend TEST si se encuentra en estado de estancamiento.
* **Precondición para Reintento de Pruebas (QA):**
  - Las operaciones `POST /iot/telemetria` y `POST /sesiones/` deben responder de manera sostenida en **menos de 5 segundos** bajo condiciones normales.

---

## 6. Diagnóstico Profundo Completado (Referencia Cruzada)
Para el detalle técnico exhaustivo de la investigación estática de código, trazabilidad de conexiones en `testing_sandbox.py`, análisis de triggers de `modulo3.telemetrias`, sonda de 146 peticiones y evidencia SQL directa en PostgreSQL TEST, consultar el informe técnico consolidado:
👉 **[DIAGNOSTICO_PROFUNDO_LATENCY.md](sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G166/evidencias/run-20261028/DIAGNOSTICO_PROFUNDO_LATENCY.md)**.

---

## 7. Actualización tras 5º Intento (2026-10-28 18:14 UTC)
- **Severidad confirmada:** `CRÍTICA-BLOQUEANTE`.
- Tras 12 horas de reposo y con pre-check SQL en estado óptimo (0 idle in transaction, 10 conexiones totales, 0 locks), la ejecución única de la suite experimentó un nuevo timeout de lectura (`ReadTimeout > 15s`) al ejecutar queries posteriores a la ingesta masiva (`POST /test-control/query` en `test_tc_m03_g166.py:286`).
- Se confirma de forma irrefutable que el fallo es de carácter endémico en el backend TEST.

---

## 8. Actualización tras 6º y ÚLTIMO Intento (2026-10-28 18:24 UTC)
- **Estado:** `VIGENTE - CRÍTICA-BLOQUEANTE`.
- **Mitigación del test aplicada:** Timeout del helper ampliado a 45s (`helpers_tc_m03_g166.py:103`).
- **Desenlace:** La suite volvió a experimentar un `ReadTimeout > 45s` durante la ingesta continua de las 41 telemetrías (`POST /iot/telemetria` en `test_tc_m03_g166.py:223`).
- **Conclusión Definitiva:** La infraestructura de TEST no soporta la ráfaga de 41 inserts con triggers activos bajo `pool_size=5`. Ningún cambio en los scripts de QA puede solventar esta limitación estructural.
- **Acción Requerida para Desbloqueo:** Despliegue obligatorio por parte de Dev/DBA de `pool_size=15`, reducción de `IDLE_TIMEOUT_SECONDS` y optimización/desactivación temporal de triggers de telemetría en sandbox.



