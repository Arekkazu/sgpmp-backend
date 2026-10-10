# 28 — Cobertura TC-M09-178 y propuesta de revalidación

**G94 permanece RECHAZADO.** Cypress TEST **no** se ejecutó. Sin commit, push, deploy, PATCH ni cambios de RLS/identidad/tema en TEST.

**Decisión:** **listo para ejecutar tras autorización**, usando el spec **nuevo** `178-rev3` (no el `tc_m09_g94_rev2_test.cy.js`). No está bloqueado por ausencia total de criterio, pero **no hay matriz formal independiente** de aceptación de 178 en el repositorio.

---

## 1. Archivos e informes inspeccionados

### Relación de casos

| Ítem | Qué dice la documentación disponible |
|---|---|
| Grupo | G94 = **TC-M09-178 + TC-M09-179** (`01_diagnostico_G94.md`) |
| RF | RF-27 (personalización / contraste WCAG / variante automática) |
| CU | CU-06 |
| WCAG | 2.1 AA **1.4.3** Contrast Minimum; umbral de caso **4.5:1** texto normal (`02_analisis_TC-M09-178.md`, `RATIO_MINIMO_AA` backend) |
| 178 | Contraste del **tema activo** en UI (axe `color-contrast` + muestra CSS) |
| 179 | **Variante automática** cuando el institucional no cumple AA |

### Matriz formal

**No se encontró** un documento de aceptación tipo hoja de casos con filas “CA-178-01…” dedicado a TC-M09-178.

- `analisis_presentacion_modulos_1_2_9/06_matriz_trazabilidad.md` mapea RF-27 a **G91** (tema 173/174/175), **no** a G94/178.
- Informes 01, 02 y 05 reconstruyen criterios desde el **título del `it`**, el spec Cypress y WCAG 1.4.3.
- La matriz de evidencias de 05 es historial de revisiones, no CA de producto.

Los criterios de la tabla de la sección 2 son los **implementados y citados** en esos artefactos. No se inventaron CA de otras pantallas de CU-06 (configuración, formularios, tablas): el spec 178 **nunca** las recorrió (`02_analisis_TC-M09-178.md` §1 y §8).

### Specs y evidencias 178

| Archivo | Uso |
|---|---|
| `tests/.../TC-M09-G94/tc_m09_g94.cy.js` | 178 DEV: axe cualquier violación = FAIL; condicional `color_ajustado` |
| `tests/.../TC-M09-G94/tc_m09_g94_rev2_test.cy.js` | 178+179 juntos; `testIsolation: false`; 179 PATCH identidad **finca 4** |
| `tests/.../TC-M09-G94/cypress.config.rev2.cjs` | Reporter `TC-M09-G94_rev2_test`; `solo178` cambia nombre a `…_rev2_178_axe` **en el mismo `Resultados/`** |
| `Resultados/G94-rev2-178-axe.json` | 0 violaciones, 12 pases, axe-core 4.13.0 |
| `Resultados/G94-rev2-178-axe-aplicables.json` | `n: 0` |
| `Resultados/G94-rev2-178-tema-ui.json` | admin `theme_mode=1` claro; `data_theme` light en nota |
| `Resultados/G94-rev2-178-ratios-css.json` | `--brand-500=#2e8634`; muchos ratios `null` (fondo transparente); NAV 1.15 |
| `Resultados/G94-rev2-178-contexto.json` | `id_finca=34`, `identidad_primary=null`, `accesibilidad=null` |
| `Resultados/TC-M09-G94_rev2_test.json` | 2026-09-25; 178 pass, 179 fail |
| `Resultados/TC-M09-G94_rev2_178_axe.json` | corrida `solo178` (179 pending) |
| `analisis_TC-M09-G94/02_analisis_TC-M09-178.md` | alcance dashboard admin |
| `analisis_TC-M09-G94/01`, `05`, `09`, `22`, `23`, `27` | 178 no reconfirmado post-redespliegue; 179 rev11 PASS |

