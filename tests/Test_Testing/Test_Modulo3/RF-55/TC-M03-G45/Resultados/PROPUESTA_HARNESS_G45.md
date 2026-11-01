# Propuesta de harness G45 (TC-M03-081) — no ejecutado

Fecha: 2026-10-31.  
Estado: **diseño listo**. **No se ejecutó.** No se tocó systemd, `/var/lib/sgpmp-edge`, MQTT ni código de producción. Este archivo **no** sustituye `INFORME_EJECUCION_G45.md` ni `AUDITORIA_FINAL_G45.md`. G45 **no** se declara aprobado.

Firmware de referencia (solo lectura): `.worktrees/sgpmp-rf55-validation/raspberry/` (`qa/rf55-validation-e618a75`).

Archivos temporales del harness (QA, no producción):

- `Resultados/evidencias/harness-propuesto-2026-10-31/harness_g45.py`
- `Resultados/evidencias/harness-propuesto-2026-10-31/escenarios_p1_p4.json`

---

## 1. Pipeline real (sin reimplementar validación)

| Paso | Símbolo real | Archivo |
|---|---|---|
| Construcción de lectura | `Reading(...)` | `edge_agent/sources.py` |
| Fuente del agente systemd | `FakeLoraSource.read` / `LoraGateway` | `sources.py`, `lora/gateway.py` |
| Captura | `Agent._capturar` | `edge_agent/agent.py` |
| Filtro RF-55.1 | `lecturas_invalidas` | `edge_agent/reglas/evaluador.py` |
| Criterio numérico del filtro | `_es_numero` | mismo (`int`/`float`, no `bool`, `isfinite`) |
| Telemetría JSON | `_es_finito` + `_telemetry_payload` + `Buffer.enqueue(KIND_TELEMETRY)` | `agent.py` |
| Clasificación | `evaluar_lote` (vuelve a filtrar inválidas **antes** de reglas) | `evaluador.py` |
| Evento MQTT (en servicio: Mosquitto; aquí: FakeLink) | `Agent._encolar_evento` → topic `evento` | `agent.py`, `reglas/evento.py` `a_payload` |
| Historial inválido | `Historial.registrar_invalida` → `LECTURA_INVALIDA`, `ruta=LOCAL` | `edge_agent/historial.py` |
| Historial NORMAL / evento | `registrar_normal` / `registrar_evento` | mismo |

Dobles **permitidos** (I/O, no lógica RF-55):

- `FuenteFija`: entrega `Reading` guionados (el servicio usa FakeLora, que **no** puede emitir `null`/texto/bool).
- `FakeLink`: captura `publish` en memoria; `mqtt_host` no se usa. **No** hay PUBLISH real.

`scripts/inyectar_lecturas.py` ya arma el `Agent` real con el mismo patrón y `mqtt_host=qa.invalid`. Este harness es la versión G45, aislada, con umbral de temperatura **solo** el id 7 de `casos_rf55.json`.

---

## 2. Por qué no se corre contra el `edge-agent` de la Pi

El servicio vivo (`PID` reciente 794) tiene `EDGE_SOURCE=fake` y `EDGE_FAKE_VARIABLES="Humedad Relativa:%:71:73"`. Meter P1–P4 ahí exige cambiar env y/o reiniciar. **Prohibido** en esta orden.

El harness corre **fuera** de systemd, en `tempfile.TemporaryDirectory` (`g45-harness-*`): `historial.db` y `buffer.db` propios. No escribe `/var/lib/sgpmp-edge/historial.db`.

---

## 3. Configuración: qué hay y qué no se inventa

| Recurso | Origen | Uso en el harness |
|---|---|---|
| Umbral temperatura id **7** (18–32 °C, bandas 18–24 / 24–28 / 28–32) | `scripts/casos_rf55.json` (bloque global) | Sí: clasificar T válida en P1/P3/P4 |
| Umbral HR / pH / OD | **No** está en ese global | **No se inventa** |
| Umbral 65 «Humedad Relativa» de la Pi | Laboratorio G38, otro nombre de variable | **No** se copia: no es el catálogo `humedad_relativa` del parser |
| Reglas THI / calidad hídrica | JSON de casos P1–P3 | **No** se cargan: evitan RF-55.2 y `ERROR_CONFIGURACION` de regla |

