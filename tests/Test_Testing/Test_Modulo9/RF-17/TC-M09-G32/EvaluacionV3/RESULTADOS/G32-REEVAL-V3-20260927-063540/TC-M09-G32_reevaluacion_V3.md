# TC-M09-G32 — TERCERA EVALUACIÓN (V3)

**Caso agrupado:** TC-M09-G32
**Caso original:** TC-M09-69 — Verificar que una modificación de umbral actualice la configuración utilizada por Monitoreo
**Requerimiento:** RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental
**Caso de uso:** CU-03 — Configurar Umbrales y Alertas Ambientales por Especie
**Responsable QA:** Juan Esteban
**RUN_ID:** `G32-REEVAL-V3-20260927-063540`
**Fecha:** 2026-09-27
**Ambiente decisorio:** TEST
**Incidencia en seguimiento:** INC-M09-107-G32 (#298)

---

## DECISIÓN GENERAL

### TC-M09-G32: APROBADO

### TC-M09-69: APROBADO

La tercera evaluación confirmó que una modificación de la configuración RF-17 queda reflejada en la
configuración utilizada por Monitoreo.

La misma lectura histórica que antes del cambio utilizaba el umbral #1 con rango 0.00–100.00 pasó,
después de la modificación, a identificar el mismo umbral con rango 0.00–32.00 y una nueva versión de
configuración.

Por tanto, se cumple el objetivo de TC-M09-69 y, al ser el único caso original contenido en
TC-M09-G32, el grupo TC-M09-G32 queda APROBADO.

**INC-M09-107-G32 (#298): CORREGIDO Y VERIFICADO EN V3.**

---

## RESUMEN DEL RESULTADO

| Caso agrupado | Caso original | Esperado | Obtenido | Resultado |
|---|---|---|---|---|
| TC-M09-G32 | TC-M09-69 | Una modificación RF-17 debe reflejarse en la configuración utilizada por Monitoreo | La misma lectura histórica pasó de utilizar rango 0.00–100.00 a 0.00–32.00 y mostró la nueva versión del umbral | **APROBADO** |

---

## ANTECEDENTES

**V1 — BLOQUEADO.** Monitoreo no permitía identificar qué configuración RF-17 utilizaba.

**V2 — DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA.** `UmbralHistoricoM09Adapter` era un stub y el
historial no consumía RF-17, por lo que no existía forma de correlacionar `RF17_BEFORE` con
`MONITORING_BEFORE` y no se ejecutó la modificación.

**Issue #298.** Se registró la ausencia de integración RF-17 → Monitoreo.

**PR #382.** Implementó la resolución real del umbral RF-17 en el historial e incorporó a la respuesta
`id_especie`, `id_umbral_ambiental`, `valor_min_umbral`, `valor_max_umbral` y `version_umbral`.

**V3.** Verifica funcionalmente la corrección. El contrato desplegado en TEST se comprobó antes de
cualquier escritura: los cinco campos están presentes y los endpoints de consulta, modificación y
auditoría de umbrales están operativos.

---

## ENTORNO

| Ambiente | Uso |
|---|---|
| TEST | Ambiente decisorio; ejecución funcional V3 |
| DEV | Contraste disponible; no fue necesario ejecutar funcionalmente porque TEST aprobó |

---

## ACTOR

Administrador autorizado con permisos de modificación sobre RF-17.

---

## CONFIGURACIÓN UTILIZADA

| Elemento | Valor |
|---|---|
| Lectura histórica | `id_telemetria` 31 |
| Sensor | 1 |
| Activo biológico | 1 |
| Especie | 1 — Tilapia Roja |
| Variable | 1 — Temperatura del agua |
| Umbral RF-17 | #1 |

Se utilizó una lectura histórica ya contextualizada, por lo que no fue necesario generar una
telemetría nueva. El umbral #1 es la única configuración activa para esa combinación de especie y
variable.

---

## RF17 BEFORE

| Campo | Valor |
|---|---|
| `id_umbral_ambiental` | 1 |
| Rango general | 0.00 – 100.00 |
| Nivel crítico | 0.00 – 20.00 |
| Nivel precaución | 20.00 – 25.00 |
| Nivel normal | 25.00 – 30.00 |
| `es_activo` | true |
| `fecha_actualizacion` | null |

---

## MONITORING BEFORE

| Campo | Valor |
|---|---|
| `id_umbral_ambiental` | 1 |
| `valor_min_umbral` | 0.00 |
| `valor_max_umbral` | 100.00 |
| `version_umbral` | null |
| `id_especie` | 1 |
| `estado_semaforo_historico` | ROJO |

`MONITORING_BEFORE` representa la misma configuración que `RF17_BEFORE`.

---

## MODIFICACIÓN RF-17

Una sola escritura sobre el umbral #1:

| | BEFORE | AFTER |
|---|---|---|
| Rango general | 0.00 – 100.00 | 0.00 – 32.00 |
| Nivel normal | 25.00 – 30.00 | 25.00 – 32.00 |
| Nivel precaución | 20.00 – 25.00 | sin cambio |
| Nivel crítico | 0.00 – 20.00 | sin cambio |

La configuración almacenada declaraba un rango general de 0.00–100.00 mientras sus niveles cubrían
solo 0.00–30.00, y 100.00 excede el máximo físico de la variable (45 °C). Las reglas vigentes de
RF-17 exigen que el rango general coincida con la cobertura de los niveles contiguos y quede dentro
de los límites físicos, de modo que la modificación normaliza el rango general y amplía su límite
superior en 2.00 unidades sobre la cobertura real. El payload se validó previamente contra esas
reglas.

```
PATCH → HTTP 500 FALLO_SINCRONIZACION_EDGE
GET posterior → confirma que la modificación persistió
```

No se reintentó la escritura. El HTTP 500 corresponde al fallo de propagación hacia los nodos Edge,
posterior al guardado, y pertenece a una incidencia de sincronización ya conocida e independiente
(INC-M09-104-G29). No invalida el oráculo de TC-M09-G32, que evalúa si Monitoreo utiliza la
configuración efectivamente almacenada.

---

## RF17 AFTER

| Campo | Valor |
|---|---|
| `id_umbral_ambiental` | 1 |
| Rango general | 0.00 – 32.00 |
| Nivel normal | 25.00 – 32.00 |
| Nivel precaución | 20.00 – 25.00 |
| Nivel crítico | 0.00 – 20.00 |
| `es_activo` | true |
| `fecha_actualizacion` | 2026-09-27T11:35:43.258018Z |

La auditoría del umbral registra un único `UPDATE`, con `valores_anteriores` 0.00 / 100.00 y
`valores_nuevos` 0.00 / 32.00.

---

## MONITORING AFTER

Se consultó **la misma lectura histórica** (`id_telemetria` 31):

| Campo | BEFORE | AFTER |
|---|---|---|
| `id_umbral_ambiental` | 1 | 1 |
| `valor_min_umbral` | 0.00 | 0.00 |
| `valor_max_umbral` | 100.00 | **32.00** |
| `version_umbral` | null | **2026-09-27T11:35:43.258018Z** |
| `id_especie` | 1 | 1 |
| `estado_semaforo_historico` | ROJO | ROJO |

Una sola consulta fue suficiente; no hubo discrepancias ni relectura confirmatoria.

La clasificación semafórica es evidencia secundaria: el valor de la lectura (36.21 °C) queda fuera de
todas las bandas configuradas tanto antes como después del cambio, por lo que el semáforo permanece
en ROJO. La modificación no se diseñó para provocar un cambio de color.

---

## RESULTADO DEL ORÁCULO

| Verificación | Resultado |
|---|---|
| MONITORING_BEFORE representa RF17_BEFORE | CUMPLE |
| RF17_AFTER difiere de RF17_BEFORE | CUMPLE |
| MONITORING_AFTER utiliza el mismo umbral actualizado | CUMPLE |
| Monitoreo expone el nuevo rango | CUMPLE |
| Monitoreo expone la nueva versión | CUMPLE |
| Monitoreo ya no utiliza el rango de RF17_BEFORE | CUMPLE |
| Auditoría registra la transición | CUMPLE |

**Newman: 22 assertions, 0 fallidas.**

---

## COMPARACIÓN V1 VS V2 VS V3

| Aspecto | V1 | V2 | V3 |
|---|---|---|---|
| Resultado TC-M09-G32 | **BLOQUEADO** | **DESAPROBADO** | **APROBADO** |
| Resultado TC-M09-69 | **BLOQUEADO** | **DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA** | **APROBADO** |
| Monitoreo identifica RF-17 | No verificable | No | **Sí** |
| `id_umbral_ambiental` disponible | No | No | **Sí** |
| Rango RF-17 visible en Monitoreo | No | No | **Sí** |
| Modificación RF-17 ejecutada | No | No | **Sí** |
| RF17_AFTER verificable | No aplica | No aplica | **Sí** |
| MONITORING_AFTER usa RF17_AFTER | No verificable | No implementado | **Sí** |
| Estado de la incidencia | Hallazgo inicial / bloqueo | Defecto confirmado | **Corregido y verificado** |

### Evolución

**V1 — BLOQUEADO:** no era posible identificar qué configuración utilizaba Monitoreo.

**V2 — DESAPROBADO:** se demostró que la integración RF-17 → Monitoreo no estaba implementada; el
adaptador era un stub y el historial no exponía la configuración efectiva.

**V3 — APROBADO:** después de PR #382, Monitoreo identifica el umbral utilizado y, tras modificar
RF-17, la misma lectura histórica refleja el nuevo rango y la nueva versión.

---

## COMPARACIÓN TEST VS DEV

| Ambiente | Resultado |
|---|---|
| TEST | V3 ejecutada funcionalmente y APROBADA |
| DEV | No fue necesario ejecutar funcionalmente porque TEST aprobó; disponibilidad verificada |

---

## ORIGEN / INTERPRETACIÓN DEL RESULTADO

La V3 demuestra que la corrección del historial implementada para #298 funciona en TEST.

La modificación RF-17 persistió y el API de Monitoreo pasó a exponer los nuevos valores y la nueva
versión para la misma lectura histórica.

El HTTP 500 de sincronización Edge es un efecto colateral ya conocido y no modifica el resultado de
TC-M09-G32.

---

## INCIDENCIA

### INC-M09-107-G32 (#298)

**Estado V3: CORREGIDO Y VERIFICADO.**

La corrección incorporada mediante PR #382 fue comprobada funcionalmente.

Después de modificar RF-17, la misma lectura histórica pasó a identificar y utilizar la configuración
actualizada.

No se crea incidencia adicional.

---

## CONCLUSIÓN

**TC-M09-G32 queda APROBADO.**

Su único caso original, **TC-M09-69**, queda igualmente **APROBADO**.

La tercera evaluación demostró que una modificación de RF-17 queda disponible para Monitoreo: la
misma lectura histórica que utilizaba el rango anterior pasó a identificar el nuevo rango y la nueva
versión del umbral.

La incidencia **INC-M09-107-G32 (#298)** queda **CORREGIDA Y VERIFICADA EN V3**.

El HTTP 500 asociado a la sincronización con Edge no modifica este resultado, porque la configuración
persistió y dicho comportamiento corresponde a una incidencia ya conocida e independiente del oráculo
de TC-M09-G32.

Conforme al alcance de la evaluación, la configuración no se restauró automáticamente: el estado
posterior forma parte de la evidencia y cualquier restauración corresponde a una decisión
independiente.

---

La evaluación se realizó sin modificar código productivo ni escribir directamente en la base de
datos. Las evidencias técnicas se conservan en la carpeta del RUN_ID correspondiente.
