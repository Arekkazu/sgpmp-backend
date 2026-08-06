# Cierre de RF-76 — Notificaciones (paso 9) y scheduler de reversión (pasos 11-13)

> **Fecha:** 2026-07-30/31
> **Módulo:** 5 (Gestión de Suministros) · `src/supplies`
> **Alcance:** Los dos pendientes que quedaron explícitamente fuera de `implementacion_dev_m05_rf75_rf76.md`
> ("Qué NO se hizo"): notificación de inicio de retiro y scheduler diario de
> reversión a `ACTIVO`. Ver también `cu03_verificacion_rf76.md` (verificación
> del resto de RF-76, ya implementado previamente).

## Resumen

| # | Entregable | Qué se hizo |
|---|-----------|-------------|
| 1 | Notificación inicio de retiro (paso 9) | Puerto `NotificacionMedicamentoPort` + adapter `NotificacionMedicamentoEmailAdapter`, invocado desde `RegistrarMedicamentoUseCase` tras el `commit()` |
| 2 | Scheduler de reversión (pasos 11-13) | Nuevo use case `RevertirRetirosVencidosUseCase` + extensión de 3 puertos existentes + tarea diaria en `main.py` |
| 3 | Notificación fin de retiro (paso 13) | Mismo puerto/adapter, invocado desde el scheduler tras revertir |

No se tocó esquema de BD ni RBAC: se reutilizan las tablas y el recurso 48 ya existentes.

## Diseño

### Notificaciones (`NotificacionMedicamentoPort` / `NotificacionMedicamentoEmailAdapter`)

- Puerto en `domain/repositories/notificacion_medicamento_port.py`: dos métodos,
  `notificar_inicio_retiro` y `notificar_fin_retiro`.
- Adapter en `infrastructure/adapters/notificacion_medicamento_email_adapter.py`: resuelve
  destinatarios con SQL directo (mismo patrón que `evento_sanitario_m02_adapter.py`, no hay
  modelo ORM de `usuarios` en este módulo):
  - **Productor** = dueño registrado del activo (`modulo2.activos_biologicos.id_usuario`,
    siempre presente).
  - **Veterinario** = `registros_medicamentos.id_usuario_veterinario` (opcional: solo se
    conoce cuando quien registró tenía rol Veterinario; `nombre_veterinario` es texto libre,
    no necesariamente una cuenta del sistema).
- Templates en `infrastructure/email_templates.py` (mismo patrón que
  `identity_access/infrastructure/email_templates.py`).
- **Decisión de diseño — envío *best-effort***: cada `send_email` va en su propio
  `try/except` con `logger.warning`, nunca propaga. Motivo: cuando se notifica, el dato de
  negocio (medicamento registrado, o activo revertido) ya quedó persistido con `commit()`; un
  fallo de SMTP no debe convertir una operación exitosa en un error para el cliente ni en una
  excepción no controlada del scheduler. Se evaluó reusar `NotificacionService`
  (`src/shared/notificacion_service.py`), pero está acoplado al modelo de `tipo_eventos` de
  `identity_access` (altas de cuenta, recuperación de contraseña); usarlo aquí habría exigido
  nuevas filas de `tipo_eventos` y una dependencia cruzada innecesaria — se replicó solo su
  filosofía de "nunca propaga", no su implementación.
- `RegistrarMedicamentoUseCase` gana una dependencia `notificacion_port`; se invoca
  **después** del `commit()` (regla de CLAUDE.md), solo si `fecha_fin_retiro is not None`.

### Scheduler de reversión (`RevertirRetirosVencidosUseCase`)

Extensiones a puertos existentes (compatibles hacia atrás, solo se agregan métodos):
- `ActivoConsultaPort.listar_en_tratamiento() -> list[int]` — SQL directo sobre
  `modulo2.activos_biologicos WHERE id_estado = 3`.
- `EstadoActivoPort.revertir_a_activo(id_activo, id_usuario, motivo)` — espejo exacto de
  `marcar_en_tratamiento` ya existente: misma entidad de dominio (`cambiar_estado`), mismo
  `SqlAlchemyHistoricoEstadoRepository`, mismo `flush` sin `commit`, idempotente si ya está
  `ACTIVO`. Confirmado que `EN_TRATAMIENTO → ACTIVO` es una transición válida en
  `TRANSICIONES_VALIDAS` (`biological_assets/domain/value_objects/estado_activo.py`).
- `MedicamentoRepository.obtener_tratamiento_vigente(id_activo) -> Optional[Medicamento]` —
  el VALIDADO con `fecha_fin_retiro` más lejana; a diferencia de
  `max_fecha_fin_retiro_vigente` (que solo da la fecha), devuelve la entidad completa porque
  el scheduler necesita su `id_usuario`.

