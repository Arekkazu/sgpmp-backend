# chore/rf23-docker-compose-mqtt-vars — RF-23

Rama: `chore/rf23-docker-compose-mqtt-vars` (desde `dev`). Fecha: 2026-09-03.

## Qué faltaba

`docker-compose.yml` (usado para el deploy en Dokploy) declara `MQTT_BROKER_URL`
y `MQTT_BROKER_TOKEN` en `.env.example` pero nunca las pasaba al servicio
`backend` — el bloque `environment:` del servicio se quedó desactualizado
cuando se agregó la integración MQTT real (RF-23, 2026-08-20). En local no se
nota porque `sgpmp-backend` corre por host (`uvicorn` directo leyendo `.env`),
no por Docker — el gap solo se manifiesta en un deploy vía Dokploy.

Sin esto, el contenedor de Dokploy arranca con `MQTT_BROKER_URL`/`MQTT_BROKER_TOKEN`
vacíos aunque estén cargadas como env var del panel de Dokploy — Compose solo
inyecta al contenedor lo que el `environment:` de cada servicio lista
explícitamente. `MqttHttpAdapter` no lanza en ese caso (por diseño, ver
`mqtt_http_adapter.py:46-48`): loguea error y degrada todo `configurar_remotamente`
a `estado="PENDIENTE"` de forma silenciosa — ningún test ni request revienta,
simplemente la config remota nunca llega al dispositivo.

## Qué se hizo

Una línea en `docker-compose.yml`, servicio `backend`:

```yaml
MQTT_BROKER_URL: ${MQTT_BROKER_URL}
MQTT_BROKER_TOKEN: ${MQTT_BROKER_TOKEN}
```

Nada más — no hay código de aplicación involucrado, es puro passthrough de
variables ya definidas en `.env.example`.

## Para que funcione en Dokploy

1. Cargar `MQTT_BROKER_URL` (URL pública/interna donde Dokploy expone el
   gateway HTTP de `BROKER-MQTT-SGPMP`) y `MQTT_BROKER_TOKEN` (el valor plano
   del token de servicio) como env vars del proyecto backend en el panel de
   Dokploy — mismo lugar donde ya están `SECRET_KEY`, `SMTP_*`, etc.
2. El hash SHA-256 de `MQTT_BROKER_TOKEN` debe existir en
   `modulo1.credenciales_servicio` (`nombre_servicio='broker_mqtt'`,
   `es_activo=true`) de la base que usa ese ambiente — es la misma DB que usa
   `BROKER-MQTT-SGPMP` para validar el Bearer en cada request a `/v1/commands`
   (`app/api/dependencies.py` + `app/db/repositories/credenciales.py` de ese
   repo), no una variable de entorno propia del broker.
3. Redeploy del servicio `backend` para que tome el `docker-compose.yml`
   actualizado.

No aplica a `BROKER-MQTT-SGPMP`: ese repo no tiene (ni necesita) las
variables `MQTT_BROKER_URL`/`MQTT_BROKER_TOKEN` — valida el token contra la
DB compartida en cada request, no contra config estática propia.

## Verificación

- **Cadena de auth confirmada en vivo (dev/local)**: hash SHA-256 del
  `MQTT_BROKER_TOKEN` del `.env` local coincide exacto con
  `modulo1.credenciales_servicio.hash_valor` (`id_credencial_servicio=1`,
  `es_activo=true`). `POST /v1/commands` del broker con ese token pasó la
  validación (no devolvió 401).
- **Suite de tests existente completa** (no se agregaron tests nuevos — el
  cambio es solo config de despliegue, sin código de aplicación tocado):
  - `pytest -q` (sin `TEST_DATABASE_URL`, tests de integración se saltan):
    `368 passed, 106 skipped`.
  - `TEST_DATABASE_URL=postgresql://postgres:dev@localhost:5432/pruebas pytest -q`
    (incluye `tests/integration/*`): **`474 passed, 0 failed`**.

## Fuera de alcance (explícito)
- `AUDIT_SERVICE_URL` tiene el mismo gap en `docker-compose.yml` (falta en
  `environment:` del backend) — no es de RF-23, no se tocó en esta rama.
- No se investigó el `500 Internal Server Error` que devuelve
  `BROKER-MQTT-SGPMP` para un `serial` de dispositivo inexistente en
  `/v1/commands` (debería ser un 404) — comportamiento del broker, no de este
  repo, y no bloquea la integración.
