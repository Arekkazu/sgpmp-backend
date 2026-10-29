# 32 — Ejecución Cypress TC-M09-178 rev4 TEST

**Fecha/hora:** 2026-10-10, Mocha `2026-10-10T17:25:39.321Z`–`17:25:49.674Z` (UTC). Duración **10353 ms**. Cypress 14.5.4 / Electron 130.

**Corrida Mocha:** 1/1 PASS, Cypress exit **0**.

**Veredicto de cierre:** TC-M09-178 y **G94 no se marcan APROBADOS** en este informe; quedan a revisión de evidencias y cobertura global (179 rev11 ya PASS en este ciclo).

Una sola corrida. Sin PATCH, sin cambios de identidad/tema/RLS, sin commit/push/deploy. Rev3 no se sobrescribió.

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.178.rev4.cjs
```

---

## Login y dashboard

| | |
|---|---|
| Usuario | `admin@pecuaria.co` |
| Login HTTP | **200** |
| Token | presente (`token_presente: true`; valor no documentado) |
| `pathname` | `/dashboard` |
| `last_step` | `aserciones` |
| `mocha_state` | `passed` |

GET tema/contexto: solo lectura. `id_finca=1` (objeto de identidad, no null). `theme_mode=1`, `fuente=personal`.

---

## Tema y colores

| | |
|---|---|
| `html data-theme` | `light` (tema activo; no forzado) |
| `--brand-500` | `#1A6B3C` |
| Primario contexto | `#1A6B3C` |
| Claro API `color_ajustado` | `#1A6B3C` (`cumple_aa` true, ratio 6.54 vs blanco) |
| Oscuro API `color_ajustado` | `#249453` (no exigido; admin no está en oscuro) |

---

## Contraste sidebar (fondo efectivo `.ds-sidebar`)

Texto `#97B68F` sobre `#0C301B`, ratio **6.47:1** (≥ 4.5) en los cuatro nodos:

| Selector | Texto |
|---|---|
| `.ds-sidebar__logo-sub` | Finca Acuícola El Remanso |
| sección 2 label | Módulos |
| sección 4 label | Mi cuenta |
| `.ds-sidebar__user-role` | Administrador |

---

## axe

- Ejecutado: sí
- `color-contrast` violations: **0**
- Nodos en pass: **23**
- `violation_nodes`: `[]`

(`diagnostico.json` guarda `axe_violations: null` porque se escribe antes de axe; el resultado válido es `G94-178-rev4-axe.json` y `ultimo-paso.json`.)

---

## Evidencias

Base: `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/178-rev4/`

- `TC-M09-G94_178_rev4_test.json` / `.html`
- `G94-178-rev4-ejecucion.txt`
- `G94-178-rev4-login.json`
- `G94-178-rev4-contexto.json`
- `G94-178-rev4-diagnostico.json`
- `G94-178-rev4-sidebar-nodos.json`
- `G94-178-rev4-axe.json`
- `G94-178-rev4-ultimo-paso.json`
- `screenshots-178-rev4-test/tc_m09_g94_178_rev4_test.cy.js/G94-178-rev4-dashboard.png`

`Resultados/178-rev3/` intacto.

---

## Conclusión para revisión

El arnés rev4 (GET tras login) funcionó. El dashboard admin en tema **claro** cumplió axe 0 y sidebar AA en esta muestra. Eso **no** sustituye la decisión formal de G94 (178+179) hasta que se cierren las evidencias en conjunto.
