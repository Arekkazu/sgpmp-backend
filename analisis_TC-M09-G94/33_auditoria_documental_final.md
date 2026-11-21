# 33 — Auditoría documental final G94 / RF-27 / CU-06 / WCAG 2.1 AA

**Alcance:** solo lectura de evidencias e informes. **No** se ejecutó Cypress. **No** se cambió el estado oficial de G94 (sigue el registro previo: no aprobado / RECHAZADO hasta decisión humana). Specs y JSON históricos **no** se modificaron.

**Recomendación de esta auditoría:** **Pendiente** (no Rechazado: no hay incumplimiento vigente en las muestras post-redespliegue; no Aprobable automático: no hay matriz formal de CA y el alcance de CU-06/estímulo 179 original no está cerrado).

Los números del resumen informado **coinciden** con los JSON abiertos en esta auditoría (redondeos de informes vs. valores de archivo se indican abajo).

---

## 1. Fuentes revisadas

### Definición del grupo (no hay matriz CA independiente)

| Fuente | Qué aporta |
|---|---|
| `01_diagnostico_G94.md` | G94 = **TC-M09-178 + TC-M09-179**; RF-27; CU-06 Personalizar Interfaz |
| `02_analisis_TC-M09-178.md` | 178 = contraste 4.5:1 / axe `color-contrast` en **dashboard**; no recorre resto de CU-06 |
| `03_analisis_TC-M09-179.md` | 179 histórico = variante ante bajo contraste; estímulo rev4 `#FFFFFF` → `#757575` en claro |
| `28_cobertura_y_revalidacion_178.md` | **No existe** hoja CA-178-xx; la matriz de presentación apunta RF-27 a **G91**, no a G94 |
| `color_hex.py` `RATIO_MINIMO_AA = 4.5` | Umbral de producto para color institucional |
| WCAG 2.1 [SC 1.4.3](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html) | Texto normal 4.5:1; grande 3:1 (externo, citado en 02) |

**Criterios derivados de specs** (no de una matriz formal): títulos de `it`, aserciones Cypress 178-rev4 y 179-rev11, y umbral 4.5 del backend. Se marcan como *derivados* en la tabla §2.

### Specs vigentes y evidencias abiertas

| Artefacto | Abierto | Contenido comprobado |
|---|---|---|
| `Resultados/178-rev4/TC-M09-G94_178_rev4_test.json` | sí | `passes: 1`, `failures: 0`, duration **10353**, 17:25:39Z–17:25:49Z |
| `G94-178-rev4-login.json` | sí | `http: 200`, `token_presente: true` |
| `G94-178-rev4-contexto.json` | sí | `theme_mode: 1`, `id_finca: 1`, primary `#1A6B3C` |
| `G94-178-rev4-diagnostico.json` | sí | `pathname /dashboard`, `html_data_theme: light`, `--brand-500 #1A6B3C`, sidebar 6.466… |
| `G94-178-rev4-axe.json` | sí | `ejecutado: true`, `violations: 0`, `color_contrast_pass_nodes: 23` |
| `G94-178-rev4-ultimo-paso.json` | sí | `mocha_state: passed`, `axe_violations: 0` |
| `G94-178-rev4-dashboard.png` | sí (archivo en disco) | captura nominada dashboard; **no** se inspeccionó visualmente píxel a píxel |
| `32_ejecucion_178_rev4.md` | sí | alineado con los JSON |
| `Resultados/rev11/TC-M09-G94_179_rev11_test.json` | sí | `passes: 1`, duration **10694**, 17:09:55Z–17:10:05Z |
| `G94-rev11-179-diagnostico.json` | sí | `data_theme: dark`, brand `#249453`, ratio marca **4.54878**, sidebar **5.07865** |
| `G94-rev11-179-axe.json` | sí | `violations: 0`, 19 pases |
| `G94-rev11-179-restore.json` | sí | `omitido: true`, razón sin PATCH |
| `G94-rev11-179-dashboard-dark-variante.png` | sí (en disco) | ídem: existencia, no OCR |
| `27_ejecucion_rev11.md` | sí | alineado con los JSON (redondea 4.55 y 5.08) |

Informes 01–03, 28–32 y specs `tc_m09_g94_178_rev4_test.cy.js` / `tc_m09_g94_179_rev11_test.cy.js` se usaron para el alcance. **No** se reabrió TEST.

