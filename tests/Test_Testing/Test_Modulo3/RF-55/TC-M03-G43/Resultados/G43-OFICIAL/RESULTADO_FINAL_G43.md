# RESULTADO FINAL G43 — TC-M03-076, TC-M03-077, TC-M03-078

Fecha de cierre documental: 2026-11-01.  
Hora de comprobación de servicios y SQL: **2026-11-01 03:17:14 -05:00**.  
Este documento cierra la validación oficial. No reejecuta casos.

---

## 1. Objetivo y alcance

Validar la integración real RF-55.1 → RF-56:

Firmware Edge (`evaluar_simple` + `FakeLoraSource`) → Mosquitto G43 → Gateway real → `POST /iot/eventos-edge` → PostgreSQL aislado `sgpmp_g43_test`.

Casos: 076 (21 °C NORMAL), 077 (35 °C DESVIACION_SIMPLE/CRITICO), 078 (10 °C DESVIACION_SIMPLE/CRITICO).

Fuera de alcance: Raspberry, brokers G38/G41, `sgpmp`, `sgpmp_pr14_test`, G43-PR1, publicación `command`, acta formal de Análisis.

---

## 2. Ambiente utilizado (comprobado en el cierre)

| Componente | Comprobación 03:17 -05:00 | Método (sin reiniciar) |
|---|---|---|
| Backend SGPMP | `127.0.0.1:18043` LISTENING, PID 35064 | `netstat`; `GET /health` → 200 `{"status":"ok",...}` |
| Gateway | `127.0.0.1:18044` LISTENING, PID 28148; MQTT ESTABLISHED a `:1884`; PG ESTABLISHED a `:5439` | `netstat`; `GET /docs` → 200 |
| PostgreSQL lab | contenedor `g43-postgres` Up healthy; host `127.0.0.1:5439` | `docker ps` / `docker inspect` |
| Mosquitto lab | contenedor `g43-mosquitto` Up, host `127.0.0.1:1884`, conexiones establecidas | `docker inspect` (healthcheck Docker = **unhealthy**; el listener sí atiende, ver limitaciones) |
| Clúster ajeno | `infra-db-1` sigue en **5433** | `netstat` — no se usó |

Identidad de base (no basta el `.env`): `docker exec g43-postgres psql … SELECT current_database()` → **`sgpmp_g43_test`**. Catálogo del clúster: solo `postgres` y `sgpmp_g43_test`.

Configuración no sensible: `evidencias/run-2026-11-01-integracion/config-sin-secretos.txt`.

---

## 3. Versiones identificables

| Pieza | Identificación (sin Git en este cierre) |
|---|---|
| Firmware | Worktree `.worktrees/sgpmp-rf55-validation`, commit ya registrado `e618a75f39d7b64bdabae4b3112490aca7ff628b`; payload MQTT `version_firmware=0.3.0` |
| Clasificador | `evaluar_simple` + umbral fixture 90043 (`umbrales.json` de cada caso) |
| Backend | Código local `sgpmp-backend`; Alembic aplicado en lab `b2e8c4a91f03`; bind `127.0.0.1:18043` |
| Gateway | Clone `_consultas/BROKER-MQTT-SGPMP`; `reenvio_nodo.evento_edge`; arranque lab `lab/scripts/run-gateway-g43.py` (SelectorEventLoop) |

No se modificó código de producción ni firmware en este cierre.

---

## 4. Procedimiento ejecutado (histórico de la corrida oficial)

1. Laboratorio `TC-M03-G43/lab/` (compose `g43-lab`, no prod).
2. Restore dump 30-10-2026 en destino vacío `sgpmp_g43_test`; Alembic hasta `b2e8c4a91f03`.
3. Semilla `G43-LAB-001` (dispositivo 52, sensor 43).
4. Backend y Gateway reales contra 5439 / 1884 / 18043.
5. Un disparo FakeLora por caso (`lab/scripts/disparo-caso-g43.py`).
6. Captura MQTT de solo lectura (`mqtt-captura-g43.py`).

Este cierre: **solo lectura** de servicios, archivos y SQL. No se publicaron eventos nuevos.

---

## 5. Resultado individual

Ver `MATRIZ_EVIDENCIAS_G43.md` y `TRAZABILIDAD_076_077_078.md`.

| Caso | Edge | MQTT | Gateway | HTTP | PG (`sgpmp_g43_test`) | Evidencias 1–10 | Dictamen |
|---|---|---|---|---|---|---|---|
| TC-M03-076 | NORMAL, sin severidad, 21.0 C, 90043 | 1 evento | parseo id `813be948…` | 201 | 1 fila, NORMAL, severidad NULL | 10/10 | **APROBADO** |
| TC-M03-077 | DESVIACION_SIMPLE / CRITICO, 35.0 C | 1 evento | parseo id `6063f185…` | 201 | 1 fila, CRITICO | 10/10 | **APROBADO** |
| TC-M03-078 | DESVIACION_SIMPLE / CRITICO, 10.0 C | 1 evento | parseo id `0fe71210…` | 201 | 1 fila, CRITICO | 10/10 | **APROBADO** |

---

## 6. SQL de cierre (solo lectura) y resultado

Consultas y salida: `evidencias/run-2026-11-01-integracion/sql-cierre-solo-lectura-2026-11-01-0317.txt`.

Confirmado en vivo: `current_database()=sgpmp_g43_test`; tres ids con `count=1`; valores 21.0 / 35.0 / 10.0; umbral 90043; 076 sin severidad CRITICO.

---

## 7. Incidentes iniciales (separados del resultado)

No forman parte de la evidencia de los casos:

1. Backend: faltaba `SECRET_KEY` de laboratorio.
2. Backend: `ModuleNotFoundError: defusedxml`.
3. Gateway: `aiomqtt` + Proactor Windows (`add_reader` NotImplementedError).
4. Mosquitto: CRLF en entrypoint (corregido a LF **antes** de la corrida oficial).

Tras corregir el arranque **de laboratorio**, se ejecutó la cadena y se obtuvieron los 201.

---

## 8. Limitaciones residuales

- Healthcheck Docker de `g43-mosquitto` figura **unhealthy**; el puerto 1884 está en LISTENING y hubo MQTT real (3 eventos + conexiones ESTABLISHED). No se reinició el broker.
- El access log del backend no incluye `id_evento_edge`; la correlación HTTP por caso es Gateway (parseo del id + httpx 201) alineado en el tiempo con el access log.
- No se guardó el cuerpo JSON de la respuesta 201; el status 201 sí está en httpx y uvicorn.
- Umbral 90043 es fixture de firmware, no fila M09.
- CONTRATO §2 vs CA-6: abierto para Análisis; **no hay acta**.
- Healthcheck Mosquitto no bloquea el veredicto: la publicación MQTT está evidenciada en `mqtt.jsonl`.

---

## 9. Veredicto global

**APROBADO.**

Los tres casos tienen evidencia verificable de clasificación Edge, MQTT real, recepción Gateway, HTTP 201 del backend real, una fila en `sgpmp_g43_test` y trazabilidad del identificador. No se eleva el estado por el mero hecho de que los servicios sigan activos: se reconsultó PostgreSQL y se releyeron los artefactos de `run-2026-11-01-integracion`.
