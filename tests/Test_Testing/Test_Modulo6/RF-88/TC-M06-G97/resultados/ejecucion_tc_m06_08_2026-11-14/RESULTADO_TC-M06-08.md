# Resultado TC-M06-08

**Caso:** TC-M06-G97 / TC-M06-08 — Obligatoriedad de vida útil (RF-88)  
**Fecha ejecución (UTC):** 2026-11-15T03:46:26.222161+00:00  
**Commit:** `3995b923` · rama `laura`  
**Ambiente:** `https://api.inmero.co/api-sgpmp-test`  
**Resultado:** **APROBADO**

## Autorización

- Origen: Usuario QA en chat Cursor
- Alcance: POST /finanzas/reconocimientos/2553 unicamente en TEST para TC-M06-08
- Limitación: solo activo 2553; sin otras escrituras.

## Solicitud

| Campo | Valor |
|---|---|
| Método | POST |
| URL | `https://api.inmero.co/api-sgpmp-test/finanzas/reconocimientos/2553` |
| Body | `{}` |
| Headers | `Accept`, `Content-Type`, `X-Zona-Horaria`, `Authorization: Bearer ***` |
| HTTP | **422** |
| error_code | `VIDA_UTIL_NO_CONFIGURADA` |

## Fixture

| Campo | Valor |
|---|---|
| Activo | 2553 / QA-M06-G97-SIN-VIDA |
| Especie | 718 / Caprino Sin Vida Util Qa |
| Clasificación | PRODUCCION |
| Vida útil | vacía |
| Costo | 900000 |

## Side-effects

| Campo | Antes | Después |
|---|---|---|
| reconocimientos | 0 | 0 |
| valoracion_costo | None | None |
| lineas | 0 | 0 |
| periodos NIT | 0 | 0 |

## Aserciones

Ver `ASERCIONES_TC-M06-08.md` — 11 PASS / 0 FAIL.

## Estado G97

| Escenario | Estado |
|---|---|
| TC-M06-08 | **APROBADO** |
| TC-M06-09 | **APROBADO** (previo) |
| G97 | **APROBADO** |
