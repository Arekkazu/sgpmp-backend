# RF-14 — Plantillas de correo y casos de notificación

Fecha: 2026-10-10 · Rama `feature/correos-plantillas-notificaciones` (apilada sobre `feature/admin-alcance-global`, PR #555)

## Casos de notificación (verificados contra el código y `sgpmp_dev`)

RF-14 exige notificar estos eventos por correo y por bandeja interna, con **tipo de evento,
mensaje y fecha y hora**:

| Evento RF-14 | Dónde se dispara | Tipo | Antes | Ahora |
|---|---|---|---|---|
| Registro exitoso | `crear_usuario_use_case` | 1 | Correo de activación propio | Rediseñado |
| (Activación) | `activar_cuenta_use_case` | 2 | `<p>` sin fecha | Plantilla por defecto |
| Inicio de sesión exitoso | `login_use_case` (en segundo plano) | 3 | `<p>` sin fecha | Plantilla + "¿no fuiste tú?" |
| Intento de inicio de sesión fallido | `login_use_case` | 4 | **Solo al 5º intento** (el del bloqueo) | Cada intento; el anti-spam deja 1 cada 5 min |
| Bloqueo de cuenta (por intentos) | `login_use_case` | 4 | Mismo aviso genérico del intento fallido | Aviso propio "Cuenta bloqueada" con la hora de desbloqueo, sin anti-spam |
| Cambio de contraseña | `cambiar_contrasena_use_case` | 6 | `<p>` sin fecha | Plantilla |
| Solicitud de recuperación | `correo_recuperacion_background_adapter` | 7 | Correo propio | Rediseñado |
| Restablecimiento de contraseña | `restablecer_contrasena_use_case` | 8 | `<p>` sin fecha | Plantilla |
| Actualización de perfil | `editar_perfil_use_case` | 9 | **No salía si la hacía un admin** | Sale siempre |
| Bloqueo/desactivación por admin | `gestionar_cuenta_use_case` | 10 | **No salía en TEST (RLS)**; texto genérico | Sale; dice si fue reactivada, desactivada, bloqueada o eliminada |
| (Login SSO AgroFusion) | `sso_login_use_case` | 20 | "Notificación" genérica | Mensaje propio |

Fuera de RF-14: M05 envía los avisos de inicio y fin del período de retiro (RF-76); ahora
también usan la plantilla común.

## Por qué no salían

1. **Edición de perfil por un admin.** El evento se registraba con el id del admin, pero
   `NotificacionService` busca el evento por el id del usuario notificado. No lo encontraba
   y descartaba el aviso en silencio. Es el mismo bug que ya se había corregido en
   `gestionar_cuenta`. Ahora el evento se registra bajo el usuario editado, con
   `id_usuario_responsable` en `detalle`.
2. **RLS en notificaciones de un admin a otro usuario.** `pol_notificaciones_insert` deja
   insertar a cualquiera, pero el repositorio hace `INSERT ... RETURNING`, que exige *ver* la
   fila (`pol_notificaciones_select`: dueño o usuario de servicio). El `UPDATE` del estado
   tiene la misma restricción. Con la app como `sgpmp_app`, como está TEST desde el
   2026-10-09, el aviso de cambio de estado y el de edición administrativa fallaban con
   `new row violates row-level security policy`.
   - En local no se veía porque la app se conecta como `dba`, que se salta RLS.
   - Los flujos anónimos (registro, activación, restablecer) no fallan: los repositorios
     declaran como identidad al propio usuario.
   - Arreglo: estos flujos notifican con `NotificacionSesionBackgroundAdapter`, el mismo que
     usa el login. Corre como el usuario de servicio (D1) y saca el SMTP del request.
     Sin migración.
3. **Intento fallido.** Solo se notificaba al llegar al bloqueo. RF-14 lo pide para cada
   intento. Como el bloqueo comparte tipo con el intento (4), su aviso pasa sin anti-spam
   en ambos canales (`aplicar_anti_spam_email/interno=False`); si no, lo descartaba la
   ventana que abrió el primer intento.

## Plantilla común (`src/shared/plantilla_correo.py`)

- La marca es **SIGAB** (el nombre que muestra el frontend), no "SGPMP". Se cambiaron
  también los asuntos.
- Colores y tipografía del design system del frontend (`tokens.css`): verde de marca
  `#226a28`, Plus Jakarta Sans con fuentes del sistema como respaldo.
- La **constancia del evento** es la pieza central: Evento / Fecha y hora (hora de
  Colombia, UTC-5) / detalles, con una barra de color según el tono (`info`, `atencion`,
  `critico`). Cubre el contenido mínimo de RF-14.
- Compatible con clientes de correo: tablas y estilos en línea, sin imágenes (se lee con
  las imágenes bloqueadas), botón "a prueba de balas" con el enlace también en texto, y
  condicional `mso` para Outlook.
- Adaptable: fluida hasta 560 px; en móvil, el botón ocupa todo el ancho y la constancia
  se apila. Modo oscuro para los clientes que respetan `prefers-color-scheme`.
- **Seguridad:** todo texto se escapa con `html.escape`. Antes, un nombre como
  `<a href=...>` se inyectaba como HTML en el correo.

## Verificación

- Capturas en Chrome headless de escritorio, móvil (375 px) y modo oscuro.
- Unitarias: 1371 pasan (el único fallo, `test_ingreso_fecha_futura_lanza_validation_error`,
  es previo y depende de la fecha). Nuevas en `tests/identity_access/test_rf14_casos_notificacion.py`.
- Integración completa con `TEST_ROL_APP=sgpmp_app` (RLS real) contra la rama base:
  0 fallos nuevos (16 contra 16, de entorno). Nueva:
  `test_edicion_administrativa_de_perfil_notifica_al_usuario_editado`. Sin el arreglo falla
  primero porque no hay evento y luego por RLS; con el arreglo pasa.

## Pendiente / no incluido

- Parte de texto plano (`multipart/alternative` con `text/plain`): mejora la entrega en
  algunos filtros de spam. Agregarlo si los correos empiezan a caer en spam.
- `send_email` sigue reintentando 3 veces, aunque RF-14 dice "sin reintentos" (gap ⚠️ ya
  documentado en `gaps_flujo_alterno_modulo1.md`). No se tocó.
