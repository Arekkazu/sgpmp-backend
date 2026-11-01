# Cierre documental y auditoría final — TC-M03-G45

Fecha de consolidación: **2026-10-31**.  
Fuente de verdad del resultado local: `Resultados/evidencias/ejecucion-harness-local-2026-10-31-reintento/`.  
Este archivo es **nuevo**. No modifica `INFORME_EJECUCION_G45.md`, `AUDITORIA_FINAL_G45.md`, `INFORME_PRUEBA_FISICA_G45.md`, `PROPUESTA_HARNESS_G45.md`, el SKIPPED de `TC-M03-081/` ni las carpetas de evidencia históricas.

No se ejecutó Git. No se publicó a `laura`. No se tocó la Raspberry ni MQTT.

---

## 1. Identificación

| Campo | Valor |
|---|---|
| Grupo | TC-M03-G45 |
| Caso | TC-M03-081 |
| Requisito | RF-55.1 (clasificación en el nodo; parser de lecturas inválidas) |
| Relacionados | INC-M03-156-G45; contrato evento Edge §2.1; TC-M03-083 (`ERROR_CONFIGURACION` por umbral ausente, **distinto**) |
| Firmware de referencia | `.worktrees/sgpmp-rf55-validation/raspberry/` (`qa/rf55-validation-e618a75`) |

---

## 2. Objetivo y alcance

**Objetivo:** comprobar que valores nulos, no numéricos, booleanos o fuera de rango físico se descartan **antes** de umbrales, se registran como `LECTURA_INVALIDA` (historial + WARNING) y **no** generan evento de desviación propio, mientras las lecturas válidas de la misma captura sí se clasifican.

**Dentro de alcance (cerrado aquí):** harness local con `Agent` real, `lecturas_invalidas`, `evaluar_lote`, historial SQLite temporal y `FakeLink` en memoria. Escenarios P1–P4 de `escenarios_p1_p4.json`.

**Fuera de alcance (no cerrados):** `edge-agent` systemd en `RASPBERRY3B`; Mosquitto TEST; pytest backend G45 (SKIPPED 2026-10-25 vigente); inyector `casos_rf55.json` P1/P3 con `umbrales: []` (mezcla 083).

---

## 3. Entorno y herramientas

| Elemento | Uso |
|---|---|
| Estación | Windows, Python **3.13.7** |
| PYTHONPATH | worktree firmware `raspberry/` |
| Script | `evidencias/harness-propuesto-2026-10-31/harness_g45.py` |
| Entrada | `escenarios_p1_p4.json` |
| Agent | `edge_agent.agent.Agent` (producción del firmware, no reimplementado) |
| Transporte | `FakeLink` (lista en memoria; **no** paho, **no** broker) |
| Persistencia | `tempfile.TemporaryDirectory` `g45-harness-*` (no `/var/lib/sgpmp-edge`) |
| Umbral | id **7** temperatura 18–32 °C, copiado de `scripts/casos_rf55.json` (no inventado; sin umbrales HR/pH/OD) |

---

## 4. Resumen P1–P4 (reintento, exit 0)

| ID | Entrada | Historial | Evento (FakeLink) | Telemetría | WARNING |
|---|---|---|---|---|---|
| **P1** | T=32.5 + HR `null` | `LECTURA_INVALIDA` HR + `DESVIACION_SIMPLE` T **CRITICO** (`fuera_de_rango`, umbral 7) | 2× mismo `DESVIACION_SIMPLE` CRITICO T | solo 32.5 | 1× HR `None` |
| **P2** | pH `"abc"` + OD `true` | 2× `LECTURA_INVALIDA` | **0** | **0** | 2× |
| **P3** | T=30, HR 150, pH 20 | 2× inválida (rango físico) + DESVIACION T **CRITICO** (`critico`) | 2× mismo evento T | T 30, HR 150, pH 20 | 2× |
| **P4** | T=30 + OD `true` | inválida OD + DESVIACION T **CRITICO** | 2× mismo evento T | solo 30 | 1× OD `True` |

Ningún inválido produjo `DESVIACION_*` ni `ERROR_CONFIGURACION` propios. Las temperaturas válidas sí.

---

## 5. Resultado de ejecución

| Categoría | Cantidad |
|---|---|
| **PASS** (criterio TC-M03-081 en el harness) | **4** (P1, P2, P3, P4) |
| **FAIL funcional** | **0** |
| **No evaluados** | **0** |

