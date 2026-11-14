# Checklist de seguridad — lab G43

Marcar **antes** de cualquier `up`, publish o POST. Hoy: servicios **no** arrancados.

| # | Control | Cómo |
|---|---|---|
| 1 | Compose es `docker-compose.g43.yml` / proyecto `g43-lab` | No `docker-compose.prod.yml` |
| 2 | Red Docker `g43_lab` no `external` | No `sgpmp-network` |
| 3 | Puertos `127.0.0.1:5439` y `127.0.0.1:1884` | No 5433, 5447, 5448; no 0.0.0.0 |
| 4 | `POSTGRES_DB=sgpmp_g43_test` | No `sgpmp`, no `sgpmp_pr14_test` |
| 5 | Volumen `g43_pgdata` | No `infra_pgdata` |
| 6 | Mosquitto ACL niega `command` | `mosquitto/acl` |
| 7 | Serial `G43-LAB-001` | No `RASPBERRY3B-TEST` ni seriales G38/G41 |
| 8 | `BACKEND_URL` loopback:18043 | No Dokploy |
| 9 | Token distinto del de TEST/prod | No imprimir |
| 10 | Firmware `EDGE_SOURCE=fake` | No `lora`, no Raspberry |
| 11 | Dump 10-30 no vacío (48202518 B) | No dumps de 0 bytes |
| 12 | Una lectura por caso | Evitar ráfaga NORMAL → E6 429 |
| 13 | No Git, no migrar `sgpmp` | |
| 14 | `validar-aislamiento.ps1` OK | |

El laboratorio **no** está operativo hasta `up` + checklist + autorización.
