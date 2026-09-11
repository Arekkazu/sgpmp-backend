# Implementación DEV — M05 CU05: Acumular inversión y proveer costos a M06 (RF-78, RF-79)

**Fecha:** 2026-07-31 · **Rama:** `feature/supplies`

Resumen de lo implementado para CU-05: acumulación continua y atómica de costos directos por
instancia de ciclo productivo (ALIMENTO/MEDICAMENTO heredados de RF-75/76 vía CU-01/CU-04, más
SERVICIO_VETERINARIO e INSEMINACION de registro directo nuevo en este CU — RF-78); y provisión
estructurada de esos costos hacia M06 para valoración NIC 41, con versionado y hash de integridad
(RF-79). Sigue la arquitectura hexagonal/DDD del proyecto (ver `CLAUDE.md`). RF-78 y RF-79 estaban
en 0% de implementación al iniciar este CU.

## Decisiones clave (acordadas antes de codificar)

- **M05 autocontenido frente a M06** (decidido explícitamente con el usuario): no se escribe en
  `modulo6.registros_costos` (schema real y maduro, con sus propias reglas RF-90 de
  PUC/`accounting_account` que M05 no tiene contexto para inventar). M05 persiste sus propios
  artefactos NIC41 (`acumulado_ciclo`, `provision_nic41`, eventos en `auditorias_suministros`) y
  expone endpoints de consulta/pull. La ingesta real hacia M06 queda pendiente explícito.
- **Hallazgo crítico verificado con datos reales**: `modulo9.ciclos_productivos` es un catálogo
  reutilizable, no una instancia única por activo (`id_ciclo_productivo=1` compartido
  simultáneamente por 4 activos distintos, algunos con fase `es_activa=true` a la vez). La clave
  real de "instancia de ciclo productivo de un activo" es `modulo2.gestiones_fases.id_gestion_fases`,
  no `id_ciclo_productivo` — el índice único preexistente de `acumulado_ciclo` estaba sobre la
  columna equivocada y habría mezclado los suministros de activos distintos en un mismo acumulado.
  Todo el diseño se re-clave sobre `id_gestion_fases` (Gap 1, el más grande de este CU).
- **Acumulación por trigger de BD, no por app**: un único trigger `AFTER INSERT` en
  `registro_suministro` (`trg_acumular_costo_ciclo`) mantiene `acumulado_ciclo` para las 4
  categorías por igual, extendiendo (additivamente) los triggers de CU-04 para que ALIMENTO/
  MEDICAMENTO también populen `id_gestion_fases`/`tipo_suministro`. Consistente con el principio ya
  establecido en el proyecto (`m05_triggers_logica`). Evita dos mecanismos de acumulación que
  podrían divergir.
- **Concurrencia**: la ruta feliz (REGISTRO) no necesita `SELECT FOR UPDATE` desde la app — el lock
  de fila del índice único de Postgres serializa la acumulación de forma nativa. Solo el flujo de
  corrección usa `SELECT ... FOR UPDATE` + `lock_timeout` explícito desde la app, porque necesita
  leer el acumulado **antes** de decidir si la corrección dejaría el total en negativo (FA-09).
- **RF-79 INCREMENTAL** se modela como un evento de auditoría (`auditorias_suministros`,
  `tipo_operacion='PROVISION_INCREMENTAL_ENTREGADA'`) en la misma transacción que la acumulación,
  no como una fila de `provision_nic41` — ese esquema (versión, hash, lista de registros) encaja
  con un artefacto CONSOLIDADO de baja frecuencia, no con un evento por cada suministro. El modelo
  es *pull* (M06/Contador consultan), no hay entrega HTTP separada que deduplicar.
- **`ConsolidarCicloUseCase` y `GenerarProvisionManualUseCase` comparten cadena de versiones**
  (`version_reporte`/`id_reporte_anterior`) — decisión corregida durante el diseño (se descartó un
  primer intento con `ConflictError("CICLO_YA_CONSOLIDADO")` que habría bloqueado el cierre oficial
  si antes se generó una provisión manual sobre el mismo ciclo).

