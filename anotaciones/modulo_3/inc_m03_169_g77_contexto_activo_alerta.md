# INC-M03-169-G77 — La alerta no se asociaba al activo biológico (RF-57 Fase 3, E6, CA-7)

**RF:** RF-57, Fase 3 ("Se consulta RF-61 para obtener el contexto del activo biológico: id_animal o
id_lote, especie, unidad productiva, ubicación geográfica"), E6 y CA-7. **Issue:** #748.
**Estado:** corregido y verificado con PostgreSQL real.

## Causa

`POST /iot/alertas` solo resolvía el dispositivo y la unidad productiva, y llamaba al caso de uso **sin**
`id_activo_biologico` ni `contexto_activo_biologico`. Como el caso de uso calcula
`tiene_contexto_incompleto = (id_activo_biologico is None)`, toda alerta quedaba "incompleta", aunque el
sensor estuviera asociado a un lote. Eso pasó con las alertas 278, 288, 289 y 290 de QA.

## Solución

Puerto nuevo **`ContextoActivoAlertaPort`** y adaptador **`ContextoActivoAlertaM02Adapter`**, que el router
inyecta. Si quien llama no trae el activo, el caso de uso lo resuelve **en el momento del evento**,
del dato más preciso al más general:

| # | Fuente | Cuándo aplica | `fuente_vinculacion` |
|---|---|---|---|
| 1 | Vinculación de RF-61 de la lectura (`modulo3.vinculaciones_lecturas`, vigente y no SUPERADA) | El evento trae `id_telemetria` | `VINCULACION_RF61` |
| 2 | Asociación **explícita** del sensor al activo (M02 `asociaciones_activos_sensores` `directa` o `poblacional`, ACTIVA y vigente) | Un único activo | `ASOCIACION_SENSOR` |
| 3 | Asociación **ambiental** del sensor | Un único activo | `ASOCIACION_AMBIENTAL` |
| 4 | Activos presentes en la unidad productiva (`historial_infraestructura_activo`) | El sensor no tiene asociaciones y hay un único activo | `UNIDAD_PRODUCTIVA` |

**Varios candidatos en el mismo nivel no se adivinan.** Por ejemplo, un sensor ambiental de una unidad con
varios lotes queda con contexto **incompleto**.

**Contexto que se guarda** (`contexto_activo_biologico`):
- `id_activo_biologico`, `identificador` (lote o animal), `modelo_manejo`, `id_especie` y `especie`.
- `unidad_productiva`: `id_infraestructura`, nombre y tipo, con la unidad del activo **en ese momento**.
- `ubicacion`: finca y ubicación geográfica.
- `fuente_vinculacion`.
- `rf61`: el snapshot histórico de M02 a la fecha del evento (fase, peso, último evento sanitario,
  datos no disponibles), que es el mismo que usa la vinculación de RF-61.

**Contexto incompleto (E6 / CA-7):** `tiene_contexto_incompleto = true`, la alerta conserva la unidad
productiva si la hay, y `metadato_evento.contexto_incompleto` explica el **motivo**
(`SIN_ACTIVO_ASOCIADO` o `VARIOS_ACTIVOS_CANDIDATOS`) y la fuente. Así se distingue "sin asociación" de
"ambiguo", que era el otro punto del ticket.

**Sin cambios:** si quien llama ya trae el activo (flujo RF-17 → RF-57 de DEV-41, eventos Edge), no se
vuelve a resolver.

**RLS:** el router usa la sesión de sistema (`get_db_sistema`), que "ve lo que ve el Administrador"
(`database.como_sistema`). Es el mismo mecanismo con el que la vinculación de RF-61 del worker post-commit
lee estas tablas de M02 en producción.

## Cambios

- `src/telemetry/domain/repositories/contexto_activo_alerta_port.py` (nuevo).
- `src/telemetry/infrastructure/adapters/contexto_activo_alerta_m02_adapter.py` (nuevo).
- `generar_alerta_use_case.py`: la Fase 3 resuelve con el puerto y deja el motivo si queda incompleta.
- `alerta_router.py`: inyecta el adaptador.

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_169_g77_contexto_activo_alerta.py`, sin BD:
- **Activo resuelto:** completa el contexto.
- **Sin activo:** queda incompleto con su motivo.
- **Activo dado por quien llama:** no se vuelve a resolver.

**Pruebas de integración.** `tests/integration/test_inc_m03_169_g77_contexto_activo_alerta.py`: router real,
adaptadores reales y PostgreSQL real.

| Prueba | Escenario | Resultado |
|---|---|---|
| `test_sensor_asociado_al_lote_da_contexto_completo` | **Caso de QA:** sensor asociado a un lote, con otro activo en la unidad | `tiene_contexto_incompleto = false`, `id_activo_biologico` = el lote, contexto con identificador, especie, unidad, finca y ubicación geográfica |
| `test_asociacion_poblacional_tambien_cuenta` | Asociación `poblacional` | Ese activo |
| `test_asociacion_ambiental_de_un_solo_activo` | Asociación `ambiental` única | Ese activo (`ASOCIACION_AMBIENTAL`) |
| `test_varias_asociaciones_ambientales_es_contexto_incompleto` | Dos activos ambientales | Incompleto, `VARIOS_ACTIVOS_CANDIDATOS`, conserva la unidad |
| `test_sin_asociacion_y_un_activo_en_la_unidad` | Sin asociaciones y un activo en la unidad | Ese activo (`UNIDAD_PRODUCTIVA`) |
| `test_sin_activos_es_contexto_incompleto_ca7` | **CA-7:** nada asociado | Incompleto, `SIN_ACTIVO_ASOCIADO` |
| `test_asociacion_vencida_no_cuenta` | La asociación terminó antes del evento | Sin activo |
| `test_vinculacion_rf61_de_la_lectura_prevalece` | La lectura ya está vinculada por RF-61 a otro activo | Gana RF-61 (`VINCULACION_RF61`) |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g77_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Unitarias (G77 + DEV-41, DEV-49, DEV-44, DEV-13)                                   90 passed
Integración (G77 + DEV-49, DEV-41, DEV-30, DEV-44, DEV-17)                         93 passed, 9 skipped
Suite completa (sin red): 2267 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Fuera de alcance

- **Notificación al administrador para completar la asociación (E6 / CA-7, RF-22).** No forma parte de este
  ticket. El motivo queda en `metadato_evento.contexto_incompleto`, así que esas alertas se pueden filtrar.
- **Conflicto esperado al unir con la cadena G68 → G71 y con G73:** las ramas tocan
  `generar_alerta_use_case.py` en otras zonas (y agregan parámetros al constructor). Lo esperable es que
  solo choquen las filas de la tabla de seguimiento, los imports y los parámetros del constructor; se
  conservan los dos lados.
