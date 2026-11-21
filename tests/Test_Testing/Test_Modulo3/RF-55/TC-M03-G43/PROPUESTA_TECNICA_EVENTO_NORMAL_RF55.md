# Propuesta técnica — evento estructurado NORMAL (RF-55)

**Estado:** propuesta. **No implementada.** No altera código, pruebas, evidencias ni el PASS offline de TC-M03-076.

Firmware de referencia: `.worktrees/sgpmp-rf55-validation`, `e618a75`.  
Broker: `_consultas/BROKER-MQTT-SGPMP` (`evento_edge` reenvía, no clasifica).  
Backend: `sgpmp-backend` `RecibirEventoEdgeUseCase` / `RecibirEventoEdgeDTO`.

RF-55 v2.0 (CA-6, CA-8, CA-10) se usa según la auditoría G43; el fichero SRS **no** está en este repo (limitación).

---

## 1. Resumen ejecutivo

El Edge **ya clasifica** la banda `normal` y la anota en `historial.db`. **No** construye `EventoEdge` ni lo saca por el outbox `KIND_EVENTO`. CA-6 (evento también en condición normal) y CA-8 (envío al sistema central con conectividad) no se cumplen para TC-M03-076.

**Recomendación:** emitir `EventoEdge` con `clasificacion=NORMAL` en `evaluar_simple` (misma fábrica `nuevo_evento` / `a_payload` / `_encolar_evento` que las desviaciones). El broker sigue solo transportando. El backend **ya acepta y persiste** `NORMAL` y **no** consolida paquete RF-56 ni alerta RF-57.

**Riesgo principal comprobado:** `IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO` (60/min, no aplica a `severidad=CRITICO`). Un NORMAL por cada captura puede saturar el límite y devolver 429; el outbox retiene y reintenta. Hace falta una decisión de tasa **antes** de producción.

MQTT es el transporte actual, no el enunciado de CA-8.

---

## 2. Situación actual comprobada

| Pieza | Archivo | Hecho |
|---|---|---|
| Clasificador | `evaluador.py` `evaluar_simple` L104–155 | Banda `normal` → `return None` (L144–145) |
| Lote | `evaluar_lote` | Solo añade `EventoEdge` no nulos |
| `normales()` | L238–254 | Lecturas `normal` que no están en ningún evento → historial |
| Historial NORMAL | `historial.py` `registrar_normal` L133–153 | `id_evento=None`, `ruta=LOCAL`, `estado=LOCAL` |
| Evento desviación | `evento.py` `nuevo_evento` / `a_payload` | `clasificacion_rf55`, `variables_involucradas`, timestamps, `origen`, `estado_conectividad`; `id_evento` en `metadata_edge`; `severidad` solo si no es `None` |
| Constante | `evento.py` L19 | `NORMAL = "NORMAL"` (existe; no se usa en `evaluar_simple`) |
| Encolado | `agent.py` `_encolar_evento` L510–547 | Buffer `KIND_EVENTO`, topic `sgpmp/<serial>/evento`, historial DIRECTA/BUFFER |
| Captura | `_capturar` L450–456 | Desviaciones → `_encolar_evento`; normales → `registrar_normal` |
| Buffer RF-54 | `buffer.py` | Outbox SQLite; **nunca descarta** ACK ni evento al llenarse (L13–15, L192); borra con PUBACK |
| Flush | `_flush` L549–582 | Con conexión publica; eventos `due_at=now`; origen BUFFER_LOCAL si > gracia |
| Broker | `reenvio_nodo.evento_edge` | Añade `device_id`/`sensor_id`; **no** clasifica |
| Backend DTO | `recibir_evento_edge_dto.py` L36, L75–80 | `NORMAL` es valor válido |
| Backend use case | L128–129, L210, L161–176 | Tasa si no CRITICO; persiste; **no** envía M04 si NORMAL; **no** alerta si no es desviación |
| `tipo_evento` BD | `clasificacion_a_tipo_evento_bd` | NORMAL → `DATOS_PROCESADOS` |
| Dedup backend | repositorio / use case | **No** se halló clave por `metadata_edge.id_evento` |

Pruebas firmware que **afirman** el comportamiento actual: `test_evaluador_simple.py` (`test_dentro_de_rango_no_emite`), `test_historial.py` (`test_normal_se_registra_localmente_y_no_se_publica`), `test_tc_m03_g43.py` 076.

---

## 3. Brecha frente a RF-55 (076)

Según RF-55 v2.0 incorporado en la auditoría (CA-6, CA-8, CA-10; archivo SRS no local):

| Exigencia | Hoy |
|---|---|
| CA-6 evento estructurado también si NORMAL | No: `None` + historial LOCAL |
| CA-8 envío al sistema central con conectividad | No hay evento que enviar |
| CA-10 persistencia local de **eventos** | Historial sin `id_evento`; no es el outbox de evento |

El PASS offline **no** cubre esta brecha.

---

## 4. Arquitectura y flujo actual

```
lectura → telemetría KIND_TELEMETRY (siempre, valor finito)
       → evaluar_lote
            desviación / error  → EventoEdge → KIND_EVENTO → MQTT …/evento
                                → broker POST /iot/eventos-edge
            banda normal        → registrar_normal (solo historial)
```

Con desconexión: eventos en outbox (`ruta=BUFFER`); telemetría también. Heartbeat **no** usa el buffer (`buffer.py` L8–9).

---

## 5. Alternativas

| Alt. | Dónde | Pros | Contras |
|---|---|---|---|
| **A** | `evaluar_simple` devuelve `EventoEdge(NORMAL)` | Un solo pipeline; `_encolar_evento` y RF-54/flush sin duplicar | Rompe tests que esperan `None`; hay que retirar o acotar `registrar_normal` |
| B | En `_capturar`, tras `normales()`, `nuevo_evento` + `_encolar_evento` | `evaluar_simple` intacto | Dos caminos de creación; fácil duplicar historial |
| C | Publicar NORMAL solo desde telemetría en backend | No toca firmware | El backend **no** clasifica (comprobado); contradice RF-55 en Edge |
| D | Broker inventa NORMAL | El broker **no** clasifica (`reenvio_nodo.py`) | Fuera de arquitectura |

**Descartadas C y D** por código comprobado.

---

## 6. Solución recomendada

**Alternativa A.**

1. En el `else` actual (banda `normal`, L144–145), llamar `nuevo_evento(ev.NORMAL, None, [reading], metadata={regla_aplicada, id_umbral, version_umbral, nivel_umbral: "normal"})`.
2. `evaluar_lote` ya reenviará ese evento.
3. Dejar de llamar `registrar_normal` para esas lecturas: `normales()` las verá en `eventos` y no duplicará. Opcional: deprecar `registrar_normal` o usarlo solo como respaldo si el historial de eventos fallara.
4. Historial de NORMAL pasa por `registrar_evento` (DIRECTA/BUFFER, con `id_evento`), igual que desviaciones.
5. **No** cambiar `_encolar_evento` para desviaciones (salvo pruebas de carga).
6. Broker: sin cambios de clasificación.
7. Backend: persistencia NORMAL ya existe; valorar tasa e idempotencia (etapas).

Justificación: reutiliza `EventoEdge`, `KIND_EVENTO`, PUBACK y RF-54; no reimplementa reglas; RF-56/57 ya ignoran NORMAL para paquete/alerta.

---

## 7. Contrato de evento propuesto

Reutilizar `a_payload` **sin campos nuevos**. Comparación con lo que el código ya emite:

| Campo RF / pregunta | En payload firmware (`a_payload`) | NORMAL propuesto | DESVIACION_* |
|---|---|---|---|
| Identificador | `metadata_edge.id_evento` (`edge-evt-{uuid}`) | Igual | Igual |
| `sensor_id` | **No** en el JSON del Edge; el **broker** lo inyecta | Igual | Igual |
| `tipo_evento` | **No** en MQTT; el backend deriva de `clasificacion_rf55` | `DATOS_PROCESADOS` en BD | `ALERTA_GENERADA` |
| Clasificación | `clasificacion_rf55` | `"NORMAL"` | SIMPLE / COMPUESTA |
| Variables | `variables_involucradas[]` (`tipo_variable`, `valor`, `unidad`, timestamps, `serial`, `sensor` opcional) | Una lectura | Una o más |
| Severidad | Omitida si `None` (L92–93) | **Omitida** | LEVE/MODERADO/CRITICO |
| Captura / procesamiento | `timestamp_captura`, `timestamp_procesamiento_edge` | Igual | Igual |
| Origen | `TIEMPO_REAL` o reescrito en flush | Igual | Igual |
| Conectividad | `estado_conectividad` | Igual | Igual |

No añadir `tipo_evento` ni `sensor_id` en firmware si el contrato vigente los resuelve en broker/backend (comprobado).

Opcional alineado a INC-M03-111 (ya en DTO, no obligatorio): `valor_evaluado`, `umbral_min_aplicado`, `umbral_max_aplicado`. Hoy `a_payload` **no** los pone; no se inventan como obligatorios de firmware hasta que el contrato Edge los liste.

---

## 8. Impacto RF-54, RF-56, RF-57

**RF-54:** el outbox ya no descarta eventos. Más filas (1 NORMAL + 1 telemetría por captura). Riesgo: buffer `LLENO` más frecuente; se sacrifican **lecturas** viejas, no eventos. Eventos >72 h se descartan (`_flush`).

**RF-56:** `POST /iot/eventos-edge` guarda NORMAL; `_enviar_a_m04` es falso (L210). Sin paquete de inferencia. Tasa 60/min (L128–129) **sí aplica** (NORMAL no lleva `severidad=CRITICO`).

**RF-57:** alerta solo si desviación + severidad (L223–227). NORMAL no dispara alerta.

---

## 9. Impacto broker y backend

**Broker:** reenvío inalterado; más mensajes `evento`. Cola BRK-09 trata todo `evento` como admisión crítica (`prioridad.py`, investigación previa). Volumen NORMAL puede adelantar telemetría.

**Backend:** acepta y **persiste** NORMAL (DTO + `guardar`). Procesa: mapea `tipo_evento`, latencia SLA, bitácora solo si hay tipo en `_EVENTO_BITACORA_RF55` (NORMAL puede no auditar como desviación — no se verificó el mapa aquí; limitación menor). **No** hay idempotencia por `id_evento` del Edge: un reintento HTTP tras 201 perdido **duplicaría** filas. 429 conserva el evento en el Edge.

---

## 10. Matriz de pruebas (propuesta; no ejecutada)

Leyenda: U = unitario firmware; E = Edge+mock MQTT (Harness); I = integración broker+backend (lab).

| # | Escenario | Tipo | Objetivo | Precondiciones | Procedimiento | Esperado | Componentes |
|---|---|---|---|---|---|---|---|
| 1 | NORMAL con conectividad | U+E | CA-6+CA-8 (mock) | Umbral válido; FakeLink up | Valor en banda `normal`; `tick` | `evaluar_simple` → EventoEdge NORMAL; `sgpmp/<serial>/evento`; historial DIRECTA; telemetría aparte | evaluador, agent, FakeLink |
| 2 | NORMAL sin conectividad | E | RF-54 | `connected=False` | Igual | KIND_EVENTO en outbox; historial BUFFER/PENDIENTE; **no** publish | buffer, historial |
| 3 | Reconexión y reenvío | E | CA-8 diferido | Caso 2 | `Connected` + PUBACK | Un publish; ENVIADO; outbox sin ese evento | flush, PubAck |
| 4 | Sobre máximo | U+E | No regresión 077 | Fixture G43 | valor > valor_max | DESVIACION_SIMPLE CRITICO `fuera_de_rango` | evaluador |
| 5 | Bajo mínimo | U+E | No regresión 078 | Igual | valor < valor_min | Igual que 4 | evaluador |
| 6 | Duplicados en reenvío | E (+ I si hay 429) | Un PUBACK / una fila o idempotencia | Inflight timeout o 429 | Reenviar mismo `id_evento` | Firmware: una fila outbox. Backend: **hoy duplicaría** — prueba I debe documentar gap o exigir unique | buffer, use case |
| 7 | Compatibilidad compuestos | U | RF-55.2 | Regla que suprime simples | Lote mixto | COMPUESTA inalterada; NORMAL solo lecturas no cubiertas | evaluar_lote |
| 8 | Trazabilidad | E | CA-10 | Historial on | Inspeccionar `id_evento` | NORMAL con id, no solo LOCAL sin id | historial |

G43 pytest backend sigue SKIPPED hasta motor o contrato de import. Integración Mosquitto/Raspberry: **fuera de esta propuesta de código**; lab autorizado aparte.

Actualizar (cuando se implemente, no ahora): `test_dentro_de_rango_no_emite`, `test_normal_se_registra_localmente_y_no_se_publica`, `test_tc_m03_g43.py` 076.

---

## 11. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| Saturación 60 eventos/min | Decidir: emitir NORMAL cada captura vs solo **transición** a/desde normal; o subir límite; o exceptuar NORMAL del rate (cambio backend, no CA) |
| CONTRATO “NORMAL nunca se emite” | Actualizar contrato Edge **junto** al código; contradice CA-6 v2.0 |
| Doble historial (`registrar_normal` + `registrar_evento`) | Quitar el primero cuando A esté activo |
| Buffer lleno | Capacidad / frecuencia de captura; eventos no se tiran |
| Duplicados HTTP | Idempotencia por `metadata_edge.id_evento` (backend, no comprobada hoy) |
| Tests offline 076 | Redefinir oráculo a “hay EventoEdge NORMAL”; no reescribir PASS histórico 2026-10-30 |

---

## 12. Dependencias y decisiones pendientes

1. ¿NORMAL en **cada** captura o solo en **cambio de banda**? CA-6 no se cita aquí con texto de archivo; “cuando se detecte” puede ser por muestra o por transición. **El análisis de capacidad y la decisión QA están en la sección «Política de emisión NORMAL» (al final).** La política **no** queda aprobada.
2. Tasa `IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO` vs frecuencia de captura.
3. Versionar SRS RF-55 v2.0 en el repo (líneas/páginas).
4. ¿Rellenar `valor_evaluado` / umbrales en payload? (DTO opcional.)
5. Idempotencia backend.
6. Autorización para **cambiar** tests firmware que hoy exigen `None`.

---

## 13. Plan por etapas (sin ejecutar)

| Etapa | Qué | Criterio de cierre |
|---|---|---|
| 0 | Decisión tasa + CONTRATO | Acta |
| 1 | `evaluar_simple` + unitarios firmware | Evento NORMAL; 077/078 iguales |
| 2 | Agent: un solo encolado; historial con `id_evento` | Harness 1–3 |
| 3 | Pruebas 4–5–7 (regresión) | Sin cambio de payload desviación |
| 4 | Backend: observar 60/min; opcional idempotencia | Lab o test integración |
| 5 | QA G43 076 con mock/lab | Distinto del PASS offline actual |

