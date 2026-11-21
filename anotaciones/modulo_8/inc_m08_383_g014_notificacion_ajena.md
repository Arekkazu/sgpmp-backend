# INC-M08-383-G014 · RF-105 — Notificación de otro usuario: 403 con el mensaje del RF

Incidencia [#1199](https://github.com/Arekkazu/sgpmp-backend/issues/1199) · TC-M08-G014, subcaso TC-M08-016. Rama basada en `origin/dev` `6cee5fc4`.

## Causa

`PATCH /notificaciones/{id}/leida`, `/atendida` y `/descartada` buscan la notificación con `obtener_interna(id, id_usuario)`, que filtra por el usuario. Además, la RLS de `modulo1.notificaciones` (`pol_notificaciones_select`) solo deja ver las propias. Por eso una notificación ajena llegaba como `None` y respondía igual que una inexistente: `404 NOTIFICACION_NO_ENCONTRADA`. El docstring del router lo documentaba («Ajena → 404»), en contra de RF-105 restricción 4 y CU03 FA3.

Nunca se modificó nada ajeno: eso ya estaba bien y no cambia.

## Decisión

Se aplica la primera opción del ticket: si la notificación existe y es de otro usuario, se responde **403 `NOTIFICACION_AJENA`** con «No tiene permisos para modificar notificaciones de otros usuarios.». Si no existe, sigue el 404.

- **Mensaje:** se tomó del ticket, que lo cita de CU03 FA3. La copia local de RF-105 restricción 4 («Solo el propio usuario puede marcar sus notificaciones…») no trae el texto literal, y la búsqueda en Drive tampoco lo encontró.
- **Cómo se sabe si existe:** el puerto `NotificacionRepository` tiene `existe_interna(id)`. La implementación pregunta dentro de `como_sistema` (el usuario de servicio actúa como Administrador, que la política SELECT deja ver) y devuelve solo sí o no. No trae el contenido. La identidad del usuario se restaura al salir.
- **Solo canal interno:** una notificación propia de otro canal (correo) sigue en 404, como antes.
- **Lo que revela:** que existe una notificación con ese id. Es lo que pide el RF, y el ticket lo reconoce como alternativa. Si Análisis prefiere no revelarlo, basta con ajustar la restricción 4 al 404 y revertir este cambio.

## Evidencia local

Se usó una BD efímera en `sgpmp-db` (PostgreSQL 18) con `alembic upgrade head`. A `sgpmp_app` se le dieron los GRANT que tiene en DEV, porque las migraciones no los crean.

- `tests/integration/test_inc_m08_383_g014_notificacion_ajena_integration.py`, como `sgpmp_app` con la identidad de un Productor:
  - La RLS le oculta la notificación de otro usuario y `existe_interna` la encuentra.
  - Leída, atendida y descartada responden 403 con el mensaje; un id inexistente responde 404.
  - La identidad vuelve a ser la del Productor después de la consulta como sistema.
  - La notificación sigue `NUEVA` y sin leer.
- `tests/identity_access/test_inc_m08_383_g014_notificacion_ajena.py`: 9 casos unitarios (ajena, inexistente y propia × leída, atendida y descartada).
- **Sin el arreglo**, las pruebas de la notificación ajena fallan con `NotFoundError`.
- Se actualizaron dos pruebas que fijaban el 404 para la ajena:
  - `tests/identity_access/test_rf14_notificaciones.py` (el fake ahora implementa `existe_interna`).
  - `tests/integration/test_rf14_notificaciones_integration.py`.
- `tests/identity_access` y las integraciones de notificaciones y M08: 287 pasan. La excepción es `test_escalamiento_auditoria_y_preferencias` (RF-105, `assert 1 == 4`), que ya fallaba antes de este cambio.

## Frontend

El interceptor de `http.ts` dispara `PERMISOS_POSIBLEMENTE_DESACTUALIZADOS` con cualquier 403. Quien lo escucha solo avisa si los permisos de verdad cambiaron, así que no cierra la sesión. La bandeja del frontend solo ofrece las propias, de modo que este 403 solo lo ve otro cliente de la API.

## Re-prueba

Repetir TC-M08-016:

- El Productor hace `PATCH /notificaciones/{id}/leida`, `/atendida` y `/descartada` sobre la notificación del Administrador y recibe **403** `NOTIFICACION_AJENA` con el mensaje del RF.
- La notificación sigue `NUEVA`.
- Un id inexistente sigue respondiendo `404 NOTIFICACION_NO_ENCONTRADA`, y sin token `401`.
