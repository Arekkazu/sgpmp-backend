# RF-01/10 — Auditoría de registro y activación de cuenta

## Hallazgo confirmado

La auditoría de referencia en `estado.md` era correcta: el registro persistía
el usuario y la cuenta, y la activación cambiaba su estado, pero ninguno de los
dos casos de uso llamaba a `EventoRepository.registrar`.

El catálogo existente reserva los tipos iniciales del módulo para estos flujos:

- `1`: registro de usuario;
- `2`: activación de cuenta.

Los tipos `3` y `4` continúan correspondiendo al login exitoso y fallido.

## Implementación

- `CrearUsuarioUseCase` registra el evento tipo `1` después de crear usuario y
  cuenta, pero antes del `commit`.
- `ActivarCuentaUseCase` registra el evento tipo `2` después de aplicar la
  transición y antes del `commit`.
- Ambos eventos pertenecen a la misma transacción de la operación principal.
  Si la auditoría obligatoria no puede persistirse, el `except` ejecuta
  `rollback` y la operación no queda confirmada, como exige RF-10.
- El router inyecta `SqlAlchemyEventoRepository` y entrega la IP y el
  user-agent normalizados por el middleware.
- Los detalles contienen IDs, acción y transición de estado. No incluyen token,
  contraseña, correo ni número de identificación.
- El correo de activación continúa enviándose después del `commit`, por lo que
  no se alteró la frontera transaccional documentada en `CLAUDE.md`.
- Desde RF-14, ese envío pasa por `NotificacionService` en segundo plano para
  aplicar anti-spam y registrar los canales EMAIL e INTERNO.

## Verificación del catálogo

Antes de desplegar en un ambiente cuya semilla no sea la misma, comprobar:

```sql
SELECT id_tipo_evento, nombre, accion
FROM modulo1.tipos_eventos
WHERE id_tipo_evento IN (1, 2)
ORDER BY id_tipo_evento;
```

La consulta debe devolver los tipos de registro y activación. No se requiere
una migración de esquema para este cambio.
