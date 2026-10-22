# CURLs — M04 DEV-15: Orquestador OTA de modelos por componente (RF-70, RF-73)

Base URL local: `http://localhost:8000`. Referencia: AIOT-DEV-03 §3 D6.

**Depende de DB-04** (`modulo4.distribuciones_ota`, columnas nuevas de `despliegues_ota`,
`versiones_modelos.firma_artefacto`, índice de despliegue vigente y permiso `(1, 44, E)`)
y de **BRK-08** en el broker (`POST /v1/ota/notify` y reenvío de `ota/<evento>`). Hasta que
DB-04 esté aplicada, el código de este PR no puede desplegarse: el ORM ya lee esas columnas.

| Método | Ruta | Auth | RF |
|---|---|---|---|
| POST | `/prediccion/ota/distribuciones` | JWT + RBAC(44, E) — Administrador | RF-70 |
| GET | `/prediccion/ota/distribuciones/{id}` | JWT + RBAC(44, R) — Admin, Ingeniero | RF-70 |
| POST | `/prediccion/ota/reportes` | Token de servicio del broker (`BROKER_SERVICE_TOKEN`) | RF-70, RF-73 |
| GET | `/prediccion/ota/artefactos/{id}?expira=&firma=` | URL firmada y temporal (sin JWT) | RF-70 |

Variables de entorno: `OTA_URL_SECRET` (HMAC de la URL), `OTA_URL_BASE` (URL pública del
backend para el nodo), `OTA_ARTEFACTOS_DIR` (raíz de `ruta_artefacto`), `OTA_URL_TTL_SEGUNDOS`
(24 h por defecto), `MQTT_BROKER_URL`/`MQTT_BROKER_TOKEN` (aviso) y `BROKER_SERVICE_TOKEN` (reportes).

---

## POST /prediccion/ota/distribuciones — Distribuir una versión

```bash
curl -s -X POST http://localhost:8000/prediccion/ota/distribuciones \
  -H "Authorization: Bearer <TOKEN_ADMIN>" -H "Content-Type: application/json" \
  -d '{
    "id_version_modelo": 35,
    "lista_dispositivos_objetivo": [38, 1, 2, 3],
    "modo_distribucion": "INMEDIATO",
    "nivel_bateria_minimo": 30,
    "tamano_fragmento_bytes": 65536,
    "max_reintentos_descarga": 3,
    "porcentaje_parcial": 25
  }'
```

- La versión debe estar **ACTIVO** y tener `ruta_artefacto` y `hash_artefacto_sha256`.
  AN-2 no está definido: se distribuye solo ACTIVO porque `trg_predicciones_version_modelo_activo`
  rechaza (P0413) las predicciones de una versión que no lo está.
- Se crea una fila `PENDIENTE` en `despliegues_ota` por nodo, con su `fase_rollout` y la versión
  que el nodo tenía de ese componente (`id_version_modelo_anterior`).
- **Rollout:** el primer nodo de la lista es el `CANARY`; luego `porcentaje_parcial` % (20–30,
  redondeado hacia arriba) es `PARCIAL`; el resto es `TOTAL`. Solo se avisa a la fase actual.
- `PROGRAMADO` exige `ventana_inicio` y `ventana_fin`.

Respuesta `201`: la distribución con sus despliegues (`fase_rollout`, `id_mensaje_notify`,
`fecha_expiracion_url`).

Aviso que el backend pide al broker (`POST {MQTT_BROKER_URL}/v1/ota/notify`, BRK-08):

```json
{
  "serial": "DISPOSITIVOCAMARONERA41",
  "id_despliegue_ota": 2,
  "tipo_modelo": "MODELO_AVES",
  "componente": "DETECTOR",
  "version": "DETECTOR v3",
  "url_descarga": "https://<OTA_URL_BASE>/prediccion/ota/artefactos/2?expira=1761000000&firma=<hmac>",
  "sha256": "<64 hex>",
  "firma": "<firma_artefacto>",
  "tamano_bytes": 300000,
  "parametros": {"fase_rollout": "CANARY", "modo_distribucion": "INMEDIATO", "tamano_fragmento_bytes": 65536,
                 "max_reintentos_descarga": 3, "nivel_bateria_minimo": 30.0, "ventana_inicio": null, "ventana_fin": null}
}
```

Los modelos sin componente (INDIVIDUAL, META) viajan con `componente: "COMPLETO"`, porque el
broker exige uno. Si el broker no publica, el despliegue queda `PENDIENTE` con el motivo.

| HTTP | `error_code` | Cuándo |
|---|---|---|
| 403 | `ACCESO_DENEGADO` | Sin permiso E sobre el recurso 44 |
| 404 | `VERSION_MODELO_NO_ENCONTRADA` | La versión no existe |
| 409 | `DESPLIEGUE_OTA_VIGENTE` | Un nodo ya tiene en curso un despliegue del mismo (tipo_modelo, componente) — DB-04 |
| 422 | `VERSION_NO_DISTRIBUIBLE` | La versión no está ACTIVO |
| 422 | `ARTEFACTO_NO_DISPONIBLE` | Sin artefacto, SHA-256 o tipo_modelo |
| 422 | `DISPOSITIVO_OTA_INVALIDO` | Algún dispositivo no existe o está inactivo |
| 503 | `OTA_NO_CONFIGURADA` | Falta `OTA_URL_SECRET` u `OTA_URL_BASE` |

