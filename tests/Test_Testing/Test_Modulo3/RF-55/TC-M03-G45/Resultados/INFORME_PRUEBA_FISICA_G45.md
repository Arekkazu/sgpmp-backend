# Informe de prueba física — TC-M03-G45 / TC-M03-081

Fecha y hora de ejecución: **2026-10-31**, 02:38–02:45 hora local (UTC−5); sondas **07:38–07:45 UTC**.  
Caso: TC-M03-G45 / TC-M03-081 (RF-55.1, parser de lecturas inválidas).  
Modo: laboratorio autorizado. **Detenido en Fase 1** antes de inyectar datos.

Este documento **no** modifica `INFORME_EJECUCION_G45.md`, `AUDITORIA_FINAL_G45.md` ni el SKIPPED de `Resultados/TC-M03-081/`. No hay operaciones Git.

Evidencias nuevas: `Resultados/evidencias/laboratorio-2026-10-31/`.

---

## 1. Dictamen QA

**NO APTO para cierre físico de TC-M03-081.**  
**P1–P4 no se ejecutaron en el nodo.** No hay PASS/FAIL funcional de laboratorio.

Motivo: no se pudo comprobar disponibilidad de la Raspberry ni el estado del agente Edge **en esta corrida**. Sin SSH no hay historial local, journal ni confirmación de seriales vigentes. No se enviaron lecturas. No se afirma ausencia de eventos MQTT.

La auditoría offline previa sigue siendo la única evidencia de parser; **no** se reutiliza aquí como resultado físico.

---

## 2. Identificación del entorno de pruebas

Identidad **histórica** de laboratorio (G38/G41, 2026-10-30), usada solo como referencia de destinos a sondear:

| Elemento | Valor de laboratorio (no producción) |
|---|---|
| Hostname esperado | `RASPBERRY3B` |
| SSH histórico | `sgpmp@100.96.29.65` |
| LAN histórica | `192.168.40.5` → broker `:1886` |
| Servicio Edge | `edge-agent` (systemd) |
| Fuente en corridas previas | `EDGE_SOURCE=fake` (`FakeLoraSource`) |
| Seriales TEST | `RASPBERRY3B-TEST`, `QA-M03-272-A-088894` |
| Broker MQTT TEST | `149.130.169.209:1886` (HTTP de comandos: host `sgpmp-brokertest-…sslip.io`) |
| Topics | `sgpmp/<serial>/{telemetry,evento,heartbeat,status,command}` |

**Confirmado hoy (TCP, sin secretos):** el puerto MQTT `149.130.169.209:1886` está **abierto**. Ese host coincide con el broker **TEST** de G38/G41 (`brokertest`, no un endpoint de producción documentado).

**No confirmado hoy:** hostname `RASPBERRY3B`, proceso `edge-agent`, seriales, `EDGE_SOURCE`, umbrales en disco, historial local.

Criterio de parada aplicado: *si no se confirma Raspberry + agente + que los datos irían solo a prueba, no enviar datos.* El broker TCP TEST no basta para inyectar P1–P4.

---

## 3. Fase 1 — conexión y entorno

### 3.1 Raspberry

| Comprobación | Resultado | Evidencia |
|---|---|---|
| SSH `sgpmp@100.96.29.65:22` | **TimeoutError** (~20 s). Credencial pedida por `Get-Credential`; no persistida. | `fase1_ssh.json` |
| TCP `100.96.29.65:22` y `:1886` | Timeout 4 s | `fase1_conectividad.json` |
| TCP `192.168.40.5:22` y `:1886` | **Connection refused** (hay respuesta de red, no SSH/MQTT) | `fase1_conectividad.json` |
| `hostname` / `systemctl is-active edge-agent` | **No ejecutados** (sin sesión SSH) | — |
| Historial `/var/lib/sgpmp-edge/` | **No consultado** | — |
| Journal del agente | **No consultado** | — |

No se usó `sudo`, no se leyó `.env`, no se listaron secretos.

### 3.2 Servicio Edge RF-55

**No identificado en vivo.** En laboratorio previo era `edge-agent` v0.4.0-rc.2 con FakeLora. Hoy no hay PID ni ActiveState.

### 3.3 MQTT / Mosquitto

| Comprobación | Resultado |
|---|---|
| TCP broker TEST `149.130.169.209:1886` | **Abierto** (38 ms) |
| CONNECT + SUB a `sgpmp/RASPBERRY3B-TEST/#` y `sgpmp/QA-M03-272-A-088894/#` | Cliente paho arrancó tras `Get-Credential`; **no quedó CONNACK/SUBACK/payload en disco** (`fase1_mqtt_sub.json`) |
| PUBLISH | **No se envió** |

Sin CONNACK evidenciado **no** se declara “0 eventos”.

### 3.4 Cómo se consultaría el historial (no ejecutado)

En corridas G38: SSH `sgpmp` + `sudo -n -u sgpmp-edge` sobre `/var/lib/sgpmp-edge/` (umbrales/historial) y `journalctl -u edge-agent` sin volcar secretos. Hoy **bloqueado** por timeout SSH.

### 3.5 Estado inicial

**No registrado en el nodo.** Estado de esta estación de trabajo: sondas TCP anteriores; ningún cambio de configuración permanente.

---

