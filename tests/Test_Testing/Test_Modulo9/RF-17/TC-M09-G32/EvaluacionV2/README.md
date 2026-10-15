# TC-M09-G32 — Evaluación V2 (reevaluación TC-M09-69, RF-17 → Monitoreo)

Reevaluación de **TC-M09-69 — Verificar que una modificación de umbral actualice
la configuración utilizada por monitoreo**. Coexiste con la evaluación V1 de
`RF-17/TC-M09-G32/` (BLOCKED), que es de solo lectura.

`run-newman.cjs` es una verificación de **solo lectura** (login + GET) de la
integración RF-17 → Monitoreo en el ambiente indicado por `G32_ENV`
(`TEST` | `DEV`). Hace tres cosas:

- Captura RF17_BEFORE y MONITORING_BEFORE (dashboard e historial).
- Registra la evidencia de código de la integración: stub
  `UmbralHistoricoM09Adapter` y ausencia de lectura de tablas RF-17 fuera de
  configuración.
- Ejecuta la colección Newman con precondiciones y oráculo.

No ejecuta ningún UPDATE: el checklist previo exige una API de Monitoreo con
configuración efectiva correlacionable, y no existe.

## Ejecución

```bash
export G32_REEVAL_V2_RUN_ID=G32-REEVAL-V2-<fecha>-<hora>
export TEST_ADMIN_PASSWORD=...     # cuenta comun (nunca en archivos)
export DEV_ADMIN_PASSWORD=...      # fallback DEV admin.general (solo si G32_ENV=DEV)
NODE_PATH="$(npm root -g)" G32_ENV=TEST node run-newman.cjs
NODE_PATH="$(npm root -g)" G32_ENV=DEV  node run-newman.cjs
```

El script no sobrescribe evidencia existente.

Resultado de `G32-REEVAL-V2-20260913-021645`: **DESAPROBADO — FUNCIONALIDAD NO
IMPLEMENTADA** (FLUJO → Desarrollo; actualizar INC-M09-33-G32).