Un nodo con `DETECTOR` en curso **sí** puede recibir `ANOMALIAS` al mismo tiempo (D-05).

---

## POST /prediccion/ota/reportes — Reporte del nodo (interno)

Lo llama el broker al reenviar `sgpmp/<serial>/ota/<evento>` (BRK-08). El `serial` es el del topic.

```bash
curl -s -X POST http://localhost:8000/prediccion/ota/reportes \
  -H "Authorization: Bearer <BROKER_SERVICE_TOKEN>" -H "Content-Type: application/json" \
  -d '{"serial": "DISPOSITIVOCAMARONERA41", "id_despliegue_ota": 2, "componente": "DETECTOR",
       "evento": "activated", "detalle": {"duracion_proceso_ms": 4200}}'
```

| `evento` | Despliegue | Evento RF-73 (`eventos_auditoria_m04`) |
|---|---|---|
| `status` | `EN_PROCESO`; con `detalle.pospuesto: true` (o `estado: "POSPUESTO"`) vuelve a `PENDIENTE` | `DISTRIBUCION_POSPUESTA` si se pospuso |
| `download_progress` | `EN_PROCESO`; `detalle.bytes_descargados`, `intento`, `nivel_bateria` | — |
| `integrity_ok` | `EN_PROCESO`, `resultado_validacion_hash = true` | `MODELO_DISTRIBUIDO_EDGE` |
| `activated` | `EXITOSO` (`detalle.duracion_proceso_ms`) | `MODELO_ACTIVADO_EDGE` |
| `rollback` | `FALLIDO`, `rollback_ejecutado = true` | `DISTRIBUCION_FALLIDA` (ERROR) |
| `critical_failure` | `FALLIDO`; con `detalle.causa = HASH_INVALIDO` marca el hash inválido | `DISTRIBUCION_FALLIDA` (CRITICAL) |

Los eventos se registran con `tipo_actor = DISPOSITIVO_EDGE`, `id_sistema = <serial>` y
`entidad_referencia = despliegue_ota`.

**Avance del rollout:** cuando todos los nodos de la fase actual reportan `activated`, la
distribución pasa a la siguiente y se avisa a sus nodos (`fase_avanzada_a` en la respuesta); sin
más fases queda `COMPLETADA`. Un `rollback` o `critical_failure` la deja `DETENIDA`.

Un reporte sobre un despliegue ya terminado responde `200` con `sin_cambios: true` (QoS 1 del
nodo puede repetir mensajes).

| HTTP | `error_code` | Cuándo |
|---|---|---|
| 401 | `TOKEN_SERVICIO_INVALIDO` | Sin token del broker o no coincide |
| 403 | `DESPLIEGUE_OTA_DE_OTRO_NODO` | El serial no es el del nodo del despliegue |
| 404 | `DESPLIEGUE_OTA_NO_ENCONTRADO` | El despliegue no existe |
| 422 | `COMPONENTE_OTA_INCORRECTO` | El componente no coincide con el del despliegue |
| 503 | `TOKEN_SERVICIO_NO_CONFIGURADO` | Falta `BROKER_SERVICE_TOKEN` |

---

## GET /prediccion/ota/artefactos/{id} — Descarga con URL firmada

La URL llega en `url_descarga` del aviso. Firma: HMAC-SHA256 de `"<id_despliegue>:<expira>"`
con `OTA_URL_SECRET`. Vence a las `OTA_URL_TTL_SEGUNDOS` o al fin de la ventana, lo que sea más tarde.

```bash
curl -s -o detector_v3.tflite "http://localhost:8000/prediccion/ota/artefactos/2?expira=1761000000&firma=<hmac>"
# Reanudar desde el byte 100000 (206 Partial Content)
curl -s -H "Range: bytes=100000-" -o resto.bin "http://localhost:8000/prediccion/ota/artefactos/2?expira=1761000000&firma=<hmac>"
```

| HTTP | `error_code` | Cuándo |
|---|---|---|
| 401 | `URL_DESCARGA_INVALIDA` | Firma alterada o URL vencida |
| 404 | `ARTEFACTO_NO_DISPONIBLE` | El archivo no existe o la ruta sale de `OTA_ARTEFACTOS_DIR` |
| 410 | `DESPLIEGUE_OTA_TERMINADO` | El despliegue ya terminó |

---

## GET /prediccion/ota/distribuciones/{id} — Estado del rollout

```bash
curl -s http://localhost:8000/prediccion/ota/distribuciones/1 -H "Authorization: Bearer <TOKEN_ADMIN>"
```

Respuesta `200`: `fase_rollout`, `estado_distribucion` (`EN_CURSO`, `COMPLETADA`, `DETENIDA`)
y cada despliegue con su estado. Errores: 401, 403, 404 `DISTRIBUCION_OTA_NO_ENCONTRADA`.
