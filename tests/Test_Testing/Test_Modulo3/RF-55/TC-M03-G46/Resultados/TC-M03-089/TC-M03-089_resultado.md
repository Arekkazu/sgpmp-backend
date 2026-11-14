# TC-M03-089 — Resultado (cierre documental G46)

Cierre respaldado por la ejecución del **firmware Edge**. El wrapper pytest del backend **no** se declara aprobado.

Fecha de la ejecución firmware: **2026-10-31**.  
Evidencia previa del wrapper (2026-10-25, SKIPPED) conservada en `evidencias/` (no se borró).

---

## 1. Identificación del caso

| Campo | Valor |
|---|---|
| Grupo | **TC-M03-G46** |
| Caso | **TC-M03-089** |
| RF | **RF-55.1** (nivel simple) / **RF-55.2** (nivel compuesto) |
| Caso de uso | CU-02 |
| Tipo | Prueba funcional |
| Prioridad | Alta |
| Criterio de aceptación | Consolidar la mayor severidad entre niveles Edge RF-55.1 y RF-55.2 (`LEVE` < `MODERADO` < `CRITICO`) |

---

## 2. Objetivo

Verificar que, cuando los niveles Edge simple y compuesto producen severidades diferentes, el evento consolidado conserva la **mayor** severidad.

Copiar `severidad` ya asignada en RF-56 **no** cubre este cálculo.

---

## 3. Entorno

| Ítem | Valor |
|---|---|
| Python | 3.13.7 (`C:\Users\ll529\AppData\Local\Programs\Python\Python313\python.exe`) |
| pytest | 9.0.3 |
| Plataforma | win32 / Windows-11-10.0.26200-SP0 |
| Raíz de ejecución | `.worktrees/sgpmp-rf55-validation/raspberry` |
| Config | `pyproject.toml` (`pythonpath = ["."]`) |
| Docker | No usado |
| PostgreSQL | No usado |
| MQTT real | No usado |
| Conexiones externas | Ninguna |

---

## 4. Archivo y función ejecutados

`raspberry/tests/test_reglas_compuestas.py::test_compuesta_que_prevalece_conserva_la_maxima_severidad`

Ruta absoluta del firmware:

`c:\Users\ll529\OneDrive\Documentos\integrador\.worktrees\sgpmp-rf55-validation\raspberry`

Motor: `edge_agent.reglas.evaluador.evaluar_lote` → `_evaluar_rf55_2` → `_con_maxima_severidad`.  
Sin mocks de la consolidación.

---

## 5. Comando exacto y resultado real

Desde la raíz del firmware:

```
python -m pytest tests/test_reglas_compuestas.py::test_compuesta_que_prevalece_conserva_la_maxima_severidad -v
```

| Métrica | Valor |
|---|---|
| Recolectados | 5 |
| Aprobados | 5 |
| Fallidos | 0 |
| Omitidos | 0 |
| Duración pytest | **5 passed in 0.07s** |
| Código de salida | **EXIT=0** |

Transcripción literal de consola: `TC-M03-089_evidencia_ejecucion.txt`.

---

## 6. Tabla de los cinco escenarios ejecutables

| Escenario | RF-55.2 | RF-55.1 | Final | Origen | Resultado |
|---|---|---|---|---|---|
| 1 | MODERADO | CRITICO | CRITICO | RF-55.1 | PASS |
| 2 | LEVE | CRITICO | CRITICO | RF-55.1 | PASS |
| 3 | CRITICO | MODERADO | CRITICO | RF-55.2 | PASS |
| 4 | CRITICO | CRITICO | CRITICO | RF-55.2 | PASS |
| 5 | LEVE | None | LEVE | RF-55.2 | PASS |

Ids pytest (nodos del parametrize):

