# Procedimiento de restauración — sgpmp_g43_test

**No ejecutar en la fase de preparación.**

## Backup verificado (solo lectura, 2026-11-01)

| Campo | Valor |
|---|---|
| Ruta | `DBIntegrador/backups/backup_sgpmp_dev_2026-10-30.dump` |
| Tamaño | 48202518 bytes (no vacío) |
| Vacíos en la misma carpeta | `2026-09-08`, `2026-09-15`, `2026-09-22`, `2026-10-27` (0 bytes) — **no usar** |

Formato: dump custom de DEV. El clúster origen de PR1.4 quedó en Alembic `6bd01d026ac4`. Este dump **no** incluye `b2e8c4a91f03` (`eventos_edge_alerta`).

## Cómo se restauraría (futuro)

Destino: contenedor `g43-postgres`, base `sgpmp_g43_test`, host `127.0.0.1:5439`.

1. `docker compose -p g43-lab -f docker-compose.g43.yml --env-file .env.g43 up -d g43-postgres`  
   Esperar healthcheck. **No** apuntar a `infra-db-1`.
2. Comprobar `SELECT current_database();` = `sgpmp_g43_test`.
3. `pg_restore --no-owner --role=g43_admin -d sgpmp_g43_test` del dump 10-30 (el dump trae roles `sgpmp_owner` / `sgpmp_app` / etc.; revisar conflictos de roles en un clúster vacío).
4. Migraciones PR1 **después** de restore, como `sgpmp_owner` **solo** sobre `sgpmp_g43_test`, hasta `b2e8c4a91f03`. No correr Alembic contra `sgpmp` ni `sgpmp_pr14_test`.
5. Crear/ajustar `g43_app` + GRANT (ver `sembrar-dispositivo-g43.sql`).
6. Semilla `G43-LAB-001`.

## Roles y permisos previstos

| Rol | Uso |
|---|---|
| Superusuario del contenedor (`g43_admin`) | Restore y DDL |
| `sgpmp_owner` (si viene del dump) | Alembic |
| `sgpmp_app` o `g43_app` | Backend y gateway (SELECT modulo9; DML modulo3) |
| `member_qa` / `rol_qa` | Opcional, kit QA del dump |

El puente necesita SELECT en `modulo9.dispositivos_iot` y `sensores`.

## Qué no hacer

- Restaurar sobre el volumen `infra_pgdata` (:5433).
- `pg_restore` a `sgpmp` o `sgpmp_pr14_test`.
- Usar dumps de 0 bytes.
