# TC-M06-29 — Criterios definitivos (RF-89 v1.2)

**Grupo:** TC-M06-G104 (TC-M06-25 y TC-M06-26 **sin cambio**)  
**Escenario:** precio **492**, especie **544**, activo **1644**, vencimiento **2026-11-10**  
**Normativa:** RF-89 v1.2 · RFC-024 C24.5 · RFC-026 C26.4 (contexto de evolución del RF) · FA-5 · CA-8  
**Fecha de cierre documental:** 2026-11-13  
**Sustituye operativamente a:** `criterios_tc_m06_29_rf89_v1_1.md`

## Objetivo y alcance delimitado

**Objetivo de TC-M06-29 (alcance de cierre):** validar el ciclo de vida del precio al vencer **sin reemplazo** y la **exclusión** de ese precio de los cálculos de simulación, conforme a RF-89 v1.2 (bloque condición sin precio / RFC-024 C24.5).

**Fuera del alcance de cierre de este subcaso (validación complementaria):** la demostración del aviso diario al Contador (CA-8 / FA-5). Esa obligación normativa **permanece vigente** en RF-89 v1.2, pero se registra como **pendiente de evidencia independiente** (no se afirma cumplida). Ver `resultados/tercera_evaluacion/VALIDACION_COMPLEMENTARIA_CA8_AVISO_DIARIO_PENDIENTE.md`.

Justificación de la delimitación:

- El agrupado original G10 centra TC-M06-25/26/29 en el **ciclo de vida** del precio (PROGRAMADO → ACTIVO → vencido sin reemplazo).
- El enunciado v1.0 pedía `SIN_PRECIO_VIGENTE` **y** “notificación **o** activación RF-88”; RFC-024 retiró estado/`PRECIO_REFERENCIA_VENCIDO`/RF-88 por vencimiento.
- La evidencia de lectura ya demuestra vencimiento + exclusión (`SIN_PRECIO`); la notificación **no** está demostrada.
- Separar CA-8 evita mantener abierto el subcaso por criterios retirados v1.0 y evita fingir que CA-8 está probado.

## Criterios de aceptación del alcance de cierre (obligatorios)

| # | Criterio | Evidencia |
|---|---|---|
| 1 | Precio 492 VENCIDO (2026-11-10) sin reemplazo aplicado | `GET /finanzas/precios?id_especie=544` |
| 2 | Activo 1644 ACTIVO, especie 544, contexto del precio 492 | `GET /finanzas/activos/1644` |
| 3 | Simulación no usa el precio vencido: motivo **`SIN_PRECIO`**, `es_valido=false` | `GET /finanzas/activos/1644/simulacion` |

## Criterios retirados (no evaluar)

- `SIN_PRECIO_VIGENTE` como estado del activo  
- Evento `PRECIO_REFERENCIA_VENCIDO`  
- Activación de RF-88 por vencimiento  

## Validación complementaria (no bloquea el AC delimitado)

| ID | Criterio RF-89 v1.2 | Estado |
|---|---|---|
| CA-8 / FA-5 | Aviso diario al Contador: precio venció sin reemplazo | **PENDIENTE DE EVIDENCIA** |

## Dictamen del subcaso

**APROBADO (alcance delimitado)** — criterios 1–3 con evidencia de lectura existente.  
CA-8 no forma parte del veredicto de cierre de este subcaso; queda pendiente y trazada.  
G104 **no** se declara completamente aprobado mientras la validación complementaria CA-8 siga pendiente a nivel de grupo/RF-89.
