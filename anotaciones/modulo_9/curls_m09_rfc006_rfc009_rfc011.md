# CURLs — M09: RFC-006 (RF-24 v1.1), RFC-009 (RF-15/RF-20 v1.1) y RFC-011 (RF-21 v2.0 / RF-22 v1.2)

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT obtenido en `/sesiones/login`.
Resumen de la implementación y de lo que quedó fuera de alcance: `anotaciones/implementacion_rfc006_rfc009_rfc011.md`.

---

## RFC-006 — RF-24 v1.1: auditoría de calibraciones rechazadas

El contrato del endpoint no cambia. Lo nuevo: **cada rechazo deja un evento en el historial de RF-10**
(`modulo1.eventos`, `tipo_evento = 29 CALIBRACION_RECHAZADA`, `resultado = FALLIDO`, `modulo = MODULO9`,
con IP, user-agent, sesión y hash SHA-256). Es best-effort: si esa escritura falla, la respuesta
conserva su 4xx (no se vuelve 500).

### Intento rechazado (ej. sensor inexistente)

```bash
curl -X POST http://localhost:8000/configuracion/sensores/99999/calibrar \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_dispositivo_iot": 1,
    "id_infraestructura": 1,
    "valor_referencia": 25.5,
    "fecha_calibracion": "2026-10-05T10:00:00Z"
  }'
```

Respuesta `404` `SENSOR_NO_ENCONTRADO` (sin cambios) **y** un evento FALLIDO en la auditoría.

Rechazos que quedan auditados (todos con su código HTTP de siempre):
- `403` — rol sin permiso C sobre `sensores` (recurso 12) — se audita en la dependencia del endpoint, antes del use case
- `404` — `DISPOSITIVO_NO_ENCONTRADO` / `SENSOR_NO_ENCONTRADO`
- `422` — `DISPOSITIVO_INACTIVO` / `SENSOR_DISPOSITIVO_INVALIDO`
- `400` — `SENSOR_AREA_INVALIDA` / `VALOR_CALIBRACION_INVALIDO` (no numérico) / `VALOR_FUERA_DE_RANGO`

No se audita el `401` (sin token): no hay usuario atribuible.

### Consultar los rechazos auditados (Administrador, RF-10)

```bash
curl -X GET "http://localhost:8000/auditoria/?tipo_evento=29" \
  -H "Authorization: Bearer <TOKEN>"
```

Cada evento trae en `detalle`: `operacion=CALIBRACION_SENSOR`, `id_sensor`, `id_dispositivo_iot`,
`id_infraestructura`, `codigo_http`, `codigo_error`, `motivo`, `ip`, `user_agent`.

---

## RFC-009 — RF-15: familia de modelo de IA de la especie

Campo nuevo opcional `tipo_modelo` (uno de los 5 modelos asignables; `MODELO_RIESGO_CONTAGIO` no
aplica). Es la base de la coherencia de RF-20. En la edición, omitirlo conserva el valor; enviar
`null` lo borra.

```bash
curl -X PATCH http://localhost:8000/configuracion/especies/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Pollo de engorde",
    "tipo_modelo": "MODELO_AVES",
    "fecha_actualizacion": "<fecha_actualizacion actual>"
  }'
```

Errores posibles (además de los de RF-15):
- `400` `VAL_ENTRADA` — `tipo_modelo` fuera de los 5 valores asignables

---

## RFC-009 — RF-20 v1.1: especie y modelo de IA del área, reactivación

### Registrar área con especie y modelo

`especie_id` es **obligatorio**; `tipo_modelo_asignado` es opcional y debe coincidir con la familia de
la especie.

```bash
curl -X POST http://localhost:8000/configuracion/infraestructuras \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_infraestructura": "Galpón Norte",
    "tipo_area": "Galpón",
    "superficie": 250,
    "finca_id": 1,
    "especie_id": 1,
    "tipo_modelo_asignado": "MODELO_AVES"
  }'
```

Respuesta esperada `201` (campos nuevos al final):
```json
{
  "id_infraestructura": 15,
  "nombre_infraestructura": "Galpón Norte",
  "tipo_area": "Galpón",
  "superficie": "250.00",
  "id_finca": 1,
  "descripcion_infraestructura": null,
  "es_activo": true,
  "fecha_actualizacion": null,
  "especie_id": 1,
  "tipo_modelo_asignado": "MODELO_AVES"
}
```

