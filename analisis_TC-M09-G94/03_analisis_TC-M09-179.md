# 03 — Análisis TC-M09-179 (variante automática)

**Objetivo declarado:** aplicar una variante automática cuando el contraste sea insuficiente.

---

## 1. Cómo se provoca la combinación de bajo contraste

**Confirmado** (`tc_m09_g94_179_rev4_test.cy.js`):

1. Login API admin `admin@pecuaria.co` y login UI productor `productor@pecuaria.co` (finca 1).
2. Snapshot: identidad `primary_color=#1A6B3C`; `theme_mode` productor = 2 (oscuro).
3. `PATCH /configuracion/personalizacion/tema` productor `{ theme_mode: 1 }` (claro).
4. `PATCH /configuracion/identidad-visual/1` admin `{ primary_color: '#FFFFFF' }` (blanco sobre superficie clara `#FFFFFF` → ratio 1).

Color de prueba constante: `COLOR_BAJO = '#FFFFFF'`; esperado `AJUSTADO = '#757575'`.

Rev2 usó `admin@pecuaria.co` con **finca 34**, no 1; el CSS no cambió. Rev3 tuvo carrera (`data-theme` null). Rev4 corrige finca 1 + espera `data-theme=light`.

---

## 2. Qué detecta el contraste insuficiente

**Backend**, read-model `AccesibilidadVisual` (`src/configuration/domain/entities/accesibilidad_visual.py`):

- Evalúa `primary_color` contra `FONDO_CLARO` y `FONDO_OSCURO`.
- Emite `ratio`, `cumple_aa`, `color_ajustado` por tema.
- Aviso literal RF-27 cuando no cumple en el modo correspondiente.

No es axe quien “detecta” el bajo contraste institucional para decidir la variante. axe es un **observador posterior** de la UI.

---

## 3. Condición que activa la variante

`ajustar_para_contraste(color, fondo)` en `color_hex.py`: si `ratio_contraste < 4.5`, barre luminosidad HLS alejándose del fondo (oscurecer sobre claro).

Para `#FFFFFF` vs `#FFFFFF`: ratio = 1.0, `cumple_aa=false`, `color_ajustado=#757575`.

**Confirmado** en aserciones rev4 del `it` y en `G94-rev4-179-identidad-despues.json` / contexto API (referenciados desde el spec y el acta).

El frontend debe pintar tokens `--brand-500` (y afines) con `color_ajustado` del tema activo (`data-theme=light` → bloque `claro`), no con `primary_color` crudo.

---

## 4. Variante aplicada y cómo se comprueba

| Capa | Qué se espera | Evidencia rev4 |
|---|---|---|
| API PATCH/GET identidad | `accesibilidad.primary_color.claro.color_ajustado = #757575` | aserciones en el `it` (JSON Mocha incrusta el código) |
| GET contexto productor | mismo `color_ajustado`; `primary_color` sigue `#FFFFFF` | acta + spec |
| CSS | `--brand-500` inline/computed `#757575` | `G94-rev4-179-css-despues.json` |
| `html` | `data-theme="light"` | spec + JSON CSS `"data_theme": "light"` |
| Captura | `G94-rev4-179-dashboard-light-variante` | referenciada en spec `cy.screenshot` |

`--brand-400` quedó `#3F8252` y `--brand-nav` `#353535`: la aserción **solo** exige `--brand-500`. **Confirmado.**

---

## 5. Aserción automática que valida el resultado

La aserción de éxito funcional es:

```text
expect(aplicado, '--brand-500 = color_ajustado #757575').to.eq(AJUSTADO)
```

Previas: PATCH 200/201, `claro.ratio === 1`, `cumple_aa === false`, GET tema navegador `theme_mode === 1`.

**No hay** `expect(results.violations).to.eq(0)` en rev4.

Cypress, al fallar el `after()`, atribuye `state: failed` al único `it`, con mensaje de hook. Eso **no borra** los `writeFile` de CSS/axe ya ejecutados.

