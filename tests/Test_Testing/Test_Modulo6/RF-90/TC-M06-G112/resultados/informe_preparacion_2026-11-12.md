# TC-M06-G112 — Informe de preparación (2026-11-12)

**Caso:** TC-M06-G112 (RF-90 / RF-109 / RF-93)  
**Subcasos:** TC-M06-39 (CAPITALIZAR), TC-M06-40 (GASTO)  
**Ambiente:** TEST (`https://api.inmero.co/api-sgpmp-test`)  
**Dictamen del caso:** BLOQUEADO  
**Clasificación:** MEJORA — ajuste de configuración y preparación de datos  
**Incidente relacionado:** INC-M06-328-G84 / #1015  

Inspección exclusivamente de lectura (GET + `POST /sesiones/`). No se registraron costos ni se modificó matriz, activos ni períodos.

Evidencia técnica: `inspeccion_preparacion_2026-11-12.json`.

## Validaciones

| Validación | Resultado | Observación |
|---|---|---|
| Activo 1573 | Disponible | `QA-M06O-COSTO-02`, ACTIVO, valoración por costo activa, `costos_adquisicion` / `valor_contable_por_costo` = 4.000.000, sin inversiones. |
| Período 220 | Disponible | ABIERTO (2026-11-01…30), titular 900000003. Existe costo ajeno 4448 (ALIMENTO en 1569, G110). |
| Activo 1567 | No disponible | Al costo, pero período 219 CERRADO y con depreciación de cierre. |
| Período 219 | No disponible | CERRADO el 2026-11-10T06:18:00Z. |
| Matriz CAPITALIZACION | Correcta | `MANO_OBRA_PROPIA` / `CAPITALIZACION` → D 158405 / C 250505. |
| Matriz UNICO | Pendiente | `MANO_OBRA_PROPIA` / `UNICO` sigue D 158405 (activo) / C 250505. Sin cuenta clase 5 o 7. |
| TC-M06-39 | Preparado | Condiciones OK; ejecución positiva no iniciada. |
| TC-M06-40 | Bloqueado | Matriz UNICO incorrecta; 1572 ya no está al costo; sin activo al costo alterno en período abierto. |
| RF-93 | Bloqueado | Requiere período cerrado con la inversión GASTO; no cerrar 220 ni reabrir 219. |

## Hallazgos

- **1572 (`QA-M06O-COSTO-01`):** el 2026-11-10 pasó de costo a valor razonable (`VARIACION_VR_PM`). No apto para CAPITALIZAR.
- **Contador:** permisos de `costos_activos`, `configuracion_contable` y `estado_resultados` presentes.
- **ER 219 (`id_estado` 38):** ya generado; `inversiones_llevadas_a_gasto = 0`.

## Acciones requeridas

1. Corregir y autorizar `MANO_OBRA_PROPIA` / `UNICO` con débito clase 5 o 7 y crédito 250505.
2. Entregar activo al costo aislado adicional en período ABIERTO para TC-M06-40 (distinto de 1573).
3. Proveer período aislado para verificar RF-93 sin usar 219 ni cerrar 220.

## Estado de ejecución

- TC-M06-39: PREPARADO / NO EJECUTADO.
- TC-M06-40: BLOQUEADO / NO EJECUTADO.
- Caso G112: **BLOQUEADO** (no aprobado).
