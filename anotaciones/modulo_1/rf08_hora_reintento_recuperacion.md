# RF-08 — hora real de reintento del límite de recuperación

## Incidente

`POST /contrasena/recuperar` y `POST /usuarios/reenviar-token` informaban
como próxima hora de intento un cálculo que siempre volvía a coincidir con
`ahora`, en vez de la hora real en que se libera el cupo.

## Qué ya estaba resuelto en `dev`

El flujo de **recuperación de contraseña** (`SolicitarRecuperacionUseCase`) ya
fue corregido de forma independiente y más completa en `dev`
(`34b5fcf`, `38ac799`, `2fe2d66`, mergeados vía PR #132) antes de que este
fix llegara: el rate limiting migró de `EventoRepository` a
`IntentoAnonimoRepository` (tabla propia sin `id_usuario`, para poder
contabilizar también correos inexistentes — INC-M01-09-043), el error pasó de
`BusinessRuleError` (422) a `TooManyRequestsError` (429), y se agregó alerta
por fallo SMTP (INC-M01-14-044). Esa versión ya calcula la hora real de
reintento con `intentos_anonimos_repo.obtener_fecha_mas_antigua_por_ip`.

Este PR se había creado desde un punto de `dev` anterior a esos commits, así
que su versión de `SolicitarRecuperacionUseCase` quedó descartada al resolver
el conflicto — mergearla habría revertido el fix de correos inexistentes y el
código 429.

## Qué seguía roto y sí se corrige aquí

El **reenvío de activación** (`ReenviarTokenUseCase`) nunca fue tocado por el
fix paralelo y seguía calculando `ahora + 1 hora` (siempre una hora en el
futuro, nunca la hora real de desbloqueo). Se aplicó la misma regla que ya
usa `intentos_anonimos_repo`, pero sobre `EventoRepository` porque este flujo
sigue contando sobre `modulo1.eventos` (tipo 7):

- El puerto `EventoRepository` expone
  `obtener_primera_solicitud_recuperacion_por_ip`, que retorna en UTC la
  solicitud tipo 7 más antigua de la IP dentro de la ventana vigente.
- `ReenviarTokenUseCase` suma una hora a esa fecha en vez de a `ahora`.

No se requirió DDL, DML ni permisos nuevos — se reutilizan las mismas
columnas de `modulo1.eventos` que ya usaba el contador existente.

## Cobertura

- `tests/identity_access/test_reenvio_activacion.py::test_rate_limit_por_ip`
  cubre el cálculo para el reenvío de activación.
- El caso de recuperación de contraseña ya está cubierto en `dev` por
  `tests/integration/test_recuperacion_contrasena.py::test_recuperacion_excede_limite_responde_429_con_hora_real_de_reintento`
  y `test_recuperacion_aplica_limite_a_correo_inexistente`.
- Se eliminaron los tests que este PR agregaba para `SolicitarRecuperacionUseCase`
  (`test_rf08_hora_reintento_recuperacion_unit.py` y
  `tests/integration/test_rf08_hora_reintento_recuperacion.py`): asumían el
  mecanismo viejo (422 vía `eventos_repo`) y ya no aplican sobre el código
  actual de `dev`.
