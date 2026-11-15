# TC-M06-G119 — Índice de evidencias (APROBADO)

Grupo **RF-COT / RF-94**: TC-M06-51 (anulación irreversible) + TC-M06-52 (vencimiento automático).

## Estructura activa

| Ruta | Rol |
|---|---|
| `ejecucion_tc51_2026-11-15/` | Ejecución autorizada TC-M06-51 (HTTP 200 + 422, RF-94 **25569**, integridad activo 1571) |
| `ultima_evaluacion/resumen_ejecucion_vigente_TC-M06-G119.json` | Resumen oficial vigente — dictamen **APROBADO** |
| `ultima_evaluacion/informe_cierre_TC-M06-G119.md` | Informe de cierre |
| `ultima_evaluacion/evidencia_escenario_tc52_TC-M06-G119.json` | Evidencia histórica TC-M06-52 (evento **7098**) |
| `_arch/` | Archivo de preparación, 1.ª evaluación, auditoría previa y docs parciales (no borrar) |

## Hallazgos clave

- Cotización **6** → `ANULADA` v2 · evento **25569** `COTIZACION_ANULADA`
- 2.º intento → HTTP **422** `COTIZACION_NO_MODIFICABLE` · sin segundo evento
- Cotización **7** → `VENCIDA` v2 · evento **7098** `COTIZACION_VENCIDA` (actor `SISTEMA`)
- Activos **1570 / 1571** → `ACTIVO`, VR **$3.760.000** · período **220** `ABIERTO`

## Scripts (raíz del caso)

- `_ejecutar_tc51_autorizado.py` — ejecución autorizada TC-51
- `_inspeccion_g119_readonly.py` / `_auditoria_final_g119_readonly.py` — solo lectura
- `ejecutar_tc_m06_g119.py` — orquestación histórica
- Colección Postman + `ejecutar_newman.ps1` (sin secretos en el environment)
