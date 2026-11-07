# Auditoría final — TC-M03-G45 / TC-M03-081

Fecha: 2026-10-31.  
Modo: auditoría. **Sin** Git, **sin** cambios de código ni pruebas, **sin** alterar `INFORME_EJECUCION_G45.md` ni `Resultados/TC-M03-081/` (SKIPPED 2026-10-25).

Firmware: `.worktrees/sgpmp-rf55-validation/raspberry/` (`qa/rf55-validation-e618a75`).  
Evidencia nueva: `Resultados/evidencias/run-2026-10-31-auditoria-final/`.

---

## 1. Objetivo y alcance

Determinar con evidencia **reproducible** si TC-M03-081 CUMPLE el tratamiento de mediciones inválidas en Edge (RF-55.1), **sin** asumir que el informe del 2026-10-31 cierra el caso.

**Dentro de alcance (ejecutado):** motor `evaluar_lote` / `lecturas_invalidas`; pytest `test_parser_entradas.py`; agente con FakeLink/Harness; inyector P1–P4; sonda de `""` y `False` sobre el evaluador existente.

**Fuera de alcance (pendiente):** Raspberry física, MQTT real (Mosquitto), pytest backend G45 (sigue SKIPPED), G58 DTO.

No es prueba de integración física. El harness y el inyector usan dobles (`FakeLink`, fuente guionada).

---

## 2. Requisito y criterios de aceptación

Fuentes: `docs/CONTRATO_EVENTO_EDGE.md` §2.1; INC-M03-156-G45; `test_tc_m03_g45.py` (objetivo: nulo/malformado → log, sin clasificación falsa); RF-55.1 (clasificación en el nodo).

**Inválido siempre:** `null`/`None`, texto (incluida cadena vacía y `"31.0"`), booleanos, NaN, +Inf, −Inf.

**Inválido por rango físico (distinto de formato):** HR fuera de [0, 100]; pH fuera de [0, 14]; OD negativo. El valor **sí** puede ir como telemetría cruda; **no** se clasifica.

**Esperado por lectura inválida:**

1. Descarte **antes** de umbrales / `evaluar_simple`.
2. Sin `NORMAL`, `DESVIACION_*`, ni severidad LEVE/MODERADO/CRÍTICO.
3. Sin evento MQTT de desviación (`sgpmp/<serial>/evento`).
4. WARNING + historial `LECTURA_INVALIDA` cuando corre el agente.
5. No contamina lecturas válidas de la misma captura (ni la ventana).
6. No usar `ERROR_CONFIGURACION` para el dato malo (eso es regla/umbral, TC-M03-083).

INC-M03-156 documentó clasificaciones falsas **antes** del filtro; el código actual es esa corrección. Esta auditoría reejecuta QA; no reabre el defecto histórico como fallo vigente.

---

## 3. Matriz de escenarios

