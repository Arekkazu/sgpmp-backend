# INC-M03-199-G54 — Trazabilidad de la regla en eventos compuestos (TC-M03-G54)

**RF:** RF-55 §6, "Trazabilidad completa del evento": cada evento "tiene contexto (variables y **reglas
usadas**)"; también CA-4. **Issue:** #746.
**Estado:**
- **Backend:** corregido y verificado. Recibe y conserva la regla sin perderla.
- **Nodo Edge:** **bloqueado**. Evaluar la regla y emitir los campos le toca al firmware; el contrato de
  campos no está aprobado.

## Responsabilidades, como las separa el ticket

| # | Componente | Qué debe hacer | Situación |
|---|---|---|---|
| 1 | Nodo Edge (firmware, equipo IoT) | Evaluar las condiciones de la regla | **Bloqueado**. El firmware no está en los repositorios del backend ni del broker. En G43 (INC-M03-111) se confirmó que el `edge_agent` no implementa la clasificación de RF-55, y la prueba de QA queda SKIPPED porque el motor Edge no está disponible (`rf55_preparacion.py:62`) |
| 2 | Nodo Edge | Generar el evento DESVIACION_COMPUESTA con `regla_aplicada`, `nombre_regla` y `version_regla` | **Bloqueado**, por la misma razón |
| — | Broker (`BROKER-MQTT-SGPMP`) | Transportar el evento | Cumple: `reenvio_nodo.evento_edge` reenvía el cuerpo **tal cual** y solo fija el `serial` desde el topic |
| 3 | Backend | Recibir y procesar el evento sin perder los campos | **Corregido en este cambio** (ver abajo) |

**Contrato funcional:** RF-55 no nombra los campos. Los nombres `regla_aplicada`, `nombre_regla` y
`version_regla` vienen del caso de prueba de QA. Hasta que se apruebe el contrato (nombres, tipos y
obligatoriedad), el backend los acepta como **opcionales**. Es coherente con lo que el backend ya manda
al Edge al sincronizar reglas compuestas (broker `regla_compuesta`: `id_regla_alerta` y
`version_regla`, entero ≥ 1).

## Brecha del backend que se corrige

`RecibirEventoEdgeDTO` solo conservaba los campos si llegaban **dentro de `metadata_edge`**. Si el nodo
los enviaba en el **nivel superior** del JSON, Pydantic los **descartaba en silencio**
(`extra = 'ignore'`), y la trazabilidad se perdía sin ningún error.

## Qué hace ahora el backend

- **Contrato de `POST /iot/eventos-edge`:**
  - Acepta `regla_aplicada` (entero o texto no vacío), `nombre_regla` (texto, máximo 150) y
    `version_regla` (entero ≥ 1), tanto en el **nivel superior** como **dentro de `metadata_edge`**.
  - Los unifica en `metadata_edge`.
  - Si los dos lugares traen valores distintos, responde **400** `VAL_ENTRADA`, porque el evento es
    incoherente.
- **Conservación:** los tres campos quedan en `eventos_edge_computing.metadatos`, en
  `paquetes_inferencia.metadatos` (viajan con el paquete de RF-56 hacia M04) y en
  `alertas.metadato_evento` (RF-57).
- **Marca en eventos compuestos:** `metadatos.trazabilidad_regla_completa` (`true` o `false`) indica si el
  nodo envió la regla completa. **No se rechaza** un evento sin ella, porque la obligatoriedad depende del
  contrato aprobado, pero queda visible en los datos y QA puede consultarlo.

## Cambios

- `src/telemetry/domain/entities/telemetria.py`: `CAMPOS_TRAZABILIDAD_REGLA`.
- `src/telemetry/infrastructure/dto/recibir_evento_edge_dto.py`: los tres campos y
  `unificar_trazabilidad_regla`.
- `recibir_evento_edge_use_case.py`: `_metadatos_evento`, con la marca para los compuestos.
- `consolidar_paquete_inferencia_use_case.py`: el paquete conserva la regla.

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_199_g54_trazabilidad_regla.py`, sin BD:
- **Transporte:** nivel superior o `metadata_edge`, en ambos casos se unifican y el resto de
  `metadata_edge` se conserva.
- **Igualdad:** el mismo valor en los dos lugares se acepta.
- **Rechazos:** valores contradictorios, `version_regla` 0 o no numérica, y `regla_aplicada` o
  `nombre_regla` vacíos.
- **Sin campos:** no se inventa nada.

**Pruebas de integración.** `tests/integration/test_inc_m03_199_g54_trazabilidad_regla_edge.py`: router
real, adaptador real de M09 y PostgreSQL real.

| Prueba | Resultado |
|---|---|
| `test_evento_compuesto_conserva_la_regla_de_punta_a_punta[nivel_superior / metadata_edge]` | 201; los tres campos en el **evento, el paquete y la alerta**; `trazabilidad_regla_completa = true`; el resto de `metadata_edge` queda intacto |
| `test_evento_compuesto_sin_regla_se_acepta_y_queda_marcado` | 201; `trazabilidad_regla_completa = false`; el paquete no inventa campos |
| `test_regla_contradictoria_entre_nivel_superior_y_metadata_edge_es_400` | 400 `VAL_ENTRADA` |
| `test_evento_simple_no_se_marca` | Un evento simple conserva la regla y no lleva la marca de compuesto |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g54_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Unitarias (G54 + DEV-17, G42, DEV-49)                          57 passed
Integración (G54 + DEV-17, DEV-49, DEV-47)                     58 passed, 2 skipped
Suite completa (sin red): 2274 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Pendiente (fuera del backend)

1. **Equipo IoT (firmware Edge):** implementar la evaluación de reglas de RF-55 y emitir los tres campos en
   cada DESVIACION_COMPUESTA. Puede enviarlos en el nivel superior o en `metadata_edge`.
2. **Análisis:** aprobar el contrato (nombres, tipos y obligatoriedad). Si se vuelven obligatorios para
   DESVIACION_COMPUESTA, el backend pasa de marcar a rechazar con un cambio de una línea.
3. **QA:** reejecutar TC-M03-G54 cuando el motor Edge esté disponible. La parte del backend se puede
   verificar ya con `metadatos.trazabilidad_regla_completa`.
