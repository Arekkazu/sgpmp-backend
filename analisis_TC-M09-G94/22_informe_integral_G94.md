# 22 — Informe integral TC-M09-G94 (RF-27 / WCAG 2.1 AA)

**Grupo:** TC-M09-G94 = TC-M09-178 + TC-M09-179  
**Requisito:** RF-27 (personalización de interfaz; contraste mínimo 4.5:1; variante automática ante incompatibilidad con identidad RF-26)  
**Caso de uso:** CU-06  
**Estado de aceptación:** **RECHAZADO**  
**Alcance de este documento:** consolidación de evidencias rev4–rev9 (y 178 rev2). Solo lectura. No Cypress, no mutación TEST, no rev10, no commit.

Informes 10–21 **existen** en `analisis_TC-M09-G94/`. Specs `tc_m09_g94_179_rev4` … `rev9` y `tc_m09_g94_rev2_test.cy.js` existen bajo `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/`.

---

## 1. Resumen ejecutivo

G94 no puede aprobarse. Ninguna corrida 179 rev4–rev9 cerró a la vez: (a) Mocha verde incluidos hooks, (b) variante oscura o clara según el estímulo, (c) ratio CSS ≥ 4.5 asertado, (d) axe `color-contrast` = 0, (e) restauración verificada. 178 solo tiene evidencia **rev2** de axe 0 en el **dashboard de administrador**, no el tema completo ni el modo oscuro del productor.

Hay **un hallazgo de producto observado en TEST** (rev8): cuatro textos del sidebar a **3.64:1** (umbral axe 4.5:1, texto normal). Hay **discrepancia API/CSS** en oscuro (`#249453` vs `--brand-500=#1A6B3C`) medida en rev7 (con `data-theme=dark` asertado) y rev8 (con `data-theme=null`). El backend **calcula** la variante y **no** sustituye el color en BD; eso es coherente con los JSON de contexto. El arnés bloqueó varias veces (wait `@temaPost`, persistencia, precondición admin `null`). RLS admin 200 null (rev5–rev8) frente a objeto en rev9 es una **diferencia observada**, no un mandato de ampliar permisos.

---

## 2. Conclusión técnica principal

1. **RF-27 en API (cálculo):** para `#1A6B3C`, claro cumple AA (ajustado = crudo); oscuro no (`ratio` API 2.69, `color_ajustado=#249453`). Confirmado en contexto productor rev6–rev8. No es un fallo de fórmula por el mero desajuste CSS.
2. **RF-27 en UI TEST:** el SPA **sí inyecta** tokens de marca (rev4: `--brand-500=#757575` = variante **clara** de `#FFFFFF`). En oscuro/productor, lo observado es el **primario / variante clara**, no `#249453`. El workspace local (`useTheme` + `--brand-500` fijo) **no** es el bundle TEST.
3. **WCAG texto en dashboard TEST (rev8):** incumplimiento **confirmado** en cuatro nodos del sidebar; independiente del ratio marca-vs-tarjeta blanca (6.54).
4. **Arnés:** varios FAIL de Mocha no son incumplimientos de contraste (rev5 identidad, rev6 intercept, rev9 admin null vs objeto, persistencia `writeFile` abortada).
5. **178:** cobertura insuficiente para cerrar el grupo.

---

## 3. Cronología rev4–rev9

Leyenda de medición: **falló** = aserción ejecutada y no cumplida; **no ejecutado** = el `it` abortó antes; **sin evidencia** = no hay archivo o no se persistió.

