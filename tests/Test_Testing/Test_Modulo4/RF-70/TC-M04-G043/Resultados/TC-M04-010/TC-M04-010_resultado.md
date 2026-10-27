# TC-M04-010

Reevaluación 2026-10-25. Sin distribución OTA real.

## Identificador y RF

**TC-M04-010** (G043). RF-70 / CU-06. Distribuir un modelo aprobado al nodo Edge.

## Runner

```
# G043 importa ota_router → DATABASE_URL=sqlite:///:memory: y SECRET_KEY de prueba
# (solo arranque de imports; no hay PostgreSQL ni escritura OTA)
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m04_g043.py::test_tc_m04_010_011_ambiguedad_gate_aprobado_vs_activo
  tests/.../test_tc_m04_g043.py::test_tc_m04_010_router_ota_solo_lectura
```

| Nodo | Pytest | EXIT |
|---|---|---|
| ambigüedad APROBADO vs ACTIVO | **SKIPPED** (`PENDING_SPEC`) | 0 |
| router OTA solo lectura | **PASSED** | 0 |

Sin `DATABASE_URL` la recolección de G043 **ERROR** (`src/shared/database.py`).

## Aserciones ejecutadas (seguras)

Métodos del router `ota_router`: conjunto `{"GET"}`. Comentario de producto: `GET /prediccion/modelos/{id}/ota-status` y `GET /prediccion/despliegues`. Use cases: `ConsultarOtaStatusUseCase`, `ListarDesplieguesUseCase`. Anotación `curls_m04_cu06_ota.md`: IoT/IA escribe `modulo4.despliegues_ota`.

## Omitido / no ejecutado

POST de inicio OTA, publicación MQTT, artefactos, dispositivos Edge, gate APROBADO o ACTIVO sobre un despliegue. **No** se eligió interpretación.

## Estado funcional

**BLOQUEADO / PENDING_SPEC**. EXIT=0 con SKIPPED **no** aprueba RF-70 de distribución. Ver `../HALLAZGO_DISCREPANCIA_ESPEC_TC-M04-010-011.md`.

## Evidencias

`evidencias/reeval-2026-10-25/test_tc_m04_010_011_ambiguedad_gate_aprobado_vs_activo.*`  
`evidencias/reeval-2026-10-25/test_tc_m04_010_router_ota_solo_lectura.*`
