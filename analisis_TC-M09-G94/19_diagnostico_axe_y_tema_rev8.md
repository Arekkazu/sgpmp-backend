# 19 — Diagnóstico axe y `data-theme` (rev8)

**G94 permanece RECHAZADO.** Cypress no se reejecutó. Rev4–rev8 en disco no se alteraron. El spec rev8 no se modifica en esta fase.

Fuentes: `18_ejecucion_rev8.md`, `G94-rev8-179-diagnostico.json`, `G94-rev8-179-axe.json`, `G94-rev8-179-refresh.json`, `G94-rev8-179-css-despues.json`, captura `G94-rev8-179-dashboard-dark-variante.png`, Mocha HTML/JSON, `tc_m09_g94_179_rev8_test.cy.js` (`leerTokens`). El HTML de mochawesome es el **reporte**, no un dump del DOM de TEST.

---

## 1. Hechos confirmados

### 1.1 Cuatro nodos axe (`color-contrast`)

Una violación (`violations: 1`, id `color-contrast`), cuatro nodos. Mismo par de colores en todos. Umbral informado por axe: **`expectedContrastRatio: 4.5:1`**.

| # | `target` | Elemento / texto | fg | bg | Ratio axe | Tamaño / peso |
|---|---|---|---|---|---|---|
| 1 | `.ds-sidebar__logo-sub` | `<div>` «Finca Acuícola El Remanso» | `#7d9a75` | `#104325` | 3.64 | 6.8pt (**9px**), `normal` |
| 2 | `.ds-sidebar__section:nth-child(2) > .ds-sidebar__section-label` | `<span>` «Módulos» | `#7d9a75` | `#104325` | 3.64 | 6.8pt (**9px**), `normal` |
| 3 | `.ds-sidebar__section:nth-child(4) > .ds-sidebar__section-label` | `<span>` «Mi cuenta» | `#7d9a75` | `#104325` | 3.64 | 6.8pt (**9px**), `normal` |
| 4 | `.ds-sidebar__user-role` | `<span>` «Productor» | `#7d9a75` | `#104325` | 3.64 | 7.5pt (**10px**), `normal` |

15 nodos constan en `passes` de color-contrast (no listados con hex en el JSON recortado).

### 1.2 Texto normal vs grande (WCAG)

**Texto normal.** WCAG 2.1 AA pide 4.5:1 para texto normal y 3:1 para texto grande (≥18pt, o ≥14pt y negrita). Axe pidió **4.5:1**. Los tamaños son 9px y 10px, peso `normal`. No es texto grande. El 3.64:1 **incumple AA de texto normal**; cumpliría el umbral de texto grande, que **no aplica**.

### 1.3 Qué lee el spec

`leerTokens()` usa **`document.documentElement`** (`<html>`):

- `data_theme = documentElement.getAttribute('data-theme')`
- tokens inline + `getComputedStyle(documentElement)`

La aserción es `medicion.data_theme === 'dark'`. Resultado: **`null`**.

Rev4, con el mismo patrón, persistió `data_theme: "light"` (no null). Rev7 hizo `cy.get('html').should('have.attr', 'data-theme', 'dark')` y **pasó**. En TEST el atributo **sí puede** vivir en `<html>`. Un selector sistemáticamente erróneo (p. ej. solo `body`) **no** encaja con rev4/rev7.

### 1.4 Captura vs GET tema

Al persistir `diagnostico.json`, `tema_browser_log` estaba **`[]`**. Después, `refresh.json` / `ultimo-paso.json` registran **un GET tema de navegador HTTP 200**. La medición CSS ocurrió **antes** de que ese GET quedara en el log.

`--brand-500` ya era `#1A6B3C` inline en esa medición (identidad aplicada sin esperar ese GET, o desde otra petición no logueada).

### 1.5 Superficie y marca (html)

| Token | Valor |
|---|---|
| `--surface-card` computed | `#ffffff` (sin inline) |
| `html` background | `rgba(0, 0, 0, 0)` |
| `--brand-500` | `#1A6B3C` ≠ `#249453` |
| `--brand-400` | `#3F8252` (= `secondary` claro.color_ajustado del contexto) |
| `--brand-nav` | `#0c301b` |

