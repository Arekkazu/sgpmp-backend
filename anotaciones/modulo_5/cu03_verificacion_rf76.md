# CU-03 (RF-76) — Verificación: registrar aplicación de medicamentos

## Fecha
2026-07-30

## Nota de numeración

El caso de uso recibido para esta sesión se identifica como **CU-03** ("Registrar aplicación
de medicamentos", RF cubiertos: RF-76, actor principal Veterinario/Administrador). En este
repositorio, RF-76 ya fue implementado el mismo día bajo la etiqueta interna **CU-01**
("Gestionar Registro de Suministros"), que agrupó RF-75 (consumo de alimentos) + RF-76
(medicamentos) en un solo caso de uso — ver `cu01_gaps_bd_rf75_rf76.md` e
`implementacion_dev_m05_rf75_rf76.md`. No existe conflicto de contenido: es el mismo RF-76,
solo con una numeración de CU distinta entre el enunciado recibido y la documentación previa
del equipo.

Este documento verifica, punto por punto, que la implementación ya existente en
`src/supplies/` cubre efectivamente cada flujo alterno (FA) y error (E) del documento de
CU-03 recibido, y dónde no.

## Alcance verificado

Componentes leídos directamente (no solo el resumen de exploración) para esta verificación:
- `src/supplies/domain/entities/medicamento.py`
- `src/supplies/domain/value_objects/via_aplicacion.py`, `justificacion_anulacion.py`
- `src/supplies/domain/repositories/medicamento_repository.py`, `estado_activo_port.py`, `activo_consulta_port.py`
- `src/supplies/infrastructure/dto/registrar_medicamento_dto.py`
- `src/supplies/infrastructure/repositories/medicamento_repository.py`
- `src/supplies/infrastructure/adapters/estado_activo_m02_adapter.py`
- `src/supplies/application/use_cases/suministros/registrar_medicamento_use_case.py`
- `src/supplies/application/use_cases/suministros/anular_medicamento_use_case.py`
- `src/supplies/infrastructure/routers/medicamento_router.py`
- `src/shared/base_dto.py`, `src/shared/error_handlers.py`, `src/shared/rbac.py`
- Esquema real de `modulo5.registros_medicamentos` (triggers, constraints, índices, enum) vía MCP postgres.

## Trazabilidad — Flujos alternos (FA)

| FA | Descripción | Cubierto | Mecanismo / archivo |
|----|-------------|----------|----------------------|
| FA-01 | Campos obligatorios incompletos | ✅ | `RegistrarMedicamentoDTO` (Pydantic, todos los campos `Field(...)` requeridos) → `RequestValidationError` → handler global `error_handlers.py:57-76` → **400** |
| FA-02 | Activo inválido/inactivo | ✅ | `registrar_medicamento_use_case.py:68-85` — `NotFoundError` 404 si no existe; `BusinessRuleError` 422 (`ACTIVO_ESTADO_INVALIDO`) si `id_estado` ∉ {ACTIVO, EN_TRATAMIENTO} |
| FA-03 | Fecha aplicación < fecha_inicio del activo | ✅ | `:108-116` — `ValidationError` 400 (`FECHA_ANTERIOR_A_CICLO`) |
| FA-04 | Vía de administración inválida | ✅ | `via_aplicacion.py:38-49` (VO `ViaAplicacion`) — `ValidationError` 400 (`VIA_ADMINISTRACION_INVALIDA`), valida las 6 vías del RF |
| FA-05 | Motivo < 10 caracteres | ✅ | DTO `Field(min_length=10)` + `field_validator` propio (`registrar_medicamento_dto.py:29,36-43`) → 400 |
| FA-06 | Evento sanitario inválido o de otro activo | ✅ | `:120-130` — `BusinessRuleError` 422 (`EVENTO_SANITARIO_INVALIDO`), consulta vía `EventoSanitarioM02Adapter` (join `eventos_sanitarios`↔`eventos_activos`) — mismo caso que E12 |
| FA-07 | Registro duplicado VALIDADO | ✅ | Pre-check en el use case (`:152-165`, `ConflictError` 409 `MEDICAMENTO_DUPLICADO`) + backstop real: índice único parcial `uq_medicamento_validado_dup` en BD (WHERE `estado_registro='VALIDADO'`) — mismo caso que E13 |
| FA-08 | POBLACIONAL con `cantidad_actual` nula/inválida | ✅ | `:132-146` — `BusinessRuleError` 422 (`POBLACIONAL_SIN_CANTIDAD`) |
| FA-09 | Fallo técnico calculando `fecha_fin_retiro` | ⚠️ Parcial | El cálculo es aritmética de fecha pura (`fecha_aplicacion + timedelta(...)`), no tiene un modo de fallo realista bajo operación normal; no hay manejo dedicado. Se considera cubierto implícitamente (no hay código que pueda lanzar aquí) más que explícitamente auditado. No se tocó — no amerita código adicional. |
| FA-10 | Falla RF-44 tras persistir el medicamento — tratamiento queda persistido, incidente en auditoría | ⚠️ Contradice a E10 | Ver sección **"FA-10 vs E10"** más abajo. La implementación sigue E10 (rollback atómico), no FA-10. |
| FA-11 | Intento de editar un registro VALIDADO | ✅ | No existe endpoint de edición (solo `POST` registrar / `POST .../anulacion` / `GET` consultar). Backstop en BD: trigger `fn_trg_medicamento_inmutable_validado` (BEFORE UPDATE) bloquea cambios fuera de estado+campos de anulación. |
| FA-12 | Intento de reactivar un ANULADO | ✅ | No existe endpoint de reactivación; estructuralmente imposible. `AnularMedicamentoUseCase` además rechaza anular un ya-ANULADO (E8, `ConflictError` 409). |
| FA-13 | Error de persistencia | ✅ | `SqlAlchemyMedicamentoRepository.guardar()` captura excepciones con `raise_from_db_error` (`medicamento_repository.py:117-123`); el use case hace `rollback()` y re-lanza (`:193-206`) |
| FA-14 | Permisos insuficientes | ✅ (parcial en auditoría) | RBAC `require_permission(48, 1/2/4)` en el router (`medicamento_router.py:53,98,125`) → `AuthorizationError` 403. El registro del intento como "evento de seguridad" depende del middleware global de auditoría (`AuditContextMiddleware`), no de código propio de M05 — mismo comportamiento que el resto de la aplicación, no es un gap de este CU. |
| FA-15 | Concurrencia — recálculo del retiro vigente | ✅ | `max_fecha_fin_retiro_vigente()` (`medicamento_repository.py:142-151`) — `MAX(fecha_fin_retiro)` sobre VALIDADOs, leído tras cada `commit()` independiente (`registrar_medicamento_use_case.py:208`). Idempotente por diseño: el resultado no depende del orden de escritura, sin necesidad de locking explícito. |
| FA-16 | Dosis subsecuente (mismo medicamento, fecha/hora posterior) | ✅ | El chequeo de duplicado exige coincidencia **exacta** de fecha+hora (`existe_duplicado_validado`); una fecha/hora posterior no colisiona → se persiste como registro independiente con su propia `fecha_fin_retiro` |

## Trazabilidad — Errores (E1-E13)

| Error | HTTP esperado | Cubierto | Mecanismo / archivo |
|-------|---------------|----------|----------------------|
| E1 | 422 | ✅ | Igual que FA-02 (`ACTIVO_ESTADO_INVALIDO`) |
| E2 | 400 | ✅ | `:99-107` — `ValidationError` (`FECHA_FUTURA`) |
| E3 | 400 | ✅ | Igual que FA-03 (`FECHA_ANTERIOR_A_CICLO`) |
| E4 | 400 | ✅ | DTO `Field(gt=0)` en `dosis_aplicada` → `RequestValidationError` → handler global → 400 |
| E6 | 400 | ✅ | Igual que FA-05 |
| E7 | 422 | ✅ | `:87-96` — `BusinessRuleError` (`CICLO_NO_ABIERTO`) |
| E8 | 409 | ✅ | `anular_medicamento_use_case.py:39-46` — `ConflictError` (`MEDICAMENTO_YA_ANULADO`) |
| E9 | 400 | ✅ | `justificacion_anulacion.py:23-33` — VO `JustificacionAnulacion`, mínimo 20 caracteres, `ValidationError` (`JUSTIFICACION_INSUFICIENTE`) |
| E10 | 500 + rollback completo | ✅ | El use case envuelve `guardar()` + `estado_port.marcar_en_tratamiento()` + `commit()` en un único `try/except` con `rollback()` (`:193-206`) — si falla la invocación a RF-44, **toda** la operación (incluido el medicamento ya "persistido" en la sesión) se revierte. Ver nota FA-10 vs E10. |
| E11 | 200, sin bloquear | ✅ | Estado `EN_TRATAMIENTO` está en `_ESTADOS_PERMITIDOS` (`:35`); `EstadoActivoM02Adapter.marcar_en_tratamiento` es idempotente (`estado_activo_m02_adapter.py:38-45`, no-op si ya está en tratamiento); `fecha_fin_retiro_vigente` recalculado con MAX tras cada registro |
| E12 | 422 | ✅ | Igual que FA-06 (`EVENTO_SANITARIO_INVALIDO`) |
| E13 | 409 | ✅ | Igual que FA-07 (`MEDICAMENTO_DUPLICADO`) |

## FA-10 vs E10 — contradicción en el documento de CU-03, resuelta a favor de E10

El propio documento de CU-03 se contradice:
- **FA-10** dice que si falla la invocación a RF-44, "el tratamiento queda persistido, pero
  el incidente se registra en auditoría como pendiente de sincronización del estado".
- **E10** dice lo opuesto: "el sistema ha revertido la operación completa" (HTTP 500).

La implementación existente sigue **E10** (rollback atómico completo vía `try/except` +
`self.db.rollback()` en `registrar_medicamento_use_case.py:193-206`), lo cual además es
obligatorio por el propio RF-76 en su sección de Requerimientos No Funcionales — Fiabilidad:
> "El proceso de registro y actualización del estado del activo se ejecutan en una
> transacción atómica."

Dejar el medicamento persistido con el activo desincronizado (como pide FA-10) violaría esa
atomicidad. Se documenta la decisión aquí; **no se modifica código** por este punto.

## Desviaciones menores conocidas (no bloqueantes)

| # | Desviación | Detalle |
|---|-----------|---------|
| 1 | Campo `observaciones` del RF no se persiste | `modulo5.registros_medicamentos` no tiene columna `observaciones` (ver Gap 4, `cu01_gaps_bd_rf75_rf76.md`). El DTO ni siquiera expone el campo. Si el frontend lo envía, Pydantic lo ignora (no hay `extra="forbid"` en `BaseDTO`). |
| 2 | `nombre_medicamento` es varchar(100) en BD/DTO vs varchar(50) del RF | Más permisivo que el RF, sin impacto funcional. |
| 3 | Campo `tipo_evento_sanitario` del RF se llama `id_evento_sanitario` en el DTO | Incompatibilidad de nombre, no de semántica — mismo significado (RF-41). |

## Pendientes reales (cerrados en esta misma sesión)

Dos piezas del proceso completo de RF-76 estaban explícitamente fuera de alcance de la
implementación previa (sección "Qué NO se hizo" de `implementacion_dev_m05_rf75_rf76.md`):

1. **Paso 9** — notificación al Veterinario/Productor sobre inicio de período de retiro.
2. **Pasos 11-13** — scheduler diario que revierte el activo a `ACTIVO` cuando vence el
   período de retiro vigente, con notificación de cierre.

Ambas se implementan en esta sesión — ver `implementacion_dev_m05_rf76_cierre.md`.

## Conclusión

El núcleo transaccional de CU-03/RF-76 (registrar, anular, consultar aplicaciones de
medicamento, con todas sus validaciones, RF-44, RF-41, RF-37/38, RF-33, concurrencia y
duplicados) **ya estaba correctamente implementado y verificado end-to-end** antes de esta
sesión. No se requirió escribir código nuevo para cerrar ningún FA/E de la tabla anterior. El
trabajo de esta sesión se limitó a cerrar los dos pendientes explícitos (notificaciones +
scheduler de reversión) — ver documento de cierre.