Etapa 5 **no** modifica el informe SKIPPED 2026-10-25 ni el PASS offline 2026-10-30; sería una corrida nueva.

---

## Limitaciones de esta propuesta

- SRS RF-55 v2.0 no está como fichero en el workspace.
- No se inspeccionó cada test de `test_reglas_compuestas.py` línea a línea.
- No se midió `EDGE_FRECUENCIA_CAPTURA` de la Raspberry (prohibido conectar).
- Broker `prioridad.py` no se reabrió en esta pasada; se usa el hallazgo de la investigación G43 broker.

---

## Política de emisión NORMAL: análisis de capacidad y decisión QA

**Estado de la decisión:** bloqueada. No hay evidencia suficiente para aprobar A, B, C ni D antes de un acta de producto sobre el significado de CA-6. Esta sección no implementa firmware.

Hechos y hipótesis van etiquetados. Lo no hallado en código o env de lab se declara limitación.

### 1. Evidencias y archivos consultados

| Área | Archivo | Qué se comprobó |
|---|---|---|
| Clasificador | `.worktrees/sgpmp-rf55-validation/raspberry/edge_agent/reglas/evaluador.py` | `evaluar_simple` → `None` en banda `normal` (L144–145). `normales()` L238–254: comentario explícito de no publicar por rate limit. `evaluar_lote` llama `evaluar_simple` **una vez por lectura** de la captura (L329–334). `MAX_REGLAS_ACTIVAS = 5`. |
| Contrato Edge | `docs/CONTRATO_EVENTO_EDGE.md` L102 | «`NORMAL` nunca se emite: un evento por muestra saturaría el rate limit del backend». Es contrato de implementación, no el texto de RF-55 v2.0. |
| Agenda de captura | `agent.py` `_Schedule`, `tick` L218–233 | Un ciclo de captura **por serial** de `EDGE_SERIALS`. Intervalo: `frecuencia_captura_min * 60` segundos. Primera captura al arrancar (`next_capture=now` en `_initial_schedule`). Presupuesto 0,2 s por vuelta (`PRESUPUESTO_CAPTURAS_S`). |
| Frecuencia | `config.py` L7–8, L156; `commands.py` L99–108 | `EDGE_FRECUENCIA_CAPTURA_MIN` es **obligatoria, sin default en código**. El comando RF-23 acepta cualquier entero **> 0** (unidad: minutos). No hay tope máximo en firmware. |
| Defaults de prueba / lab | `raspberry/tests/conftest.py`; `test_config.py`; G41 `RESULTADO_PREPARACION_PREVIA_G41.md` | Tests: 10 min. Lab G41 documentado: `EDGE_FRECUENCIA_CAPTURA_MIN=10`, `EDGE_SERIALS` con **2** seriales. **No** se leyó el env vivo de la Raspberry (conexión prohibida). |
| Lecturas por captura | `sources.py` `FakeLoraSource.read`; `lora/protocol.py` L25–28 | Fake: **una lectura por entrada** de `EDGE_FAKE_VARIABLES` (lista sin tope en código). LoRa: `MAX_MEASUREMENTS = (MAX_PAYLOAD_LEN - 3) // 5` con `MAX_FRAME_LEN=51` → **8** mediciones por trama TELEMETRIA. Máscara de sensores nombrados: 4 bits (`DHT22`, `DS18B20`, `MPU6050`, `MAX30102`). |
| Estado de bandas | `evaluador.py` RF-55.1; `ventana.py` L1–6; `agent.py` L137–147 | RF-55.1 **no** guarda la última banda. Cada captura reclasifica. `EstadoCompuestas` (RF-55.2) y `_errores_reportados` están **solo en memoria**; tras reinicio arrancan vacíos. Umbrales y `frecuencia_captura_min` sí persisten (`config.json` / stores). |
| Encolado | `agent.py` `_encolar_evento`; `buffer.py` | Outbox SQLite `KIND_EVENTO`; sobrevive reinicio. PUBACK borra la fila. Timeout inflight 300 s (`_INFLIGHT_TIMEOUT_S`): la fila **vuelve a publicarse** (comentario L70–71: espera que el servidor descarte por `event_id`). Eventos >72 h se descartan. |
| Límite backend | `recibir_evento_edge_use_case.py` L60–87, L127–129; `src/shared/rate_limit.py`; `.env.example` | Ver §3. |
| 429 | `test_inc_m03_121_g64_rafagas_eventos_edge.py`; `test_rf56_dev17_paquetes_pendientes.py` `test_e6_*` | 201 exactos al límite; 429 + `LIMITE_TASA_EXCEDIDO`; **no persiste** lo rechazado. CRITICO no cuenta. |
| Dedup | `evento_edge_model.py`; `recibir_evento_edge_use_case.py`; DTO | PK `id_evento_edge_computing` (identity). **No** hay unique sobre `metadata_edge.id_evento`. Telemetría sí tiene `idempotency_key`; eventos-edge **no**. |
| Broker | `_consultas/BROKER-MQTT-SGPMP/app/services/reenvio.py` L9–11, L27–32; `reenvio_nodo.py`; `backend/client.py` | POST `/iot/eventos-edge` **sin cola ni reintento**. HTTP error (incl. 429) → log y `ok=False`. El Edge ya pudo haber recibido PUBACK MQTT. |
| CA-6 | `AUDITORIA_CRITERIO_ACEPTACION_TC_M03_076.md` | «Generar un evento cuando se detecte una condición normal o anómala». SRS v2.0 **no** está como fichero; no hay página/línea. |

**No consultado en esta pasada (limitación):** env real `/etc/sgpmp/edge-agent.env` de Raspberry; réplicas/workers de producción del backend; `prioridad.py` del broker (se reutiliza el informe G43).

### 2. Cadencia de `evaluar_simple` y fórmula de capacidad

Por cada serial cuya agenda vence:

1. `source.read(serial)` → `V` lecturas.
2. `evaluar_lote` → `evaluar_simple` **V** veces (menos inválidas y las suprimidas por RF-55.2).
3. Hoy, las NORMAL no generan `EventoEdge`.

Frecuencia de ese lote:

```
capturas_por_minuto(serial) = 1 / F
```

`F = frecuencia_captura_min` (entero ≥ 1). No hay default compilado: el valor operativo es el de `EDGE_FRECUENCIA_CAPTURA_MIN` o el último comando RF-23 persistido.

Si se emitiera un evento NORMAL **por cada lectura clasificada** (política A):

```
eventos_NORMAL_por_minuto(serial) = V_normal / F
```

`V_normal` ≤ lecturas con umbral RF-17 usable en banda `normal` en esa captura. El límite backend **también cuenta** `DESVIACION_SIMPLE`/`COMPUESTA`/`ERROR_CONFIGURACION` cuya `severidad` **no** sea exactamente `"CRITICO"`, y los reenvíos RF-54 (mismo POST).

```
eventos_que_consumen_límite(serial) ≈ (V_no_critico) / F   +   ráfaga de outbox al reconectar
```

El contador es **por `dto.serial`**, no por sensor ni por Raspberry-gateway.

### 3. Límite de 60 eventos/minuto (hechos)

| Pregunta | Hecho comprobado | Hipótesis / no comprobado |
|---|---|---|
| Dónde | Constante `LIMITE_EVENTOS_POR_MINUTO = 60` en el use case. Override `IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO`. Ventana 60 s deslizante (`registrar_llamada(..., 60)`). | Valor de entorno en el despliegue real no leído. |
| Alcance | Clave `rf56_eventos_edge:{dto.serial}`. **Por serial del dispositivo**, no por IP, no por usuario, no global, no por `sensor_id`. | Con **N workers** el comentario de `rate_limit.py` dice que el tope **se multiplica** (contador en memoria por proceso). No se inspeccionó el número de workers de producción. |
| Tipos | El `if` es `dto.severidad != "CRITICO"`. Aplica a **cualquier** `clasificacion_rf55` (NORMAL, SIMPLE, COMPUESTA, ERROR) si la severidad no es CRITICO. | El DTO **no** prohíbe `clasificacion_rf55=NORMAL` con `severidad=CRITICO`; eso saltaría el límite. El firmware omite severidad en NORMAL (`a_payload`). |
| Excepción CRITICO | No llama `registrar_llamada`. G64: 30 CRITICO tras saturar → 201; un no-crítico siguiente → 429. | «CRITICO» es el string de severidad, no la clasificación RF-55. `fuera_de_rango` en firmware usa `_SEVERIDAD` → CRITICO: esas desviaciones **no** contarían. LEVE/MODERADO sí. |
| Respuesta | `TooManyRequestsError` → HTTP **429**, `code=LIMITE_TASA_EXCEDIDO`, headers `Retry-After`, `RateLimit-Limit`, `RateLimit-Remaining=0`, `RateLimit-Reset`. Cuerpo con mensaje genérico de tasa. Lo rechazado **no** se inserta (G64). | — |
| Reintentos Edge | Outbox retiene hasta PUBACK MQTT. Un 429 ocurre **después** del broker, no en el Edge. | El Edge **no** ve el 429. |
| Reintentos broker | `reenvio.py`: **sin cola ni reintento**. 429 = evento **perdido en el salto broker→backend**. El comentario atribuye el resguardo a RF-54 en el Edge, que ya soltó el mensaje al PUBACK. | — |
| RF-54 / reconexión | Mismo endpoint, misma clave por serial. Una ráfaga de outbox **consume** el cupo. | Tamaño de ráfaga = filas `KIND_EVENTO` pendientes; no medido en lab. |
| Dedup `id_evento` | No hay unique ni lookup por `metadata_edge.id_evento`. Re-POST del mismo payload crea **otra** fila. El comentario del Edge L70–71 («el servidor descarta por `event_id`») **no** se cumple en este use case. | `event_id` de ACK RF-23 es otro flujo. |

### 4. Cálculos (con premisas explícitas)

No se inventa `F` ni `V` de producción. Rangos derivados del código y de lab **documentado**:

| Escenario (premisa) | F (min) | V por captura y serial | Política A: NORMAL/min·serial | ¿Cabe en 60? |
|---|---|---|---|---|
| Tests / G41 documentado, 1 variable | 10 | 1 | 0,10 | Sí, holgado |
| G41, 2 variables fake en **el mismo** serial | 10 | 2 | 0,20 | Sí |
| Mínimo legal del comando (`F=1`), 1 variable | 1 | 1 | 1 | Sí |
| `F=1`, tope LoRa 8 mediciones, todas NORMAL | 1 | 8 | 8 | Sí (un serial) |
| `F=1`, 8 vars, **más** desviaciones no-CRÍTICAS y ERROR | 1 | 8+ | ≥8 + otros | Cabe salvo ráfaga |
| Fake sin tope: 70 variables, `F=1`, un serial | 1 | 70 | 70 | **No** (10×429/min en régimen, más pérdida broker) |
| Ráfaga RF-54: 200 NORMAL pendientes, reconexión | — | — | hasta 200 POST en segundos | Primeros 60 → 201; resto 429 **y el broker no reintenta** |

Varios sensores / varios seriales:

- Varias variables en **un** serial **comparten** el cupo 60.
- Varios seriales tienen **cupos independientes**.
- La Raspberry puede listar N seriales (`EDGE_SERIALS`); el código no fija un máximo de seriales (nodos LoRa v2: un `node_id` por serial, colisión de hash rechazada).

**Conclusión de capacidad:** con `F≥1` min y `V≤8` (LoRa) la política A **no satura** el 60/min **en régimen**. El riesgo de 60/min aparece en (1) `EDGE_FAKE_VARIABLES` o muchas variables en un serial con `F=1`, (2) **reconexión** con outbox grande, (3) mezcla con no-críticos, (4) duplicados por timeout inflight. El CONTRATO («un evento por muestra saturaría») **no** cuadra con `F` en minutos y `V` LoRa≤8; cuadra si se pensó captura **por segundo** (el firmware no captura en segundos: la unidad es **minuto**).

Limitación: nadie midió `V` ni `F` en el dispositivo TEST en esta sesión.

### 5. Comparación de políticas

Lectura de CA-6 usada (auditoría G43, no archivo SRS): generar evento **cuando se detecte** condición normal **o** anómala. «Detectar» puede ser (i) cada lectura clasificada o (ii) el reconocimiento del estado. **No se elige (ii) por tráfico.**

| Criterio | A. Un evento por lectura NORMAL | B. Solo al entrar a NORMAL / cambio de banda | C. Periódico mientras sigue NORMAL | D. Transición + periódico configurable |
|---|---|---|---|---|
| CA-6 | Compatible con «cada detección de lectura en condición normal». Es la lectura más literal de «cuando se detecte» junto a C3 (categoría NORMAL en el procesamiento). | **No se puede dar por cumplido** sin acta: en permanencia NORMAL **no** hay evento aunque la condición se detecte en cada muestra. El historial local no es el evento C4. | Parcial: hay eventos, pero no uno por detección; el periodo no está en RF-55/54/56/57 inspeccionados. | Igual que C respecto al hueco entre pulsos; la transición cubre el cambio, no cada detección. |
| CA-8 | Hay evento que enviar si hay conectividad. | Solo si coincidió una transición; un dispositivo que arranca y permanece NORMAL **sí** emitiría el primer evento si B incluye «entrar» al primer clasificado. Si B exige cambio *desde otra banda*, el arranque en NORMAL **no** emitiría (hueco CA-6/CA-8). | Depende del reloj de pulso. | Igual. |
| Eventos/min | `V_normal/F` + no-críticos | ~0 en régimen; picos en transiciones y, tras reboot, según definición de «entrar» | `1/T_pulso` por variable o serial (T no existe en código) | Transiciones + pulsos |
| Trazabilidad central | Una fila por muestra clasificada (alineada a telemetría, duplica volumen vs solo desviación) | Solo bordes de banda; el interior NORMAL no queda en `eventos_edge_computing` | Muestras discretas; huecos | Mejor que B, peor que A |
| Pérdida de información | Baja en régimen; alta si 429+broker drop | Alta en permanencia (valores NORMAL no viajan como evento) | Media | Media-baja |
| Duplicación | Timeout inflight + sin idempotencia backend | Menos filas; mismo bug de re-POST | Igual bug | Igual bug |
| Offline RF-54 | Cada NORMAL al outbox; buffer no tira eventos (sí telemetría vieja si LLENO) | Pocas filas | Depende de si el pulso corre offline (si el clasificador corre, sí) | Igual |
| Reenvío al reconectar | Ráfaga; choca 60/min y **pérdida broker** | Ráfaga pequeña salvo muchas transiciones offline | Ráfaga de pulsos acumulados | Ráfaga media |
| Reinicio | A no necesita última banda. Outbox SQLite retiene eventos. Estado de banda no aplica. | **Requiere** última banda persistida. Hoy **no existe**. Sin persistir, reboot = re-entrada falsa (duplica NORMAL) o no-entrada (pierde NORMAL). | Pulso no necesita banda; sí reloj | Peor: transiciones inventadas + pulsos |
| Desviaciones actuales | `evaluar_simple` sigue emitiendo SIMPLE; lote inalterado si NORMAL es otro `EventoEdge`. Riesgo: más filas, no cambiar payload SIMPLE/COMPUESTA. | Compatible si el detector de transición no suprime SIMPLE. Hoy no hay detector. | No debe sustituir SIMPLE. | Igual |
| Código existente | Encaja en `nuevo_evento` / `_encolar_evento`. Choca CONTRATO L102 y tests `None`. | Nuevo estado por (serial, variable, umbral). No hay precedente RF-55.1. RF-55.2 `Confirmaciones` sí «reinicia tras confirmar» (otro requisito). | Nuevo temporizador. No hay en RF-55.1. | Combina B+C: máxima complejidad |