| ID | Tipo | Entrada | Esperado | Obtenido | Evidencia | Veredicto |
|---|---|---|---|---|---|---|
| U-None | Unitario (`evaluar_lote`) | `None` | Sin eventos | `[]` | `pytest_parser.txt` `...[None]` | PASS |
| U-abc | Unitario | `"abc"` | Sin eventos | `[]` | pytest `[abc]` | PASS |
| U-31txt | Unitario | `"31.0"` | Sin eventos (no se parsea a float) | `[]` | pytest `[31.0]` | PASS |
| U-True | Unitario | `True` | Sin eventos | `[]` | pytest `[True]` | PASS |
| U-False | Sonda (no está en `MALOS`) | `False` | Inválido; 0 eventos | `es_numero=False`, `eventos=[]` | `probe_vacio_false.txt` | PASS |
| U-empty | Sonda | `""` | Inválido; 0 eventos | motivo `''`; `eventos=[]` | `probe_vacio_false.txt` | PASS |
| U-nan/inf | Unitario | NaN, ±Inf | Sin eventos | `[]` | pytest `[nan]` `[inf]` `[-inf]` | PASS |
| U-THI | Unitario | T o HR inválida + compañera válida | Sin THI / sin ERROR_CONFIG | `[]` | `test_thi_no_clasifica_*` | PASS |
| U-hidrica | Unitario | pH u OD inválido | Sin evento | `[]` | `test_hidrica_*` | PASS |
| U-fisico | Unitario | HR 150/−20, pH −3/20, OD −1 | Sin clasificación | `[]` | `test_fuera_de_rango_fisico_*` | PASS |
| U-bordes | Unitario | HR 0/100, pH 0/14 | Válidos (`lecturas_invalidas` vacío) | PASS | pytest bordes | PASS |
| U-misma-captura | Unitario | T=30 + HR `None` | Solo DESVIACION_SIMPLE CRITICO de T | Coincide | `test_la_lectura_valida_*` | PASS |
| U-ventana | Unitario | HR `inf` luego T | Sin THI | `[]` | `test_un_dato_invalido_no_entra_*` | PASS |
| G-lora | Gateway (doble LoRa) | NaN/±Inf en una medición | Se descarta esa; la otra se lee | HR 60 conservada | `test_gateway_*` | PASS |
| A-agente | Agente + FakeLink | NaN, None, HR 150 | `evento==[]`; 3× LECTURA_INVALIDA; WARNING×3; None/NaN sin telemetry | Coincide | `test_agente_no_publica_*` | PASS |
| I-P1 | Inyector (doble MQTT) | T=32.5, HR `null`; umbrales `[]` | LECTURA_INVALIDA HR; T sin umbral → ERROR_CONFIG (083), **no** DESVIACION | OK 1/1 | `inyector_P1.txt` | PASS |
| I-P2 | Inyector | pH `"abc"`, OD `true` | 0 eventos; 2× LECTURA_INVALIDA | OK 1/1 | `inyector_P2.txt` | PASS |
| I-P3 | Inyector | HR 150, pH 20, T y OD válidos sin umbral en el caso | 2× LECTURA_INVALIDA; 2× ERROR_CONFIG (sin umbral); **sin** DESVIACION | OK 1/1 | `inyector_P3.txt` | PASS |
| I-P4 | Inyector | T=30 + HR `null` (umbrales globales) | LECTURA_INVALIDA HR; DESVIACION_SIMPLE CRITICO T | OK 1/1 | `inyector_P4.txt` | PASS |
| B-skip | Backend | `test_tc_m03_g45.py` | No se reejecutó (restricción) | SKIPPED 2026-10-25 vigente | `TC-M03-081/` | N/A (no cierre) |
| F-hw | Integración física | Nodo + radio | No ejecutada | — | — | PENDIENTE |
| F-mqtt | MQTT real | Mosquitto | No ejecutada | — | — | PENDIENTE |

Ninguna fila de alcance offline es FAIL.

---

## 4. Pruebas ejecutadas y comandos

Directorio de trabajo del firmware: `.worktrees/sgpmp-rf55-validation/raspberry/`

```
python -m pytest tests/test_parser_entradas.py -v --tb=short
  --junitxml=<evid>/pytest_parser.xml
  --html=<evid>/pytest_parser.html --self-contained-html
```

Salida: **51 passed in 0.33s**, EXIT=0.  
`<evid>` = `.../G45/Resultados/evidencias/run-2026-10-31-auditoria-final/`

```
python scripts/inyectar_lecturas.py scripts/casos_rf55.json -v --caso "P1 TC-M03-081 humedad nula con THI"
python scripts/inyectar_lecturas.py scripts/casos_rf55.json -v --caso "P2 TC-M03-081 pH no numerico y OD booleano"
python scripts/inyectar_lecturas.py scripts/casos_rf55.json -v --caso "P3 TC-M03-081 fuera de rango fisico (HR 150 %, pH 20)"
python scripts/inyectar_lecturas.py scripts/casos_rf55.json -v --caso "P4 TC-M03-081 la lectura valida de la captura se sigue clasificando"
```

Salida: **1/1 OK** en cada caso, EXIT=0. Los WARNING de descarte salen por stderr (PowerShell los etiqueta NativeCommandError); no son fallo del inyector.

Sonda `""` / `False`: invocación a `_es_numero`, `lecturas_invalidas` y `evaluar_lote` **sin** modificar `test_parser_entradas.py`. Evidencia: `probe_vacio_false.txt`. (El intento de importar `test_reglas_compuestas` desde stdin falló; la matriz de tipos ya estaba impresa.)

No se ejecutó pytest de `sgpmp-backend` G45.

---

## 5. Resultados reales (extracto)

**Unitario / agente (51 passed):** `None`, `"abc"`, `"31.0"`, `True`, NaN, ±Inf ignorados por umbral simple, Tipo A, THI e hídrica. T=30 + HR nula → solo CRITICO de T. Agente: cero publicaciones en `evento`.

