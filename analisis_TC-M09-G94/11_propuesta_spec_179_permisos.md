# 11 — Propuesta de spec TC-M09-179 respetando RLS (decisión de diseño)

**G94 permanece RECHAZADO.** Esta es una propuesta; no se ejecutó TEST, no se alteró rev4/rev5, no hay commit/push.  
Alex: la restricción de que el administrador solo vea identidad de **sus** fincas es **intencional**. No se trata como bug ni se pide ampliar RLS/RBAC.

---

## 1. Permisos reales (quién puede qué)

| Recurso | Actor | Operación permitida | Operación prohibida / inútil para G94 |
|---|---|---|---|
| `GET /interfaz/contexto` (22) | **Productor** (y otros roles con R) | Leer finca activa, `identidad_visual` y `accesibilidad` (claro **y** oscuro) | No escribe identidad |
| `GET/PATCH /identidad-visual/{id}` (23) | **Administrador** y solo fincas de `fn_fincas_del_usuario` | GET objeto o **200 null**; PATCH si hay fila **visible** | `admin@pecuaria.co` + finca **1** → 200 null es **esperado**. Productor → 403 |
| `GET/PATCH /personalizacion/tema` (24) | El usuario autenticado, **su** preferencia | Productor lee/escribe **su** `theme_mode` | Admin PATCH **no** cambia el tema del productor |
| `GET/PATCH /personalizacion/tema/global` (27) | Administrador | Tema global compartido | **No usar** en G94: altera TEST para todos |

Tema de 179: **solo productor**, fuente `personal`.  
Identidad institucional de Remanso (finca 1): el productor la **consulta** en contexto; el admin de prueba **no** la consulta ni la parchea.

El spec rev4/rev5 hacía PATCH identidad finca 1 con `admin@pecuaria.co`. Eso **contradice** el diseño actual, no un fallo transitorio.

---

## 2. Cómo preparar 179 sin tocar identidad (vía recomendada)

El flujo alterno de RF-27 no exige `#FFFFFF`. Exige: color institucional **insuficiente en el tema activo** → variante `color_ajustado`.

Datos ya observados en TEST (rev5, contexto productor, `#1A6B3C`):

- `primary_color.claro.cumple_aa = true` (no hay variante en claro).
- `primary_color.oscuro.cumple_aa = false` y `color_ajustado` informado (p. ej. `#249453`) + aviso RF-27.

Eso es exactamente “contraste insuficiente” en **oscuro**, sin PATCH RF-26.

### Actores

| Paso | Actor | Acción |
|---|---|---|
| Login UI | Productor `productor@pecuaria.co` | Sesión de la finca 1 |
| Snapshot tema | Productor | `GET /personalizacion/tema` → guardar `theme_mode` y `fuente` |
| Snapshot marca | Productor | `GET /interfaz/contexto`: `id_finca=1`, `primary_color`, bloque `accesibilidad.primary_color.oscuro` |
| Precondición 179 | Productor | `oscuro.cumple_aa === false` y `color_ajustado` ≠ `primary_color`. Si no se cumple, **BLOQUEADO** (no inventar color) |
| Provocar tema activo insuficiente | Productor | Si `theme_mode` ≠ 2: `PATCH /personalizacion/tema` `{ theme_mode: 2 }` (solo personal). Si ya es 2, no PATCH |
| UI | Productor | Dashboard: `data-theme=dark`; `--brand-500` = `oscuro.color_ajustado` (no el crudo) |
| Contraste | Productor / axe | Ratio marca vs superficie oscura ≥ 4.5; axe `color-contrast` con nodos; `violations === 0` |
| Restore tema | Productor, **login fresco** | Si se hizo PATCH tema: `PATCH` al `theme_mode` del snapshot; GET confirma. Si no hubo PATCH, restore omitido |
| Identidad | Nadie | **Cero** GET/PATCH/POST `/identidad-visual` |
| Tema global | Nadie | No tocar |

### Restauración y residuos

- Identidad Remanso **no se muta** → no hay dato residual de marca.
- Tema: solo la fila personal del productor; restore con POST `/sesiones/` nuevo (no reutilizar Bearer tras `cy.visit`).
- Admin 200 null en finca 1: **no asertar objeto**; opcional asertar 200+null como **control de diseño**, sin usarlo de snapshot.