| Rev | Objetivo / flujo | Primera falla | HTTP relevante | Tema / escrituras | Dashboard | CSS | Ratio CSS | axe | Mocha / exit | Evidencia guardada | Conclusión sostenible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **4** (2026-09-25) | Productor; PATCH tema=1 e identidad `#FFFFFF`; medir variante clara | Hook `after`: restore `theme_mode` | PATCH restore tema **401**; login 200; GET tema nav 200 | PATCH tema e identidad; acta alega restore API posterior a `#1A6B3C` / mode 2 | Sí | Sí: `--brand-500=#757575`, `data-theme=light` | **No asertado** en spec | **Ejecutado:** 1 violación, 16 pases; spec **no** exige 0 | 0/1, fail hook; JSON fail | css, contexto, tema-browser, axe (sin nodos de violación), Mocha | Variante **clara** aplicada. Restore Cypress falló (arnés/sesión). Acta «APROBADO» **no** anula Mocha. axe 1 **sin detalle de nodos**. |
| **5** (2026-10-10) | Igual estímulo `#FFFFFF` vía admin GET identidad | GET identidad/1 **null** (intento 3) | GET 200 **null**; auditoría 404 | Sin PATCH | Login UI sí; abortó antes de visita de medición | No ejecutado | No ejecutado | No ejecutado | 0/1, fail `it` | restore omitido, get-identidad, contexto productor `#1A6B3C` | Bloqueo de **precondición/permiso de lectura admin**, no contraste. Productor sí ve identidad en contexto. |
| **6** | Productor; ya oscuro; no PATCH si mode=2; wait GET tema nav | `cy.wait('@temaPost')` 20 s | GET tema `cy.request` 200; refresh nav **401** (sin `error_code`); alias temaPost vacío | Sin PATCH; restore omitido | Sí (URL) | No ejecutado | No ejecutado | No ejecutado | 0/1 | snapshot, contexto `#249453`, tema-sin-patch, restore refresh 401 | Fallo de **arnés** (alias tardío / visit redundante). Contraste **no medido**. 401 refresh ≠ 401 restore rev4. |
| **7** | Medir CSS en dashboard ya cargado, sin wait temaPost | `--brand-500=#1A6B3C` ≠ `#249453` | Login 200 | Sin PATCH; restore omitido | Sí; spec asertó `data-theme=dark` **antes** de leer CSS | **Sí** (Mocha actual/esperado); JSON css **no** en disco | Calculado en spec **no asertado** (abortó en igualdad); archivo ausente | No ejecutado | 0/1 | snapshot, contexto, Mocha | Con **dark asertado**, la marca sigue el primario, no la variante oscura. Persistencia `writeFile` falló (arnés). |
| **8** | Persistir CSS antes de expects | `data-theme=dark` vs **null** | GET tema nav **200** (después del diagnóstico); refresh 0 | Sin PATCH | Sí `/dashboard` | Sí: `#1A6B3C` inline=computed; surface `#FFFFFF` | **Calculado 6.54** vs blanco; aserción ≥4.5 **no ejecutada** | **Ejecutado:** 1 violación, 4 nodos sidebar 3.64 | 0/1 | diagnostico, css, axe detallado, refresh, restore | Diagnóstico útil. Dark **no** confirmado en html. Marca=primario. **Sidebar 3.64 confirmado.** Ratio marca-vs-blanco no equivale a AA del nav. |
| **9** | Esperar `html[data-theme=dark]` 20 s + sidebar | GET admin identidad **objeto** ≠ `null` | GET identidad 200 con cuerpo objeto | Sin PATCH; restore omitido | No | No ejecutado | No ejecutado | No (`ejecutado:false`) | 0/1, ~2 s | ultimo-paso, estado-tema-final (about:blank), axe omitido, Mocha | Bloqueo de **precondición del spec** (esperaba el `null` de rev6–8). Contraste **sin verificar**. Diagnóstico temprano de dashboard **ausente**. |

---

## 4. Problemas por capa

### A. Backend y cálculo de contraste

