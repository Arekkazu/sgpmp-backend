# INC-M02-77-G56 — id_padre de otra finca se acepta sin validación de alcance (BOLA, OWASP API1)

**RF:** RF-42 — Registrar eventos reproductivos (CU08).
**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/reproductivo`.
**Categoría:** OWASP API1:2023 (Broken Object Level Authorization).

## Qué reportó QA/seguridad

`POST .../eventos/reproductivo` acepta un `id_padre` perteneciente a un
activo de una finca completamente distinta, sin ninguna validación.
`RegistrarEventoReproductivoUseCase` solo verificaba que el padre existiera y
estuviera en estado `ACTIVO` (FA-05); nunca comparaba
`id_infraestructura`/finca contra el activo objetivo ni contra el usuario
solicitante. El fix de alcance por finca de RF-25 (commit `6ca29b5`) no cubrió
esta ruta de escritura.

## Causa raíz (confirmada, y más amplia de lo reportado)

`6ca29b5` (RF-25) solo tocó **endpoints de lectura** (`consultar_*`,
`listar_activos`, `historial`, `ficha_integral`, `indicadores`, `datos
consolidados`, `consultar_asociacion`) — nunca los `registrar_evento_*` de
escritura. `INC-M02-71-G48` ya había detectado y corregido el mismo patrón
para `RegistrarEventoCrecimientoUseCase`, y su propia sección "Hallazgo
adicional" **nombra explícitamente** `registrar_evento_reproductivo_use_case.py`
como uno de los archivos con el mismo gap, deliberadamente diferido en ese
momento por exceder el alcance de ese issue.

Al investigar, el gap resultó más amplio que solo `id_padre`:

1. **El activo objetivo tampoco estaba escapado**: `self.activo_repo.obtener_por_id(id_activo)`
   se llamaba sin `ids_fincas_permitidas` — ni el propio router calculaba el
   alcance del usuario para este endpoint. Un usuario podía registrar un
   evento reproductivo sobre un activo de una finca completamente ajena.
2. **`id_padre`** (el caso reportado): se validaba existencia y estado
   `ACTIVO`, pero nunca finca.
3. **`id_madre`**: no tenía absolutamente ninguna validación (ni existencia,
   ni estado, ni finca) — es un campo opcional sin requisito de categoría
   como `id_padre`, así que el flujo lo guardaba directo en la entidad sin
   pasar por ninguna verificación.

## Fix

`RegistrarEventoReproductivoUseCase`:

- `execute()`/`_execute()` ganan el parámetro `ids_fincas_permitidas: list[int]
  | None = None`, propagado a `obtener_por_id(id_activo, ...)` para el activo
  objetivo — mismo patrón que `INC-M02-71-G48` estableció para crecimiento.
- Nuevo método `_validar_activo_relacionado(id_relacionado, activo_objetivo, rol)`,
  usado tanto para `id_padre` (cuando la categoría lo requiere) como para
  `id_madre` (cuando se envía, sin importar la categoría): valida existencia,
  estado `ACTIVO`, y que la infraestructura del relacionado pertenezca a la
  **misma finca** que la del activo objetivo (vía `InfraestructuraConsultaPort`,
  ya usado por `AsociarSensorActivoUseCase` para la misma comparación).
- **Decisión de diseño**: "existe pero es de otra finca" responde con el
  mismo código (`ACTIVO_RELACIONADO_NO_ENCONTRADO`, 404) que "no existe", en
  vez de un `409`/`403` que distinguiría los dos casos. Confirmar que un
  recurso existe fuera del alcance de finca del solicitante ya es una fuga de
  información en un escenario BOLA — mismo principio que ya aplica
  `ActivoBiologicoRepository.obtener_por_id(ids_fincas_permitidas=...)`, que
  devuelve `None` en ambos casos sin distinguirlos.
- Nueva dependencia `infra_port: InfraestructuraConsultaPort` en el
  constructor (inyectada en el router con `InfraestructuraM09Adapter`, ya
  usada en otros use cases del módulo).

## Fuera de alcance (documentado, no nuevo)

El resto de use cases de escritura listados en el "Hallazgo adicional" de
`INC-M02-71-G48` que aún no pasan `ids_fincas_permitidas`
(`asociar_sensor_activo_use_case.py`, `cambiar_fase_use_case.py`,
`registrar_evento_sanitario_use_case.py`, `registrar_evento_productivo_use_case.py`,
`cambiar_estado_use_case.py`, `cerrar_ciclo_use_case.py`,
`actualizar_activo_individual_use_case.py`) **no se tocan en este fix** — el
reporte de este INC es específicamente sobre `id_padre` en eventos
reproductivos. Siguen siendo la misma clase de gap, ya documentada; requieren
su propio issue si el equipo decide auditarlos todos de una vez.

## Pruebas

`tests/biological_assets/test_registrar_evento_reproductivo_use_case.py` —
6 casos nuevos (además de actualizar los 10 existentes para inyectar el
`infra_port` fake que ahora requiere el constructor):

- `id_padre` de otra finca → `404 ACTIVO_RELACIONADO_NO_ENCONTRADO` (el caso
  reportado).
- `id_padre` inexistente / inactivo → siguen rechazándose igual que antes
  (no regresión).
- `id_madre` de otra finca → rechazado (antes no se validaba en absoluto).
- `id_madre` en la misma finca → aceptado, se persiste correctamente.
- Activo objetivo fuera del alcance de finca del usuario → `404
  ACTIVO_NO_ENCONTRADO` (el gap más amplio encontrado durante la
  investigación).

Suite completa sin regresiones: 642 passed (636 previos + 6 nuevos), mismos 2
fallos preexistentes en `test_registrar_transferencia_use_case.py` (no
relacionados, confirmados fallando igual en `origin/dev` sin este cambio).