1. `[cuerpo0-lecturas0-umbral_t0-CRITICO-MODERADO-CRITICO-RF-55.1]` — Tipo A MODERADO; T 32,5 °C crítica.
2. `[cuerpo1-lecturas1-umbral_t1-CRITICO-LEVE-CRITICO-RF-55.1]` — THI 72,82 LEVE; 25 °C crítica.
3. `[cuerpo2-lecturas2-umbral_t2-CRITICO-CRITICO-MODERADO-RF-55.2]` — THI ~86,57 CRITICO; T en precaución = MODERADO.
4. `[cuerpo3-lecturas3-umbral_t3-CRITICO-CRITICO-CRITICO-RF-55.2]` — empate CRITICO; decide RF-55.2.
5. `[cuerpo4-lecturas4-umbral_t4-LEVE-LEVE-None-RF-55.2]` — THI LEVE; T en banda `normal` (sin severidad RF-55.1).

En todos, `prevalece_sobre_regla_simple` es **True**.

No se ejecutó (ni se presenta como PASS) el vector **RF-55.1 = LEVE / RF-55.2 = MODERADO**: RF-55.1 no produce `LEVE` en esta implementación (`_SEVERIDAD`: `precaucion` → MODERADO, `critico` / `fuera_de_rango` → CRITICO).

---

## 7. Evidencia de los asserts

Cada escenario comprueba:

| Assert | Esperado |
|---|---|
| `evento.clasificacion` | `DESVIACION_COMPUESTA` |
| `evento.severidad` | severidad final de la tabla |
| `a_payload(evento)["severidad"]` | misma severidad final |
| `metadata_edge.severidad_regla` | valor RF-55.2 (antes de consolidar) |
| `metadata_edge.severidad_rf55_1` | valor RF-55.1 o `None` |
| `metadata_edge.severidad_origen` | `RF-55.1` o `RF-55.2` |
| `metadata_edge.id_regla_alerta` | `12` |

---

## 8. Consolidación en firmware

La consolidación **existe** en producción del Edge:

- `_con_maxima_severidad` en `edge_agent/reglas/evaluador.py`.
- Invocada desde `_evaluar_rf55_2` cuando el evento es `DESVIACION_COMPUESTA` y `prevalece_sobre_regla_simple is True`.
- Compara con `SEVERIDADES = (LEVE, MODERADO, CRITICO)` (`SEVERIDADES.index`): **LEVE < MODERADO < CRITICO**.
- Solo **sube** la severidad; en empate deja RF-55.2 y `severidad_origen = "RF-55.2"`.
- Si RF-55.1 no clasifica (`None`), se conserva RF-55.2.

No se sustituyó esta lógica por un `max` inventado en el test.

---

## 9. Limitaciones

1. **RF-55.1 no produce LEVE** en el nodo. El escenario 55.1 LEVE / 55.2 MODERADO **no** se ejecutó y **no** forma parte del 5/5.
2. El test del backend `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G46/test_tc_m03_g46.py::test_tc_m03_089_max_severidad_entre_niveles_edge` **continúa SKIPPED** (`skip_sin_motor_edge` / `localizar_motor_edge()` retorna `None`). Evidencia 2026-10-25: `evidencias/pytest.txt`, `evidencias/pytest.html`, `evidencias/pytest.xml`, `evidencias/TC-M03-089_resultado_backend_skipped_2026-10-25.md`. **No se declara aprobado el wrapper del backend.**
3. Esta ejecución valida el **cálculo y la consolidación en el nodo**, no la persistencia en PostgreSQL (`modulo3.eventos_edge_computing`) ni MQTT físico / laboratorio Raspberry.

---

## 10. Veredicto

**APROBADO — 100 % de los escenarios ejecutables de consolidación cubiertos y superados (5/5).**

El cierre documental del caso queda respaldado por la ejecución del firmware (`evaluar_lote`, EXIT=0).

No se afirma que `test_tc_m03_g46.py` haya pasado. No se afirma validación del entorno físico ni de RF-56.
