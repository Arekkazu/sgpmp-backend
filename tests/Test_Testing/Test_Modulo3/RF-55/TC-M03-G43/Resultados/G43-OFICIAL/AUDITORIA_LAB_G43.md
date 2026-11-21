# Auditoría de preparación del laboratorio G43

Fecha: 2026-11-01.  
Alcance: solo lectura. No se ejecutó `docker compose up/down/build`. No se publicaron MQTT. No se ejecutaron migraciones ni SQL de escritura. No se leyeron ni imprimieron secretos. No se conectó a `sgpmp` ni a `sgpmp_pr14_test`. No se usó `docker-compose.prod.yml`. No hubo Git.

Dictamen G43 oficial vigente: **APROBADO PARCIALMENTE**.  
Esta auditoría **no** cambia ese dictamen. **No** se declara el laboratorio operativo. **No** se declara integración 076/077/078 ejecutada.

---

## 0. Aclaración de ubicación

No existe el directorio raíz `g43-lab/` ni los archivos `Dockerfile.g43`, `requirements.g43.txt` o `src/g43_api/main.py`.

Lo que sí existe:

| Recurso | Valor |
|---|---|
| Carpeta de laboratorio | `sgpmp-backend/tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G43/lab/` |
| Nombre de proyecto Compose | `g43-lab` (campo `name:` en `docker-compose.g43.yml`) |
| `.env.g43` | **Ausente** (solo plantilla `.env.g43.example`) |
| Contenedores G43 | **No existen** (no arrancados) |

Cualquier descripción de una API de demostración FastAPI, Redis o MinIO **no corresponde** a este laboratorio.

---

## 1. Archivos inspeccionados

### Laboratorio G43

- `lab/docker-compose.g43.yml`
- `lab/.env.g43.example`
- `lab/.gitignore`
- `lab/README_LAB_G43.md`
- `lab/CHECKLIST_SEGURIDAD.md`
- `lab/PROCEDIMIENTO_RESTAURACION.md`
- `lab/PROCEDIMIENTO_EJECUCION.md`
- `lab/matriz_payload.md`
- `lab/mosquitto/mosquitto.conf`
- `lab/mosquitto/acl`
- `lab/mosquitto/docker-entrypoint-g43.sh`
- `lab/scripts/validar-aislamiento.ps1`
- `lab/scripts/sembrar-dispositivo-g43.sql` (comentado; no ejecutado)

### Backend SGPMP real (referencia de contrato)

- `sgpmp-backend/src/telemetry/infrastructure/dto/recibir_evento_edge_dto.py`
- `sgpmp-backend/src/telemetry/infrastructure/routers/evento_edge_router.py`

### Gateway real (referencia; no incluido en el compose G43)

- `_consultas/BROKER-MQTT-SGPMP/app/mqtt/handlers.py`
- `_consultas/BROKER-MQTT-SGPMP/app/services/reenvio_nodo.py` (`evento_edge`)
- `_consultas/BROKER-MQTT-SGPMP/docker-compose.yml` (dev, no arrancado)
- `_consultas/BROKER-MQTT-SGPMP/docker-compose.prod.yml` (**no utilizado**)

### Evidencia previa / casos

- `Resultados/G43-OFICIAL/RESULTADO_G43_OFICIAL.md`
- Fixture firmware `id_umbral_ambiental=90043` en `.worktrees/sgpmp-rf55-validation/raspberry/tests/test_tc_m03_g43.py`

### Infraestructura viva (inspección Docker, sin detener)

- Contenedor `infra-db-1` (`postgres:18.0`, healthy)
- Volumen `infra_pgdata`
- Red `infra_default`
- Dump `DBIntegrador/backups/backup_sgpmp_dev_2026-10-30.dump` (48202518 bytes, no vacío)

---

## 2. Arquitectura real del laboratorio

Estado: **papel / archivos**. Servicios G43 **apagados**.

```
[previsto, no arrancado]

Firmware Edge (worktree rf55-validation)
  EDGE_SOURCE=fake + evaluar_simple
  serial G43-LAB-001
        |
        | MQTT sgpmp/G43-LAB-001/evento
        v
Mosquitto G43  (compose: g43-mosquitto)
  host 127.0.0.1:1884 → contenedor 1883
        |
        | (proceso host, no está en el compose)
        v
Gateway BROKER-MQTT-SGPMP
  reenvio_nodo.evento_edge → POST /iot/eventos-edge
        |
        | (proceso host, no está en el compose)
        v
Backend SGPMP real (uvicorn local)
  RecibirEventoEdgeDTO + evento_edge_router
  bind 127.0.0.1:18043
        |
        v
PostgreSQL G43 (compose: g43-postgres)
  host 127.0.0.1:5439 → contenedor 5432
  base sgpmp_g43_test
```

