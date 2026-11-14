# 21 — Ejecución Cypress TC-M09-179 rev9 TEST

**G94 permanece RECHAZADO.** Una sola corrida. Exit **1**. HEAD `laura` `ad55f049`. Cypress 14.5.4 / Electron 130.

Precondiciones OK: spec/config rev9, `node --check`, reporter `TC-M09-G94_179_rev9_test`, screenshots `screenshots-179-rev9-test`, JSON rev8 presente, `CYPRESS_contrasena` configurada (valor no documentado), restore omite si no hay PATCH.

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev9.cjs
```

Mocha: 1 test, 0 pases, 1 fallo, **2044 ms**, `2026-10-10T15:33:58.352Z`–`15:34:00.396Z`. `isHook: false`.

El **diagnóstico temprano de dashboard no se guardó**: el `it` abortó en el GET admin de identidad, **antes** de `cy.visit` login.

---

## Informe pedido

### 1. Exit y Mocha

Exit Cypress **1**. Fail: `GET identidad admin 200 null (diseño): expected { Object (id_identidad_visual, id_finca, ...) } to equal null`.

### 2. pathname y data-theme; espera oscuro

**No verificados** (no hubo dashboard). `estado-tema-final.json` es el documento Cypress residual (`pathname: blank`, `origin: null`, html sin `data-theme`). No se interpreta como UI TEST. La espera de 20 s a `html[data-theme=dark]` **no se ejecutó**. Criterio visual **sin verificar**.

### 3–4. `--brand-500` y comparación

No medidos. `coincide_oscuro` null.

### 5. Ratio CSS ≥ 4.5

No calculado. Aserción no ejecutada.

### 6. axe

`ejecutado: false`. No se declara `color-contrast = 0`.

### 7. Cuatro nodos sidebar

No medidos (`sidebar-nodos.json` ausente).

### 8. Último paso y causa

- `last_step`: **`inicio`**
- Hecho: el spec exige `GET /identidad-visual/1` con admin = **HTTP 200 y body `null`** (diseño RLS de corridas rev6–rev8). En esta corrida el body es un **objeto** con al menos `id_identidad_visual` e `id_finca`.
- `G94-rev9-179-admin-identidad-diseno.json` **no está en disco** (`writeFile` en el mismo `then` que el `expect` síncrono, mismo patrón que el hueco de rev7).
- Hipótesis no demostrada: cambió visibilidad RLS o hay fila visible al admin en TEST. No se afirma causa. **No se hizo PATCH ni se tocó identidad.**

### 9. Tema personal y restore

Snapshot de tema productor **no** se ejecutó. `patched_tema: false`. Restore **omitido** (`no hubo PATCH`). Identidad: solo GET admin (lectura); el `it` falló al asertar null.

### 10. Auth / refresh

Login productor UI **no** se alcanzó. `refresh_log`: `[]`. GET tema navegador: no registrado.

### 11. Rutas

- `.../Resultados/TC-M09-G94_179_rev9_test.json`
- `.../TC-M09-G94_179_rev9_test.html`
- `.../G94-rev9-179-ejecucion.txt`
- `.../G94-rev9-179-ultimo-paso.json`
- `.../G94-rev9-179-estado-tema-final.json`
- `.../G94-rev9-179-axe.json`
- `.../G94-rev9-179-restore.json`
- `.../screenshots-179-rev9-test/... (failed).png`

Ausentes (no se llegó): `diagnostico-temprano.json`, `diagnostico.json`, `css-despues.json`, `sidebar-nodos.json`, `snapshot-tema.json`, `contexto-antes.json`, `tema-sin-patch.json`.

Rev8 JSON/HTML siguen en disco.

---

## Decisión

| | |
|---|---|
| data-theme=dark | **Sin verificar** |
| Color / ratio / axe / sidebar | **Sin verificar** |
| TC-M09-179 | Mocha **FAIL** (precondición admin identidad ≠ null) |
| TC-M09-178 | Sigue rev2 |
| **G94** | **RECHAZADO** |

No se reejecuta Cypress. No se cambia el producto.