### Qué **no** cubre 179 rev11 (para no duplicar ni sustituir)

179 rev11 (`27_ejecucion_rev11.md`): **productor**, finca 1, `theme_mode=2`, espera `--brand-500=#249453`, ratio marca 4.55:1, sidebar 5.08:1, axe 0.

Eso **no** es el caso 178: ni usuario admin, ni “tema activo sin estímulo de variante oscura”, ni evidencia fechada 2026-10-10 para el dashboard de administrador.

---

## 2. Matriz de cobertura de TC-M09-178

Leyenda de actor: **178** = propio del subcaso; **179-r11** = demostrado en 179 rev11, **no transfiere** a 178; **G94** = grupo.

| Criterio de aceptación (fuente) | Evidencia histórica | ¿Suficiente y vigente? | Qué falta | Prueba / evidencia | Estado |
|---|---|---|---|---|---|
| Login UI y dashboard (spec 178 rev2 L131–143) | rev2: admin, `/dashboard`, captura | No vigente: frontend redesplegado 2026-10-10; admin ahora vinculado a finca 1 (Alex) vs finca **34** en rev2 | Repetir login+dashboard **admin** post-deploy | 178-rev3 | **pendiente** |
| Axe `color-contrast` 0 violaciones en dashboard, tema **activo** (título 178; DEV throw; RF-27 / 1.4.3) | rev2: 0 violaciones, 12 pases, **claro**, admin, finca 34 sin identidad | No: UI y CSS de sidebar cambiaron (rev8 3.64 → rev11 productor 5.08). Muestra distinta | Axe 0 en dashboard **admin**, tema que tenga el admin **hoy**, persistir nodos | 178-rev3 | **pendiente** |
| Umbral texto normal 4.5:1 (RF-27, `RATIO_MINIMO_AA`, axe `expectedContrastRatio`) | rev2 filtro “aplicables” (ratio&lt;4.5 y expected≥4.5); no aserta `violations===0` de forma directa | Parcial: el filtro es más débil que DEV. 179-r11 sí asertó 0, **otro usuario/tema** | Aserción `violations===0` + detalle de nodos | 178-rev3 | **parcial** (histórico) / **pendiente** (vigente) |
| Muestra CSS de componentes del dashboard (rev2 L150–203) | `G94-rev2-178-ratios-css.json`; fondos transparentes → ratio null; NAV 1.15 | No vigente; método de fondo efectivo ausente en rev2 | Recalcular con fondo efectivo; no tratar NAV contenedor como texto | 178-rev3 diagnóstico | **pendiente** |
| Cuatro textos muted del sidebar ≥ 4.5:1 (incumplimiento G94 rev8; mismos selectores) | rev2: logout `#7D9A75` sin ratio (bg transparente). 179-r11: **productor oscuro** 5.08 | **No cubierto para 178**: 179 no es admin ni tema activo del admin | Medir los 4 nodos en dashboard admin | 178-rev3 sidebar | **pendiente** (178) |
| GET contexto/tema **solo lectura** (rev2 L251–272) | contexto finca 34, identidad null | No vigente (vínculo admin–finca 1) | GET lectura; **sin PATCH** | 178-rev3 | **pendiente** |
| Aplicar `color_ajustado` si `cumple_aa=false` (DEV 178; solapa 179) | rev2: accesibilidad null → no se evaluó. 179-r11: oscuro productor `#249453` | 179 cubre el estímulo de variante. 178 no debe repetir PATCH ni espera `#249453` | Como mucho persistir CSS observado, **sin** asertar hex de 179 | Fuera del núcleo 178-rev3 (diagnóstico brand) | **cubierto por 179-r11** para productor oscuro; **no es CA exclusivo 178** |
| Tema claro y oscuro / todas las rutas CU-06 | Nunca en 178. 179-r11 solo oscuro productor | No exigido por el spec 178 existente | Si se ampliara el alcance, haría falta mandato escrito | No en 178-rev3 | **no verificable** / fuera de spec 178 |
| G94 conjunto 178+179 post-deploy | 179-r11 PASS; 178 última TEST 2026-09-25 | No | 178-rev3 PASS + decisión de grupo | Tras autorización | **pendiente** (G94) |