**Inyector P2:** 0 eventos MQTT simulados; historial dos `LECTURA_INVALIDA` (ph `'abc'`, OD `True`).

**Inyector P4:** un evento `DESVIACION_SIMPLE` / `CRITICO` / `UMBRAL_AMBIENTAL` para T=30; HR `None` solo en historial local.

**P1/P3:** los eventos publicados son `ERROR_CONFIGURACION` por **falta de umbral RF-17** (`umbrales: []` en el caso), no por clasificar el nulo/HR 150 como desviación. El dato inválido queda `LECTURA_INVALIDA`.

**Sonda:** `""` y `False` → `es_numero=False`, 1 inválida, 0 eventos.

---

## 6. Evidencias y código

| Pieza | Ruta | Líneas |
|---|---|---|
| `_es_numero` | `edge_agent/reglas/evaluador.py` | 660–661 |
| `lecturas_invalidas` | mismo | 260–282 |
| Filtro en `evaluar_lote` | mismo | 312–315 |
| `evaluar_simple` no clasifica no-número | mismo | 119–120 |
| Agente WARNING + historial | `edge_agent/agent.py` | 413–434 |
| `_es_finito` (no telemetría) | mismo | 699–700 |
| `registrar_invalida` | `edge_agent/historial.py` | 112–131 |
| LoRa NaN/Inf | `edge_agent/lora/gateway.py` | 364–373 |
| Contrato | `docs/CONTRATO_EVENTO_EDGE.md` | §2.1 |
| INC | `docs/incidencias/INC-M03-156-G45.md` | — |

Evidencias 2026-10-31 (nuevas, no pisan SKIPPED):

- `evidencias/run-2026-10-31-auditoria-final/pytest_parser.{txt,html,xml}`
- `inyector_P1.txt` … `inyector_P4.txt`
- `probe_vacio_false.txt`

SKIPPED backend intacto: `Resultados/TC-M03-081/`.

---

## 7. Limitaciones

- Sin Raspberry física ni radio LoRa real.
- Sin Mosquitto / MQTT de laboratorio; `evento` se afirma en **FakeLink** / inyector.
- `test_tc_m03_g45.py` del backend permanece SKIPPED.
- `FakeLoraSource` no genera nulos; hace falta inyector o `FuenteFija`.
- `""` y `False` no están en `MALOS`; cubiertos por sonda, no por pytest parametrizado.
- HR 150 % viaja como telemetría cruda (contrato D6 / G58), no como evento de desviación.
- P1/P3 mezclan 081 (dato inválido) con 083 (sin umbral) porque el caso pone `umbrales: []`.

---

## 8. Dictamen final

**CUMPLE PARCIALMENTE / PENDIENTE**

**Por qué no CUMPLE (cierre integral):** el caso de laboratorio pide nodo y, en el runner backend, el script G45 sigue SKIPPED. Esta auditoría **no** afirma cierre físico ni MQTT real.

**Por qué no NO CUMPLE:** en el alcance offline reejecutado no hay contradicción: las entradas inválidas exigidas se descartan antes de umbrales, no hay clasificación ni evento de desviación falsos, hay `LECTURA_INVALIDA` + WARNING en agente/inyector, y la lectura válida de la misma captura se clasifica (P4 / test de captura mixta). `""` y `False` se comportan como el contrato (texto/booleano).

**Por qué PARCIALMENTE / PENDIENTE:** evidencia offline **favorable y completa** para firmware de validación + inyector; faltan validaciones **exigibles para cerrar G45 en laboratorio**.

El `INFORME_EJECUCION_G45.md` (CUMPLE offline) es coherente con esta reejecución; **no** se usa como único cierre.

---

## 9. Validaciones pendientes (concretas)

1. En Raspberry TEST: inyectar `None`/`"abc"`/NaN (o equivalentes de sensor) y `python -m edge_agent.inspeccionar historial --clasificacion LECTURA_INVALIDA`.
2. Confirmar en Mosquitto que **no** aparece `sgpmp/<serial>/evento` de desviación para esas capturas.
3. Confirmar que la telemetría de HR 150 % (si se usa) llega cruda y **no** clasificada.
4. Desbloquear o sustituir `test_tc_m03_g45.py` del backend (sigue SKIPPED; no ejecutado aquí).
5. Opcional: añadir `""` y `False` a `MALOS` en pytest (cambio de prueba; **no** hecho en esta auditoría).
