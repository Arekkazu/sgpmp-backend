# TC-M06-G117 — Informe de inspeccion de preparacion

- Antecedente: TC-M06-G89 / #1020 / INC-M06-333-G89
- Correccion ambiente: #1024
- Generado: 2026-11-13T03:37:46.521082+00:00
- Dictamen: **PREPARADO_CON_DISCREPANCIA**

TEST responde, activo 1569 apto, huella #1024 presente. DISC-G117-01 pendiente de decision (422 vs 400). 49b no ejecutarse sin autorizacion (escritura).

## TEST y autenticacion

```json
{
  "health_http": 200,
  "login_http": 200,
  "login_ok": true,
  "timeout": false
}
```

## Activo 1569 y periodo 220

```json
{
  "http": 200,
  "estado": "ACTIVO",
  "id_finca": 467,
  "razon_social": "QA M06 Operaciones SAS",
  "indicador_valoracion": "VALOR_RAZONABLE",
  "tiene_calculo": true,
  "valor_razonable_neto": "3760000.0000",
  "apto_para_g117": true
}
```
```json
{
  "encontrado": true,
  "estado": "ABIERTO",
  "fecha_inicio": "2026-11-01",
  "fecha_fin": "2026-11-30",
  "razon_social": "QA M06 Operaciones SAS"
}
```

## Contrato

```json
{
  "endpoint": "POST /finanzas/cotizaciones",
  "dto": "CotizacionDTO",
  "campos": {
    "activos_cotizados": "list[int] obligatorio min_length=1",
    "valor_cotizacion_propuesto": "Decimal gt=0 max_digits=18 decimal_places=4 (DTO)",
    "condiciones": "opcional",
    "fecha_vencimiento": "Optional[date] = None (DTO); opcional"
  },
  "fecha_emision": "No se envia; hoy_usuario() America/Bogota en el caso de uso",
  "validaciones_caso_uso": {
    "valor_propuesto_le_0": {
      "http": 422,
      "code": "VALOR_COTIZACION_INVALIDO",
      "alcanzable_via_api": false
    },
    "fecha_vencimiento_anterior": {
      "http": 422,
      "code": "FECHA_VENCIMIENTO_INVALIDA",
      "alcanzable_via_api": true
    },
    "fecha_vencimiento_omitida": {
      "permitido": true,
      "efecto": "persiste null; no vence automaticamente"
    }
  },
  "validacion_dto_antes_caso_uso": {
    "valor_0_o_negativo": {
      "http": 400,
      "code": "VAL_ENTRADA",
      "motivo": "Field(gt=0) en CotizacionDTO"
    }
  }
}
```

## Discrepancias (sin autocorregir)

```json
[
  {
    "id": "DISC-G117-01",
    "tema": "TC-M06-48 esperado vs implementacion",
    "matriz_issue_1020": "HTTP 422 VALOR_COTIZACION_INVALIDO para valor 0 y -1",
    "implementacion": "CotizacionDTO.valor_cotizacion_propuesto = Field(gt=0) rechaza 0/-1 en Pydantic; error_handlers -> HTTP 400 VAL_ENTRADA. La linea FA-6 del caso de uso (422 VALOR_COTIZACION_INVALIDO) no se alcanza por la API.",
    "fuentes": [
      "src/financial_valuation/infrastructure/dto/m06_dto.py CotizacionDTO",
      "src/shared/error_handlers.py request_validation_error_handler",
      "registrar_cotizacion_use_case.py FA-6",
      "primera_evaluacion/resumen_ejecucion_TC-M06-G117.json contrato historico"
    ],
    "accion": "No se altera la matriz ni el backend. Requiere revision/autorizacion de expectativa."
  },
  {
    "id": "DISC-G117-02",
    "tema": "RF-COT 5.3.b documental",
    "matriz": "Omitir fecha_vencimiento es valido (RF-COT 5.3.b)",
    "implementacion": "fecha_vencimiento Optional en DTO; caso de uso solo valida si viene y es < hoy",
    "especificacion_en_repo": "No se encontro documento RF-COT v1.1 con seccion 5.3.b en el repositorio",
    "respaldo_disponible": "Comentario Arekkazu en #1020 + DTO/use case + tabla (nullable)",
    "accion": "Conservar referencia issue #1020 + implementacion; 49b es escritura positiva y requiere autorizacion expresa"
  }
]
```

## Huella #1024 en TEST

```json
{
  "filtros_auditoria_presentes": {
    "id_usuario": true,
    "origen_registro": true,
    "id_referencia": true
  },
  "todos": true,
  "nota": "Huella OpenAPI del commit 29512934 (lote #1024). No prueba por si sola el FA-3 de periodo; si prueba presencia del lote en TEST."
}
```

## Baseline cotizaciones (solo lectura)

Sobre activo 1569 ya existen cotizaciones **9** y **10**. No alterarlas. Total listado Contador: 7 ids (10, 9, 8, 7, 6, 4, 5).

## Decision requerida (detencion)

- **DISC-G117-01**: matriz espera 422 `VALOR_COTIZACION_INVALIDO` para 48a/48b; backend API responde 400 `VAL_ENTRADA` por `Field(gt=0)` antes de FA-6. No se autocorrige.
- **49b**: escritura positiva; queda fuera hasta autorizacion expresa.
- Negativos 48a/48b/49a pueden ejecutarse despues de decidir DISC-G117-01; no se ejecutaron en esta fase.

## Confirmacion

**No se registro ninguna cotizacion ni se modificaron datos.** Solo `GET /health`, `POST /sesiones/`, `GET /openapi.json`, `GET /finanzas/periodos`, `GET /finanzas/activos/1569` y `GET /finanzas/cotizaciones`.