**179 rev11 no cubre las filas 178.** Solo la fila de variante oscura/`#249453`.

---

## 3. Brechas y justificación

1. **Evidencia 178 obsoleta.** Fecha 2026-09-25, admin finca 34, `--brand-500=#2e8634` (token por defecto), identidad nula. El redespliegue y el vínculo admin–finca 1 invalidan esa muestra.
2. **No reutilizar `tc_m09_g94_rev2_test.cy.js`.** El segundo `it` hace PATCH de identidad finca 4. `overwrite: true` y `Resultados/` plano **pisarían** JSON rev2. `solo178` sigue escribiendo en el mismo directorio.
3. **Selectores rev2** (`header, nav`, primer `p`, primer `button`) miden mal el contraste (fondos `rgba(0,0,0,0)`). Hay que usar fondo efectivo (como 179-rev11), sin copiar la espera `#249453`.
4. **Alcance CU-06 completo:** no está especificado en el caso 178 automatizado. Declararlo **fuera de alcance** de esta revalidación, no “cubierto”.
5. **Especificación formal de CA:** ausente como artefacto independiente; los CA se toman del spec y de 02. Eso **no bloquea** una revalidación alineada al `it` histórico, pero impide afirmar CA no escritos.

---

## 4. Propuesta concreta de revalidación

Una corrida **solo 178**, lectura, dashboard **admin**, tema **que ya tenga** (sin PATCH `theme_mode`, sin `/tema/global`, sin identidad):

1. Login `admin@pecuaria.co` → `/dashboard`.
2. GET tema + contexto (evidencia).
3. Persistir `data-theme`, `--brand-500` observado (sin exigir `#249453`).
4. Persistir los cuatro nodos del sidebar con fondo efectivo y ratio.
5. Axe `color-contrast`; persistir; **`violations === 0`**.
6. Aserción AA 4.5 en esos cuatro nodos si están presentes (ampliación justificada por RF-27 + hallazgo rev8 del mismo grupo, no por 179).

No repetir: espera 20 s a `#249453`, PATCH tema=2, login productor, ratio marca vs `#171A15` de 179.

---

## 5. Archivos a crear / no tocar

**Creados en esta tarea (no ejecutados):**

- `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_178_rev3_test.cy.js`
- `…/cypress.config.178.rev3.cjs`
- `…/Resultados/178-rev3/NO_EJECUTADO.md`
- este informe `analisis_TC-M09-G94/28_cobertura_y_revalidacion_178.md`

**No modificar:** specs/evidencias rev1–rev2 178, rev4–rev11 179, RLS, usuarios, identidades.

Comando **cuando se autorice**:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.178.rev3.cjs
```

desde `sgpmp-backend`. Una sola vez. No es este ciclo.

---

## 6. Validaciones locales

| Comando | Resultado |
|---|---|
| `node --check` spec 178-rev3 | 0 |
| `node --check` config 178-rev3 | 0 |
| `G94-rev2-178-axe.json` sigue en disco | sí |
| Cypress TEST | **no ejecutado** |

---

## 7. Decisión

| Pregunta | Respuesta |
|---|---|
| ¿Bloqueado por falta total de especificación? | **No.** Hay título, spec y RF-27/1.4.3. Falta matriz CA independiente (declarado). |
| ¿El spec rev2 es válido para el frontend actual? | **No** (evidencia stale + riesgo de PATCH 179 + overwrite). |
| ¿Listo para ejecutar? | **Sí, el 178-rev3, solo con autorización explícita.** |
| ¿G94 aprobado? | **No.** 179 rev11 PASS; 178 revalidación **pendiente**. |

Riesgo residual: si el dashboard admin no monta los cuatro selectores de sidebar, 178-rev3 fallará de presencia (hay que verlo en evidencias, no relajar umbral).
