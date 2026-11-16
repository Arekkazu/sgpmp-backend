# Resultados TC-M06-G97

**Dictamen:** APROBADO (TC-M06-08 + TC-M06-09 · 18/18 aserciones).  
**RF:** RF-88 · CU07  
**Commit evidencia:** `3995b923` · rama `laura`  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`

## Estructura

```
resultados/
├── README.md
├── REPORTE_FINAL_G97.html           # informe HTML consolidado
├── DICTAMEN_FINAL_G97.md
├── estado_oficial_G97.json
├── matriz_trazabilidad_G97.md
├── ejecucion_tc_m06_08_2026-11-14/  # evidencia oficial TC-M06-08
│   └── REPORTE_TC-M06-08.html
├── ejecucion_tc_m06_09_2026-11-14/  # evidencia oficial TC-M06-09
│   └── REPORTE_TC-M06-09.html
└── evaluaciones/                    # historial (no reescrito)
    ├── diagnostico_previo/
    ├── reevaluacion_pr1118/
    ├── auditoria_reevaluacion_2026-11-14_pr1121/
    └── preparacion_funcional_2026-11-14/
```

## Informes HTML

| Informe | Ruta | Contenido |
|---|---|---|
| Consolidado G97 | `REPORTE_FINAL_G97.html` | Dictamen grupo, 18/18, trazabilidad |
| Individual 08 | `ejecucion_tc_m06_08_2026-11-14/REPORTE_TC-M06-08.html` | 11/11, HTTP 422, `VIDA_UTIL_NO_CONFIGURADA` |
| Individual 09 | `ejecucion_tc_m06_09_2026-11-14/REPORTE_TC-M06-09.html` | 7/7, HTTP 200, valores de depreciación |

Abrir directamente en Chrome (sin servidor). Cada informe incluye botón **Imprimir / Guardar PDF**.

## Fuente oficial vs snapshots históricos

| Documento | Rol |
|---|---|
| `estado_oficial_G97.json` | Estado vigente del grupo (**APROBADO**) |
| `DICTAMEN_FINAL_G97.md` | Dictamen consolidado |
| `REPORTE_FINAL_G97.html` | Informe HTML consolidado del grupo |
| `ejecucion_tc_m06_08_*/estado_ejecucion_G97.json` | Snapshot al cerrar TC-M06-08 (grupo APROBADO) |
| `ejecucion_tc_m06_09_*/estado_ejecucion_G97.json` | Snapshot histórico al cerrar solo TC-M06-09 (`PARCIALMENTE_EJECUTADO`; 08 aún pendiente entonces) |

Los JSON/MD de cada carpeta de ejecución **no se reescriben**: conservan el momento de la corrida. El estado vigente del grupo es únicamente `estado_oficial_G97.json`.

## Scripts

Los scripts de corrida viven junto a cada evidencia (`_run_tc_m06_08.py`, `_precheck_tc_m06_08.py`, `_run_tc_m06_09.py`).
