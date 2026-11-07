# 06 — Plan de corrección y reejecución (pendiente de autorización)

**Estado:** propuesta. **No aplicar código, no ejecutar contra TEST, no commit/push** hasta autorización expresa.

La nueva ejecución es una **fase posterior**.

---

## Diagnóstico que alimenta el plan

- Variante (179) evidenciada en rev4; runner FAIL por `after` 401.
- 178 cubre solo dashboard; no reejecutar 178 no reabre por sí el grupo, pero una reejecución de G94 debería **reconfirmar 178** o declarar explícitamente que se reusa rev2 con caducidad.
- Causa más probable del 401: JWT de productor capturado en login, invalidado por refresh al visitar dashboard. Misma clase G95: se resolvió con **login adicional solo para restore**.

---

## 1. Corrección propuesta del hook (no aplicada)

**Archivo:** `tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94_179_rev4_test.cy.js`  
(o un `*_rev5_test.cy.js` **nuevo**, sin reescribir el spec histórico de rev4).

Cambios concretos:

1. En `restoreTodo()`, **no** reutilizar `tokenProd` ni `tokenAdmin` capturados al inicio si hubo `cy.visit` posterior.
2. Obtener tokens **frescos** con `cy.request` POST `/sesiones/` (admin y productor) inmediatamente antes de cada PATCH de restore. Contraseña solo vía `Cypress.env('contrasena')`.
3. Persistencia de evidencia de restore: `writeFile` con `{ http, code }` **redactando** el token. Si status ≠ 200, guardar body `code`/`message`.
4. Orden: restaurar **identidad** (admin fresco) y **tema** (productor fresco); luego GET de verificación vs snapshot.
5. `failOnStatusCode: false` se mantiene; el expect 200 sigue siendo el criterio, pero un segundo intento tras re-login si el primero es 401.

**No** cambiar aserciones de variante para forzar PASS.  
**No** eliminar el expect de restore 200.

---

## 2. Autenticación y permisos

- Productor: PATCH tema individual (ya funcionó en el `it`).
- Admin: PATCH identidad finca 1 (ya funcionó en el `it`).
- No usar cookie de refresh del browser en `cy.request` salvo diseño explícito; preferir **login password grant** de corta duración al final.
- No compartir Bearer entre UI y API restore.

Si tras login fresco el PATCH tema sigue 401: entonces **sí** investigar producto (permisos, finca, usuario). Hasta ahora la evidencia no apunta ahí.

---

## 3. Mejoras de registro de errores

Escribir siempre:

- `G94-revN-179-restore-tema.json`: status, `code`, timestamp, `theme_mode` pedido.
- `G94-revN-179-restore-identidad.json`: equivalente.
- `G94-revN-179-verificacion-final.json`: GET tema + GET identidad vs snapshot.
- Intercept `POST /sesiones/refresh` durante el `it` → `G94-revN-179-refresh.json` (status, recuento). Sirve para **demostrar** rotación.

Redactar JWT en todos los JSON.

---

## 4. Restore aunque falle una aserción previa

`after()` ya corre si el `it` falla. Completar:

- `after` debe usar `Cypress.on` / encadenar restore **sin** depender de variables no asignadas: flags `patchedId`/`patchedTema` ya existen; inicializar snapshots a `null` y saltar restore si no hubo PATCH.
- Evitar que un `expect` en identidad aborte el PATCH tema: restaurar **ambos** con `cy.then` independientes o `finally` lógico (dos `cy.request` siempre si el flag está en true).
- No usar `this.skip()` en after.

---

## 5. Comprobar estado final = inicial

Criterio objetivo:

- GET identidad finca 1: `primary_color` = snapshot (`#1A6B3C` en rev4).
- GET tema productor: `theme_mode` = snapshot (2 en rev4).
- Opcional: GET contexto UI `identidad_visual.primary_color` alineado.

Si el GET final ≠ snapshot → **RECHAZADO por limpieza**, aunque la variante hubiera pasado.

---

## 6. Verificación independiente del contraste de la variante

Añadir (rev nueva, sin debilitar 178):

1. Tras CSS `#757575`, `axe.run` **con** `expect(violations, ids).to.eq(0)` **o**, si hay violaciones preexistentes no causadas por la variante, documentar baseline vs delta (no silenciar violaciones nuevas).
2. Medir `--brand-500` vs fondo real (`--surface-card` / `html` background) con fórmula WCAG o tarea Node; asertar ≥ 4.5 para texto de marca si el caso mantiene ese umbral.
3. Distinguir en el informe: texto normal 4.5:1 vs UI 3:1 (1.4.11) **sin cambiar** el criterio de aceptación original del caso (4.5:1) salvo decisión del líder.

