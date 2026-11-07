# RESULTADO — Integración oficial G43 (TC-M03-076 / 077 / 078)

Fecha: 2026-11-01.  
Evidencias: `Resultados/G43-OFICIAL/evidencias/run-2026-11-01-integracion/`  
G43-PR1 **no** se usa como evidencia de estos casos.

Cadena ejecutada:

`FakeLoraSource` + `evaluar_simple` → Mosquitto `g43-mosquitto` (`127.0.0.1:1884`) → Gateway real `_consultas/BROKER-MQTT-SGPMP` (`reenvio_nodo.evento_edge`) → `POST /iot/eventos-edge` backend SGPMP (`127.0.0.1:18043`) → PostgreSQL `sgpmp_g43_test` (`127.0.0.1:5439`).

---

## Veredicto global

**APROBADO.**

Los tres casos demostraron la cadena real MQTT + HTTP 201 + una fila PostgreSQL por `id_evento_edge`, con clasificación, valor, unidad y umbral 90043 coherentes. Cero publicaciones en `command`. Cero duplicados. Base confirmada: `current_database() = sgpmp_g43_test`. No se escribió en `sgpmp` ni en `sgpmp_pr14_test`.

El CONTRATO §2 (NORMAL no se emite) **no se reescribe**. El DTO y el CA-6 de trabajo aceptan NORMAL; 076 persistió `metadatos.clasificacion_rf55 = NORMAL`.

---

## Tabla por caso

| Caso | Lectura | MQTT | HTTP | PostgreSQL | Clasificación / severidad | Valor / unidad / umbral | Duplicados | command | Dictamen |
|---|---|---|---|---|---|---|---|---|---|
| TC-M03-076 | 21.0 °C | 1 `sgpmp/G43-LAB-001/evento` | 201 | 1 fila `edge-evt-813be948-1919-4175-b0b3-2ab0bfc03e3a` | NORMAL / severidad NULL; columna `tipo_evento=DATOS_PROCESADOS` | 21.0 C / 90043 | 1 | 0 | **APROBADO** |
| TC-M03-077 | 35.0 °C | 1 evento | 201 | 1 fila `edge-evt-6063f185-ecb2-443a-ad4c-418f190749b2` | DESVIACION_SIMPLE / CRITICO; `tipo_evento=ALERTA_GENERADA` | 35.0 C / 90043 | 1 | 0 | **APROBADO** |
| TC-M03-078 | 10.0 °C | 1 evento | 201 | 1 fila `edge-evt-0fe71210-6dcd-428e-a6be-ab40130f55e7` | DESVIACION_SIMPLE / CRITICO; `tipo_evento=ALERTA_GENERADA` | 10.0 C / 90043 | 1 | 0 | **APROBADO** |

Correlación: `metadata_edge.id_evento` = historial firmware = MQTT = columna `id_evento_edge`.

---

## Aislamiento demostrado

| Control | Resultado |
|---|---|
| Clúster | contenedor `g43-postgres`, no `infra-db-1` |
| Puerto host PG | `127.0.0.1:5439` (5433 sigue en `infra-db-1`) |
| Base | solo `sgpmp_g43_test` en este clúster (además de `postgres`/`template*`) |
| Volumen | `g43_pgdata` creado vacío; no se usó `infra_pgdata` |
| Red | `g43_lab` (no `external`) |
| MQTT | `g43-mosquitto` `127.0.0.1:1884` |
| Backend | `DATABASE_URL` …`127.0.0.1:5439/sgpmp_g43_test`; health `{"status":"ok"}` |
| Guardia lab | `scripts/assert-url-g43.py` y `run-backend-g43.py` rechazan `sgpmp` / `sgpmp_pr14_test` |

Dump restaurado: `backup_sgpmp_dev_2026-10-30.dump` (48202518 bytes) sobre destino vacío. Alembic `6bd01d026ac4` → `b2e8c4a91f03`.

Semilla modulo9 (solo G43): serial `G43-LAB-001`, `id_dispositivo_iot=52`, `id_sensores=43`. Umbral 90043 en firmware (`UmbralStore`), no se insertó fila M09 de umbral (el CA usa el id en `metadata_edge`).

---

## Correcciones durante la ejecución (laboratorio, no producción)

1. Mosquitto no arrancaba por CRLF en `docker-entrypoint-g43.sh` (`set: illegal option -`). Convertido a LF. Volumen PG **no** se recreó.
2. ACL de lab: escritura `status` y lectura `command` para el serial de lab (el `MqttLink` real se suscribe a command y publica LWT en status). **Deny write** `command` se mantiene.
3. Nombre de finca: el trigger rechaza dígitos; se usó `Finca Laboratorio`.
4. Backend exigía `SECRET_KEY` de lab (JWT). Añadida solo en `.env.g43` gitignorado.
5. Gateway `aiomqtt` en Windows Proactor: `NotImplementedError` en `add_reader`. Arranque lab con `WindowsSelectorEventLoopPolicy` + `uvicorn.Server` (`run-gateway-g43.py`). Código del broker **no** se modificó.
6. Dependencias Python locales (`defusedxml`, `asyncpg`, `aiomqtt`) para poder ejecutar backend y gateway reales.

No se publicó `command`. No se usó `docker-compose.prod.yml`. No hubo Git.

---

## Evidencias

| Archivo | Contenido |
|---|---|
| `evidencias/run-2026-11-01-integracion/mqtt.jsonl` | 3 eventos; 0 command |
| `TC-M03-076/firmware.json`, `mqtt.jsonl` | clasificador + MQTT 076 |
| `TC-M03-077/firmware.json`, `mqtt.jsonl` | 077 |
| `TC-M03-078/firmware.json`, `mqtt.jsonl` | 078 |
| `sql-verificacion-tres-casos.txt` | `current_database`, counts=1, campos |
| `http-201.txt` | tres POST 201 |
| `config-sin-secretos.txt` | puertos, nombres, serial; sin claves |

HTTP gateway (resumen): tres líneas `POST http://127.0.0.1:18043/iot/eventos-edge "HTTP/1.1 201 Created"`.  
Access log backend: tres `POST /iot/eventos-edge HTTP/1.1 201 Created`.

---

## Notas de contrato / esquema

- `clasificacion_rf55` en PostgreSQL vive en `metadatos` JSONB, no como columna homónima.
- `tipo_evento` persistido: `DATOS_PROCESADOS` (NORMAL) y `ALERTA_GENERADA` (desviación).
- Firmware emite `temperatura_ambiente` (no código catálogo `TEMPERATURA_AMBIENTAL`); el DTO lo aceptó y el evento persistió.

---

## Procesos al cierre de esta corrida

Quedaron en ejecución (lab): `g43-postgres`, `g43-mosquitto`, uvicorn backend `:18043`, gateway `:18044`, suscriptor MQTT de evidencia. No son producción. Deben detenerse cuando ya no se inspeccione el lab (`docker compose -p g43-lab -f docker-compose.g43.yml down` **sin** `-v`).
