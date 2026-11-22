# INC-M03-117-G60 — Idempotencia y detección de paquetes duplicados en M04 (RF-56)

**RF:** RF-56 (restricciones 3 y 10) y RF-66 (Fase 7). **Grupo:** TC-M03-G60.
**Casos:** TC-M03-119 (idempotencia en M04) y TC-M03-120 (mismo id con contenido distinto).
**Issue:** #660. **Estado:** **parcial**. El emisor queda completo; la idempotencia en el receptor
está bloqueada por #658.

## Qué estaba establecido

| Dónde | Qué hay |
|---|---|
| **RF-56** | Restricción 3: "cada evento enviado debe ser único: no duplicado, identificable mediante `id_evento` o `id_paquete`". Restricción 10: "reenvíos no generen duplicados en el backend". No dice qué responder si llega el mismo id con otro contenido |
| **RF-66 / M04** | Fase 7: el resultado se guarda con su `id_paquete`; los eventos se correlacionan por `id_paquete`. Nada sobre duplicados en el receptor |
| **Base de datos** | `paquetes_inferencia.id_paquetes_inferencia` es la PK; `resultados_inferencia.id_paquete_inferencia` la referencia por FK (`fk_ri_paquete`). **No hay UNIQUE** sobre esa columna |
| **Backend (emisor)** | El id ya es estable: los reintentos (#656) y la reconsolidación (DEV-17) reutilizan la misma fila; nunca se reenvía un paquete `ENVIADO` |

**Sobre la falta de UNIQUE:** la BD no impide dos resultados para el mismo paquete. En modo
HÍBRIDO puede ser legítimo, porque RF-66 (Fase 6.1) permite que el servidor recalcule lo que ya infirió
el Edge. Un UNIQUE solo por `id_paquete_inferencia` sería incorrecto; por `(id_paquete_inferencia,
modo_ejecucion)` podría serlo. **Es decisión de M04.**

## Cambios: identificador de negocio estable

El identificador de un envío es **`id_paquetes_inferencia` + `huella_contenido`**:

- **`huella_contenido_paquete(paquete)`** (`telemetria.py`): SHA-256 del contenido en JSON canónico,
  con claves ordenadas y Decimal normalizado (38.5 = 38.5000).
  - **Incluye:** sensor, equipo, evento Edge, variable, valor, unidad, calidad, desviación, severidad,
    origen, contexto, `contexto_incompleto`, versión de modelo y `metadatos` (timestamps de captura y
    procesamiento, clasificación RF-55).
  - **Excluye:** el id, `estado_paquete`, `intento_envios`, `fecha_envio` y la propia huella, que
    cambian en cada intento o van aparte.
- **`ConsolidarEnviarPaqueteUseCase`:** calcula la huella al generar el paquete y la guarda en
  `metadatos.huella_contenido`. No hace falta migración, y la huella sale en
  `GET /iot/paquetes-inferencia/{id}` (#659).
- **`huella_coincide(paquete)`:** dice si el contenido actual corresponde a la huella guardada. Los
  paquetes anteriores a este cambio no tienen huella y devuelven `false`.

**Comportamiento resultante del lado del emisor:**

| Caso | Id | Huella |
|---|---|---|
| Reintento del mismo paquete (cualquier intento) | El mismo | La misma |
| Reconsolidación del mismo evento Edge | El mismo (DEV-17) | La misma (no se recalcula) |
| Paquete de otro evento | Otro | Otra |
| El mismo id con contenido alterado | El mismo | **Distinta**: `huella_coincide` es `false` |

## Bloqueado: la idempotencia en M04 (#658)

TC-M03-119 y TC-M03-120 verifican al **receptor**, y el receptor no existe: no hay endpoint ni
contrato IA-1 (ver `inc_m03_115_g58_bloqueo_integracion_m04.md`). **Propuesta de contrato para M04**,
para que la confirme:

1. **El paquete viaja con `id_paquete` (entero) y `huella_contenido`.**
2. **Mismo `id_paquete` y misma huella:** es un reintento. M04 no vuelve a procesar ni a insertar un
   resultado, y responde aceptado (2xx) con el resultado existente. El emisor lo marca `ENVIADO`.
3. **Mismo `id_paquete` y huella distinta:** es una reutilización indebida del identificador. M04
   rechaza, por ejemplo con **409 `PAQUETE_DUPLICADO_CONTENIDO_DISTINTO`**, y no procesa. El emisor lo
   trata como rechazo definitivo (`MotorInferenciaRechazoError`, E5): `FALLIDO` sin reintentos y
   registrado en la bitácora RF-63.
4. **En la BD:** M04 decide si respalda la regla con un índice único sobre `resultados_inferencia`, por
   `(id_paquete_inferencia, modo_ejecucion)` si el modo HÍBRIDO admite dos resultados por paquete.
   Esa migración requiere aprobación del DBA.

**Registro:** los resultados de aceptación y rechazo ya quedan en la bitácora RF-63 del paquete
(`PAQUETE_ENVIADO_IA`, `FALLO_ENVIO_PAQUETE`), y se consultan con
`GET /iot/paquetes-inferencia/{id}` o `GET /iot/auditoria?entidad_afectada_tipo=PAQUETE_IA` (#659).

## Fuera de alcance, para no perderlo

**Duplicados de Edge hacia el backend.** RF-55 define `id_evento` (UUID) en la estructura mínima del
evento Edge, pero `POST /iot/eventos-edge` no lo recibe. Un reenvío del buffer del Edge crea otro
evento y otro paquete. Esto ya estaba anotado en DEV-17 ("un nuevo POST sin identificador externo sigue
creando un nuevo evento"). Corregirlo requiere que el Edge envíe el `id_evento`, una columna con un
índice único en `eventos_edge_computing` (migración) y acordarlo con AIoT. No es el escenario de este
ticket, que trata de los envíos a M04.

## Pruebas

`tests/telemetry/test_inc_m03_117_g60_huella_paquetes.py`, 12 pruebas. **Son de identidad local del
emisor y no demuestran la idempotencia en M04.**

- **Determinismo y reintentos:**
  - La huella es un SHA-256 determinista.
  - Un reintento (otro estado, otros intentos, otra fecha) conserva la huella.
- **Paso por PostgreSQL:** la huella se mantiene aunque JSONB reordene claves, `Numeric` devuelva otra
  escala o los Enum vuelvan como `str`. Esto se contrastó con `sgpmp_dev`: `'38.5000'::numeric` devuelve
  `Decimal('38.5000')` y `jsonb` reordena las claves.
- **Contenido distinto:** cambiar el valor, la severidad, el evento, el contexto o el timestamp cambia
  la huella (5 casos).
- **Verificación de la huella:**
  - La huella guardada no entra en su propio cálculo.
  - `huella_coincide` detecta un contenido alterado y los paquetes sin huella.
- **Consolidación:**
  - Guarda la huella del paquete que genera.
  - Al reconsolidar devuelve el mismo id y la misma huella, sin volver a guardar.
