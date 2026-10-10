# 25 — Ejecución Cypress TC-M09-179 rev10 TEST

**G94 permanece RECHAZADO.** Una sola corrida. Cypress 14.5.4 / Electron 130. Exit **1**.

Precondiciones OK: spec `tc_m09_g94_179_rev10_test.cy.js` y `cypress.config.179.rev10.cjs`; `node --check` exit 0; reporter `TC-M09-G94_179_rev10_test`; capturas `screenshots-179-rev10-test`; JSON con prefijo `G94-rev10-179-`; diagnóstico persistido antes de aserciones; admin GET identidad espera objeto de contrato (sin intercept de identidad); snapshot + restore (PATCH solo si `theme_mode ≠ 2`; restore omite si no hubo PATCH). `CYPRESS_contrasena` presente (valor no documentado).

Las correcciones de `useTemaSesion` / `--sidebar-muted` **no se asumen en TEST**. Esta corrida las contradice en el bundle desplegado.

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev10.cjs
```

Mocha: 1 test, 0 pases, 1 fallo, **10405 ms**, `2026-10-10T16:01:26.718Z`–`16:01:37.123Z`.

---

## Tema e identidad

### Identidad visual del administrador

`GET /configuracion/identidad-visual/1` (solo lectura): **HTTP 200**, `body_nulo: false`.

| Campo | Valor observado |
|---|---|
| `id_finca` | `1` |
| `id_identidad_visual` | `1` |
| `primary_color` | `#1A6B3C` |
| `tiene_accesibilidad` | `true` |

La aserción de contrato (objeto, `id_finca`, `id_identidad_visual` number) **pasó**. No hay intercept que simule la respuesta. No se hizo PATCH de identidad.

### Dashboard y tema DOM

La prueba **sí llegó** a `/dashboard` (login productor UI HTTP 200).

| Momento | `pathname` | `html data-theme` | `body data-theme` |
|---|---|---|---|
| Diagnóstico temprano (antes de esperar dark) | `/dashboard` | **null** (`html_has_data_theme: false`) | null |
| Tras espera `THEME_WAIT_MS` (20 s) | `/dashboard` | **`dark`** (asociación cumplida) | null |
| Cierre del `it` | `/dashboard` | **`dark`** | null |

Origen TEST: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io/dashboard`.

GET tema en el navegador: **HTTP 200**, `error_code` null. Refresh: **0** llamadas.

Tema personal al snapshot: `theme_mode=2`, `fuente=personal`, `id_tema_visual=2`. **No se PATCH** (ya estaba oscuro).

---

## Colores y contraste

Contexto productor (API, finca 1, usuario 2):

| Dato | Valor |
|---|---|
| `primary_color` | `#1A6B3C` |
| Oscuro `cumple_aa` | `false` (ratio API 2.69 vs `#171A15`) |
| Oscuro `color_ajustado` | **`#249453`** (esperado en `--brand-500`) |
| Claro `color_ajustado` | `#1A6B3C` |

### `--brand-500` en el navegador

| | |
|---|---|
| Inline / computed | `#1A6B3C` |
| Normalizado | `#1A6B3C` |
| Esperado API oscuro | `#249453` |
| Comparación | **No coincide** (`coincide_oscuro: false`; `coincide_crudo: true`; `coincide_claro: true`) |
| Fondo medido | `--surface-card` `#171A15` |
| Ratio `--brand-500` vs fondo | **2.69:1** (< 4.5) |

El umbral **4.5:1 no se rebajó**. El fallo Mocha que abortó el `it` fue la igualdad hex:

`--brand-500 = color_ajustado oscuro: expected '#1A6B3C' to equal '#249453'`

Las aserciones posteriores (`ratio >= 4.5`, axe 0, sidebar 4.5) **no se evaluaron en Mocha** porque el `expect` de marca falló primero. Aun así **sí se midieron** CSS, sidebar (`getComputedStyle`) y axe **antes** de esas aserciones.

Esto **no prueba** que el frontend local esté en TEST: el bundle sigue inyectando el primario / variante clara con `data-theme=dark`.

### Cuatro nodos sidebar (rev8)

`getComputedStyle` del spec devolvió `backgroundColor: rgba(0,0,0,0)` (transparente). El harness convierte eso a `#000000` y un ratio **6.75:1** que **no es el fondo real**. No se usa como cumplimiento AA.

**Fuente de contraste: axe** (fondo compuesto):

