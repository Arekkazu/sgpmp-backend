# TC-M06-G117 — Matriz de escenarios (preparacion)

Endpoint: `POST /finanzas/cotizaciones`

| ID | Subcaso | Payload clave | Esperado (matriz/#1020) | Observacion implementacion |
|---|---|---|---|---|
| 48a | TC-M06-48 | `valor_cotizacion_propuesto: 0`, activo 1569 | 422 `VALOR_COTIZACION_INVALIDO` | **DISC-G117-01**: DTO `gt=0` -> 400 `VAL_ENTRADA` |
| 48b | TC-M06-48 | `valor_cotizacion_propuesto: -1`, activo 1569 | 422 `VALOR_COTIZACION_INVALIDO` | **DISC-G117-01**: idem |
| 49a | TC-M06-49 | `valor` > 0, `fecha_vencimiento` = ayer (America/Bogota) | 422 `FECHA_VENCIMIENTO_INVALIDA` | Alineado con FA-5 del caso de uso |
| 49b | TC-M06-49 | omitir `fecha_vencimiento`, `valor` > 0 | Valido (RF-COT 5.3.b / #1020) → HTTP 201 | **Escritura**: crea cotizacion + `COTIZACION_REGISTRADA`; requiere autorizacion |

Cuerpo base DTO: `activos_cotizados` (enteros), `valor_cotizacion_propuesto`, opcionales `condiciones`, `fecha_vencimiento`.
No enviar `fecha_emision` (la calcula el servidor).

Activo de prueba: **1569** (`QA-M06O-VR-01`), periodo **220 ABIERTO**. Baseline sobre 1569: cotizaciones 9 y 10 (no alterar).

**No ejecutar POST hasta autorizacion expresa.** Decidir DISC-G117-01 antes de calificar 48a/48b.
