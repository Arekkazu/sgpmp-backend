# INC-M02-G22 — V3 RF-35: dos fallas en el PATCH del activo individual

**RF:** RF-35 — Gestión individual de activos biológicos (CU02)
**Endpoint:** `PATCH /activos-biologicos/{id_activo}`
**Issue:** #427

## Qué reportó QA

1. `estado_activo` enviado junto a un campo válido (ej. `raza`) respondía
   `200` e ignoraba el cambio de estado sin avisar. Se esperaba `400`.
2. Con el activo en `EN_TRATAMIENTO` (proceso sanitario abierto) la edición
   no se bloqueaba. Se esperaba `409`.

## Análisis

**Falla 1.** `ActualizarActivoIndividualDTO` usaba la configuración por
defecto de Pydantic (`extra='ignore'`): cualquier campo que no estuviera
declarado se descartaba antes de llegar al caso de uso. RF-35 en sus
Restricciones dice *"El estado del activo no puede ser modificado
directamente en este requerimiento. Todo cambio de estado debe realizarse
exclusivamente a través de RF-44"*, y en sus criterios de aceptación *"El
sistema impide cambios no permitidos (tipo, especie)"*. Impedir no es
descartar en silencio. El mismo hueco afectaba a `especie_id`, `tipo` o
cualquier otro campo no editable.

**Falla 2.** El bloqueo no existía cuando QA ejecutó la V3: lo agregó
`e84c0ac2` (tarea Taiga "RF-35: RBAC Veterinario, validar eventos
pendientes, concurrencia optimista"), mergeado a dev el mismo 2026-09-23,
pero respondía `422 BusinessRuleError`. QA espera `409`, y es consistente
con `ESTADO_NO_PERMITE_EVENTOS` en el mismo `_event_validations.py`: la
petición es válida, lo que impide aplicarla es el estado actual del recurso.

## Fix

| Archivo | Cambio |
|---|---|
| `infrastructure/dto/actualizar_activo_individual_dto.py` | `extra='forbid'`. `estado_activo` se declara solo para rechazarlo con un mensaje propio que remite a RF-44 (con `extra='forbid'` a secas saldría el genérico). Si el campo viene, aunque sea `null`, se rechaza. |
| `src/shared/error_handlers.py` | Mensaje en español para `extra_forbidden` (*"Este campo no está permitido en esta solicitud."*). Antes salía el texto de Pydantic en inglés. También aplica a `perfil_dto.py`, que ya usaba `extra='forbid'`. |
| `application/use_cases/gestion/_event_validations.py` | `validar_sin_eventos_pendientes` lanza `ConflictError` (409) en vez de `BusinessRuleError` (422). Mismo `code` y mismo mensaje. |
| `infrastructure/routers/activo_biologico_router.py` | `409` agregado a `responses` del PATCH. |

`HISTORIAL_INCONSISTENTE` se queda en `422`: el issue no lo menciona y es
otra condición.

**Impacto en frontend:** ninguno en el flujo normal. `EditarActivoModal.tsx`
solo envía `raza`, `sexo`, `fecha_nacimiento` y `peso_inicial`. El único
cambio visible es `422 → 409` en `EVENTO_PENDIENTE_SIN_CERRAR`, y el modal ya
muestra `saveError.message` para cualquier status < 500.

## Alembic: dos heads en dev

Al mergear #387 (`6d8b88392ac8`) después de #445 (`1b9536d4411c`), dev quedó
con dos heads y el deploy de migraciones a DEV cortó en *"Verificar que existe
una única head"*. Se corrige en esta misma rama:

- `3cb8965cdc6d`: merge vacío de las dos heads.
- `6d8b88392ac8` se edita en el mismo archivo, porque no llegó a aplicarse en
  DEV ni en TEST (el deploy cortó antes del `upgrade`):
  - `NOT VALID`: la bitácora ya tiene filas `POBLACIONAL` +
    `ACTIVO_INDIVIDUAL_CONSULTA` anteriores a `9c05d30d`
    (INC-M02-34-G29/G31 v2). En la BD local hay 2, y el `ADD CONSTRAINT`
    validado falla con `check_violation`, reproducido en un bloque que
    termina revertido. Sin `NOT VALID`, el deploy volvería a fallar después
    del merge. La bitácora es historial y no se reescribe: la regla aplica a
    las filas nuevas.
  - `chk_coherencia_auditoria_eventos` → `ck_coherencia_auditoria_evento`
    (prefijo `ck_`, singular; `convencion_nomenclatura_bd.md`).

## Verificación

- `tests/biological_assets/test_rf35_rbac_vet_eventos_concurrencia.py`:
  422 → 409 en los dos tests de evento pendiente, y 6 casos nuevos del DTO
  (`estado_activo` con/sin otro campo y en `null`; `especie_id`, `tipo`,
  `id_estado`). Los 10 casos nuevos o ajustados fallan contra el código de
  dev y pasan con el fix.
- Petición HTTP por `TestClient` con el router real y repos falsos:
  `raza+estado_activo` → 400, solo `estado_activo` → 400,
  `raza+especie_id` → 400, `EN_TRATAMIENTO` → 409, `AISLADO` → 409.
- `alembic heads` → una sola head (`3cb8965cdc6d`).
