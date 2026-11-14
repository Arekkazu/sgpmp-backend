# Auditoría de diagnóstico — TC-M03-G43 / RF-55.1

Fecha: 2026-10-30. **Solo inspección.** No se ejecutó pytest, no se modificó producción, no se alteraron resultados 2026-10-25.

---

## 1. Estado de Git (sgpmp-backend)

| Campo | Valor |
|---|---|
| Rama | `laura` |
| HEAD | `d1df708217868f77b4dbed32d65da5b172c9e6d2` (coincide con lo esperado) |
| Tracking | `ahead 538` vs `origin/laura` |
| Merge/rebase/stash en curso | no |

Working tree **sucio y ajeno a G43** (no se tocó):

- Deleted unstaged: `tests/Test_Testing/Resultados_M09_RF21-23_2026-10-06.md`, `TCs_M09_v2_2026-10-06.md`
- Modified: `tests/biological_assets/…`, `tests/integration/conftest.py` y varios `test_inc_m02_*`
- Untracked: G34/G35/G36, restos G38, auxiliares G41, G57, M09 G94, `mochawesome-report/`, etc.

No hay commit, push, merge, rebase, stash, reset ni clean en esta fase.

---

## 2. Estructura real de G43

Ruta: `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G43/`

| Pieza | Estado |
|---|---|
| `test_tc_m03_g43.py` | Existe. Tres funciones independientes; **no** usa `pytest.mark.parametrize` |
| `pytest.ini` / config propia G43 | No hay. Usa `pytest.ini` raíz del backend |
| `Resultados/TC-M03-076/` | Existe + `evidencias/pytest.{txt,html,xml}` |
| `Resultados/TC-M03-077/` | Igual |
| `Resultados/TC-M03-078/` | Igual |
| Informe agrupado único de los tres | No hay (correcto) |
| Fixtures de umbral/medición G43 | **No hay** |
| `conftest.py` local | **No hay** |

Falta respecto al enunciado de parametrización: el script de matriz **no parametriza**; solo llama `skip_sin_motor_edge` tres veces.

---

## 3. Implementación encontrada (backend vs Edge)

### En `sgpmp-backend` (este repo)

| Pregunta | Hallazgo |
|---|---|
| ¿Motor de clasificación por umbrales en Edge? | **No.** `localizar_motor_edge()` → `None` (`rf55_preparacion.py`) |
| ¿Simulador Edge en `src/` o `tests/` de este repo? | **No** |
| ¿Fuente de mediciones para G43 pytest? | **No** |
| ¿Umbrales? | Persistencia RF-17 en M09 / sync MQTT; el backend **no** clasifica lecturas |
| ¿`POST /iot/eventos-edge`? | Recibe `clasificacion_rf55` **ya calculada**. No es el clasificador RF-55.1 |
| ¿RF-56? | Ingesta de evento. **No** sustituye RF-55.1 |
| Unitarios relacionados | `tests/telemetry/test_inc_m03_111_g43_umbrales_evento_edge.py`: parametriza 076/077/078 **solo** para persistir `valor_evaluado` / umbrales en el DTO. **No** prueba el nodo |

`SemaforoCalculator` (monitoreo histórico) no es RF-55.1.

### Fuera de este repo (contexto, no ejecutado ahora)

- Anotación `anotaciones/modulo_3/inc_m03_111_g43_evidencia_umbrales_rf55.md` (2026-10-27): firmware `develop` `66a22a2` **sin** clasificador RF-55.1; sí `FakeLoraSource` y `UmbralStore`.
- Laboratorio G41 (2026-10-30, Raspberry `edge-agent` `v0.4.0-rc.2`): el nodo **sí** evaluó `Humedad Relativa` contra umbral **65** (bandas RF-17 `normal`/`precaucion`/`critico`) y publicó `DESVIACION_SIMPLE`. Eso **no** es ejecución de TC-M03-076/077/078 y **no** desbloquea el pytest de G43, que solo mira `src/`/`tests/` del backend.
- Firmware aislado `.worktrees/sgpmp-rf55-validation` (`evaluar_simple`): `NORMAL` = banda `normal` (sin evento MQTT); fuera de esa banda → `DESVIACION_SIMPLE`. Los umbrales son **tres bandas**, no un par `umbral_min`/`umbral_max` como enuncia G43.

---

## 4. Los tres casos (sin inventar datos de ejecución)

No hay umbrales ni mediciones **aplicados** en G43. La propuesta 18–30 / 25 / 35 / 10 de INC-M03-111 **no está** en el pytest ni en evidencias 2026-10-25.

### TC-M03-076

