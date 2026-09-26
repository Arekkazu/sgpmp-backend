# TC-M09-G49 (TC-M09-97, 98, 99, 100) — Validación de datos al registrar área productiva

**RF-20 / CU-04 — Gestionar Infraestructura Productiva**

## Estado vigente — reevaluación 2026-09-26

**Resultado: FALLA (1 defecto real)** — 4 de 5 verificaciones pasan; TC-M09-99 falla con 500.

El bloqueo original ya no existe: la migración `2dbb6d44046f` está aplicada en TEST
(`modulo9.tipos_area` existe y el área `estanque` se crea con `201`). Se ajustó la colección a
la realidad del catálogo, sin cambiar lo que valida cada sub-caso:

- `tipo_area`: `"galpon"` → `"Galpón"`. El catálogo guarda los nombres canónicos (`Galpón`,
  `Corral`, `Potrero`, `Estanque`, `Invernadero`); la búsqueda ignora mayúsculas pero no tildes,
  así que `galpon` responde `400 TIPO_AREA_NO_RECONOCIDO`.
- TC-M09-100a: la respuesta devuelve el nombre canónico (`Estanque`), no el texto enviado.
- TC-M09-100b: se espera `400` (no `422`). El flujo alterno "Tipo de área no reconocido" de
  RF-20 lo clasifica como dato inválido (400); así lo implementa
  `registrar_infraestructura_use_case.py`. Era la expectativa de la colección la imprecisa.

| Sub-caso | Verificación | Resultado |
|---|---|---|
| TC-M09-97 | `finca_id` inexistente → `404 FINCA_NO_ENCONTRADA`; finca inactiva → `422 FINCA_INACTIVA` | ✅ PASA |
| TC-M09-98 | Superficie `0` y `-5` → `400 VAL_ENTRADA`; `0.01` → `201` con superficie `0.01` | ✅ PASA |
| TC-M09-99 | Nombre duplicado en la misma finca variando mayúsculas → se espera `409` | ❌ FALLA (500) |
| TC-M09-100 | `Estanque` → `201`; `TipoQueNoExiste` → `400 TIPO_AREA_NO_RECONOCIDO` | ✅ PASA |

**Totales Newman:** 13 requests, 21 assertions, 1 failed.

### Defecto TC-M09-99: duplicado sin distinguir mayúsculas responde 500

- Request: `POST /configuracion/infraestructuras` con `nombre_infraestructura: "GALPON DUPLICADO TEST"`
  en la misma finca donde ya existe `"Galpon Duplicado Test"`.
- Respuesta: `500 {"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos","fields":[]}`.
- Causa (verificada en la BD de TEST, solo lectura): el trigger
  `modulo9.trg_fn_infraestructura_nombre_unique_ci` sí detecta el duplicado sin distinguir
  mayúsculas (`LOWER(TRIM(nombre))` por finca) y lanza
  `RAISE EXCEPTION 'DUPLICATE_AREA: ...' USING ERRCODE = 'P0125'`, pero `P0125` no está en
  `_ERRCODES_NOMBRE_DUPLICADO` de `src/shared/db_error_translator.py` (solo `P0104`, `P0109`),
  así que cae como error interno. Como el trigger se ejecuta `BEFORE INSERT`, un duplicado con
  el mismo texto exacto sigue el mismo camino.
- La regla de negocio sí se cumple (el registro no se guarda: la transacción se revierte), lo
  que falla es la respuesta: debería ser `409` con un código de negocio de nombre duplicado.
- Esto resuelve la duda de la nota original: la unicidad real es **case-insensitive** (vía
  trigger), no case-sensitive como dice `curls_m09_cu04_infraestructura.md`.

Evidencia: `Resultados/reporte-TC-M09-G49.html` (Newman htmlextra, 2026-09-26).

---

## Resultado original (2026-09-05) — histórico

**Resultado: PARCIAL** — 2 de 4 sub-casos pasan limpio; los otros 2 quedan bloqueados por el
mismo gap de entorno de `tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G48/NOTA_BLOQUEO.md`
(migración `2dbb6d44046f` no aplicada en `sgpmp_test` → `modulo9.tipos_area` no existe).

Antes de descartar el caso completo, se revisó el orden exacto de validaciones en
`registrar_infraestructura_use_case.py`: la finca (existe/activa) y la superficie (DTO,
Pydantic) se validan **antes** de llegar al catálogo de tipos roto, así que esas dos
sub-pruebas sí son 100% verificables hoy. El nombre duplicado se valida por constraint de BD
al guardar, y el tipo de área se valida contra el catálogo mismo — ambos ocurren **después**
del punto de falla, así que quedan bloqueados.

### Resultado por sub-caso

| Sub-caso | Verificación | Resultado |
|---|---|---|
| TC-M09-97 | `finca_id` inexistente → `404 FINCA_NO_ENCONTRADA`; finca inactiva → `422 FINCA_INACTIVA` | ✅ PASA |
| TC-M09-98 | Superficie `0` y `-5` → `400 VAL_ENTRADA` (mitad de rechazo) | ✅ PASA |
| TC-M09-98 | Superficie `0.01` (positiva) → se espera `201` | ❌ BLOQUEADO (500, mismo gap) |
| TC-M09-99 | Nombre duplicado en la misma finca (variando mayúsculas) → se espera `409` | ❌ BLOQUEADO (500, mismo gap) |
| TC-M09-100 | Tipo de área válido (`estanque`) → `201`; tipo no reconocido → `422 TIPO_AREA_NO_RECONOCIDO` | ❌ BLOQUEADO (500, mismo gap) |

**Totales Newman:** 13 requests, 21 assertions, 8 failed — las 8 fallas son exactamente los
5 requests bloqueados (algunos con más de una aserción), sin ninguna falla inesperada.

### Nota sobre TC-M09-99

El dato de prueba de la planilla pide verificar duplicado "sin distinguir mayúsculas". La
documentación existente (`curls_m09_cu04_infraestructura.md`) dice lo contrario: *"La
unicidad del nombre de área es por finca y **case-sensitive** vía constraint de DB (FA-08)"*.
Esta discrepancia no se pudo verificar en ningún sentido porque el caso está bloqueado antes
de llegar a esa validación — queda pendiente confirmar cuál de las dos es la real en cuanto
se aplique la migración.

### Cómo cerrar el caso

Una vez aplicada la migración pendiente (ver `TC-M09-G48/NOTA_BLOQUEO.md`), reejecutar sin
cambios:

```bash
newman run "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G49/TC-M09-G49.postman_collection.json" \
  -r cli,htmlextra --reporter-htmlextra-export "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G49/Resultados/reporte-TC-M09-G49.html"
```
