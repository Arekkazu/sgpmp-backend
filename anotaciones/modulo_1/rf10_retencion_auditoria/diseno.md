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

**Verificación contra la base (2026-08-27).** La decisión de copiar en vez de
trasladar se confirmó consultando el esquema real:

- `modulo1.notificaciones.id_evento` es `NOT NULL` con FK `fk_evento` hacia
  `modulo1.eventos`; borrar un evento rompería notificaciones existentes.
- `trg_proteger_auditoria_delete` bloquea `DELETE` sobre `modulo1.eventos`
  incluso para el rol `postgres`.

El propio RF se contradice en este punto: **Restricciones** prohíbe `DELETE`
"ni siquiera para el rol Administrador", mientras que **Proceso** habla de
"trasladar a almacenamiento histórico". Se resuelve a favor de la restricción
dura, que es la que el esquema ya hace cumplir a nivel de motor.

Consecuencia asumida: `modulo1.eventos` no decrece. El beneficio del archivo es
tener el histórico desacoplado de los catálogos operativos, no reducir la tabla
activa.

## Consulta del archivo histórico

Como el archivo por copia dejaba `modulo1.eventos_archivados` sin ningún lector,
se expone:

```
GET /auditoria/archivado/
```

Reusa por completo `ConsultarAuditoriaUseCase` a través de un parámetro
`archivados: bool`, de modo que el histórico hereda sin duplicar código:

- el mismo permiso RBAC `require_permission(6, 2)` (recurso 6 = auditoría,
  acción 2 = leer) — no se creó recurso ni permiso nuevo;
- el 403 del FA "acceso denegado", que además audita el intento fallido;
- el 400 del FA "filtro de búsqueda inválido" por rango de fechas inconsistente;
- la paginación obligatoria con tope de 50 ítems;
- la verificación del hash SHA-256 en cada fila consultada (`integridad_ok`).

En el repositorio, `_query_con_filtros` quedó parametrizado por modelo. Como
`EventosArchivados` replica los nombres de columna de `Eventos`, `_a_entidad` y
`_verificar_hash` se reusan tal cual: sólo se amplió su anotación de tipo.

La consulta del histórico se audita igual que la del log activo (evento tipo 16,
`CONSULTA_AUDITORIA`), con `archivados: true` en el detalle para distinguirlas.

Se descartó un flag `incluir_archivados` sobre `GET /auditoria/`: paginar sobre
la unión de dos tablas complica `offset` y `total` sin aportar nada al RF.

## Alerta del flujo alterno "Error en el proceso de archivado automático"

El RF pide que un fallo del proceso programado *"dispare una alerta crítica al
administrador"* como **Notificación Interna**. Sólo dejar un log no lo cubre, así
que el `except` del scheduler emite además una notificación real.

`NotificarFalloArchivadoUseCase` registra **un** evento de auditoría de tipo 25
(`FALLO_ARCHIVADO_AUDITORIA`, resultado `fallido`) y **una notificación por
destinatario** en la bandeja interna de RF-14 (canal 2), con el mensaje del RF más
el texto de la excepción real — la causa concreta no se puede afirmar, el RF sólo
la ejemplifica como falta de espacio en disco.

Detalles de diseño:

- **Destinatarios por permiso, no por rol fijo.** Se resuelven con
  `UsuarioRepository.listar_ids_con_permiso(6, 2)`: recibe la alerta quien puede
  leer el historial de auditoría, según `modulo1.permisos`. Evita el
  `ROL_ADMINISTRADOR = 1` quemado que `CLAUDE.md` prohíbe, y sólo considera
  usuarios con cuenta en estado `Activo`.
- **Sesión propia.** La sesión del archivado quedó en `rollback`, así que la
  alerta abre una `SessionLocal()` limpia.
- **La alerta no puede tumbar el bucle.** Va en su propio `try/except`; si
  también falla, queda un segundo log ERROR.
- **Sin destinatarios no se registra nada.** `modulo1.eventos.id_usuario` es
  `NOT NULL` con FK hacia `usuarios` y este proceso no tiene actor humano: el
  evento se atribuye al destinatario de menor `id_usuario`. Si no hay ninguno, no
  hay a quién atribuirlo ni a quién avisar, y sólo queda el log del scheduler.
  Alternativa futura si molesta la atribución: un usuario de sistema dedicado.
- **Categoría `MODIFICACION`.** Sólo existen tres categorías funcionales; el
  proceso de retención actúa sobre el propio almacén de auditoría, así que es la
  que menos desencaja.

## Automatización

El `lifespan` de FastAPI inicia una tarea diaria a las **04:00 UTC**. La tarea
ejecuta `ArchivarAuditoriaUseCase` fuera del event loop y procesa como máximo 20
lotes de 5.000 filas por ejecución.

Se utiliza `pg_try_advisory_xact_lock(10101608)` para que varias réplicas del
backend no procesen el mismo archivo simultáneamente. El `INSERT ... ON
CONFLICT DO NOTHING` agrega una segunda defensa de idempotencia.

Los fallos no detienen la API: se hace `rollback`, se emite un log de nivel ERROR
con el prefijo `ALERTA INTERNA RF-10` y se dispara la notificación interna
descrita más abajo. Si se alcanza el máximo de lotes, se emite WARNING y el
remanente se procesa en la siguiente ejecución.

No se usa `pg_cron`: aunque el paquete está disponible en desarrollo, la
extensión no está instalada y el usuario de aplicación no puede garantizar su
activación en todos los ambientes.

## Migraciones Alembic

```text
8fc28a787fc8_rf10_retencion_auditoria_12_meses.py   (tabla histórica + índices + trigger)
a3b7c1d95e40_rf10_tipo_evento_fallo_archivado.py    (tipo de evento 25 + setval de la secuencia)
```

Aplicación, usando la `DATABASE_URL` del ambiente correspondiente:

```bash
.venv/bin/alembic current
.venv/bin/alembic upgrade head
```

Las migraciones deben ejecutarse antes de desplegar la versión del backend que
activa el scheduler. Ya están aplicadas en `sgpmp` (dev) y en `pruebas`; el
detalle por base está en [`RESUMEN_FINAL.md`](./RESUMEN_FINAL.md).

El `downgrade` de `8fc28a787fc8` elimina la tabla histórica y, por tanto, sus
copias archivadas; en un entorno con datos debe hacerse una exportación antes de
degradar. El de `a3b7c1d95e40` sólo retira el tipo de evento si ningún evento lo
referencia.

## Pruebas

- Unitarias:
  - `tests/identity_access/test_rf10_retencion_auditoria.py` — archivado.
  - `tests/identity_access/test_rf10_alerta_fallo_archivado.py` — alerta del FA.
  - `tests/identity_access/test_rf10_categorias_eventos.py` — catálogo de categorías.
- Integración PostgreSQL/Alembic:
  - `tests/integration/test_rf10_retencion_auditoria_integration.py` — migración y archivado.
  - `tests/integration/test_rf10_consulta_archivado_integration.py` — endpoint del histórico y alerta.

Verifican meses calendario, lotes, bloqueo entre réplicas, rollback, esquema e
índices, corte estricto de 12 meses, idempotencia, conservación de
originales/FK, bloqueo de modificaciones en el histórico, filtros y paginación
del endpoint archivado, su 403/400, y la llegada de la alerta a la bandeja.
