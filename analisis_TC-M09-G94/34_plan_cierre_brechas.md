# 34 — Plan de cierre de brechas G94 (sin ejecución TEST)

**Estado oficial de G94:** no se cambia. Sigue **pendiente / no aprobado** según `33_auditoria_documental_final.md`. Este documento no aprueba el grupo porque 178-rev4 y 179-rev11 hayan pasado.

Cypress **no** se ejecutó. No hay PATCH, commit ni deploy.

---

## 1. Fuentes inspeccionadas

| Fuente | Uso |
|---|---|
| `33_auditoria_documental_final.md` | Brechas: estímulo `#FFFFFF`/`#757575`; CU-06 fuera del dashboard |
| `03_analisis_TC-M09-179.md` | Mecánica de la variante |
| `tc_m09_g94_179_rev4_test.cy.js` | Spec que define el estímulo histórico |
| `G94-rev4-179-css-despues.json` | `--brand-500` inline/computed `#757575`, `data_theme: light` |
| `G94-rev4-179-axe.json` | 1 violación `color-contrast`, 16 pases; **sin nodos** |
| `TC-M09-G94_179_rev4_test.json` | Mocha **fail** (`after all` restore 401) |
| `tc_m09_g94_179_rev11_test.cy.js` + `27_ejecucion_rev11.md` | 179 vigente: oscuro `#249453`, **sin** PATCH identidad |
| `tc_m09_g94_178_rev4_test.cy.js` + `32_ejecucion_178_rev4.md` | 178 vigente: admin claro, axe 0 |
| `anotaciones/modulo_9/curls_m09_cu06_personalizar_interfaz.md` | Flujos documentados CU-06 (RF-25…29) |
| `analisis_presentacion_modulos_1_2_9/04_modulo_9.md` | CU-06 = RF-25…29; G91/G85/G88 cubren tema/identidad **aparte** de G94 |
| `06_matriz_trazabilidad.md` | RF-27 → **G91**; RF-26 → G85/G88; **G94 no aparece** |
| `02_analisis_TC-M09-178.md` | 178 limitado a dashboard |
| `color_hex.py` / curls RF-25 | `color_ajustado`, aviso por tema, se guarda color bajo contraste |

No hay documento de caso de uso CU-06 con pasos de pantalla “el usuario abre Configuración…”. Lo definido es **API** (curls) más los specs G94.

---

## 2. Análisis del estímulo histórico TC-M09-179 (`#FFFFFF` → `#757575`)

### Qué lo desencadena

**No es un clic de color en la UI** en el spec. El disparador documentado en `tc_m09_g94_179_rev4_test.cy.js` es:

1. Login API **admin** + login UI **productor** (finca 1).
2. Snapshot identidad (`primary` debe ser `#1A6B3C`) y `theme_mode` productor (**debe ser 2**).
3. `PATCH /configuracion/personalizacion/tema` productor `{ theme_mode: 1 }` (claro).
4. `PATCH /configuracion/identidad-visual/1` admin, `form`, `primary_color: '#FFFFFF'` (resto de campos del snapshot + `version`).

El producto (curls RF-26/RF-27): un administrador **puede guardar** un primario de bajo contraste; el backend **no rechaza**; calcula `color_ajustado` y el cliente debe pintar la variante. El test **simula** esa escritura por API, no recorre el formulario de identidad.

### Qué CSS debe cambiar

Aserción del spec rev4 (única de éxito funcional de marca):

`--brand-500` (inline o computed) **= `#757575`** con `html[data-theme=light]`.

También se escribe `--brand-600` / `--brand-cta` en el JSON rev4 (`#757575`); **el `expect` solo nombra `--brand-500`**. `--brand-400` y `--brand-nav` **no** se asertan (en rev4 quedaron `#3F8252` y `#353535`).

### Precondiciones (spec rev4)

| Condición | Dónde |
|---|---|
| Productor UI, dashboard, `id_finca === 1` | contexto |
| GET identidad finca 1 **200 objeto**, `primary_color === #1A6B3C` | snapshot |
| `theme_mode` inicial productor **=== 2** | snapshot tema |
| PATCH tema 200 → GET tema 1 | |
| PATCH identidad 200/201; `claro.ratio === 1`, `cumple_aa === false`, `color_ajustado === #757575` | |
| Tras `cy.visit /dashboard`: GET tema nav `theme_mode === 1`; `data-theme=light`; contexto `primary #FFFFFF` y ajustado claro `#757575` | |
| Restore: PATCH identidad al snapshot; PATCH tema al snapshot | `after()` |

### Resultado correcto según el spec original (rev4)

