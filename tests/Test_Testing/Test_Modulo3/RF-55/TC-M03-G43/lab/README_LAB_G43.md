# Laboratorio aislado G43 (preparación)

Estado: **archivos listos, servicios no arrancados.**  
Dictamen G43 oficial: **APROBADO PARCIALMENTE** (offline firmware). Esta carpeta no lo cambia.

Flujo previsto:

`FakeLoraSource` + `evaluar_simple` → Mosquitto G43 (`127.0.0.1:1884`) → gateway local → backend `127.0.0.1:18043` → PostgreSQL `sgpmp_g43_test` (`127.0.0.1:5439`).

## Contenido

| Archivo | Función |
|---|---|
| `docker-compose.g43.yml` | Postgres 18 + Mosquitto; red `g43_lab`; bind loopback |
| `mosquitto/mosquitto.conf`, `acl`, `docker-entrypoint-g43.sh` | MQTT lab; deny `command` |
| `.env.g43.example` | Plantilla; copiar a `.env.g43` |
| `scripts/validar-aislamiento.ps1` | Comprueba nombres de BD y loopback (sin imprimir secretos) |
| `scripts/sembrar-dispositivo-g43.sql` | Semilla **no ejecutada** |
| `PROCEDIMIENTO_RESTAURACION.md` | Dump 10-30 + Alembic futuro |
| `PROCEDIMIENTO_EJECUCION.md` | 076/077/078 de un disparo |
| `CHECKLIST_SEGURIDAD.md` | Antes de `up` |
| `matriz_payload.md` | Firmware vs DTO vs catálogo |

## Aislamiento

| Recurso existente | Lab |
|---|---|
| `infra-db-1` :5433 `sgpmp` / `sgpmp_pr14_test` | Otro contenedor, puerto **5439**, base **sgpmp_g43_test**, volumen **g43_pgdata** |
| Broker prod / G38 | Mosquitto propio :1884 loopback |
| Raspberry | `EDGE_SOURCE=fake`, serial `G43-LAB-001` |

Cómo no escribir en `sgpmp` ni `sgpmp_pr14_test`: esas bases viven en **otro** clúster (5433). El lab solo escucha 5439. `validar-aislamiento.ps1` falla si `DATABASE_URL` termina en esos nombres.

Gateway y backend: **procesos locales independientes** (no el compose prod). El compose G43 solo lleva Postgres y Mosquitto.

## Componentes listos vs pendientes

**Listos (papel):** compose, Mosquitto ACL, plantilla env, procedimientos, matriz payload, serial de lab, checklist.

**Pendientes (hace falta autorización y arranque):** `.env.g43` real; `docker compose up`; restore del dump; migraciones `b2e8c4a91f03`; rol `g43_app`; semilla modulo9; uvicorn backend; proceso gateway; agente fake; evidencias MQTT/HTTP/SQL.

## Comandos futuros (no ejecutar ahora)

```powershell
cd tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G43/lab
Copy-Item .env.g43.example .env.g43
# completar secretos localmente
.\scripts\validar-aislamiento.ps1
docker compose -p g43-lab -f docker-compose.g43.yml --env-file .env.g43 up -d
# restore + alembic + seed + backend + gateway + un caso firmware
# docker compose -p g43-lab -f docker-compose.g43.yml --env-file .env.g43 down
# no usar down -v salvo borrar el lab a propósito
```

Puerto backend 18043 evita chocar con 8000/5447.  
No usar `docker-compose.prod.yml` del broker.