Detalle completo de gaps de BD/RBAC (con todo el DDL aplicado, incluyendo el bug de trigger
encontrado en verificación) en [`cu05_gaps_bd_rf78_rf79.md`](cu05_gaps_bd_rf78_rf79.md).

## Paso 0 (BD/RBAC) — aplicado vía MCP postgres, resumen

- Gap 1 (crítico): `id_gestion_fases` agregado a `registro_suministro`, `acumulado_ciclo`,
  `provision_nic41`, `auditorias_suministros`; backfill de 18/18 filas; índice único de
  `acumulado_ciclo` recreado sobre `id_gestion_fases`; 2 vistas `vw_m05_*` corregidas.
- Gap 2: columna `tipo_suministro` en `registro_suministro` (backfill desde `id_registro_rf75/76`);
  índice único parcial de deduplicación por contenido (solo `tipo_operacion='REGISTRO'`).
- Gap 3: `AuditoriaSuministroModel` no existía — modelo ORM nuevo.
- Gap 4: 8 valores nuevos en `enum_auditoria_suministro_tipo_operacion`.
- Gap 5: `calcular_hash_integridad()` genérico, documentado sin modificar.
- Gap 6: trigger único de acumulación (`fn_acumular_costo_ciclo` + extensión de los 2 triggers de
  CU-04) — **corregido durante la verificación E2E** (ver más abajo).
- Gap 7: política de `naturaleza_costo` por categoría — M09 no tiene esa configuración; defaults
  documentados en `politica_naturaleza_costo.py`.
- Gap 8: recursos **55/56** + 16 permisos RBAC.
- Gap 9: RF-41 (cierre de ciclo) no existe — CU-05 verifica `gestiones_fases.es_activa=false` desde
  su propio endpoint de consolidación.
- Gap 10: anulación de RF-75/76 no revierte RF-78 automáticamente — mitigado, la corrección acepta
  `id_registro_original` de cualquier tipo de suministro.
- Gap 11: `provision_nic41.modalidad='INCREMENTAL'` sin usar, documentado.

## Estructura de código (`src/supplies/`)

### Dominio
- `domain/value_objects/` — `tipo_suministro.py` (`TipoSuministro` + constante `DIRECTOS`),
  `justificacion_precio.py`, `motivo_correccion.py` (min 20/max 500 chars, patrón
  `JustificacionAnulacion`), `eventos_auditoria_suministro_enums.py`.
- `domain/entities/` — `registro_suministro_directo.py` (`RegistroSuministroDirecto`, calcula
  `costo_registro` en Python vía `crear()`/`crear_correccion()` — a diferencia de ALIMENTO/
  MEDICAMENTO, aquí no hay trigger `BEFORE INSERT` que lo haga), `acumulado_ciclo.py`
  (`validar_correccion_no_negativa()` → `BusinessRuleError` 422 o delta seguro, `_snapshot()`),
  `provision_nic41.py`.
- `domain/services/` — `politica_naturaleza_costo.py` (función pura, Gap 7),
  `consolidador_nic41.py` (`construir_consolidado()` — calculadora pura reutilizada por
  consolidar/manual/corrección, patrón `calculadora_ica.py`; resuelve el costo "efectivo" de cada
  registro buscando la CORRECCION más reciente que lo referencia, y marca
  `es_reporte_potencialmente_incompleto` cuando el total recomputado difiere del acumulado
  almacenado).
- `domain/repositories/` (ports) — `ciclo_abierto_port.py` extendido (`id_gestion_fases` en
  `CicloAbierto`, nuevo `FaseProductiva` + `obtener_por_id()`), `registro_suministro_repository.py`,
  `acumulado_ciclo_repository.py`, `provision_nic41_repository.py`, `auditoria_suministro_port.py`.

