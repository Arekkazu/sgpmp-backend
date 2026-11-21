# 38 — Ejecución controlada TC-M09-179 rev12 (TEST)

**G94:** no se cambia (sigue pendiente). Una sola corrida. Sin commit, push ni deploy. Sin reintento. `NO_EJECUTADO.md` de preparación **no** se reescribió.

**Veredicto rev12:** **FALLÓ** (funcional Cypress). **Restauración:** identidad **no modificada**; tema **verificado** igual al snapshot (`theme_mode=2`). No hay `RESTORE-PENDIENTE.json`. No se aplicó el oráculo `#757575`.

---

## 1. Fecha y hora

Mocha: **2026-10-10T21:05:51.569Z** – **21:06:06.362Z** (UTC). Duración **14793 ms** (Cypress reporta ~14 s). Cypress 14.5.4 / Electron 130.

## 2. Comando y salida

Desde `sgpmp-backend`:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```

`CYPRESS_EXIT=1`. Credencial: `CYPRESS_contrasena` en el proceso (valor no documentado). `baseUrl` y `TEST_API`: sslip.io TEST.

## 3. Cypress y aserciones

| | |
|---|---|
| Tests | 1 |
| Passing | 0 |
| Failing | **1** |
| `last_step` | `tema_patch_enviando` |
| `mocha_state` | `failed` |
| Error | `PATCH tema=1: expected 401 to equal 200` |

No se alcanzaron visita post-estímulo, `--brand-500`, axe ni aserciones de marca.

## 4. Preflight

`apto: true`. Logins frescos admin y productor HTTP **200**. GET identidad 200 objeto, `primary_color=#1A6B3C`, `version=5`. GET tema 200, `theme_mode=2`, `fuente=personal`.

## 5. Snapshot y paquete antes del PATCH

Persistidos **antes** del intento de escritura (existen `snapshot-identidad`, `snapshot-tema`, `paquete-recuperacion`; no existe `identidad-despues` ni `tema-tras-patch`):

- `snapshot_valido: true`, `campos_restore_completos: true`
- Identidad finca 1: primary `#1A6B3C`, secondary `#A8D5B5`, org `Acuícola El Remanso`, logo `/assets/logos/remanso.png`, version **5**, `id_usuario` fila **1**
- Tema productor: **2** (personal)

No había paquete previo en `179-rev12/` que se pudiera perder.

## 6. PATCH de estímulo

| Recurso | ¿Se envió? | HTTP | ¿Aplicado? |
|---|---|---|---|
| Tema productor `{ theme_mode: 1 }` | Sí (`escritura_tema_iniciada: true`) | **401** | No: `patched_tema: false`. GET restore posterior `theme_mode=2` (= snapshot) |
| Identidad finca 1 `#FFFFFF` | **No** (`escritura_identidad_iniciada: false`) | — | No se tocó |

El PATCH de tema usó el JWT capturado en el login **UI** del productor (`api(..., 'prod')`). El preflight, con login **fresco**, sí leyó tema 200. Misma clase de 401 que el restore de 179-rev4 (token de SPA no válido para escritura API). **401 no se interpretó como éxito.**

No hubo HTTP 412 ni conflicto de identidad.

## 7. Oráculo CSS

`--brand-500` y `data-theme`: **no medidos** (`brand500_normalizado: null`, `data_theme: null`). axe: no ejecutado (`violations: null`; no se declara 0).

## 8. Restauración y GET posterior

`after()` corrió.

- **Identidad:** restore **omitido** (no se inició escritura). No hay GET de restore de identidad porque no procedía.
- **Tema:** login productor fresco HTTP 200. GET `theme_mode=2` = snapshot. `patch_omitido_ya_coincide: true`. **No** se envió PATCH de restore. `coincide_snapshot: true`. `pendiente: false`.

No se creó `G94-rev12-179-RESTORE-PENDIENTE.json`.

## 9. Evidencias

`sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/179-rev12/`

Incluye Mocha JSON/HTML, snapshots, paquete, preflight, restore, verificación-final, ultimo-paso, axe (no ejecutado), captura de fallo Cypress, `NO_EJECUTADO.md` (marcador de preparación, intacto), `RECUPERACION_MANUAL.md`.

No se tocaron `Resultados/rev11/`, `178-rev4/` ni `G94-rev4-179-*`.

## 10. Errores, limitaciones, riesgos

- El estímulo de tema no puede usar el token del SPA si ese JWT ya no autoriza PATCH; el restore con login fresco **sí** funcionó para leer.
- El oráculo histórico `#FFFFFF` → `#757575` **no** se revalidó.
- Una corrida; no se autoriza otra aquí.
- Riesgo residual de kill de proceso: no aplicó (el hook sí corrió).

## 11. Estado final de la identidad (finca 1)

**No alterada y no requiere recuperación de identidad.** El único PATCH intentado fue de **tema** y respondió 401; el GET con sesión nueva dejó `theme_mode=2` como el snapshot. Primary sigue el valor fotografiado `#1A6B3C` (nunca se envió PATCH RF-26).

No hay procedimiento de escritura adicional que ejecutar ahora.

---

## Veredicto

| Capa | Resultado |
|---|---|
| Cypress / Mocha (`it`) | **FALLÓ** |
| Restauración | Identidad: no escrita. Tema: verificado = snapshot, sin PATCH extra |
| G94 oficial | **Pendiente** (no aprobado) |

Rev12 **FALLÓ**. No se declara G94 aprobado.
