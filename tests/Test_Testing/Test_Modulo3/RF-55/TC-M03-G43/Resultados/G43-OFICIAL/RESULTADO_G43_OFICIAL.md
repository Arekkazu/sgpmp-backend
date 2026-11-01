# RESULTADO G43 oficial — TC-M03-076 / 077 / 078

Fecha: 2026-11-01.  
Worktree firmware: `.worktrees/sgpmp-rf55-validation`, rama `qa/rf55-validation-e618a75`, commit `e618a75f39d7b64bdabae4b3112490aca7ff628b`.  
G43-PR1 **no** se reabre. Evidencias `offline-2026-10-30` y del 25-10-2026 **intactas**.  
Base original `sgpmp`: no modificada. Sin Git. Sin MQTT/HTTP a producción. Sin Raspberry.

Criterio de trabajo: `DECISION_CA6_TRABAJO.md`.

---

## 1. Archivos modificados (firmware / pruebas firmware)

| Archivo | Cambio |
|---|---|
| `raspberry/edge_agent/reglas/evaluador.py` | Banda `normal` arma `EventoEdge` NORMAL (`nivel_umbral=normal`, sin `severidad`) |
| `raspberry/tests/test_evaluador_simple.py` | `test_dentro_de_rango_emite_normal` |
| `raspberry/tests/test_historial.py` | NORMAL se publica una vez (FakeLink) y queda en historial |
| `raspberry/tests/test_tc_m03_g43.py` | 076 exige EventoEdge + un MQTT mock; 077/078 sin cambio de clasificación |

No se modificó `CONTRATO_EVENTO_EDGE.md`. No se tocó `sgpmp-backend` de producción ni G43-PR1.

---

## 2. Defecto encontrado

`evaluar_simple` devolvía `None` en banda `normal`. El agente solo llamaba `registrar_normal` (historial LOCAL, sin `id_evento`, sin topic `evento`). Motivo documentado: no saturar el rate limit (CONTRATO §2). Eso **contradice** CA-6 de trabajo (evento estructurado también si NORMAL).

077/078 ya emitían `DESVIACION_SIMPLE` / `CRITICO` / `fuera_de_rango`.

---

## 3. Corrección

Una lectura en banda `normal` produce un `EventoEdge` con `id_evento` (`edge-evt-` + UUID) y entra a `_encolar_evento` (mismo canal que 077/078). El historial se escribe vía `registrar_evento` (ruta DIRECTA si hay “conexión”). `normales()` queda como residuo; no duplica si el evento ya existe. CONTRATO sin editar.

---

## 4. Pruebas ejecutadas

**Nivel 1–2: unitarias + offline firmware (FakeLink, sin Mosquitto).**

```
pytest tests/test_tc_m03_g43.py tests/test_evaluador_simple.py tests/test_historial.py
```

**41 passed** en 1.77 s.

**Nivel 3 (simulador + Mosquitto + backend + PG):** no ejecutado.  
**Nivel 4 (E2E físico):** no ejecutado.

### Por qué no hay integración (fase D)

No se pudo demostrar, a la vez:

1. Broker Mosquitto **solo** de laboratorio (existe `docker-compose.prod.yml` en el clone del broker; no se levantó).
2. Backend de pruebas con URL no productiva (no se arrancó la API).
3. Que el laboratorio no pudiera publicar comandos a un Gateway real.
4. Aislamiento operativo de `sgpmp_pr14_test` **para este flujo MQTT** (la copia existe y no es `sgpmp`, pero el puente MQTT→POST no está acreditado como lab G43).

Sin esas pruebas, **no** se publicó MQTT ni se hizo POST.

---

## 5. Resultados individuales

| Caso | Unitario firmware | Offline (FakeLink) | Integración broker | E2E físico | Dictamen |
|---|---|---|---|---|---|
| TC-M03-076 | PASS: `NORMAL`, `id_evento`, valor 21.0, umbral 90043, sensor `dht22_ambiente` en `evaluar_simple` | PASS: 1 mensaje mock `sgpmp/IOT-TEST-001/evento`; historial DIRECTA; sin duplicado | No ejecutado | No ejecutado | **APROBADO PARCIALMENTE** |
| TC-M03-077 | PASS: `DESVIACION_SIMPLE` / `CRITICO`, 35.0 °C | PASS: 1 evento mock | No ejecutado | No ejecutado | **APROBADO PARCIALMENTE** |
| TC-M03-078 | PASS: `DESVIACION_SIMPLE` / `CRITICO`, 10.0 °C | PASS: 1 evento mock | No ejecutado | No ejecutado | **APROBADO PARCIALMENTE** |

Pytest backend `test_tc_m03_g43.py` (SKIPPED, `skip_sin_motor_edge`): **sin cambio**. Un DTO POST no cubre este grupo.

Fixture: `temperatura_ambiente` 18–32 °C, bandas 18–24 / 24–28 / 28–32. **No** se usó umbral 65 de G38/G41.

`FakeLoraSource` no rellena `sensor`; el sensor se afirma en `evaluar_simple` con `Reading` explícito.

---

## 6. Nivel de integración alcanzado

**Offline de firmware** (clasificador real + historial SQLite temporal + FakeLink).  
No hay Mosquitto real, HTTP real ni PostgreSQL en esta corrida.

---

## 7. Evidencias (carpeta nueva)

`tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G43/Resultados/G43-OFICIAL/`

- `DECISION_CA6_TRABAJO.md`
- `RESULTADO_G43_OFICIAL.md`
- `evidencias/run-2026-11-01-firmware-offline/pytest-junit.xml`
- `evidencias/run-2026-11-01-firmware-offline/pytest.html`
- `evidencias/run-2026-11-01-firmware-offline/pytest.txt`

Sin captura MQTT de broker, sin HTTP, sin SQL.

---

## 8. Pendiente

1. Acta formal Análisis: CONTRATO §2 vs CA-6 (SRS v2.0 aún no versionado en el repo).
2. Actualizar CONTRATO / broker / OpenAPI si se acepta `NORMAL` en `sgpmp/<serial>/evento`.
3. Laboratorio aislado: Mosquitto local, puente, backend y PG de pruebas (no `sgpmp`).
4. Evidencia HTTP 201 + una fila `clasificacion_rf55` coherente.
5. Riesgo E6 (60 eventos/min) si cada muestra NORMAL se publica.
6. Autorización expresa para Raspberry/dispositivo.
7. Desbloqueo del pytest backend (motor no está en `src/`; no se cubre con POST fabricado).

Siguiente paso seguro: laboratorio **solo** con Mosquitto de pruebas, backend contra copia `*_test`, sin `command` MQTT a seriales de lab reales, evidencias en subcarpeta nueva bajo `G43-OFICIAL/`.

---

## 9. Dictamen de esta corrida offline (histórico)

Este archivo documenta la corrida firmware/FakeLink. La integración MQTT+HTTP+PG está en `RESULTADO_INTEGRACION_G43.md` (**APROBADO**).

Dictamen **offline**: **APROBADO PARCIALMENTE.** Clasificador y publicación mock según CA-6 de trabajo. Sin MQTT/HTTP/PG en esta corrida. G43-PR1 no es evidencia de 076/077/078.
