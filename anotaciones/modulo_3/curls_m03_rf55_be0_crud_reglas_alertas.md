# CURLs — M03 RF-55 BE-0: CRUD de reglas de alerta

Las reglas de `modulo3.reglas_alertas` ya no se cargan por SQL. Migración
`46252dbd62b4`: recurso RBAC `reglas_alertas` (id por secuencia, el código lo
ubica por nombre) y corrección de `fn_regla_alerta_versionamiento`, que fallaba
en todo UPDATE que cambiara un umbral.

Una regla **compuesta** con `tiene_ejecutar_edge: true` se propaga a sus Gateway
Edge después de cada escritura (`sincronizacion_edge` en la respuesta, mismo
contenido que `POST /{id}/sincronizar-edge`, ver `curls_m03_dev08_reglas_compuestas_edge.md`).
Las demás responden `sincronizacion_edge: null`.

## Endpoints

| Método | Ruta | RBAC `reglas_alertas` | RF |
|--------|------|------|----|
| POST | `/iot/reglas-alertas` | C — admin | RF-55, RF-57 |
| GET | `/iot/reglas-alertas?tipo_sensor=&es_activa=&es_regla_compuesta=` | R — admin, ing | RF-55, RF-57 |
| GET | `/iot/reglas-alertas/{id}` | R — admin, ing | RF-55, RF-57 |
| PUT | `/iot/reglas-alertas/{id}` | U — admin | RF-55, RF-57 |
| PATCH | `/iot/reglas-alertas/{id}/desactivar` | D — admin | RF-55, RF-57 |
| PATCH | `/iot/reglas-alertas/{id}/reactivar` | D — admin | RF-55, RF-57 |

`tipo_sensor`: `HUMEDAD`, `TEMPERATURA`, `OXIGENO`, `PH`, `AMONIACO`, `SALINIDAD`,
`LUMINOSIDAD`. `categoria_variable`: `AMBIENTAL`, `ANIMAL`, `HIDRICA`.

---

## POST — Crear

Regla RF-55.2 con fórmula del catálogo del firmware (se identifica por `nombre`,
los parámetros van en `umbrales_severidad`):

```bash
curl -s -X POST http://localhost:8000/iot/reglas-alertas \
  -H "Authorization: Bearer <TOKEN_ADMIN>" -H "Content-Type: application/json" \
  -d '{
    "nombre": "ESTRES_TERMICO",
    "descripcion": "Estrés térmico por THI",
    "tipo_sensor": "TEMPERATURA",
    "categoria_variable": "AMBIENTAL",
    "umbrales_severidad": {"THI": {"LEVE": 68, "MODERADO": 72, "CRITICO": 79}},
    "ventana_confirmacion_min": "5",
    "lectura_confirmacion_max": "3",
    "mensaje": "Estrés térmico",
    "id_finca": 1,
    "es_regla_compuesta": true,
    "tiene_ejecutar_edge": true
  }'
```

**201:** la regla (`version_regla: 1`, `fecha_actualizacion`) y `sincronizacion_edge`
(`APLICADA` / `PENDIENTE` / `NO_CONF` por Gateway). Sin Gateway Edge destino:
`PENDIENTE` sin llamar al broker.

Regla RF-55.1 (umbral simple, no va al Edge por aquí; los umbrales del Edge son RF-17):

```bash
curl -s -X POST http://localhost:8000/iot/reglas-alertas \
  -H "Authorization: Bearer <TOKEN_ADMIN>" -H "Content-Type: application/json" \
  -d '{"nombre": "PH_AGUA_FUERA_DE_RANGO", "tipo_sensor": "PH", "umbral_min": "6.5", "umbral_max": "8.5",
       "ventana_confirmacion_min": "5", "lectura_confirmacion_max": "3"}'
```

