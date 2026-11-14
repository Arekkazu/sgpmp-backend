# RF-54 E9 — Contrato de reloj e integración IoT · INC-M03-132-G30

Fecha: 2026-10-27. Issue: #687. Backend implementado y validado localmente; firmware, broker y despliegue oficial pendientes de validación conjunta.

## Señal enviada por lectura

`POST /iot/telemetria` y cada elemento de `POST /iot/telemetria/batch` admiten `reloj_sincronizado` opcional: true, false, null o ausente. Cuando se informa un booleano, representa el estado del reloj al capturar esa lectura, incluso si luego se almacena en el buffer. El broker debe preservar ese valor original al sincronizar; no sustituirlo por el estado actual del nodo.

Ejemplo parcial de la ampliación del payload existente:

```json
{"reloj_sincronizado": false}
```

El DTO exige booleano estricto: 0, 1 y las cadenas “true”/“false” no son válidos. Se conserva el manejo HTTP de validación existente (400 VAL_ENTRADA).

Para integraciones que llaman directamente a la función SQL de ingesta, transmitirlo como `p_metadatos.reloj_sincronizado`. Se conservan los 19 argumentos y el resultado de la función. Un valor no booleano ni null produce ERROR_ESTRUCTURA con la bitácora existente; no inserta telemetría. El camino HTTP traslada el campo al mismo metadato.

## Prioridad y evidencia persistida

| Evidencia disponible | Fuente | Decisión |
|---|---|---|
| Booleano de la lectura | LECTURA | Prevalece sobre cualquier heartbeat |
| Campo ausente o null; existe heartbeat | HEARTBEAT | Último recibido del mismo dispositivo al instante de la ingesta |
| Sin señal ni heartbeat | SIN_EVIDENCIA | Estado sincronizado desconocido; no se marca desincronización sin evidencia |

El heartbeat se selecciona por fecha_recepcion descendente y, en empate, id_heartbeat descendente, sin tomar recepciones posteriores al instante de procesamiento. No se exige que su fecha de captura sea anterior a la lectura: para buffer se usa exclusivamente como estado conocido al ingerir, según decisión confirmada por el usuario.

El backend escribe `telemetrias.reloj_desincronizado` antes del INSERT y genera `metadatos.rf53_reloj` con:

- reloj_sincronizado (booleano o null), reloj_desincronizado y codigo (TIME_DESYNC o null).
- fuente, id_heartbeat y fecha_recepcion_heartbeat (estos dos null si no se usó heartbeat).
- instante_decision y alcance: CAPTURA_REPORTADA, ESTADO_CONOCIDO_AL_INGERIR o SIN_EVIDENCIA.

El snapshot es calculado por el servidor. No debe enviarse como evidencia fabricada por el cliente. No requiere una columna nueva ni modifica la respuesta de recibo de ingesta. La columna original y el metadato son consultables en persistencia; la evaluación RF-62 expone el flag y la justificación por su contrato existente.

## Consumo de calidad

Tanto el procesamiento posterior al commit como POST /iot/calidad/{id}/evaluar reciben la marca persistida y su snapshot. Cuando hay TIME_DESYNC:

- flags_detectados.reloj_desincronizado = {activo: true, codigo: TIME_DESYNC}.
- parametros_aplicados.reloj_rf53 conserva la evidencia original.
- parametros_aplicados.restriccion_temporal documenta RF54_E9, ambas aptitudes false y descuento_indice = 0.
- La evaluación vigente de telemetria_calidad tiene apto_para_ia=false y apto_para_nic41=false. El índice y la clasificación siguen el cálculo existente: APTO con ambas aptitudes false es posible y deliberado.

Los consumidores deben consultar las aptitudes oficiales de la evaluación vigente; las columnas legacy de telemetrias no se actualizan (DEV-02). Un heartbeat posterior sincronizado afecta nuevas lecturas; no elimina la restricción de una lectura antigua, tampoco al reevaluarla. No hay reconstrucción retroactiva de lecturas sin evidencia.

## Límites y entrega pendiente

Se mantienen los rechazos existentes de captura futura y buffer mayor de 72 horas. TIME_DESYNC no convierte una petición temporalmente rechazada en una lectura aceptada. No se agrega un estado al enum de estado_calidad ni una penalización estadística nueva.

IoT debe detectar y conservar la señal del reloj en firmware/buffer y hacer que el broker la transmita. Backend no realiza la resincronización NTP del nodo. El fallback ya cubre clientes antiguos que únicamente envían heartbeat, con el alcance limitado indicado arriba.

Antes de QA conjunta: desplegar la migración c687132a0270 y el backend; acordar versiones de firmware/broker; usar dispositivo y datos aislados; comparar señal original, snapshot persistido y aptitudes RF-62. Probar desincronización, recuperación y sincronización de buffer con señal histórica distinta del heartbeat actual. La validación local no acredita el firmware ni un despliegue oficial.