El compose **solo** declara Postgres y Mosquitto. No hay servicio `api`, `gateway`, Redis ni MinIO.

---

## 3. Componentes que están preparados

| Componente | Preparación | Operativo |
|---|---|---|
| Compose aislado `g43-lab` | Sí: red `g43_lab` no external, bind loopback, `restart: "no"` | No |
| PostgreSQL dedicado | Sí: servicio `g43-postgres`, contenedor `g43-postgres`, volumen `g43_pgdata`, DB `sgpmp_g43_test`, usuario vía env, healthcheck, puerto host **5439** | No |
| Mosquitto dedicado | Sí: `g43-mosquitto`, puerto host **1884**, ACL deny `command`, persistencia en volumen `g43_mosquitto_config` | No |
| Plantilla env | Sí: `.env.g43.example` (MQTT_HOST, BACKEND_URL, DATABASE_URL, token placeholder) | `.env.g43` no creado |
| Script de aislamiento estático | Sí: rechaza nombres `sgpmp` y `sgpmp_pr14_test` y exige `:5439` | No corrido contra `.env.g43` (no existe) |
| Procedimiento restore dump 10-30 | Documentado; dump verificado no vacío | No restaurado |
| Semilla finca/dispositivo/sensor | SQL comentado, serial `G43-LAB-001` | No insertado |
| Matriz firmware ↔ DTO ↔ catálogo | Documentada | — |
| Procedimiento 076/077/078 one-shot | Documentado | No ejecutado |
| Firmware clasificador (fase previa) | Offline 41 PASS, CA-6 de trabajo | Sin Mosquitto real |

---

## 4. Componentes faltantes para la integración oficial

1. **Arranque autorizado** de `g43-postgres` y `g43-mosquitto`.
2. **`.env.g43`** real (gitignorado), distinto de TEST/prod, validado con `validar-aislamiento.ps1`.
3. **Restauración** del dump 10-30 **solo** en `sgpmp_g43_test` (:5439).
4. **Migraciones Alembic** hasta `b2e8c4a91f03` (el dump queda en origen `6bd01d026ac4`; **no** trae `eventos_edge_alerta`).
5. **Rol de aplicación** y GRANT modulo3/modulo9.
6. **Semilla modulo9**: finca, infraestructura, dispositivo `G43-LAB-001`, al menos un sensor activo (el puente descarta el evento si no hay `device_id`/`sensor_id`).
7. **Backend SGPMP real** en proceso independiente (`127.0.0.1:18043`) con `DATABASE_URL` de G43 y `BROKER_SERVICE_TOKEN` de laboratorio.
8. **Gateway real** en proceso independiente (`MQTT_HOST=127.0.0.1`, `MQTT_PORT=1884`, `BACKEND_URL=http://127.0.0.1:18043`), **sin** `docker-compose.prod.yml` y **sin** publicar `command`.
9. **Firmware** one-shot FakeLora + `evaluar_simple` contra serial de lab (no Raspberry, no G38/G41).
10. **Evidencias** MQTT + HTTP 201 + SELECT PostgreSQL por `id_evento_edge`.

Sin esos diez puntos, **no** se puede ejecutar la integración oficial 076/077/078.

---

## 5. PostgreSQL, puertos y riesgos de aislamiento

### Compose G43 (previsto)

| Campo | Valor |
|---|---|
| Proyecto | `g43-lab` |
| Servicio | `g43-postgres` |
| Contenedor | `g43-postgres` |
| Imagen | `postgres:18.0` |
| Volumen | `g43_pgdata` → `/var/lib/postgresql` |
| Red | `g43_lab` (bridge, no `external`) |
| Puerto publicado | `127.0.0.1:5439` → `5432` |
| Base | `POSTGRES_DB` default `sgpmp_g43_test` |
| Usuario | `${POSTGRES_USER}` (plantilla: `g43_admin`) |
| Healthcheck | `pg_isready` local al contenedor |

