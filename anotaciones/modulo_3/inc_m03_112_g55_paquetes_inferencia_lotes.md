# INC-M03-112-G55 — Generación, envío y fragmentación de paquetes de inferencia (RF-56)

**RF:** RF-56 (Preparación y envío del paquete de datos al motor de inferencia). **Grupo:** TC-M03-G55.
**Casos:** TC-M03-090 (generación), TC-M03-091 (envío real a M04), TC-M03-092 (fragmentación).
**Issue:** #655.

## Diagnóstico por caso

### TC-M03-090 — Generación del paquete: cobertura ampliada

`ConsolidarEnviarPaqueteUseCase` construye el paquete a partir del evento Edge. Se agrega una
prueba que compara el paquete con los campos obligatorios de la sección Salida de RF-56:

| Campo RF-56 | En el paquete |
|---|---|
| `id_paquete` | `id_paquetes_inferencia` (entero de BD) |
| `sensor_id`, `dispositivo_id` | `id_sensor`, `id_dispositivo_iot` |
| `timestamp_captura`, `timestamp_procesamiento_edge` | `metadatos` |
| `tipo_variable`, `valor`, `unidad` | `tipo_variable`, `valor_numerico`, `unidad` |
| `estado_calidad`, `estado_desviacion`, `severidad`, `origen` | Mismos nombres |
| `version_modelo_objetivo` | **No se propaga**: el DTO de `/iot/eventos-edge` lo recibe, pero no llega al paquete (`id_version_modelo` queda `NULL`) |

Hay dos diferencias con el contrato, y ambas dependen de que M04 defina su esquema (RF-56,
restricción 4: "esquema definido por M04"):

- RF-56 pide `id_paquete` de tipo UUID; la BD usa un entero.
- Falta `version_modelo_objetivo`.

No se cambian aquí porque no existe ese esquema (ver TC-M03-091).

### TC-M03-091 — Envío real a M04: sigue bloqueado

- **La premisa del ticket ya no se cumple.** `MotorInferenciaStubAdapter.enviar_paquete` no
  devuelve `True` desde DEV-17 (ver `rf56_dev17_stub_paquetes_pendientes.md`). Lanza
  `MotorInferenciaNoIntegradoError` y el paquete queda `PENDIENTE` con 0 intentos; nunca se marca
  `ENVIADO` sin una entrega real.
- **No existe un receptor.** Según RF-66, la inferencia principal se ejecuta en el **nodo Edge**
  (Fase 6.1). La del servidor (`modo_ejecucion = SERVIDOR`) es solo un respaldo (E1, E6), y no
  está implementada en el backend: ningún router de `src/prediction` recibe paquetes y no hay un
  `POST /inferencia`.
- **No está definido el contrato de entrega** (lo que DEV-17 llama "IA-1"): endpoint, payload,
  ACK y autenticación. Si el backend construyera ahora un adaptador HTTP, estaría inventando un
  contrato que M04 no tiene.

**A quién le corresponde:** a M04 (y a AIoT si el respaldo en servidor corre fuera del backend).
Debe definir el receptor de modo SERVIDOR y su contrato. Con eso, el backend reemplaza
`MotorInferenciaStubAdapter` por un adaptador real sin tocar los use cases.

### TC-M03-092 — Fragmentación: implementada

QA tenía razón: no había fragmentación. Cada evento genera un paquete y no existía ningún proceso
que enviara los pendientes por lotes. El límite de `/iot/telemetria/batch` es de RF-53.

Se implementó el envío batch de RF-56 (Fase 6, "envío batch si proviene de buffer"):

| Pieza | Cambio |
|---|---|
| `MAX_REGISTROS_POR_ENVIO_INFERENCIA = 500` (`telemetria.py`) | Restricción 5 de RF-56 como constante de dominio |
| `MotorInferenciaPort.enviar_lote` | Envío de un lote de máximo 500 paquetes, con la misma semántica que `enviar_paquete` |
| `MotorInferenciaStubAdapter.enviar_lote` | Lanza `MotorInferenciaNoIntegradoError`; nunca confirma una entrega ficticia |
| `PaqueteInferenciaRepository.listar_pendientes(limite)` | `PENDIENTE` en orden cronológico de captura (restricción 6), con `FOR UPDATE OF paquetes_inferencia SKIP LOCKED` |
| `DrenarPaquetesPendientesUseCase` | Toma lotes de hasta 500 (configurable entre 1 y 500), los envía, guarda `ENVIADO` o `FALLIDO` con un intento más y hace `commit` por lote |

Comportamiento:

- **501 pendientes:** se envían en dos lotes, de 500 y de 1, en orden de captura.
- **Sin integración (stub):** hace `rollback` y se detiene; todo sigue `PENDIENTE` con sus
  intentos. Es el comportamiento actual en DEV.
- **Lote no confirmado o error de transporte:** el lote queda `FALLIDO`, como en DEV-17.
- **Bloqueo por lote:** cada lote se toma y se confirma en su propia transacción. `SKIP LOCKED`
  evita que dos drenados concurrentes envíen el mismo paquete.
- **`max_lotes`** (20 por defecto, es decir hasta 10 000 paquetes) acota cada ejecución.

**No se expone endpoint.** El drenado está pensado para un worker o tarea programada que se
conecte junto con el transporte real. Exponerlo hoy no tendría efecto: con el stub no envía nada.
Por eso no hay CURL nuevo, y TC-M03-092 se valida con las pruebas unitarias.

## Verificación

- **SQL de `listar_pendientes`:** se compiló con el dialecto PostgreSQL y se validó con
  `EXPLAIN` contra `sgpmp_dev`, sin la cláusula `FOR UPDATE`, que el MCP de solo lectura no
  admite. Resultados:
  - El join, el filtro, el orden y el límite son válidos.
  - El plan usa `idx_paquetes_inferencia_estado`.
- **Estado en DEV:** 2 `PENDIENTE`, 8 `ENVIADO`, 1 `FALLIDO`. No se escribió nada en DEV.

## Pruebas

`tests/telemetry/test_inc_m03_112_g55_paquetes_inferencia.py`, 14 pruebas:

- **Fragmentación:**
  - 501 pendientes salen como 500 + 1, en orden y sin repetir ni saltar ninguno.
  - Exactamente 500 salen en un solo lote.
  - Con un tamaño de lote de 200, salen 200 + 200 + 101.
  - Un tamaño de 0 o de 501 se rechaza.
- **Estados:**
  - El stub deja todo `PENDIENTE` y no hace `commit`.
  - Un `False` o un `ConnectionError` dejan el lote `FALLIDO` con 1 intento.
  - Sin pendientes, no se llama al motor.
  - `max_lotes` acota la ejecución.
  - Un fallo al guardar el estado revierte el lote.
- **SQL:** orden por `fecha_captura`, `LIMIT 500` y `FOR UPDATE OF ... SKIP LOCKED`.
- **TC-M03-090:** campos obligatorios de RF-56 en el paquete generado.

## Pendiente fuera del backend

1. **M04 y AIoT:** definir el receptor de inferencia en modo SERVIDOR (RF-66, E1/E6) y el contrato
   IA-1: endpoint, esquema, ACK y autenticación con TLS (RF-56, restricción 7).
2. **M04:** definir si el identificador del paquete es UUID y cómo se informa
   `version_modelo_objetivo`.
3. **Backend, cuando lo anterior exista:**
   - Adaptador real de `MotorInferenciaPort`, con `enviar_paquete` y `enviar_lote`.
   - Worker que invoque `DrenarPaquetesPendientesUseCase`.
   - Propagar `version_modelo_objetivo` al paquete.
