# TC-M04-021

Reevaluación 2026-10-25.

## Identificador y RF

**TC-M04-021** (G038). RF-65 / CU-02. Rechazar configuración incompatible con el contrato de entrada del modelo (`tipo_modelo` / `componente`).

## Runner

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m04_g038.py::test_tc_m04_021_incompatibilidad_es_422_no_409
```

**PASSED**, EXIT=0.

## Aserciones ejecutadas

Versión ACTIVO de `MODELO_AVES`/`DETECTOR` contra config `MODELO_ESPECIES_GRANDES` → `BusinessRuleError` `VERSION_MODELO_INCOMPATIBLE`, `status_code==422` y `!=409`. Vigente sin `id_version_modelo_activa`, `config_version==1`.

No se ejercitó `ventana_temporal_minutos` ni lista de variables del modelo: el puerto de prueba solo entrega `(estado, tipo_modelo, componente)`.

## Discrepancia (no convertida en defecto de producto)

La matriz de 2026-10-19 pedía HTTP **409**. El contrato Dev mapea `BusinessRuleError` a **422**. El test documenta el 422. Clasificación: **discrepancia de especificación / matriz**, no incidencia confirmada (no hay ID oficial INC-M04).

## Estado funcional

**PASS** del rechazo de llave incompatible en memoria. HTTP real no ejecutado.

## Evidencias

`evidencias/reeval-2026-10-25/test_tc_m04_021_incompatibilidad_es_422_no_409.{txt,html,xml}`
