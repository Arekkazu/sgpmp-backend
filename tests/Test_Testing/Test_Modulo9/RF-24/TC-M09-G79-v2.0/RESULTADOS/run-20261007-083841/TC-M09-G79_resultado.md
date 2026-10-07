# TC-M09-G79-v2.0 — RESULTADO

## DECISIÓN GENERAL

**Grupo:** TC-M09-G79-v2.0
**Caso:** TC-M09-150-v2.0
**Resultado:** APROBADO

## RESUMEN DEL RESULTADO

Sobre PostgreSQL real y backend HTTP real, con un fault injection verdadero de privilegios, se
demostró la cadena completa que exige el caso:

```text
calibración válida -> alcanza la transacción de persistencia
-> falla el INSERT de auditoría por permisos -> rollback
-> HTTP 500 con el mensaje exacto del FA -> ninguna calibración nueva persistida
```

El control positivo previo creó la calibración `id_calibracion = 1` con **HTTP 201** y su
auditoría correspondiente, lo que acredita que el camino normal funciona y que el laboratorio
era apto para inducir el fallo.

Tras revocar el `INSERT` de las tablas de auditoría al rol de la aplicación, el único POST
objetivo devolvió **HTTP 500** con el mensaje literal del requisito y `error_code`
`AUDITORIA_CALIBRACION_FALLIDA`. El log del backend prueba el punto de fallo:
`permission denied for table auditorias_calibraciones`. En la base, el conteo de calibraciones
del sensor quedó en **1 antes y 1 después**, con los mismos IDs, sin filas alteradas ni
desaparecidas y sin auditoría huérfana. Los privilegios se restauraron exactamente a su estado
previo.

Conviene subrayar lo que esto significa: la transacción revirtió de verdad en PostgreSQL, y al
cliente se le entregó el mensaje funcional en lugar de filtrarle la excepción SQL, que quedó
únicamente en el log del servidor.

## ANTECEDENTES

RF-24 v2.0.
CU05 — Gestionar Dispositivos IoT, Flujo D.
Objetivo: verificar la atomicidad del registro de calibración ante un fallo real de escritura
de auditoría.

Esta es la primera evaluación del grupo actualizado: no se creó `EvaluacionV2`, no se compara
con la prueba histórica y no se reutilizan sus resultados. La implementación histórica de
`TC-M09-G79/test_tc_m09_150.py` declaraba expresamente no usar PostgreSQL real (operaba con
`DbFake`, `TransactionalStore` y repositorios falsos), de modo que no podría haber satisfecho
este caso; se consultó solo como referencia de estructura.

## ENTORNO AISLADO

**Tipo:** Local aislado, efímero
**PostgreSQL:** PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2) en contenedor
**Base:** `sgpmp_g79_v2`
**Backend local:** http://127.0.0.1:18079 (contenedor, imagen real del proyecto)
**Postgres local:** 127.0.0.1:55479
**Compose project:** `sgpmp-g79-v2`
**Contenedores:** `sgpmp-g79-v2-db`, `sgpmp-g79-v2-backend`
**Alembic:** `78f6f579b5ba (head)` — migraciones reales del proyecto, sin modificar
**Rama:** qa/juan-esteban-rf24-v2
**Commit:** 30ddd72144102a60af006b265a20cb18c1c72c85
**RUN_ID:** run-20261007-083841

**Safety guard remoto:** PASS

El guard verificó por SQL `current_database()`, `current_user` y el puerto, y comprobó que
tanto el DSN administrativo como la URL de la API apuntan a `127.0.0.1`, que la base es
exactamente `sgpmp_g79_v2` y que ninguna cadena referencia `inmero.co`, `sslip.io`,
`back-sigab` ni `dokploy`. Ambos puertos se publicaron solo en `127.0.0.1`, de modo que el
laboratorio no quedó expuesto a la red. **Ninguna sentencia SQL de esta prueba se ejecutó
contra TEST, DEV ni MAIN.**

El backend se ejecuta en contenedor porque no puede correr nativo en Windows: el módulo
`src/biological_assets/application/use_cases/_registrar_evento_bitacora.py` importa `fcntl`,
que solo existe en Unix.

## ROLES DE BD

