# INC-M09-106-G31 (#297) — La clasificación semafórica no usaba los niveles RF-17

Reevaluación V2 (`RUN_ID G31-REEVAL-V2-20260913-103722`, TC-M09-66/67/68, DESAPROBADA en
TEST y DEV). QA confirma que la ingesta marca `VERDE` para toda `LECTURA_VALIDA` sin evaluar
los niveles NORMAL/PRECAUCIÓN/CRÍTICO de RF-17, y que AMARILLO/ROJO dependen únicamente de la
severidad de alertas M03, sin relación con los intervalos configurados. Issue relacionado ya
documentado como bloqueado: `#159` (INC-M09-32-G31, precondiciones de TEST).

Complementa `INC-M09-107-G32` (#298, historial RF-59, ya resuelto) — este issue es la mitad
que falta: el **estado en tiempo real** (`estados_actuales_sensores.estado_semaforo`,
RF-58/dashboard).

## Hallazgo: no es un proceso externo, es un trigger propio de esta BD

`modulo3.fn_actualizar_estado_sensor()` (trigger `trg_rf58_01_cache_estado_sensor`, `AFTER
INSERT ON modulo3.telemetrias`, definido en `alembic/baseline/esquema_baseline.sql`) hardcodea
`estado_semaforo = 'VERDE'` para toda `LECTURA_VALIDA`, sin consultar RF-17. Esto corrige una
suposición de `INC-M09-107-G32`: el dashboard no depende de un proceso Edge/IoT externo para
esta parte — es lógica de este mismo repositorio.

**Por qué no se reescribió el trigger**: corre en `AFTER INSERT` sobre `telemetrias`, pero la
vinculación `telemetria → activo_biológico → especie` (RF-61-A) se crea **después**, en una
transacción independiente (`ingerir_telemetria_use_case.py`, tras el `commit()` de la
telemetría). El trigger no puede conocer la especie en el momento en que se dispara — no es un
problema de "falta lógica SQL", es una restricción de orden de las transacciones. Reescribirlo
tampoco resolvería el problema real (ver siguiente hallazgo). Se decidió (con el usuario)
recalcular en Python después de que la vinculación se resuelve, reutilizando exactamente la
misma lógica ya implementada para el historial — sin migración de Alembic.

## Segundo hallazgo: la vinculación automática también es un stub (M02 ↔ M03)

`VincularLecturaActivoUseCase` (RF-61-A) depende de `ActivoBiologicoDependencyPort`, cuya única
implementación es `ActivoBiologicoStubAdapter` — **siempre retorna `[]`** → toda vinculación
automática queda `SIN_VINCULAR`. Se verificó en BD: las únicas 6 filas `VINCULADA` que existen
tienen `mecanismo_vinculacion='AUTOMATICA'` pero `fecha_captura` de 2024 — son datos de siembra,
no producto del flujo automático real (que hoy nunca vincula nada).

A diferencia del bloqueo de `INC-M09-104-G29` (Backend → Nodo Edge, requiere mapeo +
contrato MQTT con otro equipo), este stub es **interno**: `src/biological_assets` (M02) ya
existe en este mismo repositorio, con `activos_biologicos.id_dispositivo_iot` como columna real.
Implementar el adaptador real requeriría resolver "cuál es el activo *vigente* para este
dispositivo" (un dispositivo puede tener varios activos a lo largo del tiempo/ciclos —
verificado: dispositivo 1 tiene 7 activos con distintos `id_estado`) — trabajo real pero de
alcance mayor al de este issue, y no lo pidió el reporte de QA. **No se toca en este fix.**

## Qué se implementó

Dado que la vinculación automática no resuelve nada hoy, la única vía **real y verificable**
para que RF-17 gobierne el semáforo en tiempo real es la vinculación manual (RF-61-C, ya
implementada y sin stubs): `PATCH /iot/vinculaciones/{id}/resolver` (AMBIGUA → VINCULADA) y
`POST /iot/vinculaciones/{id}/corregir` (corrección inmutable). Se creó
`ReclasificarSemaforoUseCase`, que:

1. Recibe `id_telemetria` + `id_activo_biologico` (ya resuelto por la vinculación).
2. Resuelve `id_especie` vía `EspecieActivoM02Adapter` (`modulo2.activos_biologicos`, lectura
   directa — no requiere el stub de `ActivoBiologicoDependencyPort`, ya que aquí el activo ya
   es conocido, solo falta su especie).
3. Consulta el umbral RF-17 vigente vía `UmbralHistoricoM09Adapter` — el mismo adaptador que ya
   implementa `INC-M09-107-G32` para el historial.
4. Calcula el color con `SemaforoCalculator.calcular_por_niveles` — la misma función que usa el
   historial (una sola fuente de verdad, pedido explícito de QA).
5. Sobrescribe `estados_actuales_sensores.estado_semaforo` vía
   `actualizar_estado_semaforo_si_vigente`, con guarda `ultimo_timestamp_captura <=
   :timestamp_captura` para no pisar el semáforo de una lectura más reciente del mismo sensor
   si se corrige una vinculación vieja.

Se conecta como efecto colateral de mejor esfuerzo (try/except, no rompe la operación principal)
en tres puntos: `IngerirTelemetriaUseCase` (tras RF-61-A automática — hoy sin efecto práctico
por el stub, pero correcto en cuanto se reemplace), `ResolverVinculacionUseCase` y
`CorregirVinculacionUseCase` (ambos con efecto real hoy).

## Qué sigue sin resolver

- **Vinculación automática (M02↔M03)**: sigue en `ActivoBiologicoStubAdapter`. Mientras tanto,
  el semáforo en tiempo real solo refleja RF-17 para lecturas vinculadas manualmente
  (`resolver`/`corregir`), no para telemetría fresca del flujo normal de ingesta.
- **AMARILLO/ROJO por alertas M03**: `ObtenerDashboardUseCase._calcular_semaforo_efectivo`
  sigue aplicando el override de alertas (`tiene_alerta_critica`→ROJO,
  `tiene_alerta_activa`→al menos AMARILLO) **sobre** el color ya calculado por RF-17. Esto no
  se tocó: es una capa operacional distinta (alertas), no la configuración RF-17, y QA no pidió
  eliminarla — solo que la base ya no sea un `VERDE` fijo sin evaluar niveles.
- **Reejecución de TC-M09-66/67/68**: pendiente por QA tras el merge, usando el flujo real
  disponible hoy (vincular manualmente vía `resolver`/`corregir`, no depender de la vinculación
  automática).