- `color_ajustado` = `ajustar_para_contraste(color, FONDO_CLARO|FONDO_OSCURO)` en `color_hex.py` / `accesibilidad_visual.py`. No se persiste; `test_el_color_ajustado_no_reemplaza_al_guardado`.
- TEST productor (rev6–rev8 contexto): primario `#1A6B3C`; claro `cumple_aa=true`, ajustado `#1A6B3C`, ratio 6.54; oscuro `cumple_aa=false`, ajustado `#249453`, ratio API **2.69**, fondo `#171A15`. **Coherente** con el código actual.
- Rev2 documentó oscuro `color_ajustado=#83C398` para el mismo primario. Es **diferencia temporal** de valor API; no se concluye defecto de fórmula sin historial de commits del cálculo.
- El CSS que no usa `#249453` **no** implica que el GET contexto esté mal.

### B. Frontend TEST

**Confirmado**

- Inyecta `--brand-*` inline (rev4 y rev8).
- Rev4 light: `--brand-500` = `claro.color_ajustado` de `#FFFFFF` (`#757575`).
- Rev7: `data-theme=dark` asertado; `--brand-500=#1A6B3C`.
- Rev8: `html` `data-theme=null`; `--brand-500=#1A6B3C`; `--surface-card=#FFFFFF`; GET tema nav 200 **después** del snapshot CSS (`diagnostico.tema_browser_log=[]` vs `refresh.json` 200).
- Local `useTheme` + `tokens.css` (`#2e8634` / `#52a057`) **no** explica `#1A6B3C` ni el subtítulo de finca en el logo. TEST ≠ este repo.

**Hipótesis** (no causa cerrada): TEST aplica primario o `claro.color_ajustado`, no `oscuro.color_ajustado` cuando el modo es oscuro. Encaja rev4+rev7; rev8 midió sin dark en html. **Falta** el bundle desplegado.

### C. Sidebar (rev8)

Datos comprobados en `G94-rev8-179-axe.json`: fg `#7d9a75`, bg `#104325`, ratio 3.64, umbral **4.5:1**, 9px/10px `normal` → **texto normal**. Independiente de `--brand-500` vs `--surface-card` (6.54 sobre blanco): otro par, otra superficie (nav verde). La captura muestra main claro + sidebar verde. **No** se afirma que `data-theme=null` cause las 4 violaciones. Rev4 axe 1 violación **sin** nodos: **no** se identifica con estos cuatro.

### D. Arnés

| Bloqueo | Rev | Capa arnés | ¿Impidió ver producto? |
|---|---|---|---|
| JWT encolado null | 5 intento 1 | Sí | Sí |
| `wait('@temaPost')` alias tardío / visit de más | 6 | Sí | Sí (CSS no medido) |
| `writeFile` + `expect` síncrono | 7 (css), 9 (admin json) | Sí | Parcial (Mocha sí guarda actual/esperado en 7) |
| Medir CSS sin esperar `data-theme` | 8 | Sí (carrera) | Parcial (sí hay CSS y axe, dark no confirmado) |
| Exigir identidad admin `null` | 9 (y el inverso en 5: exigir no null) | Spec acoplado a un GET admin que **no** es el criterio RF-27 | Sí en 5 y 9 |
| Restore Bearer viejo | 4 | Sí (sesión) | No para la variante clara del `it` |

`cy.request` no alimenta `cy.intercept`. Eso es Cypress, no RF-27.

### E. Cuenta, permisos, RLS

- **Medición de tema personal / contexto:** `productor@pecuaria.co` (id 2, finca 1).
- **Admin:** control de diseño GET identidad/1; en rev4 también PATCH identidad (estímulo `#FFFFFF`). Alex: RLS de fincas **intencional**; no ampliar admin ni usar `/tema/global`.
- Rev5–rev8: GET admin identidad/1 **200 null**; productor contexto **sí** trae `#1A6B3C`.
- Rev9: el mismo GET admin devuelve **objeto** (`id_identidad_visual`, `id_finca`, …). Diferencia **observada**. No hay JSON de cuerpo en disco. No se clasifica como defecto de producto ni como “RLS roto” sin contrato de esa corrida. No se propone bypass.

