# 45 — Cierre definitivo TC-M09-G94

**Decisión documental:** **APROBADO**

**Fecha del cierre:** 2026-10-10 (evidencias vigentes; última corrida 179 rev12 Mocha 2026-10-10T21:39:10Z–21:39:30Z).

Sin Cypress en esta tarea. Sin peticiones TEST. Sin commit. Informes 01–44 y JSON históricos **no** se reescribieron.

---

## 1. Identificación y alcance

| | |
|---|---|
| Caso | **TC-M09-G94** = **TC-M09-178** + **TC-M09-179** (`01_diagnostico_G94.md`) |
| Requisito | **RF-27** (tema visual): contraste mínimo institucional 4.5:1 y **variante automática** cuando el primario no cumple AA (`color_hex.py` `RATIO_MINIMO_AA`; `03_analisis_TC-M09-179.md`) |
| Caso de uso | **CU-06** Personalizar interfaz. G94 **no** recorre RF-25…29 completos: contexto/identidad/tema jerárquico/layout/idioma están en curls CU-06 y, en pruebas, en **G91 / G85 / G88** (`34_plan_cierre_brechas.md`, `analisis_presentacion_modulos_1_2_9/04_modulo_9.md`) |
| Superficie automatizada | Dashboard TEST (`/dashboard`) tras login; no formularios de Configuración |
| WCAG citado | 2.1 AA **SC 1.4.3** (texto). **SC 1.4.11** (no texto) queda **fuera** (`02_analisis_TC-M09-178.md`) |
| Matriz de presentación | `06_matriz_trazabilidad.md` asignaba RF-27 (jerarquía claro/oscuro) a **G91**, no a G94. G94 cubre **contraste + variante en dashboard**, no GET/PATCH `/tema/global` |

No hay hoja CA-G94-xx independiente (`33_auditoria_documental_final.md`). Los criterios de aceptación de este cierre son los **explícitos** de RF-27/CU-06 (alcance G94) y de los specs vigentes **178-rev4**, **179-rev11** y **179-rev12**. No se inventan CA. Axe, ratios extra y diagnósticos **solo** cuentan si el spec correspondiente los `expect`.

Plan `34` **opción B** (única vía de cierre con polo claro vigente): 178-rev4 PASS + 179-rev11 PASS + 179-rev12 PASS (Mocha incluido restore) con `--brand-500=#757575` y `data-theme=light`. Esa condición **está cumplida**.

---

## 2. Tabla de criterios, evidencia y veredicto

* = aserción del spec Cypress vigente, no de una matriz CA archivada.

