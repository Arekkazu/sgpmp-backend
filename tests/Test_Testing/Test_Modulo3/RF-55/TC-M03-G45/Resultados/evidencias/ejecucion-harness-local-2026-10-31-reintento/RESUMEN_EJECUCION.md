# Resumen — reintento harness G45 local 2026-10-31

Corrida **nueva** (esta carpeta). La evidencia del NameError permanece en `ejecucion-harness-local-2026-10-31/` (no se sobrescribió).

Corrección autorizada: `v` → `r.valor_crudo` en `harness_g45.py` L177. Sin cambios de Agent, escenarios ni umbrales.

| Campo | Valor |
|---|---|
| Intérprete | Python 3.13.7 |
| Exit | **0** |
| MQTT real / systemd / Raspberry | no |
| Tmp | `g45-harness-*` bajo `%TEMP%` (ya eliminado al salir) |

**G45 no se declara aprobado** (harness local + FakeLink; el nodo 794 no se tocó).

## Esperado vs obtenido

### P1 — PASS (081). Observación: 2 publishes del mismo evento T

| Campo | Esperado | Obtenido |
|---|---|---|
| Validación | HR inválida (`None`) | `valor no numérico o no finito: None`; T finita |
| Historial | `LECTURA_INVALIDA` HR + `DESVIACION_SIMPLE` T CRITICO | coincide; T `fuera_de_rango` umbral 7; `ruta` LOCAL / DIRECTA |
| Evento | 1× `DESVIACION_SIMPLE` CRITICO `UMBRAL_AMBIENTAL` | **2** payloads idénticos (tick 0 + flush 15 min **sin PubAck**) |
| Telemetría | solo T 32.5 | solo 32.5 |
| WARNING | 1× descartada HR | sí |

### P2 — PASS

| Campo | Esperado | Obtenido |
|---|---|---|
| Validación | pH `"abc"`, OD `true` inválidos | ambos no numéricos |
| Historial | 2× `LECTURA_INVALIDA` | sí |
| Evento | 0 | 0 |
| Telemetría | 0 | 0 |

### P3 — PASS (081). Misma observación de 2 eventos T

| Campo | Esperado | Obtenido |
|---|---|---|
| Validación | HR 150 y pH 20 fuera de rango físico | `[0,100]` y `[0,14]` |
| Historial | 2× inválida + DESVIACION T CRITICO | T `nivel_umbral=critico` |
| Evento | 1× T CRITICO | **2** iguales (sin PubAck) |
| Telemetría | T 30, HR 150, pH 20 | sí |

### P4 — PASS (081). Misma observación de 2 eventos T

| Campo | Esperado | Obtenido |
|---|---|---|
| Validación | OD `true` inválido; T 30 válida | coincide |
| Historial | inválida OD + DESVIACION T CRITICO | sí |
| Evento | 1× T CRITICO | **2** iguales (sin PubAck) |
| Telemetría | solo T 30 | sí |

El inválido **nunca** generó `DESVIACION_*` ni `ERROR_CONFIGURACION`. Historial de desviación queda `PENDIENTE` porque FakeLink no entrega PUBACK (no es ENVIADO).

## Conteos pedidos

| Categoría | Cantidad | IDs |
|---|---|---|
| **PASS** (criterio TC-M03-081 / RF-55.1 en este harness) | **4** | P1, P2, P3, P4 |
| **FAIL funcional** (clasificación falsa del dato inválido) | **0** | — |
| **No evaluados** | **0** | — |

Desvío respecto a la matriz que pedía **exactamente 1** mensaje `evento` en P1/P3/P4: se vieron **2** por reintento de buffer al segundo `tick`, no por el nulo/texto/bool. No se cuenta como FAIL 081.