| Selector | Texto | fg | bg (axe) | Ratio axe | Esperado | Resultado |
|---|---|---|---|---|---|---|
| `.ds-sidebar__logo-sub` | Finca Acuícola El Remanso | `#7d9a75` | `#104325` | **3.64:1** | 4.5:1 | **incumple** |
| `.ds-sidebar__section:nth-child(2) > .ds-sidebar__section-label` | Módulos | `#7d9a75` | `#104325` | **3.64:1** | 4.5:1 | **incumple** |
| `.ds-sidebar__section:nth-child(4) > .ds-sidebar__section-label` | Mi cuenta | `#7d9a75` | `#104325` | **3.64:1** | 4.5:1 | **incumple** |
| `.ds-sidebar__user-role` | Productor | `#7d9a75` | `#104325` | **3.64:1** | 4.5:1 | **incumple** |

Mismo par que rev8. El token local `--sidebar-muted: #B8D4AE` **no está** en el CSS servido por TEST.

### axe

- Ejecutado: **sí**
- `color-contrast` violations: **1** (4 nodos)
- Nodos que pasan color-contrast: 15
- Criterio original (0 violaciones): **no cumplido**

No se forzaron estilos desde Cypress.

---

## Integridad y resultado

| | |
|---|---|
| Exit Cypress | **1** |
| Mocha | 1 test, 0 passing, 1 failing, ~10 s |
| Último paso | `aserciones` |
| Causa observada | `--brand-500` pintado `#1A6B3C` (primario / claro) con `html[data-theme=dark]`; API pedía `#249453` |
| Escrituras | snapshot, contexto, tema-sin-patch, diagnósticos, CSS, sidebar, axe, refresh, último-paso, estado-tema-final, restore omitido |
| PATCH tema | **no** (`theme_mode` ya 2) |
| Restore | omitido (`no hubo PATCH de tema personal`) |
| Refresh / 401 | ninguno |
| Auth | login admin y productor 200 |

Criterios **sí verificados** y fallidos: marca oscura en `--brand-500`; ratio marca vs `#171A15`; axe 0; AA de los cuatro textos del sidebar (vía axe).

Criterios de arnés **cumplidos**: admin objeto; dashboard; espera `data-theme=dark`. Eso no aprueba G94.

TC-M09-178 no se reejecutó en este ciclo. G94 exige evidencia satisfactoria de **178 y 179**.

---

## Rutas exactas

Base: `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/`

- `TC-M09-G94_179_rev10_test.json`
- `TC-M09-G94_179_rev10_test.html`
- `G94-rev10-179-ejecucion.txt`
- `G94-rev10-179-admin-identidad-diseno.json`
- `G94-rev10-179-snapshot-tema.json`
- `G94-rev10-179-contexto-antes.json`
- `G94-rev10-179-tema-sin-patch.json`
- `G94-rev10-179-diagnostico-temprano.json`
- `G94-rev10-179-diagnostico.json`
- `G94-rev10-179-ubicacion.json`
- `G94-rev10-179-css-despues.json`
- `G94-rev10-179-sidebar-nodos.json`
- `G94-rev10-179-axe.json`
- `G94-rev10-179-refresh.json`
- `G94-rev10-179-ultimo-paso.json`
- `G94-rev10-179-estado-tema-final.json`
- `G94-rev10-179-restore.json`
- `screenshots-179-rev10-test/tc_m09_g94_179_rev10_test.cy.js/G94-rev10-179-dashboard-dark-variante.png`
- `screenshots-179-rev10-test/tc_m09_g94_179_rev10_test.cy.js/TC-M09-179 rev10 TEST -- TC-M09-179 aplica color_ajustado oscuro en --brand-500 con data-theme=dark (failed).png`

No hay `verificacion-final.json` (restore no aplicó PATCH). Rev9 y anteriores no se modificaron. Sin segunda ejecución. Sin commit/push/merge/despliegue.

---

## Decisión

| Criterio | Resultado |
|---|---|
| Identidad admin (contrato objeto) | OK en TEST |
| Dashboard + `data-theme=dark` | OK |
| `--brand-500` = `color_ajustado` oscuro | **Fallo** (`#1A6B3C` ≠ `#249453`) |
| Ratio marca ≥ 4.5 | **Fallo** (2.69:1) |
| axe color-contrast = 0 | **Fallo** (1 violación, 4 nodos 3.64:1) |
| Frontend TEST = correcciones locales | **No.** El despliegue no refleja el cambio. |
| G94 | **RECHAZADO** |
