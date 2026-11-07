# 08 — Cambios locales rev5 (post-implementación)

G94 **no** se marca APROBADO. Rev4 intacta.

## Archivos creados

- `analisis_TC-M09-G94/07_propuesta_rev5.md` — diagnóstico y plan (antes del spec).
- `analisis_TC-M09-G94/08_cambios_rev5.md` — este inventario.
- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev5_test.cy.js`
- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev5.cjs`
- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/G94-rev5-179-NO_EJECUTADO.md`

## Archivos no modificados (histórico)

- Spec y config rev4.
- `Resultados/G94-rev4-*`, `TC-M09-G94_179_rev4_test.json|.html`.
- `src/**`, otros casos, configs de TEST.

## Ejecución

Ejecutada el 2026-10-10. Detalle: `09_ejecucion_rev5.md`. Mocha oficial FAIL. G94 sigue RECHAZADO.

## Cómo reejecutar (si hay fila RF-26 en GET identidad finca 1)

Desde `sgpmp-backend`, con `CYPRESS_contrasena` o `--env contrasena=...` (no commitear el secreto):

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev5.cjs --env contrasena=***
```

Ventana exclusiva sobre identidad finca 1 y tema del productor id=2. Tras la corrida, el restore del `after` debe dejar snapshot; si Mocha falla el hook, TEST puede quedar alterado y hay que restaurar con un POST `/sesiones/` **nuevo** (nunca el Bearer del `it`).
