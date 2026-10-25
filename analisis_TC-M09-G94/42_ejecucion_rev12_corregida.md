# 42 — Ejecución TC-M09-179 rev12 corregida (TEST)

**G94:** no se cambia (pendiente). Una sola corrida. Sin commit. Sin reintento. Evidencias de la corrida 38 copiadas a `Resultados/179-rev12/ejecucion-38/` **antes** de esta ejecución.

**Veredicto:** Cypress **FALLÓ**. Restauración **verificada**. Oráculo CSS `--brand-500=#757575` **no medido**.

---

## 1. Fecha y hora

Mocha: **2026-10-10T21:24:57.748Z** – **21:25:33.076Z** (UTC). Duración **35328 ms**. Cypress 14.5.4 / Electron 130.

## 2. Comando y salida

Desde `sgpmp-backend`:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```

`CYPRESS_EXIT=1`. `CYPRESS_contrasena` presente (valor no documentado). `baseUrl` / API: sslip.io TEST. Spec con `sesionVigente` / `adoptarJwt` (informe 41).

## 3. Cypress y aserciones

| | |
|---|---|
| Tests | 1 |
| Passing | 0 |
| Failing | **1** |
| `last_step` | `contexto_api_despues` |
| Error | `cy.wait()` 20000 ms: no hubo request `temaPost` |

El 401 de tema de la corrida 38 **no** se repitió. PATCH tema e identidad **sí** pasaron (HTTP 200). El fallo es posterior: `cy.visit /dashboard` no disparó el GET tema interceptado (`@temaPost`). En el log de restore, `refresh_durante_it` incluye HTTP **401** `REFRESH_TOKEN_REQUERIDO` (sin cuerpo de token).

`--brand-500` / `data-theme` / axe: no medidos.

## 4. Preflight

`apto: true`. Logins frescos 200. GET identidad 200, primary `#1A6B3C`, version 5. GET tema 200, `theme_mode=2`. `jwt_vigente_actualizado.admin` y `.prod`: **true**.

## 5. Snapshot antes de PATCH

`paquete-recuperacion.json`: `generado: antes de cualquier PATCH`, `snapshot_valido: true`. Snapshot identidad version **5**, primary `#1A6B3C`. Snapshot tema **2**. Copia de la corrida 38 en `ejecucion-38/`.

## 6. PATCH de estímulo

| Recurso | HTTP | Efecto |
|---|---|---|
| Tema `{ theme_mode: 1 }` | **200** (`tema-patch-estimulo.json`; `error_code: null`) | GET posterior `theme_mode=1` |
| Identidad `primary=#FFFFFF` | **200** (inferido: `identidad-despues` version **6**, primary `#FFFFFF`) | `claro.ratio=1`, `cumple_aa=false`, `color_ajustado=#757575` |
| Contexto API productor | — | primary `#FFFFFF`, ajustado claro `#757575` |

## 7. Oráculo CSS

No se alcanzó. `brand500_normalizado: null`, `data_theme: null`.

## 8. Restauración (GET posterior)

`after()` corrió. **No** hay `RESTORE-PENDIENTE.json`.

**Identidad:** GET previo al restore: `#FFFFFF`, version 6 (estímulo). PATCH restore **200**. GET final: primary `#1A6B3C`, secondary `#A8D5B5`, org `Acuícola El Remanso`, logo `/assets/logos/remanso.png`, version **7**, `id_finca=1`. `coincide_snapshot: true`. `pendiente: false`.

**Tema:** GET previo: `theme_mode=1`. PATCH restore **200**. GET final: `theme_mode=2`, `fuente=personal`. `coincide_snapshot: true`.

## 9. Evidencias

- Esta corrida: `sgpmp-backend/tests/.../TC-M09-G94/Resultados/179-rev12/` (JSON G94-rev12-179-*, Mocha, captura de fallo).
- Corrida 38: `.../179-rev12/ejecucion-38/`.
- `NO_EJECUTADO.md` y `RECUPERACION_MANUAL.md` no se reescribieron como historial falso.

## 10. Errores, riesgos, estado de la finca

- Causa Mocha: timeout `@temaPost` tras estímulo aplicado (SPA / cookie de refresh `REFRESH_TOKEN_REQUERIDO`, no 401 de PATCH API).
- Riesgo residual: el dashboard del navegador no revalidó CSS; G94 no cierra por esta corrida.
- **Finca 1:** identidad **restaurada y verificada** (`#1A6B3C`, logo y org del snapshot). Tema productor **restaurado y verificado** (`theme_mode=2`). No hace falta recuperación manual ni más escrituras.

---

## Veredicto

| Capa | Resultado |
|---|---|
| Cypress / oráculo CSS | **FALLÓ** |
| Estímulo API (tema 1, primary blanco, `color_ajustado=#757575`) | Aplicado en esta corrida |
| Restauración | **Verificada** (GET) |
| G94 oficial | **Pendiente** |