Montajes: solo volumen nombrado `g43_pgdata`. **No** monta `infra_pgdata`, backups de `DBIntegrador` ni rutas de otros proyectos.

### Puerto 5433 (inspección en vivo)

**Ocupado.** `infra-db-1` (`postgres:18.0`, Up ~2 h, healthy) publica `0.0.0.0:5433→5432` (también `[::]:5433`).  
Volumen: `infra_pgdata`. Red: `infra_default`. Bind adicional de backups en `/backups` (ro).

Ese clúster es el de DBIntegrador (`sgpmp` / `sgpmp_pr14_test`). **No se detuvo.** El laboratorio G43 **no** usa 5433.

### Otros puertos

| Puerto | Estado observado |
|---|---|
| 5433 | En uso (`infra-db-1`) |
| 5439 | Libre (previsto G43 PG) |
| 1884 | Libre (previsto G43 MQTT) |
| 1883 | No aparece en `netstat` del host |
| 18043 | Libre (previsto backend lab) |
| 5447 / 5448 | No aparecen en la muestra de `netstat` |

Volúmenes Docker actuales: `infra_pgdata`, volúmenes Agriscan. **No** existe aún `g43_pgdata` (solo se crea al `up`).

Redes actuales: `infra_default`, `deploy_default`. **No** existe `g43_lab`.

### ¿La API se conecta al servicio `postgres` en Docker?

**No hay API en el compose G43.** No existe servicio llamado `postgres`.

La plantilla apunta el backend **en el host** a `127.0.0.1:5439/sgpmp_g43_test`. Eso es correcto para procesos locales. Si más adelante se metiera la API en Docker, el hostname interno sería `g43-postgres`, no `postgres`.

### Riesgo de escribir en `sgpmp` o `sgpmp_pr14_test`

| Control | Efecto |
|---|---|
| Puerto distinto (5439 vs 5433) | Impide chocar con `infra-db-1` si se respeta el compose |
| Nombre de base `sgpmp_g43_test` | Pytest `_validar_url_pruebas` exige `test` en el nombre |
| `validar-aislamiento.ps1` | Falla si `DATABASE_URL` termina en `sgpmp` o `sgpmp_pr14_test` o no usa `:5439` |
| Red propia | El contenedor G43 no se une a `infra_default` |

**Riesgo residual (configuración humana, no del YAML):**

- Arrancar uvicorn/gateway/Alembic con un `.env` de PR1.4 o TEST que apunte a `:5433`.
- `pg_restore` contra `infra-db-1` en lugar de `g43-postgres`.
- Copiar `DATABASE_URL` de `sgpmp_pr14_test` “porque también tiene `test` en el nombre”. El script G43 lo rechaza; hay que ejecutarlo **antes** de cada arranque.

Mientras no exista `.env.g43` y no se arranquen procesos, el aislamiento es **diseño**, no **hecho operativo**.

---

## 6. API: demostración vs backend real

No hay `Dockerfile.g43` ni `g43_api`.

El contrato que G43 necesita está en el **backend SGPMP**:

- Ruta real: `POST /iot/eventos-edge` (`evento_edge_router.py`), status **201**.
- Auth: Bearer `BROKER_SERVICE_TOKEN` (`require_token_servicio_broker`).
- DTO: `RecibirEventoEdgeDTO`.
- Persistencia: `modulo3.eventos_edge_computing` (y efectos PR1 si hay migración).

Un endpoint echo/health de demostración **no** validaría G43. Hoy **no está implementado** ese demo; el hueco es otro: el backend real **no está empaquetado ni arrancado** en este laboratorio.

### Campos del DTO relevantes

Obligatorios (directos o vía unificación):

- `device_id`, `sensor_id`, `serial`
- `clasificacion_rf55` ∈ {NORMAL, DESVIACION_SIMPLE, DESVIACION_COMPUESTA, ERROR_CONFIGURACION}
- `variables_involucradas` (`tipo_variable`, `valor`, `unidad`)
- `timestamp_captura`, `timestamp_procesamiento_edge` (UTC)
- `origen`, `estado_conectividad`
- `id_evento_edge` **o** `metadata_edge.id_evento` (`edge-evt-` + UUID)

Opcional: `severidad` (LEVE/MODERADO/CRITICO). Ausente es válido para NORMAL.

El DTO **no** valida el catálogo M09: acepta `temperatura_ambiente` como string.