### 6. Matriz de escenarios

| # | Escenario | A | B | C | D | Notas de plataforma (comunes) |
|---|---|---|---|---|---|---|
| 1 | Un sensor, NORMAL continuo | 1 evento/captura; CA-6 literal | Tras el primero (si se define entrada), silencio. CA-6 dudoso | Pulsos | Entrada + pulsos | Telemetría KIND_TELEMETRY **sigue** en todos. |
| 2 | Varios sensores / vars simultáneas | V eventos/captura, **un** cupo 60 por serial | V transiciones independientes | V×pulsos o 1 pulso agregado (no especificado) | Idem | Fake: V = len(`EDGE_FAKE_VARIABLES`). LoRa ≤8/trama. |
| 3 | NORMAL → DESVIACION_SIMPLE | SIMPLE se emite como hoy (077/078). A añade el último NORMAL de la captura previa, no de la anómala | Evento de salida de NORMAL no está en RF; SIMPLE cubre la anomalía | Un pulso podría coincidir | Igual | No mezclar severidad CRITICO (fuera_de_rango) con el cupo. |
| 4 | SIMPLE → NORMAL | A: NORMAL en esa captura | **Este** es el caso que B cubre bien (entrada a NORMAL) | El pulso no marca el instante del cambio salvo coincidencia | Transición explícita | Sin estado persistido, B/D fallan tras reboot en medio del cambio. |
| 5 | Permanencia larga NORMAL | Trazas densas; RF-56 guarda `DATOS_PROCESADOS`; RF-57 no alerta | Hueco de trazabilidad central | Depende de T | Depende de T | Historial local ya registra NORMAL hoy (`registrar_normal`). |
| 6 | Sin conectividad en NORMAL | KIND_EVENTO en SQLite; historial BUFFER | Pocas/cero filas nuevas | Pulsos encolados si el loop corre | Idem | Buffer no descarta eventos al LLENO. |
| 7 | Reconexión con pendientes | Flush inmediato (`due_at=now` en eventos). 60/min. Exceso → 429 en backend; broker **no** reencola; Edge **ya** borró al PUBACK → **pérdida** | Menos exposición | Media | Media | Hecho broker: `sin cola ni reintento`. |
| 8 | Reinicio con pendientes | Outbox persiste; se reenvía. Clasificación no se “recuerda” | Pendientes OK; **banda anterior se pierde** | OK | Banda anterior se pierde | `ventana.py`: estado RF-55.2 vacío es intencional. |
| 9 | HTTP 429 | No llega al firmware. Broker log error. Evento MQTT “entregado”. | Igual mecanismo | Igual | Igual | Mitigar 429 **no** basta en el Edge si el ACK MQTT es el criterio de borrado. |
| 10 | Reenvío del mismo evento | Timeout 300 s o re-publish: mismo `id_evento` en JSON. Backend **duplica** filas. | Menos probable por volumen | Igual bug | Igual bug | Comentario Edge L70–71 **incorrecto** respecto a este endpoint. |

### 7. Riesgos

| Riesgo | Grav. | Evidencia |
|---|---|---|
| Aprobar B como “CA-6” solo por tráfico | Alta | CA-6 habla de detectar condición normal **o** anómala; B silencia detecciones sucesivas. |
| Pérdida tras PUBACK + 429 | Alta | `reenvio.py` + use case E6. Independiente de A/B/C/D en ráfaga. |
| Duplicados HTTP | Media | Sin unique `id_evento` Edge. |
| B/D sin persistir última banda | Alta | Reinicio = falso positivo o hueco. No hay tabla/campo de última banda RF-55.1. |
| C/D inventan periodo | Alta | No aparece en firmware ni en RF citados en esta carpeta. |
| Saturar 60/min | Baja en LoRa `F≥1`, V≤8; **alta** en ráfaga y fake masivo | Cálculo §4. |
| CONTRATO vs RF-55 v2.0 | Alta | CONTRATO L102 vs CA-6 auditoría. Producto debe derogar uno. |
| `_enviar_a_m04` falso para NORMAL | Baja (deseable RF-56/57) | Use case L210 (propuesta previa). A aumenta filas `DATOS_PROCESADOS`, no alertas. |
| Contador no distribuido | Media | Réplicas relajan el 60. |

### 8. Recomendación QA

**No se selecciona A, B, C ni D para implementar.**

Motivo: la única lectura de CA-6 disponible es la de la auditoría (SRS ausente). Esa lectura **no autoriza** a sustituir «detectar una condición NORMAL» por «detectar un *flanco* hacia NORMAL». B y D solo serían aprobables **después** de un acta que redefina CA-6 (o el CONTRATO) en ese sentido. C y D introducen un periodo que **no** está en el código ni en los RF comprobados.

A es la única política que, **si** producto confirma que cada lectura clasificada en banda `normal` es una detección, cumple CA-6/CA-8 sin inventar estado. Los números LoRa/`F` en minutos **no** justifican por sí solos rechazar A: el cuello real comprobado es **ráfaga + 429 + broker sin reintento**, no el 60/min en régimen de 1–8 eventos/min. Eso es un defecto de **entrega** (RF-56/broker), no un argumento de requisito para dejar de generar el evento.

Preferencia técnica **condicional** (no es aprobación): **A**, reutilizando `nuevo_evento → _encolar_evento → KIND_EVENTO`, **después** de las decisiones de la §9. Hasta entonces, el PASS offline de TC-M03-076 permanece como clasificación local y **no** se reinterpreta.

### 9. Decisiones pendientes (bloquean firmware)

1. **Significado de CA-6:** ¿evento por cada lectura en condición NORMAL, o por transición de estado? Debe citarse el SRS v2.0 en archivo (hoy no está).
2. **CONTRATO L102** («NORMAL nunca se emite») vs RF-55 v2.0: cuál rige.
3. **Arranque en NORMAL** si se eligiera B: ¿la primera clasificación cuenta como entrada?
4. **Persistencia de última banda** si B/D (hoy no existe).
5. **Periodo** si C/D (valor, unidad, por variable vs por serial). No proponer un número aquí.
6. **Qué hacer con 429:** ¿broker reencola? ¿Edge no borra hasta 201? ¿idempotencia por `metadata_edge.id_evento`? Hoy: pérdida o duplicado, no hay tercer camino.
7. **Sobre** `IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO` y workers: ¿el 60 aplica al dispositivo de campo con ráfaga RF-54?
8. Autorización para cambiar tests que exigen `None` (`test_dentro_de_rango_no_emite`, historial, G43 076).

### 10. Criterios que deberán cumplirse antes de implementar

No abrir PR de firmware NORMAL hasta que existan, por escrito:

1. Acta de producto sobre CA-6 (muestra vs transición) **o** SRS v2.0 versionado en el repo con la cláusula citada.
2. Actualización o derogación explícita del CONTRATO § campo `clasificacion_rf55`.
3. Tratamiento de 429 en la cadena Edge PUBACK → broker POST (hoy se pierde el evento en el backend).
4. Postura sobre idempotencia de `metadata_edge.id_evento` (hoy duplica).
5. Envolvente operativa: `F` mínimo permitido, `V` máximo por serial, número de seriales por Edge, y prueba de ráfaga RF-54 ≤ política de 60/min o cambio de límite.
6. Si la acta elige B o D: diseño de persistencia de última banda y comportamiento post-reinicio, más tests de flanco NORMAL↔SIMPLE.
7. Plan de no regresión 077/078 / compuestos, **sin** reescribir el PASS offline 2026-10-30 de 076.

Hasta cumplir 1–5, cualquier parche en `evaluar_simple` sería implementación a ciegas del requisito.

---

## Entrega confiable, reintentos e idempotencia

**Estado:** propuesta de integración. **No implementada.** Aplica a `KIND_EVENTO` (desviaciones actuales y un futuro NORMAL). El PASS offline de TC-M03-076 no cambia.

Criterio de aceptación de entrega (esta sección): un evento RF-55 **solo** está entregado cuando el backend **acepta** `POST /iot/eventos-edge` (HTTP 2xx del router, hoy **201**). El PUBACK MQTT **no** es esa confirmación.

### 1. Flujo actual comprobado

```
Edge outbox SQLite (RF-54)
  → publish QoS 1 sgpmp/<serial>/evento
  → Mosquitto PUBACK  → Edge borra fila + historial ENVIADO
  → suscriptor SGPMP encola (BRK-09) y procesa
  → reenvio.reenviar() crea tarea HTTP; no espera el resultado
  → POST /iot/eventos-edge
       201: persiste (identity id_evento_edge_computing)
       4xx/5xx/timeout: log en broker; nadie reintenta
```

| Paso | Código | Hecho |
|---|---|---|
| Extraer RF-54 | `buffer.due(now, _FLUSH_BATCH=100, exclude=inflight)` | `ORDER BY due_at, id`. Eventos con `due_at=now` (no esperan ventana de telemetría). |
| Inflight | `agent._inflight[mid] = (row_id, now)` | Si no hay PUBACK en 300 s (`_INFLIGHT_TIMEOUT_S`) el `mid` se olvida y la fila **vuelve** a `due()`. |
| Borrar | `PubAck` → `buffer.delete` | QoS 1: `mqtt_client.on_publish` = PUBACK de **Mosquitto**, no del POST. |
| Historial | `marcar_enviado` en el mismo PubAck | `ENVIADO` = llegó al broker MQTT. Comentario de `historial.py`: «si llegó al broker». |
| Descarte Edge | `_expirado` 72 h | Borra outbox y `DESCARTADO` / `TIMESTAMP_EXPIRADO` **antes** de publicar. |
| HTTP | `reenvio.py` L9–11, L27–32 | «sin cola ni reintento». `ok=False` solo se registra. |
| Fire-and-forget | `evento_edge` llama `reenviar` **sin await** | El worker BRK-09 termina antes de saber 201/429. |
| Cola broker | `cola.py` | Evento = `Prioridad.CRITICO` (`prioridad.py` L149–160). Saturación: `_rechazar` envía `RETENER` **solo** si el topic es telemetría (L107–108). Un `evento` rechazado por cola **no** avisa al Edge. Cola **en memoria**; reinicio del proceso broker la pierde. |
| Telemetría (contraste) | `ingest.py` L191–196 | Ya **no** se libera el buffer de lecturas con el PUBACK: hay `sgpmp/<serial>/resultado` con `LIBERAR`/`RETENER`. **Los eventos no tienen ese canal.** |
| Edge `resultado` | firmware `mqtt_client` / `agent` | No se halló suscripción ni manejo de `accion_buffer` para eventos. Limitación: no se reabrió cada test de telemetría RF-54. |

**Reinicio:**

- Edge: outbox SQLite + WAL + `synchronous=FULL`. Filas sin PUBACK permanecen. `_inflight` y `_eventos_en_vuelo` son memoria: un corte a mitad de publish puede reenviar el mismo JSON (mismo `id_evento` en payload).
- Broker: tarea HTTP y cola BRK-09 no persistentes. Mensaje MQTT ya ACK al publicador.
- Backend: commit en `guardar` + `db.commit()`; si cae **después** del commit y **antes** de responder, el cliente ve timeout y un reintento crea **otra** fila (sin unique).

### 2. Códigos HTTP (este endpoint)

Router: `status_code=201`; declara 400, 401, 422, 429, 503. El cliente broker trata `httpx.is_error` (4xx/5xx) como fallo único; **no** ramifica por código.

| Código | ¿Existe en este POST? | Efecto actual | Clase propuesta |
|---|---|---|---|
| 200 | **No** declarado; éxito sería `ok=True` si ocurriera | No hay rama | Tratar como aceptado **solo** si se introduce idempotencia replay |
| **201** | Sí, éxito | Persistido | `ACEPTADO_BACKEND` |
| 400 | `ValidationError`: `TIMESTAMP_FUTURO`, `TIMESTAMP_EXPIRADO`, `ORDEN_TEMPORAL_INVALIDO` | No persiste (si falla antes de `guardar`) | Permanente salvo política de reloj (ver abajo) |
| 401 | Token broker o `DISPOSITIVO_NO_AUTORIZADO` | Bitácora E7; no persiste | Permanente hasta corregir identidad; no reintentar en bucle |
| 409 | **No** en router ni use case de eventos-edge | — | Reservar para conflicto de idempotencia **si** no se prefiere 201 replay |
| 422 | Pydantic (cuerpo) | No persiste | Permanente (contrato) |
| **429** | `LIMITE_TASA_EXCEDIDO` | No persiste. Headers: `Retry-After`, `RateLimit-Limit`, `RateLimit-Remaining=0`, `RateLimit-Reset` (**comprobado** en `rate_limit.py` L47–59 y G64). Valor = segundos restantes de la ventana, `max(1, ceil(...))`. | Temporal: respetar `Retry-After` |
| 5xx | Handler: BD → 503; no controlado → 500 | No persiste si el error es antes del commit; **ambiguo** si es después | Temporal |
| Timeout / red | `client.py` L60–65 | `ok=False`, sin status | Temporal; **posible 201 ya commit** |

No hay backoff, tope de intentos ni persistencia de estado de envío en el broker para este POST.

### 3. Arquitectura propuesta

Objetivo: alinear **eventos** con el patrón que **ya** existe para telemetría RF-54 (`resultado` + `RETENER`/`LIBERAR`), más idempotencia en RF-56.

**Responsabilidades:**

| Componente | Hoy | Propuesto |
|---|---|---|
| Firmware | Libera con PUBACK Mosquitto | Conservar outbox hasta `LIBERAR` de aplicación (o equivalente). PUBACK solo = «Mosquitto tiene el mensaje». Actualizar `due_at` en reintentos. |
| Mosquitto | Transporte QoS 1 | Sin clasificar; sin HTTP. |
| Broker SGPMP | POST fire-and-forget | **Await** (o outbox propio) del POST; mapear status → `accion_buffer`; publicar `resultado` de evento. Reintento HTTP con política §5 **antes** de `LIBERAR`. Si se rechaza la cola BRK-09 para `evento`, también `RETENER` (hoy no). |
| Backend | 201 insert; 429 sin persistir | Idempotencia por id Edge; 201 en replay; 429 + `Retry-After` (ya existe). |

