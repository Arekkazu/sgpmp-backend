# INC-M03-119-G62 — Claves alteradas y revocadas (TC-M03-124) y BOLA entre gateways (TC-M03-126)

**RF:** RF-56 E7 ("Error en autenticación: credenciales inválidas o expiradas"). **Grupo:** TC-M03-G62.
**Issue:** #664. **Estado:** **verificado** con el adaptador real de M09 y PostgreSQL real.
Queda un riesgo residual en el broker: la credencial compartida legacy.

## Contrato de autenticación vigente

`access_key` **ya no existe** en `POST /iot/eventos-edge`. Las pruebas de QA que lo usan
(`test_tc_m03_124_dto_sin_access_key`) corresponden a un contrato anterior a D3 (AIOT-DEV-03).
Hoy la identidad se verifica en **dos capas**:

| Capa | Qué verifica | Dónde |
|---|---|---|
| **Broker** (`BROKER-MQTT-SGPMP`) | La credencial MQTT del Edge (usuario = serial del Edge, dynamic-security). Una clave **alterada** no conecta. Una **revocada** se corta: `disableClient` para el Edge (lo desconecta en el acto) o `deleteRole serial-<S>` para un dispositivo. Cada Edge solo puede publicar en los topics de sus propios seriales (`sgpmp/<S>/evento`, etc.), y **el `serial` que reenvía al backend es siempre el del topic**: si el cuerpo trae otro, se ignora | `docs/RFC_credencial_mqtt_por_dispositivo.md` §7. Verificado contra Mosquitto 2.1.2 con 25 comprobaciones en `scripts/e2e_credenciales_mqtt.py` |
| **Backend** | El token de servicio del broker (`require_token_servicio_broker`). Además, **la terna completa** con `DispositivoM09Adapter.obtener_dispositivo_activo`: `device_id`, `sensor_id` y `serial` en un mismo `WHERE`, con el dispositivo y el sensor activos en M09 | `evento_edge_router.py`, `dispositivo_m09_adapter.py`, `recibir_evento_edge_use_case.py` |

### ¿Hay que distinguir clave alterada de clave revocada?

**No.** RF-56 E7 trata las dos como "credenciales inválidas o expiradas", con la misma acción:
"se bloquea el envío, se registra intento fallido, se notifica". Además, el backend nunca ve la clave MQTT.

**Lo que sí distingue el backend:**
- **Token del broker inválido o ausente:** 401, y el intento queda en la bitácora con su código.
- **Dispositivo o sensor que no corresponden al serial, o están desactivados en M09** (la
  revocación del lado de M09): 401 `DISPOSITIVO_NO_AUTORIZADO`, y el intento
  `INTENTO_NO_AUTORIZADO_EVENTO_EDGE` (CRITICAL) queda en la bitácora RF-63.

## Riesgo residual: credencial compartida legacy

Mientras exista `MQTT_DEVICE_USERNAME`/`MQTT_DEVICE_PASSWORD`, el broker mantiene el rol
`dispositivos_legacy`, cuya ACL se arma con `+` en lugar del serial
(`app/services/credenciales_mqtt.py`, `_acls_dispositivo(settings, "+", ...)`). Con esa
credencial **se puede publicar en `sgpmp/<cualquier serial>/evento`**.

- **Qué pasa en el backend:** la terna sigue rechazando una mezcla de identificadores (serial de A
  con dispositivo o sensor de B). Pero alguien con la credencial legacy puede publicar con la
  **terna completa** de otro gateway, y eso el backend no lo puede distinguir.
- **Cómo se cierra:** con el paso 3 de la migración del RFC (§7.4): borrar la credencial
  compartida en Dokploy cuando todos los Edge tengan su credencial propia.
- **A quién le toca:** al broker y a infraestructura, no al backend.

No se pudo comprobar si DEV todavía la tiene activa: depende de la configuración de Dokploy.

## Evidencia: pruebas de integración con el adaptador real

