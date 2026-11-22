# INC-M03-114-G57 — Aclaración funcional del indicador `apto_para_ia` en TC-M03-094

**RF:** RF-56 (paquete de inferencia) y RF-62 (calidad y aptitud). **Grupo:** TC-M03-G57.
**Casos:** TC-M03-094 (contexto incompleto) y TC-M03-115 (contexto completo, ya aprobado).
**Issue:** #657. **Tipo:** solicitud de aclaración funcional, no defecto.

QA omitió `test_tc_m03_094_no_apto_para_ia` porque `PaqueteInferencia` no tiene `apto_para_ia`
y la consolidación no lo usa para filtrar el envío. Esta nota responde las cinco preguntas desde
las fichas vigentes y el código de `dev`. **La propuesta de Desarrollo queda sujeta a que Análisis
Funcional la ratifique.**

## Respuestas

### 1. ¿Debe existir `apto_para_ia` en `PaqueteInferencia`?

**No.** La Salida de RF-56 lista los campos del paquete y `apto_para_ia` no está entre ellos:

- **Obligatorios:** `id_paquete`, `sensor_id`, `dispositivo_id`, `timestamp_captura`,
  `timestamp_procesamiento_edge`, `tipo_variable`, `valor`, `unidad`, `estado_calidad`,
  `estado_desviacion`, `severidad`, `origen` y `version_modelo_objetivo`.
- **Opcionales:** `contexto` y `metadata_edge`.

En toda la ficha de RF-56, la palabra "apto" solo aparece en la dependencia general con RF-62
("garantiza que los datos incluidos en el paquete … sean aptos para IA"), no como campo ni como
regla de envío.

`apto_para_ia` es un atributo **de cada lectura de telemetría**, no del paquete. Lo calcula RF-62
y su fuente oficial es `modulo3.telemetria_calidad`, con la evaluación vigente (DEV-02, ver
`rf62_dev02_persistencia_aptitud.md`).

### 2. ¿Qué condiciones determinan que algo sea apto para IA?

Las define RF-62 con la regla de tres tramos, sobre el `indice_calidad` de la lectura. Está
implementada en `clasificar_desde_indice` y `derivar_aptitud`
(`src/telemetry/domain/entities/telemetria_calidad.py`):

| `indice_calidad` | Clasificación | `apto_para_ia` | `apto_para_nic41` |
|---|---|---|---|
| 80–100 | `APTO` | `true` | `true` |
| 40–79 | `APTO_CON_RESERVA` | `true` | `false` |
| 0–39 | `NO_APTO` | `false` | `false` |
| Sin índice | `INDETERMINADA` | `false` | `false` |

En las observaciones de visión (RFC-011), `estado_calibracion = SIN_LINEA_BASE` fuerza
`apto_para_ia = false`.

### 3. ¿Un contexto incompleto debe impedir el envío a M04?

**No.** RF-56 lo dice explícitamente:

- **E2, contexto multivariable incompleto:** "Se genera paquete con flag `contexto_incompleto`. Se
  reduce prioridad o confianza en inferencia. Se registra advertencia".
- **CA-3:** "debe marcarse con el flag `contexto_incompleto` **sin bloquear el envío**".

M04 es coherente con esto. RF-66, en su E4, dice que, sin contexto del activo, "la inferencia se
ejecuta sin contexto … se marca `contexto_incompleto = true`. La confianza reportada se reduce".

La restricción 1 de RF-56 ("no se permite enviar paquetes incompletos") se refiere a paquetes con
**campos obligatorios faltantes o inconsistencias estructurales** (E1), no al contexto
multivariable. Son dos situaciones distintas.

**Lo que hace el código hoy (`dev`) cumple con esto:**
- `ConsolidarEnviarPaqueteUseCase` marca `contexto_incompleto` sin bloquear el envío.
- El repositorio registra `CONTEXTO_INCOMPLETO` en la bitácora RF-63 al guardar el paquete.

### 4. ¿La regla pertenece a RF-62, a RF-56 o a ambos?

**A RF-62.** Ahí se calcula y se persiste la aptitud.

**Su consumidor en M04 es el entrenamiento, no la inferencia:**
- RF-71 (reentrenamiento) usa "solo registros con `apto_para_ia = true` (RF-62)", sobre el
  dataset de RF-59.
- También alimenta la línea base de visión de M09·RF-24.
- RF-56 no filtra por aptitud. Su único control de calidad propio es el flag `contexto_incompleto`.

**No hace falta coordinar los dos requisitos para TC-M03-094.** Si Análisis quisiera que
RF-56 también descartara paquetes no aptos, sería un cambio de la ficha y no un defecto. Además,
habría que definir de qué lectura sale la aptitud, porque el paquete se arma a partir del evento
Edge (RF-55), no de una lectura de RF-53.

### 5. ¿Qué debe verificar TC-M03-094?

El comportamiento de E2 y CA-3 de RF-56. Con un evento Edge al que le faltan variables mínimas de
su contexto (por ejemplo, solo `TEMPERATURA_AMBIENTAL`, sin `HUMEDAD_RELATIVA`):

1. Se genera el paquete con `contexto_incompleto = true`.
2. El paquete **no se bloquea**: queda en el flujo de envío normal. Hoy, con el stub del motor,
   queda `PENDIENTE` (ver #655 y #656).
3. Queda la advertencia `CONTEXTO_INCOMPLETO` en la bitácora RF-63.

**`test_tc_m03_094_no_apto_para_ia` debería retirarse de TC-M03-094.** Si se quiere cubrir la
aptitud, corresponde a los casos de RF-62: clasificación y aptitud por lectura en
`telemetria_calidad`, con los casos base de su CA-4.

## Observación adicional (fuera de la pregunta)

`ConsolidarEnviarPaqueteUseCase` asigna `estado_calidad = LECTURA_VALIDA` a todo paquete. RF-56
describe ese campo como "proveniente de RF-53", pero el paquete nace de un evento Edge sin una
lectura de RF-53 asociada. No se cambia aquí; se deja para que Análisis lo tenga en cuenta si
amplía el contrato con M04 (ver las diferencias de contrato documentadas en #655).

## Cambios

Ninguno en código ni en BD. Solo esta nota.
