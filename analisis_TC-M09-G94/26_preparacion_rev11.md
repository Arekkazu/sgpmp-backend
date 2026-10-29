# 26 — Preparación TC-M09-179 rev11 (espera `--brand-500` = `#249453`)

**G94 permanece RECHAZADO.** Esta tarea **no** ejecutó Cypress contra TEST. No hay commit, push ni despliegue. No se afirma que el frontend TEST esté corregido.

Alex anunció corrección del sidebar y redespliegue; la corrida TEST queda **pendiente** de esa confirmación y de autorización explícita.

---

## 1. Git

Rama de trabajo: **`laura`**. HEAD `ad55f049` (`Merge branch 'laura' of … into test`).

| Referencia | SHA | Relación |
|---|---|---|
| `HEAD` / `laura` | `ad55f049` | actual |
| `origin/test` (tras `git fetch origin test`) | `ad55f049` | **igual a laura** |
| `origin/laura` | (282 commits atrás) | no se hizo push |
| rama local `test` | `115418da` | **desactualizada** vs `origin/test`; no se usó |

`git rev-list --count HEAD..origin/test` = **0**. No había commits de `test` pendientes de integrar. No se hizo merge (evita ruido y no hay nada que traer). Archivos locales: solo **untracked** (specs/evidencias QA); ningún cambio tracked sucio. No hubo conflictos ni riesgo de pérdida por merge.

Evidencias rev4–rev10 y specs históricos **intactos** (no se sobrescribieron).

---

## 2. Nueva revisión

**rev11** (siguiente libre; no reutiliza rev10).

| Entregable | Ruta |
|---|---|
| Spec | `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev11_test.cy.js` |
| Config | `…/cypress.config.179.rev11.cjs` |
| Evidencias (vacío salvo marcador) | `…/Resultados/rev11/` |
| Marcador | `…/Resultados/rev11/NO_EJECUTADO.md` |
| Informe | `analisis_TC-M09-G94/26_preparacion_rev11.md` |

Reporter: `Resultados/rev11/TC-M09-G94_179_rev11_test`. Capturas: `Resultados/rev11/screenshots-179-rev11-test`. `trashAssetsBeforeRuns: false`.

### Archivos modificados / creados

**Creados:** spec rev11, config rev11, `Resultados/rev11/NO_EJECUTADO.md`, este informe.

**No tocados:** `tc_m09_g94_179_rev{4–10}_test.cy.js`, configs rev5–rev10, JSON/HTML/capturas históricas, RLS, permisos, producto `src`.

### Cambios de diseño respecto a rev9/rev10

- **rev9** abortó en GET admin identidad exigiendo `null` (~2 s, sin dashboard).
- **rev10** esperó objeto admin, llegó a dashboard y `data-theme=dark`, **luego** midió `--brand-500` (`#1A6B3C` ≠ `#249453`) y axe (sidebar 3.64:1).
- **rev11:**
  1. Quita por completo el GET auxiliar `/identidad-visual/{finca}` del **admin** (ni `null` ni objeto). La visual corre solo con `productor@pecuaria.co` y `GET /interfaz/contexto`.
  2. No altera pruebas de contrato independientes ni RLS/usuarios/fincas/identidad.
  3. Persiste diagnóstico temprano (incluye `brand500_computed`, `data-theme`, URL).
  4. Espera con reintentos Cypress (`cy.document({ timeout: BRAND_WAIT_MS })`, **20000 ms**) a:

     `getComputedStyle(document.documentElement).getPropertyValue('--brand-500').trim().toUpperCase() === '#249453'`

  5. Si el timeout vence, el `expect` falla con **observado**, `data-theme`, URL y `timeout`. No se escribe CSS ni se toca el DOM.
  6. Solo después: registro de tema/CSS, ratios con **fondo efectivo** (sube padres si el nodo es transparente; evita el falso `#000000` / 6.75:1 de rev10), axe, aserciones 4.5:1 y axe 0.
  7. Snapshot + PATCH tema personal **solo si** `theme_mode ≠ 2`; restore igual que rev10.

Constante explícita: `BRAND_OSCURO_ESPERADO = '#249453'` (mismo hex que `color_ajustado` oscuro de finca 1 en evidencias rev8–rev10). También se compara con el hex del GET contexto del productor.

---

## 3. Comandos locales

```
git fetch origin test
git rev-parse HEAD origin/test
git merge-base HEAD origin/test
git rev-list --count HEAD..origin/test
node --check …/tc_m09_g94_179_rev11_test.cy.js
node --check …/cypress.config.179.rev11.cjs
```

Resultados: fetch OK; SHAs iguales; count 0; **SPEC_CHECK=0**, **CONFIG_CHECK=0**.

Cypress TEST: **no ejecutado**.

---

## 4. Criterio de espera `#249453`

Tras login productor, snapshot/contexto y (si aplica) PATCH+reload, el spec **no mide contraste** hasta que el CSS calculado de `<html>` tenga `--brand-500` = `#249453`. Timeout 20 s con reintentos nativos de `.should()`. Mensaje de fallo incluye último valor, `data-theme`, URL y tiempo de espera.

---

## 5. Qué falta para ejecutar

1. Confirmación de Alex de que el frontend TEST ya incluye la corrección del sidebar y la aplicación de `color_ajustado` oscuro en `--brand-500`.
2. Autorización explícita de **una** corrida:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev11.cjs
```

Hasta entonces G94 sigue **RECHAZADO**. TC-M09-178 no se reejecutó en este ciclo; la cobertura conjunta 178+179 sigue pendiente de evidencia TEST posterior al redespliegue.
