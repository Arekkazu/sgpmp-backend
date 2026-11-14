# INC-M03-113-G56 — Reintentos, backoff y cola de reenvío de paquetes de inferencia (RF-56)

**RF:** RF-56, restricción 14 (política de reintentos), E4, E5, CA-5, CA-6 y CA-14.
**Grupo:** TC-M03-G56. **Issue:** #656.
**Depende de:** INC-M03-112-G55 (#655), que aporta el envío por lotes que reutiliza esta cola.

## Lo que pide RF-56

| Regla | Texto de la ficha |
|---|---|
| Restricción 14 | 5 intentos: el 1 inmediato, el 2 a los 5 s, el 3 a los 15 s, el 4 a los 30 s y el 5 a los 60 s. Si falla tras el máximo, se marca FALLIDO |
| E4: falla de conectividad | "Se marca como pendiente de envío. Se reintenta automáticamente" |
| E5: rechazo del motor | "Se clasifica el paquete como FALLIDO" |
| CA-6 | Al restablecerse la conectividad, "reenviar automáticamente los paquetes pendientes en orden" |
| Restricción 8 | "Debe ser asíncrono": no bloquea la captura (RF-53) ni el procesamiento Edge (RF-55) |

## Antes

En `ConsolidarEnviarPaqueteUseCase` había un único intento síncrono. Si no se confirmaba, el
paquete quedaba `FALLIDO` con 1 intento y nada volvía a intentarlo. El propio código lo decía:
"backoff diferido fuera de alcance".

## Ahora

| Situación | Estado del paquete | Siguiente intento |
|---|---|---|
| Motor sin integrar (stub) antes del primer intento | `PENDIENTE`, 0 intentos | En el siguiente ciclo de la cola |
| Intento n (1 a 4) no confirmado: `False`, timeout, conexión o error genérico | `PENDIENTE`, n intentos | Cuando pase la espera n (5, 15, 30 o 60 s) desde ese intento |
| Intento 5 no confirmado | `FALLIDO`, 5 intentos | Ninguno |
| Rechazo del motor (`MotorInferenciaRechazoError`, E5) | `FALLIDO` | Ninguno |
| Confirmado | `ENVIADO` | — |

**Dónde ocurre cada intento:**
- El **intento 1** lo hace la consolidación, de inmediato, en la misma petición de
  `POST /iot/eventos-edge`.
- Los **intentos 2 a 5** los hace la cola. No se usa `sleep` dentro de la petición, porque
  RF-56 exige que el envío sea asíncrono.

**Cola de reenvío:**
- `reenviar_paquetes_inferencia_periodicamente`
  (`src/telemetry/infrastructure/workers/reenvio_inferencia_worker.py`) arranca desde el
  `lifespan` de `main.py`, como las demás tareas periódicas.
- Corre cada `IOT_INFERENCIA_REENVIO_SEG` segundos (5 por defecto, la espera más corta de la
  política) y ejecuta `DrenarPaquetesPendientesUseCase`.
- `listar_pendientes` solo devuelve los paquetes cuya espera ya venció, en orden cronológico de
  captura, en lotes de máximo 500 y con `SKIP LOCKED`.
- Cuando el motor vuelve a estar disponible, la cola reenvía los pendientes en orden (CA-6).

**Cuándo toca el siguiente intento (sin migración):**
- `fecha_envio` pasa a ser la fecha del último intento.
- El siguiente vence en `fecha_envio + espera[intento_envios]`, calculado en SQL con
  `make_interval` y un `CASE` generado desde `ESPERAS_REINTENTO_INFERENCIA_SEG`.
- Hasta ahora esa columna guardaba cuándo se construyó el paquete y no la usaba ninguna lógica.
  Un paquete que nunca se intentó (0 intentos) siempre vence.

**Registro (RF-63):** `actualizar_estado` deja evidencia de cada transición:

| Transición | Evento en la bitácora |
|---|---|
| Intento no confirmado que se reprograma | `REINTENTO_ENVIO_PAQUETE_PROGRAMADO`, con resultado `FALLIDO` y severidad `WARNING` |
| Paquete agotado o rechazado | `FALLO_ENVIO_PAQUETE` |
| Paquete entregado | `PAQUETE_ENVIADO_IA` |

La consolidación también conserva su registro de causa: `MOTOR_INFERENCIA_NO_DISPONIBLE`,
`ENVIO_INFERENCIA_NO_CONFIRMADO`, `ERROR_ENVIO_INFERENCIA` y, ahora, `MOTOR_INFERENCIA_RECHAZO`.

## Buffer RF-54

El buffer de RF-54 vive en el **nodo Edge**, no en el backend. Del lado del backend, su
equivalente es el estado `PENDIENTE`, que la propia Salida de RF-56 describe como "PENDIENTE
(almacenado en buffer RF-54)". El paquete se conserva sin pérdida y la cola lo reenvía. No se crea
un buffer paralelo (P5 de DEV-17). Lo que el nodo haga con su propio buffer al no poder enviar le
corresponde al firmware Edge.

## Con el motor actual

`MotorInferenciaStubAdapter` sigue siendo el único adaptador, porque no existe un receptor en M04
ni un contrato IA-1 (ver INC-M03-112-G55).

- **Hoy, con el stub:** la cola corre, pero el stub declara que el motor no está integrado. Hace
  `rollback` y los paquetes siguen `PENDIENTE` con sus intentos; solo deja un `INFO` en el log.
- **Cuando exista el adaptador real:** se reemplaza en `drenar_una_vez()` y en
  `evento_edge_router`, y los reintentos y el reenvío funcionan sin tocar los use cases.

## Pruebas

**Todas usan dobles del motor** (Mock del puerto o el stub); ninguna demuestra una integración real
con M04.

`tests/telemetry/test_inc_m03_113_g56_reintentos_paquetes.py`, 15 pruebas:

- **Política y esperas:**
  - La política son 5 intentos con esperas de 0, 5, 15, 30 y 60 s, y el quinto fallo deja FALLIDO.
  - Con reloj controlado, los intentos ocurren en t = 0, 5, 20, 50 y 110 s; un segundo antes de
    cada espera no se intenta, y nunca hay un sexto intento.
  - Un rechazo (E5) deja FALLIDO de inmediato, sin reintentos.
- **Recuperación de M04:**
  - Si M04 no está disponible antes del primer intento, el paquete queda PENDIENTE con 0 intentos.
  - Al recuperarse M04, los pendientes se reenvían en orden de captura (CA-6).
  - Tras una caída temporal, cuando vence la espera se reenvían en orden, con 2 intentos.
- **Consolidación (intento 1):** con `True`, `False`, `TimeoutError` y rechazo se aplica la
  política, y se guarda la fecha del intento.
- **Repositorio:**
  - La SQL de `listar_pendientes` filtra por espera vencida con `make_interval` y el `CASE`.
  - `actualizar_estado` guarda la fecha y registra `REINTENTO_ENVIO_PAQUETE_PROGRAMADO`,
    `FALLO_ENVIO_PAQUETE` o `PAQUETE_ENVIADO_IA`.
- **Worker:** usa el adaptador configurado y cierra la sesión.

**Pruebas existentes actualizadas** al nuevo comportamiento, porque el intento 1 no confirmado ya
no es FALLIDO:

| Archivo | Cambio |
|---|---|
| `tests/telemetry/test_rf56_dev17_paquetes_pendientes.py` | `False` y error de envío ahora dejan `PENDIENTE` con 1 intento; `actualizar_estado` recibe la fecha del intento |
| `tests/telemetry/test_dev49_alertas_historial_auditoria.py` | El estado esperado pasa a `PENDIENTE`; el registro de la causa no cambia |
| `tests/telemetry/test_inc_m03_112_g55_paquetes_inferencia.py` | El repositorio en memoria respeta el backoff; un lote no confirmado queda `PENDIENTE` (reprogramado) |
| `tests/integration/test_rf56_dev17_paquetes_pendientes.py` | `False` y error de envío ahora dejan `PENDIENTE` |
| `tests/integration/test_dev47_auditoria_integridad.py` | El caso negativo deja `PENDIENTE` con `REINTENTO_ENVIO_PAQUETE_PROGRAMADO` |

Las dos pruebas de integración necesitan `TEST_DATABASE_URL`. Se comprobó que se recolectan, pero
no se ejecutaron localmente.

**Verificación en `sgpmp_dev`, solo lectura:**
- `EXPLAIN` de la consulta de `listar_pendientes` con el filtro de espera vencida, sin el
  `FOR UPDATE` que el MCP no admite: es válida y usa `idx_paquetes_inferencia_estado`.
- En DEV hay 2 paquetes `PENDIENTE` (ids 14 y 17), y ambos ya vencieron. Con el adaptador real,
  la cola los intentaría en el primer ciclo.
