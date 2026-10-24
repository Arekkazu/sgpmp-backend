# CURLs — M03 DEV-08: Propagar reglas compuestas al Gateway Edge (RF-55, RF-57)

Una regla compuesta de `modulo3.reglas_alertas` (THI, síndrome respiratorio,
riesgo hídrico...) se envía a los Gateway Edge de su finca y especie por el
broker, con `origen: "regla_compuesta"` (BRK-05 de `BROKER-MQTT-SGPMP`:
`tipo_comando = REGLA_COMPUESTA`, confirmación `ACK_REGLA`). Es el mismo patrón
que los umbrales de RF-17. El veredicto de cada Gateway queda en
`modulo3.sincronizaciones_reglas_edge` (migración `e3b8c1d9f702`, ver
`dev08_gaps_bd_rf55_rf57.md`).

Hoy no hay CRUD de reglas (se cargan por SQL): la propagación se dispara con el
endpoint de sincronizar. Cuando exista el CRUD, su caso de uso debe llamar a
`SincronizarReglaEdgeUseCase` después de su commit.

## Endpoints

| Método | Ruta | Auth | RF |
|--------|------|------|----|
| POST | `/iot/reglas-alertas/{id}/sincronizar-edge` | JWT + RBAC(65, E) — admin + ing | RF-55, RF-57 |
| GET | `/iot/reglas-alertas/{id}/sincronizacion-edge` | JWT + RBAC(65, R) — admin + ing | RF-55, RF-57 |

---

## POST /iot/reglas-alertas/{id}/sincronizar-edge — Propagar la regla

Se resuelven los Gateway Edge activos de las áreas activas de la finca de la
regla (si tiene `id_finca`) y de su especie (si tiene `id_especie`, por el
`id_especie` del área o por activos biológicos vivos). Una regla sin finca ni
especie es global. A cada Gateway se le envía:

```json
{
  "origen": "regla_compuesta",
  "serial": "EDGE-001",
  "id_regla_alerta": 11,
  "version_regla": 2,
  "es_activa": true,
  "regla": {
    "nombre": "THI_ESTRES_CALORICO",
    "descripcion": "THI = f(temperatura, humedad)",
    "tipo_sensor": "TEMPERATURA",
    "categoria_variable": "AMBIENTAL",
    "umbral_min": "68",
    "umbral_max": "79",
    "umbrales_severidad": {"ALTA": 75, "CRITICA": 79},
    "ventana_confirmacion_min": "5",
    "lectura_confirmacion_max": "3",
    "mensaje": "Estrés calórico (THI)",
    "id_finca": 3,
    "id_especie": 4,
    "prevalece_sobre_regla_simple": true
  }
}
```

`version_regla` la sube el trigger `trg_aux_02_version_regla_alerta` y le
permite al Edge descartar una versión vieja que llegue tarde. Con
`es_activa: false` el Edge retira la regla. `prevalece_sobre_regla_simple`
corresponde a RF-57 E14/E15.

### Flujo principal — el Gateway confirma con ACK_REGLA

```bash
curl -s -X POST http://localhost:8000/iot/reglas-alertas/11/sincronizar-edge \
  -H "Authorization: Bearer <TOKEN_ING>"
```

**Respuesta esperada (200):**
```json
{
  "id_regla_alertas": 11,
  "version_regla": 1,
  "estado": "APLICADA",
  "mensaje": "Confirmada por 1 Gateway Edge.",
  "nodos": [
    {
      "id_dispositivo_iot": 38,
      "serial": "DISPOSITIVOCAMARONERA41",
      "version_regla": 1,
      "estado_sincronizacion": "APLICADA",
      "mensaje": "El dispositivo confirmó la recepción de la configuración.",
      "intentos_sincronizacion": 1,
      "fecha_ultimo_intento": "2026-10-19T05:21:20Z",
      "fecha_aplicacion": "2026-10-19T05:21:20Z"
    }
  ]
}
```

### Flujo alterno — Gateway apagado

El broker sabe que el Gateway está desconectado y no publica: el nodo queda
`PENDIENTE` y el Edge sigue con la versión anterior. Se responde **200**, porque
el estado es justamente lo que se consulta. Se reintenta con el mismo endpoint.

```json
{
  "estado": "PENDIENTE",
  "mensaje": "DISPOSITIVOCAMARONERA41: El dispositivo está desconectado; el comando no se publicó.",
  "nodos": [{"serial": "DISPOSITIVOCAMARONERA41", "estado_sincronizacion": "PENDIENTE", "intentos_sincronizacion": 2}]
}
```

### Consolidación del estado de la regla

| Resultados por Gateway | `estado` |
|---|---|
| todos `APLICADA` | `APLICADA` |
| alguno `NO_CONF` (broker caído, error HTTP, sin `ACK_REGLA`) | `NO_CONF` |
| ninguno falló, alguno `PENDIENTE` (desconectado o sin broker en el ambiente) | `PENDIENTE` |
| la regla no tiene Gateway Edge destino (`nodos: []`) | `PENDIENTE` |

### Errores posibles

| HTTP | `error_code` | Cuándo |
|------|--------------|--------|
| 401 | `TOKEN_REQUERIDO` / `TOKEN_REVOCADO` | Sin token o token inválido |
| 403 | `ACCESO_DENEGADO` | Rol sin permiso E sobre el recurso 65 (ej. Productor) |
| 404 | `REGLA_ALERTA_NO_ENCONTRADA` | La regla no existe |
| 422 | `REGLA_NO_COMPUESTA` | La regla es simple (`es_regla_compuesta = false`) |
| 422 | `REGLA_SIN_EJECUCION_EDGE` | La regla no está marcada para el Edge (`tiene_ejecutar_edge = false`) |

---

## GET /iot/reglas-alertas/{id}/sincronizacion-edge — Estado por Gateway

```bash
curl -s http://localhost:8000/iot/reglas-alertas/11/sincronizacion-edge \
  -H "Authorization: Bearer <TOKEN_ING>"
```

Misma respuesta que el POST, con el último veredicto guardado de cada Gateway.
Si la regla cambió después del último envío (`version_regla` de la regla mayor
que la del nodo), el `estado` consolidado es `PENDIENTE` aunque el nodo haya
confirmado la versión anterior:

```json
{
  "id_regla_alertas": 11,
  "version_regla": 2,
  "estado": "PENDIENTE",
  "mensaje": "La regla va en la versión 2; sin sincronizar: DISPOSITIVOCAMARONERA41.",
  "nodos": [{"serial": "DISPOSITIVOCAMARONERA41", "version_regla": 1, "estado_sincronizacion": "APLICADA"}]
}
```

Errores: 401, 403 (`ACCESO_DENEGADO`, permiso R sobre el recurso 65), 404 (`REGLA_ALERTA_NO_ENCONTRADA`).
