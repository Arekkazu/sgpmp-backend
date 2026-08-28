# Pruebas de integracion del modulo 1

Estas pruebas ejercitan los routers, casos de uso, repositorios SQLAlchemy y el
esquema real de PostgreSQL. Cada prueba abre una transaccion exterior y convierte
los `commit()` de la aplicacion en savepoints. Al finalizar hace rollback, por lo
que no conserva usuarios, sesiones, eventos, permisos ni cambios DDL de pytest.

## Requisitos

- Una base PostgreSQL exclusiva para pruebas con el esquema `modulo1` cargado.
- El nombre de la base debe contener `test` o ser exactamente `pruebas`.
- La variable `TEST_DATABASE_URL` debe definirse solo en la terminal. No se debe
  guardar una contrasena real en `.env`, `.env.example` ni en archivos versionados.

Ejemplo en PowerShell:

```powershell
$env:TEST_DATABASE_URL = "postgresql://USUARIO:CONTRASENA@localhost:5432/pruebas"
```

## Ejecucion

Solo integracion:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration -m integration -q
```

Suite completa, unitarias e integracion:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Solo unitarias, sin requerir PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -m "not integration" -q
```

Al terminar se puede retirar la credencial de la sesion:

```powershell
Remove-Item Env:TEST_DATABASE_URL
```

## Cobertura integrada

- RF-01: confirmacion de contrasena, identificacion numerica, correo de
  activacion asincrono, registro, reenvio, hash del token, auditoria y
  activacion.
- RF-02: login, JWT y sesion persistida con vigencia de ocho horas.
- RF-01/08/09: recuperacion de cuenta activa, redireccion de cuenta pendiente
  hacia activacion, hash del token y restablecimiento de contrasena.
- RF-01: validacion de la migracion Alembic que protege nuevas identificaciones
  sin bloquear la edicion de otros campos en filas historicas incompatibles.
- RF-05/06: autorizacion RBAC en router, edicion del perfil propio y proteccion
  del ultimo usuario activo de un rol protegido.
- RF-10: categoria canonica de eventos al consultar auditoria.
- RF-10: retención mínima de 12 meses, archivado histórico idempotente e
  inmutabilidad de los registros archivados.
- RF-10: consulta del archivo histórico (`GET /auditoria/archivado/`) con filtros,
  paginación, 403 al no administrador y 400 por rango de fechas inconsistente; y
  alerta interna al administrador cuando el archivado automático falla.
- RF-11: ausencia del listado legacy, permiso del listado administrativo y orden
  descendente por fecha de registro.
- RF-12: semilla idempotente del permiso y enmascaramiento de identificacion.
- RF-14: persistencia por el servicio central, bandeja interna y marcado como
  leida sin acceso a notificaciones de otros usuarios.
