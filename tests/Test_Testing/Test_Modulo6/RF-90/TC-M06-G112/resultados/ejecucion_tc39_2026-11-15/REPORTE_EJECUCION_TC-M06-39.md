# Reporte de ejecución TC-M06-39 — G112

- Fecha UTC: `2026-11-16T02:59:10.868082+00:00`
- Ambiente: `https://api.inmero.co/api-sgpmp-test`
- Posts ejecutados: **1**
- HTTP POST: **201**
- `id_registro_costo`: **4498**
- `id_linea_asiento`: **7121**
- Política: **CAPITALIZAR**
- Dictamen: **APROBADO**

## Criterios

| ID | Criterio | Resultado |
|---|---|---|
| 39-B1 | Baseline activo 1573 costos/valor | CUMPLE |
| 39-B2 | Baseline sin inversión previa del caso | CUMPLE |
| 39-B3 | Matriz MOP/CAPITALIZACION → 158405/250505 (asig 36) | CUMPLE |
| 39-B4 | Período 220 ABIERTO (no cerrar) | CUMPLE |
| 39-E1 | POST HTTP 201 | CUMPLE |
| 39-E2 | id_registro_costo presente | CUMPLE |
| 39-E3 | id_linea_asiento presente (ASIENTO_NIC41) | CUMPLE |
| 39-V1 | Costo persistido CAPITALIZAR / INVERSION / monto | CUMPLE |
| 39-V2 | Delta costo histórico = monto | CUMPLE |
| 39-V3 | Línea MOP/CAPITALIZACION D158405 C250505 | CUMPLE |
| 39-V4 | Auditoría COSTO_REGISTRADO con política CAPITALIZAR | CUMPLE |
| 39-V5 | Comprobante de cierre no exigido (período abierto) | CUMPLE |
| 39-X1 | RF-93 / cerrar 220 (excluido del alcance G112) | NO VERIFICABLE |
| 39-S1 | Activo 1573 permanece ACTIVO | CUMPLE |
| 39-S2 | Período 220 permanece ABIERTO | CUMPLE |
| 39-S3 | Sin afectación colateral a activo 2552 / período 629 por este POST | CUMPLE |

## Estado final

- Activo 1573: `ACTIVO` · costos `4100000.0000` · valor `4100000.0000`
- Período 220: `ABIERTO`
- Asiento: MANO_OBRA_PROPIA/CAPITALIZACION D158405/C250505
- RF-94: `COSTO_REGISTRADO` id_evento=`28938`

Estado oficial G112 **no** actualizado. Sin commit/push.