---

## 5. Registro de hallazgos

| ID | Título | Capa | Evidencia | Observado | Esperado (RF-27 / caso) | Impacto AA | Clasificación | Prioridad sugerida | Equipo | Falta para cerrar |
|---|---|---|---|---|---|---|---|---|---|---|
| H-G94-01 | Sidebar 3.64:1 (4 nodos) | Frontend TEST / diseño | `Resultados/G94-rev8-179-axe.json` | 3.64; umbral 4.5; texto normal | ≥4.5 texto normal; axe 0 | **Incumplimiento observado** SC 1.4.3 en esos nodos | **Defecto de producto confirmado** (en el DOM medido rev8) | Alta | Frontend | Reproducir con `data-theme` conocido; no asumir que dark lo corrige |
| H-G94-02 | `--brand-500` ≠ `oscuro.color_ajustado` | Frontend TEST (consumo API) | Mocha rev7; `G94-rev8-179-diagnostico.json`; contexto `#249453` | `#1A6B3C` | Flujo alterno: pintar variante del **tema activo** | Variante oscura **no demostrada** en CSS; API sí la calcula | **Hipótesis pendiente** (fuerte en rev7; rev8 sin dark) | Alta | Frontend | Bundle TEST; medición con `html[data-theme=dark]` persistido |
| H-G94-03 | `data-theme=null` rev8 | Frontend y/o arnés | diagnostico + Mocha rev8 | null en `<html>` | Dark si `theme_mode=2` y el cliente lo refleja en html | Impide afirmar que se midió el tema oscuro | **Hipótesis pendiente** (carrera vs no inicializa) | Media | Frontend + QA | Snapshot html/body + GET tema ordenados; rev7 dice que dark **puede** existir |
| H-G94-04 | Admin identidad null vs objeto | Contrato prueba / datos / RLS | rev8 admin json `body_nulo:true`; Mocha rev9 objeto | 200 null (rev5–8) vs objeto (rev9) | Spec 9 exigía null; spec 5 exigía no null | Ninguno directo de contraste | **Bloqueo de ejecución** | Media | QA (contrato del spec); backend solo si el contrato GET admin está mal documentado | Cuerpo persistido; no ampliar RLS |
| H-G94-05 | Sincronización y persistencia Cypress | Arnés | rev6 wait; rev7/9 writeFile; rev4 hook 401 | Varios FAIL sin medir o sin JSON | Evidencia aunque falle el expect | Enmascara o retrasa hallazgo de producto | **Problema del arnés confirmado** | Media | QA | Ya mitigado en parte en rev8/9; no reabrir waits de GET no garantizados |
| H-G94-06 | 178 solo dashboard admin rev2 | Cobertura | `G94-rev2-178-axe.json`, `02_analisis_TC-M09-178.md` | axe 0, 12 pases, admin | Contraste del **tema** (claro/oscuro, más que una vista) | 0 en esa muestra **no** cubre sidebar productor ni oscuro | **Cobertura insuficiente** | Alta (cierre de grupo) | QA + producto | 178 con alcance acordado (productor, ambos temas, o exclusión explícita) |
| H-G94-07 | Restore 401 rev4 | Arnés / sesión | Mocha rev4 after | PATCH tema 401 | Restore 200 con sesión fresca | No es SC 1.4.3 | **Problema del arnés confirmado** (`error_code` no persistido) | Baja si no se reusa Bearer viejo | QA | — |
| H-G94-08 | Cálculo API oscuro 2.69 | Backend (informativo) | contexto rev6–8 | `cumple_aa=false`, `#249453` | Detectar e informar variante | El aviso y el hex **sí** salen; pintar es del cliente | **No es defecto de cálculo** | — | — | El cliente debe consumir oscuro |

---

## 6. Hechos, inferencias, incógnitas

