# Resumen — harness G45 local 2026-10-31

**G45 no se declara aprobado.**

| Campo | Valor |
|---|---|
| Intérprete | Python 3.13.7 |
| PYTHONPATH | `.worktrees/sgpmp-rf55-validation/raspberry` |
| Código de retorno | **1** |
| `resultado_local.json` | **no generado** |
| stdout | vacío |
| Detención | sí (no se parcheó el harness) |

## Error exacto

```
NameError: name 'v' is not defined
  harness_g45.py line 177, in correr_escenario
    "valor": None if v is None else (v if isinstance(v, bool | str) else v)
```

El bucle es `for r, motivo in invalidas` y el informe referencia `v`, que no existe. Fallo del **código de reporte del harness**, no un veredicto RF-55.

`Agent.tick` de **P1** llegó a ejecutarse (el traceback es *después* de los ticks). El dict de salida no se construyó. P2–P4 **no** se lanzaron.

No es error de importación del firmware. No es MQTT ni systemd.

## Esperado vs obtenido

| ID | Esperado (propuesta) | Obtenido | Veredicto |
|---|---|---|---|
| P1 | HR `LECTURA_INVALIDA`; T `DESVIACION_SIMPLE` CRITICO; telemetría 32.5; 1 evento T | sin JSON (NameError al serializar P1) | **NO EVALUADO** |
| P2 | 2× `LECTURA_INVALIDA`; 0 eventos; 0 telemetría | no ejecutado | **NO EVALUADO** |
| P3 | 2× inválida HR/pH; T DESVIACION CRITICO; telemetría T+150+20 | no ejecutado | **NO EVALUADO** |
| P4 | OD inválido; T DESVIACION CRITICO; telemetría solo T | no ejecutado | **NO EVALUADO** |

| | |
|---|---|
| Escenarios PASS | **0** |
| Escenarios FAIL (criterio RF-55) | **0** |
| Escenarios no evaluados | **4** |
| Ejecución del harness | **FAIL** (exit 1) |

Historial, eventos, telemetría y severidad **no** quedan contrastados con evidencia serializada.

Siguiente paso (cuando se autorice): corregir solo la variable `v` en el reporte del harness y reejecutar en local. No se hizo en esta corrida.