### Infraestructura
- `infrastructure/models/` — `acumulado_ciclo_model.py`, `provision_nic41_model.py`,
  `auditoria_suministro_model.py` nuevos; `registro_suministro_model.py` modificado
  (`tipo_suministro`, `id_gestion_fases`). **`ciclo_productivo_model.py` nuevo** — no existía ningún
  modelo ORM para `modulo9.ciclos_productivos` en todo el proyecto (siempre consultada vía `text()`
  crudo); las FK de los modelos de CU-05 lo necesitan para resolver al hacer `flush()` (bug
  encontrado en verificación, ver abajo).
- `infrastructure/repositories/` — `registro_suministro_repository.py` (cuantiza cantidad/precio a
  escala real antes de comparar/persistir), `acumulado_ciclo_repository.py` (`obtener_bloqueando`
  con `SET LOCAL lock_timeout` + `with_for_update()`), `provision_nic41_repository.py` (Decimal↔str
  en JSONB), `auditoria_suministro_repository.py`.
- `infrastructure/adapters/ciclo_m02_adapter.py` — extendido con `obtener_por_id()` y
  `id_gestion_fases` en `obtener_abierto()`.
- `infrastructure/dto/` — `registrar_suministro_directo_dto.py`,
  `registrar_correccion_suministro_dto.py` (`id_registro_original` viaja en la URL, no en el body),
  `corregir_provision_dto.py`.
- `infrastructure/schema/` — `registro_suministro_directo_schema.py`, `acumulado_ciclo_schema.py`,
  `provision_nic41_schema.py` (paginación de `lista_registros`).
- `infrastructure/factories/` — `costeo_suministros_factory.py`, `provision_nic41_factory.py`.
- `infrastructure/routers/` — `costeo_suministros_router.py` (recurso 55: `POST ""`,
  `POST "/{id}/correccion"`, `GET "/acumulado/activo/{id}"`, `GET "/acumulado/ciclo/{id}"`),
  `provision_nic41_router.py` (recurso 56: `POST "/ciclo/{id}/consolidar"`,
  `POST "/ciclo/{id}/consolidar-manual"`, `POST "/{id}/correccion"`, `GET "/{id}"`,
  `GET "/ciclo/{id}/versiones"`).

### Aplicación
- `application/use_cases/costeo_suministros/` — `registrar_suministro_directo_use_case.py`
  (idempotencia → ciclo abierto → fecha en rango → dedup contenido → justificación → construir →
  reintentos con backoff 1s/3s/5s), `registrar_correccion_suministro_use_case.py` (mismo patrón +
  `SELECT FOR UPDATE` + validación FA-09; clasifica el agotamiento de reintentos en
  `CONFLICTO_CONCURRENCIA` (409) vs `REGISTRO_FALLIDO` (500) inspeccionando
  `psycopg2.errors.LockNotAvailable`/`DeadlockDetected`), `consultar_acumulado_ciclo_use_case.py`.
  Ambos use cases de registro devuelven `ResultadoRegistroDirecto(registro, ya_procesado: bool)`
  para que el router pueda responder `200` (no `201`) en un reenvío idempotente (E8).
- `application/use_cases/provision_nic41/` — `consolidar_ciclo_use_case.py`,
  `generar_provision_manual_use_case.py`, `corregir_provision_use_case.py` (recalcula desde el
  estado actual, no copia el valor anterior; no muta el `estado` de la versión anterior),
  `consultar_provision_use_case.py`, `listar_versiones_provision_use_case.py`.

**Nota de alcance async**: a diferencia de CU-02/CU-04, este CU no tiene cola/worker — el RF
describe los reintentos como parte de una request HTTP síncrona. `main.py` no necesitó tareas
nuevas en `lifespan`.

### `main.py`
- 2 routers nuevos registrados (`costeo_suministros_router`, `provision_nic41_router`).

## Verificación end-to-end

