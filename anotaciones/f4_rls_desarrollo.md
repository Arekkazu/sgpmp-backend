# F4 — Piloto RLS: lo que hizo Desarrollo

**Rama:** `feature/f4-rls-desarrollo`, sobre `feature/RolesF4` (PR #485, migración `bc82ffbdf797` del DBA) más `dev`.
**Plan:** `IMPLEMENTACION_control_acceso_bd_rls.md`, F4. Cuando el plan y el DBA no coinciden, manda la decisión del DBA en el PR #485 (comentario del 2026-10-06).

## Decisiones que aplica

| Tema | Decisión | Quién |
|---|---|---|
| Alcance global | Ningún rol lo tiene, ni el Administrador: cada uno ve las fincas que tiene en `usuarios_fincas`. `fn_alcance_global` no se crea | DBA |
| D1 (tareas de fondo) | Usuario de servicio en `modulo1.usuarios` con filas explícitas en `usuarios_fincas`; nada de `BYPASSRLS` | DBA |
| D4 (ingesta IoT) | Mismo usuario de servicio que D1 (uno solo) | Equipo |
| Alta de fincas | Quien la registra queda con acceso | Equipo |

## Cambios

**1. La identidad sobrevive al `commit()`.** `set_config(..., true)` muere con la transacción, así que todo lo que corría después del primer commit del request (por ejemplo, el avance automático de fase de RF-37) quedaba sin identidad: bajo RLS, cero filas. Ahora `declarar_identidad` (`src/shared/database.py`) guarda la identidad en `Session.info`, y un listener `after_begin` la reaplica en cada transacción de esa sesión. `get_current_user` la usa en lugar de los tres `set_config` sueltos.

**2. Usuario de servicio (D1 y D4).**
- La migración `5c3e9b1d7a20` crea `servicio.sistema@sgpmp.local` con rol Administrador. Las políticas de `modulo1` solo reconocen ese rol por nombre, y es la identidad que ya declaraban las tareas.
- Su contraseña es aleatoria y su cuenta queda Inactiva. El rol es protegido, así que esa cuenta no se puede reactivar desde la API.
- La migración le da acceso a todas las fincas existentes. El trigger diferido `trg_despues_insertar_finca` se lo da a cada finca nueva al confirmar la transacción. Su fila queda última para no figurar como propietario.
- `sesion_sistema()` reemplaza a `SessionLocal()` en las 9 tareas de `main.py` y en las 3 factories de batch de M05.
- `get_db_sistema` se usa en los 5 endpoints de dispositivos: `/iot/telemetria`, `/iot/telemetria/batch`, `/iot/eventos-edge`, `/iot/heartbeat` y `POST /iot/alertas`.
- El id del usuario se resuelve por correo al empezar la primera transacción, porque difiere entre bases.
- Se retira `_declarar_identidad_sistema`, que solo ponía el rol.

**3. Nadie es global en la app.** `AlcanceFincaAdapter.es_global` devuelve siempre `False`. Los 12 archivos que lo usan, incluido el alcance de activos de M05, pasan por ahí. Consecuencia visible: el Administrador ve solo sus fincas en todos los módulos.

**4. Alta de fincas bajo RLS.** `guardar(finca, id_creador)` le da acceso al propietario indicado y al creador, en ese orden. `FincaModel` deja de usar `INSERT ... RETURNING`: con `RETURNING`, la fila nueva tiene que pasar la política SELECT, y nadie tiene acceso a la finca hasta que se inserta su fila en `usuarios_fincas`.

## Verificación

Hecha en Postgres 17 desechable, con toda la cadena de Alembic, dueño `sgpmp_owner` y los grants de `sgpmp_app` iguales a DEV:

- `tests/integration/test_control_acceso_f4_aislamiento.py`, conectado como `sgpmp_app` con `SET LOCAL ROLE`. La prueba falla si el rol es superusuario o tiene `BYPASSRLS`. Cubre cinco casos:
  - dos usuarios del mismo rol solo ven sus activos, infraestructuras y fincas;
  - un UPDATE sobre un activo ajeno afecta 0 filas;
  - mover un activo propio a una finca ajena falla por RLS;
  - las vistas también filtran;
  - sin identidad, no se ve nada.
- La identidad sobrevive al `commit()` y al `rollback()`, y no pasa a otra sesión.
- Pruebas como `sgpmp_app` con el código real:
  - el alta de una finca deja los accesos en el orden propietario, creador, servicio;
  - el usuario de servicio se resuelve solo y ve todas las fincas.
- Con `pol_fincas_select` sin la excepción del Administrador, el alta sigue funcionando. En SQL, el mismo INSERT con `RETURNING` falla con `new row violates row-level security policy`.
- La migración `5c3e9b1d7a20` se revierte y se vuelve a aplicar sin errores.
- Suite unitaria: sin fallos nuevos. Fallan 2, que también fallan en `dev` (necesitan un Postgres local).
- Suite de integración: los mismos 15 fallos que en `dev`, más 5 pruebas nuevas en verde.

Dos pruebas cambiaron porque fijaban la regla vieja ("el administrador ve todo"):
- `test_inc_m09_g82_acceso_finca.py::test_permiso_de_gestion_no_concede_alcance_global`
- `test_inc_m09_g82_acceso_finca_integration.py::test_administrador_solo_consulta_sus_fincas`

## Pendiente

**DBA:**
1. Quitar `OR fn_rol_actual() = 'Administrador'` de las políticas SELECT de `fincas` e `infraestructuras`, y en INSERT/UPDATE de `infraestructuras` filtrar por las fincas del usuario. La app ya está lista para eso: el alta de fincas lo resiste.
2. **Bloqueante para cambiar `DATABASE_URL`: las políticas de `modulo1` (migración `8d80fb56a30b`) impiden autenticarse como `sgpmp_app`.** Hoy, con el código real conectado como `sgpmp_app`, `get_current_user` responde 401 a todos, Administrador incluido. Las causas:
   - `roles`, `permisos` y `recursos` solo los lee el rol `'Administrador'`, pero la app los lee en cada request para autorizar a cualquiera.
   - `pol_tokens_select` y `pol_tokens_update` enlazan por `tokens.id_sesion`, que solo existe en los tokens de refresco. El de acceso se enlaza por `sesiones.id_token`, así que nadie ve su propio token de acceso.
   - `pol_cuentas_usuarios_update` no deja al usuario actualizar su propia cuenta (`ultimo_acceso`, intentos fallidos).
   - Login, registro, activación, refresh y recuperación ocurren antes de que haya identidad.
   - `credenciales_servicio` e `intentos_anonimos_ip` tienen RLS sin ninguna política.

   La propuesta que se le pasó al DBA, probada como `sgpmp_app`, deja autenticar al Productor y al Administrador:
   - catálogos legibles para todos;
   - el enlace del token corregido;
   - actualización de la propia cuenta;
   - una función `SECURITY DEFINER` por cada búsqueda previa a la identidad.

   Del lado de desarrollo quedan dos cosas:
   - Declarar la identidad apenas se resuelve quién es: ya está hecho en `get_current_user`; falta en login, registro, refresh y recuperación.
   - Insertar `tokens` y `usuarios` sin `RETURNING`: con `RETURNING`, la fila nueva tiene que pasar la política SELECT antes de quedar enlazada.
3. Triggers que fallan abiertos cuando RLS les oculta filas:
   - `trg_fn_fase_activo_estado_valido`;
   - `trg_finca_nombre_unique`: la unicidad de nombre deja de ver las fincas ajenas, y no hay índice único que la respalde;
   - `trg_finca_no_delete`.
4. `ANALYZE` y `EXPLAIN (ANALYZE, BUFFERS)` con y sin política.

**Datos (DEV y TEST):**
- Asignarles fincas a los 3 administradores que no tienen ninguna.
- Asignarles fincas a los usuarios de Integración M04 y M06.

**Despliegue:** `DATABASE_URL` a `sgpmp_app` va al final, cuando el punto 2 de arriba esté resuelto.

**Fuera de F4:** los workers de reportes de gastos e historial de suministros procesan como el usuario de servicio. El filtro por usuario sigue siendo el que guarda cada trabajo. Cuando M05 tenga RLS (F5), conviene que corran con la identidad de quien pidió el trabajo.
