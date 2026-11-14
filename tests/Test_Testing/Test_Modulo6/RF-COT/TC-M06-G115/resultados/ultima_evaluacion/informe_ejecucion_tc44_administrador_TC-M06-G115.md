# TC-M06-G115 / TC-M06-44 — Ejecución Administrador (única)

- Ambiente: `https://api.inmero.co/api-sgpmp-test`
- Generado: 2026-11-13T02:31:16.190595+00:00
- Valor propuesto: `1000.0000`
- VR referencia esperado: `3760000.0000`

## Análisis reutilización activo 1569

1569 admite segunda cotización válida sin invalidar cotización 9

## Precondiciones

```json
{
  "administrador_ok": true,
  "id_usuario": 137,
  "puede_crear_cotizaciones": true,
  "periodo_220_abierto": true,
  "activo_1569_apto": true,
  "vr_antes": "3760000.0000",
  "cotizacion_9_intacta": true,
  "cotizacion_9_snapshot": {
    "id_cotizacion": 9,
    "estado": "COTIZADO",
    "valor_cotizacion_propuesto": "1000.0000",
    "valor_razonable_referencia": "3760000.0000",
    "id_periodo_contable": 220,
    "activos_cotizados": [
      1569
    ],
    "id_usuario": 141,
    "version": 1
  },
  "segunda_cotizacion_1569_permitida_por_codigo": true,
  "reservadas_6_7_presentes": true,
  "eventos_antes": 4,
  "lineas_antes": 0,
  "todas_ok": true
}
```

## POST

- HTTP: **201**
- id_cotizacion: **10**
- estado: COTIZADO
- valor_razonable_referencia: 3760000.0000
- id_periodo_contable: 220

## Verificaciones (GET; SQL directo no disponible)

- VR: 3760000.0000 → 3760000.0000
- Eventos: 4 → 5 (delta 1)
- Líneas: 0 → 0
- Actor admin id_usuario: 137

```json
{
  "http_201": true,
  "id_cotizacion_presente": true,
  "estado_cotizado": true,
  "valor_propuesto_1000": true,
  "valor_referencia_3760000": true,
  "periodo_220": true,
  "activo_1569_en_cotizacion": true,
  "actor_administrador": true,
  "evento_delta_1": true,
  "vr_sin_cambio": true,
  "periodo_sigue_abierto": true,
  "sin_asientos_nuevos": true,
  "cotizacion_9_intacta": true,
  "reservadas_6_7_intactas": true,
  "distinta_de_cotizacion_9": true
}
```

## Dictamen Administrador

**APROBADO**

POST Administrador 201; cotización 10 COTIZADO; referencia 3760000.0000; actor 137; VR sin cambio; evento +1; cotización 9 intacta.

## Estado G115

```json
{
  "tc_m06_44_contador": "APROBADO",
  "tc_m06_44_administrador": "APROBADO",
  "tc_m06_45": "APROBADO_HISTORICO",
  "g115": "APROBADO 2/2",
  "denominador": "2/2 = TC-M06-44 (Contador+Admin) + TC-M06-45",
  "g115_aprobado": true
}
```

