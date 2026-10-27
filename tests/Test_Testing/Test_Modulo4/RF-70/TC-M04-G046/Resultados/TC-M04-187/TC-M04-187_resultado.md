# TC-M04-187 — Resultado de ejecución

Fecha: 2026-10-25. Rama `laura`. Responsable: Laura Lopez.  
Grupo: **TC-M04-G046**. RF-70 / CU-06. Capa exigida: **API + Edge**.

Script interno: `test_tc_m04_018_concurrencia_un_proceso_por_dispositivo` (SKIP). ID de matriz: **TC-M04-187**.

---

## 1. Identificador original

**TC-M04-187** — Controlar actualizaciones OTA concurrentes (un proceso por dispositivo).

## 2. Criterios

Dos solicitudes OTA al mismo dispositivo: exclusión; segunda bloqueada/rechazada según contrato; sin duplicados; concurrencia **real** (no dos GET/POST secuenciales); integridad y auditoría; otros dispositivos no bloqueados globalmente.

## 3. Precondiciones

Sin endpoint de inicio, sin lock en ORM (`DespliegueOtaModel`: solo PK, sin índice único por dispositivo+EN_PROCESO), sin Edge, sin API local.

## 4. Comandos

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/Test_Testing/Test_Modulo4/RF-70/TC-M04-G046/test_tc_m04_g046.py
```

Inventario OTA (repo solo lectura). Probe `http://127.0.0.1:8000/docs` → timeout.

**No** se lanzaron dos POST concurrentes contra PostgreSQL.

## 5–7. Esperado vs observado / HTTP

| Criterio | Esperado | Observado |
|---|---|---|
| Dos inicios simultáneos mismo dispositivo | Una activa; segunda rechazada/encolada | **No ejecutado:** no hay POST ni lock |
| HTTP e IDs de órdenes | Códigos reales | Ninguno |
| Dos dispositivos en paralelo | Permitido si el diseño lo dice | No verificado |
| Pytest skip 018 | Documenta bloqueo | SKIPPED (mensaje: no hay endpoint ni lock) |
| Dos GET concurrentes | — | **No usados** como evidencia de exclusión |

## 8. Auditoría

No verificable sin escrituras de despliegue.

## 9. Pruebas

| Ítem | Resultado |
|---|---|
| `test_tc_m04_018_*` | SKIPPED |
| Concurrencia real API+Edge | **No ejecutada** |

## 10. Limitaciones

El passed de `test_tc_m04_027_consulta_filtra_por_dispositivo` es listado en memoria, **no** es este subcaso.

## 11. Evidencias

- `.../TC-M04-G046/Resultados/TC-M04-187/TC-M04-187_resultado.md`
- `.../evidencias/ejecucion-2026-10-25-2109/g046-pytest.txt`, `inventario-ota.txt`, `api-local.txt`
- `.../Resultados/auditoria-2026-10-25/g046.{txt,html,xml}`

## Estado

**BLOQUEADO.**