Errores posibles (nuevos):
- `422` `ESPECIE_INVALIDA` — "Especie inválida: la especie seleccionada no existe o está inactiva."
- `422` `INCOHERENCIA_ESPECIE_MODELO` — el modelo no es la familia de la especie, la especie no tiene
  familia configurada, o se envió `MODELO_RIESGO_CONTAGIO`
- `400` `VAL_ENTRADA` — falta `especie_id` o `tipo_modelo_asignado` no es uno de los 6 valores

### Editar área (cambio de especie)

```bash
curl -X PATCH http://localhost:8000/configuracion/infraestructuras/15 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_infraestructura": "Galpón Norte",
    "tipo_area": "Galpón",
    "superficie": 250,
    "especie_id": 2,
    "tipo_modelo_asignado": null,
    "fecha_actualizacion": "<fecha_actualizacion actual>"
  }'
```

Errores posibles (nuevos, además de los de RF-20):
- `422` `AREA_CON_ACTIVOS_DE_OTRA_ESPECIE` — "Operación denegada: el área '[NOMBRE]' tiene [M] activos
  biológicos de la especie '[ESPECIE]'. Traslade o desvincule los activos antes de cambiar la especie."
  (se evalúa si cambia la especie o el modelo; cuenta activos que no estén CERRADO ni BAJA)
- `422` `ESPECIE_INVALIDA` — solo si se **cambia** a una especie inexistente o inactiva; conservar una
  especie que se desactivó después no bloquea la edición
- `422` `INCOHERENCIA_ESPECIE_MODELO`

### Reactivar área inactiva (Flujo F)

Solo Administrador (acción D=4 sobre el recurso 10, la misma que desactivar, igual que en fincas).
Se audita como `UPDATE`.

```bash
curl -X PATCH http://localhost:8000/configuracion/infraestructuras/15/reactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta `200` con el área y `"es_activo": true`.

Errores posibles:
- `404` `INFRAESTRUCTURA_NO_ENCONTRADA`
- `422` `INFRAESTRUCTURA_YA_ACTIVA`
- `422` `FINCA_INACTIVA_O_INEXISTENTE` — no se reactiva un área de una finca inactiva
- `403` — rol sin permiso D sobre `infraestructuras`

---

## RFC-011 — RF-21 v2.0 / RF-22 v1.2: cámara (nodo de visión)

### Consultar el catálogo de tipos (ahora con categoría)

```bash
curl -X GET http://localhost:8000/configuracion/tipos-dispositivo-iot \
  -H "Authorization: Bearer <TOKEN>"
```

Cada tipo trae `"categoria": "SENSOR" | "CAMARA"`. La migración siembra `CAMARA_VISION` (categoría CAMARA).

### Registrar una cámara

La categoría sale del tipo; `resolucion`, `fps` y `area_cobertura_m2` son obligatorios si es CAMARA.
Varias cámaras pueden ir a la misma área (N:1): la asociación cámara→área es su `id_infraestructura`.

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "serial": "CAM-GALPON-01",
    "descripcion": "Camara cenital galpon norte",
    "id_infraestructura": 15,
    "id_tipo_dispositivo": <id de CAMARA_VISION>,
    "resolucion": "1920x1080",
    "fps": 25,
    "area_cobertura_m2": 80.5
  }'
```

Respuesta `201` con `resolucion`, `fps` y `area_cobertura_m2`.

Errores posibles (nuevos):
- `400` `ATRIBUTOS_VISION_INVALIDOS` (`field` = el atributo) — "Error de validación: La cámara requiere
  resolución (formato ANCHOxALTO), fps (1–60) y área de cobertura (m²) válidos. Verifique el atributo '[CAMPO]'."

Para un tipo de categoría SENSOR, esos tres campos se **ignoran** si llegan (no se persisten, sin error).

### Una cámara no admite sensores escalares

```bash
curl -X POST http://localhost:8000/configuracion/dispositivos-iot/<id_camara>/sensores \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"nombre": "Temperatura", "categoria": "TEMPERATURA"}'
```

Respuesta `422` `CAMARA_SIN_SENSORES`.
