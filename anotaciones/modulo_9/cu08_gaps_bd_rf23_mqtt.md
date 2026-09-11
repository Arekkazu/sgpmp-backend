# CU-08 – Gaps de BD para RF-23 (integración MQTT real)

A diferencia de los CU anteriores de este módulo, este gap se gestiona por
**Alembic** (decisión explícita del usuario para este caso), no por DDL
directo vía MCP postgres. Este documento es la referencia legible; la fuente
de verdad es la migración `alembic/versions/7e2d5f3bf17a_rf23_mqtt_integracion.py`
(sobre el baseline `f7fe43537842`, primera migración real del proyecto).

## Bootstrap de Alembic

El proyecto tenía `alembic==1.18.4` en `requirements.txt` y una carpeta
`alembic/versions/` vacía, pero sin `alembic.ini`/`env.py` funcionales. Se
creó ambos apuntando a la `Base` declarativa compartida
(`src/shared/base_model.py`, reexportada por todos los módulos salvo
`prediction`, que declara su propia `DeclarativeBase` — inconsistencia
preexistente, no corregida acá porque no bloquea esta migración escrita a
mano). `env.py` importa todos los modelos ORM dinámicamente (recorre
`src/*/infrastructure/models/*.py`) para poblar `target_metadata`.

Se encontró un `alembic_version` huérfano en la base `sgpmp`
(`796957ec0da2`, sin ninguna migración correspondiente en el repo ni en el
historial de git — resto de un experimento local anterior). Se resolvió con
`alembic stamp --purge head` sobre la migración baseline vacía
(`f7fe43537842`), que reemplaza ese puntero por uno coherente sin intentar
recrear el esquema ya existente.

## Migración RF-23 (`7e2d5f3bf17a`)

1. `configuraciones_remotas_estado_check`: se agrega `NO_CONF` al conjunto
   permitido (antes `PENDIENTE/APLICADA/CANCELADA`). `CANCELADA` sigue sin
   ser escrito por ningún código (huérfano, preexistente, no tocado).
2. Índice único parcial `uq_config_remota_pendiente_por_dispositivo` sobre
   `(id_dispositivo_iot) WHERE estado='PENDIENTE'` — cierra un TOCTOU real:
   `ConfiguracionRemotaRepository.obtener_pendiente()` es un `SELECT` sin
   `FOR UPDATE`, así que dos requests concurrentes para el mismo dispositivo
   podían crear dos filas `PENDIENTE`. Ahora la segunda choca contra el
   índice y sale como `409 ConflictError` vía `raise_from_db_error`.
3. Tabla `modulo1.credenciales_servicio` — credencial de servicio para que
   el backend se autentique contra `BROKER-MQTT-SGPMP` (hash sha256 sin sal
   en `hash_valor`, mismo formato que `modulo1.tokens.hash_valor`). **No se
   reutilizó `modulo1.tokens`**: su `enum_token_tipo` está cerrado a
   `{recuperacion, verificacion_correo, acceso, refresco}`, tiene FK
   conceptual a `id_sesion` (token humano) y un trigger de un solo uso
   (`trg_token_un_solo_uso`) — semántica incompatible con un credential de
   servicio de larga vida reutilizado en cada request.

Aplicado con `alembic upgrade head`:
- `sgpmp` (dev): **aplicado correctamente**, en head `7e2d5f3bf17a`.
- Token de servicio generado (`secrets`-equivalente vía `/dev/urandom` +
  `sha256sum`, mismo resultado), hash insertado en
  `modulo1.credenciales_servicio` (`id_credencial_servicio=1`,
  `nombre_servicio='broker_mqtt'`); el valor plano vive solo en
  `sgpmp-backend/.env` (`MQTT_BROKER_TOKEN`, no committeado).

## Gap encontrado, no resuelto en este ticket

**`pruebas` (BD de tests de integración) no tiene el schema `modulo9` en
absoluto** — solo `modulo1` (confirmado: `information_schema.schemata`
devuelve únicamente `modulo1` con prefijo `modulo%`). La migración de RF-23
falló ahí en el primer `DROP CONSTRAINT` (`InvalidSchemaName: schema
"modulo9" does not exist`) y se revirtió sin dejar cambios a medias
(transacción DDL de Alembic). `pruebas` queda estampada en el baseline
(`f7fe43537842`), no en head.

Esto no es un bug introducido por RF-23: confirma que el módulo 9 completo
(no solo esta migración) nunca tuvo su esquema provisionado en `pruebas` —
coherente con que `tests/integration/conftest.py` solo verifica
`TABLAS_MODULO1_REQUERIDAS` y solo monta routers de `identity_access`. No
existen (ni pueden existir hoy) tests de integración de módulo 9 contra
`pruebas`. Recrear el esquema completo de módulo 9 en `pruebas` es trabajo
de infraestructura de testing más allá del alcance de este ticket — queda
como hallazgo para un ticket de seguimiento propio, no específico de RF-23.