**Owner de los objetos:** `postgres` (`modulo1.eventos`, `modulo9.calibraciones`) y
`sgpmp_owner` (`modulo9.auditorias_calibraciones`)
**Identidad de migraciones:** `sgpmp_owner`, vía `ALEMBIC_DATABASE_URL`
**App role (DATABASE_URL del backend):** `sgpmp_app`
**App role superuser:** false
**App role owner de las tablas implicadas:** false

El proyecto ya contempla esta separación: `alembic/env.py` distingue `ALEMBIC_DATABASE_URL`
(owner) de `DATABASE_URL` (la API, sujeta a RLS). El rol `postgres` existe porque el dump
baseline del proyecto asigna a él la propiedad de los objetos.

### Nota sobre `BYPASSRLS`, que condiciona la validez del laboratorio

`sgpmp_app` se creó con `BYPASSRLS`. Es necesario y no debilita la prueba:

- las políticas RLS de `modulo1` leen `app.current_user_id` y `app.current_role`, y la
  aplicación las fija en `get_current_user`
  (`src/identity_access/infrastructure/dependencies.py:147-151`), es decir **después** de
  autenticar. El login ocurre antes, así que un rol sujeto a RLS ve 0 filas en
  `modulo1.usuarios` y **nunca logra autenticarse**: se verificó empíricamente
  (`SELECT count(*) ... = 0` y login HTTP 401 `CREDENCIALES_INVALIDAS`);
- en los entornos desplegados la API se conecta con el usuario dueño de los objetos
  (`docker-compose.yml` arma `DATABASE_URL` con `POSTGRES_USER`, y `.env.example` indica que
  ese Postgres no bootstrapea `sgpmp_app`/`sgpmp_owner`), y un owner elude RLS. `BYPASSRLS`
  reproduce ese comportamiento **sin** conceder ownership ni superusuario, que son justamente
  las condiciones que invalidarían el `REVOKE`;
- lo decisivo: `BYPASSRLS` afecta solo políticas de **fila**, no los privilegios de **tabla**.
  Se comprobó antes del RUN que, con `BYPASSRLS` activo, `REVOKE INSERT` deja
  `has_table_privilege` en `false` y `GRANT` lo devuelve a `true`.

El RUN volvió a verificar esa efectividad antes de enviar el POST objetivo, de modo que la
conclusión no depende de este razonamiento sino de la comprobación empírica.

## ACTOR FUNCIONAL

**Usuario:** ingeniero@pecuaria.co
**id_usuario:** 3
**Rol:** Ingeniero de Campo
**Estado de cuenta:** Activo
**Credencial:** [REDACTED]
**Token obtenido antes del fault:** SÍ
**Permiso de calibración:** acciones `[1, 2]` sobre el recurso 12

La identidad se preparó con el propio mecanismo del proyecto: el hash bcrypt se generó con
`src/identity_access/domain/value_objects/contrasena.py`, sin inventar hashes a mano. El
archivo de seed no contiene contraseñas; el hash entra por variable de `psql`.

## FIXTURE

**dispositivo:** 1 — serial `IOT-G79V2-LAB-001`, activo
**sensor:** 1 — activo, perteneciente al dispositivo
**área:** 1 — asociación vigente (`tiene_estado = true`, `fecha_finalizacion = null`)
**categoría:** TEMPERATURA
**rango:** 0.0000 – 45.0000
**valor interior:** 22.5000

Los IDs se descubrieron dinámicamente del seed, no se heredaron de la prueba histórica ni de
TEST. El valor es el punto medio exacto del rango, calculado con `Decimal`: estrictamente
interior y nunca una frontera, para que la única invalidez posible del POST objetivo fuera el
fallo de auditoría.

Las migraciones ya aportaban los catálogos (11 roles, 361 permisos, estados de cuenta, tipos
de dispositivo y los 7 rangos de calibración), así que el seed solo creó los datos de negocio
del caso: finca, área, dispositivo, sensor, asociación vigente, el usuario Ingeniero con su
cuenta activa y su vínculo de finca. Ese vínculo es imprescindible: las políticas RLS de
`modulo9` filtran por `fn_fincas_del_usuario`.

## CONTROL POSITIVO

**HTTP:** 201
**id_calibracion:** 1
**calibración persistida:** SÍ
**auditoría modulo9 creada:** SÍ
**evento RF-10 observado:** NO

