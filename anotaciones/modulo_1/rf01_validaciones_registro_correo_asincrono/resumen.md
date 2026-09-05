# RF-01 — Resumen de implementación

Issue #1601 · PR #48 · rama `feature/rf01-validaciones-registro-correo-asincrono`

Cierra tres huecos de RF-01: confirmación de contraseña, formato del número de
identificación y envío del correo de activación fuera del request.

---

## 1. Confirmación de contraseña

`UsuarioCreateDTO` exige `confirmar_contrasena` y verifica que coincida con
`contrasena`. La validación es de campo (`field_validator`), no de modelo, para
que la respuesta de error conserve `field: "confirmar_contrasena"` — el contrato
de error del proyecto lo expone y el frontend lo usa para marcar el input.

```json
{"error_code": "VAL_ENTRADA", "fields": [
  {"field": "confirmar_contrasena", "message": "Error de confirmación. Las contraseñas ingresadas no coinciden. …"}
]}
```

## 2. Formato del número de identificación

RF-01 exige rechazar caracteres alfabéticos, pero también lista `Pasaporte`
entre los tipos válidos — y un pasaporte es alfanumérico. **La regla depende del
tipo declarado:**

| `tipo_identificacion` | Patrón | Ejemplo válido |
|-----------------------|--------|----------------|
| `CC`, `CE` | `^[0-9]+$` | `1090234567` |
| `Pasaporte` | `^[A-Za-z0-9]+$` | `AB1234567` |

Fuente única de la regla: `src/identity_access/domain/value_objects/identificacion.py`
(`identificacion_valida` / `mensaje_identificacion_invalida`), con los patrones
en `src/shared/regex.py`. La comparten cuatro puntos:

- `UsuarioCreateDTO` — registro.
- `AgroFusionCreateUserDTO` — alta server-to-server (Mecanismo B).
- `Usuario.registrar_nuevo` — invariante de dominio.
- `EditarPerfilUseCase` — edición de perfil.

`tipo_identificacion` pasó de `str` libre a `Literal["CC","CE","Pasaporte"]` en
los DTO. Antes solo lo restringía el `CHECK` de la BD, así que un valor inválido
llegaba hasta PostgreSQL; ahora devuelve `400` con el campo señalado.

**Por qué la validación de perfil no vive en el DTO.** En `EditarPerfilDTO` ambos
campos son opcionales: una edición parcial puede traer el número sin el tipo (o
al revés), y el DTO no conoce el tipo efectivo. La regla se aplica en
`EditarPerfilUseCase`, justo después de volcar los cambios sobre la entidad y
antes de `usuarios_repo.actualizar`, que es el único punto donde coexisten el
valor declarado y el que la cuenta ya tenía.

## 3. Correo de activación asíncrono

`CrearUsuarioUseCase` ya no recibe el `NotificacionService`; recibe el puerto
`CorreoActivacionPort`. El router inyecta `CorreoActivacionBackgroundAdapter`,
que agenda la notificación con `BackgroundTasks` sobre una sesión `SessionLocal`
propia (la del request ya está cerrada cuando la tarea corre).

`src/shared/email.py` **no cambió**: conserva los 3 intentos y las pausas de 5 s.
Lo que cambió es cuándo ocurren.

Medido con el SMTP apuntando a un puerto muerto:

```
INFO:  "POST /usuarios/ HTTP/1.1" 201 Created          <- 0,32 s
Intento 1/3 fallido al enviar correo a … Connection refused
Intento 2/3 fallido al enviar correo a … Connection refused
Intento 3/3 fallido al enviar correo a … Connection refused
```

Antes el usuario esperaba ~15 s (3 intentos + 2 pausas de 5 s) dentro del
request. La respuesta es la que pide el RF:

```json
{"message": "Registro exitoso, envío de correo en proceso."}
```

`503` se retiró de los `responses` del endpoint. No es una pérdida de contrato:
`NotificacionService.notificar` ya capturaba toda excepción y la registraba en el
log, así que ese `503` nunca llegaba al cliente tampoco antes del cambio.

---

## Base de datos

