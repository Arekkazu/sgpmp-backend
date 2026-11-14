# Diagnóstico de despliegue #1024 en TEST

**Fecha:** 2026-11-13 (UTC)  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Alcance:** solo lectura (sin POST de cotizaciones)

## 1. Corrección verificada

| Campo | Valor |
|---|---|
| Commit | `29512934f10e83c6904fbd4aeddec24086640947` |
| Merge PR #1024 | `e84650d37464db79e35d69d58f45c5aed7c78b60` |
| Archivo | `registrar_cotizacion_use_case.py` |
| Comportamiento | Tras `periodo_para`, si `not periodo.contiene(hoy)` → HTTP 422 `PERIODO_CONTABLE_CERRADO` sin insertar |

Confirmado en el diff del commit (INC-M06-332-G88 / RF-COT FA-3), no confundido con otros ítems del lote.

## 2. Señales del ambiente TEST

| Señal | Resultado |
|---|---|
| `GET /health` | 200 `{status, message}` — sin SHA |
| `GET /version` | 404 |
| Headers | sin `x-git-sha` / version commit |
| OpenAPI `info.version` | `1.0.0` (no identifica release) |

## 3. Cadena de evidencia

1. **Mismo commit** `29512934` introdujo:
   - filtros OpenAPI de auditoría `id_usuario`, `origen_registro`, `id_referencia`;
   - el check `PERIODO_CONTABLE_CERRADO` de cotizaciones.
2. **TEST en vivo** expone hoy esos tres filtros en `GET /finanzas/auditoria` (OpenAPI).
3. **`origin/test`** contiene `29512934` y `e84650d3`; el archivo en esa punta incluye el check FA-3.
4. Tags `v1.4.0-rc.52` … `rc.59` contienen el fix (`git tag --contains`).
5. No hay evidencia de un revert posterior del check en `origin/test`.

## 4. Separación de estados

| Estado | ¿Cumple? |
|---|---|
| Integrado en `dev` | Sí |
| Incluido en release (rc.52+) | Sí |
| Desplegado en TEST (proceso en ejecución) | Sí, por huella OpenAPI del mismo commit + presencia en `origin/test` |

## 5. Dictamen

**CONFIRMADO_DESPLEGADO**

Residual: TEST no publica el SHA del proceso; la certeza se basa en la huella OpenAPI del mismo commit atómico que contiene el fix de cotización, no en un endpoint `/version`.
