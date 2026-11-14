# TC-M06-G117 — Resultados esperados (preparación)

Endpoint: `POST /finanzas/cotizaciones`  
Headers: `Authorization: Bearer <token Contador>`, `Content-Type: application/json`, `X-Zona-Horaria: America/Bogota`

## Payload real (CotizacionDTO / OpenAPI TEST)

Obligatorios:

- `activos_cotizados`: `list[int]` (min 1, max 500) → `[1569]`
- `valor_cotizacion_propuesto`: Decimal `gt=0`, max 18 dígitos / 4 decimales

Opcionales:

- `condiciones`: string ≤ 2000
- `fecha_vencimiento`: date o null / omitido

No enviar `fecha_emision` (servidor: `hoy_usuario()` con zona America/Bogota).

Éxito de registro (si se autorizara 49b): HTTP **201**, evento `COTIZACION_REGISTRADA`.

## Matriz vs implementación

| ID | Escenario | Esperado matriz / #1020 | Implementación observada | Dictamen prep |
|---|---|---|---|---|
| 48a | `valor_cotizacion_propuesto = 0` | 422 `VALOR_COTIZACION_INVALIDO` | DTO `Field(gt=0)` → **400 `VAL_ENTRADA`** (FA-6 no alcanzable vía API) | **DISC-G117-01** — detener revisión |
| 48b | `valor_cotizacion_propuesto = -1` | 422 `VALOR_COTIZACION_INVALIDO` | Idem 48a | **DISC-G117-01** |
| 49a | emisión hoy + vencimiento ayer | 422 `FECHA_VENCIMIENTO_INVALIDA` | FA-5 `BusinessRuleError` → 422; alineado | Listo (negativo) |
| 49b | omitir `fecha_vencimiento` | Válido (RF-COT 5.3.b / #1020) | Optional en DTO; use case no exige; columna nullable | Escritura: **no ejecutar** sin autorización |

## Referencias de reglas

- DTO: `src/financial_valuation/infrastructure/dto/m06_dto.py` · `CotizacionDTO`
- Caso de uso: `registrar_cotizacion_use_case.py` FA-5 / FA-6
- HTTP negocio: `BusinessRuleError.status_code = 422` (`src/shared/errors.py`)
- HTTP validación Pydantic: `request_validation_error_handler` → 400 `VAL_ENTRADA` (ruta POST cotizaciones **sin** `x-codigo-validacion: 422`)
- Router: `POST /cotizaciones` `status_code=201`
- Opcionalidad vencimiento: comentario responsable en #1020 + DTO/use case; **no** hay RF-COT v1.1 §5.3.b en el repo (**DISC-G117-02**)

## Decisión requerida antes de ejecutar

1. **DISC-G117-01**: ¿calificar 48a/48b contra 422 matriz o contra 400 implementación?
2. **49b**: autorización expresa de escritura (crea cotización + auditoría).
