# TC-M03-117 — reevaluación 2026-10-25

No sustituye `TC-M03-117_resultado.md` previo (tramo ERROR_CONFIGURACION).

## RF

RF-56. Relación evento–paquete; GET por id; PostgreSQL.

## Runner

PASSED: evento NORMAL, enlace desviación, ERROR_CONFIGURACION sin paquete, timestamps, buffer expirado, copia severidad.  
**FAILED** EXIT=1: `test_tc_m03_117_repos_aislados_entre_instancias` — `assert 1 != 1` en IDs de **dos dobles** que reinician `_seq` en 1. Defecto del **test/doble**, no de M04 ni de SQL.  
SKIPPED: `test_tc_m03_117_consulta_http_por_id_paquete` — no hay GET `/inferencia/paquetes/{id}`.

## Estado funcional GET/SQL

**BLOQUEADO** (INC-M03-116-G59). Memoria ≠ PostgreSQL.

## Evidencias

`evidencias/reeval-2026-10-25/` (incluye el FAILED).
