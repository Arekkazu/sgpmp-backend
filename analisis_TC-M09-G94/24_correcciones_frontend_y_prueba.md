# 24 — Correcciones locales de frontend y prueba (G94)

**Estado de G94:** RECHAZADO. Este informe documenta correcciones locales; **no** constituye aprobación ni prueba de que el despliegue TEST ya las incluye.

**Alcance de este ciclo:** implementación y revisión local. No se ejecutó Cypress contra TEST. No hay commit ni push. No se modificó RLS ni permisos. No se tocó producción ni datos TEST.

**Aviso de paquete:** el frontend en `SGPMP-FRONT-END-PWA` **no es el bundle desplegado en TEST**. TEST inyecta `--brand-*` en línea, el subtítulo del sidebar es el nombre de finca (no el texto local “Sistema Pecuario”) y el fondo observado en rev8 fue `#104325`, distinto de `--neutral-900` (`#141610`) y de `[data-theme=dark] .ds-sidebar` (`#0A0C09`) de este repositorio. **No se afirma que el despliegue TEST esté corregido.** Hasta que este código (o equivalente) se despliegue, G94 en TEST puede seguir fallando por tema y contraste.

---

## 1. Archivos modificados

### Frontend (`SGPMP-FRONT-END-PWA`)

| Archivo | Tipo |
|---|---|
| `src/shared/tema/useTemaSesion.ts` | sincronización `data-theme` + marca |
| `src/shared/hooks/useTheme.ts` | observación de `data-theme` |
| `src/configuration/hooks/useTemaVisual.ts` | `colorMarcaActivo` / `aplicarMarcaTema` |
| `src/configuration/hooks/useTemaVisual.test.ts` | unitario local (nuevo) |
| `src/shared/hooks/useTheme.test.ts` | unitario local (nuevo) |
| `src/setupTests.ts` | `matchMedia` con `addEventListener` |
| `src/App.tsx` | `useTemaSesion()` en `AppShell` |
| `src/shared/design-system/tokens.css` | token `--sidebar-muted` |
| `src/shared/design-system/Sidebar.css` | textos muted del sidebar |

### Prueba (backend repo, specs exclusivos)

| Archivo | Tipo |
|---|---|
| `tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev10_test.cy.js` | spec nuevo |
| `tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev10.cjs` | config nueva |

**Intactos:** `tc_m09_g94_179_rev9_test.cy.js`, `cypress.config.179.rev9.cjs`, evidencias históricas rev1–rev9, RLS, intercepts de identidad.

---

## 2. Causa confirmada y corrección por archivo

### A. Spec de identidad visual (rev9 → rev10)

**Causa (rev9, Mocha ~2 s):** la precondición exigía `GET /identidad-visual/{finca}` con `admin@pecuaria.co` y `body === null`. El contrato `IdentidadVisualResponse` admite objeto o nulo; Alex confirmó que el admin **está vinculado a la finca 1** y ahora recibe el objeto real (`id_identidad_visual`, `id_finca`, …). La aserción `null` era incorrecta para el estado actual; no era un fallo de RLS a “arreglar”.

**Corrección (solo rev10):** se persiste `G94-rev10-179-admin-identidad-diseno.json` **antes** del `expect`. Se exige HTTP 200, cuerpo objeto no nulo, `id_finca === 1`, `id_identidad_visual` number. Si `primary_color` viene informado, se valida formato `#RRGGBB`; **no se inventa el hex**. No hay intercepts. Login, 401/403 y el resto de autorización se conservan. No hay PATCH de identidad.

### B. Sincronización de tema

**Causa (rev7–rev8):** TEST pintó `--brand-500` del primario / `claro.color_ajustado` (`#1A6B3C`) con `data-theme=dark` o el atributo quedó `null`. El hook de sesión no reaccionaba a cambios de `data-theme` hechos por el AppBar (`useTheme.toggle` → `setAttribute`) ni reaplicaba `oscuro.color_ajustado` (`#249453` en evidencias de contexto) sin recarga.

**Corrección:**

- `useTemaVisual.ts`: elige `accesibilidad.primary_color.{oscuro|claro}.color_ajustado` según el tema efectivo; si falta, cae al `primary_color`. Escribe `--brand-500`, `--brand-cta`, `--brand-600`. No fuerza un color fijo ni elimina el cálculo de `color_ajustado`.
- `useTemaSesion.ts`: con token, GET `/configuracion/personalizacion/tema` y `/configuracion/interfaz/contexto`. Aplica `data-theme` una vez desde `theme_mode` (1 claro, 2 oscuro, 3 sistema vía `prefers-color-scheme`). `MutationObserver` sobre `html[data-theme]` reaplica marca. Limpieza al desmontar. Modo Sistema: listener `matchMedia` `change`.
- `useTheme.ts`: solo escribe `data-theme` si el valor difiere (evita bucles). Observer sincroniza `dark` si el atributo cambia fuera del toggle. Disconnect al desmontar.
- `App.tsx`: `AppShell` llama `useTemaSesion()`.

### C. Contraste sidebar (rev8)

**Causa:** axe color-contrast, 4 nodos, `#7D9A75` sobre `#104325`, ratio **3.64:1** (esperado 4.5:1, texto normal 9–10 px). Independiente de marca vs blanco.