**Alternativa B (solo broker):** outbox HTTP persistente; el Edge sigue borrando al PUBACK. Recupera 429/5xx **si** el broker no se reinicia antes de persistir el outbox. **No** cubre pérdida si Mosquitto ACK y el proceso broker muere con cola en RAM. Inferior a A.

**Recomendación:** alternativa A (ACK de aplicación en Edge) + idempotencia backend. Reutiliza RF-54 y el canal `resultado` ya previsto en ACL del broker (`test_credenciales_mqtt.py`). Extender el contrato de `resultado` a `KIND_EVENTO` (hoy el firmware no lo consume para eventos).

No pedir al broker que reclasifique lecturas.

### 4. Ciclo de vida propuesto

Nombres lógicos; no hace falta que coincidan con columnas actuales.

| Estado | Dónde | Significado | Transiciones |
|---|---|---|---|
| `PENDIENTE` | Outbox Edge `due_at ≤ now` | Clasificado, no confirmado backend | → `ENVIANDO` al publish |
| `ENVIANDO` | Inflight MQTT y/o espera `resultado` | En tránsito | PUBACK MQTT **no** sale de aquí. `LIBERAR`/201 → `ACEPTADO_BACKEND`. `RETENER`/429/5xx/timeout → `REINTENTO_PROGRAMADO`. 401/422/400 definitivo → `ERROR_PERMANENTE` |
| `REINTENTO_PROGRAMADO` | Outbox `due_at` futuro | Temporal | → `PENDIENTE` al vencer |
| `ACEPTADO_BACKEND` | Fuera del outbox; historial | HTTP 2xx de aceptación (201 o replay idempotente) | Terminal OK |
| `ERROR_PERMANENTE` | Historial `DESCARTADO` + motivo | No reintentar (72 h, esquema, no autorizado, expirado) | Terminal KO |

Por qué no basta el historial actual: `PENDIENTE`/`ENVIADO`/`DESCARTADO` miden **MQTT**, no RF-56. `ENVIADO` hoy es un falso positivo de entrega al sistema central.

`TIMESTAMP_FUTURO` (captura > ahora+30 s): podría volverse válido. Decisión pendiente: permanente vs un reintento acotado. No se asume.

### 5. Reintentos

| Caso | Acción | Tope |
|---|---|---|
| **429** | Esperar **`Retry-After`** (header comprobado, entero de segundos ≥ 1). No martillar. Si falta el header (no debería en este use case), fallback: ventana 60 s del límite. | Mientras el evento tenga < 72 h (ya alineado a `_ANTIGUEDAD_MAX_EVENTO_S` y `_MAX_VENTANA_BUFFER_HORAS`). Tras 72 h: `ERROR_PERMANENTE` / descarte Edge actual. |
| 5xx, timeout, conexión | Backoff exponencial **con jitter** en el componente que reintenta (broker HTTP y/o Edge `due_at`). Factor 2, tope sugerido alineado a `Retry-After` máximo de tasa (60 s) o un techo operativo a definir (no está en RF). | Igual 72 h. Contador de intentos: **no existe**; producto debe fijarlo. Sin acta, el techo temporal 72 h es el único comprobado. |
| 400 `TIMESTAMP_EXPIRADO` | No reintentar. Edge ya descarta a las 72 h. | Permanente |
| 400 `ORDEN_TEMPORAL_INVALIDO` | No reintentar (dato mal formado). | Permanente |
| 401 / 422 | No reintentar en caliente. | Permanente; corrección operacional |
| 409 | Hoy no aplica. Si se usa por duplicado: tratar como **éxito idempotente** o mapear a `ACEPTADO_BACKEND`, no como fallo. | — |

Ráfaga: `_FLUSH_BATCH=100` puede emitir 100 eventos seguidos contra un cupo 60/min: los 40 siguientes 429. El reintento **debe** serializar o respetar `Retry-After` por serial; no reenviar el lote completo al instante.

Reinicio Edge: `REINTENTO_PROGRAMADO` vive en `due_at` persistido (campo ya existe). No hace falta nueva tabla si se reutiliza. Reinicio broker: sin outbox HTTP, solo A (Edge retiene) es robusto.

### 6. Deduplicación e idempotencia

`metadata_edge.id_evento` (`edge-evt-{uuid}`) **ya es estable** en el payload del outbox (`evento.py`). Basta como **clave de negocio** si el backend la **persiste con unique** y el replay devuelve 201 con el `id_evento_edge_computing` original.

No basta dejarla solo dentro de JSONB `metadatos` sin índice único: el use case no busca por ella.

Clave adicional (`idempotency_key` estilo telemetría): **no** es necesaria si `id_evento` Edge es obligatorio y único. Telemetría usa `event_id` en `metadatos` del payload (`agent.py` L687) y el comentario L70–71 asume descarte servidor; para **eventos** esa asunción es **falsa**.

Escenarios:

| Situación | Sin unique | Con unique + 201 replay |
|---|---|---|
| 201 commit, respuesta perdida, re-POST | Segunda fila | Una fila |
| Broker repite HTTP | Duplicado | Una fila |
| Edge timeout inflight, re-publish MQTT, segundo POST | Duplicado | Una fila |
| RF-54 tras respuesta ambigua | Duplicado | Una fila |

RF-57/M04: un duplicado hoy puede duplicar paquete/alerta (desviaciones). Idempotencia debe cortar **antes** de consolidar otra vez. Limitación: no se leyó `ConsolidarEnviarPaqueteUseCase` línea a línea en esta pasada; hay que exigir «replay no reenvía M04» en implementación.

### 7. Orden

Edge: FIFO local `due_at, id` (comprobado).  
Broker: workers **en paralelo**, comentario `cola.py` L24–26: sin orden por serial.  
RF-54 `buffer_sequence_id` (anotaciones G23) es de **telemetría/batch**, no se halló en el payload de evento Edge.  
Backend: INC-M03-110 valida orden **captura vs procesamiento**, no el orden de llegada de muchos eventos.

**No se afirma** que RF-55/56 exijan FIFO global de eventos. La matriz de pruebas incluye orden **solo** como no-regresión del FIFO del outbox Edge, no como CA inventada.

### 8. Matriz de pruebas (no ejecutada)

U = unitario (firmware harness / rate_limit / reenvio mock).  
IB = integración broker→backend (lab, HTTP real).  
R = recuperación (reinicio proceso, corte de red simulado).

| # | Caso | Tipo | Objetivo | Precondición | Procedimiento | Esperado |
|---|---|---|---|---|---|---|
| 1 | Reenvío exitoso | U+IB | CA entrega | Outbox con 1 evento; backend 201 | Flush + POST | 201; outbox vacío **solo tras aceptación**; historial alineado a backend |
| 2 | HTTP 429 | IB | No persistir; no perder en Edge | Límite 2 (como DEV-17) | 3 POST no-CRÍTICOS | 201, 201, 429 + `Retry-After`; 3.er evento sigue `PENDIENTE`/`RETENER` |
| 3 | 429 luego recuperación | IB+U | Respetar espera | Caso 2 | Esperar header; reenviar | 201; una fila; sin martillo |
| 4 | 500 temporal | IB | Retry | Mock 500 luego 201 | Dos intentos | Una persistencia; outbox libera al 201 |
| 5 | Backend inaccesible | IB | Timeout | Puerto cerrado | POST | Broker no `LIBERAR`; Edge retiene |
| 6 | Respuesta perdida tras persistir | IB | Idempotencia | Commit + drop respuesta | Re-POST mismo `id_evento` | 201 replay; **una** fila BD |
| 7 | Evento duplicado MQTT | U+IB | Mismo id | Timeout inflight o doble publish | Dos MQTT / dos POST | Un registro backend |
| 8 | Reinicio durante envío | R | Outbox | Kill Edge tras publish antes de ACK app | Rearranque | Reenvío; idempotente |
| 9 | Muchos pendientes | IB | 60/min + batch 100 | 100 KIND_EVENTO | Reconexión | Ninguno perdido; ritmo ≤ límite o cola de `due_at`; no 40 drops silenciosos |
| 10 | Orden outbox | U | FIFO local | 3 eventos due distintos | Flush | Publicación `due_at, id`. **No** exigir orden en workers broker salvo acta |

### 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Seguir usando PUBACK como “entregado” | Cambiar criterio de borrado; no emitir NORMAL a producción hasta eso si se espera CA-8 real |
| Solo reintentar en broker (RAM) | Insuficiente; Edge debe retener |
| Unique sin replay 201 | El cliente podría interpretar 409 como fallo y reintentar eterno o descartar mal |
| Replay que dispara otra alerta RF-57 | Idempotencia **antes** de M04/alerta |
| `FLUSH_BATCH=100` vs 60/min | Programar `due_at` / respetar Retry-After por serial |
| Cola BRK-09 llena descarta `evento` sin `RETENER` | Extender `_rechazar` |
| 72 h vs reconexión larga | Ya hay pérdida legal TIMESTAMP_EXPIRADO; documentar, no silenciar |

### 10. Decisiones pendientes

1. ¿El ACK de aplicación de eventos reutiliza `sgpmp/<serial>/resultado` o un topic nuevo? El de telemetría ya existe; el firmware de eventos no lo usa.
2. ¿Quién reintenta el HTTP: broker (await + backoff) o solo el Edge (más simple, más MQTT)? Recomendación: Edge retiene; broker puede reintentar **corto** (p. ej. una vez con Retry-After) para no duplicar carga, pero la fuente de verdad de no-pérdida es el outbox Edge.
3. Unique `id_evento` Edge: columna vs índice en JSONB; 201 replay vs 409.
4. Tope de intentos además de 72 h.
5. `TIMESTAMP_FUTURO`: ¿reintento?
6. Orden entre workers del broker: ¿in-scope?
7. No implementar emisión NORMAL (política A) **antes** de 429+idempotencia si la ráfaga RF-54 es el escenario de campo.

Limitaciones de esta sección: no se inspeccionó Mosquitto (`persistence`, `max_queued_messages`); no se midió `mqtt_cola_capacidad` de un despliegue real. El replay M04 se detalla en la sección de protocolo (consolidar ya evita un segundo paquete **por** `id_evento_edge_computing` interno, no por `metadata_edge.id_evento`).

---

## Protocolo de confirmación de aplicación Edge-Broker-Backend

**Estado:** diseño. **No implementado.** Independiente de PUBACK. El PASS offline de TC-M03-076 no cambia.

### 1. Hallazgos de inspección (esta pasada)

| Pieza | Hecho | Implicación |
|---|---|---|
| Edge `mqtt_client.py` | Solo se suscribe a `command` (L137–143). `publish` QoS 1; `on_publish` → `PubAck`. | **No** hay consumidor de `resultado` en firmware `e618a75`. |
| Edge `agent.py` | `buffer.delete` en `PubAck`. Historial `ENVIADO` = MQTT. | Liberación RF-54 de eventos **antes** de RF-56. |
| Edge `evento.py` | `id_evento = edge-evt-{uuid}`; va en `metadata_edge.id_evento`; estable en el JSON del outbox. | Clave de correlación ya existe. |
| Broker `config.py` L44–48 | Topic `sgpmp/<serial>/resultado` (`mqtt_topic_resultado`). Comentario: formato **propuesto**; «AIoT lo confirma en FW-01». | El topic **está definido en el broker**; **no** está implementado en el Edge. No se asume uso actual. |
| Broker `ingest.py` | `RESULTADO_INGESTA` + `LIBERAR`/`RETENER`; correlación telemetría por `id_mensaje` o (sensor, variable, timestamp_captura). | Contrato de **lecturas**, no de eventos. |
| Broker `publisher.resultado_topic` | Publica QoS 1 hacia el nodo. | Canal descendente posible; ACL ya lista `resultado` en credenciales. |
| Broker `reenvio.py` | POST sin await útil ni reintento. | Hay que **esperar** el HTTP antes de confirmar. |
| Broker `cola.py` L107–108 | `RETENER` de saturación solo si el topic es telemetría. | Un `evento` expulsado de BRK-09 no avisa al Edge. |
| Backend 201 | `EventoEdgeResponse`: PK interna, clasificación, timestamps, umbrales, SLA. **Sin** `metadata_edge.id_evento`. | El broker debe correlacionar con el **request**, no con el 201. |
| Backend 429 | Cuerpo `ErrorResponse` (`error_code`, `message`, `fields`, `timestamp`). Headers `Retry-After` y `RateLimit-*`. | El cuerpo **no** trae segundos; están en el header (comprobado). |
| Backend modelo | PK identity; `metadatos` JSONB incluye lo de `metadata_edge` más `clasificacion_rf55`. **Sin** unique de id Edge. | |
| M04 | `obtener_por_evento(id_evento_edge_computing)`: si existe paquete, **no** crea otro ni reenvía. | Protege replay **solo** si es el mismo PK interno. Un segundo INSERT de evento (uuid Edge duplicado sin unique) **sí** arma otro paquete. |
| RF-57 | Alerta best-effort tras persistir desviación con severidad. Rollback local si falla. | Segundo INSERT = riesgo de segunda alerta. Hay ventana de deduplicación de alertas (INC-M03-176) **no reabierta** aquí (limitación). |
| NORMAL | `_enviar_a_m04` falso; sin alerta. | Igual necesita confirmación si se emite. |

### 2. Arquitectura del protocolo

Confirmación de **aplicación** = «el backend persistió (o reconoció idempotente) este `id_evento`». Mosquitto PUBACK = «el broker MQTT aceptó el publish».

```
Edge outbox KIND_EVENTO
  --QoS1--> Mosquitto --PUBACK--> Edge: estado ESPERANDO_CONFIRMACION (NO borrar)
  --cola--> Broker await POST /iot/eventos-edge
              201 o replay 201 --> MQTT descendente CONFIRMACION (LIBERAR)
              429/5xx/red        --> MQTT descendente CONFIRMACION (RETENER + retry_after_s)
              400/401/422        --> MQTT descendente CONFIRMACION (RECHAZO_PERMANENTE)
Edge: LIBERAR → delete outbox. RETENER → due_at += espera. RECHAZO → DESCARTADO + trazabilidad.
```

**Topic propuesto (no existe hoy en firmware):**

No mezclar el payload de telemetría `RESULTADO_INGESTA` con eventos.

| Opción | Topic | Pros | Contras |
|---|---|---|---|
| **P1 (recomendada)** | Mismo `sgpmp/<serial>/resultado` (broker ya lo define) con `tipo_mensaje` **nuevo** `RESULTADO_EVENTO_EDGE` | ACL y publisher existentes; un solo subscribe en Edge | Firmware debe discriminar `tipo_mensaje`; no chocar con `RESULTADO_INGESTA` |
| P2 | `sgpmp/<serial>/confirmacion_evento` | Separación nítida | Topic **nuevo**: ACL, Mosquitto, tests de credenciales, FW-01 |

