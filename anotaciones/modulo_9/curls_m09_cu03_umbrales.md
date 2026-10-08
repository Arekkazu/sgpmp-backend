# CURLs — M09 CU03: Configurar Umbrales y Alertas Ambientales

Base URL local: `http://localhost:8000`
Reemplazar `<TOKEN>` por el JWT obtenido en `/sesiones/login`.

---

## Variables ambientales disponibles

Catálogo predefinido en `modulo9.variables_ambientales`. Consultar directamente en BD.
Ejemplo de IDs habituales: temperatura (id=1), humedad (id=2), pH (id=3).

---

## Flujo A — Registrar umbral ambiental con niveles de alerta

Los 3 niveles deben ser: `normal`, `precaucion`, `critico`.
Los niveles deben ser **contiguos** y cubrir exactamente `[valor_min, valor_max]`.

```bash
curl -X POST http://localhost:8000/configuracion/umbrales \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "id_especie": 1,
    "id_variable_ambiental": 1,
    "valor_min": 15.0,
    "valor_max": 40.0,
    "niveles": [
      { "nivel": "normal",    "limite_inferior": 18.0, "limite_superior": 28.0 },
      { "nivel": "precaucion","limite_inferior": 28.0, "limite_superior": 35.0 },
      { "nivel": "critico",   "limite_inferior": 15.0, "limite_superior": 18.0 }
    ]
  }'
```

**Nota:** El orden de los niveles en el arreglo no importa. El sistema los ordena internamente.

Respuesta esperada `201` (solo si el Nodo Edge confirmó `APLICADA` — ver nota):
```json
{
  "id_umbral_ambiental": 1,
  "id_especie": 1,
  "id_variable_ambiental": 1,
  "unidad_medida": "°C",
  "valor_min": 15.0,
  "valor_max": 40.0,
  "es_activo": true,
  "fecha_actualizacion": null,
  "niveles": [
    { "nivel": "critico",    "limite_inferior": 15.0, "limite_superior": 18.0 },
    { "nivel": "normal",     "limite_inferior": 18.0, "limite_superior": 28.0 },
    { "nivel": "precaucion", "limite_inferior": 28.0, "limite_superior": 35.0 }
  ],
  "estado_sincronizacion": "APLICADA",
  "fecha_ultima_sincronizacion": "2026-09-19T12:00:00Z",
  "motivo_fallo_sincronizacion": null
}
```

**INC-M09-104-G29 (RF-17):** después de guardar, el umbral se propaga a cada Gateway Edge
activo de las áreas activas de la especie, por el broker MQTT (`POST /v1/commands` con
`origen: "umbral"`; el broker espera hasta 30 s el `ACK_UMBRAL` de cada Edge). Los
resultados se consolidan en un único `estado_sincronizacion` (`PENDIENTE` / `APLICADA` /
`NO_CONF`), que queda guardado **antes** de responder (dos commits separados). La
respuesta puede tardar hasta ~35 s mientras se espera el ACK.