`casos_rf55.json` P1 y P3 ponen `"umbrales": []`. Eso mezcla **TC-M03-083** (`ERROR_CONFIGURACION` por T/OD sin umbral) con 081. El harness **no** replica esa mezcla: T usa el umbral 7; OD de P3 se **omite** (limitación documentada).

---

## 4. Escenarios de entrada (este pedido)

| ID | Inválido | Válidas en la misma captura |
|---|---|---|
| **P1** | `humedad_relativa = null` | `temperatura_ambiente = 32.5` |
| **P2** | `ph = "abc"` y `oxigeno_disuelto = true` | ninguna |
| **P3** | HR `150`, pH `20` | T `30` (OD del JSON **no** se envía) |
| **P4** | `oxigeno_disuelto = true` | T `30` (booleano + válida, como pidió esta orden; el P4 del JSON era HR `null`, ya cubierto en P1) |

---

## 5. Matriz de resultados **esperados** (no obtenidos: no ejecutado)

Criterio: inválido **antes** de umbrales; `LECTURA_INVALIDA` local; WARNING `descartada para RF-55`; sin `DESVIACION_*` por el dato malo; `ERROR_CONFIGURACION` solo si una **válida** no tiene umbral (083, no 081).

| ID | Validación | Historial | Evento `evento` | Telemetría | PASS si |
|---|---|---|---|---|---|
| P1 | HR: no numérico/no finito (`None`). T: finita, no inválida | 1× `LECTURA_INVALIDA` (HR, `ruta=LOCAL`) + 1× `DESVIACION_SIMPLE` T | **1** `DESVIACION_SIMPLE` / **CRITICO** / `UMBRAL_AMBIENTAL` (32.5 fuera de [18, 32], igual que S4 del JSON) | Solo T `32.5` (None no es JSON finito) | HR no genera evento; T sí se clasifica |
| P2 | ambas no numéricas (`str`, `bool`) | 2× `LECTURA_INVALIDA` | **0** | **0** | ningún evento ni 083 |
| P3 | HR 150 y pH 20 fuera de rango físico; T finita válida | 2× `LECTURA_INVALIDA` (HR, pH) + 1× `DESVIACION_SIMPLE` T | **1** `DESVIACION_SIMPLE` / **CRITICO** (T=30 en banda crítico 28–32) | T `30`, HR `150`, pH `20` (finitos crudos) | inválidos sin clasificación; T sí |
| P4 | OD `true` no numérico; T=30 válida | 1× `LECTURA_INVALIDA` (OD) + 1× `DESVIACION_SIMPLE` T | **1** `DESVIACION_SIMPLE` / **CRITICO** | Solo T `30` | el bool no clasifica; T sí |

Severidad Edge RF-55.1 (bandas del umbral 7, no la fórmula % de G44): `precaucion`→MODERADO, `critico` o fuera de rango→CRITICO. No hay LEVE en este umbral.

### Divergencia respecto a `casos_rf55.json` (inyector)

| Caso JSON | Esperado JSON | Por qué el harness G45 difiere |
|---|---|---|
| P1 `umbrales: []` | `LECTURA_INVALIDA` + `ERROR_CONFIGURACION` T | JSON no carga umbral 7 → 083. Harness sí carga 7 → DESVIACION T, que es 081 aislado |
| P3 incluye OD 3.9 | 2× inválida + 2× `ERROR_CONFIGURACION` | OD sin umbral = 083. Harness omite OD |
| P4 JSON HR `null` | inválida HR + DESVIACION T | Cubierto por P1 + P4 de esta orden (bool + T) |

---

## 6. Cómo ejecutarlo cuando se autorice (local, no Pi)

Desde el worktree firmware, o con el `sys.path` del script:

```
python Resultados/evidencias/harness-propuesto-2026-10-31/harness_g45.py
```

Salida prevista: `resultado_local.json` en la misma carpeta (tmp ya borrado al salir). Contrastar con la matriz §5. **No** es cierre MQTT ni cierre del nodo 794.

Para un cierre físico posterior haría falta un canal autorizado en el servicio vivo (fuera de alcance de este harness).