**Decisión de diseño — actor de auditoría de la reversión automática**: el proyecto no tiene
convención de "usuario del sistema" para acciones automáticas (se buscó explícitamente y no
existe). `historicos_estados_activos.id_usuario` es `NOT NULL` con FK a `usuarios`. Se usa el
`id_usuario` que registró el tratamiento cuyo retiro se está venciendo — es el actor que
generó la obligación que ahora se levanta, y siempre existe (es el mismo que persistió el
registro VALIDADO). Si un activo queda `EN_TRATAMIENTO` sin ningún tratamiento VALIDADO con
`fecha_fin_retiro` referenciable (estado inconsistente fuera del flujo normal de RF-76), el
activo se omite con `logger.warning` y se deja para revisión manual — caso borde fuera de
alcance de RF-76.

`RevertirRetirosVencidosUseCase.ejecutar()`:
1. Lista activos `EN_TRATAMIENTO` (una sesión de solo lectura).
2. Por cada uno, abre **su propia sesión/transacción** — mismo patrón de aislamiento que
   `EjecutarBatchICAUseCase._procesar_activo` (RF-74): el fallo de un activo no afecta a los
   demás.
3. Si `obtener_tratamiento_vigente(id_activo)` es `None` o su `fecha_fin_retiro > hoy` → no
   se toca (aún hay retiro activo, o no hay base para decidir).
4. Si venció → `revertir_a_activo(...)` + `commit()`; luego notifica (`notificar_fin_retiro`)
   en una sesión aparte, fuera de esa transacción, best-effort.

**Decisión de diseño — hora fija sin tabla de configuración**: a diferencia de RF-74 (que
tiene panel de administración y `configuracion_batch_ica`), RF-76 no pide disparo manual ni
configuración de hora — solo "el scheduler diario". Se hardcodea `03:00` (server time) en
`_revertir_retiros_vencidos_diariamente()` (`main.py`), con el mismo patrón de espera
calculada que `_ejecutar_batch_ica_diario` (evita depender de una tabla nueva sin
justificación en el RF).

## Cómo se verificó (contra la BD dev, usando las clases reales sin pasar por HTTP/JWT)

Se instanciaron `RegistrarMedicamentoUseCase`, `AnularMedicamentoUseCase` y
`RevertirRetirosVencidosUseCase` directamente (mismo wiring que los routers), con un
`UsuarioActual` sintético (rol Veterinario, `id_usuario=3`, el mismo veterinario de los datos
de prueba de CU-01). Activo de prueba: **5**, el único con ciclo productivo abierto y estado
compatible con RF-76 en los datos semilla de dev.

1. Estado inicial: activo 5 `EN_TRATAMIENTO` (id_estado=3), con el tratamiento VALIDADO
   id 15 (Enrofloxacina) vigente hasta `2026-08-08`.
2. Se registró un nuevo medicamento (id 18, "TestRetiroVencidoRF76") con
   `fecha_aplicacion=2026-07-01`, `periodo_retiro_dias=1` → `fecha_fin_retiro=2026-07-02`
   (ya vencido). La notificación de inicio de retiro se invocó sin lanzar excepción
   (best-effort).
3. Se corrió el scheduler: **no revirtió** (0 activos) — correcto, porque el `MAX` seguía
   siendo `2026-08-08` (tratamiento id 15 aún VALIDADO). Confirma RF-76 Restricción 11: el
   estado se mantiene hasta que **todos** los tratamientos activos vencen.
4. Se anuló el tratamiento id 15 (justificación ≥20 caracteres) vía
   `AnularMedicamentoUseCase` real.
5. Se corrió el scheduler de nuevo: **revirtió 1 activo**. Verificado en BD:
   - `modulo2.activos_biologicos.id_estado` de 5 pasó a `1` (ACTIVO).
   - Nuevo registro en `modulo2.historicos_estados_activos` (id 80):
     `id_estado_anterior=3, id_estado_nuevo=1, motivo_cambio='Vencimiento de período de
     retiro (RF-76).', modulo_origen='modulo5', id_usuario=3`.
6. Se corrió el scheduler una tercera vez: **0 revertidos** — idempotente (el activo ya no
   aparece en `listar_en_tratamiento()`).

Notas de datos de prueba (dev, append-only): quedó el medicamento 18 (test) y el
tratamiento 15 pasó a `ANULADO` con la justificación de la prueba. El activo 5 quedó en
`ACTIVO` (antes `EN_TRATAMIENTO`) como resultado esperado de esta verificación — a diferencia
del estado descrito en `implementacion_dev_m05_rf75_rf76.md`, que documentaba un snapshot
anterior a este cierre.

## Qué sigue sin cubrirse (fuera de alcance de RF-76, no pedido)

- Bus asíncrono RF-80 y deduplicación por `id_evento_m05`.
- Panel de configuración/disparo manual del scheduler (RF-76, a diferencia de RF-74, no lo pide).
- Entrega garantizada de notificaciones (colas de reintento, estado de envío persistido) —
  aquí es best-effort simple, igual que el resto del cierre de este módulo.