Definido con claridad para la **marca**:

`expect(aplicado, '--brand-500 = color_ajustado #757575').to.eq('#757575')`

API: primario persistido `#FFFFFF`; variante clara `#757575`.

**Ambiguo / no definido en rev4:**

- axe `violations === 0` (**no** se aserta; rev4 dejó **1** violación **sin nodos**).
- Ratio CSS `--brand-500` vs superficie real (03: no persistido; solo el algoritmo 4.5 del backend).
- Recorrido UI de “guardar identidad” o “selector de tema” en Configuración.

### Por qué la evidencia rev4 quedó obsoleta

| Hecho | Fuente |
|---|---|
| Fecha 2026-09-25; frontend **redesplegado** después | 33 |
| Mocha **FAIL** (restore tema 401), no PASS de grupo | `TC-M09-G94_179_rev4_test.json` |
| axe 1, nodos desconocidos | `G94-rev4-179-axe.json` |
| 179-rev11 prueba **otro** estímulo (oscuro `#249453`, sin PATCH identidad) | 27 |
| CSS/hooks de marca cambiaron (MutationObserver / `color_ajustado` por tema) | 24 |

`G94-rev4-179-css-despues.json` **sí** muestra `#757575` en claro **en aquel** bundle. No demuestra el bundle TEST **actual**.

### ¿Revisión independiente?

**Sí.** No reutilizar `tc_m09_g94_179_rev4_test.cy.js` (escribe en `Resultados/` plano, `overwrite` Mocha `TC-M09-G94_179_rev4_test`). Cualquier revalidación debe ser p. ej. **179-rev12** con `Resultados/rev12/` (o `179-rev12/`), spec y config nuevos. Conservar rev4–rev11.

---

## 3. Matriz de cobertura CU-06

CU-06 documentado (`04_modulo_9.md` + curls): **RF-25 contexto, RF-26 identidad, RF-27 tema, RF-28 dashboard layout, RF-29 idioma**. G94 solo titula 178 (contraste) + 179 (variante). **No** se inventan pantallas de Configuración como CA de G94.

| Recorrido o criterio | Fuente | Evidencia existente | Brecha | Prueba necesaria | Prioridad | Especificación |
|---|---|---|---|---|---|---|
| GET contexto + accesibilidad (aviso / `color_ajustado`) | curls RF-25 Flujo A | 178-rev4 y 179-rev11 JSON contexto | — | Ninguna repetición | — | **definido** API; cubierto como lectura |
| Contraste dashboard admin, tema activo | spec 178; 1.4.3 | 178-rev4 PASS, axe 0, sidebar 6.47 | — | No repetir | — | **derivado** spec 178 |
| Variante UI oscuro (`#249453` en `--brand-500`) | spec 179-rev11; RF-27 aviso | 179-rev11 PASS | No es el estímulo claro `#FFFFFF` | No repetir 179-rev11 | — | **derivado** spec vigente |
| Variante UI claro `#FFFFFF` → `--brand-500=#757575` | spec **179-rev4**; 03 | CSS 2026-09-25; Mocha fail hook | No vigente post-deploy | **179-rev12** si se exige este estímulo | **Alta si G94 incluye ambos polos**; si no, decisión humana | **definido** en rev4 (marca); axe 0 **ambiguo** |
| GET/PATCH tema personal (jerarquía) | curls RF-27 A/B | 179-rev11 GET; G91 173/174/175 | G94 no es G91 | Fuera de G94 salvo PATCH mínimo del estímulo | — | **definido** (G91) |
| PATCH tema global | curls RF-27 C/D | G91 | — | No G94 | — | **definido** otros casos |
| CRUD identidad UI | curls RF-26; G85/G88 | G85/G88 APROBADO | G94 no recorre formulario | No inventar Cypress de menú Configuración para G94 | — | **definido** G85/G88, no G94 |
| Layout dashboard RF-28 | curls RF-28 | `04_modulo_9`: no auditado en G94 | Widgets/layout | No es 178/179 | Baja para G94 | **definido** CU-06, **fuera** G94 |
| Idioma RF-29 | curls RF-29 | no G94 | — | No G94 | — | **definido** CU-06, **fuera** G94 |
| UI Configuración (tema/identidad) en PWA | 04: local `App.tsx` sin esas páginas; TEST sí en G85 | ninguna de G94 | Recorrido UI no está en specs 178/179 | Solo si un mandato **escrito** amplia G94 | — | **ambiguo** para G94 |
| 204/FA-18/FA-19 contexto | curls RF-25 | no G94 | Flujos alternos | No G94 | — | **definido** curls, no G94 |

