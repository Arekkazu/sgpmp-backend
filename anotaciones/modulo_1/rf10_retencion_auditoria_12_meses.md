# RF-10 — Retención y archivado de auditoría por 12 meses

## Alcance

La política aplica a `modulo1.eventos`, que es el historial auditable definido
por RF-10. No incluye `auditoria.logs_dml` ni `auditoria.logs_ddl`: esas tablas
son trazas técnicas transversales y tienen una política operativa separada.

## Decisión de integridad

Los eventos originales **no se eliminan ni se actualizan**. El RF declara que
son inmutables, `modulo1.notificaciones` mantiene una clave foránea hacia ellos
y la postcondición exige conservar el historial completo.

Al superar 12 meses, cada evento se copia a
`modulo1.eventos_archivados`. Esta tabla:

- conserva el `id_evento` y todos los campos originales, incluido
  `hash_integridad`;
- no tiene claves foráneas, para que el histórico no dependa de cambios futuros
  en usuarios, sesiones o catálogos;
- tiene índices por fecha y por usuario/fecha;
- bloquea `UPDATE` y `DELETE` mediante trigger;
- usa el `id_evento` como clave primaria, haciendo el proceso idempotente.

Este archivado por copia cumple la retención mínima y crea almacenamiento
histórico sin debilitar la inmutabilidad del registro operativo.

## Automatización

El `lifespan` de FastAPI inicia una tarea diaria a las **04:00 UTC**. La tarea
ejecuta `ArchivarAuditoriaUseCase` fuera del event loop y procesa como máximo 20
lotes de 5.000 filas por ejecución.

Se utiliza `pg_try_advisory_xact_lock(10101608)` para que varias réplicas del
backend no procesen el mismo archivo simultáneamente. El `INSERT ... ON
CONFLICT DO NOTHING` agrega una segunda defensa de idempotencia.

Los fallos no detienen la API: se hace `rollback` y se emite un log de nivel
ERROR con el prefijo `ALERTA INTERNA RF-10`. Si se alcanza el máximo de lotes,
se emite WARNING y el remanente se procesa en la siguiente ejecución.

No se usa `pg_cron`: aunque el paquete está disponible en desarrollo, la
extensión no está instalada y el usuario de aplicación no puede garantizar su
activación en todos los ambientes.

## Migración Alembic

Revisión:

```text
8fc28a787fc8_rf10_retencion_auditoria_12_meses.py
```

Aplicación, usando la `DATABASE_URL` del ambiente correspondiente:

```powershell
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe upgrade head
```

La migración debe ejecutarse antes de desplegar la versión del backend que
activa el scheduler. No se aplicó automáticamente sobre la base de desarrollo.

El `downgrade` elimina la tabla histórica y, por tanto, sus copias archivadas;
en un entorno con datos debe hacerse una exportación antes de degradar.

## Pruebas

- Unitarias:
  `tests/identity_access/test_rf10_retencion_auditoria.py`.
- Integración PostgreSQL/Alembic:
  `tests/integration/test_rf10_retencion_auditoria_integration.py`.

Las pruebas verifican meses calendario, lotes, bloqueo entre réplicas,
rollback, esquema e índices, corte estricto de 12 meses, idempotencia,
conservación de originales/FK y bloqueo de modificaciones en el histórico.