Recálculo independiente (luminancia WCAG, Node, umbral 0.04045) a partir de los hex de los JSON:

| Par | Archivo | Recálculo |
|---|---|---|
| `#249453` / `#171A15` | 4.54878655 | **4.5488** |
| `#97B68F` / `#104325` | 5.07865329 | **5.0787** |
| `#97B68F` / `#0C301B` | 6.46638541 | **6.4664** |
| `#1A6B3C` / `#FFFFFF` (API claro) | contexto 6.54 | **6.5375** |
| `#1A6B3C` / `#171A15` (primario vs oscuro, no pintado en 179) | API 2.69 | **2.6880** |

Los ratios de informes **se rastrean** a colores efectivos de los JSON.

---

## 2. Matriz de trazabilidad

* = criterio **derivado** del spec Cypress o de informes 01–03, no de una matriz CA archivada.

| Criterio o condición | Fuente | Subcaso | Evidencia concreta | Resultado observado | ¿Suficiente? | Brechas |
|---|---|---|---|---|---|---|
| Login admin + dashboard * | spec 178-rev4 / 02 | 178 | `login.json` HTTP 200; diagnóstico `pathname=/dashboard`; Mocha pass | Cumple | Sí para 178 | Solo esa ruta |
| Tema **activo** admin (no forzar oscuro / `#249453`) * | spec 178-rev4; 28 | 178 | `theme_mode=1`, `data-theme=light`, brand `#1A6B3C` | Cumple | Sí para 178 | No cubre oscuro admin |
| Contraste **marca** claro (institucional vs superficie) | RF-27 / `RATIO_MINIMO_AA`; API contexto | 178 (dato API); no asertado CSS vs blanco | API claro 6.54, `cumple_aa` true; CSS `#1A6B3C` | API cumple; CSS no cruzado vs `#FFFFFF` en 178 | Parcial | 178 no calculó ratio marca vs tarjeta clara |
| Contraste **marca** oscuro (`color_ajustado` en `--brand-500`, ≥4.5 vs fondo) * | spec 179-rev11; RF-27 variante; 1.4.3 | 179 | `--brand-500=#249453` vs `--surface-card #171A15` = **4.55:1**; `coincide_oscuro` true | Cumple en sample | Sí para 179 vigente | Estímulo histórico `#FFFFFF`/`#757575` **no** reejecutado post-deploy |
| Contraste **sidebar** texto muted ≥4.5 * | RF-27/1.4.3; hallazgo rev8; specs 178-rev4 y 179-rev11 | 178 y 179 | 178: `#97B68F`/`#0C301B` **6.47:1** (admin, claro). 179: `#97B68F`/`#104325` **5.08:1** (productor, oscuro) | Cumple en ambas muestras | Sí para esos 4 nodos × 2 temas/usuarios | Otros textos del sidebar (ítems `#8AAA80`, etc.) no tienen fila propia |
| Tema oscuro productor * | spec 179-rev11 | 179 | `data-theme=dark`, `theme_mode=2`, sin PATCH | Cumple | Sí | — |
| axe `color-contrast` = 0 en dashboard * | specs; 02; 1.4.3 vía axe | 178, 179 | 178: 0 viol / 23 pass. 179: 0 viol / 19 pass | Cumple en esas corridas | Sí **como muestra axe** | Axe ≠ todo 1.4.3 (hover, focus, otras páginas, no texto) |
| Variante automática RF-27 (backend calcula `color_ajustado`) | 03; `accesibilidad_visual.py` | apoyo API en ambos | 178 y 179 contexto: oscuro `cumple_aa` false, ajustado `#249453` | Cálculo presente | Sí como read-model | No prueba sola la pintura UI |
| Pintura UI de la variante | 03; 179-rev11 | 179 | CSS = `#249453` ≠ primario `#1A6B3C` | Cumple oscuro post-deploy | Sí para ese estímulo | Variante **clara** `#757575` solo evidenciada en **rev4-179** (2026-09-25), Mocha fail por hook |
| CU-06 pantallas de personalización | CU-06; 02 §1 y §8 | ninguno | — | No recorrido | **No** | Configuración de tema/identidad, formularios, tablas: **no verificable** |
| WCAG 1.4.11 (no texto) | 02 (explícitamente fuera del umbral del caso) | — | NAV ratio 1.15 en 178-rev2, excluido | Fuera de alcance del caso | N/A | No exigir 4.5 en contenedores |
| G94 = 178+179 Mocha verde | 01 | grupo | Mocha 178-rev4 1/1 y 179-rev11 1/1, exit 0 | Runners PASS | Parcial para cierre oficial | Ver §5 |
| Restauración 179 | spec 179-rev11 | 179 | restore omitido, `patched_tema: false` | Coherente | Sí | No prueba restore 200 (no hubo escritura) |