**Hechos:** Mocha 0/1 en 179 rev4–rev9; rev4 variante clara `#757575`; rev7/8 marca `#1A6B3C`; API oscuro `#249453` / 2.69; rev8 sidebar 3.64; 178 rev2 axe 0 dashboard admin; admin GET 200 null luego objeto; no PATCH en rev6–9; RLS intencional.

**Inferencias:** TEST pinta claro/primario; `null` de dark en rev8 es carrera; 401 restore = token rotado.

**Incógnitas:** bundle TEST; `error_code` de 401; nodos de axe rev4; por qué admin dejó de ver `null`; si dark estable pinta `#249453` o corrige el sidebar.

---

## 7. Estado de los subcasos

| | Evidencia | Limitación |
|---|---|---|
| **178** | rev2 TEST, admin, dashboard, axe 0 / 12 pases | No productor, no oscuro, no sidebar rev8, no reconfirmado en 2026-10-10 |
| **179** | rev4 variante clara OK + hook fail; rev7/8 marca ≠ oscuro; rev8 axe 1 | Nunca Mocha verde con axe 0 y restore; oscuro CSS no demostrado |

---

## 8. Aceptación G94

**RECHAZADO.**

- **Incumplido con evidencia:** contraste de los 4 textos del sidebar en el DOM de rev8 (1.4.3 texto normal). Mocha 179 nunca 0 fallos.
- **Sin verificar / incompleto:** `--brand-500` = variante **oscura**; ratio marca vs superficie **oscura** ≥ 4.5 asertado; axe 0 en tema oscuro confirmado; 178 con alcance de grupo.
- **Solo arnés:** wait temaPost, persistencia, restore 401, precondiciones admin invertidas (5 vs 9).
- Un subcaso con muestra verde (178 rev2 o variante clara rev4) **no** aprueba el grupo.

---

## 9. Recomendaciones por equipo

**Frontend TEST:** (1) Consumir `accesibilidad.primary_color.{claro\|oscuro}.color_ajustado` según tema efectivo. (2) Corregir o justificar labels del sidebar 3.64 sobre `#104325`. (3) Definir si `theme_mode=2` debe setear `html[data-theme=dark]` y cuándo. No usar el `useTheme` local como prueba del deploy.

**Backend:** Mantener cálculo y aviso; no persistir la variante. Documentar GET identidad admin 200 null vs objeto. No cambiar RLS para hacer pasar G94.

**QA:** No acoplar 179 a GET admin null/no-null. Medir con productor. Persistir siempre antes de expect. No `wait` de GET no garantizado. 178: acordar alcance o dejar exclusión escrita. No reejecutar Cypress a ciegas.

---

## 10. Acciones para cerrar (sin corridas repetitivas)

1. Frontend: variante por tema + contraste sidebar (H-G94-01, H-G94-02).  
2. Acuerdo de alcance 178 (H-G94-06).  
3. Spec 179: productor + contexto; no depender del JSON admin; evidencia antes de assert; esperar `data-theme` **después** de un snapshot temprano.  
4. Una sola ejecución de cierre **cuando** haya cambio de producto o de contrato, no otra rev solo de arnés.  
5. Restore solo con login fresco si hay PATCH.

---

## Rutas fuente (mínimo)

- Informes: `analisis_TC-M09-G94/10_…` a `21_ejecucion_rev9.md` (todos presentes).  
- Mocha 179: `…/Resultados/TC-M09-G94_179_rev{4,5,6,7,8,9}_test.json`  
- Rev8 axe/diagnóstico: `G94-rev8-179-axe.json`, `G94-rev8-179-diagnostico.json`  
- Rev4 css/axe: `G94-rev4-179-css-despues.json`, `G94-rev4-179-axe.json`  
- 178: `G94-rev2-178-axe.json`, `G94-rev2-test-ejecucion.txt`  
- Cálculo: `sgpmp-backend/src/configuration/domain/value_objects/color_hex.py`, `…/accesibilidad_visual.py`