### Migración `e7b31f4a6c20`

`down_revision = "c8e4a5b13d72"`. En la rama original apuntaba a
`d4e2f8a15c9b`, que dejó de ser la cabeza al mergearse RF-10; eso producía dos
cabezas y `alembic upgrade head` fallaba con *Multiple head revisions are present*.

Instala `modulo1.trg_fn_validar_identificacion_numerica` y el trigger
`trg_validar_identificacion_numerica`, `BEFORE INSERT OR UPDATE OF
numero_identificacion, tipo_identificacion`. Dispara solo en altas o cuando
cambia alguno de los dos campos, de modo que una fila histórica incompatible
puede seguir actualizando cualquier otro campo.

El patrón se resuelve en una variable `DECLARE` en vez de en línea: PL/pgSQL no
acepta una expresión `CASE` como valor de una opción de `RAISE … USING`.

Se mantiene el trigger, y no un `CHECK`, porque quedan filas heredadas que un
`CHECK` validado sobre toda la tabla rechazaría.

### Datos normalizados en `sgpmp`

Había 7 filas con `numero_identificacion` no numérico y `tipo_identificacion = 'CC'`.
Se normalizaron 5:

```sql
UPDATE modulo1.usuarios
SET numero_identificacion = '9' || lpad(id_usuario::text, 14, '0')
WHERE id_usuario IN (22, 24, 26, 45, 46);
```

Se usa un valor sintético derivado del `id_usuario` en vez de filtrar los
dígitos del original: los ids 22, 24 y 26 colapsan al mismo número al quitar las
letras y chocarían con `uq_usuario_numero_identificacion`.

**Se conservan intactas** las filas 30 (`TEST-GESTOR-01`) y 31
(`TEST-REVFISCAL-01`), fixtures de módulo 9. El trigger las tolera; solo un
administrador que edite su documento recibirá un `400` pidiendo un valor válido.

Este DML no forma parte de la migración: son ids concretos de la base de
desarrollo, no un cambio de esquema.

### Aplicación

```bash
alembic upgrade head                                  # sgpmp
DATABASE_URL=<…>/pruebas alembic upgrade head         # ver nota
```

La base `pruebas` es solo-módulo1 y está en el baseline `f7fe43537842`, así que
la cadena completa no le aplica (falla en las migraciones de `modulo9`). La
revisión RF-01 se ejecutó ahí directamente, reusando el propio archivo de
migración vía `MigrationContext`/`Operations`, sin tocar su `alembic_version`.

RBAC: sin cambios. No hay recurso ni permiso nuevo — `POST /usuarios/` es
público y el resto de endpoints tocados ya tenían sus permisos.

---

## Verificación ejecutada

- `pytest tests -q` → **177 pasan, 7 omitidas**. Las omitidas son de módulo 9
  (`La base de pruebas no tiene el schema modulo9`), preexistentes.
- Trigger probado contra `sgpmp` en un bloque revertido: CC alfanumérico
  rechazado, pasaporte alfanumérico aceptado, pasaporte con guion rechazado,
  fila heredada capaz de actualizar otros campos, cambio de tipo revalidado.
- Endpoint contra `uvicorn` con SMTP muerto: `201` en 0,32 s con los tres
  reintentos posteriores en el log; `400` con `field` correcto en confirmación,
  identificación y tipo; `403` de menor de edad sin regresión.

---

## Fuera de alcance

- **CAPTCHA.** Estuvo fuera del alcance histórico del PR #48 y fue resuelto
  posteriormente por la implementación dedicada de la issue #1600. Ver
  `anotaciones/modulo_1/rf01_captcha_registro.md`.
- **Cola durable para el correo.** `BackgroundTasks` vive en el proceso de
  FastAPI: si el proceso se reinicia con tareas pendientes, esos correos se
  pierden. Sacarlo a una cola persistente es una mejora de infraestructura
  aparte, no un requisito del RF.
- **Filas 30 y 31 de `sgpmp`.** Se dejaron con identificación no numérica por
  decisión explícita, al ser fixtures que módulo 9 podría referenciar por ese
  valor.