P1 **no** asume que el Edge ya escucha `resultado`: hay que **añadir** la suscripción (hoy solo `command`). Eso también habilita el contrato BRK-01 de telemetría, hoy publicado por el broker y **no consumido** en `e618a75`.

QoS 1 + sesión persistente Edge (`clean_session=False`): una confirmación publicada con el nodo caído puede reentregarse al reconectar (mismo patrón que `ota/notify` en `publisher.py`).

### 3. Identificador y correlación

| Campo | Origen | Uso |
|---|---|---|
| `metadata_edge.id_evento` | Edge, `edge-evt-{uuid}` en `nuevo_evento` | Identidad de negocio; eco obligatorio en la confirmación |
| Serial | Segmento del topic MQTT (broker ya ignora serial del cuerpo si choca) | Binding: confirmación solo en `…/<serial>/resultado` del dueño |
| `id_evento_edge_computing` | PK backend, solo tras 201 | Eco opcional para trazabilidad; **no** es la clave del outbox Edge |

El Edge indexa inflight de eventos por `id_evento` (además del `mid` MQTT). Un PUBACK actualiza MQTT; la liberación usa **solo** el mensaje `RESULTADO_EVENTO_EDGE` cuyo `id_evento` coincide y cuyo topic serial coincide con `evento.serial`.

Confirmación con `id_evento` desconocido, serial ajeno o `tipo_mensaje` distinto: **ignorar** (no liberar otra fila). Confirmación repetida `LIBERAR` de un id ya borrado: no-op.

Pérdida de confirmación: el outbox sigue; timeout de espera de aplicación (distinto de `_INFLIGHT_TIMEOUT_S` MQTT) → re-publish del **mismo** JSON. El backend debe ser idempotente.

### 4. Contrato del mensaje de confirmación (propuesto)

Publica el **broker**, después de conocer el HTTP. No lo publica el backend (el Edge no llama HTTP).

```json
{
  "tipo_mensaje": "RESULTADO_EVENTO_EDGE",
  "id_evento": "edge-evt-…",
  "serial": "<serial del topic>",
  "accion_buffer": "LIBERAR | RETENER | RECHAZO_PERMANENTE",
  "http_status": 201,
  "codigo": "ACEPTADO | LIMITE_TASA_EXCEDIDO | …",
  "mensaje": "…",
  "id_evento_edge_computing": 12345,
  "retry_after_s": 12
}
```

| Campo | Obligatorio | Notas |
|---|---|---|
| `tipo_mensaje` | Sí | Distinto de `RESULTADO_INGESTA` |
| `id_evento` | Sí | Eco de `metadata_edge.id_evento` |
| `serial` | Sí | Debe igualar el topic; el Edge valida |
| `accion_buffer` | Sí | Tres valores; no reutilizar `EXITO`/`FALLIDO` de transmisiones MQTT de telemetría sin mapeo |
| `http_status` | Recomendado | 201, 429, 400, …; ausente en timeout de red (`null`) |
| `codigo` | Sí | `error_code` del cuerpo o `ACEPTADO` |
| `retry_after_s` | Si 429 | Parseado del header `Retry-After` (**no** está en `ErrorResponse`) |
| `id_evento_edge_computing` | Si 201 | Del 201; el schema actual **sí** lo trae |

`EventoEdgeResponse` **no** incluye `id_evento` Edge: suficiente para el broker si conserva el cuerpo MQTT original hasta el POST.

### 5. Secuencia (éxito)

1. Edge: `enqueue` KIND_EVENTO; `PENDIENTE`.
2. Edge: `publish` QoS 1 → `ENVIANDO_MQTT`.
3. Mosquitto PUBACK → `ESPERANDO_CONFIRMACION` (fila **sigue**).
4. Broker worker: `await` POST (dejar el fire-and-forget).
5. Backend `guardar` + `commit` → 201.
6. Broker: publish `RESULTADO_EVENTO_EDGE` `LIBERAR` QoS 1.
7. Edge: match `id_evento` → `delete` + historial `ACEPTADO_BACKEND` (nombre nuevo o redefinir `ENVIADO` para que no signifique PUBACK).

429: paso 5 falla; paso 6 `RETENER` + `retry_after_s`; Edge `due_at = now + retry_after_s` → `REINTENTO_PROGRAMADO`.

### 6. Máquina de estados

**Edge (fuente de no-pérdida)**

| Estado | Quién entra | Quién sale |
|---|---|---|
| `PENDIENTE` | Clasificador + `_encolar_evento` | Agent al publicar |
| `ENVIANDO_MQTT` | Agent publish | PUBACK → `ESPERANDO_CONFIRMACION`; fallo publish/desconexión → `PENDIENTE` |
| `ESPERANDO_CONFIRMACION` | PUBACK MQTT | Confirmación `LIBERAR` → `ACEPTADO_BACKEND`; `RETENER` → `REINTENTO_PROGRAMADO`; `RECHAZO_PERMANENTE` → `ERROR_PERMANENTE`; timeout app → `REINTENTO_PROGRAMADO` (re-publish) |
| `REINTENTO_PROGRAMADO` | Edge (`due_at`) | Reloj → `PENDIENTE` |
| `ACEPTADO_BACKEND` | Edge | Terminal; borra outbox |
| `ERROR_PERMANENTE` | Edge | Terminal; historial motivo; no outbox |

**Broker (no es autoridad de retención)**

| Estado lógico | Transición |
|---|---|
| Recibido MQTT | Cola BRK-09 |
| `POST_EN_CURSO` | Await HTTP |
| Emitir `LIBERAR` / `RETENER` / `RECHAZO_PERMANENTE` | Según §7 |
| Saturación cola | Hoy: drop silencioso de `evento`. Propuesto: publicar `RETENER` (como telemetría) **sin** inventar 201 |

El broker **no** marca `ACEPTADO_BACKEND`. Si muere en `POST_EN_CURSO`, el Edge timeout y reenvía.

Historial actual `ENVIADO` choca con este diseño: hay que **no** llamar `marcar_enviado` en PubAck de eventos.

### 7. Tratamiento HTTP → confirmación

| HTTP | ¿Info actual suficiente? | `accion_buffer` | Edge |
|---|---|---|---|
| **201** | Sí para PK; no trae uuid Edge (broker lo tiene) | `LIBERAR`, `codigo=ACEPTADO` | Borrar |
| **201 replay** (propuesto) | Hoy **no existe** | Igual `LIBERAR` | Borrar (idéntico al primero) |
| **429** | Header `Retry-After` sí; cuerpo no | `RETENER` + `retry_after_s` | Esperar exactamente esos segundos (mín. 1, comprobado) |
| **5xx** / 503 BD | `error_code` + 503/500 | `RETENER`; backoff broker **corto** opcional + `retry_after_s` sugerido (p. ej. 5×2^n con jitter, tope 60 s) si no hay header | Conservar; `due_at` |
| Red / timeout | Broker `ok=False` sin status | `RETENER` (si el broker aún puede MQTT) o silencio (Edge timeout) | Conservar. **Ambiguo:** pudo haber 201. Idempotencia obligatoria |
| **400** `TIMESTAMP_EXPIRADO`, `ORDEN_TEMPORAL_INVALIDO` | `error_code` + `fields` | `RECHAZO_PERMANENTE` | Historial; no reenviar. 72 h Edge ya alinea expirado |
| **400** `TIMESTAMP_FUTURO` | Igual | Decisión pendiente: `RETENER` acotado vs permanente | No asumir |
| **401** | `DISPOSITIVO_NO_AUTORIZADO` o token | `RECHAZO_PERMANENTE` | Trazabilidad; corrección operacional |
| **422** | Validación Pydantic (no `ErrorResponse` de AppError en todos los casos; handler de validación — limitación: no se releyó el JSON 422 campo a campo) | `RECHAZO_PERMANENTE` | No reenviar cuerpo inválido |
| **409** | **No** usado en este POST | Si se introduce por colisión de contenido: `RECHAZO_PERMANENTE` + código de conflicto. Duplicado **idéntico** no debe ser 409, debe ser **201 replay** | |

Broker: un reintento HTTP interno **como mucho** respetando `Retry-After` una vez reduce MQTT extra; la autoridad sigue siendo el Edge.

### 8. Idempotencia backend (diseño, sin código)

**Clave:** `metadata_edge.id_evento` (texto `edge-evt-` + UUID). Extraer a columna o índice único JSONB `UNIQUE` donde no sea null.

**Atómico (propuesto):**

1. `INSERT` evento con unique en id Edge.
2. Conflicto: `SELECT` fila existente **en la misma transacción**.
3. Comparar huella de contenido (clasificación, timestamps de captura/procesamiento, variables, severidad).  
   - Igual → **no** INSERT; **no** consolidar M04; **no** `GenararAlertaUseCase`; return 201 con PK original (`replay`).  
   - Distinto → **409** `ID_EVENTO_EN_USO` (UUID reutilizado). El Edge no debe reciclar ids (`uuid4` en fábrica lo impide salvo bug).

Carrera de dos POST simultáneos: unique + un ganador INSERT; el otro toma la rama conflicto. M04 `obtener_por_evento` ya evita segundo paquete **si** es el mismo PK; el unique evita el segundo PK.

**Históricos:** filas sin `metadatos.id_evento` (o null): el unique debe ser **parcial** (`WHERE id_evento IS NOT NULL`) para no romper datos viejos. No reescribir históricos en esta propuesta.

`EventoEdgeResponse` en replay: mismos campos que 201 original (PK, clasificación). El broker no necesita campos nuevos para `LIBERAR`.

### 9. Compatibilidad

| Flujo | Impacto si se implementa el protocolo |
|---|---|
| Telemetría RF-54 | Subscribe nuevo a `resultado`. Despachar por `tipo_mensaje`: `RESULTADO_INGESTA` vs `RESULTADO_EVENTO_EDGE`. No cambiar `KIND_TELEMETRY` hasta que producto active BRK-01 en firmware (hoy tampoco se consume). |
| SIMPLE / COMPUESTA | Mismo outbox y mismo confirmación. Payloads `a_payload` sin campos nuevos obligatorios. |
| MQTT actual | QoS 1 se mantiene; solo deja de ser criterio de borrado de **eventos**. |
| RF-56 | 201 / replay; M04 solo en INSERT nuevo. NORMAL sigue sin paquete. |
| RF-57 | Alerta solo en INSERT nuevo de desviación. |
| Heartbeat / command | Sin cambio de topics. |
| Contratos tests firmware `marcar_enviado` en PubAck | Habría que actualizarlos **cuando** se implemente, no ahora. |

### 10. Matriz de pruebas del protocolo

U = unitario Edge/broker mock. IB = broker-backend. R = recuperación. E = Edge+MQTT mock.

| # | Escenario | Tipo | Precondiciones | Pasos | Esperado | Responsable |
|---|---|---|---|---|---|---|
| 1 | PUBACK sin 201 | E | Backend caído o POST no lanzado | Publish; llega PubAck | Outbox **intacta**; historial ≠ aceptado | Edge |
| 2 | 201 + confirmación | IB+E | POST 201; broker publica `LIBERAR` | Flujo completo | Delete outbox; una fila BD | Broker+Edge |
| 3 | 429 + Retry-After | IB+E | Límite 2 | 3.er evento | `RETENER`; `due_at` += header; no persistido | Backend header + Edge |
| 4 | 429 y corte en la espera | R | Tras 429, desconectar MQTT | Esperar header offline | Sigue en SQLite; al reconectar no reenvía antes de `due_at` | Edge |
| 5 | 500 + backoff | IB | 500 luego 201 | Reintento | Una fila; `RETENER` intermedio | Broker opcional + Edge |
| 6 | Persistido, confirmación perdida | IB+E | 201, no MQTT down | Timeout app; re-POST | 201 replay; **una** fila; segundo `LIBERAR` borra | Backend unique + Edge |
| 7 | Reenvío duplicado | IB | Mismo JSON dos POST | — | Un PK | Backend |
| 8 | Mismo id, cuerpo distinto | IB | Unique ya ocupado | POST alterado | 409; Edge no LIBERAR (rechazo permanente) | Backend+Edge |
| 9 | Reinicio Edge pendiente | R | Kill en `ESPERANDO_CONFIRMACION` | Arranque | Fila SQLite; re-publish mismo id | Edge |
| 10 | Reinicio broker en POST | R | Kill tras MQTT, antes/durante HTTP | — | Edge timeout + reenvío; idempotencia si 201 ocurrió | Broker no autoridad |
| 11 | Confirmación inválida | U | `id_evento` ajeno / serial distinto / tipo mal | Publish falso | Ningún delete | Edge validación |
| 12 | Confirmación `LIBERAR` repetida | U | Ya aceptado | Segundo mensaje | No-op | Edge |
| 13 | Varios pendientes | E | N eventos | Confirmaciones desordenadas | Cada id libera su fila; no la vecina | Edge índice por id |
| 14 | Reconexión con cola | E+IB | 100 KIND_EVENTO | Flush | Ritmo 429+`due_at`; ninguno LIBERAR sin 201 | Edge+backend |
| 15 | NORMAL y desviación | U+IB | Ambos tipos | Mismo protocolo | NORMAL: 201 sin M04/alerta. SIMPLE/COMPUESTA: 201 + paquete/alerta **una vez** | Use case |

### 11. Riesgos y decisiones pendientes

1. ¿P1 (`resultado` + `tipo_mensaje`) o P2 (topic nuevo)? Recomendación P1 por ACL ya prevista; firmware debe suscribirse **por primera vez**.
2. Timeout de `ESPERANDO_CONFIRMACION` (no usar 300 s MQTT como único).
3. Unique parcial JSONB vs columna `id_evento_edge` texto.
4. Huella de «mismo contenido» (campos exactos).
5. Activar a la vez BRK-01 telemetría o solo eventos (riesgo de cambiar liberación de lecturas si se interpreta mal `RESULTADO_INGESTA`).
6. FW-01 / CONTRATO: documentar que PUBACK ≠ entrega RF-56.
7. 422: forma exacta del JSON (limitación).
8. Deduplicación RF-57 por ventana: no re-verificada; el unique de evento es la barrera primaria.

Sin unique + sin dejar de borrar al PUBACK, este protocolo **no** cierra la brecha 429.

---

## Revisión de consistencia y especificación técnica para implementación

**Naturaleza:** revisión QA del documento anterior. **No** modifica las conclusiones históricas de las secciones 1–13 ni el PASS offline de TC-M03-076. **No** autoriza implementar firmware, broker ni backend hasta los criterios de la §6.

