# Informe de ejecución — TC-M03-G45 / TC-M03-081

Fecha de consolidación: 2026-10-31.  
Alcance: pruebas **offline del firmware** en `.worktrees/sgpmp-rf55-validation/raspberry/` (`qa/rf55-validation-e618a75`).  
Esta ejecución **no** es Raspberry física, **no** usa Mosquitto ni MQTT de laboratorio, **no** desbloquea el pytest de `sgpmp-backend`.

El informe histórico `Resultados/TC-M03-081/TC-M03-081_resultado.md` (25 de octubre de 2026, SKIPPED del runner backend) **permanece vigente** para ese runner. Este documento no lo sustituye ni modifica sus evidencias `pytest.{txt,html,xml}`.

---

## 1. Identificación del caso

| Campo | Valor |
|---|---|
| Grupo | TC-M03-G45 |
| Subcaso | TC-M03-081 |
| Requisito | RF-55.1 |
| Caso de uso | CU-02 |
| Resultado | **CUMPLE** (implementación Edge de validación, evidencia automatizada offline) |
| Suite ejecutada | `raspberry/tests/test_parser_entradas.py` |
| Pytest | **51 passed** en 0,50 s (2026-10-31) |
| Firmware | `.worktrees/sgpmp-rf55-validation/raspberry/` |
| Backend | `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G45/test_tc_m03_g45.py` — **SKIPPED** (`skip_sin_motor_edge`) |

## 2. Objetivo de la prueba

Comprobar que el firmware Edge detecta, descarta y registra mediciones nulas o con formato inválido **antes** de evaluar umbrales, de modo que:

- no produzcan clasificación `NORMAL`, `LEVE`, `MODERADO` o `CRITICO`;
- no generen evento de desviación;
- no se publiquen como evento RF-55 en el topic `evento`;
- quede evidencia de descarte (log WARNING e historial `LECTURA_INVALIDA`).

El rechazo Pydantic del DTO backend (G58) **no** sustituye este parser.

## 3. Datos inválidos evaluados

La matriz `MALOS` en `test_parser_entradas.py` L17 es:

`None`, `"abc"`, `"31.0"`, `True`, `math.nan`, `math.inf`, `-math.inf`.

| Entrada | Tratamiento observado en código | Cubierto por pytest 2026-10-31 |
|---|---|---|
| `None` | `_es_numero` falso → inválida | Sí (`MALOS`; P1/P4 en inyector, no reejecutado) |
| Cadenas no numéricas (`"abc"`, `"31.0"`) | `str` no es `int`/`float` → inválida | Sí (`MALOS`) |
| Cadena vacía `""` | Misma rama de `_es_numero` | **No** hay parámetro explícito (limitación §10) |
| Booleanos (`True`; `False` por ser `bool`) | Excluidos de `_es_numero` | `True` sí; `False` no parametrizado aparte |
| `NaN`, `+Inf`, `−Inf` | No finitos; gateway y agente los descartan | Sí (`MALOS` + `test_gateway_descarta_mediciones_no_finitas`) |

`_es_numero` (`evaluador.py` L660–661): `int`/`float`, no `bool`, y `math.isfinite`.

## 4. Validaciones del parser y del agente Edge

No hay parser HTTP. El camino es fuente → `Reading` → `Agent._capturar`.

| Capa | Archivo | Líneas | Función |
|---|---|---|---|
| Criterio numérico | `edge_agent/reglas/evaluador.py` | 660–661 | `_es_numero` |
| Filtro RF-55 | mismo | 260–282 | `lecturas_invalidas` (nulo/no numérico/no finito o fuera de rango físico HR/pH/OD) |
| Antes de umbrales | mismo | 312–315 | `evaluar_lote` quita inválidas **antes** de RF-55.2 y `evaluar_simple` |
| Defensa extra | mismo | 119–120, 224–225 | `evaluar_simple` / `_peor_nivel` no clasifican si no es número |
| Agente | `edge_agent/agent.py` | 413–434 | WARNING + historial; telemetría solo si `_es_finito` |
| Finitud telemetría | mismo | 699–700 | `_es_finito` (igual que `_es_numero`) |
| Historial | `edge_agent/historial.py` | 47, 112–131 | `LECTURA_INVALIDA`, `severidad=None`, `ruta=LOCAL` |
| LoRa | `edge_agent/lora/gateway.py` | 364–373 | Descarta NaN/Inf **por medición** |
| Simulador | `edge_agent/sources.py` | 62–72 | `FakeLoraSource`: solo `uniform(min, max)` finito |
| Inyector QA | `scripts/inyectar_lecturas.py` | 388–392 | Conserva `null`, texto y booleanos (no reejecutado el 2026-10-31) |

