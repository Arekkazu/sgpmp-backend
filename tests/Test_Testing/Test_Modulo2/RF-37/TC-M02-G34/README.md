# TC-M02-G34 — Validación de fechas, secuencia y solapamiento en cambios de fase del ciclo productivo

**CU-02 · RF-37 — Gestión de Fases del Ciclo Productivo.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-040) Rechazar fecha inválida · (TC-M02-041) Rechazar transición no estándar sin confirmación · (TC-M02-043) Rechazar solapamiento de fases · (TC-M02-044) Rechazar cambio de fase en activo CERRADO/BAJA |
| Tipo | Validación |
| Herramienta | API — Postman |
| Endpoints | `POST /activos-biologicos/{id_activo}/fases` · `GET /activos-biologicos/{id_activo}/fases` |
| Responsable | Juan Manuel · Prioridad Alta |

## ✅ Resultado vigente (2026-09-26): 4/4 sub-casos PASS — 15/15 assertions

Los 4 gaps del 2026-09-19 están corregidos en TEST por cambios que llegaron con el merge de `dev`:
`15c4611e feat(m02): fase_destino/confirmacion_no_estandar, fecha no futura y RBAC (RF-37)` (TC-M02-040 y 041) y
`05b4cdec fix(rf37): 409 en vez de 500 al cambiar de fase un activo cerrado o con fechas solapadas (INC-M02-G34)`
(TC-M02-043 y 044).

Único cambio en la colección: en TC-M02-041, `fase_destino_id` pasa de `3` a `{{id_fase_destino}}=6`. El campo es
el **id de la fase dentro del ciclo** (`id_ciclos_productivo_biologico`), no el número de paso; con `3` el sistema
respondía `400 FASE_DESTINO_INVALIDA` (correcto, ese id no pertenece al ciclo 2), sin llegar a la regla que se
prueba. En TEST el ciclo 2 tiene las fases `4`, `5` y `6` (pasos 1-3), verificado en la BD de TEST (solo lectura).

| Caso | WHEN | Resultado real (2026-09-26) |
|---|---|---|
| TC-M02-040 | `fecha_inicio` futura (2027-01-01) | **400** `VAL_ENTRADA`, `fecha_inicio`: "La fecha de inicio de la fase no puede ser futura." — PASS |
| TC-M02-041 | Salto de la fase 1 a la 3 (`fase_destino_id=6`) sin `confirmacion_no_estandar` | **409** `TRANSICION_NO_ESTANDAR_SIN_CONFIRMAR` — PASS |
| TC-M02-043 | Fase con `fecha_inicio` 2020-01-01, que solapa el historial | **409** `FASE_SOLAPADA` (antes 500) — PASS |
| TC-M02-044 | Cambio de fase sobre activo `CERRADO` (cierre RF-38 → 200) | **409** `ACTIVO_NO_OPERATIVO` (antes 500) — PASS |

Activos propios creados por la corrida: 623 (040), 624 (041), 625 (043), 626 (044). Evidencia:
`RESULTADOS/TC-M02-G34_resultado.html` (Newman htmlextra, 2026-09-26).

---

## Histórico (2026-09-19): 4/4 sub-casos FAIL — pero ya por gaps reales, no por bloqueos de entorno

**INC-M02-37-01 (el crash que bloqueaba los 4 sub-casos) está resuelto**, igual que el defecto de RF-45 que
bloqueaba la precondición de TC-M02-044 (ver `NOTA_BLOQUEO.md`). Los 4 sub-casos ya llegan a probar su regla de
negocio real contra TEST — y los 4 siguen en FAIL, cada uno por una causa distinta, ya confirmada en vivo hoy:
**11/15 assertions PASS** (todo el setup/precondiciones), **4/15 FAIL** (la assertion final de cada sub-caso). Ver
`RESULTADOS/TC-M02-G34_resultado.html` para el reporte completo.

### GIVEN / WHEN / THEN

| Caso | WHEN | THEN esperado (RF) | Resultado real (2026-09-19) |
|---|---|---|---|
| TC-M02-040 | `POST /fases` con `fecha_inicio` futura (2027) | 400 "Fecha de cambio de fase inválida" | **201 — FAIL.** `CambiarFaseDTO` no valida `fecha_inicio` en absoluto |
| TC-M02-041 | `POST /fases` con `fase_destino_id` fuera de secuencia, sin confirmación | 409 "La transición requiere confirmación explícita" | **201 — FAIL.** El campo se ignora y el sistema avanza a la siguiente fase secuencial (INC-M02-37-02, mismo gap que TC-M02-G33) |
| TC-M02-043 | Crear una fase con `fecha_inicio` que solapa una fase ya cerrada | 409 "Solapamiento de fases detectado" | **500 — FAIL.** El trigger de BD (`trg_fn_fase_solapamiento`, `P0227`) sí lo detecta y lo rechaza, pero `raise_from_db_error` no traduce ese código — sale como 500 genérico |
| TC-M02-044 | `POST /fases` sobre un activo `CERRADO` | 409 "No se puede cambiar la fase de un activo inactivo" | **500 — FAIL.** Mismo patrón: el trigger (`trg_fn_fase_activo_estado_valido`, `P0228`) sí lo detecta, pero tampoco está traducido |

TC-M02-043 y TC-M02-044 comparten la misma causa raíz (falta mapear `P02xx` en `raise_from_db_error`) — ambos
deberían pasar a 409 el mismo día que se agregue ese mapeo, sin más cambios de lógica.

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuenta: `admin.test@sgpmp.com.co`. Sin acceso a base de datos — toda la verificación es vía API.
- Cada sub-caso crea su propio activo en el setup (especie 2/Trucha, ciclo productivo 2).
- Newman 6.2.2 + htmlextra 1.23.1. Fecha de ejecución: 2026-09-19.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-37/TC-M02-G34
newman run TC-M02-G34.postman_collection.json -r cli,htmlextra \
  --reporter-htmlextra-export RESULTADOS/TC-M02-G34_resultado.html \
  --suppress-exit-code
```
