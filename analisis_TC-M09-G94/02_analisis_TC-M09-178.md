# 02 — Análisis TC-M09-178 (contraste mínimo 4.5:1)

**Objetivo declarado:** verificar el contraste mínimo de 4.5:1 del tema.  
**RF-27 / CU-06 / WCAG 2.1 AA criterio 1.4.3 (Contrast Minimum), más el uso de axe-core regla `color-contrast`.**

---

## 1. Elementos de interfaz examinados

**Confirmado por evidencia** (rev2 TEST, `G94-rev2-test-ejecucion.txt` y `tc_m09_g94_rev2_test.cy.js`):

- Página: dashboard tras login de `admin@pecuaria.co`.
- Inyección de axe-core en `window` y `axe.run(document, { runOnly: { type: 'rule', values: ['color-contrast'] } })`.
- Nodos reportados en pases: 12 (`G94-rev2-178-axe.json`).
- El archivo `G94-rev2-178-axe-aplicables.json` tiene `"n": 0, "nodos": []` — el spec filtra nodos “aplicables” con una heurística propia; en esa corrida ninguno quedó clasificado como aplicable para el detalle, aunque axe sí evaluó 12 nodos en `passes`.

**No se recorre** el resto de rutas de CU-06 (configuración de tema, identidad visual, formularios, tablas, estados vacíos). **Confirmado:** el spec 178 de rev2 se limita al dashboard.

Rev1 DEV (`G94-rev1-dev-ejecucion.txt`): 178 FALLÓ antes de axe (`GET /configuracion/interfaz/contexto` 401). No hay `G94-178-axe.json` de esa corrida.

---

## 2. Combinaciones de color evaluadas

- axe compara, por cada nodo de texto que puede evaluar, el color de primer plano computado contra el fondo efectivo (algoritmo axe-core / WCAG relative luminance).
- El producto, en paralelo, evalúa el **color institucional** (`primary_color`) contra fondos fijos:
  - claro: `#FFFFFF` (`FONDO_CLARO`)
  - oscuro: `#171A15` (`FONDO_OSCURO`)
  - umbral: `RATIO_MINIMO_AA = 4.5`  
  Fuente: `sgpmp-backend/src/configuration/domain/value_objects/color_hex.py`.

En 178 **no** se fuerza un color de bajo contraste. Se mide el tema/identidad **ya presentes** en TEST al momento de rev2.

Combinación institucional en rev2: `primary_color=#1A6B3C`, `cumple_aa` claro=true, oscuro=false, `color_ajustado` oscuro=`#83C398` (`G94-rev2-test-ejecucion.txt`). Eso es **cálculo de backend**, no axe.

---

## 3. Cómo se calcula o verifica el contraste

Dos mecanismos distintos:

| Mecanismo | Dónde | Qué mide | Umbral |
|---|---|---|---|
| axe-core `color-contrast` | Cypress 178 | Texto visible en el DOM del dashboard | WCAG AA según axe (4.5:1 texto normal, 3:1 texto grande) |
| `ratio_contraste` / `AccesibilidadVisual` | backend Python | `primary_color` vs `FONDO_CLARO`/`FONDO_OSCURO` | 4.5:1 fijo (`RATIO_MINIMO_AA`) |

**Confirmado.** 178 usa el primero. El segundo aparece en el GET contexto como dato de apoyo, no como aserción de “todo el tema”.

---

## 4. Herramienta real

- **Cypress 14** + **axe-core** inyectado (`cy.task('getAxeSource')` en configs G94).
- **No hay spec Playwright** en `TC-M09-G94/`. La matriz menciona Playwright; en el repositorio G94 la automatización es Cypress-axe.
- Newman no ejecuta este caso.

**Confirmado por evidencia** (árbol de specs).

---

## 5. Criterio WCAG que aplica realmente

Fuente externa (no es del repositorio): [WCAG 2.1 Understanding SC 1.4.3](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html) y [SC 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG21/Understanding/non-text-contrast.html).

