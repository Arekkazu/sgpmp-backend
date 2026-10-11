# INC-M09-107-G32 (#298) — Monitoreo no consumía las modificaciones de umbrales RF-17

Reevaluación V2 (`RUN_ID G32-REEVAL-V2-20260913-021645`, TC-M09-69, DESAPROBADO en TEST y DEV).
QA confirma que `UmbralHistoricoM09Adapter` seguía siendo un stub y que el dashboard no
consulta `umbrales_ambientales`/`niveles_alerta_ambientales`.

Issue relacionado ya cerrado como bloqueado: `#160` (INC-M09-33-G32,
`inc_m09_monitoreo_umbral_efectivo_bloqueado.md`, 6 de septiembre). Ese análisis concluyó que
faltaba correlación `sensor → variable → activo → especie` y mapeo `tipo_variable ↔
variables_ambientales`. Esta iteración verificó ese mismo hueco contra la BD real y encontró
que **ya no es un bloqueo completo**: parte del camino se puede resolver dentro de este mismo
backend, sin depender de otro equipo.

## Qué se verificó en BD (MCP postgres, `sgpmp_dev`)

- `modulo3.telemetrias.id_variable` **es el mismo espacio de ids** que
  `modulo9.variables_ambientales.id_variable_ambiental` (verificado id por id: 1=Temperatura
  del agua, 2=pH del agua, 3=Oxígeno disuelto, …). No hace falta pasar por el catálogo
  `CATALOGO_I3P1` (que además no tiene entrada para id 1, "temperatura del agua" — el caso de
  prueba de QA — solo cubre `PH_AGUA`(2) y `OXIGENO_DISUELTO`(3); queda anotado pero fuera de
  alcance de este fix porque no lo necesita).
- La especie sí es resoluble: `modulo3.vinculaciones_lecturas.id_activo_biologico` →
  `modulo2.activos_biologicos.id_especie`. `historial_telemetria_repository.py` **ya hacía**
  ese join para mostrar el nombre de la especie en el historial; solo faltaba seleccionar
  también el `id_especie` para poder consultar el umbral.
- `src/configuration` (RF-17) ya expone `SqlAlchemyUmbralAmbientalRepository
  .obtener_por_especie_y_variable(id_especie, id_variable_ambiental)`, con `niveles`
  (normal/precaución/crítico) completos. No hizo falta escribir SQL nueva contra M09: el
  adaptador de M03 reutiliza ese repositorio real en vez de duplicar la consulta.

## Qué sigue bloqueado (mismo root cause que INC-M09-104-G29)

El camino de **escritura** (Backend → Nodo Edge, para que el dispositivo aplique el umbral en
campo) sigue bloqueado por lo mismo que ya documentó anoche `INC-M09-104-G29`
(`inc_m09_104_g29_sincronizacion_edge_umbrales.md`): no existe mapeo `especie/variable →
dispositivo concreto` ni contrato de publicación MQTT. `EdgeSincronizacionPort` sigue con su
adaptador stub (degrada a `PENDIENTE`), correctamente, y no se toca en este fix.

El **dashboard en tiempo real** (`GET /iot/monitoreo/dashboard`) tampoco se toca: la columna
`modulo3.estados_actuales_sensores.estado_semaforo` no la calcula este backend — la escribe un
proceso externo (Edge/IoT), y no hay en `src/` ningún punto que evalúe umbrales contra el valor
crudo en tiempo real (`GenararAlertaUseCase` recibe severidad ya clasificada por Edge/IA, no la
calcula). Hacer que el dashboard "consuma" RF-17 requeriría ese mismo mapeo + contrato de
Edge — no es un problema de este backend en aislamiento.

## Qué se implementó (alcance de esta iteración: historial RF-59)

1. `UmbralHistoricoPort.obtener_umbral_vigente` cambia su firma de `tipo_variable: str` a
   `id_variable_ambiental: int` — ya no hace falta el tipo string porque el historial trae el
   id real de M09 directamente.
2. `UmbralHistoricoM09Adapter` deja de ser un stub: resuelve el umbral activo vía
   `SqlAlchemyUmbralAmbientalRepository`, devuelve `id_umbral_ambiental`, `umbral_min`,
   `umbral_max`, `niveles` y `version` (= `fecha_actualizacion` del umbral; M09 no tiene una
   columna de versión explícita, y no se agrega una en este fix — ver limitación abajo).
3. `historial_telemetria_repository.py` selecciona `ab.id_especie` (el join ya existía) y lo
   mapea a `LecturaHistorica.id_especie`.
4. `SemaforoCalculator.calcular_por_niveles` reemplaza el cálculo por `umbral_min/max +
   tolerancia_pct` para el histórico: usa las bandas normal/precaución/crítico de RF-17
   directamente (más preciso que el heurístico de tolerancia). Un valor fuera de todas las
   bandas configuradas se trata como `ROJO`.
5. `ConsultarHistorialUseCase._semaforo_historico` pasa `id_variable_ambiental` + `id_especie`
   reales al puerto y expone en `LecturaHistorica` el umbral usado
   (`id_umbral_ambiental`, `valor_min_umbral`, `valor_max_umbral`, `version_umbral`) para que el
   contrato permita identificar qué configuración RF-17 se aplicó (pedido explícito de #298).

## Limitación conocida que no se resuelve aquí

RF-59 Restricción 16 pide el umbral **vigente en el timestamp** de la lectura (versionado con
`fecha_inicio_vigencia`/`fecha_fin_vigencia`). `modulo9.umbrales_ambientales` no tiene esas
columnas — solo `es_activo` y `fecha_actualizacion`. Este fix resuelve contra el umbral
**actualmente activo**, no contra el vigente históricamente en esa fecha (si el umbral cambió
después del `timestamp_captura` de una lectura antigua, el histórico usa la config nueva, no la
de ese momento). Agregar la vigencia temporal implica una migración nueva en `modulo9
.umbrales_ambientales`, fuera de alcance de esta iteración — queda para cuando se priorice esa
restricción.

## Reejecución de TC-M09-69

Pendiente por QA en TEST/DEV tras el merge — este fix no incluye la corrida de Postman/Newman
mencionada en la evidencia (`newman-TC-M09-69-v2-*.html`), solo el código y las pruebas unitarias
en `tests/telemetry/test_inc_m09_107_g32_umbral_historico_real_rf17.py`.