## 4. Fase 2 — observación

No se activó captura continua de MQTT, journal ni historial: no había Raspberry alcanzable y la SUSCRIPCIÓN no dejó mensajes auditables.

No se modificó configuración ni se reinició ningún servicio.

---

## 5. Fase 3 — TC-M03-081 escenarios P1–P4

**No inyectados.** Datos de `scripts/casos_rf55.json` (firmware worktree `qa/rf55-validation-e618a75`) se documentan solo como **plan**, no como tráfico de laboratorio.

El inyector `inyectar_lecturas.py` usa `mqtt_host="qa.invalid"`: no habla con Mosquitto real. `FakeLoraSource` solo emite `uniform(min, max)` finito: no puede generar `null`, `"abc"` ni booleanos sin cambiar código, env o reiniciar el agente (prohibido en esta orden).

| ID | Dato inválido | Lecturas válidas en la misma captura | Esperado (offline / contrato) | Resultado físico |
|---|---|---|---|---|
| **P1** | `humedad_relativa` = `null` | `temperatura_ambiente` = 32.5 °C | HR → `LECTURA_INVALIDA`; T sin umbral en el caso → `ERROR_CONFIGURACION` (083), **no** DESVIACION por el nulo; `esperado` MQTT `[]` | **NO EJECUTADO** |
| **P2** | `ph` = `"abc"`; `oxigeno_disuelto` = `true` | ninguna válida | 2× `LECTURA_INVALIDA`; 0 eventos | **NO EJECUTADO** |
| **P3** | HR = 150 %; pH = 20 (rango físico) | T = 30 °C; OD = 3.9 | 2× `LECTURA_INVALIDA` (HR/pH); T y OD sin umbral en el caso → `ERROR_CONFIGURACION`; sin DESVIACION por el inválido; HR/pH pueden ir en telemetría cruda | **NO EJECUTADO** |
| **P4** | HR = `null` | T = 30 °C (umbrales globales del caso) | `LECTURA_INVALIDA` HR; `DESVIACION_SIMPLE` CRITICO de T (lectura válida sí se clasifica) | **NO EJECUTADO** |

Ningún escenario se marca PASS o FAIL: no hay historial, WARNING, telemetría ni topic `evento` de esta corrida.

Contraste con auditoría offline: **no aplicado** (haría falta el mismo lote en el agente vivo). EXIT 0 del inyector **no** se usó como evidencia física (el inyector no se lanzó contra el broker).

---

## 6. Fase 4 — MQTT real

| Pregunta | Respuesta de esta corrida |
|---|---|
| ¿Se capturó el topic `evento`? | No hay payload guardado |
| ¿Hubo evento de desviación indebido por P1–P4? | **No evaluable** (P1–P4 no se enviaron) |
| Topic / timestamp / payload | N/A |
| Telemetría vs evento | N/A |

Limitación: TCP al broker TEST sí; sesión MQTT auditada **no**. No se afirma que no hubo publicaciones.

---

## 7. Fase 5 — restauración y cierre

- No se inyectó tráfico de prueba; no hay lote P1–P4 pendiente en el bus por esta sesión.
- No se cambiaron umbrales, `config.json`, unit ni env.
- No se reinició `edge-agent`.
- No se borraron registros originales.
- Continuidad del agente **en el nodo: desconocida** (SSH caído). El broker TEST sigue aceptando TCP.

---

## 8. PASS / FAIL por escenario

| Escenario | Veredicto laboratorio 2026-10-31 |
|---|---|
| P1 | NO EJECUTADO |
| P2 | NO EJECUTADO |
| P3 | NO EJECUTADO |
| P4 | NO EJECUTADO |
| Criterios de aceptación RF-55.1 en nodo físico | **NO EVALUADOS** |

---

## 9. Limitaciones e incidencias

1. **SSH Tailscale `100.96.29.65:22` timeout.** Impide identificar la Pi, el servicio, el historial y los logs.
2. **LAN `192.168.40.5:22` refused.** No es un camino SSH usable hoy.
3. **MQTT SUB sin evidencia de CONNACK.** No se usa como prueba de silencio en `evento`.
4. **FakeLora + inyector `qa.invalid`:** aunque la Pi volviera, P1–P4 **no** entrarían al agente systemd sin un mecanismo de inyección autorizado distinto (código/env/restart: fuera de esta orden).
5. No se tocó producción. No se publicaron datos de prueba. Credenciales solo en cuadros Windows; no aparecen en este informe ni en JSON de evidencias.

---

## 10. Qué impide continuar

Para reanudar hace falta, en este orden:

1. Raspberry TEST alcanzable por SSH (`RASPBERRY3B`, usuario `sgpmp`) y `edge-agent` activo.
2. Confirmar seriales y broker `brokertest` / `149.130.169.209:1886` **desde el propio nodo**.
3. Un canal **autorizado** para inyectar `null` / texto / booleanos / fuera de rango físico en el agente vivo (FakeLora no los genera).
4. SUB MQTT con CONNACK/SUBACK guardados **antes** de cada escenario.
5. Lectura de historial `LECTURA_INVALIDA` y journal WARNING por escenario, sin alterar umbrales permanentes.

Hasta entonces el cierre de G45 permanece **offline (auditoría) + físico pendiente**.
