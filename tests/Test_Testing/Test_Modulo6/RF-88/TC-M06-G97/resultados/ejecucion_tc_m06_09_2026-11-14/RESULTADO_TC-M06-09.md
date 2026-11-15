# Resultado TC-M06-09

**Caso:** TC-M06-G97 / TC-M06-09  
**Fecha ejecución (UTC):** 2026-11-14T06:41:19.080176+00:00  
**Commit:** `3995b923` · rama `laura`  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Resultado:** **APROBADO**

## Solicitud

| Campo | Valor |
|---|---|
| Método | GET |
| URL | `https://api.inmero.co/api-sgpmp-test/finanzas/activos/1858/depreciacion?fecha=2027-11-12` |
| Headers | `Accept: application/json`, `X-Zona-Horaria: America/Bogota`, `Authorization: Bearer ***` |
| HTTP | **200** |

## Precondiciones

- Activo **1858** presente, valoración al costo activa.
- Costo **1700000**, vida **60**, adquisición **2026-11-12**, registrada **0**.
- Permiso `valoracion_por_costo` R confirmado.
- Baseline registrada: depreciación `0.0000`, líneas `1`.

## Valores obtenidos

| Campo | Valor |
|---|---|
| depreciacion_anual | 340000.0000 |
| depreciacion_acumulada | 340000.0000 |
| valor_contable | 1360000.0000 |
| depreciacion_registrada | 0.0000 |
| meses_transcurridos | 12 |
| fecha_adquisicion | 2026-11-12 |
| fecha_calculo | 2027-11-12 |
| vida_util_meses | 60 |
| costo_adquisicion | 1700000.0000 |

## Side-effect

| Campo | Antes | Después |
|---|---|---|
| depreciacion_acumulada (persistida) | 0.0000 | 0.0000 |
| valor_contable_por_costo | 1700000.0000 | 1700000.0000 |
| lineas contables | 1 | 1 |

## Aserciones

Ver `ASERCIONES_TC-M06-09.md` — 7 PASS / 0 FAIL.

## Alcance G97 (snapshot al momento de esta corrida)

> **Histórico:** este apartado refleja el estado del grupo **al cerrar solo TC-M06-09** (08 aún pendiente).  
> **Estado vigente del grupo:** ver `../estado_oficial_G97.json` y `../DICTAMEN_FINAL_G97.md` → **G97 APROBADO** (08+09).  
> El resultado del escenario TC-M06-09 permanece **APROBADO** e intacto.

- TC-M06-09: **APROBADO**
- TC-M06-08: **NO EJECUTADO** *(en ese momento; ejecutado después — ver `../ejecucion_tc_m06_08_2026-11-14/`)*
- Estado grupo en este snapshot: **PARCIALMENTE_EJECUTADO** *(superado)*
