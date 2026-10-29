# 12 — Rev6: precondiciones GET y plan (Cypress no ejecutado)

**HEAD:** `laura` = `ad55f049`. **G94: RECHAZADO.** Sin PATCH/POST de dominio en TEST (solo login+GET). Sin commit/push.

---

## Resultados reales de los GET (2026-10-10)

Credenciales: `SGPMP_TEST_PASSWORD` / `CONTRASENA` presentes. Valores no registrados.

### Productor `productor@pecuaria.co`

| Consulta | HTTP | Resultado |
|---|---|---|
| POST `/sesiones/` | 200 | Token presente (no documentado) |
| GET `/configuracion/interfaz/contexto` | 200 | `id_usuario=2`, `id_finca=1`, Remanso |
| Identidad en contexto | — | `primary_color=#1A6B3C`, `secondary=#A8D5B5` |
| Accesibilidad **claro** | — | ratio 6.54, `cumple_aa=true`, `color_ajustado=#1A6B3C` |
| Accesibilidad **oscuro** | — | ratio 2.69, **`cumple_aa=false`**, `color_ajustado=#249453`, fondo `#171A15`, aviso presente |
| GET `/configuracion/personalizacion/tema` | 200 | `theme_mode=2`, `fuente=personal`, `id_tema_visual=2` |

### Admin `admin@pecuaria.co`

| Consulta | HTTP | Resultado |
|---|---|---|
| GET `/configuracion/identidad-visual/1` | 200 | cuerpo **null** (diseño RLS; no se modificó) |

No se llamó `/tema/global`. No PATCH/DELETE.

Copia estructurada: `tests/.../TC-M09-G94/Resultados/G94-rev6-179-precondiciones-get.json`.

---

## Precondiciones

| Condición | Estado |
|---|---|
| Productor finca 1 con marca en contexto | **Confirmada** |
| `oscuro.cumple_aa === false` | **Confirmada** |
| `color_ajustado` ≠ `primary_color` (`#249453` ≠ `#1A6B3C`) | **Confirmada** |
| Snapshot de restore tema: `theme_mode=2` personal | **Confirmada** |
| Admin 200 null finca 1 | **Confirmada** (diseño) |
| Pendiente | UI `--brand-500` y axe **solo** tras Cypress autorizado |

Rev6 **sí** se preparó: hay estímulo AA insuficiente sin mutar identidad.

---

## Archivos nuevos (no pisan rev4/rev5)

- `tests/.../TC-M09-G94/tc_m09_g94_179_rev6_test.cy.js`
- `tests/.../TC-M09-G94/cypress.config.179.rev6.cjs` → reporter `TC-M09-G94_179_rev6_test`
- `Resultados/G94-rev6-179-precondiciones-get.json`
- `Resultados/G94-rev6-179-NO_EJECUTADO.md`
- este documento

---

## Criterios de contraste y accesibilidad

- `--brand-500` = `accesibilidad.primary_color.oscuro.color_ajustado` (runtime, no constante).
- Ratio WCAG marca vs `--surface-card` / fondo html / `#171A15` **≥ 4.5**.
- axe `color-contrast`, nodos persistidos, **`violations === 0`**.
- No se baja el umbral si el color ajustado no alcanza 4.5:1 en UI.

---

## Restauración

- Única escritura posible: `PATCH /personalizacion/tema` del **productor**.
- Hoy `theme_mode` ya es 2: el spec **no** PATCHea; `after` queda omitido.
- Si en la corrida el tema no fuera 2: PATCH a 2 y restore al snapshot con **login fresco**; GET final = snapshot; Mocha fail si restore ≠ 200.
- Sonda del Bearer capturado (diagnóstico 401) sin afirmar `TOKEN_REVOCADO` hasta ver `error_code`.
- Cero escritura de identidad o tema global.

---

## Validación local

- `node --check` spec y config: **OK**.
- Escrituras en el spec: PATCH tema personal productor **solo si** `theme_mode !== 2`; restore igual.
- GET identidad admin: solo control de diseño (200 null).
- Reporter `..._rev6_test`, carpeta `screenshots-179-rev6-test`.

---

## Comando posterior (no ejecutado)

Desde `sgpmp-backend`, con `CYPRESS_contrasena` ya en el entorno:

```
npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev6.cjs
```

Efecto si se autoriza: con el estado actual, **ningún PATCH** de tema. Riesgo residual: axe o CSS pueden **RECHAZAR** de verdad; si alguien cambia el tema del productor entre tanto, un PATCH 2 + restore podría ocurrir **solo** sobre esa preferencia personal.

---

## Autorización requerida

1. Ventana Cypress TEST (productor id=2).
2. Nadie más parcheando su tema durante la corrida.
3. Aceptar que 179 rev6 cubre variante en **oscuro** con marca real, no el escenario `#FFFFFF`/claro (ese sigue exigiendo un admin miembro de la finca).
4. 178 no se reejecuta aquí; el grupo no se aprueba solo con 179.

**No hay Mocha rev6 → G94 no APROBADO.**