**Corrección en fuente:** `--sidebar-muted: #b8d4ae` en `:root` y `[data-theme=dark]`. `.ds-sidebar__logo-sub`, `.ds-sidebar__section-label`, `.ds-sidebar__user-role` (y logout, mismo muted) usan el token. No se debilitó axe ni se cambiaron selectores Cypress para ocultar el fallo.

---

## 3. Cómo se sincroniza ahora el tema

1. Tras login, `useTemaSesion` lee `theme_mode` y contexto (identidad + `accesibilidad`).
2. Si el modo es 1/2, fija `data-theme` a `light`/`dark`. Si es 3 (Sistema), usa `prefers-color-scheme` y reacciona a cambios del SO.
3. `aplicarMarcaTema` pinta `--brand-*` con `color_ajustado` del tema **activo**.
4. El botón del AppBar (`useTheme.toggle`) cambia `data-theme`. El observer de sesión vuelve a aplicar la variante de marca **sin recargar**.
5. El observer de `useTheme` alinea el estado `dark` si otro escritor cambió el atributo.
6. `setDark` / `setAttribute` solo si el valor cambió → no hay bucle de observers. Un observer por hook; `disconnect` + `removeEventListener` en cleanup.

Comprobado en unitario local: `colorMarcaActivo('dark')` → `#249453`; `'light'` → `#1A6B3C`; `useTheme` pasa a `dark` cuando el atributo cambia fuera del toggle. **No demostrado en TEST** (Cypress no ejecutado).

---

## 4. Ratios de los cuatro textos del sidebar

Los cuatro nodos usan el mismo color de texto muted y el mismo fondo de `.ds-sidebar`, por tanto **el mismo ratio**.

Fórmula WCAG 2.x (luminancia relativa sRGB, umbral 0.04045, `(L1+0.05)/(L2+0.05)`), calculada con Node sobre los hex del CSS local y el par de rev8.

| Tema / fondo | Texto | Fondo | Ratio | AA 4.5:1 |
|---|---|---|---|---|
| Claro local (`background: var(--neutral-900)` = `#141610`) | `#B8D4AE` | `#141610` | **11.34:1** | cumple |
| Oscuro local (`[data-theme=dark] .ds-sidebar` = `#0A0C09`) | `#B8D4AE` | `#0A0C09` | **12.22:1** | cumple |
| Fondo TEST observado rev8 | `#B8D4AE` | `#104325` | **7.06:1** | cumple *si TEST adopta este texto* |
| Par fallido rev8 (histórico) | `#7D9A75` | `#104325` | **3.65:1** | no cumple |

Los cuatro selectores: `.ds-sidebar__logo-sub`, `.ds-sidebar__section:nth-child(2) > .ds-sidebar__section-label`, `.ds-sidebar__section:nth-child(4) > .ds-sidebar__section-label`, `.ds-sidebar__user-role`.

**No medido en el navegador TEST** (sin Cypress). Si TEST no despliega `--sidebar-muted` / este CSS, el ratio en axe seguirá siendo el de rev8.

---

## 5. Comprobaciones locales y resultados

| Comprobación | Resultado |
|---|---|
| `node --check` spec y config rev10 | OK (exit 0) |
| `npx tsc --noEmit` (frontend) | OK (`TSC_EXIT=0`) |
| `npx vitest run` `useTemaVisual.test.ts` + `useTheme.test.ts` | 5/5 PASS (sin red, sin TEST) |
| `npx eslint` sobre archivos tocados | No hay `eslint.config.*` en el frontend; ESLint 9 sale 2. No se interpretó como fallo de producto. |
| Cypress contra TEST | **No ejecutado** (instrucción) |

Rev9 no se reescribió: sigue conteniendo `expect(idRes.body).to.eq(null)`.

---

## 6. Criterios aún no demostrados

- Precondición admin GET identidad objeto en TEST (rev10 no corrido).
- `html[data-theme=dark]` tras PATCH tema personal del productor, sin forzar el atributo.
- `--brand-500` / CTA igual a `oscuro.color_ajustado` del contexto, sin recarga.
- axe `color-contrast` 0 violaciones en dashboard productor oscuro (G94-179).
- Restauración del `theme_mode` previo sin 401.
- Que TEST sirva este frontend.

G94 **no** está aprobado.

---

## 7. Qué validar en la siguiente ejecución controlada

Pendiente de autorización explícita:

```text
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev10.cjs
```

Comprobar en evidencias (sin debilitar 4.5:1 ni axe 0):

1. JSON admin identidad: HTTP 200, objeto, `id_finca=1`, `id_identidad_visual` numérico (no nulo).
2. Diagnóstico temprano y `data-theme=dark` tras el PATCH de tema (timeout existente).
3. CSS `--brand-500` alineado a `accesibilidad.primary_color.oscuro.color_ajustado` (hex del GET contexto, no un valor inventado).
4. Axe 0 en los cuatro nodos del sidebar (y resto del dashboard).
5. After-hook: restore tema productor 200, no 401.
6. Si el CSS TEST del sidebar no es `#B8D4AE` sobre el fondo real, el fallo de contraste **sigue siendo de despliegue**, no del spec.

Hasta esa corrida y, si hace falta, el despliegue del frontend local, **G94 permanece RECHAZADO**.
