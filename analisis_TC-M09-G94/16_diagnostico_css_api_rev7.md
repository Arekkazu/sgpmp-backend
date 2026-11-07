# 16 — Diagnóstico CSS/API tras TC-M09-179 rev7

**G94 permanece RECHAZADO.** Rev7 no se reescribe ni se reejecuta. Cypress no se corrió en esta fase.

Estado de rev7 **antes** de añadir rev8 (hechos de `15_ejecucion_rev7.md` y Mocha):

- Exit 1. `--brand-500` `#1A6B3C` ≠ `color_ajustado` oscuro `#249453`.
- `data-theme=dark` asertado.
- Ratio CSS y axe no asertados.
- `css-despues.json` / `ubicacion.json` / `refresh.json` / `axe.json` no en disco (`writeFile` en el mismo `then` que un `expect` síncrono).
- Sin PATCH ni restore. `refresh_durante_it: []`.

---

## 1. Hechos confirmados

### 1.1 Medición rev7 (TEST)

| Campo | Valor | Fuente |
|---|---|---|
| `data-theme` | `dark` (aserción previa al fail) | Mocha + orden del spec |
| `--brand-500` | `#1A6B3C` | Mocha actual |
| Esperado oscuro | `#249453` | Mocha + `G94-rev7-179-contexto-antes.json` |
| `identidad_visual.primary_color` | `#1A6B3C` | mismo JSON |
| `oscuro.cumple_aa` | `false`, ratio API 2.69, fondo `#171A15` | mismo JSON |
| `claro.color_ajustado` | `#1A6B3C` (`cumple_aa=true`) | mismo JSON |
| `theme_mode` | `2`, `fuente=personal` | `G94-rev7-179-snapshot-tema.json` |

El hex en UI **coincide** con el primario guardado y con `claro.color_ajustado`. **No coincide** con `oscuro.color_ajustado`.

No hay `css-despues.json` rev7: no se sabe si `#1A6B3C` era `style` inline o computed. El spec usa `inline || computed`.

### 1.2 Backend local (cálculo de `color_ajustado`)

Se calcula al leer, no se persiste. `AccesibilidadVisual.evaluar` llama `ajustar_para_contraste` contra `FONDO_CLARO` `#FFFFFF` y `FONDO_OSCURO` `#171A15` (`color_hex.py`, `accesibilidad_visual.py`).

`GET /configuracion/interfaz/contexto` asigna ese read-model (`obtener_contexto_use_case.py`). El aviso RF-27 dice que **se aplicará** una variante; el servidor **no** pinta CSS.

Pruebas de dominio:

- `test_el_contexto_evalua_el_contraste_de_los_dos_colores`: el cliente necesita la variante para pintar; `oscuro.color_ajustado != "#1A6B3C"`.
- `test_el_color_ajustado_no_reemplaza_al_guardado`: BD conserva el primario.

La respuesta TEST de rev7 es **coherente** con este código: primario intacto, oscuro ajustado a `#249453`. La discrepancia **no** es un fallo de cálculo API en esta corrida.

### 1.3 Frontend en este workspace (`SGPMP-FRONT-END-PWA`)

`useTheme.ts` solo pone `data-theme` desde `localStorage` (`sgpmp-theme`). **No** llama `/personalizacion/tema` ni `/interfaz/contexto`. **No** hay `setProperty('--brand-500')` ni lectura de `color_ajustado` / `primary_color` en `src/`.

`tokens.css`: `--brand-500` claro `#2e8634`; `[data-theme="dark"]` `#52a057`. Ninguno es `#1A6B3C` ni `#249453`.

**Hecho:** el workspace local **no** explica el `--brand-500=#1A6B3C` de TEST. El deploy TEST **no coincide** con este árbol para marca.

### 1.4 Frontend TEST (solo por evidencias de corridas)