| Campo | Contenido en archivos |
|---|---|
| Objetivo | Valor entre `umbral_min` y `umbral_max` en el **nodo** → `NORMAL` |
| Precondiciones | Motor/simulador Edge, umbral local, medición válida |
| Datos / umbrales | Ninguno aplicado |
| Esperado | Clasificación `NORMAL` calculada en Edge |
| Evidencia 2026-10-25 | `pytest.txt/html/xml`: **SKIPPED** `rf55_preparacion.py:62` |
| Estado documental | **BLOQUEADO** / runner **SKIPPED**. No es PASS |

### TC-M03-077

| Campo | Contenido |
|---|---|
| Objetivo | Valor > `umbral_max` → `DESVIACION_SIMPLE` |
| Precondiciones | Igual; umbral máximo en nodo |
| Datos | Ninguno |
| Esperado | `DESVIACION_SIMPLE` en Edge |
| Evidencia | SKIPPED 2026-10-25 |
| Estado | **BLOQUEADO** / **SKIPPED** |

### TC-M03-078

| Campo | Contenido |
|---|---|
| Objetivo | Valor < `umbral_min` → `DESVIACION_SIMPLE` |
| Precondiciones | Umbral mínimo en nodo |
| Datos | Ninguno |
| Esperado | `DESVIACION_SIMPLE` por infracción de mínimo |
| Evidencia | SKIPPED 2026-10-25 |
| Estado | **BLOQUEADO** / **SKIPPED** |

Dependencia común: clasificador en el proceso Edge, no `POST /iot/eventos-edge` ni unitarios INC-M03-111.

---

## 5. Reglas de documentación (cumplimiento)

Carpetas por caso **existen**. Informes individuales **existen**. Distinción SKIPPED ≠ PASS **está escrita**. No se fabricó PASS. No se reescribieron esos informes en esta auditoría.

Brecha de diseño: G43 habla de `umbral_min`/`umbral_max`; el firmware RF-17 vigente usa tres bandas. `NORMAL` en firmware G41 **no** se publica como evento MQTT (solo historial local). El CA “evento NORMAL” puede no coincidir con el producto actual. Eso debe ratificarse **antes** de implementar pytest.

---

## 6. Qué se puede automatizar vs qué impide lo funcional

**Hoy, en este repo, de forma honesta:**

- Automatizable: el skip parametrizable (hoy son tres tests iguales) y los unitarios INC-M03-111 (persistencia, no clasificación).
- **No** automatizable como PASS G43: pytest que invoque un motor inexistente en `src/`.

**Impedimentos:**

1. `localizar_motor_edge()` no encuentra interfaz en el backend.
2. No hay fixtures de umbral/medición G43.
3. No hay `parametrize` en `test_tc_m03_g43.py`.
4. POST de evento clasificado a mano **no** cubre el CA (el propio script lo dice).
5. Usar G41 (fake HR / umbral 65) como 076/077/078 **reduciría** el CA: es otro grupo, otra variable, bandas de precaución/crítico, y 076 (`NORMAL`) no quedó demostrado como evento MQTT.

---

## 7. Próximo paso técnico recomendado (no ejecutado)

1. **No** marcar PASS ni rellenar umbrales inventados.
2. Decidir con autorización: (A) mantener SKIPPED hasta un gancho oficial al firmware; (B) prueba de laboratorio en Raspberry **distinta de G41**, con umbrales y valores **declarados** y evidencia MQTT/historial, sin fingir que el pytest backend ya clasifica.
3. Aclarar con análisis: min/max de dos números vs tres bandas RF-17; si `NORMAL` debe publicarse.
4. Si se implementa pytest: `parametrize` de los tres IDs, **sin** usar RF-56 ni POST de clasificación fabricada.

Esperar instrucciones. Casos: **SKIPPED / BLOQUEADO**.

---

## 8. Addendum de trazabilidad (consolidación documental, 2026-10-30)

Esta sección **no reescribe** el diagnóstico anterior ni los informes del 25 de octubre. Tras la ejecución **offline** autorizada en firmware `e618a75`:

| Superficie | Estado vigente |
|---|---|
| Pytest `sgpmp-backend` `test_tc_m03_g43.py` | Sigue **SKIPPED** (sin motor en `src/`) |
| Informes `TC-M03-07x_resultado.md` (2026-10-25) | **Intactos** — SKIPPED/BLOQUEADO del runner backend |
| Firmware `raspberry/tests/test_tc_m03_g43.py` | **6 passed** offline |
| TC-M03-076 / 077 / 078 (firmware) | **PASS offline** — ver `RESULTADO_OFFLINE_2026-10-30.md` e `INFORME_EJECUCION_OFFLINE_G43.md` |

Pendiente de validación integral: MQTT real, Raspberry, recepción en backend, y el CA “evento NORMAL” frente a `evaluar_simple` → `None`.