178: o reejecutar dashboard en el mismo theme_mode que 179 (claro + variante) para no mezclar temas.

---

## 7. Evidencias a generar (rev5, si se autoriza)

- Mocha JSON/HTML/XML (el automático **es** el veredicto de runner).
- Acta `G94-rev5-*-ejecucion.txt` que **cite** el JSON, no que lo contradiga.
- CSS antes/después, snapshots, contexto, axe **con nodos** (no solo `violations: n`).
- Screenshot dashboard light.
- Restore + verificación final.
- No borrar rev1–rev4.

---

## 8. Criterios APROBADO / RECHAZADO / BLOQUEADO

| Veredicto | Condición (todas las de la columna) |
|---|---|
| **APROBADO** (grupo) | 178: axe muestra acordada 0 violaciones (o delta aceptado por líder). 179: `color_ajustado` + CSS aplicado. axe/medición de la UI **resultante** cumple el criterio del caso. Restore HTTP 200 **y** GET final = snapshot. Mocha `failures: 0`. Acta alineada al JSON |
| **RECHAZADO** | Variante no se aplica; o contraste de la UI resultante falla el criterio; o restore/GET final no coinciden; o Mocha fail (incluido hook) |
| **BLOQUEADO** | TEST no autenticable; 503/identidad borrada (clase G91); falta `CYPRESS_contrasena`; finca 1/usuario 2 no disponibles; prohibición de escribir identidad compartida sin ventana de mantenimiento |

Un acta APROBADO con Mocha fail → el caso **sigue RECHAZADO**. No repetir la discrepancia de rev4.

---

## 9. Procedimiento seguro para no alterar TEST compartido

1. Autorización explícita de ventana.
2. Snapshot GET **antes** de cualquier PATCH.
3. Un solo escritor de identidad finca 1 durante la ventana (no paralelizar G94 con otros RF-26/27).
4. Restore con login fresco **incluso si el `it` falla** (try/finally de runner + script Python de emergencia **solo** si Cypress no restauró, con las mismas credenciales de TEST, documentado).
5. No SQL DML.
6. No PATCH `tema` global; solo fuente individual del productor de prueba.
7. Verificar GET final; si falla, **detener** la ventana y avisar: identidad blanca o tema claro residual afectan a otros testers.
8. No usar `#FFFFFF` en identidad más tiempo que el `it`.

---

## 10. Distinguir fallo de producto vs fallo de arnés

| Señal | Producto | Arnés |
|---|---|---|
| `--brand-500` distinto de `color_ajustado` con contexto y tema correctos | Defecto RF-27/front | — |
| API no calcula `color_ajustado` / ratio absurdo | Defecto backend `color_hex` / `AccesibilidadVisual` | — |
| axe 0 en 178 y violación nueva solo tras variante, en texto sobre marca | Defecto de la variante (color o token mal mapeado) | — |
| Login 200, PATCH del `it` 200, restore 401, refresh 200 de por medio | — | Token stale (esta rev4) |
| Login 401 / password | — | Config de CI |
| Mocha fail solo en `after`, evidencias del `it` coherentes | No aprueba el caso | Sí explica el 401 |
| Acta vs JSON | Nunca usar el acta para tapar el JSON | — |

---

## Archivos a tocar si se autoriza implementación (lista, no diff aplicado)

- Nuevo: `tc_m09_g94_179_rev5_test.cy.js` + `cypress.config.179.rev5.cjs` (preferible a editar rev4).
- Opcional: extraer `restoreConLoginFresco()` a un util **solo de tests** bajo `TC-M09-G94/`, sin tocar `src/`.
- Acta nueva en `Resultados/`.
- **Prohibido:** cambiar `src/configuration/**` para hacer pasar el test; cambiar expect de `--brand-500`; borrar JSON rev4.

---

## Fase posterior (checklist de autorización)

- [ ] Líder autoriza ventana TEST y escritura de identidad finca 1.
- [ ] Se implementa spec rev5 (hook con login fresco) **después** de este diagnóstico.
- [ ] Se ejecuta Cypress 178 (o se documenta reuso de rev2) + 179.
- [ ] Restore verificado por GET.
- [ ] Veredicto = Mocha, no el acta sola.
- [ ] Commit/push solo si el usuario lo pide.

Hasta que esos ítems se marquen, G94 permanece **RECHAZADO** con el diagnóstico de este paquete.
