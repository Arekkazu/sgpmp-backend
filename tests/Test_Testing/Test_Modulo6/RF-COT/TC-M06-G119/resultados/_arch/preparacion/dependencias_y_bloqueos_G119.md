# TC-M06-G119 — Dependencias y bloqueos

## Dependencia G118

{
  "descripcion": "Cotización 6 / activo 1571 es el mismo activo aislado preparado para G118 (TC-M06-50). G118 sigue pendiente de autorización de POST de registro. Anular la cotización 6 alteraría el baseline comercial de 1571 y debe coordinarse: no ejecutar TC-M06-51 sin decisión expresa respecto a G118.",
  "impacto_si_se_anula_6": "1571 perdería la cotización COTIZADO id 6; G118 podría necesitar otra cotización o reordenar ejecución",
  "g118_post_ejecutado": false
}

## Riesgos / bloqueos

- Dependencia G118: no anular cotización 6 sin autorización coordinada
- No alterar cotizaciones 4/5 ni periodos 219/220

## Actualización 2026-11-13

- TC-M06-52 cerrado documentalmente como **APROBADO**.
- TC-M06-51 sigue pendiente; dependencia G118 vigente.
- Grupo G119: **PARCIALMENTE_PENDIENTE** (no aprobado completo).

## Dictamen

{
  "categoria": "PREPARADO_PENDIENTE_AUTORIZACION",
  "tc51_listo_para_anulacion": true,
  "tc52_estado": "YA_OCURRIO",
  "tc52_evidencia_automatica_suficiente": true,
  "escritura_ejecutada": false,
  "motivo": "Baseline de solo lectura listo. Anulación 51 preparada (no enviada). Vencimiento 52: YA_OCURRIO. Coordinar dependencia G118 antes de anular cotización 6.",
  "requiere_autorizacion_expresa": [
    "POST anulación cotización 6 (TC-M06-51) — coordinar con G118",
    "Segundo intento de anulación (irreversibilidad)",
    "No ejecutar vencer() manual para TC-M06-52"
  ]
}
