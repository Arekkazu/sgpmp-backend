# INC-M03-167-G75 — Reevaluación de alertas tras la recuperación del motor de IA (TC-M03-153, N15, N16)

**RF:** RF-57, E3 (motor no disponible), E16 (reevaluación por IA tras la recuperación) y CA-6.
**Issue:** #745. **Depende de:** INC-M03-166-G73 (#744), porque usa el mismo patrón de parámetro de
DEV-14 con valor base; esta rama parte de la de G73.
**Estado:** implementado y verificado con PostgreSQL real.

## Causa

No existía ninguna entrada para la reevaluación. Las columnas `referencia_alerta_original` y
`tiene_generada_por_reevaluacion` ya estaban en la BD y en las respuestas, pero nada las llenaba. Por eso
una alerta creada con el motor caído (`tiene_inferencia_no_disponible = true`) se quedaba para siempre
con la severidad del Edge.

## Entrada (el RF no la define)

**`POST /iot/alertas/{id_alerta}/reevaluacion`**. Usa el **mismo canal y el mismo token de servicio**
(`Authorization: Bearer <BROKER_SERVICE_TOKEN>`) por los que hoy entran los eventos de IA en
`POST /iot/alertas` (`origen_evento = IA`). Cuando se integre M04 (IA-1, ver G58), el motor llama a esta
ruta al recuperarse, o al caso de uso `ReevaluarAlertaUseCase` si la llamada es en proceso.

```bash
curl -X POST "$API/iot/alertas/496/reevaluacion" \
  -H "Authorization: Bearer $BROKER_SERVICE_TOKEN" -H "Content-Type: application/json" \
  -d '{"severidad_ia": "CRITICO", "tipo_alerta_ia": "ESTRES_TERMICO", "probabilidad_ia": 0.91,
       "id_paquete_inferencia": 120, "metadata_reevaluacion": {"version_modelo": "v3"}}'
```

| Campo | Obligatorio | Descripción |
|---|---|---|
| `severidad_ia` | Sí | LEVE, MODERADO o CRITICO |
| `tipo_alerta_ia` | No | Tipo que propone la IA. Si no se envía, se toma el de la alerta original |
| `probabilidad_ia` | No | Entre 0 y 1; queda como traza |
| `id_paquete_inferencia` | No | Paquete reevaluado |
| `metadata_reevaluacion` | No | Datos del motor (versión, etc.) |

## Reglas (E16)

| Situación | Respuesta | Efecto |
|---|---|---|
| Tipo **o** severidad distintos de los de la alerta original | **201** `{"resultado": "ALERTA_GENERADA", "id_alerta_original", "id_alerta_nueva", ...}` | Alerta **nueva**: `origen_evento = IA`, `referencia_alerta_original`, `tiene_generada_por_reevaluacion = true` y `tiene_inferencia_no_disponible = false`. Conserva el evento original (sensor, variable, valor, `fecha_evento`, área, activo y telemetría) y suma `metadato_evento.reevaluacion`. El SLA se calcula con la severidad nueva. **La alerta original no se modifica** |
| Confirma tipo **y** severidad | **200** `{"resultado": "CONFIRMADA"}` | Sin alerta nueva; `REEVALUACION_CONFIRMADA` en la bitácora RF-63 |
| Fuera de la ventana | **422** `VENTANA_REEVALUACION_VENCIDA` | `REEVALUACION_FUERA_DE_VENTANA` en la bitácora |
| La alerta no se generó sin motor, es TECNICA o ya es producto de una reevaluación | **422** `REEVALUACION_NO_APLICA` | — |
| La alerta ya tiene su alerta de reevaluación | **409** `REEVALUACION_YA_REGISTRADA` | Lock consultivo por alerta original: no hay dos reevaluaciones concurrentes |
| La alerta no existe | 404 `ALERTA_NO_ENCONTRADA` | — |
| Token ausente o inválido | 401 | — |

**Ventana:** se mide desde `fecha_generacion` de la alerta original. El borde es **inclusivo**: 60:00
entra y 60:00.001 no. Es configurable con el parámetro de DEV-14 **`rf57_ventana_reevaluacion_min`**
(entero, ≥ 1). Si falta, se usa el **valor base del RF (60)**, con el mismo criterio que G73. Un valor
inválido responde 503 `PARAMETRO_CONFIGURACION_INVALIDO`.

## Cambios

