# TC-M04-003

Reevaluación 2026-10-25.

## Identificador y RF

**TC-M04-003** (G037). RF-65 / CU-02. Coherencia `umbral_alerta_critica >= umbral_riesgo_alto`.

## Runner

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m04_g037.py::test_tc_m04_003_alerta_menor_que_riesgo_no_guarda
```

**PASSED**, EXIT=0.

## Aserciones ejecutadas

Intento 0.80 riesgo / 0.70 crítica → `UMBRAL_CRITICA_MENOR_QUE_RIESGO`, `status_code==422`. Vigente sigue 0.70/0.80, `config_version==1`. Ningún evento de auditoría con acción `ACTUALIZADA`.

## Estado funcional

**PASS** en use case en memoria. Sin HTTP real ni SQL.

## Evidencias

`evidencias/reeval-2026-10-25/test_tc_m04_003_alerta_menor_que_riesgo_no_guarda.{txt,html,xml}`
