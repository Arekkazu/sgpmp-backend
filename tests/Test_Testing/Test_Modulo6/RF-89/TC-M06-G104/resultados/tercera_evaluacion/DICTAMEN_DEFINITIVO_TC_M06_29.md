# Dictamen definitivo — TC-M06-29 (RF-89 v1.2)

**Fecha de cierre documental:** 2026-11-13  
**Estado oficial del subcaso:** **APROBADO (alcance delimitado)**  
**Archivo de estado oficial del grupo:** `estado_oficial_G104.json`

## 1. Trazabilidad normativa

| Versión | Efecto sobre TC-M06-29 |
|---|---|
| RF-89 v1.0 | Diseño original: `SIN_PRECIO_VIGENTE` + notificación **o** RF-88 → originó el **RECHAZADO** histórico |
| RF-89 v1.1 / RFC-024 C24.5 | Retira estado/`PRECIO_REFERENCIA_VENCIDO`/RF-88 por vencimiento; simulación `SIN_PRECIO`; aviso Contador (CA-8) |
| RF-89 v1.2 + RFC-026 C26.4 | Versión vigente del RF (evolución posterior, p. ej. correcciones); **no** restituye los criterios v1.0 retirados por C24.5 |
| RF-88 v2.0 | Reconocimiento inicial sin precio; **no** aplica al vencimiento de un activo ya reconocido |

## 2. Comportamientos evaluados

### A. Vencimiento y exclusión del precio — **APROBADO**

Evidencia reutilizada (sin nuevas consultas): `tercera_evaluacion/evidencia_verificacion_lectura_tc_m06_29.json` y reiteraciones en investigación (solo lectura).

| Observación | Resultado |
|---|---|
| Precio 492 `VENCIDO`, venc. 2026-11-10, sin reemplazo aplicado | Cumple |
| Activo 1644 ACTIVO, especie 544 / precio 492 | Cumple |
| Período 266 ABIERTO (contexto) | Cumple |
| Simulación: `es_valido=false`, motivo `SIN_PRECIO`, sin uso del precio vencido | Cumple |

### B. Notificación diaria al Contador (CA-8 / FA-5) — **NO DEMOSTRADA**

- Bandeja Contador: sin aviso identificable del precio 492.  
- Job diario 11/11 UTC: ejecución no confirmada.  
- **No** se inventan logs ni notificaciones.  
- Registrada como **validación complementaria pendiente** (`VALIDACION_COMPLEMENTARIA_CA8_AVISO_DIARIO_PENDIENTE.md`), fuera del alcance de cierre de TC-M06-29.

### C. Criterios v1.0 — **retirados** (no fundamentan el dictamen)

Conservados solo como antecedente en `tercera_evaluacion/dictamen_historico_rechazo_rf89_v1_0.md` (RECHAZADO histórico).

## 3. Alcance exacto de lo aprobado

Se aprueba que, en TEST y con el escenario 492/544/1644:

1. El precio queda efectivamente **VENCIDO** sin reemplazo vigente.  
2. El activo no requiere estado `SIN_PRECIO_VIGENTE`.  
3. La simulación **excluye** el precio vencido y responde **`SIN_PRECIO`**.

**No** se aprueba la entrega del aviso diario al Contador.

## 4. Limitaciones y pendientes

- CA-8 / FA-5 pendiente de evidencia (Dev/Ops: `SOLICITUD_EVIDENCIA_JOB_DIARIO_DEV_OPS_TC_M06_29.md`).  
- Excel de casos (`casos de prueba modulo 6.xlsx`) sigue con enunciado v1.0; la versión operativa en repo es `criterios_tc_m06_29_rf89_v1_2.md`.  
- G104 no se declara 100 % cerrado a nivel de obligaciones RF-89 del grupo mientras CA-8 complementaria siga abierta.

## 5. Qué determina el estado oficial

No hay CI automatizada que fije el veredicto. El **estado oficial** queda en:

1. `resultados/estado_oficial_G104.json`  
2. Este dictamen  
3. `criterios_tc_m06_29_rf89_v1_2.md`  

`segunda_evaluacion/resumen_ejecucion_TC-M06-G104.json` conserva la corrida del 2026-11-10 (25/26 APROBADO; 29 aún “PREPARADO…”) y **no** se reescribe para no alterar el historial de 25/26.
