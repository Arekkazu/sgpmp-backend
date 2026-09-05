# RF-08 — hora real de reintento del límite de recuperación

## Incidente

`POST /contrasena/recuperar` informaba como próxima hora de intento el mismo
instante en que rechazaba la solicitud. El cálculo sumaba una hora al inicio de
la ventana (`ahora - 1 hora`), por lo que el resultado siempre volvía a ser
`ahora` y no indicaba cuándo se liberaba realmente el cupo.

El flujo de reenvío de activación compartía el tipo de evento y la ventana de
rate limiting, pero informaba `ahora + 1 hora`; ese valor también podía exceder
la espera real. Se corrigieron ambos para mantener un único criterio de negocio.

## Paso 0 — base de datos y RBAC

No se requiere DDL, DML ni un permiso nuevo. La tabla `modulo1.eventos` ya
contiene las tres fuentes necesarias:

- `fecha_evento`, para encontrar el inicio de la ventana vigente;
- `tipo_evento = 7`, que identifica las solicitudes contabilizadas;
- `detalle->>'ip'`, usado por el contador existente para aislar la conexión.

La base remota `sgpmp_dev` se considera de consulta y no recibió cambios ni
ejecuciones destructivas. La validación con escritura se realizó sobre una base
local temporal cuyo nombre contiene `test`.

## Corrección

- El puerto `EventoRepository` expone la fecha de la primera solicitud vigente.
- `SqlAlchemyEventoRepository` obtiene `MIN(eventos.fecha_evento)` usando los
  mismos filtros que el contador y normaliza el timestamp a UTC al cruzar la
  frontera ORM hacia el dominio.
- Los casos de uso suman una hora a esa solicitud. Si un adaptador devolviera
  un conteo limitado sin una fecha asociada, se usa `ahora + 1 hora` como
  fallback futuro para evitar volver a informar una hora vencida.
- Una IP distinta y un evento anterior al inicio de la ventana no participan en
  el cálculo.

## Evidencia de QA recibida

Los artefactos `TC-M01-049` corresponden a rendimiento, no al defecto de la
hora. La prueba aislada de QA continúa pasando después de esta corrección: 10
repeticiones, promedio de 1.33 ms, mínimo de 1.06 ms y máximo de 1.81 ms.

El reporte Newman recibido medía el endpoint completo y registró 3518 ms por el
envío síncrono de correo. Ese hallazgo corresponde al defecto de correo
documentado por QA y no es causado por el cálculo del rate limit.

## Cobertura agregada

- Reproducción determinista del mensaje anterior (`ahora`) y comprobación de la
  nueva expiración (`primera solicitud + 1 hora`).
- Prueba HTTP/BD con tres eventos reales, otra IP y un evento fuera de ventana.
- Normalización de la zona horaria devuelta por PostgreSQL.
- Mismo cálculo para el reenvío de activación.
- Confirmación de que al bloquear no se consulta al usuario, no se genera token,
  no se envía correo y no se confirma ninguna transacción.