### 1.6 Captura de pantalla

Dashboard: **panel principal claro** (fondo casi blanco, título negro «Hola, Laura», tarjeta blanca). **Sidebar verde institucional oscuro**, subtítulo de finca, «MÓDULOS», «MI CUENTA», rol «Productor». Hay un error de widgets («No se pudo cargar el dashboard»); no es el objeto de las 4 violaciones axe.

Eso **no** parece `[data-theme=dark]` del `tokens.css` local (`--surface-bg` `#0f110e`). Es coherente con chrome **claro** + sidebar siempre oscuro.

El subtítulo del logo en TEST es el **nombre de finca**, no el texto fijo local «Sistema Pecuario» (`Sidebar.tsx`). El bundle TEST **no es** este workspace.

### 1.7 Workspace local (solo contraste, no es TEST)

`useTheme` escribe `data-theme` en `documentElement` como `dark` o `light` (nunca lo deja ausente tras el `useEffect`). Sidebar local: fondo `--neutral-900`; labels `#3a5035` / `#4a6445`. TEST midió sidebar bg **`#104325`** y fg **`#7d9a75`**, distintos del CSS local.

---

## 2. Inferencias (no demostradas)

1. **`null` = atributo aún no escrito en `<html>`**, no un `query` al nodo equivocado. Encaja con: GET tema 200 **después** del `writeFile` diagnóstico; rev7 **reintentaba** hasta `data-theme=dark`; rev8 fotografió en cuanto hubo `/dashboard`.
2. **Marca `#1A6B3C` = primario / variante clara**, no `oscuro.color_ajustado`. Coherente con superficie blanca y con no tener tema oscuro aplicado en html.
3. Las **4 violaciones axe son del sidebar** (verde `#104325` + texto apagado `#7d9a75`), **no** de `--brand-500` vs `--surface-card` (ese par da 6.54:1 sobre blanco).
4. El sidebar oscuro **puede** contrastar mal **aunque** el main sea claro (en el diseño local el nav ya es oscuro en tema claro). Por eso **no** se afirma: «`data-theme=null` causó las 4 violaciones».

Relación: **coexistencia en la misma página**, no cadena causal única. Tres observaciones distintas: (a) html sin `data-theme`, (b) marca institucional cruda en `:root`, (c) labels del sidebar bajo 4.5:1 sobre verde de marca.

---

## 3. Información faltante

- Snapshot de atributos de `<html>` y `<body>` (¿`data-theme` en `body`? no hay dump).
- Instantánea del GET tema (body `theme_mode`) respecto al `writeFile` CSS.
- Estilos computados de `.ds-sidebar` (solo axe bg `#104325`).
- Si, esperando como rev7, `data-theme` pasaría a `dark` y el main dejaría de ser blanco.
- Bundle JS de TEST.

---

## 4. Causa probable (para no “arreglar a ciegas”)

**Probable (arnés + carrera):** rev8 mide `<html>` antes de que TEST asigne `data-theme`. El GET tema 200 llega tarde. No es, con la evidencia actual, un selector distinto de `documentElement`.

**Probable (producto, independiente del wait):** TEST pinta `--brand-500` con el primario / claro, no con `oscuro.color_ajustado`; el sidebar usa verde de marca + texto `#7d9a75` a 3.64:1, por debajo de AA de texto normal.

Ninguna de las dos se cierra sin otra corrida **instrumentada** (no hecha aquí).

---

## 5. Siguiente paso recomendado (no ejecutado)

No marcar G94 APROBADO. No parchear producto ni forzar `setAttribute('data-theme','dark')` desde Cypress.

Si se autoriza una **rev9** (archivos nuevos, rev8 intacta):

1. Seguir persistiendo diagnóstico **antes** de expects.
2. Registrar `html.getAttribute('data-theme')` y `body.getAttribute('data-theme')`.
3. **Después** de persistir un primer snapshot, `cy.get('html')` con timeout a `data-theme` `dark`|`light` (como rev7), segundo snapshot CSS + axe.
4. No debilitar 4.5:1 ni axe 0.
5. 178 sigue pendiente de alcance.

Hasta entonces, 179 no tiene evidencia satisfactoria de tema oscuro ni de axe 0.
