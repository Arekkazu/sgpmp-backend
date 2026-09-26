# INC-M02-73-G80 — DESTINO_IGUAL_ORIGEN respondía 400 en lugar de 422

**RF:** RF-48 — Registrar transferencia interna (CU10C)
**Endpoint:** `POST /activos-biologicos/{id_activo}/transferencias`
**TC:** TC-M02-134

## Causa raíz (confirmada por QA en el propio reporte)

`RegistrarTransferenciaUseCase.execute()`, chequeo E-06 (destino igual al
origen), lanzaba `ValidationError` (400). Las reglas equivalentes C1
(`INCOMPATIBILIDAD_ESPECIE`) y C3 (`CAPACIDAD_EXCEDIDA`) del mismo método usan
`BusinessRuleError` (422) — E-06 es la misma clase de regla (dato
estructuralmente válido, combinación inválida), no un error de formato. El
contrato OpenAPI del endpoint tampoco declara 400 como respuesta posible.

## Fix

Cambio de una línea: `ValidationError` → `BusinessRuleError` en E-06, mismo
`code` (`DESTINO_IGUAL_ORIGEN`) y mensaje. Sin cambios de esquema ni de
contrato de respuesta (422 ya estaba declarado en `responses`).

## Fuera de alcance, explícito (mismo criterio que el reporte de QA)

El propio issue señala que E-04 (`SIN_INFRAESTRUCTURA_ORIGEN`,
`INFRAESTRUCTURA_ORIGEN_INCORRECTA`) y E-05 (`INFRAESTRUCTURA_DESTINO_INVALIDA`)
usan el mismo mecanismo (`ValidationError`) y podrían tener el mismo defecto,
pero aclara que "no fueron ejecutados en G80 y no deben considerarse defectos
funcionalmente confirmados con esta evidencia". No se tocan aquí — documentado
en `curls_m02_cu10_gestionar_transferencias_historial.md` como comportamiento
actual, a la espera de que QA lo confirme en un issue propio.

## Pruebas

`tests/biological_assets/test_registrar_transferencia_e06_destino_igual_origen.py`
(nuevo): verifica que E-06 lanza `BusinessRuleError` (422), no `ValidationError`.
Suite completa `tests/biological_assets/`: 87 passed, sin regresiones.
