# TC-M03-091

Reevaluación 2026-10-25. Evidencias nuevas en `evidencias/reeval-2026-10-25/` (no se sobrescribió el lote RF-56 de 090).

## Identificador y RF

**TC-M03-091** (G55). RF-56 / CU-02. Envío HTTP real del paquete a M04 (JWT, ≤500 registros, ACK de recepción).

## Objetivo

Verificar cliente HTTP hacia M04. Precondición: motor real, no stub.

## Resultado esperado

POST de inferencia aceptado/rechazado por M04 con evidencia de red.

## Runner (reeval)

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/.../test_tc_m03_g55.py::test_tc_m03_091_envio_real_a_m04
```

**SKIPPED**, EXIT=0. Motivo: `MotorInferenciaStubAdapter.enviar_paquete` retorna `True` sin HTTP; no existe `POST /inferencia`. `test_tc_m03_090_mapeo_puerto_true_es_enviado_del_puerto_no_m04` **PASSED** (mapeo bool → ENVIADO, no ACK M04).

## Estado funcional

**BLOQUEADO** / funcionalidad faltante (cliente M04). No es defecto de un payload HTTP incorrecto: no hay llamada. INC-M03-112-G55.

## Evidencias

`evidencias/reeval-2026-10-25/test_tc_m03_091_envio_real_a_m04.txt|html|xml`
