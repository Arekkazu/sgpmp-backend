# 07 — Propuesta técnica rev5 (antes de tocar el spec)

Fecha de la propuesta: 2026-10-10.  
**Veredicto histórico G94 / rev4: no se modifica. Sigue RECHAZADO.**  
**Esta revisión no se ejecutó contra TEST.**

---

## 1. Diagnóstico de causa del HTTP 401 (rev4)

### Hechos confirmados por evidencia de G94

| Hecho | Evidencia |
|---|---|
| El fail de Mocha es `after all`, no `--brand-500` | `Resultados/TC-M09-G94_179_rev4_test.json` (`expected 401 to equal 200`, mensaje `restore theme_mode HTTP`) |
| El PATCH que falló es `PATCH /configuracion/personalizacion/tema` con `tokenProd` | `tc_m09_g94_179_rev4_test.cy.js` `restoreTodo()` + aserción `restore theme_mode HTTP` |
| Ese mismo `tokenProd` **sí** autenticó GET/PATCH tema y GET contexto **después** del primer aterrizaje en `/dashboard` | mismo spec, líneas 173–235; evidencias `G94-rev4-179-tema-tras-patch.json`, `G94-rev4-179-contexto-api-despues.json` |
| Entre esas llamadas 200 y el `after` hay un **segundo** `cy.visit(.../dashboard)` | spec L237–239 |
| Tras ese visit, el **navegador** obtuvo GET tema HTTP 200 (`theme_mode=1`) | `G94-rev4-179-tema-browser.json` |
| Login inicial admin y productor fueron HTTP 200 | JSON Mocha, código del `it` |
| El spec **no** intercepta `POST /sesiones/refresh` y **no** guarda el body del 401 | ausencia en `Resultados/` |

### Lo que no está demostrado en G94

- El `error_code` del 401 (`TOKEN_REVOCADO`, `TOKEN_REQUERIDO`, `SESION_EXPIRADA_INACTIVIDAD`, u otro).
- Que en la corrida rev4 existiera un `POST /sesiones/refresh` HTTP 200.
- Que `tokenAdmin` también estuviera inválido (el mensaje apunta solo al restore de tema).

Por tanto **no se afirma** en esta propuesta que la causa sea rotación/revocación. Esa es una **hipótesis alineada** con:

- `src/identity_access/infrastructure/dependencies.py` (`fecha_uso is not None` → 401 `TOKEN_REVOCADO`);
- `tests/integration/test_refresh_token.py::test_access_token_anterior_a_un_refresh_queda_revocado`;
- `anotaciones/modulo_9/tc_m09_g94_contexto_401_no_es_bug.md`;
- el patrón G99 (relogin solo para restaurar).

El frontend **de este workspace** (`SGPMP-FRONT-END-PWA/src/shared/auth/AuthContext.tsx`) usa `localStorage` y **no** llama `/sesiones/refresh` en el montaje. El desplegable de TEST puede diferir. Esa divergencia refuerza que la causa exacta debe **medirse** en rev5, no presuponerse.

### Causa demostrada (alcance seguro para corregir el arnés)

El hook reutiliza un Bearer de productor **capturado en el login UI** y lo envía por `cy.request` **después** de una recarga completa de página. Ese mecanismo es el que devolvió 401. Corregir el arnés consiste en:

1. **Diagnosticar** el 401 (sonda GET con el token capturado, persistir `http` + `error_code`).
2. **Autenticar de nuevo** con las mismas credenciales de prueba (POST `/sesiones/`) **solo para restaurar**, sin omitir Bearer ni relajar RBAC.
3. Verificar con GET que identidad y tema coinciden con el snapshot.
4. Fallar la suite si restore o verificación no dan 200/coincidencia — el JSON Mocha sigue siendo el veredicto.

Si la sonda rev5 muestra `TOKEN_REVOCADO`, la hipótesis queda **confirmada**. Si muestra otro `error_code`, el informe de ejecución deberá reclasificar la causa. El relogin de restore sigue siendo el arreglo correcto del arnés en ambos casos (token inválido ≠ bypass de seguridad).

