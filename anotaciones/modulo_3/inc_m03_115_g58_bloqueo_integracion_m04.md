# INC-M03-115-G58 — Integración real con M04 y rechazo de esquema (TC-M03-114): bloqueada

**RF:** RF-56 (E5 y E8) y RF-66 (M04). **Grupo:** TC-M03-G58. **Casos:** TC-M03-114 y TC-M03-121.
**Issue:** #658. **Estado:** **bloqueada** por una definición que corresponde a M04 y AIoT.

## Por qué está bloqueada

El ticket pide implementar el adaptador HTTP real hacia M04 y **confirmar el endpoint de
recepción, el esquema esperado y la autenticación**. Esa definición no existe en ningún lado.
Se revisaron los cuatro lugares donde podría estar:

| Dónde | Qué hay | ¿Define la entrega del paquete a M04? |
|---|---|---|
| **Requerimientos** (Módulos 3 y 4, `.md` y `ESPECIFICACION_REQUERIMIENTOS_COMPLETA.xlsx` en Drive) | La Salida de RF-56 define los campos del paquete JSON. RF-66 dice que la inferencia principal corre en el **Edge**, con respaldo en servidor (`modo_ejecucion = SERVIDOR`), y que el motor "recibe el paquete de RF-56" | **No.** Solo "canal seguro (TLS)" y "esquema definido por M04". No hay endpoint, autenticación ni formato de respuesta |
| **Backend** (`src/`) | Solo `MotorInferenciaStubAdapter`. Ningún router de `src/prediction` recibe paquetes. `modulo4.resultados_inferencia` solo se **lee** (RF-72) | **No.** Nada produce resultados de inferencia |
| **Broker** (`BROKER-MQTT-SGPMP`, rama `develop`) | Reenvía al backend `evento`, `vision`, `ota/<evento>`; envía comandos (`/v1/commands`, `/v1/ota/notify`) | **No.** No hay topic ni ruta de inferencia, ni de entrada ni de resultados |
| **Base de datos** (`sgpmp_dev`, solo lectura) | `modulo4.resultados_inferencia.id_paquete_inferencia` → FK a `modulo3.paquetes_inferencia` (entero, `NOT VALID`); `paquetes_inferencia.id_version_modelo` → FK a `modulo4.versiones_modelos`; enum `modo_ejecucion` | **En parte.** Fija cómo se **relaciona** un resultado con su paquete, no cómo **llega** el paquete al motor |

Sin esa definición, cualquier adaptador HTTP tendría que inventar la ruta, la autenticación y los
códigos de respuesta de M04. Las pruebas de contrato quedarían probando un contrato que M04 no ha
aceptado.

## Lo que ya está resuelto del lado del backend

- **La premisa del ticket ya no se cumple.** `MotorInferenciaStubAdapter.enviar_paquete` no
  devuelve `True` desde DEV-17: lanza `MotorInferenciaNoIntegradoError` y el paquete queda
  `PENDIENTE` con 0 intentos. El resultado del stub nunca se presenta como una entrega.
- **El rechazo de esquema (E5) ya está separado de los fallos temporales** en el puerto
  (INC-M03-113-G56, #656, todavía sin mergear):

  | Situación | Señal del adaptador | Resultado |
  |---|---|---|
  | Rechazo de esquema o de datos (E5) | `MotorInferenciaRechazoError` | `FALLIDO`, sin reintentos |
  | Conexión, timeout o motor no disponible (E4) | `ConnectionError`, `TimeoutError`, `ServiceUnavailableError` o `False` | `PENDIENTE` y reintento con backoff 0/5/15/30/60 s; `FALLIDO` tras el quinto |
  | Sin integración | `MotorInferenciaNoIntegradoError` | `PENDIENTE`, 0 intentos |

  El adaptador real solo tendrá que traducir las respuestas de M04 a esas señales.
  Los use cases no cambian.
- **Envío por lotes y cola de reenvío** (#655, #656): listos para usarse en cuanto exista el
  adaptador real.

## Lo que hace falta para desbloquear (M04 / AIoT)

1. **Mecanismo de entrega del paquete al motor en modo SERVIDOR** (RF-66, E1/E6): ¿HTTP hacia un
   servicio de M04, MQTT por el broker o lectura directa de `paquetes_inferencia`?
2. **Si es HTTP:** URL, autenticación (RF-56, restricción 7: TLS) y respuesta:
   - qué código o cuerpo significa aceptado;
   - cuál es un rechazo de esquema (E5);
   - cuál es un error temporal.
3. **Esquema del paquete.** Lo que ya está fijado y la propuesta debería respetar:
   - los campos de la Salida de RF-56;
   - `id_paquete` **entero**, porque así lo exige la FK de `resultados_inferencia` (cierra la
     diferencia con el UUID que pide RF-56, señalada en #655).
4. **Quién escribe `modulo4.resultados_inferencia`:** el motor del servidor, el Edge vía el broker
   (RF-66, Fase 6.1: el resultado del Edge "se sincroniza con el servidor central") o ambos.

Con eso, el backend agrega el adaptador real (`httpx` ya está en `requirements.txt`), su mapeo de
respuestas y las pruebas de contrato, y reemplaza el stub en `evento_edge_router` y en
`reenvio_inferencia_worker`.

## TC-M03-121 (E8): pendiente de especificación

RF-56 E8 ("el paquete no corresponde a la versión actual del modelo") da tres acciones sin elegir
ninguna: "se ajusta versión si es posible", "o se envía a pipeline compatible" y "o se rechaza con
log técnico".

**Lo que sí está fijado:**
- `paquetes_inferencia.id_version_modelo` es una FK a `modulo4.versiones_modelos`. La versión
  objetivo debería resolverse a un `id_version_modelo` existente.
- Hay una sola versión `ACTIVO` por tipo de modelo y componente: lo garantiza el índice único
  `uq_version_modelo_activa_tipo_componente`, sobre `(tipo_modelo, componente)` con
  `estado_version = 'ACTIVO'`.

**Lo que falta definir (Análisis Funcional):**
- Cuándo una versión "no corresponde": distinta de la `ACTIVO` de su tipo de modelo y
  componente, o inexistente.
- Cuál de las tres acciones se aplica, y si depende del caso.

**Hoy:** `version_modelo_objetivo` llega en el DTO de `POST /iot/eventos-edge`, pero no se
propaga al paquete (`id_version_modelo` queda `NULL`).

**Propuesta de Desarrollo, para ratificar:**
- Resolver el texto recibido contra `versiones_modelos`.
- Si coincide con una versión existente, guardar su `id_version_modelo`.
- Si no existe, rechazar con un registro técnico en RF-63, que es la opción más conservadora y no
  requiere un "pipeline compatible" que todavía no existe.

## Otro hallazgo, para no perderlo

El trigger `trg_rf55_01_crear_paquete_inferencia` (`AFTER INSERT ON
modulo3.eventos_edge_computing`, función `modulo3.fn_crear_paquete_inferencia`) también crea paquetes
directamente en la BD, cuando un evento se inserta con `enviado_backend = true`.

- **Hoy no se dispara,** porque el backend inserta los eventos con `enviado_backend = false` y
  crea el paquete en `ConsolidarEnviarPaqueteUseCase`.
- **Si alguien cambiara ese valor,** habría dos paquetes por evento, y el del trigger tendría
  `contexto_incompleto = false` y `estado_calidad = LECTURA_VALIDA` fijos.

Conviene que el DBA decida si se retira.

## Cambios

Ninguno en código ni en BD. Solo esta nota.
