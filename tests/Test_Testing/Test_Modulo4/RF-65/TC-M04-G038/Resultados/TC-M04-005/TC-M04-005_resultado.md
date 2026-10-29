# TC-M04-005

Reevaluación 2026-10-25.

## Identificador y RF

**TC-M04-005** (G038). RF-65 / CU-02. Rechazar modelo que no esté ACTIVO al configurar el motor.

## Runner

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m04_g038.py::test_tc_m04_005_rechaza_modelo_no_activo[APROBADO]
  tests/.../test_tc_m04_g038.py::test_tc_m04_005_rechaza_modelo_no_activo[DEPRECADO]
  tests/.../test_tc_m04_g038.py::test_tc_m04_005_rechaza_modelo_no_activo[RECHAZADO]
  tests/.../test_tc_m04_g038.py::test_tc_m04_005_acepta_modelo_activo
```

Cuatro nodos **PASSED**, EXIT=0.

## Aserciones ejecutadas

- `PreconditionFailedError` `MODELO_NO_ACTIVO`, `status_code==412` para APROBADO, DEPRECADO y RECHAZADO (doble `VersionPortFijo`).
- Configuración vigente: `id_version_modelo_activa is None`, `config_version==1`, un evento de auditoría.
- ACTIVO id=20 se vincula y queda en el repo en memoria.

No se llamó HTTP contra la API ni contra PostgreSQL. El 412 es el atributo del error de dominio (comentario del script: gate FA-03).

## Estado funcional

**PASS unitario** del gate ACTIVO en `ConfigurarMotorUseCase._validar_version`. **BLOQUEADO** para prueba de integración HTTP/BD.

## Evidencias

`evidencias/reeval-2026-10-25/test_tc_m04_005_rechaza_modelo_no_activo_{APROBADO,DEPRECADO,RECHAZADO}_.*`  
`evidencias/reeval-2026-10-25/test_tc_m04_005_acepta_modelo_activo.*`