| Id | Criterio | Fuente | Cubierto por | Evidencia | Veredicto |
|---|---|---|---|---|---|
| G94-178-A | Login admin UI 200 y dashboard | spec 178-rev4 * | 178-rev4 | `G94-178-rev4-login.json` http 200; diagnóstico `pathname=/dashboard`; Mocha 1/1 | **Cumple** |
| G94-178-B | Tema **activo** (no forzar oscuro) | spec 178-rev4 *; 28 | 178-rev4 | `theme_mode=1`, `html_data_theme=light`, `--brand-500=#1A6B3C` | **Cumple** |
| G94-178-C | axe `color-contrast` = 0 en dashboard | spec 178-rev4 `expect(axe_violations).eq(0)` * | 178-rev4 | `G94-178-rev4-axe.json`: 0 viol / 23 pases | **Cumple** |
| G94-178-D | Cuatro nodos sidebar ≥ 4.5:1 | spec 178-rev4 * | 178-rev4 | `#97B68F` / `#0C301B` ratio **6.47** (`G94-178-rev4-diagnostico.json`) | **Cumple** |
| G94-179O-A | Variante oscura en `--brand-500` = `#249453` | spec 179-rev11 *; RF-27 | 179-rev11 | `G94-rev11-179-diagnostico.json`; `coincide_oscuro: true`; Mocha 1/1 | **Cumple** |
| G94-179O-B | `data-theme=dark`, productor, finca 1 | spec 179-rev11 * | 179-rev11 | diagnóstico + `ultimo-paso.json` | **Cumple** |
| G94-179O-C | Ratio `--brand-500` vs superficie CSS ≥ 4.5 | spec 179-rev11 * | 179-rev11 | `#249453` / `#171A15` = **4.55:1** | **Cumple** |
| G94-179O-D | axe 0 y sidebar ≥ 4.5 (cuatro nodos) | spec 179-rev11 * | 179-rev11 | axe 0 / 19; sidebar **5.08:1** | **Cumple** |
| G94-179C-A | API: primario `#FFFFFF`, `claro.ratio=1`, `cumple_aa=false`, `color_ajustado=#757575` | spec 179-rev4 / rev12 * | 179-rev12 | `G94-rev12-179-identidad-despues.json`; `44_ejecucion_final_rev12.md` | **Cumple** |
| G94-179C-B | GET tema navegador 200, `theme_mode=1` | spec 179-rev12 * | 179-rev12 | `G94-rev12-179-tema-browser.json` | **Cumple** |
| G94-179C-C | `--brand-500=#757575` y `data-theme=light` | spec 179-rev12 * (oráculo rev4) | 179-rev12 | `ultimo-paso.json`; `diagnostico.json`; Mocha PASS `CYPRESS_EXIT=0` | **Cumple** |
| G94-179C-D | Restauración identidad (colores, org, logo) y tema productor, GET final = snapshot | spec 179-rev12 `after()` * | 179-rev12 | `G94-rev12-179-restore.json` / `verificacion-final.json`; sin `RESTORE-PENDIENTE.json` | **Cumple** |

**No son criterios formales de G94** (fuera de alcance o explícitamente no asertados):

| Ítem | Tratamiento |
|---|---|
| Recorrido UI Configuración / RF-26 formulario | G85/G88, no G94 (`34`) |
| Jerarquía `/tema` y `/tema/global` | G91 (`06_matriz_trazabilidad.md`) |
| RF-28 layout, RF-29 idioma | CU-06, no 178/179 |
| WCAG 1.4.11, hover/focus, otras rutas | Fuera (`02`, `33`) |
| axe `violations===0` en **179-rev12** | Diagnóstico; `criterio_aceptacion: false` en `G94-rev12-179-axe.json` (hubo 0 violaciones; **no** se usa como CA) |
| Ratio CSS marca vs blanco en 178 | 178 no lo aserta; API claro 6.54 es apoyo |
| Inspección visual píxel a píxel de PNG | Archivos existen; no OCR |

**Brechas reales de CA obligatorio:** ninguna identificada. Lo restante es **limitación de alcance** (dashboard, no toda la PWA).

---

## 3. Resumen de subcasos vigentes

### TC-M09-178 rev4

- Informe: `32_ejecucion_178_rev4.md`. Evidencias: `Resultados/178-rev4/`.
- Mocha 2026-10-10T17:25:39Z–17:25:49Z, duration 10353 ms, **PASS**, exit 0.
- Admin, tema activo claro, `--brand-500=#1A6B3C`, axe 0, sidebar 6.47:1.
- Sin PATCH. Restauración 179 **no aplica**.

### TC-M09-179 rev11

- Informe: `27_ejecucion_rev11.md`. Evidencias: `Resultados/rev11/`.
- Mocha 2026-10-10T17:09:55Z–17:10:05Z, duration 10694 ms, **PASS**, exit 0.
- Productor, `data-theme=dark`, `--brand-500=#249453`, ratio marca 4.55, sidebar 5.08, axe 0.
- **Sin** PATCH de identidad. Restore **omitido** (`patched_tema: false`); coherente, no prueba restore 200.

### TC-M09-179 rev12 (cierre del polo claro)