Harness local: **APROBADO** (exit 0 del reintento; contraste con `resultado_P1.json` … `resultado_P4.json`).

---

## 6. Evidencias (dos intentos independientes)

### Primer intento — no evaluó P1–P4

Ruta: `Resultados/evidencias/ejecucion-harness-local-2026-10-31/`  
Exit **1**. `NameError: name 'v' is not defined` en el dict de reporte (`for r, motivo in invalidas` usaba `v`). Sin `resultado_local.json`. Conservado; no se sobrescribió.

### Reintento — base del cierre local

Ruta: `Resultados/evidencias/ejecucion-harness-local-2026-10-31-reintento/`  
Exit **0**. Corrección autorizada: `v` → `r.valor_crudo`. Archivos: `stdout.txt`, `exit_code.txt`, `python_version.txt`, `resultado_local.json`, `resultado_P1.json`–`resultado_P4.json`, `RESUMEN_EJECUCION.md`.

Antecedentes de laboratorio (no son este cierre): `INFORME_PRUEBA_FISICA_G45.md`, `REINTENTO_CONEXION_RASPBERRY.md`, `laboratorio-2026-10-31/`. Pytest offline 51 passed y SKIPPED backend **no** se reabren aquí.

---

## 7. Observación: duplicación de eventos (P1, P3, P4)

FakeLink **publicó dos veces** el mismo evento de temperatura válida.

Causa observada: el harness hace `agent.tick(T0)` y luego `agent.tick(T0 + 15*60)`. Los eventos salen por el buffer; FakeLink devuelve `mid` pero **no hay PUBACK**. El segundo tick vuelve a hacer flush del mismo lote.

- Historial: **una** fila `DESVIACION_SIMPLE`, estado **`PENDIENTE`** (no `ENVIADO`).
- Payloads FakeLink: dos copias idénticas (`clasificacion_rf55=DESVIACION_SIMPLE`, `severidad=CRITICO`, `regla_aplicada=UMBRAL_AMBIENTAL`).
- **P2 no duplica** (cero eventos).

**No es FAIL funcional de RF-55.1:** el dato inválido no se clasificó. Queda como **observación técnica pendiente de análisis independiente** (FakeLink / PUBACK / segundo tick). **No se cambió código** para ocultarla ni para “arreglar” el conteo.

---

## 8. Limitaciones del harness local

- No es el proceso systemd PID del laboratorio (`edge-agent` en `RASPBERRY3B`).
- `FakeLink` no es Mosquitto; los campos MQTT de `Settings` no abren socket.
- Umbral solo temperatura id 7; HR/pH/OD sin umbral a propósito (P3 omite OD para no mezclar TC-M03-083).
- Variable de laboratorio viva `Humedad Relativa` 71–73 % **no** se usó.
- `FuenteFija` inyecta `Reading`; FakeLora del servicio **no** puede emitir `null`/texto/bool.
- Duplicado §7 es artefacto de observación, no evidencia de broker.

---

## 9. Validaciones físicas pendientes

Para desbloquear el cierre integral hace falta, con autorización aparte:

1. Raspberry TEST identificada (`RASPBERRY3B`) con `edge-agent` activo.
2. Canal autorizado para meter P1–P4 en **ese** proceso (hoy `EDGE_SOURCE=fake` no genera inválidos de formato).
3. SUB MQTT real (CONNACK/SUBACK guardados) a `sgpmp/<serial>/evento` y `telemetry`, sin PUBLISH de comando no autorizado.
4. Historial `/var/lib/sgpmp-edge/historial.db` en solo lectura, contrastado por escenario.
5. Análisis aparte de la duplicación FakeLink vs. comportamiento con PUBACK real.

Hasta entonces **no** se afirma que el agente de la Pi ni MQTT real hayan pasado G45.

---

## 10. Conclusión y estado final

| Superficie | Estado |
|---|---|
| **Harness local** (Agent real + FakeLink + tmp) | **APROBADO** — 4 PASS, 0 FAIL funcionales, 0 no evaluados |
| **Validación en Raspberry Pi** | **PENDIENTE** |
| **Validación con MQTT real** | **PENDIENTE** |
| **Cierre integral TC-M03-G45 / TC-M03-081** | **BLOQUEADO** hasta las validaciones físicas |

El parser RF-55.1, en el `Agent` del firmware y en este harness, trata P1–P4 como se exige para 081. Eso **no** equivale a prueba de campo ni a producción.