| Tipo | WCAG 2.1 AA | Qué hace el caso |
|---|---|---|
| Texto normal | 4.5:1 | Declarado en RF-27 y en `RATIO_MINIMO_AA`. axe 178 usa la regla que distingue tamaño. |
| Texto grande (≥18pt o 14pt bold) | 3:1 | axe lo aplica; el caso de prueba **no documenta** la distinción. |
| Componentes UI / gráficos (1.4.11) | 3:1 | **No** es el umbral del caso (el caso dice 4.5:1). El acta rev2 marca un contenedor NAV con ratio 1.15 como **no aplicable**. |

El umbral 4.5:1 del caso es **el de texto normal** y el del color institucional vs superficie. No equivale a “todos los gráficos a 4.5:1”.

---

## 6. Valores obtenidos (si existen)

Rev2 TEST (`G94-rev2-178-axe.json`):

```json
{ "violations": 0, "violation_ids": [], "color_contrast_pass_nodes": 12 }
```

GET contexto (mismo acta): `accesibilidad.primary_color.claro.ratio` no está en el fragmento citado del acta como número de axe; sí `cumple_aa` claro true / oscuro false.

Rev1 DEV: sin valores de contraste (fallo 401 en contexto).

---

## 7. Qué falló y qué pasó

| Revisión | 178 | Detalle |
|---|---|---|
| rev1 DEV | FAIL | `GET contexto` 401; axe no llegó a correr |
| rev2 TEST | PASS (acta + axe 0) | 12 nodos en pases; 0 violaciones |
| rev3/rev4 | no reejecutan 178 | specs 179 separados |

En rev2 el acta menciona un nodo NAV `rgb(53,53,53)` sobre `rgb(26,107,60)` ratio **1.15**, clasificado **no aplicable** (fondo de marca, no texto). Eso es juicio manual, no un fail de axe.

---

## 8. ¿Tema activo completo o muestra?

**Muestra limitada.** Solo dashboard, solo regla `color-contrast`, solo nodos que axe puede computar (texto con color determinado). No hay barrido de tokens CSS (`--brand-*`, `--surface-*`) ni de otras vistas.

**No se puede afirmar** que “el tema cumple 4.5:1” de forma global. Se puede afirmar: **en rev2, axe no halló violaciones `color-contrast` en el dashboard analizado**.

---

## 9. Falsos positivos, exclusiones, límites de axe

- axe no evalúa texto en canvas, sombras, texto en imágenes, ni todos los estados hover/focus.
- Elementos con transparencia, texto sobre degradados o iconos pueden quedar fuera o generar ruido.
- El spec 178 **no** usa `axe.configure` de exclusiones persistidas en JSON de rev2 más allá del filtro “aplicables” que resultó vacío.
- El ratio 1.15 del NAV es un ejemplo de contraste de **contenedor**, no de texto; el acta lo excluye. **Confirmado** en narrativa; **no verificable** el selector exacto sin HTML de esa captura.

---

## 10. ¿La evidencia permite afirmar el criterio de contraste?

**No para el tema completo.**  
**Sí, de forma acotada, para el dashboard de rev2 bajo axe `color-contrast`:** 0 violaciones.

Clasificación:

- Cumplimiento parcial 178 rev2: **confirmado**.
- Cumplimiento RF-27 “relación 4.5:1 entre texto y fondo” como propiedad de **todo** el sistema: **no verificable** con estos artefactos.
- Oscuro institucional `cumple_aa=false` en el mismo GET de 178: el backend ya declara que el verde `#1A6B3C` **no** cumple 4.5:1 sobre fondo oscuro y ofrece variante `#83C398`. Eso **no** hizo fallar 178 porque 178 no forzó tema oscuro ni asertó ambos temas. **Confirmado** en acta rev2.

Implicación para el grupo G94: 178 APROBADO no cierra 179 ni el grupo.
