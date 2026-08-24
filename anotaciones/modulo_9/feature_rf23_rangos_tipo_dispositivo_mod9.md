# feature/rf23-rangos-tipo-dispositivo-mod9 — RF-23 / issue #1632

Rama: `feature/rf23-rangos-tipo-dispositivo-mod9` (desde `dev`). Fecha: 2026-08-24.

## Qué pedía el issue #1632

Tres puntos sobre RF-23 (configuración remota de dispositivos IoT):
1. Timeout de ACK de 30s → estado `No Confirmado` → HTTP 504.
2. Estado explícito `No Confirmado` (el issue asumía solo binario PENDIENTE/APLICADA).
3. Rangos de configuración por tipo de dispositivo (`dispositivos_iot` sin columna `tipo`).

## Hallazgo: #1 y #2 ya estaban hechos

El repo estaba adelantado al texto del issue. En el MVP MQTT del 2026-08-20:
- El timeout de 30s vive en `BROKER-MQTT-SGPMP` (`MQTT_ACK_TIMEOUT_SECONDS`).
- El backend ya consumía el veredicto `NO_CONF` y lo mapeaba a `GatewayTimeoutError` (504)
  en `dispositivo_iot_router.py`. `NO_CONF` ya existía en la entidad y en el `CHECK` de
  `configuraciones_remotas.estado`.

Por decisión del usuario ("reimplementar los 3") se cubrieron los tres, pero para #1 y #2 —que
ya funcionaban— la acción fue **verificar + cubrir con tests + endurecimiento mínimo**, no
reescribir código que funciona.

## Qué se hizo

### #3 — Rangos por tipo de dispositivo (trabajo neto)
- **Migración Alembic** `b1c4a7e9d2f3_rf23_rangos_tipo_dispositivo.py` (head `192872fafd40`):
  tabla `modulo9.tipos_dispositivo_iot` (nombre + min/max por parámetro + 2 `CHECK`), seed de
  3 tipos (`GENERICO`/`NODO_BAJO_CONSUMO`/`SENSOR_AMBIENTAL`), columna
  `dispositivos_iot.id_tipo_dispositivo` nullable → backfill a `GENERICO` → NOT NULL + FK.
- **ORM**: `TipoDispositivoIotModel` nuevo; `DispositivoIotModel` con `id_tipo_dispositivo` + FK.
- **Dominio**: entidad `TipoDispositivoIot` con `verificar_rango(...)`; `DispositivoIot` lleva
  `id_tipo_dispositivo` (en `crear` y `_snapshot`); puerto `TipoDispositivoIotRepository`.
- **Repos**: `SqlAlchemyTipoDispositivoIotRepository` (obtener_por_id, listar);
  `SqlAlchemyDispositivoIotRepository` mapea/persiste el nuevo campo.
- **DTO/use cases**: `RegistrarDispositivoIotDTO` exige `id_tipo_dispositivo`;
  `RegistrarDispositivoIotUseCase` valida que el tipo exista (404
  `TIPO_DISPOSITIVO_NO_ENCONTRADO`); `ConfigurarRemotamenteUseCase` valida los valores contra el
  rango del tipo del dispositivo → 400 `PARAMETRO_FUERA_DE_RANGO` con el mensaje exacto del FA.
- **Router/schema**: nuevo `GET /configuracion/tipos-dispositivo-iot` (solo lectura, RBAC 11/R),
  registrado en `main.py`; `DispositivoIotResponse` ahora incluye `id_tipo_dispositivo`.

### #1/#2 — verificación + endurecimiento
- `mqtt_http_adapter.py`: el timeout HTTP al broker pasa a ser configurable
  (`MQTT_BROKER_HTTP_TIMEOUT`, default 35s) con comentario del contrato de 30s. No se reimplementa
  la espera del ACK (autoridad del broker).
- Tests `tests/configuration/test_rf23_rangos_tipo_dispositivo.py`: rango fuera de límites → 400
  con mensaje FA; propagación de estado `APLICADA`/`PENDIENTE`/`NO_CONF`; unit de `verificar_rango`.

## Fuera de alcance (explícito)
- Campo `estado_dispositivo` (boolean) que el FA lista como input del endpoint de configurar:
  #1632 no lo menciona y no está en el DTO → desviación conocida.
- CRUD de escritura de tipos: los rangos se gestionan por seed/SQL (`# ponytail:` en la migración).
- Reenvío automático de config `PENDIENTE` al reconectar (necesita webhook broker→backend).
- No se tocó el repo `BROKER-MQTT-SGPMP`.

## Verificación
- `alembic upgrade head` OK sobre `sgpmp`; tabla + seeds + backfill verificados por MCP postgres
  (11 dispositivos existentes → `GENERICO`, columna NOT NULL).
- `pytest tests/configuration` → 22 passed.
- Ver end-to-end con curl en `curls_m09_cu05_dispositivos_iot.md`.
- La BD `pruebas` no tiene schema `modulo9` → sin tests de integración de módulo 9 (unit only).