**TC-M09-58-G22 (#459) — cuándo responde 201 y cuándo 500:**

| Resultado de los Gateway Edge | `estado_sincronizacion` | Respuesta |
|---|---|---|
| todos confirmaron | `APLICADA`, con `fecha_ultima_sincronizacion` | `201` (alta) / `200` (edición) |
| alguno desconectado del broker (TC-M09-63): el Edge avisó su desconexión y el broker no publica | `PENDIENTE` ("Pendiente de Sincronización"), con el motivo en `motivo_fallo_sincronizacion` | `500` `FALLO_SINCRONIZACION_EDGE` |
| alguno no confirmó (sin ACK en 30 s, broker caído o con error) | `NO_CONF` | `500` `FALLO_SINCRONIZACION_EDGE` |
| la especie no tiene Gateway Edge, o el broker no está configurado en el ambiente (no hubo intento) | `PENDIENTE`, con el motivo | `201` / `200` |

Al **editar**, el umbral queda `PENDIENTE` desde el primer commit, hasta que el resultado
de la propagación lo reemplace.

Los dos casos con `500` son el flujo alterno "Error de sincronización con el Nodo Edge" del RF-17
(el Edge sigue con el umbral anterior), que exige responder:

```
HTTP 500
{
  "error_code": "FALLO_SINCRONIZACION_EDGE",
  "message": "Configuración guardada en la base de datos, pero falló la actualización de los nodos Edge. Es posible que las alertas en campo sigan operando con los valores anteriores hasta que se restablezca la conexión."
}
```

Contrato completo (payload, ACK, cómo simular el Edge con `mosquitto_pub`):
`INTEGRACION_DISPOSITIVOS_RF17.md` del repo `BROKER-MQTT-SGPMP`. Ver también
`anotaciones/modulo_9/inc_m09_104_g29_sincronizacion_edge_umbrales.md`.

Errores posibles:
- `500` — el Nodo Edge no confirmó la propagación (`NO_CONF`) o está desconectado (`PENDIENTE`, TC-M09-63), tras haber guardado — ver arriba
- `422` — especie inactiva (FA-01)
- `404` — variable ambiental no existe o inactiva
- `409` — ya existe umbral para esa especie-variable (FA-02)
- `400` — valor_min >= valor_max (FA-03)
- `400` — valores fuera del rango físico de la variable (FA-04)
- `400` — solapamiento o cobertura incompleta de niveles (FA-05)
- `400` — algún nivel fuera del rango general (FA-08)
- `403` — sin permiso C sobre umbrales_ambientales

---

## Flujo C — Consultar umbrales por especie

```bash
curl -X GET "http://localhost:8000/configuracion/umbrales?id_especie=1" \
  -H "Authorization: Bearer <TOKEN>"
```

Solo activos:
```bash
curl -X GET "http://localhost:8000/configuracion/umbrales?id_especie=1&solo_activas=true" \
  -H "Authorization: Bearer <TOKEN>"
```

Respuesta esperada `200`:
```json
{
  "total": 2,
  "items": [
    {
      "id_umbral_ambiental": 1,
      "id_especie": 1,
      "id_variable_ambiental": 1,
      "unidad_medida": "°C",
      "valor_min": 15.0,
      "valor_max": 40.0,
      "es_activo": true,
      "fecha_actualizacion": null,
      "niveles": [...]
    }
  ]
}
```

---

## Flujo B — Editar umbral ambiental

`fecha_actualizacion` debe ser el valor exacto devuelto por el sistema (concurrencia optimista).
Enviar `null` si el umbral nunca ha sido editado.

```bash
curl -X PATCH http://localhost:8000/configuracion/umbrales/1 \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "valor_min": 10.0,
    "valor_max": 42.0,
    "niveles": [
      { "nivel": "critico",    "limite_inferior": 10.0, "limite_superior": 15.0 },
      { "nivel": "normal",     "limite_inferior": 15.0, "limite_superior": 30.0 },
      { "nivel": "precaucion", "limite_inferior": 30.0, "limite_superior": 42.0 }
    ],
    "fecha_actualizacion": null
  }'
```

Errores posibles:
- `404` — umbral no existe
- `422` — umbral inactivo
- `412` — conflicto de concurrencia (FA-09)
- `400` — rango inválido o fuera de límites físicos
- `400` — solapamiento de niveles (FA-05)
- `500` — el Nodo Edge no confirmó la re-propagación (`NO_CONF`), igual que en el Flujo A

Igual que en el Flujo A, la edición también dispara un intento de re-propagación hacia
el Nodo Edge (INC-M09-104-G29): el `200` llega con `APLICADA` o `PENDIENTE` (TC-M09-58-G22, #459)
y el `500` solo si el intento falló.

---

## Flujo D — Desactivar umbral ambiental

```bash
curl -X PATCH http://localhost:8000/configuracion/umbrales/1/desactivar \
  -H "Authorization: Bearer <TOKEN>"
```

Errores posibles:
- `404` — umbral no existe
- `422` — umbral ya inactivo

---

## Tabla de rangos físicos por variable (valores de referencia)

| Variable       | unidad | valor_fisico_min | valor_fisico_max |
|----------------|--------|-----------------|-----------------|
| Temperatura    | °C     | 0               | 50              |
| Humedad        | %      | 0               | 100             |
| pH             | pH     | 0               | 14              |

Los límites reales se leen de `modulo9.variables_ambientales.valor_fisico_min/max`.

---

## Notas

- La `unidad_medida` del umbral se toma automáticamente de la variable ambiental al registrar.
- Los 3 niveles son obligatorios y su unión debe cubrir exactamente `[valor_min, valor_max]` sin huecos ni solapamientos.
- Para probar con Swagger: `http://localhost:8000/docs` → sección "Configuración - Umbrales Ambientales".
