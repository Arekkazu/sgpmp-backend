# TC-M06-G118 — Informe de inspeccion de preparacion

- Antecedente: #1021 / INC-M06-334-G90
- Subcaso: TC-M06-50
- Generado: 2026-11-13T04:09:23.629348+00:00
- Dictamen: **PREPARADO_PENDIENTE_AUTORIZACION_POST**
- POST ejecutado: **No**

Baseline de solo lectura completo para activo 1571 / periodo 220. Solicitud POST preparada; requiere autorización expresa antes de enviar.

## Activo 1571
```json
{
  "http": 200,
  "id_activo_biologico": 1571,
  "identificador": "QA-M06O-VR-03",
  "estado": "ACTIVO",
  "id_finca": 467,
  "razon_social": "QA M06 Operaciones SAS",
  "indicador_valoracion": "VALOR_RAZONABLE",
  "valor_razonable_neto": "3760000.0000",
  "fecha_calculo": "2026-11-08T21:25:06.574099Z",
  "cantidad_calculos": 1,
  "lineas_en_historial": 2,
  "coincide_codigo": true,
  "coincide_vr_referencia": true,
  "apto_para_g118": true
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

## Lineas periodo 220
```json
{
  "http": 200,
  "total": 7,
  "ids": [
    894,
    895,
    896,
    2665,
    5799,
    5800,
    5801
  ],
  "estados": [
    "REGISTRADA"
  ],
  "ids_activos_en_lineas": [
    1569,
    1570,
    1571,
    1572
  ],
  "lineas_del_activo_1571": [
    896,
    5801
  ]
}
```

## Permisos
```json
{
  "rol": "Contador",
  "cotizaciones_C": true,
  "cotizaciones_R": true,
  "valoracion_activos_R": true,
  "auditoria_financiera_R": true,
  "exportacion_contable_R": true,
  "nota": "No se consultó GET /integracion/auditoria sin permiso (escribe ACCESO_AUDITORIA_DENEGADO)."
}
```

## AAEF
```json
{
  "canal_externo": {
    "ruta": "/integracion/aaef/productores/900000003",
    "auth_requerida": "Bearer token de canal (POST /integraciones/agrofusion/token) emitido para cliente externo por Administrador",
    "consultado": false,
    "motivo": "No hay credenciales de cliente externo / token de canal en el entorno QA Contador. No se inventan."
  },
  "vista_previa_contador": {
    "ruta": "/integracion/aaef/vista-previa/productores/900000003",
    "permiso_requerido": "exportacion_contable R",
    "tiene_permiso": true,
    "consultado": true,
    "nota_rf": "RF-AE01: AAEF de canal opera sobre períodos cerrados; 220 está ABIERTO.",
    "http": 422,
    "rango": {
      "desde": "2026-11-01",
      "hasta": "2026-11-30"
    },
    "resumen": {
      "keys": [
        "error_code",
        "fields",
        "message",
        "timestamp"
      ],
      "error_code": "CONTRATO_NO_ACTIVO",
      "message": "No hay una versión vigente del contrato contable. Contacte al administrador."
    }
  },
  "integracion_auditoria": {
    "ruta": "/integracion/auditoria",
    "consultado": false,
    "motivo": "Consulta sin permiso puede escribir ACCESO_AUDITORIA_DENEGADO; no se intentó."
  }
}
```

## Solicitud preparada (NO enviada)
```json
{
  "endpoint": "POST /finanzas/cotizaciones",
  "headers": {
    "Authorization": "Bearer <token Contador>",
    "Content-Type": "application/json",
    "X-Zona-Horaria": "America/Bogota"
  },
  "usuario_rol": "Contador (QA_CORREO)",
  "body": {
    "activos_cotizados": [
      1571
    ],
    "valor_cotizacion_propuesto": "1000.0000",
    "condiciones": "TC-M06-G118 / TC-M06-50 — integridad activo sin efectos contables (pendiente autorizacion)"
  },
  "notas": [
    "valor_cotizacion_propuesto sigue el precedente G115 (1000.0000 > 0); no es el VR.",
    "fecha_vencimiento omitida (opcional; RF-COT / #1020).",
    "fecha_emision la calcula el servidor (hoy_usuario America/Bogota).",
    "NO EJECUTADO en esta fase."
  ],
  "efectos_esperados": {
    "http": 201,
    "estado_cotizacion": "COTIZADO",
    "valor_razonable_referencia": "3760000.0000",
    "evento_auditoria": "COTIZACION_REGISTRADA",
    "activo_estado": "ACTIVO sin cambio",
    "vr_neto": "sin cambio",
    "lineas_periodo_220": "sin nuevas",
    "aaef": "sin nuevas exportaciones (use case no llama M07)",
    "periodo_220": "ABIERTO",
    "periodo_219": "CERRADO"
  },
  "ejecutado": false
}
```

## Limitaciones AAEF (no verificable al 100%)

- Canal externo `GET /integracion/aaef/productores/900000003`: **no consultado** (falta token de canal / cliente externo; no se inventan credenciales).
- Vista previa Contador: permiso `exportacion_contable` R presente, pero respuesta **422 `CONTRATO_NO_ACTIVO`** (“No hay una versión vigente del contrato contable”).
- El período 220 está ABIERTO; RF-AE01 de canal opera sobre períodos cerrados.
- Tras el POST (si se autoriza), la ausencia de AAEF nueva **no podrá demostrarse por API** mientras el contrato siga inactivo / sin token de canal. El use case de cotización no invoca M07; eso se documenta como evidencia de código, no como prueba funcional AAEF.

## Baseline adicional

- Cotizaciones: 7 (ids 10,9,8,7,6,4,5); sobre 1571 ya existe **cotización 6** (no se altera).
- Eventos `COTIZACION_REGISTRADA`: 5.
- Líneas 220: 7 ids `[894, 895, 896, 2665, 5799, 5800, 5801]`; del activo 1571: `[896, 5801]`.

## Confirmacion

**No se registro ninguna cotizacion.** Solo health, login y GET.
**Detenido antes del POST.** Se requiere autorización expresa para ejecutar TC-M06-50.

## Revalidación posterior (AAEF / Samuel)

Ver `revalidacion_lectura_aaef_G118.md` y `.json`.

- Activo 1571, líneas 220 (7), periodos 220 ABIERTO / 219 CERRADO: **sin cambio**.
- Contrato AAEF: **aún sin versión ACTIVO** (1.0 INACTIVO, 2.0 DEPRECADO) → vista previa sigue en `CONTRATO_NO_ACTIVO`.
- Credencial temporal: **no recibida** en el entorno del agente; no se consultó el canal AAEF.
- No se emitió token de canal (requeriría POST auxiliar).