Privilegios antes del control: `calibraciones_insert = true`, `audit_m9_insert = true`,
`eventos_insert = true`.

Sobre el evento RF-10: se consultó `modulo1.eventos` tras el control y el camino de éxito no
generó ninguna fila. Se registra el comportamiento real **sin** convertirlo en una expectativa
adicional de G79, cuyo oráculo es la atomicidad de la calibración frente al fallo de auditoría.
La exposición y auditoría general corresponden a sus propios grupos.

## SNAPSHOT PRE DEL POST OBJETIVO

**count_before:** 1
**IDs:** `[1]`

Snapshot autoritativo con filas completas en `rows_target_before.json`, para poder comprobar
después que ninguna fila histórica fue alterada y no solo que el conteo coincide.

## FAULT INJECTION

**`modulo9.auditorias_calibraciones` INSERT antes:** true
**`modulo1.eventos` INSERT antes:** true
**REVOKE ejecutado:** SÍ (como DB_OWNER, solo en `sgpmp_g79_v2`)
**INSERT auditoría modulo9 después del REVOKE:** false
**INSERT eventos después del REVOKE:** false
**INSERT calibraciones conservado:** true

Se revocó únicamente el `INSERT` de las dos tablas de auditoría. No se tocó el `INSERT` de
`modulo9.calibraciones`, ni el `SELECT` de datos funcionales, ni `CONNECT`, ni el `USAGE` de
los schemas: cambiar eso habría movido el punto de fallo y la prueba habría dejado de ser la
del caso.

La comprobación de efectividad se hizo **antes** del POST: si `audit_insert` hubiera seguido en
`true`, el POST no se habría enviado y el resultado habría sido una ejecución inválida, no un
defecto del producto.

## POST OBJETIVO TC-M09-150-v2.0

### Request

```json
{
  "modo_calibracion": "SENSOR",
  "id_dispositivo_iot": 1,
  "id_infraestructura": 1,
  "valor_referencia": 22.5,
  "observaciones": "QA TC-M09-150-v2.0",
  "fecha_calibracion": "2026-10-07T08:38:45.769627+00:00"
}
```

Encabezado `Authorization`: [REDACTED]. Ejecutado **una sola vez**, con el token obtenido antes
del fault. Sin reintentos.

### Response

**HTTP esperado:** 500
**HTTP obtenido:** 500
**error_code:** `AUDITORIA_CALIBRACION_FALLIDA`
**Devuelve `id_calibracion`:** NO

**Mensaje esperado:**
Error de integridad: No se pudo garantizar la trazabilidad de la calibración. El ajuste no ha sido aplicado; por favor, intente de nuevo.

**Mensaje obtenido:**
Error de integridad: No se pudo garantizar la trazabilidad de la calibración. El ajuste no ha sido aplicado; por favor, intente de nuevo.

**Coincidencia exacta:** PASS

### Punto de fallo observado

`backend_fault.log`, capturado durante el POST objetivo:

```text
INFO: "POST /configuracion/sensores/1/calibrar HTTP/1.1" 500 Internal Server Error
InfrastructureError [AUDITORIA_CALIBRACION_FALLIDA] en .../configuracion/sensores/1/calibrar:
ProgrammingError('(psycopg2.errors.InsufficientPrivilege) permission denied for table auditorias_calibraciones')
```

La evidencia permite concluir que la petición superó las validaciones funcionales (no hubo 400,
403 ni 404), que la escritura alcanzó la transacción de persistencia y que el fallo corresponde
al `INSERT` de auditoría. Se verificó además que **no** apareció
`permission denied for table calibraciones`: el fallo no ocurrió antes del punto buscado.

Nótese también que la excepción SQL quedó solo en el log del servidor: la respuesta pública fue
el mensaje funcional, no un traceback ni un error de PostgreSQL.

## VERIFICACIÓN DEL ROLLBACK

| Verificación | PRE | POST | Resultado |
|---|---:|---:|---|
| count calibraciones sensor 1 | 1 | 1 | PASS |
| IDs | `[1]` | `[1]` | PASS |
| históricos intactos | — | sin filas alteradas ni desaparecidas | PASS |
| nueva calibración del intento | 0 | 0 | PASS |
| auditoría huérfana | 0 | 0 | PASS |