Ejecutada contra servidor local real con 5 usuarios de prueba (Admin/Productor/Veterinario/
Contador/Ingeniero de Campo para el caso RBAC negativo), usando los activos 57 (`id_gestion_fases
33`) y 5 (`id_gestion_fases 32`) como fixtures. Los 16 escenarios del plan más 1 caso adicional
(corrección sobre corrección) verificados exitosamente — CURLs completos y respuestas reales en
[`curls_m05_cu05_costeo_nic41.md`](curls_m05_cu05_costeo_nic41.md).

**Dos bugs reales encontrados y corregidos durante la verificación** (no en el análisis estático):

1. **`NoReferencedTableError` al registrar el primer suministro directo** — ningún módulo del
   proyecto tenía un modelo ORM para `modulo9.ciclos_productivos` (siempre se consultaba vía
   `text()` crudo); las FK de `registro_suministro`/`acumulado_ciclo`/`provision_nic41` hacia esa
   tabla nunca se habían ejercitado por el ORM hasta que los nuevos repositorios de este CU
   empezaron a usar `db.add()`/`flush()`. Corregido creando `CicloProductivoModel` (modelo mínimo,
   sin FK propias, solo para que SQLAlchemy pueda resolver la referencia).
2. **`chk_acumulado_no_negativo` fallaba en correcciones válidas con delta negativo** — bug real en
   el diseño del trigger `fn_acumular_costo_ciclo`: PostgreSQL valida el `CHECK` de una tabla contra
   los valores literales del `VALUES` de un `INSERT ... ON CONFLICT DO UPDATE`, **antes** de
   resolver si hay conflicto. Un delta de corrección negativo (p. ej. `-30000`) violaba el `CHECK`
   como candidato de inserción aunque el resultado final del `UPDATE` real fuera positivo
   (`230000 - 30000 = 200000`). No se manifestó en las pruebas de solo-REGISTRO (delta siempre
   positivo); apareció en el primer escenario con CORRECCION. Corregido reescribiendo el trigger
   como `UPDATE` primero (el `CHECK` se evalúa entonces contra el acumulado final correcto) con
   `INSERT ... ON CONFLICT DO UPDATE` solo como fallback si la fila no existe (caso alcanzable
   únicamente desde un REGISTRO, donde el delta siempre es positivo). Ver el detalle completo en
   `cu05_gaps_bd_rf78_rf79.md`.

Confirmado además: la concurrencia (2 requests simultáneas sobre un `id_gestion_fases` nuevo) no
pierde ninguna actualización; el hash de integridad de una provisión es estable en GETs repetidos;
la cascada de acumulación extendida a CU-01/CU-04 funciona sin tocar su código Python (un nuevo
registro ALIMENTO vía RF-75 actualiza `acumulado_ciclo` automáticamente); el detector de
"reporte potencialmente incompleto" del consolidador funciona correctamente (detectó y marcó
como incompleto un caso real del fixture de pruebas con datos anteriores al trigger).

## Qué NO se hizo (pendientes explícitos, ver gap doc)

- Política de capitalización por especie en M09 (Gap 7) — usa defaults documentados.
- Reversión automática de RF-78 al anular un registro RF-75/76 (Gap 10) — mitigado con corrección
  manual por Contador/Administrador.
- Ingesta real hacia `modulo6.registros_costos` — M05 solo expone lectura/pull; queda para cuando
  M06/RF-90 esté listo para consumir.
- Integración M40 (`origen_precio=M40_AUTOMATICO`) — sigue fuera de alcance, no existe en el sistema.
- Catálogo `tipos_suministro` en M09 con unidades por tipo — `unidad_medida` sigue sin catálogo.
- `provision_nic41.modalidad='INCREMENTAL'` sin usar (Gap 11).
- Backfill ambiguo de `id_gestion_fases` para 11 filas de `activo_biologico=1` (Gap 1) — resuelto
  por desempate determinístico, no por certeza temporal, por datos de semilla de M02 defectuosos.
