# INC-M06-317-G17 — El valor neto ≤ 0 se bloqueaba sin dejar el cálculo en revisión ni permitir validarlo (RF-84)

**RF:** RF-84 (restricción 3, paso 6, FA-2, salida 4, CA-5). **Issue:** #1004.
**Estado:** corregido con pruebas unitarias y SQL verificado contra el esquema real. Sin migración.

## Causa

`Valorador.valorar` devolvía `VALOR_NETO_NO_POSITIVO` sin el cálculo, y la confirmación del reconocimiento
(`POST /finanzas/reconocimientos/{id}`) respondía 422 sin escribir nada:

- no quedaba ningún cálculo en `REVISION_REQUERIDA` (el estado existe en `enum_calculos_valor_razonable_estado`
  pero nada lo escribía);
- no quedaba alerta de ningún nivel: la auditoría del activo estaba vacía;
- no existía una operación para validar el neto con justificación. `aceptar_no_positivo` solo lo usaba la
  simulación.

## Corrección

1. **El cálculo queda en revisión.** `Valorador.valorar` devuelve el motivo y, además, el cálculo en
   `REVISION_REQUERIDA`. La propuesta lo guarda en `calculo_revision`.
2. **Confirmación con neto ≤ 0** (cuando es el único bloqueo de la propuesta):
   - guarda el cálculo en `REVISION_REQUERIDA` en el período abierto que corresponde;
   - audita `CALCULO_VALOR_RAZONABLE` con severidad **CRITICAL**. El evento lleva el activo, el bruto, cada
     componente de costo con su método y el neto (salida 4);
   - hace commit y, después, avisa a los Contadores de la finca (`ALERTA_FINANCIERA_NIC41`, bandeja interna);
   - sigue respondiendo **422 `VALOR_NETO_NO_POSITIVO`**, ahora con las cifras y lo que puede hacer el Contador.
   Si la propuesta tiene otro bloqueo (por ejemplo, la finca sin titular), responde ese bloqueo y no guarda nada.
3. **Validación del Contador:** `POST /finanzas/calculos/{id_calculo_valor_razonable}/validacion` con
   `{"justificacion": "..."}` (permiso `valoracion_activos` / Ejecutar, que el Contador ya tiene).

   | Caso | Respuesta |
   |---|---|
   | Justificación ausente, vacía, en blanco o de menos de 20 caracteres | 400 `JUSTIFICACION_VALIDACION_REQUERIDA` (`field: justificacion`) |
   | Cálculo inexistente | 404 `CALCULO_NO_ENCONTRADO` |
   | Cálculo que no está en `REVISION_REQUERIDA` | 409 `CALCULO_SIN_REVISION_PENDIENTE` |
   | Período del cálculo cerrado o en cierre | 422 `PERIODO_NO_ABIERTO` |
   | Válida | 200: el cálculo pasa a `CALCULADO`; la justificación, el Contador y la fecha quedan en `json_metodo_costo.validacion_valor_no_positivo`, y se audita `CALCULO_VALOR_RAZONABLE` (WARNING, con `estado_anterior`) |

## Decisiones

1. **El reconocimiento con neto ≤ 0 sigue sin confirmarse.** `reconocimientos_iniciales` tiene
   `chk_reconoc_valor_positivo CHECK (valor_razonable_neto_inicial > 0)`. RF-84 pide validar «el cálculo», no el
   reconocimiento. Permitirlo exigiría una migración y definir cómo se asienta un activo con valor negativo.
   Decisión del equipo (2026-11-09): validar el cálculo sin migración.
2. **Sin tipo de evento nuevo.** Se usa `CALCULO_VALOR_RAZONABLE` (ya está en el catálogo) con el estado y el
   motivo en el payload, para no necesitar migración del enum.
3. **Cada intento deja su cálculo.** Cada confirmación rechazada guarda un cálculo nuevo en revisión: la tabla
   registra cada ejecución del cálculo.

## Impacto en el frontend

- El 422 de la confirmación ya trae un mensaje con las cifras.
- No hay pantalla para validar el cálculo. El id está en `GET /finanzas/periodos/{id}/calculos` (columna
  `estado`) y en el historial del activo. Falta un botón «Validar» con justificación que llame al endpoint nuevo.

## Fuera de alcance

- La medición posterior con neto ≤ 0 (`Medidor`) sigue en `MEDICION_PENDIENTE` sin guardar el cálculo en revisión.
- La vista `v_ultimo_calculo_por_activo` filtra `REVISION_REQUERIDA` antes del `DISTINCT ON`: muestra un cálculo
  en revisión aunque haya otro más reciente. No la usa el backend.

## Verificación

`tests/financial_valuation/test_inc_m06_317_g17_revision_valor_neto.py` (16 pruebas): valorador, confirmación
(cálculo en revisión, alerta CRITICAL, aviso después del commit, otro bloqueo sin escritura), validación (400 con
la justificación ausente, vacía, en blanco o corta; 404; 409; período cerrado; validación correcta) y contrato HTTP.

`obtener_calculo` y `validar_calculo` se ejecutaron contra una BD efímera con `alembic upgrade head`, con los
triggers activos (`REVISION_REQUERIDA` → `CALCULADO`, la validación en el JSON, sin cambio si ya no está en
revisión). La BD se borró al terminar.