**Confirmado:** `TC-M09-G94_179_rev4_test.json` (`pass: false` + `err` de `after all`). Distinguir: los comandos del `it` llegaron a escribir evidencias; el runner **no** da PASS.

---

## 6. ¿La interfaz cambió y el contraste resultante es suficiente?

- **Cambio de interfaz:** sí, tokens de marca primaria a `#757575`. **Confirmado.**
- **Contraste suficiente de esa marca vs blanco:** `#757575` sobre `#FFFFFF` es el mínimo AA que calcula el backend (objetivo 4.5:1). **Inferencia razonable** (algoritmo del producto); no hay medición independiente persistida del ratio de `--brand-500` vs superficie real del dashboard.
- **Contraste de toda la página:** axe **1 violación** `color-contrast`. **Confirmado** `G94-rev4-179-axe.json`. Sin lista de nodos, **no verificable** qué elemento falló (¿texto sobre marca, sidebar, otro?).

Por tanto: variante aplicada ≠ página AA completa.

---

## 7. ¿Se valida la legibilidad después de la variante?

Parcial:

- Sí: CSS token alineado con `color_ajustado`.
- Débil: axe se corre y se **guarda**, no se aserta.
- No: no hay recálculo de `ratio_contraste` en el test contra el color computado del DOM vs `--surface-card`.
- No: no se prueba el aviso de accesibilidad en UI (el texto `_AVISO` del dominio).

---

## 8. ¿Se restauran preferencias y estado?

Diseño del `after()` (`tc_m09_g94_179_rev4_test.cy.js`):

1. Si `patchedId`: PATCH identidad con snapshot (`primary_color` original, `tokenAdmin`).
2. Si `patchedTema`: PATCH tema `theme_mode: snapTema` (2) con `tokenProd`.
3. `expect(r.status, 'restore theme_mode HTTP').to.eq(200)` ← **aquí rev4 obtuvo 401**.

El hook **sí está escrito para ejecutarse al final de la suite** (también si el `it` fallara, en principio `after` corre). En rev4 el `it` casi completó y el restore de tema falló.

Acta: “RESTORE API posterior” identidad `#1A6B3C` y `theme_mode=2`. Eso es **fuera** del runner Cypress. **Confirmado como narrativa**; **no verificable ahora** sin GET a TEST (prohibido como escritura; un GET de solo lectura no se ejecutó en esta fase de análisis).

Riesgo si la restore posterior no se hubiera hecho: productor en claro y finca 1 con blanco institucional. El acta dice que sí se restauró.

---

## 9. ¿Una aserción aprobada de variante demuestra accesibilidad?

**No.** Tres capas distintas:

| Capa | ¿Rev4 la cubre? |
|---|---|
| Detectar insuficiente (`cumple_aa=false`, ratio 1) | Sí, API |
| Aplicar variante (`--brand-500=#757575`) | Sí, CSS |
| Variante cumple 4.5:1 en UI real (axe 0 / medición) | No demostrado (1 violación; sin aserción) |
| Restaurar estado | Hook FAIL; acta posterior |

El grupo G94 exige 178 **y** 179. 179 no tiene PASS automático en ninguna revisión TEST hallada.

---

## Historial breve 179

| Rev | Entorno | Funcional | Notas |
|---|---|---|---|
| 1 | DEV | pending | 178 falló antes; no PATCH identidad |
| 2 | TEST | RECHAZADO | CSS `--brand-500` siguió `#1A6B3C`; finca 34 |
| 3 | TEST | incompleto | `data-theme` null / carrera |
| 4 | TEST | variante OK en evidencias; runner FAIL | after 401; acta APROBADO |

---

## Conclusión 179

- Variante automática del producto: **evidencia de que sí se aplicó en rev4**.
- Criterio de aceptación “accesibilidad de la UI resultante”: **no cerrado**.
- Criterio de aceptación “suite Cypress verde + restore 200”: **no cumplido**.
- Clasificar 179 como APROBADO solo por el acta **contradice** Mocha. El mantenimiento de RECHAZADO del grupo es la lectura correcta del reporte automático.
