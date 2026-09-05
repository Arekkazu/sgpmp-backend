# INC-M01-05-035 — RF-07: rechazo de la contraseña actual

Issue: `#84`

Caso reportado: `TC-M01-035`

## Defecto reproducido

El `PUT /contrasena/usuarios/{id_usuario}` aceptaba que
`contrasena_actual`, `nueva_contrasena` y `confirmar_nueva_contrasena`
tuvieran el mismo valor. El caso respondía `200 OK`, aunque RF-07 exige
`409 Conflict` con el mensaje:

> No se permite reutilizar la contraseña actual. Defina una clave completamente nueva.

El baseline incluía un trigger que comparaba `NEW.contrasena_cifrada` con
`OLD.contrasena_cifrada`. Esa comparación no protege esta regla: BCrypt
genera un salt nuevo en cada cifrado, así que una misma contraseña produce
hashes diferentes.

## Corrección

El caso de uso verifica la nueva entrada contra el hash BCrypt vigente antes
de cifrar o escribir. Si coincide, lanza `ConflictError` con código
`CONTRASENA_REUTILIZADA` y el mensaje literal de RF-07. La migración
`b7e19f07a038` elimina el trigger ineficaz; el `downgrade` lo restaura para
mantener reversibilidad.

El rechazo ocurre antes de modificar la contraseña o la cuenta, registrar
auditoría, invalidar sesiones/tokens o emitir una notificación.

## Verificación

La prueba `tests/integration/test_tc_m01_035_reutilizacion_contrasena.py`
reproduce el flujo del equipo de pruebas: inicia sesión y envía el `PUT` con
la contraseña vigente en los tres campos. Comprueba:

- respuesta `409`, código `CONTRASENA_REUTILIZADA` y mensaje exacto;
- hash de contraseña sin cambios y todavía válido;
- contador de intentos y bloqueo sin cambios;
- sesión activa y token sin consumir;
- ningún evento de cambio de contraseña ni notificación.

El escenario ya estaba cubierto parcialmente por las pruebas unitarias y la
matriz de integración de RF-07; el caso dedicado añade trazabilidad directa a
`TC-M01-035` e inspecciona todos los efectos persistentes relevantes.