`tests/integration/test_inc_m03_119_g62_autenticacion_bola.py`: router real, `DispositivoM09Adapter`
real y PostgreSQL real. Hay **dos Gateway Edge** (tipo `GATEWAY_EDGE`) en **fincas distintas**, cada uno
con su nodo (`id_dispositivo_gateway`) y su sensor.

| Prueba | Escenario | Resultado |
|---|---|---|
| `test_gateway_legitimo_es_aceptado` | Gateway A con su propia terna | 201; 1 evento y 1 paquete |
| `test_bola_gateway_a_no_puede_enviar_por_el_gateway_b[dispositivo_y_sensor_de_B]` | Serial de A con dispositivo y sensor de B | 401 `DISPOSITIVO_NO_AUTORIZADO`; **0 eventos y 0 paquetes** en A y en B; intento en la bitácora |
| `…[sensor_de_B]` | Dispositivo de A con sensor de B | Igual |
| `…[dispositivo_de_B]` | Dispositivo de B con sensor de A | Igual |
| `test_dispositivo_o_sensor_revocado_en_m09_es_rechazado[dispositivo]` | Dispositivo desactivado | 401; 0 eventos y 0 paquetes; intento en la bitácora |
| `…[sensor]` | Sensor desactivado | Igual |
| `test_token_del_broker_ausente_o_alterado_es_rechazado[None / alterado / vacío]` | Sin token, token alterado o token vacío | 401; 0 eventos y 0 paquetes; intento registrado |

En la prueba del token, el registro del intento se captura en vez de usar `sesion_sistema()`, porque
esa sesión usa `DATABASE_URL` y no la base de pruebas.

### Ejecución (2026-10-27)

**Base efímera** en el PostgreSQL local (`sgpmp-db`, postgres:18):
- Se creó la base `pruebas_g62_test` y se le aplicó `alembic upgrade head` hasta `ebbb160365e5`.
- `DATABASE_URL` y `TEST_DATABASE_URL` apuntaban a esa base.
- Al terminar se borraron la base y los roles temporales.

**Resultados:**

```
tests/integration/test_inc_m03_119_g62_autenticacion_bola.py ......... 9 passed
tests/integration/test_rf56_dev17_paquetes_pendientes.py (control, mismo endpoint) 23 passed
32 passed in 4.00s
```

**Para reproducirlo**, siguiendo `tests/integration/README.md` (base `*test*` y `TEST_DATABASE_URL`):
- En un PostgreSQL local cuyo superusuario no sea `postgres`, el baseline exige el rol `postgres`, y
  la migración `app_ctx` exige `sgpmp_app` y `sgpmp_owner`. Se crearon como `NOLOGIN`, con
  `postgres SUPERUSER NOLOGIN`, porque las funciones `SECURITY DEFINER` del baseline le pertenecen y en
  DEV ese rol es superusuario.
- Los nombres de finca solo admiten letras (trigger `trg_fn_finca_nombre_unique`).

## Cambios

- **Código de producción:** ninguno. La terna, la revocación en M09 y el token ya estaban
  implementados (DEV-06, DEV-29, DEV-45).
- **Prueba de integración nueva:** `tests/integration/test_inc_m03_119_g62_autenticacion_bola.py`.
- **Documentación:** esta nota.

## Para QA

- **TC-M03-124:**
  - Retirar el escenario de `access_key`, que ya no existe.
  - La clave MQTT alterada o revocada se verifica en el broker (`e2e_credenciales_mqtt.py`).
  - En el backend: token del broker y revocación en M09, ambos con 401, sin persistencia y con
    registro en la bitácora.
- **TC-M03-126:** la prueba de integración de arriba es el escenario de ataque pedido (dos gateways
  independientes, rechazo, sin persistir ni enviar, terna aplicada). La prueba con
  `DispositivoPortFijo` de QA solo prueba su doble, como ya señala el ticket.