**Formularios, tablas, vacíos** citados en 02 como no recorridos: **no** figuran como pasos de CU-06 en curls. Tratarlos como **derivados/no formales**; no elevarlos a requisito G94.

---

## 4. Brechas verificadas y ambigüedades

| Ítem | Verificado | Ambigüedad |
|---|---|---|
| Estímulo `#FFFFFF`/`#757575` no revalidado post-deploy | Sí (33 + fechas) | ¿G94 **exige** ambos polos (claro y oscuro) o basta 179-rev11? **No está en una matriz CA.** |
| axe 0 en el estímulo claro | Rev4 **no** lo exigía y midió 1 violación | Si rev12 exige axe 0, es **ampliación**, no el spec original |
| CU-06 “fuera del dashboard” | G94 nunca lo automatizó | Ampliar a Configuración **no** está definido para G94; choca con G85/G91 |
| Restore 401 rev4 | Sí | Rev12 debe restaurar con **login fresco** (lección 179-rev11), no reusar JWT del SPA |

---

## 5. Plan mínimo de pruebas nuevas

**No repetir** 178-rev4 ni 179-rev11: ya cubren admin claro + productor oscuro + axe 0 + sidebar.

### Paso 0 — Decisión humana (bloquea el resto)

Elegir una:

- **A.** Cerrar G94 con el alcance *specs vigentes* (178-rev4 + 179-rev11). Entonces **no** hay Cypress nuevo. Documentar por escrito que el polo claro `#FFFFFF` queda **fuera** (histórico rev4, no vigente).
- **B.** Exigir el polo claro. Entonces crear **TC-M09-179 rev12** (única prueba nueva mínima).

### Si se elige B: 179-rev12 (independiente)

| | |
|---|---|
| Archivos | `tc_m09_g94_179_rev12_test.cy.js`, `cypress.config.179.rev12.cjs`, `Resultados/rev12/` |
| Criterios (los de rev4, más arnés de 179-rev11) | `--brand-500 === #757575`; `data-theme=light`; API `claro.color_ajustado=#757575`, `ratio=1`, `cumple_aa=false`; primario `#FFFFFF`; GET tras login en `cy.then`; persistir CSS **antes** de expect; restore identidad **y** tema con sesión nueva; evidencias exclusivas |
| Conservar | Snapshot `primary/secondary/org/version` finca 1 y `theme_mode` productor; **restaurar ambos** aunque falle el `it` |
| No | `/tema/global`; POST/DELETE negocio; overwrite de `Resultados/G94-rev4-*` |
| Axe | **Decisión:** o se mide como observador (como rev4, sin fail) o se aserta 0 (**ampliación**; documentarla) |
| Estáticos previos | `node --check`; revisión de que ningún GET/PATCH autenticado sea síncrono (fallo 178-rev3) |
| Antes de autorizar TEST | Ventana acordada: PATCH identidad finca 1 es **dato compartido**; restore obligatorio; no ejecutar si no hay autorización explícita de escritura RF-26 |

Orden: (1) decisión A/B → (2) si B, spec rev12 → (3) estáticos → (4) **una** corrida autorizada → (5) informe de ejecución. 178-rev4/179-rev11 se **citan**, no se reejecutan.

No hay en este plan un Cypress “recorrer CU-06 Configuración” salvo mandato nuevo: no está en G94.

---

## 6. Cuándo G94 podría aprobarse

Sin cambiar el estado ahora. Condiciones **documentables**:

**Opción A (alcance dashboard + specs 178-rev4 y 179-rev11):** acta humana que declare fuera de alcance el estímulo `#FFFFFF` y las pantallas RF-25…29 no cubiertas por G94 (delegadas a G91/G85/G88). Entonces G94 es **aprobable** con esa acta. Hoy **falta el acta**.

**Opción B:** 179-rev12 PASS (Mocha incluido restore) con `--brand-500=#757575` y `data-theme=light`, más 178-rev4 y 179-rev11 ya existentes. Axe: según lo que se haya escrito en el spec rev12.

**No basta** el simple “dos subcasos PASS”.

**Sigue sin ser G94:** jerarquía tema global (G91), CRUD identidad (G85/G88), RF-28, RF-29.

---

## 7. Validaciones hechas y lo no ejecutado

Hecho: lectura de specs/JSON/informes listados en §1; cruce con curls CU-06 y matriz G91/G85.

**No ejecutado:** Cypress TEST; creación de spec 179-rev12; PATCH; cambio de estado G94.

Comando **futuro, solo si se autoriza B:**

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```

(el archivo aún **no existe**; no inventar la corrida).
