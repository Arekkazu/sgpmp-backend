# TC-M06-G115 / TC-M06-44 — Ejecución Contador (única)

- Ambiente: `https://api.inmero.co/api-sgpmp-test`
- Generado: 2026-11-13T02:24:42.223507+00:00
- Valor propuesto enviado: `1000.0000`
- VR referencia esperado: `3760000.0000`

## Precondiciones

```json
{
  "contador_ok": true,
  "id_usuario": 141,
  "puede_crear_cotizaciones": true,
  "periodo_220_abierto": true,
  "activo_1569_apto": true,
  "vr_antes": "3760000.0000",
  "sin_cotizacion_previa_1569": true,
  "eventos_cotizacion_registrada_antes": 3,
  "lineas_antes": 0,
  "todas_ok": true
}
```

## POST

- HTTP: **201**
- id_cotizacion: **9**
- estado: COTIZADO
- valor_razonable_referencia: 3760000.0000
- id_periodo_contable: 220

## Verificaciones

- VR antes/después: 3760000.0000 → 3760000.0000
- Eventos COTIZACION_REGISTRADA: 3 → 4 (delta 1)
- Líneas/asientos: 0 → 0
- SQL SELECT: NO_EJECUTADO — sin conexión SQL directa en este entorno; verificación vía GET API

### Checks

```json
{
  "http_201": true,
  "id_cotizacion_presente": true,
  "estado_cotizado": true,
  "valor_propuesto_1000": true,
  "valor_referencia_3760000": true,
  "periodo_220": true,
  "activo_1569_en_cotizacion": true,
  "evento_cotizacion_registrada_delta_1": true,
  "vr_sin_cambio": true,
  "periodo_sigue_abierto": true,
  "sin_asientos_nuevos": true,
  "reservadas_6_7_intactas": true
}
```

## Dictamen

**APROBADO_PARCIAL_CONTADOR**

POST Contador 201; cotización 9 COTIZADO; referencia 3760000.0000; VR 1569 sin cambio; evento COTIZACION_REGISTRADA +1. Admin pendiente. G115 no cerrado.

- G115 no se marca APROBADO (Administrador pendiente; TC-M06-45 histórico).

