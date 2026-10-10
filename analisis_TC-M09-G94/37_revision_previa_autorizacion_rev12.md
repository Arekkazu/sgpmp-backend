# 37 — Revisión previa a autorización TC-M09-179 rev12

Conserva `36_auditoria_restore_rev12.md`. Cypress **no** se ejecutó. G94 sigue **pendiente**. Sin PATCH a TEST, sin commit.

Esta pasada encontró un hueco de concurrencia en el restore de 36 y lo corrigió en el spec local **antes** del veredicto de autorización.

---

## 1. Paquete de recuperación

| Criterio | Comprobado en spec |
|---|---|
| Antes de escrituras | `G94-rev12-179-paquete-recuperacion.json` se escribe en el `then` del GET de tema, **después** de snapshots y **antes** del preflight y de cualquier PATCH (línea de `generado: 'antes de cualquier PATCH'`). Primer PATCH posible: tema, más abajo. |
| Valores para reconstruir | Form: `primary_color`, `secondary_color`, `org_display_name`, `version_en_snapshot`, `logo_path_esperado`, paths, `theme_mode` snapshot, estímulo `#FFFFFF` / tema 1. |
| Válido vs incompleto | `snapshot_valido` (`camposRestoreCompletos() && snapTema != null`) y `campos_restore_completos`. El snapshot de identidad **no** se escribe si fallan hex/org/finca/versión. Sin archivo o `snapshot_valido !== true` → no recuperar a ciegas (`RECUPERACION_MANUAL.md`). |
| Secretos | El paquete no incluye contraseña ni JWT. Preflight/restore solo persisten `http` y `error_code` de logins. Password UI: `{ log: false }`. |
| Ubicación | `tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/179-rev12/` (cwd `sgpmp-backend`). Procedimiento: `RECUPERACION_MANUAL.md`. Config Mocha: mismo directorio; `retries: 0`; `trashAssetsBeforeRuns: false`. |

Si Cypress muere **antes** del paquete, no hay valores de restore: la manual ordena detenerse.

---

## 2. Restauración y concurrencia

**PATCH de estímulo sin confirmación HTTP.** `escrituraIdentidadIniciada` / `escrituraTemaIniciada` se ponen a true **al encolar** el PATCH. El `after()` intenta restore aunque no haya `patchedId` 200.

**Antes de esta revisión (defecto):** el restore hacía PATCH con colores del snapshot y `version` del GET vigente **siempre**. Un 412 del estímulo (otro usuario cambió la finca) dejaba el GET en colores **ajenos**; el hook los **pisaba** con el snapshot.

**Ahora (sin reintentos):** GET fresco, luego:

| GET vigente | Acción |
|---|---|
| Coincide snapshot (colores, org, logo) | No PATCH. `patch_omitido_ya_coincide`. Éxito. |
| Parece estímulo (`primary=#FFFFFF` / tema claro si el snapshot no era 1) | Un PATCH de restore + GET de verificación. |
| Ni snapshot ni estímulo | `conflicto_concurrente`, `pendiente`, **cero PATCH**. Mocha FAIL visible. |
| Restore 401 / 412 / otro | `pendiente`, no reintento, no JWT del SPA. |

GET posterior de restore comprueba primary, secondary, org, `logo_path` (identidad) y `theme_mode` (tema). `id_usuario` **no** se aserta: el use case lo cambia al admin que escribe; queda en el GET y en el paquete (`id_usuario_original_fila` + nota).

Cypress `retries: 0`. No hay bucle de PATCH.

---

## 3. Interrupción (solo análisis estático)

| Escenario | Automático | Manual |
|---|---|---|
| Cierre durante PATCH de estímulo | `after` puede no correr. Paquete ya en disco si se superó el snapshot. | GET; restaurar **solo** si se ve el estímulo. |
| Cierre durante restore | Igual. | Mismo GET ternario. |
| Restore 401 | Hook persiste `RESTORE-PENDIENTE.json`, FAIL. | Login fresco; no reusar SPA. |
| GET final ≠ snapshot | `pendiente` + FAIL. | No segundo PATCH automático; humano. |

Una persona **puede** seguir `RECUPERACION_MANUAL.md` con seguridad **si** `snapshot_valido` es true y el GET vigente es snapshot o estímulo. Si el GET es un tercer estado, la guía manda parar.

Los hooks **no** sustituyen un kill del proceso (ya en 36).

---

## 4. Validaciones

- `node --check` spec + `cypress.config.179.rev12.cjs`: exit 0.
- Sin `npx cypress run`. Sin HTTP de escritura a TEST.
- Informe 36 conservado.

---

## 5. Condiciones para una ejecución segura

1. Autorización explícita de escritura: identidad finca 1 y, si aplica, tema del productor.
2. Ventana en la que nadie más edite esa identidad.
3. Tener a mano `RECUPERACION_MANUAL.md` y no aprobar G94 solo por Mocha del `it`.
4. Una corrida; no repetir 178-rev4 ni 179-rev11.
5. Si aparece `RESTORE-PENDIENTE.json` o Mocha FAIL en `after`, tratarlo como incidente de datos, no como “casi PASS”.

Comando (no ejecutado):

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
```

---

## 6. Veredicto

**APTA PARA SOLICITAR AUTORIZACIÓN**

El paquete de recuperación, la guarda de concurrencia (no pisar un GET que no es el estímulo), el GET de verificación y la guía manual cubren lo exigido para pedir una corrida controlada. Sigue sin estar ejecutada. G94 no se aprueba. El kill de Cypress y el cambio de `id_usuario` al admin restaurador son riesgos residuales aceptados y documentados.
