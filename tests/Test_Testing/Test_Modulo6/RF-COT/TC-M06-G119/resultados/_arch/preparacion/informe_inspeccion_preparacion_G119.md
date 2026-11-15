# TC-M06-G119 — Informe de inspección de preparación

- Antecedente: #1022 / INC-M06-335-G91
- Generado: 2026-11-13T05:44:59.920739+00:00
- Dictamen: **PREPARADO_PENDIENTE_AUTORIZACION**
- Escritura: **No**

Baseline de solo lectura listo. Anulación 51 preparada (no enviada). Vencimiento 52: YA_OCURRIO. Coordinar dependencia G118 antes de anular cotización 6.

## Cotización 6 (TC-M06-51)
```json
{
  "id_cotizacion": 6,
  "estado": "COTIZADO",
  "version": 1,
  "activos_cotizados": [
    1571
  ],
  "fecha_emision": "2026-11-08",
  "fecha_vencimiento": null,
  "motivo_anulacion": null,
  "id_periodo_contable": 220,
  "estado_periodo": "ABIERTO",
  "valor_cotizacion_propuesto": "3900000.0000",
  "valor_razonable_referencia": "3760000.0000",
  "fecha_actualizacion": null
}
```

## Cotización 7 (TC-M06-52)
```json
{
  "id_cotizacion": 7,
  "estado": "VENCIDA",
  "version": 2,
  "activos_cotizados": [
    1570
  ],
  "fecha_emision": "2026-11-08",
  "fecha_vencimiento": "2026-11-08",
  "motivo_anulacion": null,
  "id_periodo_contable": 220,
  "estado_periodo": "ABIERTO",
  "valor_cotizacion_propuesto": "3800000.0000",
  "valor_razonable_referencia": "3760000.0000",
  "fecha_actualizacion": "2026-11-09T00:00:06.613021Z"
}
```

## Evaluación
```json
{
  "tc51_cotizacion_6": {
    "apta_para_anulacion": true,
    "estado": "COTIZADO",
    "version": 1,
    "activo_ok": true,
    "sin_vencimiento": true
  },
  "tc52_cotizacion_7": {
    "transicion_automatica": "YA_OCURRIO",
    "estado": "VENCIDA",
    "fecha_vencimiento": "2026-11-08",
    "version": 2,
    "activo_ok": true,
    "evento_COTIZACION_VENCIDA_ref_7": {
      "http": 200,
      "total_registros": 1,
      "muestra": [
        {
          "id_evento": 7098,
          "id_referencia": 7,
          "timestamp_evento": "2026-11-09T00:00:06.613021Z",
          "tipo_actor": "SISTEMA",
          "id_sistema": "M06_VENCIMIENTO_COTIZACIONES"
        }
      ]
    },
    "evidencia_automatica_suficiente": true,
    "accion": "No reprocesar; verificar activo 1570 y dictaminar con evidencia de estado+evento"
  }
}
```

## Activo 1570
```json
{
  "http": 200,
  "identificador": "QA-M06O-VR-02",
  "estado": "ACTIVO",
  "id_finca": 467,
  "razon_social": "QA M06 Operaciones SAS",
  "indicador_valoracion": "VALOR_RAZONABLE",
  "valor_razonable_neto": "3760000.0000",
  "fecha_calculo": "2026-11-08T21:25:04.061875Z"
}
```

## Periodos
```json
{
  "220": {
    "encontrado": true,
    "estado": "ABIERTO",
    "fecha_inicio": "2026-11-01",
    "fecha_fin": "2026-11-30",
    "razon_social": "QA M06 Operaciones SAS"
  },
  "219": {
    "encontrado": true,
    "estado": "CERRADO",
    "fecha_inicio": "2026-11-01",
    "fecha_fin": "2026-11-30",
    "razon_social": "QA M06 Cierre SAS"
  }
}
```

## Auditoría (resumen)
```json
{
  "COTIZACION_ANULADA": {
    "total": 0,
    "ref6": {
      "http": 200,
      "total_registros": 0,
      "muestra": []
    },
    "ref7": {
      "http": 200,
      "total_registros": 0,
      "muestra": []
    }
  },
  "COTIZACION_VENCIDA": {
    "total": 2,
    "ref6": {
      "http": 200,
      "total_registros": 0,
      "muestra": []
    },
    "ref7": {
      "http": 200,
      "total_registros": 1,
      "muestra": [
        {
          "id_evento": 7098,
          "id_referencia": 7,
          "timestamp_evento": "2026-11-09T00:00:06.613021Z",
          "tipo_actor": "SISTEMA",
          "id_sistema": "M06_VENCIMIENTO_COTIZACIONES"
        }
      ]
    }
  },
  "COTIZACION_REGISTRADA": {
    "total": 5,
    "ref6": {
      "http": 200,
      "total_registros": 1,
      "muestra": [
        {
          "id_evento": 7071,
          "id_referencia": 6,
          "timestamp_evento": "2026-11-08T21:25:14.590377Z",
          "tipo_actor": "USUARIO",
          "id_sistema": null
        }
      ]
    },
    "ref7": {
      "http": 200,
      "total_registros": 1,
      "muestra": [
        {
          "id_evento": 7072,
          "id_referencia": 7,
          "timestamp_evento": "2026-11-08T21:25:15.761785Z",
          "tipo_actor": "USUARIO",
          "id_sistema": null
        }
      ]
    }
  }
}
```

## Solicitud de anulación (NO enviada)
```json
{
  "endpoint": "POST /finanzas/cotizaciones/6/anulacion",
  "headers": {
    "Authorization": "Bearer <token Contador>",
    "Content-Type": "application/json",
    "X-Zona-Horaria": "America/Bogota"
  },
  "usuario_rol": "Contador (permiso cotizaciones desactivar)",
  "body": {
    "version": 1,
    "motivo_anulacion": "TC-M06-G119 / TC-M06-51 — anulación controlada de cotización 6 (activo 1571). Motivo de prueba QA; pendiente autorización."
  },
  "segundo_intento": {
    "endpoint": "POST /finanzas/cotizaciones/6/anulacion",
    "body": {
      "version": 2,
      "motivo_anulacion": "TC-M06-G119 / TC-M06-51 — anulación controlada de cotización 6 (activo 1571). Motivo de prueba QA; pendiente autorización. segundo intento"
    },
    "esperado": {
      "http": 422,
      "code": "COTIZACION_NO_MODIFICABLE"
    },
    "nota": "Usar version actualizada tras primera anulación; no ejecutar sin autorización"
  },
  "consultas_posteriores": [
    "GET /finanzas/cotizaciones (filtrar id 6)",
    "GET /finanzas/auditoria?tipo_evento=COTIZACION_ANULADA&id_referencia=6",
    "GET /finanzas/activos/1571"
  ],
  "ejecutado": false
}
```

## Confirmación

Sin POST de anulación. Sin ejecución manual de vencer(). Solo health, login y GET.

