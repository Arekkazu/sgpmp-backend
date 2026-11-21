# Matriz de compatibilidad de payload — lab G43

Fuente firmware: `a_payload` (worktree `e618a75` + CA-6 de trabajo).  
Fuente backend: `RecibirEventoEdgeDTO`.  
Puente: `reenvio_nodo.evento_edge` añade `device_id`, `sensor_id`, `serial` del topic.

| Campo | Firmware 076 | Firmware 077/078 | DTO | Acción lab |
|---|---|---|---|---|
| `clasificacion_rf55` | `NORMAL` | `DESVIACION_SIMPLE` | Obligatorio; ambos válidos | OK |
| `severidad` | Ausente | `CRITICO` | Opcional | OK; no inventar LEVE en 076 |
| `variables_involucradas[].tipo_variable` | `temperatura_ambiente` | igual | string libre | Ver nota catálogo |
| `valor` | 21.0 | 35.0 / 10.0 | Decimal | OK |
| `unidad` | `C` | `C` | OK (`C` y `°C` en alertas) | OK |
| `sensor` | Puede faltar | igual | Opcional | Sembrar un sensor; el puente usa fallback |
| `serial` | `G43-LAB-001` | igual | Topic gana | OK |
| `timestamp_captura` / `_procesamiento_edge` | ISO UTC `Z` | igual | `FechaHoraUtc` | OK |
| `origen` | `TIEMPO_REAL` | igual | Obligatorio | OK |
| `estado_conectividad` | bool | bool | Obligatorio | OK |
| `metadata_edge.id_evento` | `edge-evt-`+UUID | igual | Obligatorio (o `id_evento_edge`) | Clave de correlación |
| `device_id` / `sensor_id` | No los manda el Edge | igual | Obligatorio | Los pone el gateway tras SELECT modulo9 |
| `valor_evaluado` / `umbral_*_aplicado` | No van en el primer nivel | igual | Opcional | No bloquea G43 |
| CONTRATO §2 | Dice que NORMAL no se emite | — | DTO sí acepta NORMAL | **No se modifica el contrato.** Incompatibilidad documentada |

## `temperatura_ambiente` vs `TEMPERATURA_AMBIENTAL`

| Capa | Nombre |
|---|---|
| Firmware lectura / umbral / payload evento | `temperatura_ambiente` (fixture G43) |
| `EDGE_RF55_VARIABLES` (plantilla agente) | `TEMPERATURA_AMBIENTAL=temperatura_ambiente` |
| Backend consolidación M04 / alertas RF-57 | códigos `TEMPERATURA_AMBIENTAL` |
| DTO de ingesta de evento | no valida contra el catálogo |

**No se cambia el DTO ni el CONTRATO en esta preparación.**

- 076 (NORMAL) no consolida paquete M04: el nombre de variable **no** impide persistir el evento.
- 077/078 pueden persistir el evento con `temperatura_ambiente`; el paquete M04 podría quedar incompleto si el consolidar exige el código de catálogo. Eso es **fuera del CA de clasificación G43** (HTTP 201 + fila `clasificacion_rf55`).
- Si Análisis exige alinear el catálogo, el cambio sería en el **firmware** (`FakeVariable.nombre` y `Umbral.variable`) o en un alias, no en un POST fabricado.

Cambio requerido **solo si** el lab demuestra 422/rechazo por variable: abrir incidencia; no parchear el DTO a ciegas.
