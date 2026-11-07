# TC-M04-002

Reevaluación 2026-10-25. Evidencias por nodo en `evidencias/reeval-2026-10-25/`.

## Identificador y RF

**TC-M04-002** (G037). RF-65 / CU-02. Límites de umbrales (0.50–0.95) y ventana (5–15 min). Rechazo sin alterar la vigente.

## Objetivo

Aceptar bordes válidos; rechazar 0.49, 0.96, 4 min y 16 min con código de negocio y sin persistir el cambio.

## Runner (reeval)

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m04_g037.py::test_tc_m04_002_limites_validos[...]
  tests/.../test_tc_m04_g037.py::test_tc_m04_002_fuera_de_rango_no_persiste[...]
```

12 nodos **PASSED**, EXIT=0 cada uno (el primer lote de inválidos falló al escribir HTML por ruta Windows demasiado larga; se reejecutaron con nombres cortos `inv_*`).

## Aserciones ejecutadas

- Bordes válidos: riesgo/crítica 0.50 y 0.95; ventana 5 y 15; quedan en el repo en memoria.
- Inválidos: `BusinessRuleError` 422 `UMBRAL_RIESGO_FUERA_RANGO` / `UMBRAL_CRITICA_FUERA_RANGO` / `VENTANA_TEMPORAL_FUERA_RANGO`; vigente 0.70 y `config_version==1`; un solo evento de auditoría (el de la creación previa); `db.rollbacks==0` (el use case lanza antes de persistir).

No hubo respuestas HTTP: el código 422 es `exc.value.status_code` del error de dominio.

## Estado funcional

**PASS unitario en memoria** para rangos FA-01 del use case. **No** se verificó persistencia PostgreSQL ni API.

## Evidencias

Límites válidos: `test_tc_m04_002_limites_validos_*`.  
Inválidos: `inv_riesgo_049`, `inv_riesgo_096`, `inv_critica_049`, `inv_critica_096`, `inv_ventana_4`, `inv_ventana_16`.