### 1. Hallazgos de consistencia interna

| Id | Dónde choca | Hecho de código | Cómo planificar |
|---|---|---|---|
| C1 | §1 y §6: «outbox retiene ante 429» / «reutiliza PUBACK» | `handle_event(PubAck)` borra la fila **antes** del POST | La especificación vigente para entrega es el **protocolo de confirmación**, no el resumen ejecutivo. El resumen describe el **deseo** CA-8, no el comportamiento actual. |
| C2 | CONTRATO Edge: `NORMAL` nunca se emite vs §6 alternativa A | `evaluar_simple` → `None`; CONTRATO L102 | Bloqueado por acta CA-6 (sección política). Implementar NORMAL **después** o en paralelo al protocolo, no en un solo PR ciego. |
| C3 | Telemetría «usa RETENER/LIBERAR» vs firmware | Broker publica `RESULTADO_INGESTA`; Edge **no** se suscribe a `resultado` | BRK-01 está a medias. El protocolo de eventos **no** puede asumir un consumidor existente. |
| C4 | Suscribir `resultado` sin despacho | Todo `Message` entra a `_on_command` (L206–207). `_serial_from_command_topic` exige sufijo `/command` | **Bloqueante:** hay que ramificar por sufijo de topic. Si no, un `RESULTADO_EVENTO_EDGE` se ignora (serial None) **o**, si se parseara mal, no debe caer en RF-23. |
| C5 | `RESULTADO_INGESTA` vs `RESULTADO_EVENTO_EDGE` | Contratos distintos (`id_mensaje` vs `id_evento`) | Mismo topic P1 **solo** con `tipo_mensaje` discriminante. No reutilizar campos de telemetría como si fueran el evento. |
| C6 | 201 no trae `id_evento` Edge | `EventoEdgeResponse` | Broker correlaciona con el MQTT original. |
| C7 | OpenAPI del POST lista 422; validación Pydantic sin `x-codigo-validacion` | Default del handler = **400** (`error_handlers.py` L200) | Tratar esquema inválido como **400** `ERROR_ESTRUCTURA` (bitácora E1), no asumir 422. 422 queda para `BusinessRuleError` si apareciera. |
| C8 | 409 | `ConflictError` existe; **este** POST no lo lanza | 409 es **contrato propuesto**. |
| C9 | Replay M04 | `obtener_por_evento` usa PK interna | Unique del uuid Edge debe ejecutarse **antes** de un segundo `guardar`. |
| C10 | Historial `ENVIADO` = PUBACK | `marcar_enviado` en PubAck | Redefinir semántica o nuevo estado; no mezclar con `ACEPTADO_BACKEND`. |
| C11 | Reintento broker | `reenvio.py` sin cola | La especificación: Edge es autoridad; broker `await` + una confirmación MQTT, reintento HTTP corto opcional. |
| C12 | Política NORMAL bloqueada vs §6 «implementar A» | Capacidad LoRa no satura 60/min; 429 es ráfaga/entrega | Orden de PRs: (1) confirmación+idempotencia, (2) acta CA-6, (3) emisión NORMAL. |

### 2. Especificación de contratos

#### 2.1 Evento MQTT (`sgpmp/<serial>/evento`) — **derivado de** `a_payload` (firmware)

QoS 1. El broker inyecta `device_id` y `sensor_id` antes del POST. Ejemplo **SIMPLE** (campos reales):

```json
{
  "clasificacion_rf55": "DESVIACION_SIMPLE",
  "severidad": "CRITICO",
  "variables_involucradas": [
    {
      "tipo_variable": "temperatura_ambiente",
      "valor": 35.0,
      "unidad": "C",
      "timestamp_captura": "2026-10-30T15:00:00.000Z",
      "serial": "QA-NODO-1"
    }
  ],
  "timestamp_captura": "2026-10-30T15:00:00.000Z",
  "timestamp_procesamiento_edge": "2026-10-30T15:00:00.120Z",
  "origen": "TIEMPO_REAL",
  "estado_conectividad": true,
  "metadata_edge": {
    "id_evento": "edge-evt-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "regla_aplicada": "UMBRAL_AMBIENTAL",
    "tiempo_procesamiento_ms": 0.12,
    "version_firmware": "v0.3.0"
  }
}
```

NORMAL **propuesto** (mismo esquema; **sin** `severidad`, como L92–93): `clasificacion_rf55: "NORMAL"`. Hoy el firmware **no** publica este cuerpo.

#### 2.2 `RESULTADO_INGESTA` — **derivado de** `ingest._avisar_nodo` (solo telemetría)

Topic `sgpmp/<serial>/resultado`. Campos: `tipo_mensaje=RESULTADO_INGESTA`, `id_mensaje`, `sensor`, `variable`, `timestamp_captura`, `resultado` (EXITO/FALLIDO/TIMEOUT), `accion_buffer` (LIBERAR/RETENER), `codigo`, `mensaje`, `id_telemetria`.  
**No** usarlo para eventos.

#### 2.3 `RESULTADO_EVENTO_EDGE` — **contrato propuesto** (no existe en firmware)

Mismo topic `resultado`, QoS 1, ACL ya: `subscribeLiteral` + `publishClientReceive` en `credenciales_mqtt.py` (`_topics_hacia_el_nodo` incluye `resultado`). El Edge **debe** suscribirse (hoy no).

```json
{
  "tipo_mensaje": "RESULTADO_EVENTO_EDGE",
  "id_evento": "edge-evt-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "serial": "QA-NODO-1",
  "accion_buffer": "LIBERAR",
  "http_status": 201,
  "codigo": "ACEPTADO",
  "mensaje": "",
  "id_evento_edge_computing": 42,
  "retry_after_s": null
}
```

Validación Edge **obligatoria** antes de borrar: `tipo_mensaje`, `serial` ∈ `EDGE_SERIALS` y igual al topic, `id_evento` exacto de una fila outbox `KIND_EVENTO`. Cualquier fallo → ignorar.

#### 2.4 HTTP 201 — **derivado de** `EventoEdgeResponse`

```json
{
  "id_evento_edge_computing": 42,
  "clasificacion_rf55": "DESVIACION_SIMPLE",
  "severidad": "CRITICO",
  "estado_conectividad": true,
  "fecha_captura": "2026-10-30T15:00:00.000Z",
  "fecha_procesamiento": "2026-10-30T15:00:00.120Z",
  "paquete_inferencia_estado": "PENDIENTE",
  "valor_evaluado": null,
  "umbral_min_aplicado": null,
  "umbral_max_aplicado": null,
  "latencia_edge_ms": 120,
  "sla_edge_excedido": false
}
```

NORMAL: `paquete_inferencia_estado` típico `null` (no M04). Replay idempotente **propuesto:** mismo JSON, mismo PK, HTTP **201** (no 409).

#### 2.5 HTTP 429 — **derivado de** `ErrorResponse` + headers G64

Cuerpo:

```json
{
  "error_code": "LIMITE_TASA_EXCEDIDO",
  "message": "Demasiadas solicitudes en poco tiempo. Intenta de nuevo en unos momentos.",
  "fields": [],
  "timestamp": "2026-10-30T15:00:01.000Z"
}
```

Headers (obligatorios para el broker): `Retry-After: <enteros segundos ≥ 1>`, `RateLimit-Limit`, `RateLimit-Remaining: 0`, `RateLimit-Reset`. El broker copia `Retry-After` a `retry_after_s` del MQTT.

#### 2.6 HTTP 409 — **contrato propuesto**

Usar `ConflictError` (status 409 ya en `errors.py`):

```json
{
  "error_code": "ID_EVENTO_EN_USO",
  "message": "metadata_edge.id_evento ya identifica un evento con contenido distinto.",
  "fields": [{"field": "metadata_edge.id_evento", "message": "conflicto de contenido"}],
  "timestamp": "2026-10-30T15:00:02.000Z"
}
```

MQTT: `accion_buffer=RECHAZO_PERMANENTE`, `http_status=409`. **No** usar 409 para el duplicado idéntico.

### 3. Secuencias A–J (especificación)

Notación: E = Edge, B = broker SGPMP, M = Mosquitto, API = backend.

**A. Nuevo + 201**  
E `PENDIENTE` → publish QoS1 → M PUBACK → E `ESPERANDO_CONFIRMACION` (fila viva) → B await POST → API INSERT+commit 201 → B MQTT `LIBERAR` → E delete. Desviación: M04/alerta **una** vez. NORMAL: persistencia `DATOS_PROCESADOS`, sin M04/alerta.

**B. Duplicado idéntico**  
API unique: conflicto + huella igual → 201 replay, **sin** segundo INSERT, **sin** segundo paquete (`obtener_por_evento` no basta solo), **sin** segunda alerta → `LIBERAR`.

**C. Id reutilizado, cuerpo distinto**  
409 `ID_EVENTO_EN_USO` → `RECHAZO_PERMANENTE`. E no borra por LIBERAR; marca `ERROR_PERMANENTE`. No debe ocurrir con `uuid4` de `nuevo_evento`.

**D. 429 y recuperación**  
API no inserta → B `RETENER` + `retry_after_s` → E `due_at=now+N` → tras N, re-publish **mismo** JSON → 201 → `LIBERAR`.

**E. 500**  
Sin persistir (si el error es pre-commit) → `RETENER` + backoff (jitter; tope sugerido 60 s, no está en RF) → reintento. Si el 500 es post-commit, el reintento cae en **B**.

**F. 201 y MQTT de confirmación perdido**  
Outbox sigue. Timeout aplicación (valor a fijar; **no** reutilizar en silencio los 300 s de inflight MQTT) → re-POST → **B** → segundo `LIBERAR` → delete. Sin unique esto duplica filas.

**G. Reinicio Edge**  
SQLite WAL. `_inflight` se pierde. Filas sin delete permanecen `PENDIENTE`. Re-publish mismo payload. Confirmaciones MQTT QoS1 con sesión persistente pueden llegar al reconectar (`publisher.py` mismo patrón OTA).

**H. Reinicio broker en POST**  
Cola BRK-09 y tarea HTTP en RAM se pierden. M ya dio PUBACK a E. E espera timeout → reenvía. Si API había hecho commit, entra **B**. B no es autoridad.

**I. Confirmación inválida**  
`tipo_mensaje` ≠ `RESULTADO_EVENTO_EDGE`, serial de topic ≠ campo, `id_evento` desconocido, o publicador que no es el broker (ACL: el nodo **no** tiene `publishClientSend` en `resultado`; solo receive/subscribe). E no borra. Un peer con credencial de **otro** serial no puede escribir el `resultado` ajeno (ACL por serial). Limitación: réplica mal configurada del broker no se auditó.

**J. `LIBERAR` repetido**  
Id ya ausente del outbox → no-op. No reencolar.

### 4. Seguridad y persistencia (comprobado vs propuesto)

| Control | Hoy | Especificación |
|---|---|---|
| Auth MQTT | Usuario/ACL dynsec por serial | Conservar. Confirmar `subscribeLiteral` de `resultado` al añadir la suscripción Edge. |
| Auth HTTP | `BROKER_SERVICE_TOKEN` | Sin cambio. El Edge no llama al POST. |
| Serial | Broker fuerza serial del topic | Confirmación: topic + campo + membresía `EDGE_SERIALS`. |
| `id_evento` | UUID en JSON; sin unique BD | Unique parcial; validar formato `edge-evt-` + UUID en confirmación. |
| Confirmación falsa | N/A | ACL impide publish del nodo a `resultado`. Edge ignora ids ajenos. No fiarse de PUBACK. |
| Outbox | SQLite, eventos no se evictan | `due_at` para RETENER; delete solo LIBERAR o 72 h / rechazo permanente. |
| Reinicio | Buffer persiste; inflight no | OK si no se borra en PubAck. |
| Dedup atómica | No | Unique + SELECT en la misma transacción; huella de contenido. |
| Error permanente | Historial DESCARTADO 72 h | + 401/400 esquema/409 contenido; retención en historial, no en outbox. |

`ConflictError` 409 y `TooManyRequestsError` 429 ya tienen handler con `headers` opcionales.

### 5. Orden de implementación recomendado (planificable)

1. Backend: unique + replay 201 + 409 contenido; tests G64 no deben romper (el unique no cambia el 60/min).  
2. Broker: `await` POST; mapear status → `RESULTADO_EVENTO_EDGE`; `_rechazar` de cola también para `evento`.  
3. Firmware: subscribe `resultado`; despacho ≠ `_on_command`; no `delete` en PubAck de `KIND_EVENTO`; `due_at` por `retry_after_s`.  
4. Acta CA-6; luego emisión NORMAL (alternativa A) **si** se aprueba muestra-a-muestra.  
5. No unificar en el mismo PR la liberación de **telemetría** por `RESULTADO_INGESTA` (riesgo C3/C5).

### 6. Matriz de aceptación para autorizar implementación e integración

**Puerta 0 — autorización de diseño (funcional/arquitectura)**  
Acta CA-6 (muestra vs flanco); CONTRATO L102; P1 vs P2 de topic; timeout de espera de confirmación; huella de replay; no mezclar BRK-01 lecturas en el mismo cambio.

**Puerta 1 — unitarias (código nuevo, aún no esta sesión)**  
Despacho topic `resultado` vs `command`; ignore confirmación inválida (I, J); unique/huella (B, C); mapeo 201/429/500/409 → `accion_buffer`; `Retry-After` → `due_at`.

**Puerta 2 — offline Edge (harness, sin Pi)**  
A, D, G, I, J, 15 (NORMAL mock vs SIMPLE). **No** reescribir el informe PASS 2026-10-30 de 076; corrida nueva si cambia el oráculo.

**Puerta 3 — MQTT (broker mock o lab)**  
QoS 1; suscripción `resultado`; PUBACK no borra (escenario 1 del protocolo).

**Puerta 4 — broker-backend**  
G64 sigue: 60 aceptados, 429, CRITICO exento. Replay 201 una fila. 409 contenido. Confirmación MQTT tras 201/429.

**Puerta 5 — extremo a extremo (lab autorizado)**  
A–J sobre SIMPLE existente **antes** de activar NORMAL en campo. Ráfaga 100 vs 60/min sin pérdida. M04/alerta: una por id. NORMAL lab solo tras puerta 0.

Criterio de **aprobación de integración:** ningún `KIND_EVENTO` sale del outbox sin `LIBERAR` correlacionado a 201/replay; duplicado idéntico = una fila; 429 no desaparece el evento; tests 077/078 de desviación sin cambio de payload.

### 7. Decisiones que siguen requiriendo aprobación

**Funcional:** significado de CA-6; si CONTRATO «NORMAL nunca se emite» queda derogado; arranque en banda normal si hubiera política B (sigue no recomendada sin acta).

