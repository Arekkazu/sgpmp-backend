# TC-M09-G49 (TC-M09-97, 98, 99, 100) — Validación de datos al registrar área productiva

**RF-20 / CU-04 — Gestionar Infraestructura Productiva**
**Resultado: PARCIAL** — 2 de 4 sub-casos pasan limpio; los otros 2 quedan bloqueados por el
mismo gap de entorno de `tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G48/NOTA_BLOQUEO.md`
(migración `2dbb6d44046f` no aplicada en `sgpmp_test` → `modulo9.tipos_area` no existe).

Antes de descartar el caso completo, se revisó el orden exacto de validaciones en
`registrar_infraestructura_use_case.py`: la finca (existe/activa) y la superficie (DTO,
Pydantic) se validan **antes** de llegar al catálogo de tipos roto, así que esas dos
sub-pruebas sí son 100% verificables hoy. El nombre duplicado se valida por constraint de BD
al guardar, y el tipo de área se valida contra el catálogo mismo — ambos ocurren **después**
del punto de falla, así que quedan bloqueados.

## Resultado por sub-caso

| Sub-caso | Verificación | Resultado |
|---|---|---|
| TC-M09-97 | `finca_id` inexistente → `404 FINCA_NO_ENCONTRADA`; finca inactiva → `422 FINCA_INACTIVA` | ✅ PASA |
| TC-M09-98 | Superficie `0` y `-5` → `400 VAL_ENTRADA` (mitad de rechazo) | ✅ PASA |
| TC-M09-98 | Superficie `0.01` (positiva) → se espera `201` | ❌ BLOQUEADO (500, mismo gap) |
| TC-M09-99 | Nombre duplicado en la misma finca (variando mayúsculas) → se espera `409` | ❌ BLOQUEADO (500, mismo gap) |
| TC-M09-100 | Tipo de área válido (`estanque`) → `201`; tipo no reconocido → `422 TIPO_AREA_NO_RECONOCIDO` | ❌ BLOQUEADO (500, mismo gap) |

**Totales Newman:** 13 requests, 21 assertions, 8 failed — las 8 fallas son exactamente los
5 requests bloqueados (algunos con más de una aserción), sin ninguna falla inesperada.

## Nota sobre TC-M09-99

El dato de prueba de la planilla pide verificar duplicado "sin distinguir mayúsculas". La
documentación existente (`curls_m09_cu04_infraestructura.md`) dice lo contrario: *"La
unicidad del nombre de área es por finca y **case-sensitive** vía constraint de DB (FA-08)"*.
Esta discrepancia no se pudo verificar en ningún sentido porque el caso está bloqueado antes
de llegar a esa validación — queda pendiente confirmar cuál de las dos es la real en cuanto
se aplique la migración.

## Cómo cerrar el caso

Una vez aplicada la migración pendiente (ver `TC-M09-G48/NOTA_BLOQUEO.md`), reejecutar sin
cambios:

```bash
newman run "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G49/TC-M09-G49.postman_collection.json" \
  -r cli,htmlextra --reporter-htmlextra-export "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G49/Resultados/reporte-TC-M09-G49.html"
```
