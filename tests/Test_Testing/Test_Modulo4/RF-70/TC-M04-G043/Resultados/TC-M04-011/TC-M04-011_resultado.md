# TC-M04-011

Reevaluación 2026-10-25. Sin rechazo OTA real de modelo no aprobado.

## Identificador y RF

**TC-M04-011** (G043). RF-70 / CU-06. Rechazar distribución de un modelo no aprobado.

## Runner

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m04_g043.py::test_tc_m04_010_011_ambiguedad_gate_aprobado_vs_activo
  tests/.../test_tc_m04_g043.py::test_tc_m04_011_activar_version_exige_aprobado_rf69_no_es_ota
```

SKIPPED (PENDING_SPEC, evidencia bajo TC-M04-010) y **PASSED** el nodo de activación RF-69. EXIT=0.

## Aserciones ejecutadas (seguras, no son OTA)

`VersionModelo.crear` queda `EN_VALIDACION`. `activar()` lanza `VERSION_NO_APROBADA`. El fuente de `ActivarVersionModeloUseCase.execute` no menciona “despliegue”. Eso es **RF-69** (paso a ACTIVO), no inicio OTA.

## No ejecutado

Rechazo de distribución OTA por estado no APROBADO/no ACTIVO: no hay use case de inicio en `src/prediction/application/use_cases/ota/`.

## Estado funcional

**BLOQUEADO / PENDING_SPEC**. No se declara defecto de RF-70. Ver hallazgo de discrepancia en el grupo.

## Evidencias

`evidencias/reeval-2026-10-25/test_tc_m04_011_activar_version_exige_aprobado_rf69_no_es_ota.*`  
Skip compartido: `../TC-M04-010/evidencias/reeval-2026-10-25/test_tc_m04_010_011_ambiguedad_gate_aprobado_vs_activo.*`