### Qué deja de hacer el spec

- No snapshot ni PATCH identidad con admin.
- No forzar `#FFFFFF` / `#757575` (eso exigiría un admin **asignado** a esa finca).
- No `PATCH .../tema/global`.
- No POST identidad (G85; no hay DELETE).

El criterio de 179 se mantiene: **variante automática cuando el contraste del tema activo es insuficiente**, medido en UI. Cambia el **estímulo** (tema oscuro + marca real) no el umbral 4.5:1.

---

## 3. Vía alternativa (solo si el caso obliga a `#FFFFFF` en claro)

Hace falta un **Administrador que pertenezca a la misma finca que el productor** (membresía `usuarios_fincas`, no un cambio de política).

1. Lectura previa: con ese admin, `GET /identidad-visual/{id}` **no** null y `version` presente.
2. Ese admin: snapshot + PATCH color bajo + restore identidad.
3. El **productor de esa finca**: tema claro, UI, axe, restore tema personal.

Si en TEST no existe ese par admin–finca–productor, **no crear** asignaciones ni identidades. 179 queda BLOQUEADO para el escenario blanco/claro. La vía de la sección 2 sigue siendo la ejecutable.

`admin@pecuaria.co` + finca 1 **no** es ese par.

---

## 4. 178 y grupo

178 (axe dashboard) no escribe identidad. Puede reutilizarse rev2 como muestra limitada o reejecutarse como productor en el tema que 179 deje restaurado. **No** aprueba G94 solo.

---

## 5. Verificaciones **antes** de autorizar Cypress (solo lectura)

No ejecutar el spec hasta esta lista. Preferir GET; ningún PATCH.

1. Login productor → `GET /interfaz/contexto`: `id_finca`, `primary_color`, `accesibilidad.primary_color.claro|oscuro` (`cumple_aa`, `color_ajustado`, aviso).
2. Mismo productor → `GET /personalizacion/tema`: `theme_mode`, `fuente` (esperable `personal` / 2 en rev5).
3. Login `admin@pecuaria.co` → `GET /identidad-visual/{id_finca_del_productor}`: documentar 200 null como **diseño**, no como defecto.
4. Confirmar que **no** se usará `/tema/global`.
5. Si `oscuro.cumple_aa` no es false: no hay 179 sin mutar identidad → BLOQUEADO o vía 3.
6. Ventana: un solo escritor del **tema personal del productor**; nadie más parchea identidad Remanso.

Tras autorización: spec **nuevo** `rev6` (no reescribir rev4/rev5), evidencias `G94-rev6-*`, Mocha `TC-M09-G94_179_rev6_test`. Veredicto = `stats.failures`. Acta no anula Mocha.

---

## 6. Cambios concretos a implementar en rev6 (cuando se autorice el código)

Archivos nuevos, no tocar `tc_m09_g94_179_rev5_test.cy.js` ni reportes rev5.

- Un solo actor de mutación: productor.
- Token de restore: relogin productor en `after`, no JWT del login UI.
- Snapshot y aserciones de marca desde **contexto**, bloque `oscuro` si `data-theme=dark`.
- `AJUSTADO` leído de la API en runtime, no constante `#757575`.
- Flags `patchedTema`; `patchedId` siempre false.
- Sonda 401 del Bearer viejo **sí** (diagnóstico del arnés), sin afirmar `TOKEN_REVOCADO` hasta ver `error_code`.
- Axe nodos + ratio WCAG vs `--surface-card` / fondo oscuro real.

---

## 7. Conclusión

El spec actual **no** se puede ejecutar tal cual sin violar el diseño (admin + finca 1) o sin POST residual. **Sí** se puede adaptar 179: el productor consulta la marca en contexto, mueve **solo su tema** al modo donde ya hay incumplimiento AA, comprueba la variante en CSS/axe y restaura su tema. Identidad intocable. Seguridad y RLS intactas.

G94 no se marca APROBADO hasta Mocha rev6 (y 178 en el alcance acordado) en una ejecución autorizada.