La comparación no se limitó al conteo: se contrastaron fila por fila `id_dispositivo_iot`,
`id_sensor`, `valor_referencia`, `fecha_calibracion`, `id_usuario` y `observaciones`. También
se comprobó que no quedó ninguna auditoría de calibración sin su calibración, ni eventos
parciales atribuibles al intento fallido.

## RESTAURACIÓN

**GRANT ejecutado:** SÍ
**Privilegios restaurados:** SÍ
**Restauración pendiente:** NO

Se devolvieron exactamente los privilegios que el snapshot PRE demostraba disponibles
(`INSERT` en las dos tablas de auditoría). No se usó `GRANT ALL`, `SUPERUSER` ni
`ALTER OWNER`. El `GRANT` se ejecuta en un bloque `finally`, de modo que no depende de que una
assertion pase ni del orden de los tests. La verificación de cierre confirmó, por consulta
independiente, que `has_table_privilege` volvió al estado PRE en las tres tablas.

## RESULTADO PYTEST

**Tests:** 1
**Passed:** 1
**Failed:** 0
**Errors:** 0

El test se ejecutó con `--noconftest`: el `conftest.py` del repositorio importa `src`, que
arrastra `fcntl` y no es importable en Windows. La prueba es autónoma y no necesita ese
conftest; no se modificó ningún archivo del repositorio para lograrlo.

**Escrituras funcionales del RUN:** 1 POST de control positivo y 1 POST objetivo. Ninguna
repetición.

## VERIFICACIÓN FINAL (SOLO LECTURA)

Ejecutada después del RUN, sin SQL de escritura y sin borrar nada:

- calibraciones del sensor: `[1]`, idéntico al cierre del RUN;
- el control positivo sigue presente, con su auditoría;
- no existe ninguna calibración con las observaciones del POST objetivo;
- auditorías huérfanas: 0;
- privilegios del app role de vuelta en el estado PRE;
- fixture sin cambios: dispositivo activo, sensor activo, asociación vigente;
- rango sin cambios: 0.0000 – 45.0000;
- app role sigue sin ser superusuario ni owner de las tablas implicadas.

## EVIDENCIAS

```text
git_pre.txt                      git_final.txt
environment_guard.json           postgres_version.txt        alembic_state.txt
db_identity_pre.json             db_role_pre.json            table_owners_pre.json
fixture.json                     actor.json

control_request.json             control_response.json
control_db_calibracion.json      control_db_auditoria_m9.json    control_db_eventos.json

count_target_before.json         rows_target_before.json
privilegios_pre.json             privilegios_pre_snapshot.txt
revoke_output.txt                privilegios_revoke.json

target_request.json              target_response.json        backend_fault.log
count_target_after.json          rows_target_after.json      audit_partial_check.json

restore_output.txt               privilegios_post_restore.json

pytest-TC-M09-150-v2.0.xml       pytest-TC-M09-150-v2.0.log
automation/                      automation_manifest.json
verificacion-final-readonly.json seguridad-evidencias.json
TC-M09-G79_resultado.md
```

`automation/` conserva, ya sanitizados, los 10 artefactos que produjeron el RUN (test, helpers,
verificador de cierre, compose y los 6 SQL del laboratorio) con su SHA-256 en
`automation_manifest.json`, de modo que la prueba pueda repetirse exactamente. Los archivos no
se modificaron entre la ejecución y la captura de hashes.

`seguridad-evidencias.json` reporta la carpeta limpia: ningún archivo contiene contraseñas,
`DATABASE_URL` con contraseña, JWT, Bearer con token, cookies, `POSTGRES_PASSWORD` ni
`APP_DB_PASSWORD`. El sanitizador redacta además la contraseña embebida en cualquier cadena de
conexión, aunque no esté en el entorno.

## OBSERVACIONES

Solo hechos demostrados por esta corrida.

1. **El rollback es real, no inferido.** No se concluyó nada a partir de que el código contenga
   un `rollback()`: la atomicidad se comprobó consultando PostgreSQL antes y después del POST,
   con filas completas y no solo conteos.