---

## 7. MQTT y Gateway

### Mosquitto G43 (compose)

- Listener contenedor 1883; host **solo** `127.0.0.1:1884`.
- Sin websockets, sin anonymous.
- ACL: usuario edge escribe `sgpmp/G43-LAB-001/evento` (y telemetry/heartbeat); **deny** `sgpmp/+/command` y `sgpmp/G43-LAB-001/command`.
- Gateway lab: read de `evento`/`telemetry`/`heartbeat`/`status`; write `resultado`; deny `command`.
- No hay `external` network ni enlace a brokers G38/G41.

El compose G43 **no** incluye el proceso Gateway.

### Gateway real

`handlers.py` despacha `mqtt_topic_evento` → `reenvio_nodo.evento_edge`.

`evento_edge`:

1. Resuelve `device_id` por serial en modulo9.
2. Resuelve `sensor_id` (nombre o primer sensor activo; FakeLora no manda `sensor`).
3. Inyecta `serial` del tópico, `device_id`, `sensor_id`.
4. POST `/iot/eventos-edge`.

Si el serial no está sembrado, **descarta** el mensaje (no hay HTTP).

El mismo árbol del broker contiene `publish_command` y `POST /v1/commands`. **No se ejecutó.** Riesgo: levantar el compose **completo** de `_consultas/BROKER-MQTT-SGPMP` (dev o prod) contra un Mosquitto que no sea G43, o con un usuario MQTT con ACL de escritura en `command`.

Mitigación prevista: Mosquitto G43 propio + ACL deny + no usar `docker-compose.prod.yml` + no llamar `/v1/commands` en la corrida 076/077/078.

El compose de desarrollo del broker publica por defecto host **1884** (mismo número que G43). Hoy 1884 está libre. Si alguien levantara **ambos**, colisionarían. El lab G43 debe usar **solo** `docker-compose.g43.yml`.

---

## 8. Compatibilidad con TC-M03-076 / 077 / 078

La infraestructura **documentada** cubre el flujo, pero **no está levantada**. No hay evidencia MQTT/HTTP/PG.

| Caso | Lectura | Clasificación esperada | Qué faltaría verificar en lab |
|---|---|---|---|
| 076 | 21.0 °C | NORMAL, `severidad` ausente | MQTT 1 msg, POST 201, 1 fila |
| 077 | 35.0 °C | DESVIACION_SIMPLE / CRITICO | igual |
| 078 | 10.0 °C | DESVIACION_SIMPLE / CRITICO | igual |

Cómo se conservarían (cuando exista PG G43 + backend real):

| Campo | Origen | Dónde verificar |
|---|---|---|
| `id_evento_edge` | firmware `metadata_edge.id_evento` | MQTT JSON, body HTTP, columna `modulo3.eventos_edge_computing.id_evento_edge` |
| `clasificacion_rf55` | `evaluar_simple` | mismas tres capas |
| `severidad` | None en 076; CRITICO en 077/078 | JSON + columna |
| `variables_involucradas` | payload | JSON persistido / columnas según schema |
| `valor` / `unidad` | 21/35/10 y `C` | JSON |
| `id_umbral_ambiental = 90043` | **fixture firmware**, no fila M09 obligatoria | `metadata_edge` del evento; no exige INSERT 90043 en catálogo para el CA de clasificación |
| Serial | tópico `G43-LAB-001` (el puente pisa el body) | topic MQTT + columna `serial` |
| HTTP 201 | router RF-56 | access log / cliente |
| Fila PG | use case | `SELECT` por `id_evento_edge`; `count(*) = 1` |
| Sin `command` | ACL + no POST commands | captura MQTT de `sgpmp/+/command` vacía |

Incompatibilidad ya documentada (sin cambiar DTO ni CONTRATO): firmware emite NORMAL (CA-6 de trabajo); CONTRATO §2 dice que NORMAL no se publica. El DTO **sí** acepta NORMAL. No se modifica el contrato en esta auditoría.

`temperatura_ambiente` vs `TEMPERATURA_AMBIENTAL`: no bloquea la ingesta del evento. Puede afectar consolidación M04 en 077/078; queda **fuera** del CA mínimo de G43 (201 + fila de clasificación).

---

## 9. Diferencias API demo vs backend real

