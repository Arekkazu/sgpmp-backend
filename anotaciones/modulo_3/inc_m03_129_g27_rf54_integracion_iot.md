# #684 · Ampliación confirmada de D10 — BUFFER_CAPACITY_WARNING

Fecha: 2026-10-27. RF-54 / RF-60 / RF-63; DEV-11 y AIOT-08. La ampliación fue confirmada por el usuario para esta corrección; el acuerdo descargado conserva su versión original.

## Responsabilidades

- Firmware/Edge mide la ocupación real y emite avisos según su umbral configurable. Debe reportar también al cruzar 95 % para permitir el escalamiento.
- Broker admite BUFFER_CAPACITY_WARNING, extrae serial del tópico y reenvía al backend con el token de servicio existente.
- Backend valida el sobre, registra/consolida la alerta técnica y conserva su auditoría. La cola física sigue en Edge.

## Publicación del nodo

Tópico: sgpmp/<serial>/status.

```json
{
  "tipo_mensaje": "EVENTO_BUFFER",
  "evento": "BUFFER_CAPACITY_WARNING",
  "porcentaje_ocupacion": 80,
  "politica_aplicada": null,
  "cantidad_datos_afectados": 0,
  "timestamp_evento": "2026-10-27T15:00:00Z"
}
```

Al pasar al 95 %, se envía otro evento del mismo tipo con porcentaje_ocupacion=95 y su timestamp real. Es un aviso preventivo: cantidad_datos_afectados puede ser cero. La política es opcional y puede indicar la política configurada; no se declara una pérdida de datos que no ocurrió.

## Reenvío del broker

```http
POST /iot/eventos-buffer
Authorization: Bearer <token_servicio_broker>
Content-Type: application/json
```

```json
{
  "serial": "GW-001",
  "evento": "BUFFER_CAPACITY_WARNING",
  "porcentaje_ocupacion": 80,
  "politica_aplicada": null,
  "cantidad_datos_afectados": 0,
  "timestamp_evento": "2026-10-27T15:00:00Z"
}
```

Porcentaje finito entre 0 y 100; cantidad no negativa; timestamp de evento real. Se recomienda zona explícita como en D10. La normalización compartida vigente acepta también un datetime sin zona como UTC; no se introduce otro rechazo.

## Respuestas y consulta

Primer aviso, HTTP 201:

```json
{"id_alerta": 41, "es_duplicado": false, "tipo_alerta_tecnica": "BUFFER_CAPACITY_WARNING", "severidad": "LEVE"}
```

Reporte posterior al 95 %, HTTP 201:

```json
{"id_alerta": 41, "es_duplicado": true, "tipo_alerta_tecnica": "BUFFER_CAPACITY_WARNING", "severidad": "CRITICO"}
```

El ID es ilustrativo. Mientras el incidente siga ACTIVA/EN_ATENCION, se conserva el ID y la severidad máxima alcanzada; los avisos se cuentan en frecuencia_evento. D10 no incluye un identificador de evento para distinguir retransmisión de nueva ocurrencia.

GET /iot/alertas-tecnicas permite al Administrador y al Ingeniero autorizado identificar tipo_variable=BUFFER_CAPACITY_WARNING y su severidad. El Productor no accede a esta bandeja y el listado operativo excluye las alertas técnicas. Se conserva el filtro por finca.

Se mantienen 401 por token ausente/inválido, 400 VAL_ENTRADA por entrada inválida y 404 por serial desconocido. La creación/consolidación conserva el schema y HTTP 201 existentes.

## Compatibilidad y límites

OVERFLOW y DATA_CORRUPTION mantienen sus mensajes y severidades. El backend no convierte automáticamente un porcentaje del heartbeat en EVENTO_BUFFER; se requiere este aviso por el canal de control. #681 / PR #806 consulta un snapshot de ocupación y cumple otra parte del contrato.

estado_buffer CRITICO, BUFFER_ACTIVO del dispositivo y estado_alerta ACTIVA/EN_ATENCION son conceptos diferentes. Esta corrección escala severidad de una alerta y no sustituye esos estados.

Los metadatos de la alerta describen su primera ocurrencia. Cada nuevo aviso deja su porcentaje/timestamp y la severidad efectiva en RF-63 bajo el comportamiento best-effort existente. No se cierra automáticamente un incidente al disminuir la ocupación: se conserva el flujo de atención vigente.

## Validación conjunta pendiente

1. Publicar el aviso real al 80 % y comprobar alerta LEVE mediante JWT de Administrador/Ingeniero asignado.
2. Publicar el aviso real al 95 % y comprobar el mismo ID con severidad CRITICO.
3. Repetir avisos y comprobar consolidación, concurrencia e historial sin estados ficticios.
4. Verificar acceso del Productor y de un Ingeniero de otra finca.
5. Contrastar auditoría, timestamps y reinicio/reenvío del dispositivo en un entorno aislado autorizado.

Las pruebas backend locales no acreditan estos pasos sobre firmware/MQTT reales. No se realizaron escrituras en la base oficial.