**Arquitectónica:** P1 (`resultado` + `tipo_mensaje`) vs P2 (topic nuevo) — revisión recomienda **P1** por ACL existente, con despacho C4 obligatorio; timeout de `ESPERANDO_CONFIRMACION`; unique columna vs JSONB; campos de la huella; reintento HTTP extra en broker (sí/no); activar BRK-01 telemetría aparte; tope de backoff 5xx.

**QA/proceso:** no implementar NORMAL ni cambiar tests que esperan `None` hasta puertas 0 y 1–4 del protocolo de entrega.

Limitaciones de esta revisión: SRS v2.0 no está en disco; ventana de deduplicación RF-57 no reabierta; Mosquitto `persistence` no inspeccionado; forma JSON 422 de otras rutas no aplica a este POST (default 400).

---

## Plan de implementación por PR y criterios de aprobación QA

**Estado:** plan. **No implementado.** No crea ramas ni PRs. El PASS offline de TC-M03-076 no se reescribe.

Ramas **observadas** (lectura `git rev-parse`, 2026-10-30): `sgpmp-backend` → `laura`; `_consultas/BROKER-MQTT-SGPMP` → `develop`; `.worktrees/sgpmp-rf55-validation` → `qa/rf55-validation-e618a75`. Nombres de ramas de feature / destino de merge **no** están fijados en este documento (pendiente de quien abra el PR). No se asume `origin/test` ni push.

Orden: PR1 → PR2 → PR3 → **acta CA-6** → PR4. Integrar PR4 sin acta es detención QA.

Tensión con la sección de protocolo: aquel diseño publicaba `RETENER`/`RECHAZO_PERMANENTE` por MQTT. **Este plan sigue el enunciado obligatorio de PR2:** `RESULTADO_EVENTO_EDGE` **solo** tras aceptación (201 o replay). El Edge (PR3) retiene por **ausencia** de `LIBERAR` + timeout/`due_at`. Un MQTT `RETENER` explícito queda **fuera** de PR2 salvo ampliación posterior aprobada.

---

### PR 1 — Backend: idempotencia

1. **Objetivo.** Un mismo `metadata_edge.id_evento` no crea dos filas ni dos efectos M04/RF-57. Replay idéntico → 201. Id reutilizado con otro contenido → 409.
2. **Repositorio / rama.** `sgpmp-backend`. Trabajo sobre `laura` (HEAD actual). Rama de PR: **pendiente de nombrar**.
3. **Archivos potencialmente afectados (existen):**  
   `src/telemetry/application/use_cases/inferencia/recibir_evento_edge_use_case.py`  
   `src/telemetry/infrastructure/repositories/evento_edge_repository.py`  
   `src/telemetry/domain/repositories/evento_edge_repository.py` (hoy solo `guardar`)  
   `src/telemetry/infrastructure/models/evento_edge_model.py`  
   `src/telemetry/infrastructure/schema/evento_edge_schema.py` (201 sin uuid Edge: suficiente si el replay reutiliza el schema)  
   `src/telemetry/infrastructure/routers/evento_edge_router.py` (declarar 409 en OpenAPI si se expone)  
   `src/shared/errors.py` (`ConflictError` 409 **ya existe**)  
   `src/telemetry/application/use_cases/inferencia/consolidar_paquete_inferencia_use_case.py` (`obtener_por_evento` por PK interna)  
   `alembic/versions/` — **no hay** migración de unique sobre id Edge; haría falta una **nueva** (ruta exacta pendiente).  
   Pruebas existentes a no romper: `tests/integration/test_inc_m03_121_g64_rafagas_eventos_edge.py`, `tests/integration/test_rf56_dev17_paquetes_pendientes.py`, `tests/telemetry/test_inc_m03_111_g43_umbrales_evento_edge.py`.
4. **Permitido.** Extraer y persistir `id_evento`; unique **parcial** (históricos sin clave); INSERT atómico + rama replay; comparar huella; 201 replay; 409 `ID_EVENTO_EN_USO` (código **propuesto** en la revisión); no llamar consolidar/alerta en replay.
5. **Excluido.** Emitir NORMAL; cambiar el clasificador Edge; broker; límite 60/min; RF-57 de generación (salvo no reentrar en replay); reescribir G64; PASS 076.
6. **Dependencias.** Ningún PR anterior. Acta CA-6 **no** bloquea PR1.
7. **Unitarias (a añadir, no existentes).** Replay idéntico; 409 contenido distinto; id ausente/malformado (comportamiento a definir: unique no aplica o 400 — **pendiente**); dos POST concurrentes → una fila.
8. **Integración.** Extender el POST `/iot/eventos-edge` (mismo cliente de G64/DEV-17): duplicado 201 una fila; 409; G64 60/429/CRITICO **igual**.
9. **Aceptación.** Segunda petición idéntica no incrementa `eventos_edge_computing`; sin segundo paquete ni alerta; G64 verde; 409 no persiste el segundo cuerpo.
10. **Riesgos.** Unique sobre JSONB vs columna; carreras sin `ON CONFLICT`; huella mal definida (falso 409); históricos null.
11. **Parar integración.** G64 deja de cumplir 201×60/429; duplicados crean dos PK; replay dispara M04/alerta.
12. **Evidencias.** Pytest integración (cuando se autorice ejecutar); SQL de unique; trazas de `id_evento_edge_computing` estable en replay. No sustituir evidencias G38/G43 previas.

---

### PR 2 — Broker: entrega confiable

1. **Objetivo.** El POST se espera. 201/replay → publicación `RESULTADO_EVENTO_EDGE` `LIBERAR`. 429 respeta `Retry-After`. 5xx/red: backoff+jitter y reintento HTTP. No mezclar `RESULTADO_INGESTA`.
2. **Repositorio / rama.** `_consultas/BROKER-MQTT-SGPMP` (clone local). HEAD `develop`. Rama de PR: **pendiente**.
3. **Archivos (existen):**  
   `app/services/reenvio.py` (fire-and-forget)  
   `app/services/reenvio_nodo.py` (`evento_edge`, `reenviar` sin await)  
   `app/backend/client.py` (`is_error`, timeout)  
   `app/mqtt/publisher.py` (`resultado_topic`, `publish_resultado_ingesta`)  
   `app/mqtt/cola.py` (`_rechazar` solo telemetría)  
   `app/mqtt/handlers.py`  
   `app/config.py` (`mqtt_topic_resultado="resultado"`)  
   `app/services/ingest.py` (`TIPO_RESULTADO_INGESTA` — **no modificar contrato de lecturas**)  
   `tests/test_reenvio_nodo.py`, `tests/test_backend_client.py`.
4. **Permitido.** `await` del HTTP de eventos; mapear 201 → MQTT `tipo_mensaje=RESULTADO_EVENTO_EDGE`; leer header `Retry-After`; reintentos temporales; eco de `metadata_edge.id_evento` y serial de topic; `_rechazar` de `evento` **sin** llamar `_avisar_nodo` de telemetría.
5. **Excluido.** Clasificar lecturas; cambiar ingesta telemetry/heartbeat; dynsec salvo evidencia de ACL faltante (ACL `resultado` **ya** está en `credenciales_mqtt.py`); firmware; unique backend (depende de PR1 en lab conjunto).
6. **Dependencias.** Lab e2e de no-duplicados requiere PR1 fusionado o ambiente con unique. PR2 puede desarrollarse contra 201 actuales, pero el escenario F (respuesta perdida) **falla** sin PR1.
7. **Unitarias.** Mock HTTP 201 → un MQTT `RESULTADO_EVENTO_EDGE` no `RESULTADO_INGESTA`; 429 no publica `LIBERAR` y espera `Retry-After`; 500 reintenta; timeout no `LIBERAR`.
8. **Integración.** `test_reenvio_nodo` más casos de status; no ejecutar contra backend de producción.
9. **Aceptación.** Worker no termina el evento como “ok” si el POST no fue 2xx; `LIBERAR` solo tras 201/replay; telemetría sigue usando `RESULTADO_INGESTA` sin cambios de campos.
10. **Riesgos.** Publicar `LIBERAR` en 429; mezclar tipos; reintentos HTTP que duplican POST **antes** de PR1; cola en RAM (reinicio H).
11. **Parar.** Telemetría deja de recibir `RESULTADO_INGESTA`; eventos `LIBERAR` sin 201; clasificación inventada.
12. **Evidencias.** Logs de status HTTP + payload MQTT de confirmación (lab). Sin tocar evidencias G43 offline.

---

### PR 3 — Firmware: confirmación de aplicación

1. **Objetivo.** Outbox de `KIND_EVENTO` sobrevive al PUBACK. Suscripción `…/resultado`. Despacho por sufijo. `_on_command` solo `/command`. Liberar solo con confirmación válida correlacionada.
2. **Repositorio / rama.** Firmware evaluado: worktree `.worktrees/sgpmp-rf55-validation`, `qa/rf55-validation-e618a75` (`e618a75`). Clone `_consultas/EDGE-FIRMWARE-SGPMP` `main` **no** usar (RF-55 revertido, auditoría G43). Rama de PR: **pendiente** (no inventar nombre).
3. **Archivos (existen):**  
   `raspberry/edge_agent/mqtt_client.py` (subscribe solo `command`)  
   `raspberry/edge_agent/agent.py` (`handle_event` → todo a `_on_command`; `PubAck` → `delete`)  
   `raspberry/edge_agent/buffer.py`  
   `raspberry/edge_agent/historial.py` (`ENVIADO` = PUBACK)  
   `raspberry/edge_agent/config.py` (no hay `topic_resultado` hoy; habría que **añadirlo** o hardcode alineado al broker `resultado` — pendiente de no divergir de `EDGE_TOPIC_*`)  
   `raspberry/edge_agent/reglas/evento.py` (`id_evento`)  
   Tests: `raspberry/tests/test_agent.py`, `test_historial.py`.
4. **Permitido.** Subscribe QoS 1 a `sgpmp/<serial>/resultado` por cada serial; `Message` ramificado; handler de `RESULTADO_EVENTO_EDGE`; `delete` de evento solo con `LIBERAR` + `id_evento` + serial; timeout → re-publish mismo JSON; no borrar en PubAck si `kind==evento` (telemetría: **no cambiar** en este PR salvo que el delete sea por `mid` común — hay que ramificar por kind de la fila inflight).
5. **Excluido.** `evaluar_simple` NORMAL; cambiar payload SIMPLE/COMPUESTA; suscribir `command` de menos; implementar `RESULTADO_INGESTA` (BRK-01 lecturas) **en el mismo PR**.
6. **Dependencias.** Confirmación real requiere PR2. Harness puede inyectar MQTT `resultado` sin broker. Integración lab: PR1+PR2.
7. **Unitarias.** PubAck no borra `KIND_EVENTO`; `LIBERAR` válido borra esa fila; inválida (I) no; repetida (J) no-op; `/command` intacto.
8. **Integración.** Harness FakeLink + mensaje `resultado`; no Raspberry en este plan salvo autorización expresa.
9. **Aceptación.** Tras PUBACK la fila sigue; solo sale con `LIBERAR` correlacionado; comandos RF-23/umbral/regla sin regresión.
10. **Riesgos.** C4 (todo a `_on_command`); borrar telemetría al cambiar PubAck; timeout demasiado corto (ráfaga MQTT); `ENVIADO` engañoso.
11. **Parar.** Un `resultado` se interpreta como comando; se pierden ACK de config; se evictan eventos en PubAck; 077/078 dejan de encolar SIMPLE.
12. **Evidencias.** Pytest firmware harness (cuando se autorice). No modificar `RESULTADO_OFFLINE_2026-10-30` de 076.

---

### Acta funcional CA-6 (no es PR de código)

1. **Objetivo.** Decidir si cada muestra en banda `normal` genera `EventoEdge`, y si el CONTRATO L102 («NORMAL nunca se emite») se deroga. No reescribir el RF por capacidad o 60/min.
2. **Repositorio.** Ninguno obligatorio. El SRS v2.0 **no está** en el workspace (limitación).
3. **Archivos a citar, no a editar en el acta:** CONTRATO `docs/CONTRATO_EVENTO_EDGE.md` L102; `evaluador.py` L144–145 y `normales()` L243–244; auditoría `AUDITORIA_CRITERIO_ACEPTACION_TC_M03_076.md`.
4. **Permitido.** Acta firmada / ticket con la lectura de CA-6 y vigencia del CONTRATO.
5. **Excluido.** Parche de `evaluar_simple`; “aprobado porque el tráfico LoRa cabe en 60/min”.
6. **Dependencias.** Independiente de PR1–3 para **redactarse**; PR4 **no** arranca sin ella.
7–8. **Pruebas.** Ninguna de código.
9. **Aceptación del acta.** Texto explícito: muestra vs flanco; CONTRATO derogado o no; PR4 sí/no.
10. **Riesgos.** Implementar PR4 con CONTRATO aún vigente.
11. **Parar PR4** si el acta no existe o dice no emitir NORMAL.
12. **Evidencia.** El acta versionada (ruta **pendiente**). No cambiar el PASS offline 076.

---

### PR 4 — Firmware: generación NORMAL

1. **Objetivo.** Tras el acta: `evaluar_simple` emite `EventoEdge(NORMAL)` con `nuevo_evento` / `_encolar_evento`. Sin cambiar SIMPLE/COMPUESTA.
2. **Repositorio / rama.** Mismo firmware que PR3. Debe **incluir** PR3 (outbox no se pierde en PUBACK) o fusionarse encima.
3. **Archivos:** `raspberry/edge_agent/reglas/evaluador.py`; `agent.py` (`registrar_normal` vs `normales()`); `raspberry/edge_agent/reglas/evento.py` (constante `NORMAL` ya existe); tests `test_evaluador_simple.py` (`test_dentro_de_rango_no_emite`), `test_historial.py` (`test_normal_se_registra_localmente_y_no_se_publica`), `raspberry/tests/test_tc_m03_g43.py` (076). Backend G43 pytest SKIPPED: **no** es este PR.
4. **Permitido.** Return `nuevo_evento(NORMAL, None, …)` en banda `normal`; dejar de duplicar `registrar_normal` si la lectura ya está en el evento; tests **nuevos** o oráculos actualizados en **corrida nueva**.
5. **Excluido.** Reescribir evidencias 2026-10-30; cambiar `_SEVERIDAD` de desviación; broker clasificando; exceptuar NORMAL del rate 60/min (eso sería backend, otro PR no pedido).
6. **Dependencias.** Acta CA-6 aprobando emisión por muestra (si el acta elige flanco, este PR **no** aplica tal cual). PR3 en el mismo árbol. PR1+PR2 para lab CA-8.
7. **Unitarias.** 076: hay `EventoEdge` NORMAL; 077/078 SIMPLE igual; compuestos no regresionan.
8. **Integración.** Harness MQTT `…/evento` + confirmación PR3; lab backend 201 `DATOS_PROCESADOS` sin paquete/alerta.
9. **Aceptación.** Clasificación de desviación bit-compatible; NORMAL en outbox y, con conectividad+PR2, POST 201; historial con `id_evento`.
10. **Riesgos.** Ráfaga 60/min; tests que exigen `None`; CONTRATO desalineado si el acta es incompleta.
11. **Parar.** Acta ausente; 077/078 fallan; NORMAL dispara RF-57; se modifica el informe PASS 076 histórico.
12. **Evidencias.** Nueva carpeta de corrida (fecha nueva). Prohibido editar `Resultados` offline 2026-10-30 de 076.