---

## 2. Archivos que se planea crear o cambiar

| Acción | Ruta | Motivo |
|---|---|---|
| **Crear** | `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev5_test.cy.js` | Spec nuevo; no edita rev4 |
| **Crear** | `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev5.cjs` | Reporter `..._rev5_test` para no sobrescribir Mocha rev4 |
| **Crear** | `sgpmp-backend/tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/G94-rev5-179-NO_EJECUTADO.md` | Deja explícito que no hay PASS |
| **Crear** | `analisis_TC-M09-G94/07_propuesta_rev5.md` | Este documento |
| **Crear** | `analisis_TC-M09-G94/08_cambios_rev5.md` | Inventario post-edición |
| **No tocar** | `tc_m09_g94_179_rev4_test.cy.js`, `cypress.config.179.rev4.cjs`, todos los `G94-rev4-*` y `TC-M09-G94_179_rev4_test.*` | Evidencia histórica |
| **No tocar** | `src/**`, otros casos, configs globales de TEST | Fuera de alcance |

178 no se reescribe: su última evidencia TEST es rev2. La reconfirmación 178 queda como paso pendiente de autorización (login + axe, sin PATCH de identidad).

---

## 3. Solución propuesta (detalle)

### 3.1 Restore

- Interceptar `POST /sesiones/refresh` durante el `it` (solo recuento y status, sin tokens).
- En `after`:
  1. Si no hubo PATCH, no restaurar.
  2. Sonda: GET tema con `tokenProd` capturado → JSON `G94-rev5-179-sonda-token-capturado.json`.
  3. POST `/sesiones/` admin y productor (un intento cada uno).
  4. PATCH identidad (admin fresco) y PATCH tema (productor fresco), **ambos** antes de cualquier `expect` de restore, para no abortar el segundo.
  5. GET identidad y GET tema; comparar con snapshot.
  6. Escribir `G94-rev5-179-restore.json` y `G94-rev5-179-verificacion-final.json`.
  7. `expect` HTTP 200/201 y coincidencia de snapshot. Si fallan, Mocha `failures ≥ 1`.

### 3.2 Contraste tras la variante (criterio del caso: 4.5:1 texto/marca vs fondo)

1. Seguir exigiendo `--brand-500 === color_ajustado` (`#757575` para `#FFFFFF` en claro).
2. Calcular ratio WCAG 2.1 entre `--brand-500` y el fondo de superficie (`--surface-card` o `html` background; respaldo `#FFFFFF` del dominio). **`expect(ratio).to.be.at.least(4.5)`**.
3. axe `color-contrast` con **nodos** (fg, bg, ratio, target). **`expect(violations.length).to.eq(0)`**.  
   Nota: rev4 ya registró 1 violación sin nodos. Rev5 puede RECHAZAR por accesibilidad aunque el restore funcione. Eso es correcto y no se silencia.

### 3.3 Acta vs automático

- Plantilla de acta (solo se rellena tras ejecución): el veredicto es `stats.failures` del JSON Mocha.
- Frase prohibida: clasificar APROBADO si Mocha falló.
- Prefijos de archivo `G94-rev5-*` / reporter `TC-M09-G94_179_rev5_test`.

### 3.4 Seguridad

- Sigue exigiendo Bearer.
- Credenciales solo por `Cypress.env('contrasena')`.
- No se desactiva rotación de tokens ni se reutiliza un JWT inválido como “éxito”.
- Relogin es el mismo POST `/sesiones/` que el producto ofrece a un usuario legítimo.

---

## 4. Criterios de rev5 (cuando se autorice ejecutar)

APROBADO 179 solo si Mocha `failures === 0`, lo que implica variante CSS, ratio ≥ 4.5, axe 0, restore 200 y GET = snapshot.  
El grupo G94 además necesita 178 reconfirmado o aceptación explícita del líder de reusar rev2.  
Sin esa ejecución, **G94 permanece RECHAZADO**.
