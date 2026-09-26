# RF-08 — resiliencia ante fallo SMTP en recuperación

## Incidente

`INC-M01-14-044`: `POST /contrasena/recuperar` propagaba el error final de
`send_email` como HTTP 503 después de agotar sus reintentos. RF-08 exige
mantener HTTP 202 con el mensaje genérico y emitir una alerta interna para el
administrador.

## Paso 0 — base de datos y RBAC

No se requiere migración ni DML. La alerta utiliza:

- El evento `SOLICITUD_RECUPERACION` ya confirmado para la solicitud.
- El canal interno existente en `modulo1.notificaciones`.
- Los usuarios activos con permiso de lectura sobre el recurso de auditoría
  `(recurso=6, acción=2)`, resueltos dinámicamente mediante RBAC.

No se fija un `id_rol` y no se modifica `sgpmp_dev`.

## Comportamiento corregido

1. El token y el evento de recuperación se confirman antes del envío SMTP.
2. Si SMTP falla, el error se registra en logs sin incluir el token.
3. Se crea una notificación interna para cada destinatario resuelto por RBAC.
4. La API conserva HTTP 202 y el mensaje genérico.
5. Si falla la persistencia de la alerta, solo se revierte esa segunda
   transacción; el token permanece confirmado y la respuesta continúa siendo
   genérica.

La misma protección aplica cuando el correo solicitado pertenece a una cuenta
pendiente y el flujo rota un token de activación.

## Validación

- Reproducción previa: `TC-M01-044` fallaba en sus 2 casos con HTTP 503.
- QA original después de la corrección: `2 passed`.
- Pruebas unitarias nuevas: 6 casos para fallo SMTP, alerta por RBAC, cuenta
  pendiente, fallo de la alerta, ausencia de destinatarios y fallo de BD.
- Flujo HTTP/PostgreSQL enfocado: `4 passed`.
- Suite completa sin integración: `405 passed`.
- Integración compatible con la base temporal: `71 passed`.

La ejecución de toda la integración también expuso 17 fallos anteriores y no
relacionados: integridad RF-10 por normalización horaria y casos de Módulo 9 con
RBAC/datos incompatibles con la copia local. Los archivos incompatibles se
excluyeron de la segunda ejecución para obtener el resultado limpio indicado.

Las pruebas de integración se ejecutaron sobre `test_rf08_smtp_044`, clonada de
la base local `test-captcha-dev-leandro`, con una transacción exterior revertida
por caso. La base temporal se elimina al terminar la validación.
