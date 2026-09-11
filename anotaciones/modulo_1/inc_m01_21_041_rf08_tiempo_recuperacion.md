# INC-M01-21-041 — anti-enumeración temporal en recuperación

## Incumplimiento

`POST /contrasena/recuperar` entregaba el mismo estado y mensaje para un
correo existente y uno inexistente, pero el envío SMTP del caso existente se
ejecutaba antes de completar la petición. Los reintentos del servicio de correo
añadían varios segundos y permitían inferir si el correo estaba registrado.

La evidencia `TC-M01-041` midió 3124 ms para el correo existente y 134 ms para
el inexistente. La segunda petición recibió 422 porque la IP ya había agotado
el límite; por eso la regresión se valida también con eventos e IP limpios.

## Corrección

- El caso de uso conserva dentro de la petición la consulta, generación segura
  del token, almacenamiento de su hash, auditoría y `commit`.
- Después del `commit`, un puerto de dominio agenda el correo mediante
  `BackgroundTasks`; la tarea usa una sesión de base de datos independiente.
- El envío usa la plantilla de recuperación o activación según el estado de la
  cuenta y mantiene el mensaje genérico de RF-08.
- Los correos con tokens omiten únicamente el anti-spam del canal email porque
  cada token nuevo invalida al anterior. La notificación interna conserva su
  ventana anti-spam.
- Si falla la persistencia del token o del evento, se ejecuta `rollback` y no se
  agenda ningún correo.

No se requieren cambios de esquema, migraciones ni RBAC para esta incidencia.

## Validación

- Reproducción determinista con SMTP de 450 ms: diferencia previa de 456,5 ms.
- Validación HTTP real con Uvicorn y SMTP de 600 ms: 132,1 ms para el correo
  existente, 20,2 ms para el inexistente y 111,9 ms de diferencia; el envío
  seguía pendiente cuando el cliente recibió el 202.
- Pruebas unitarias de tiempo, encolado, cuenta pendiente, rollback y anti-spam.
- Prueba HTTP/BD con correo existente e inexistente: mismo 202, mismo cuerpo y
  diferencia menor de 300 ms.
- Suite no integrada: 419 pruebas aprobadas.
- Flujos integrados de identidad y acceso relacionados: 73 pruebas aprobadas
  sobre una base local temporal clonada de la referencia de desarrollo.
