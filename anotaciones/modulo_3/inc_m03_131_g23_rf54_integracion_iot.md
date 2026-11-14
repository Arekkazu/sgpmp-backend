# #686 — Contrato de secuencia entre Edge, broker y backend

Fecha: 2026-10-27. RF-53/RF-54, INC-M03-131-G23.

## Responsabilidades

| Pieza | Responsabilidad |
|---|---|
| Edge/AIoT | Generar buffer_sequence_id al almacenar localmente y conservarlo en reintentos; ejecutar el FIFO y gestionar el ACK/liberación del buffer |
| Broker/AIoT | Mantener la secuencia del datagrama al llamar la función existente; no descartarla ni recalcularla |
| Backend/Desarrollo | Admitirla por HTTP, conservarla en el INSERT inmutable y permitir contrastarla en la BD |
| QA | Contrastar la secuencia persistida con el datagrama y la evidencia local de envío del Edge |

RF-54 Entradas define buffer_sequence_id como Long/Integer; Fase 3 lo asigna en Edge; Fase 6 ordena el envío por secuencia y captura; Salidas §1 exige conservar la secuencia en los datos sincronizados. CA-4/Postcondiciones también expresan orden cronológico por timestamp_captura. Este cambio conserva el orden existente del batch y la evidencia original, sin redefinir esa política.

AIOT-DEV-03 P5/D10 mantiene el buffer físico en Edge y elimina modulo3.buffers. D2 conserva la función común y su firma. Conservar un metadato de la lectura sincronizada no recrea un buffer central.

## Camino HTTP existente

POST /iot/telemetria y los elementos de POST /iot/telemetria/batch admiten este campo opcional:

```json
{
  "device_id": 123,
  "sensor_id": 456,
  "serial": "SERIAL_DEL_DISPOSITIVO",
  "tipo_variable": "TEMPERATURA_AMBIENTAL",
  "valor": 22,
  "unidad": "°C",
  "timestamp_captura": "2026-10-27T15:00:00Z",
  "origen": "BUFFER_LOCAL",
  "buffer_sequence_id": 37
}
```

Los IDs son ilustrativos; deben usarse dispositivos/sensores reales del entorno aislado. El serial es identidad, no credencial. Se conserva el token de servicio vigente del broker.

El campo se valida como entero JSON, entre 0 y 9223372036854775807. Se rechazan booleanos, flotantes y cadenas con el error de entrada HTTP 400 existente. Omitido/null conserva compatibilidad y no inventa una secuencia. Cero se conserva como cero. No se exige el campo a clientes anteriores ni se incorpora otra condición de origen.

## Camino MQTT/B+ existente

El broker continúa llamando modulo3.fn_ingesta_telemetria con sus 19 entradas. Debe incorporar la secuencia del nodo en el argumento JSONB p_metadatos:

```json
{
  "buffer_sequence_id": 37
}
```

Se mantienen los otros metadatos que ya envía. La función existente copia ese JSONB a telemetrias.metadatos. No hay una migración ni nueva llamada posterior que el broker deba ejecutar.

El DTO HTTP no interviene en el camino MQTT directo. Por ello, actualizar solo el backend HTTP no demuestra que el broker real esté reenviando el campo. La prueba local SQL acredita que el destino conserva el valor que recibe; falta contrastar el productor externo. Debe conservarse la precisión de los enteros durante la serialización de cada componente.

## Consulta para QA

Usar parámetros de la herramienta SQL; no reemplazar IDs con datos compartidos sin autorización:

```sql
SELECT id_telemetria,
       id_dispositivo_iot,
       id_sensor,
       timestamp_captura,
       (metadatos ->> 'buffer_sequence_id')::bigint AS buffer_sequence_id
FROM modulo3.telemetrias
WHERE id_dispositivo_iot = :id_dispositivo
  AND origen = 'BUFFER_LOCAL'
ORDER BY timestamp_captura, id_telemetria;
```

Si la clave falta, el resultado es NULL, no cero. Una columna física nueva no es necesaria para consultar este dato JSONB. El acceso sigue sujeto al entorno, privilegios y alcance existentes; esta consulta no crea un endpoint público.

No usar el orden físico de las filas como evidencia. La secuencia es del buffer local, no globalmente única ni una nueva clave de idempotencia. Se conserva la unicidad existente por sensor/variable/captura/origen. No se reconstruyen secuencias históricas ni se modifica una lectura ya confirmada para cambiar su número.

Si secuencia y timestamp recibidos discrepan, la corrección conserva ambos originales; no renumera para aparentar FIFO. La validación integral TC-M03-037 requiere además capturar el orden de envío/ACK en el Edge y el broker reales.

## Despliegue y pendiente IoT

Desplegar el backend compatible para el camino HTTP y verificar que firmware publica el campo y broker lo conserva en p_metadatos. La generación, reinicio/reutilización de contadores, orden de envío y liberación por ACK permanecen en IoT; no se infiere una política de reinicio no especificada.

Repetir TC-M03-037 en entorno autorizado con la misma secuencia identificable en nodo, datagrama y BD. No se publicaron mensajes MQTT ni se ejecutaron escrituras oficiales en este trabajo.
