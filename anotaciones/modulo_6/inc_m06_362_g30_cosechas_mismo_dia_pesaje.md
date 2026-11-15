# INC-M06-362-G30 · RF-85 — Las cosechas del mismo día del pesaje no se acumulaban (TC-M06-136)

Fecha: 2026-11-14. Responsable Git: destroyerban. Issue: #1124.
Rama: `fix/m06-inc362-g30-cosechas-acumulativas`, desde `origin/dev` en `9e9eb1ed`.
Antecedentes: INC-M06-326-G30 (#1013, `e0f474f4`) e INC-M06-321-G25 (#1008, `2651c852`), ambos en `origin/test`.

## Causa confirmada

#1013 descuenta de la magnitud del activo los kg cosechados **después del último pesaje**, comparando
`eventos_activos.fecha`. Pero M02 guarda la cosecha (RF-43) solo con su día: `datetime(fecha, tzinfo=utc)`, o la
hora de creación del activo si es ese día (`no_anterior_a_creacion`). El pesaje guarda el instante real. Una
cosecha del mismo día del pesaje queda «antes» de él y no se descontaba: cada cosecha se calculaba sobre los
1.000 kg, la de 300 kg pasaba la validación de #1008 y el activo terminaba en 18.800.000 × 0,7 = 13.160.000.
Además el pesaje, procesado después de la primera cosecha, registraba una ganancia por transformación falsa.

Reproducido en BD efímera con `tests/integration/test_inc_m06_362_g30_cosechas_acumulativas.py`: con el código de
`dev` las tres cosechas quedan PROCESADO; con la corrección, la tercera queda MEDICION_PENDIENTE.

## Corrección

`ActivoFinancieroM02Adapter`: una cosecha se descuenta si está fechada después del último pesaje **o si se
registró después de él** (`ev.id_eventos > p.id_evento`). Sin migración.

Límite conocido: una cosecha registrada después de un pesaje pero fechada en un día anterior a él se descontaría
aunque ese pesaje ya la reflejara. Con fechas de solo día no hay forma de distinguirlo del caso de QA sin
cambiar cómo M02 guarda la cosecha.