| | Demo `g43_api` (no existe) | Backend SGPMP |
|---|---|---|
| `POST /iot/eventos-edge` | No | Sí, 201, token broker, DTO, PG |
| Auth RF-56 / E6 / E7 | No | Sí |
| Persistencia `eventos_edge_computing` | No | Sí |
| Resolución modulo9 | No | Vía gateway + backend |
| Sirve como evidencia G43 | No | Único camino válido |

**No** se debe usar un echo HTTP como evidencia de 076/077/078.

---

## 10. Cambios mínimos necesarios (no implementados)

1. Crear `.env.g43` desde la plantilla (secretos locales; no commitear).
2. Autorizar y arrancar **solo** `docker compose -p g43-lab -f docker-compose.g43.yml --env-file .env.g43 up -d`.
3. Restaurar dump 10-30 en `sgpmp_g43_test` (:5439); luego Alembic PR1 **solo** ahí.
4. Sembrar `G43-LAB-001` + sensor activo + GRANTs.
5. Arrancar uvicorn SGPMP en `127.0.0.1:18043` con `DATABASE_URL` G43.
6. Arrancar el Gateway como proceso local apuntando a Mosquitto G43 y a ese backend; no levantar el compose prod del broker.
7. Suscriptor de evidencia en `sgpmp/G43-LAB-001/evento` y en `sgpmp/+/command`.
8. Un disparo firmware por caso (`EDGE_FAKE_VARIABLES` min=max).
9. SELECT de verificación; guardar evidencias en subcarpeta nueva bajo `G43-OFICIAL/` (no pisar offline ni PR1).

Opcional de endurecimiento (no bloquea el diseño actual):

- Usuario MQTT del gateway **sin** capacidad de publish a `command` (ya en ACL).
- No exponer `POST /v1/commands` en la corrida, o no arrancar esa ruta.
- Confirmar columnas reales de `modulo9.fincas` / `dispositivos_iot` **con SELECT** tras el restore antes de descomentar el SQL de semilla.

---

## 11. Secuencia segura posterior (no ejecutada)

```powershell
cd tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G43/lab
Copy-Item .env.g43.example .env.g43
# editar secretos en local; no pegarlos en informes
.\scripts\validar-aislamiento.ps1
# si OK y hay autorización expresa:
docker compose -p g43-lab -f docker-compose.g43.yml --env-file .env.g43 up -d
# esperar health de g43-postgres y g43-mosquitto
# pg_restore --no-owner hacia 127.0.0.1:5439 / sgpmp_g43_test  (NO :5433)
# alembic upgrade (DATABASE_URL G43 únicamente) hasta b2e8c4a91f03
# SELECT current_database() debe ser sgpmp_g43_test
# semilla G43-LAB-001
# uvicorn backend 127.0.0.1:18043
# gateway local MQTT 127.0.0.1:1884 BACKEND_URL http://127.0.0.1:18043
# firmware fake un caso (076, luego 077, luego 078)
# docker compose -p g43-lab -f docker-compose.g43.yml --env-file .env.g43 down
# no usar down -v salvo borrar el lab a propósito
```

Prohibido en esa secuencia: `docker-compose.prod.yml`, brokers G38/G41, Raspberry, `DATABASE_URL` a `sgpmp` o `sgpmp_pr14_test`, publicar `command`, POST DTO fabricado como clasificador.

---

## 12. Veredicto

| Pregunta | Respuesta |
|---|---|
| ¿El laboratorio está preparado en disco? | **Parcialmente sí** (compose PG+MQTT, ACL, procedimientos). |
| ¿Puede usarse **ahora** para la integración oficial 076/077/078? | **No.** Servicios no arrancados, sin restore, sin semilla, sin backend/gateway en ejecución. |
| ¿Hay una API demo que sustituya a SGPMP? | **No existe.** Tampoco debe usarse si se creara. |
| ¿El puerto 5433 está libre? | **No.** Lo ocupa `infra-db-1`. G43 debe seguir en **5439**. |
| ¿Hay riesgo de tocar `sgpmp` / `sgpmp_pr14_test` si se sigue el compose? | Bajo, por puerto/volumen/nombre distintos. Alto si se reutiliza un `.env` ajeno. |
| Dictamen G43 oficial | **APROBADO PARCIALMENTE** (firmware offline). Sin evidencia MQTT + HTTP + PostgreSQL **no APROBADO**. |

**El laboratorio no está operativo.**  
**La integración oficial no se ejecutó.**
