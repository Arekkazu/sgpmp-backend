# TC-M03-G166 — Informe de Cierre (Reintento 1)

**Fecha:** 2026-10-28 | **Ambiente:** TEST | **Veredicto:** RECHAZADO

## 1. Resumen ejecutivo
6 intentos de reintento 1 ejecutados el 2026-10-28. Todos bloqueados por
INC-M03-G166-LATENCY (CRÍTICA-BLOQUEANTE). El defecto es del producto
(pool_size=5 + triggers sin aislamiento por sensor), no del ambiente.
En producción real, el mismo defecto colapsaría bajo carga concurrente.

## 2. Historial de 6 intentos
| # | Timeout ingesta | Timeout helper | Resultado |
|---|---|---|---|
| 1 | 15s | 15s | ReadTimeout ingesta |
| 2 | 45s | 15s | ReadTimeout ingesta |
| 3 | 45s | 15s | Ingesta OK, ReadTimeout helper:103 |
| 4 | 45s | 45s | ReadTimeout ingesta, 188.22s > 180s sandbox |
| 5 | — | — | Diagnóstico Fase B: 41/41 ingestas en 40.52s (aislado) |
| 6 | 45s | 45s | ReadTimeout ingesta (mismo defecto) |

## 3. Evidencia SQL (los 6 intentos)
Pre-check y post-check: 0 idle-in-transaction, 0 locks no otorgados,
10 conexiones totales (<12). No hay huérfanos del sandbox. El bloqueo
es server-side por triggers.

## 4. Diagnóstico profundo (absorbido)
- H1 (pool agotado por huérfanos): DESCARTADA — SQL limpio.
- H2 (trigger serializa escrituras): CONFIRMADA — triggers
  trg_aux_01_telemetria_contacto_dispositivo y
  trg_rf58_01_cache_estado_sensor hacen UPDATE sobre misma fila.
- H3 (use case comitea en sandbox): DESCARTADA — savepoint reutilizable.
- H4 (locks por competencia): CONFIRMADA — falla en medio de la corrida,
  no al inicio, con pre-check limpio.
- H5 (DDL activo): DESCARTADA — 0 migraciones.

## 5. Veredicto
RECHAZADO. El defecto impide la operación del sistema bajo carga
concurrente. No es bloqueo de ambiente. Afecta producción.

## 6. Acciones para Dev (detalle en INC-M03-G166-LATENCY.md)
1. pool_size=15, max_overflow=10, pool_timeout=30.
2. IDLE_TIMEOUT_SECONDS=60.
3. Advisory lock por id_sensor/id_dispositivo en los 2 triggers.

## 7. Inocuidad
Teardown 200 "Rollback exitoso" en los 6 intentos. 0 contaminación.

## 8. Próximo paso
Reintento 2 (V3) cuando Dev despliegue los 3 fixes y QA coordine ventana
exclusiva (sin otros testers sobre el mismo sensor).