| Error | HTTP | `error_code` |
|-------|------|--------------|
| Sin `umbral_min`, `umbral_max` ni `umbrales_severidad` | 400 | `REGLA_SIN_UMBRAL` |
| `umbral_min >= umbral_max` | 400 | `RANGO_UMBRAL_INVALIDO` |
| `tiene_ejecutar_edge` en una regla simple | 400 | `REGLA_EDGE_NO_COMPUESTA` |
| `id_finca` / `id_especie` inexistente | 400 | (FK) |
| Nombre repetido | 409 | `RECURSO_DUPLICADO` |
| Rol sin C | 403 | `ACCESO_DENEGADO` |

---

## GET — Listar y obtener

```bash
curl -s "http://localhost:8000/iot/reglas-alertas?es_regla_compuesta=true&es_activa=true" \
  -H "Authorization: Bearer <TOKEN_ING>"
curl -s http://localhost:8000/iot/reglas-alertas/12 -H "Authorization: Bearer <TOKEN_ING>"
```

`404 REGLA_ALERTA_NO_ENCONTRADA` si no existe.

---

## PUT — Editar

Reemplaza la regla completa (mismos campos que el POST salvo `es_regla_compuesta`
y `tiene_ejecutar_edge`, que no cambian). `fecha_actualizacion` va tal cual la
devolvió el último GET/POST/PUT.

```bash
curl -s -X PUT http://localhost:8000/iot/reglas-alertas/12 \
  -H "Authorization: Bearer <TOKEN_ADMIN>" -H "Content-Type: application/json" \
  -d '{"nombre": "ESTRES_TERMICO", "tipo_sensor": "TEMPERATURA", "categoria_variable": "AMBIENTAL",
       "umbrales_severidad": {"THI": {"LEVE": 68, "MODERADO": 74, "CRITICO": 80}},
       "ventana_confirmacion_min": "5", "lectura_confirmacion_max": "3", "id_finca": 1,
       "fecha_actualizacion": "2026-10-28T18:46:27.151216Z"}'
```

**200:** `version_regla` sube si cambió algo de lo que recibe el Edge (lo hace el
trigger); con eso el Gateway descarta la versión vieja. Se repropaga si aplica.

| Error | HTTP | `error_code` |
|-------|------|--------------|
| `fecha_actualizacion` vieja o ausente | 412 | `CONFLICTO_CONCURRENCIA` |
| Regla inactiva | 422 | `REGLA_ALERTA_INACTIVA` |
| Validaciones del POST | 400 / 409 | ídem |

---

## PATCH — Desactivar / reactivar

```bash
curl -s -X PATCH http://localhost:8000/iot/reglas-alertas/12/desactivar -H "Authorization: Bearer <TOKEN_ADMIN>"
curl -s -X PATCH http://localhost:8000/iot/reglas-alertas/12/reactivar  -H "Authorization: Bearer <TOKEN_ADMIN>"
```

Baja lógica. Si la regla estaba en el Edge, se le envía con `es_activa: false` y
el Gateway la retira; al reactivar se le envía de nuevo. Como el nombre es único
(y el firmware identifica las fórmulas por nombre), una regla dada de baja se
reactiva en vez de crearse otra vez.

`422 REGLA_ALERTA_YA_INACTIVA` / `REGLA_ALERTA_YA_ACTIVA`.

---

## Eventos Edge (BE-1, BE-2, BE-3)

En `POST /iot/eventos-edge` (`curls_m03_cu02_procesar_enviar_inferencia.md`):

- `variables_involucradas[]` acepta y guarda `sensor`, `serial` y `sensor_id`.
- `metadata_edge.id_regla_alerta` se guarda en `eventos_edge_computing.id_regla_alerta`
  si la regla existe (si no existe se ignora; el evento no se pierde).
- La alerta generada lleva en `reglas_activadas` la regla que evaluó el Edge:
  `{"id": 12, "nombre": "ESTRES_TERMICO", "tipo": "REGLA_EDGE", "clasificacion_rf55": "DESVIACION_COMPUESTA", "version_regla": 3}`.
  Sin `metadata_edge.regla_aplicada` queda la clasificación, como antes.