- Informe de la **última** corrida autorizada: `44_ejecucion_final_rev12.md`. Evidencias raíz: `Resultados/179-rev12/`.
- Mocha 2026-10-10T21:39:10Z–21:39:30Z, duration 20067 ms, **PASS**, `CYPRESS_EXIT=0`.
- GET tema nav 200 `theme_mode=1`; `--brand-500=#757575`; `data-theme=light`; refresh `[]`.
- Restore verificado: identidad `#1A6B3C` v9, org `Acuícola El Remanso`, logo `/assets/logos/remanso.png`; tema `theme_mode=2`.

**Historial rev12 (no se oculta):**

| Corrida | Informe | Mocha | Qué falló | Restore |
|---|---|---|---|---|
| Primera (copia `ejecucion-38/`) | `38_ejecucion_rev12.md` | FAIL | PATCH tema 401 (JWT UI revocado por preflight `loginApi`; `39`/`40`/`41`) | Tema ya snapshot; identidad no escrita |
| Segunda (raíz, luego sobrescrita por Mocha de 44) | `42` + `43` | FAIL | `wait @temaPost`; API `REFRESH_TOKEN_REQUERIDO` (arnés: recarga sin relogin UI) | Identidad y tema **verificados** |
| **Final autorizada** | **44** | **PASS** | — | **Verificado** |

El fallo de las corridas 38 y 42 fue de **arnés**, no de RF-27. La última ejecución **corregida** pasó. `ejecucion-38/` y los informes 38–43 se conservan.

---

## 4. Resultado funcional vs restauración

| | Funcional (oráculo de producto) | Restauración |
|---|---|---|
| 178-rev4 | Contraste dashboard admin (axe 0 + sidebar AA) | N/A (solo lectura) |
| 179-rev11 | Variante oscura pintada `#249453` | Omitida (sin escritura) |
| 179-rev12 | Variante clara pintada `#757575` en light | GET final = snapshot; sin `RESTORE-PENDIENTE.json` |

Un PASS Mocha **no** se tomó como cierre del grupo hasta cruzar los tres specs con las fuentes 33/34/41/44. Con opción B de `34` satisfecha, el grupo es aprobable.

---

## 5. Referencias

- Auditoría y plan: `33_auditoria_documental_final.md`, `34_plan_cierre_brechas.md`
- JWT / sesión única: `41_revision_final_jwt_rev12.md`
- Ejecución final: `44_ejecucion_final_rev12.md`
- Alcance: `01_diagnostico_G94.md`, `02_analisis_TC-M09-178.md`, `03_analisis_TC-M09-179.md`
- RF-27 presentación: `analisis_presentacion_modulos_1_2_9/04_modulo_9.md`, `06_matriz_trazabilidad.md`
- Specs: `tc_m09_g94_178_rev4_test.cy.js`, `tc_m09_g94_179_rev11_test.cy.js`, `tc_m09_g94_179_rev12_test.cy.js`
- Evidencias: `Resultados/178-rev4/`, `Resultados/rev11/`, `Resultados/179-rev12/` (+ `ejecucion-38/`)

---

## 6. Limitaciones conocidas

- G94 **no** certifica toda la PWA ni CU-06 completo.
- Capturas PNG existen; no se hizo inspección visual independiente.
- axe 0 en 178/179-rev11 es muestra de dashboard, no 1.4.3 de todas las vistas.
- Informes 22 y anteriores dejan G94 **RECHAZADO** en su fecha; ese texto histórico **no se altera**. El estado vigente es este informe.
- Mocha de `179-rev12/` raíz corresponde a la corrida **44**; el FAIL de 42 ya no está en esos JSON de raíz (sí en `42_*.md` y, para 38, en `ejecucion-38/`).

---

## 7. Decisión

**APROBADO.**

Justificación: los criterios aplicables de G94 (contraste 4.5:1 en dashboard 178; variante automática oscura 179-rev11; variante automática clara `#FFFFFF`→`#757575` 179-rev12; restore verificado en rev12) tienen evidencia Mocha PASS y JSON coherentes. No queda CA obligatorio de G94 sin verificar. CU-06 fuera del dashboard no es CA de este grupo. Los FAIL 38/42 se documentan como arnés superado, no como incumplimiento vigente de RF-27.
