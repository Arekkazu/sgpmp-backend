# TC-M04-001

Reevaluación 2026-10-25. Evidencias en `evidencias/reeval-2026-10-25/` (no había evidencias históricas en este grupo).

## Identificador y RF

**TC-M04-001** (G037). RF-65 / CU-02. Configurar y aplicar parámetros válidos.

## Objetivo

Aplicar umbrales y ventana válidos, persistir, auditar, incrementar `config_version` y aplicar en caliente si el entorno lo permite.

## Runner (reeval)

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m04_g037.py::test_tc_m04_001_configuracion_valida_en_use_case
  tests/.../test_tc_m04_g037.py::test_tc_m04_001_hot_reload_edge
```

Entorno: `--noconftest`, dobles en memoria (`rf65_dobles.py`). Sin PostgreSQL compartido, sin MQTT, sin POST HTTP.

| Nodo | Pytest | EXIT |
|---|---|---|
| `test_tc_m04_001_configuracion_valida_en_use_case` | **PASSED** | 0 |
| `test_tc_m04_001_hot_reload_edge` | **SKIPPED** | 0 |

## Aserciones ejecutadas

Use case en memoria: `es_nueva=True`, umbrales 0.70/0.80, ventana 10, `config_version==1`, `modo_ejecucion=SERVIDOR`, repositorio retiene valores, `db.commits>=1`, auditoría `CONFIGURACION_MOTOR_CAMBIADA` / `CREADA` / `id_usuario=9`.

## Aserciones omitidas

Hot-reload Edge ≤5 s: `NodoEdgePort` solo expone `hay_nodos_activos`. `ConfigurarMotorUseCase` no notifica nodos. Persistencia SQL real no ejecutada (`SesionNula`, no es PostgreSQL).

## Estado funcional

**PARCIAL / BLOQUEADO** en hot-reload y SQL. El SKIPPED con EXIT=0 **no** aprueba el requisito de aplicación en caliente. Lo verificado es el use case + auditoría + “commit” del doble.

## Evidencias

- `evidencias/reeval-2026-10-25/test_tc_m04_001_configuracion_valida_en_use_case.{txt,html,xml}`
- `evidencias/reeval-2026-10-25/test_tc_m04_001_hot_reload_edge.{txt,html,xml}`
