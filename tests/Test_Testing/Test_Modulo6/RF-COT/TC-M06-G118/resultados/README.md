# TC-M06-G118 — Índice de evidencias

Grupo **RF-COT / AAEF** · subcaso **TC-M06-50**.

Ambiente: `api-sgpmp-test` · Período **220 ABIERTO** · Período **219 CERRADO**.

## Dictamen vigente

**G118: APROBADO** · **TC-M06-50: APROBADO** (14/14 CUMPLE).

| Componente | Estado | Fuente | Evidencia |
|---|---|---|---|
| TC-M06-50 cotización | **APROBADO** | Cursor (1 POST) | [`ejecucion_tc50_2026-11-15/`](ejecucion_tc50_2026-11-15/) — cotización **15**, RF-94 **29463** |
| Fixture / vista previa Contador (NIT 901333217) | CUMPLE | Cursor (solo lectura) | [`reevaluacion_fixture_aaef_2026-11-15/`](reevaluacion_fixture_aaef_2026-11-15/) |
| Auth externa AAEF + rotación credencial | CUMPLE | **Confirmación externa Samuel** (no ejecutada por Cursor) | [`confirmacion_samuel_aaef_2026-11-15/`](confirmacion_samuel_aaef_2026-11-15/) |
| Negativo NIT 900000003 / período 220 | CUMPLE | Cursor + Samuel | fixture + ejecución 50 · HTTP **422** `PERIODO_NO_CERRADO` |

Estado máquina: [`estado_oficial_G118.json`](estado_oficial_G118.json)  
Organización: [`ORGANIZACION_FINAL_G118.json`](ORGANIZACION_FINAL_G118.json)  
Informe HTML: [`REPORTE_FINAL_G118_RF_AAEF.html`](REPORTE_FINAL_G118_RF_AAEF.html)

## TC-M06-50 — resumen

| Campo | Valor |
|---|---|
| HTTP | **201** |
| `id_cotizacion` | **15** |
| Estado / versión | **COTIZADO** / **1** |
| Activo | **1571** (`QA-M06O-VR-03`) |
| VR referencia | **$3.760.000** (sin cambio en el activo) |
| RF-94 | **29463** `COTIZACION_REGISTRADA` |
| Líneas contables nuevas | ninguna |
| AAEF vista-previa 900000003 | **422** `PERIODO_NO_CERRADO` |

### Revalidación 50.11 / 50.13 / 50.14

En la pasada inicial del script, esos tres criterios fallaron temporalmente por `TOKEN_REVOCADO` mid-script. Se revalidaron **solo con consultas de lectura** y login fresco → **CUMPLE**. No hubo POST adicional. Ver `ejecucion_tc50_2026-11-15/verificacion_complementaria_lectura.json`.

## Estructura activa

```
resultados/
  estado_oficial_G118.json
  ORGANIZACION_FINAL_G118.json
  README.md
  REPORTE_FINAL_G118_RF_AAEF.html
  preparacion/                         # payload y precondiciones TC-50
  confirmacion_samuel_aaef_2026-11-15/ # evidencia externa
  reevaluacion_fixture_aaef_2026-11-15/
  ejecucion_tc50_2026-11-15/
  _arch/                               # histórico (primera evaluación, diagnósticos, scripts aux.)
```

## Seguridad

No versionar `.env` ni secretos AAEF. No incluir enlaces de entrega de credenciales.