- `src/telemetry/application/use_cases/alertas/reevaluar_alerta_use_case.py` (nuevo).
- `src/telemetry/infrastructure/dto/reevaluar_alerta_dto.py` (nuevo) y `ResultadoReevaluacionSchema` en
  `alerta_schema.py`.
- `alerta_router.py`: `POST /iot/alertas/{id_alerta}/reevaluacion`.
- `AlertaRepository.buscar_reevaluacion`, con lock consultivo `rf57:reevaluacion:<id>`.
- **Parámetro** `rf57_ventana_reevaluacion_min`:
  - `parametro_mlops.py`
  - validación en `configurar_parametros_mlops_use_case.py`
  - `ParametrosAlertasPort.obtener_ventana_reevaluacion_min` y su adaptador
  - documentación de DEV-14 (`dev14_parametros_operativos.md` y el JSON de ejemplo)

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_167_g75_reevaluacion_ia.py`, sin BD y con el reloj
inyectado:
- **Bordes de N16:** 59:59 y **60:00** se aceptan; **60:00.001** y 60:01 se rechazan.
- **Ventana configurada:** con 90 min, 89 se acepta.
- **Reevaluación que difiere:** crea la alerta vinculada (IA, referencia, flags, mismo evento, SLA de
  CRITICO de 5 min) y la original queda intacta. Un tipo distinto con la misma severidad también crea
  alerta.
- **Reevaluación que confirma (N15):** no crea alerta.
- **Rechazos:** las tres alertas que no admiten reevaluación, la segunda reevaluación (409), la alerta
  inexistente y los valores fuera del catálogo en el DTO.

**Pruebas de integración.** `tests/integration/test_inc_m03_167_g75_reevaluacion_ia.py`: router real y
PostgreSQL real. La alerta original se **inserta** con `fecha_generacion` en el pasado: el trigger
`trg_rf57_04_contenido_inmutable` solo impide el UPDATE, que era lo que bloqueaba N16 en QA.

| Caso de QA | Prueba | Resultado |
|---|---|---|
| TC-M03-153: reevaluación que difiere | `test_153_reevaluacion_que_difiere_crea_alerta_vinculada` | 201; alerta IA CRITICO con referencia y flags; la fila original queda idéntica |
| TC-M03-N15: reevaluación que confirma | `test_n15_reevaluacion_que_confirma_no_crea_alerta` | 200 CONFIRMADA; 0 alertas vinculadas; `REEVALUACION_CONFIRMADA` |
| TC-M03-N16: 59:59 / 60:01 | `test_n16_ventana_de_60_minutos` | 201 / 422 y `REEVALUACION_FUERA_DE_VENTANA`. El 60:00 exacto se prueba en la unitaria (por HTTP siempre pasan algunos ms) |
| Ventana configurada (BUG-G57A-03) | `test_ventana_configurada_por_el_administrador` | Con 90 min, una alerta de hace 75 min se acepta |
| Idempotencia | `test_segunda_reevaluacion_es_409` | 201 y luego 409 |
| No aplica | `test_alerta_que_no_admite_reevaluacion[...]` | 422 |
| Errores | `test_alerta_inexistente_y_token_ausente` | 404 / 401 |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g75_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Unitarias (G75 + G73 + DEV-14)                                         74 passed
Integración (G75 + G73 + DEV-14, DEV-30, DEV-49, DEV-41)               75 passed, 6 skipped
Suite completa (sin red): 2296 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Fuera de alcance

- **Llamada automática desde M04:** el motor no está integrado (contrato IA-1, G58). Esta entrada es la que
  usará al recuperarse.
- **Reevaluaciones que generan alerta nueva:** no se registra un tipo de bitácora propio; queda el
  `ALERTA_GENERADA` del repositorio, y la relación con la original viaja en la alerta
  (`referencia_alerta_original` y `metadato_evento.reevaluacion`). El RF solo pide
  `REEVALUACION_CONFIRMADA` para el caso que confirma.

## Para QA

- **TC-M03-153 y N15:** usar `POST /iot/alertas/{id}/reevaluacion` con el token de servicio, sobre una
  alerta con `tiene_inferencia_no_disponible = true`.
- **TC-M03-N16:** se puede probar sin esperar 60 min si se inserta la alerta con `fecha_generacion` en el
  pasado (INSERT, no UPDATE), o si se baja la ventana con `rf57_ventana_reevaluacion_min`.