2. **El fault injection es genuino.** Se verificó antes del POST que el app role no es owner ni
   superusuario y que el `REVOKE` dejó `has_table_privilege` en `false` para la auditoría y en
   `true` para calibraciones. El `permission denied` provocado a propósito es la precondición de
   la prueba, no un defecto.

3. **El error SQL no se filtra al cliente.** La respuesta pública fue el mensaje funcional del
   FA; la excepción `InsufficientPrivilege` quedó únicamente en el log del servidor.

4. **El camino de éxito no genera evento RF-10.** Tras el control positivo, `modulo1.eventos`
   no registró filas. Se documenta como comportamiento real observado, sin añadirlo al oráculo
   de G79.

5. **Las migraciones requieren que `sgpmp_app` exista antes de aplicarse.** Una migración
   (`315eaa6c5dc1_f3`) ejecuta `GRANT EXECUTE ... TO sgpmp_app` sin condicional, de modo que
   `alembic upgrade head` falla si el rol no se creó previamente. Es un detalle de preparación
   de entorno que conviene conocer para reproducir el laboratorio.

6. **El login no funciona con un rol de BD sujeto a RLS.** Verificado empíricamente: las
   políticas de `modulo1.usuarios` solo permiten ver la propia fila o actuar como
   Administrador, y el contexto RLS se fija después de autenticar, así que la autenticación
   queda sin filas visibles. Esto no afecta el oráculo de G79 y no se evalúa aquí, pero es un
   hallazgo de configuración relevante para el diseño F1 de control de acceso por BD: tal como
   están hoy las políticas, la API solo puede autenticar si su rol elude RLS.

7. **Sobre el nombre de este informe.** El paquete pedía `TC-M09-F79_resultado.md`. Se usa
   `TC-M09-G79_resultado.md`, con el identificador del grupo, por indicación expresa del
   responsable de QA de mantener los informes nombrados como el grupo al que pertenecen.

8. **Estado del laboratorio al cerrar.** Los contenedores quedaron **en ejecución** a propósito.
   La base usa `tmpfs`, de modo que detener el contenedor descarta los datos en memoria; dejarlo
   arriba permite inspeccionar el estado mientras se valida el informe, conforme al criterio de
   no destruir el entorno antes de revisar el resultado. La limpieza es una operación separada.

## INCIDENCIA

**INCIDENCIA REQUERIDA:** NO

No se encontró defecto del producto. El comportamiento observado es exactamente el que RF-24
v2.0 exige: ante el fallo de la escritura de auditoría, la transacción revierte, no queda
ninguna calibración persistida y la API responde `500` con el mensaje funcional correcto.

El `permission denied` provocado por el `REVOKE` es la precondición del experimento y no
constituye una incidencia.

La observación 6 (el login requiere un rol de BD que eluda RLS) no se convierte en incidencia
desde este grupo: no pertenece al oráculo de TC-M09-150-v2.0 y correspondería evaluarla en el
grupo de control de acceso por BD, con su propio esperado. Se deja registrada para que el
equipo decida.

## CONCLUSIÓN

**TC-M09-150-v2.0 queda APROBADO**, y con él el grupo **TC-M09-G79-v2.0**, sobre evidencia
empírica del RUN `run-20261007-083841` en un laboratorio local aislado con PostgreSQL 18.6 real
y el backend real del proyecto, sin dobles de sesión, repositorios ni transacción.

La cadena quedó demostrada en este orden: el camino normal funciona (control positivo HTTP 201
con auditoría); se capturó el conteo y las filas previas; se revocó el `INSERT` de auditoría al
rol real de la aplicación, que no es owner ni superusuario; se verificó que el `REVOKE` era
efectivo y que el `INSERT` de calibraciones seguía disponible; el único POST objetivo alcanzó el
punto de auditoría y falló allí, acreditado por `permission denied for table
auditorias_calibraciones`; la API respondió `500` con el mensaje exacto del FA; el conteo y los
IDs quedaron idénticos, sin filas alteradas, sin calibración parcial y sin auditoría huérfana;
y los privilegios se restauraron a su estado previo.

No se modificó código productivo, migraciones ni el esperado del caso. Todo lo nuevo reside en
`TC-M09-G79-v2.0/`, y la carpeta histórica `TC-M09-G79/` quedó intacta.