## 5. Evidencia de descarte antes de umbrales

`evaluar_lote` (L312–315) filtra con `lecturas_invalidas` **antes** de reglas y de `evaluar_simple`. El agente llama `lecturas_invalidas` (L413) **antes** del `try` de evaluación (L435–447).

Pytest: `test_umbral_simple_y_tipo_a_ignoran_valores_invalidos`, THI e hídrica parametrizados con `MALOS` → `evaluar(...) == []` (sin `DESVIACION_*` ni `ERROR_CONFIGURACION`). El inválido no culpa a la regla.

T=30 °C + HR `None` en la misma captura: solo `DESVIACION_SIMPLE`/`CRITICO` de T (`test_la_lectura_valida_de_la_captura_se_sigue_clasificando`). HR infinita no entra a la ventana (`test_un_dato_invalido_no_entra_a_la_ventana_de_correlacion`).

## 6. Evidencia de logging y `LECTURA_INVALIDA`

`test_agente_no_publica_ni_encola_valores_invalidos` (Harness + `FuenteFija` con NaN, `None` y HR 150 %):

- `caplog.text.count("descartada para RF-55") == 3` — WARNING `agent.py` L415–419.
- Historial: tres filas `clasificacion == "LECTURA_INVALIDA"`, `ruta=LOCAL`, `detalle.motivo` presente; valores `"nan"`, `"None"`, `150.0`.

Gateway: `test_gateway_descarta_mediciones_no_finitas` exige `"valor no finito"` en el log; la medición hermana finita sí se lee.

## 7. Evidencia de ausencia de publicaciones falsas en `evento`

Mismo test de agente:

- `h.link.on("evento") == []`
- NaN y `None` **no** salen en `telemetry`
- HR 150 % sí sale como telemetría cruda (dato finito; **no** clasificado)
- `json.dumps(..., allow_nan=False)` sobre todo lo publicado

No se afirma publicación ni recepción en broker real.

## 8. Resultado de ejecución

```
python -m pytest tests/test_parser_entradas.py -q --tb=line
```

Directorio: `.worktrees/sgpmp-rf55-validation/raspberry/`  
Salida: **51 passed in 0.50s**, código de salida 0.  
Fecha: 2026-10-31.  
No se reejecutó para este informe.

No se ejecutó el inyector `casos_rf55.json` P1–P4 en esta fecha.

## 9. Archivos y funciones revisados

Ver tabla del §4. Pruebas: `raspberry/tests/test_parser_entradas.py` (51 casos: motor, LoRa, agente). El script backend `test_tc_m03_g45.py` **no** se usó como oráculo de esta corrida.

## 10. Limitaciones

- No se ejecutó en Raspberry física.
- El caso del backend (`test_tc_m03_g45.py`) continúa SKIPPED; evidencias 2026-10-25 sin alterar.
- El simulador predeterminado (`FakeLoraSource`) no genera valores nulos; G45 se inyecta con `FuenteFija` / lecturas sintéticas / gateway de prueba.
- La cadena vacía no tiene parametrización explícita (cae en `_es_numero`, no en `MALOS`).
- Los valores fuera de rango físico (p. ej. HR 150 %) pueden transmitirse como telemetría cruda **sin** clasificarse (decisión D6 de INC-M03-156-G45).

## 11. Dictamen final

**CUMPLE** para la implementación Edge de validación, con evidencia automatizada offline (`51 passed` en `test_parser_entradas.py`).

Los datos nulos y de formato inválido se descartan antes de umbrales, no generan clasificación RF-55 ni evento MQTT de desviación en el harness, y quedan WARNING + `LECTURA_INVALIDA`.

## 12. Actividad pendiente

Validación en **nodo físico** (historial `LECTURA_INVALIDA` vía `inspeccionar`, sin MQTT inventado en este informe) para el cierre integral de laboratorio. Opcional: P1–P4 del inyector en ese nodo.