Rev4 (`G94-rev4-179-css-despues.json`, `data-theme=light`): `--brand-500` **inline y computed** `#757575` (= `claro.color_ajustado` de identidad `#FFFFFF`, no el crudo). `--brand-400` `#3F8252` (= `secondary` claro ajustado en el contexto de entonces). El SPA TEST **inyecta** tokens de marca en `documentElement.style`.

Rev4 también interceptó GET tema de navegador 200. El `useTheme` local no lo hace.

Rev7: con oscuro, la marca medida es el primario / variante **clara**, no la oscura.

---

## 2. Hipótesis (no cerradas)

Ordenadas de más a menos alineadas con rev4+rev7. **Ninguna está demostrada en el bundle TEST** (no hay fuente del deploy).

1. **El SPA TEST pinta `accesibilidad.primary_color.claro.color_ajustado` (o equivalente: ajustar solo contra fondo claro) en `--brand-500`, sin cambiar a `oscuro` cuando `data-theme=dark`.** Encaja: rev4 light `#757575`; rev7 dark `#1A6B3C` = claro.color_ajustado. RF-27 y el docstring del backend piden elegir según el tema efectivo.
2. **El SPA aplica `identidad_visual.primary_color` siempre, y solo sustituye si el claro incumple AA.** Encaja rev7 (`#1A6B3C`). Encaja rev4 solo si, para `#FFFFFF`, también ajustan el claro (lo cual rev4 muestra). Es casi el mismo comportamiento que (1) cuando el claro ya cumple.
3. **Aplica `oscuro.color_ajustado` pero otra capa lo pisa** (CSS de `tokens.css`, carrera, medición de inline vs computed). **No verificable** sin `css-despues` rev7. En contra: el default local oscuro sería `#52a057`, no `#1A6B3C`.
4. **El spec midió demasiado pronto** y aún no había aplicado la variante oscura. **Débil:** `data-theme=dark` y `--brand-500` no vacío ya pasaron; el valor estable es el primario, no un default intermedio.

No se afirma bug de backend. No se afirma que el workspace local sea el de TEST.

---

## 3. Qué no se puede saber sin el deploy

- El commit/bundle JS de `sslip.io` frontend TEST.
- Si el hook de marca usa `claro`, `oscuro`, `theme_mode` o solo `primary_color`.
- Inline vs computed en rev7.
- Recuento GET contexto/tema del navegador en rev7 (`temaBrowserLog` no persistió).
- Ratio CSS real de `--brand-500` vs `--surface-card` en rev7 (el 2.69 es de la API contra `#171A15`).

---

## 4. Instrumentación rev8 (no ejecutada)

Rev4–rev7 intactos. Archivos nuevos:

- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev8_test.cy.js`
- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev8.cjs` (reporter `TC-M09-G94_179_rev8_test`)

`node --check` OK. Criterios **iguales**: `--brand-500` = `oscuro.color_ajustado`, ratio ≥ 4.5, axe 0. Restore y fallos de hook no se ocultan.

Cambios de captura:

1. `writeFile` de `diagnostico.json`, `css-despues.json` y `ubicacion.json` **encadenados y completados** antes de cualquier `expect` de color/ratio/axe.
2. Diagnóstico incluye `pathname`, `data-theme`, `--brand-500` inline/computed, esperado oscuro, crudo, `ajustado_claro`, flags `coincide_*`, ratio calculado, logs refresh/tema (`http` + `error_code`).
3. axe se **escribe** y luego se aserta (si se llega a esa fase).
4. `afterEach` → `G94-rev8-179-ultimo-paso.json` (`last_step`, mensaje Mocha, logs).
5. Sin `wait` de GET tema. Sin secretos en disco.

Rev8 queda **lista para revisión estática y una ejecución autorizada posterior**. No se declara 179 ni G94 aprobados.

Pendiente de autorización:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev8.cjs
```

178 sigue en rev2 (dashboard). G94 no se cierra con 179 solo.
