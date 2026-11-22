# INC-M06-361-G24 · RF-85 FA-4 — La cosecha del 100 % no dejaba el activo en baja (TC-M06-110)

Fecha: 2026-11-14. Responsable Git: destroyerban.
Rama: `fix/m06-inc361-g24-cosecha-total-baja`, desde `origin/dev` en `9e9eb1ed`.
Antecedente: INC-M06-320-G24 (#1007, `0dfc5afc`), ver `inc_m06_320_g24_cosecha_total_activo_en_cero.md`.

## Causa confirmada

La corrección de #1007 sí está en `origin/test`: tras la cosecha del 100 % se audita `MEDICION_POSTERIOR`
(`COSECHADO_COMPLETAMENTE`) y, después del commit, se pide la baja a M02. El adaptador de baja abría **otra
sesión** (`sesion_sistema()`, una conexión nueva).

QA corre en un sandbox transaccional (`src/shared/rollback/infraestructure/testing_sandbox.py` en `origin/test`):
todo el run va en una conexión con transacción externa y `join_transaction_mode="create_savepoint"`, así que el
`commit()` de M06 solo libera un SAVEPOINT. La conexión nueva del adaptador no ve el activo creado en el run, M02
responde que no existe y M06 deja el `MEDICION_PENDIENTE` «no se pudo registrar su baja». Resultado: activo
ACTIVO, sin fila en `eventos_bajas`. Es exactamente lo que reporta QA.

Se reprodujo en una BD efímera con `db_session` de integración (misma mecánica que el sandbox): con el código de
`dev` el activo queda en estado 1 (ACTIVO); con la corrección, en 6 (BAJA) y con su evento de baja `sacrificio`.

## Corrección

1. `BajaActivoM02Adapter` recibe la sesión de M06 y corre el caso de uso de bajas de M02 en ella, como usuario de
   servicio (`como_sistema`). Sigue después del commit de M06: si M02 la rechaza, el reconocimiento ya quedó y se
   alerta al Contador como antes. Fuera del sandbox el comportamiento es el mismo.
2. `GET /finanzas/activos/{id}` (historial) marca cada cálculo con `consumido_por_cosecha` y agrega
   `cosechado_completamente` y `valor_en_libros_actual` (0 tras la cosecha total; `null` si no hay cálculo base o
   el activo está al costo).

## Lo que no se puede sin el DBA

El ticket pide «el último cálculo del activo es 0» y «la medición posterior en cero» en SQL. La BD lo impide:

| Tabla | Restricción |
|---|---|
| `modulo6.calculos_valor_razonable` | `chk_calculo_bruto_positivo`: `valor_razonable_bruto > 0` |
| `modulo6.mediciones_posteriores` | `chk_medicion_valores_positivos`: `valor_razonable_anterior > 0 AND valor_razonable_actual > 0` |

Por eso #1007 dejó el cálculo «consumido» (deja de ser valor vigente) y respalda el cero con el evento
`MEDICION_POSTERIOR` de la auditoría, que el criterio de aceptación admite («la medición posterior **o el evento
que lo respalda**»). Una fila explícita en cero exigiría relajar esas restricciones con una migración aprobada por
el DBA; además, una medición posterior en cero registraría una variación por el valor total que el estado de
resultados no debe tomar como pérdida (la cosecha es un traslado a inventario). Se deja como propuesta.

## Pruebas

- Integración `tests/integration/test_inc_m06_361_g24_cosecha_total_baja.py`: falla con el código de `dev`
  (activo en estado 1) y pasa con la corrección (BAJA, evento `sacrificio`, sin `MEDICION_PENDIENTE`, producto por
  el 100 %, historial con valor 0).
- Unitarias `tests/financial_valuation/test_inc_m06_361_g24_baja_misma_sesion.py` (3) y suite de finanzas: 208.
- Integraciones de M06 y de bajas de M02: 55 pasan; 8 fallan igual en `dev` (entorno local: grants y RLS).