---

### Criterios de aprobación QA del conjunto

| Puerta | Condición |
|---|---|
| Merge PR1 | Unique + replay + 409 + G64 intacto |
| Merge PR2 | `LIBERAR` solo post-201; telemetría `RESULTADO_INGESTA` intacta |
| Merge PR3 | PubAck ≠ delete evento; despacho `/command` vs `/resultado` |
| Acta | CA-6 y CONTRATO por escrito |
| Merge PR4 | Acta + 077/078 verdes + 076 **nuevo** oráculo, histórico 076 intocado |
| E2E lab | Autorización expresa Raspberry/Mosquitto/backend; escenarios A–J de la revisión sobre SIMPLE **antes** de NORMAL de campo |

**Detención global:** cualquier PR que clasifique en el broker, borre eventos al PUBACK, publique `LIBERAR` sin 201, o altere evidencias/PASS offline 076.

---

## Cierre técnico de PR1: idempotencia, rate limit y recuperación de efectos secundarios

**Estado:** diseño aprobado para implementación de **solo PR1**. **No implementado.** Fuente: complemento de auditoría PR1 (chat, 2026-10-31). No modifica código, migraciones, pytest ni evidencias. No altera el alcance de PR2, PR3, PR4 ni el acta CA-6.

Este cierre **no borra** el plan histórico de «PR 1 — Backend: idempotencia» ni el apartado «Idempotencia backend» del protocolo. **Sustituye, para la implementación de PR1**, los enunciados que omitían M04/RF-57 en replay, que aplicaban E6 antes de saber si el id existía, y que trataban el SELECT previo como garantía de unicidad.

Código de referencia (rama `laura`, inspección de lectura):

- `RecibirEventoEdgeUseCase.execute`: `registrar_llamada` L127–129 **antes** de `guardar`/`commit` L180–186; bitácora L188–204; M04 L210–220; RF-57 L222–235 / `_generar_alerta_best_effort` L291–293.
- `src/shared/rate_limit.py` L34–61: ventana en memoria; **no** transaccional; **no** reversible de forma fiable.
- `ConsolidarEnviarPaqueteUseCase`: `obtener_por_evento(..., bloquear_evento=True)` L187–196; si hay paquete, no reenvía HTTP; HTTP al motor **después** del `commit` del paquete L235–278; `DrenarPaquetesPendientesUseCase` reintenta `PENDIENTE`.
- `EventoEdgeComputingModel`: **no** hay columna `id_evento_edge`. `AlertaModel.id_evento_edge_computing` es FK opcional **sin** unique. `paquetes_inferencia.id_evento_edge_computing` es FK **sin** unique ORM; unicidad de paquete = aplicación.

Hecho actual: un replay HTTP **sí consume E6** porque el rate limit corre antes de persistir. Un INSERT confirmado **antes** de M04/RF-57 deja el evento aceptado aunque fallen los efectos. No se afirma que el replay deje de contar E6 hasta que exista el salto documentado abajo.

### 1. Columna `id_evento_edge` y unique parcial

Persistir el uuid de Edge en columna dedicada `id_evento_edge` (texto), **no** como único índice sobre JSONB.

Índice **parcial** PostgreSQL: unicidad solo `WHERE id_evento_edge IS NOT NULL`. Históricos sin clave no colisionan. La migración se genera en implementación (`alembic revision`; no inventar hash). El unique es la **garantía de una fila de evento**, no el SELECT.

### 2–4. Orden: validar ID → SELECT de cortesía → E6 solo si INSERT → unique

```
validar id (ausente / malformado → 400; sin E6)
SELECT por id_evento_edge
  fila + huella distinta → 409 ID_EVENTO_EN_USO (sin E6, sin INSERT)
  fila + huella igual     → no registrar_llamada → completar_efectos → 201
  sin fila                → registrar_llamada (429 posible, sin INSERT)
                          → INSERT
                          → UniqueViolation → SELECT + huella
                               igual → completar_efectos → 201
                               distinta → 409 ID_EVENTO_EN_USO
                          → INSERT ok → completar_efectos → 201
```

- El SELECT **no** evita carreras: dos POST simultáneos pueden ver vacío y ambos pasar a INSERT.
- `UniqueViolation` es la garantía definitiva: un ganador persiste; el perdedor **no** inserta segunda fila y entra a huella (201 o 409).
- Interceptar UniqueViolation de este unique **antes** de traducirlo a `RECURSO_DUPLICADO` (`db_error_translator`).

Huella: clasificación, timestamps de captura/procesamiento, variables, severidad. **Excluir** `origen` y `estado_conectividad` (ya definido en auditorías PR1).

### 5. Códigos HTTP

| Situación | HTTP | Cuerpo |
|---|---|---|
| Primer INSERT | 201 | PK interna existente (`EventoEdgeResponse`) |
| Replay idéntico (SELECT o UniqueViolation + huella igual) | 201 | Misma PK; no segunda fila |
| Mismo id, contenido distinto | 409 | `ID_EVENTO_EN_USO`; no persistir el segundo cuerpo |
| Id ausente o malformado | 400 | Sin E6 |
| Ventana E6 llena en camino de INSERT (no CRITICO) | 429 | Sin fila nueva |

### 6. E6 solo en el intento de INSERT

`registrar_llamada` **únicamente** cuando el SELECT de cortesía no halló fila y se va a intentar INSERT. CRITICO sigue sin E6.

El contador es memoria de proceso: **no** se deshace si el INSERT falla después. No hay “devolución” de marca.

**Limitación conocida (aceptada en PR1):** dos primicias concurrentes con el mismo id pueden **ambas** llamar `registrar_llamada` (SELECT vacío en las dos) y dejar **dos marcas** para **un** evento. El unique evita la segunda fila, no la segunda marca. Corregirlo exigiría E6 transaccional o almacen compartido (fuera de PR1). Producto/QA acepta este sesgo.

429: no hay INSERT; el siguiente intento con cuota libre es otra vez camino de INSERT (correcto).

### 7. `completar_efectos` en todo 201

Todo 201 (primicia o replay) ejecuta la misma rutina. **Prohibido** omitir M04/RF-57 solo porque UniqueViolation o el SELECT indicaron replay: si el primer `commit` del evento ganó y M04/alerta no llegaron a persistir, el salto ciego **pierde** efectos.

```
completar_efectos(evento):
  consolidar.execute(evento)          # M04; ver §8
  si el tipo exige alerta RF-57:
      recuperar_alerta_si_falta(...)  # ver §9; no declarado idempotente sin lock
  no reescribir bitácora RF-63 si el evento ya existía (replay)  # ver §10
```

NORMAL / `ERROR_CONFIGURACION`: consolidar y alerta siguen **no** aplicándose (comportamiento actual L210). Replay de NORMAL: no inventar paquete ni alerta.

### 8. M04: reentrar a `consolidar.execute`, sin outbox nuevo

No hay tabla outbox nueva en PR1. El outbox de envío al motor **ya es** `paquetes_inferencia` (`PENDIENTE` + `DrenarPaquetesPendientesUseCase`).

- Replay **debe** llamar `consolidar.execute`.
- Si `obtener_por_evento` encuentra paquete: **no** segundo INSERT de paquete y **no** segundo HTTP inmediato (L191–194). El drenado gestiona `PENDIENTE`/`FALLIDO`.
- Si no hay paquete (crash entre `commit` del evento y `guardar` del paquete): consolidar **crea** la fila. Eso recupera el efecto perdido.
- El HTTP al motor **no** forma parte de la transacción PostgreSQL del evento: I/O externo. Un rollback único desharía un evento ya aceptado (201/CA-8). El `commit` del evento **antes** del HTTP se mantiene.

Dos concurrentes: unique de evento + `bloquear_evento` en consolidar. No se afirma unique SQL de paquete en PR1.

### 9. RF-57: búsqueda por `id_evento_edge_computing` (no idempotencia plena aún)

Hoy **no** existe `obtener_alerta_por_evento_edge` en el repositorio. PR1 **añade** esa consulta.

Rutina:

1. Si el evento no es desviación con severidad: no alerta (igual que ahora).
2. Buscar alerta con `id_evento_edge_computing` = PK interna.
3. Si existe: no llamar `GenararAlertaUseCase`.
4. Si no existe: generar (recupera alerta perdida tras INSERT del evento).

**El SELECT de alerta no evita carreras.** Dos `completar_efectos` concurrentes pueden ver “no hay alerta” y crear dos filas: el modelo **no** tiene unique sobre ese FK.

Protección **definida** para PR1 (sin unique de alerta y sin outbox):

- Tras consolidar, abrir transacción que hace `bloquear_evento` sobre la PK del evento, **vuelve a** consultar alerta y, solo entonces, inserta.
- Hasta que esa serialización esté **en código y cubierta por prueba de concurrencia**, **no** se declara la alerta idempotente.
- Unique SQL sobre `alertas.id_evento_edge_computing` **queda fuera** de PR1 (podría chocar con ventanas RF-57 si producto permite más de una alerta por evento a lo largo del tiempo). Pendiente de producto, no de este cierre.

Best-effort actual (log + `rollback` de la tx de alerta, 201 igual) se mantiene para fallos del generador; el replay posterior es quien reintenta si sigue ausente.

### 10. RF-63: no duplicar bitácora en replay

`DESVIACION_DETECTADA` (L188–204) **solo** en la primicia (INSERT nuevo). Replay: no segundo asiento. 409: no bitácora del cuerpo rechazado.

### 11. HTTP M04 vs transacción del evento

Documentado como restricción de arquitectura: el POST al motor de inferencia **no** se incluye en el `commit` de `eventos_edge_computing`. Recuperación = fila `PENDIENTE` + drenado + replay que crea el paquete si faltaba. Fusionar HTTP en la tx del evento está **excluido** de PR1.

### 12. Pruebas a añadir (no ejecutadas aquí)

Además de G64/DEV-17 (regresión, **ids distintos** en la ráfaga de 60):

| Caso | Esperado |
|---|---|
| Replay idéntico | 201, misma PK, una fila evento, **sin** segunda `registrar_llamada` |
| 61.º evento **nuevo** vs replay del 1.º | El replay no provoca 429; el 61.º id nuevo sí (G64) |
| Id + cuerpo distinto | 409 `ID_EVENTO_EN_USO`, sin segunda fila, sin E6 extra de cortesía |
| Id ausente / malformado | 400, sin E6 |
| Dos POST concurrentes mismo id | Una fila evento; perdedor 201 o 409 según huella |
| Evento persistido **sin** paquete + replay | Un `paquetes_inferencia`; consolidar se invocó |
| Paquete `PENDIENTE` ya existente + replay | Sin segundo paquete ni segundo HTTP inmediato |
| Desviación sin alerta + replay | Una alerta (recuperación) |
| Alerta ya ligada al evento + replay | Sin segunda alerta **si** corre el lock de §9; la prueba de dos POST concurrentes debe fallar el PR si aparecen dos alertas |
| G64 | 201×60 / 429 / CRITICO exceptuado, intacto |

No reescribir informes PASS offline de TC-M03-076 / 077 / 078.

### Relación con el plan PR1 histórico

| Enunciado histórico (conservado arriba) | Este cierre |
|---|---|
| «no llamar consolidar/alerta en replay» | **Derogado para implementación.** Replay llama `completar_efectos`. |
| «RF-57 excluido salvo no reentrar» | **Derogado.** Reentrar solo si no hay alerta; lock obligatorio. |
| «sin segundo paquete ni alerta» como omisión de llamadas | Se cumple **reutilizando** paquete/alerta, no saltando el use case. |
| «Parar si replay dispara M04/alerta» | Parar si replay **duplica** paquete/alerta o si **omite** recuperación cuando faltan. |
| Unique JSONB vs columna | Columna dedicada + unique parcial. |

PR2 (broker `LIBERAR` tras 201), PR3 (outbox hasta ACK), acta CA-6 y PR4 (emisión NORMAL) **no cambian**.

### Decisiones aprobadas (PR1)

1. Columna `id_evento_edge` + unique parcial PostgreSQL.
2. Validación de ID (400) antes de E6.
3. SELECT de cortesía para replay/409; **no** es la barrera de concurrencia.
4. UniqueViolation = garantía ante dos INSERT.
5. 201 replay idéntico; 409 `ID_EVENTO_EN_USO`.
6. E6 solo en camino de INSERT; dos primicias concurrentes pueden dejar dos marcas.
7. Todo 201 ejecuta `completar_efectos`.
8. M04: siempre `consolidar.execute`; reutilizar paquete; drenado de `PENDIENTE`/`FALLIDO`; sin tabla outbox nueva.
9. RF-57: alta de búsqueda por `id_evento_edge_computing`; generar solo si falta; serializar con `bloquear_evento` en la misma transacción que el INSERT de alerta.
10. RF-63: bitácora solo en primicia.
11. HTTP M04 fuera de la transacción del evento.
12. Matriz de pruebas §12, con regresión G64.
13. Acta CA-6 **no** bloquea PR1.

### Decisiones pendientes (no bloquean el diseño de PR1; sí pueden bloquear merge)

1. Nombre de rama de feature / destino de merge.
2. Hash de revisión Alembic (generado al implementar).
3. Aceptación formal de producto de «dos marcas E6 en carrera de primicias».
4. Unique SQL de alerta por evento (fuera de PR1 hasta que RF-57 confirme “una alerta por `id_evento_edge_computing`”).
5. Unique SQL de `paquetes_inferencia` por evento (opcional; hoy lock de aplicación).
6. Criterio de alerta **idempotente** en QA: solo tras prueba de dos POST concurrentes **sin** segunda fila de alerta. Hasta entonces el dictamen es “recuperable + anti-duplicado bajo lock”, no “idempotente”.

### Limitaciones conocidas

- Rate limit no distribuido ni transaccional.
- SELECT previo no serializa primicias.
- Alerta **no** es idempotente en el esquema actual (FK sin unique); depende del lock de §9.
- Si consolidar aborta **después** de soltar el lock de evento y **antes** del lock de alerta, sigue habiendo ventana; la prueba de concurrencia es la red de seguridad.
- 201 puede devolverse con alerta aún ausente si `GenararAlertaUseCase` falla (best-effort); el replay debe poder crearla.
- Este documento no autoriza pytest, migraciones ni Git de escritura.
- PASS offline 076/077/078 intactos.
