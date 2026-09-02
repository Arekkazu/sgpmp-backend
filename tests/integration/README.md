# Pruebas de integracion

Estas pruebas ejercitan los routers, casos de uso, repositorios SQLAlchemy y el
esquema real de PostgreSQL. Cada prueba abre una transaccion exterior y convierte
los `commit()` de la aplicacion en savepoints. Al finalizar hace rollback, por lo
que no conserva usuarios, sesiones, eventos, permisos ni cambios DDL de pytest.

## Provisionar la base de pruebas

```bash
./scripts/provisionar_pruebas.sh
```

Recrea la base de pruebas a partir del esquema de la base de desarrollo (todos
los schemas de negocio, mas los catalogos de referencia) y la sella en head.

**Hace falta porque `alembic upgrade head` no puede levantar una base desde
cero.** El baseline `f7fe43537842` es un no-op deliberado: el esquema hasta ese
punto se construyo a mano, modulo por modulo, con SQL suelto. Alembic solo
aplica los deltas posteriores, asi que sobre una base vacia falla en cuanto
intenta `ALTER` sobre una tabla que no existe. Por eso la base de pruebas vivio
mucho tiempo con solo `modulo1` y sellada en el baseline, y la integracion de
modulo 9 nunca llego a ejecutarse.

Mientras el baseline siga siendo un no-op, la unica fuente fiel del esquema
completo es la base de desarrollo. El script aborta si esa base no esta en head,
porque en ese caso el sello mentiria.

El script **borra y recrea** la base de destino, previo respaldo en `backups/`.
Solo acepta nombres de base de pruebas (la misma lista que valida `conftest.py`).
No copia datos transaccionales: los tests crean lo que necesitan y cada uno se
revierte en su transaccion. Si lo corres con migraciones sin mergear en tu rama,
la base queda sellada en una revision que `dev` desconoce.

## Requisitos

- Una base PostgreSQL exclusiva para pruebas, provisionada con el script de arriba.
- El nombre debe contener `test` o ser una base local permitida explícitamente:
  `pruebas` o `pruebas-integrador`.
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
  activacion asincrono, CAPTCHA obligatorio antes de persistir, registro,
  reenvio, hash del token, auditoria y activacion.
- RF-02: login, JWT y sesion persistida con vigencia de ocho horas.
- RF-01/08/09: recuperacion de cuenta activa, redireccion de cuenta pendiente
  hacia activacion, hash del token y restablecimiento de contrasena.
- RF-01: validacion de la migracion Alembic que protege nuevas identificaciones
  sin bloquear la edicion de otros campos en filas historicas incompatibles.
- RF-04/06: cambio de rol aplicado con el JWT vigente, sin invalidar la sesion
  ni exigir relogin.
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
- RF-12: migracion Alembic idempotente del permiso exclusivo del Administrador
  y enmascaramiento de identificacion para actores sin esa capacidad.
- RF-14: persistencia por el servicio central, bandeja interna y marcado como
  leida sin acceso a notificaciones de otros usuarios.