**Axe 0 no cubre:** rutas distintas de `/dashboard`; estados hover/focus; texto en canvas/imagen; 1.4.11; “todo el tema” (02 §8). Eso se deja **no verificable**, no se da por cubierto.

---

## 3. Inspección de evidencias vs resumen informado

El resumen de la solicitud **cuadra** con los archivos:

| Afirmación | JSON |
|---|---|
| 178 exit 0, ~10 s, admin, light, `#1A6B3C`, sidebar 6.47, axe 0 / 23 | Mocha 10353 ms; diagnóstico y axe citados |
| 179 exit 0, productor, dark, `#249453`, marca 4.55, sidebar 5.08, axe 0 / 19, sin PATCH | diagnóstico, restore omitido, axe |

Capturas existen con nombres de esas corridas. `diagnostico.json` de ambos lleva `axe_violations: null` porque se escribe **antes** de axe; el resultado usable es `*-axe.json` / `ultimo-paso.json`.

No se inventaron hex ni ratios distintos de esos archivos.

---

## 4. Brechas

1. **Sin matriz formal de aceptación G94** en el repositorio (28). Cualquier “todos los CA” sería invención.
2. **CU-06 incompleto** respecto al caso de uso (configuración, otras vistas): nunca estuvo en 178/179 automatizados (02).
3. **Estímulo 179-rev4** (`primary #FFFFFF`, `--brand-500=#757575`, `data-theme=light`) **no** se revalidó en el frontend redesplegado. Rev11 cubre la variante **oscura** de `#1A6B3C`. No hay incumplimiento actual de ese estímulo; está **sin evidencia vigente**.
4. 178 no midió ratio marca vs `#FFFFFF` en CSS (sí lo declara la API).
5. Axe no equivale a WCAG 1.4.3 de toda la aplicación.
6. Inspección visual de PNG no realizada (solo existencia de archivo).

**No hay** evidencia vigente de fallo 1.4.3 en los dashboards medidos (rev8 3.64:1 quedó superado en 178-rev4 y 179-rev11).

---

## 5. Recomendación final

| Nivel | Recomendación | Razón |
|---|---|---|
| Incumplimiento WCAG en muestras actuales | **No demostrado** | axe 0; ratios sidebar y marca oscura ≥ 4.5, rastreados a hex |
| Subcasos automatizados vigentes (178-rev4, 179-rev11) | Runners **PASS**, evidencias coherentes | Abierto en JSON Mocha y mediciones |
| **G94 / RF-27 / CU-06 (cierre oficial)** | **Pendiente** | Falta matriz CA; CU-06 no barrido; estímulo 179 claro `#FFFFFF` no reejecutado; no convertir dos PASS Cypress en aprobación global |

**No Rechazado:** no hay hallazgo actual que incumpla 4.5:1 en las evidencias de cierre.

**No Aprobable** como sello automático de este informe: el propio encargo pide no hacerlo, y las brechas §4 son de cobertura, no de un FAIL Mocha.

El estado oficial **no se cambia aquí**. Históricamente el grupo figuraba RECHAZADO; esta auditoría **no** lo actualiza.

---

## 6. Acciones pendientes (si se busca cierre oficial)

1. Decisión humana: aceptar el alcance *dashboard + specs vigentes* como G94, o exigir revalidación del estímulo `#FFFFFF` y/o una pantalla de CU-06.
2. Si se acepta el alcance actual, registrar el veredicto oficial **aparte** de este documento.
3. Opcional: documentar una matriz CA mínima (178 dashboard 1.4.3; 179 variante del tema activo) para no depender solo de specs.
4. No hace falta Cypress adicional **salvo** que se elija ampliar alcance.

Ninguna ejecución nueva en esta tarea.
