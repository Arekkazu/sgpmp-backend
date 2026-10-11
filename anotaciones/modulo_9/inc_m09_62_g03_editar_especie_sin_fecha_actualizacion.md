# INC-M09-62-G03 (Arekkazu/SGPMP-FRONT-END-PWA#231) — RF-15: 412 en la primera edición de una especie

Rama `fix/rf15-editar-especie-sin-fecha-actualizacion`. Sin migraciones.

## Síntoma

Editar una especie recién creada o que nunca se modificó (QA: Equino #42, Bovino #39
en TEST) respondía `412 CONFLICTO_CONCURRENCIA` — "La especie fue modificada por otro
usuario. Recargue los datos e intente de nuevo." Las especies que ya tenían una
edición previa sí se podían editar.

## Causa

- `RegistrarEspecieUseCase` no llena `fecha_actualizacion`: toda especie nueva queda
  con `NULL` hasta su primera edición.
- `EditarEspecieDTO.fecha_actualizacion` era un `datetime` obligatorio, así que un
  `null` respondía `400 VAL_ENTRADA`.
- Para esquivar el 400, el frontend enviaba la hora del navegador. El caso de uso
  compara `NULL` (BD) contra esa hora, no coinciden y responde `412`.

El caso de uso ya contemplaba `None` en ambos lados (`elif ts_actual != ts_dto`): el
bloqueo estaba solo en el DTO. El test de integración
`test_editar_especie_activa_responde_200` lo documentaba como "un problema aparte" y
lo esquivaba fijando la fecha por SQL.

## Corrección

`EditarEspecieDTO.fecha_actualizacion: Optional[datetime] = None`, igual que en
`EditarCicloDTO`, `EditarMetricaDTO`, `EditarPatologiaDTO` y
`EditarInfraestructuraDTO`. La concurrencia optimista no se debilita:

| BD | Enviado | Resultado |
|---|---|---|
| `NULL` | `null` / omitido | `200` (primera edición) |
| `NULL` | una fecha (p. ej. la del cliente) | `412` |
| fecha | la misma fecha | `200` |
| fecha | `null` / omitido / otra fecha | `412` |

## Contrato para frontend

`PATCH /configuracion/especies/{id}` acepta `"fecha_actualizacion": null`. El cliente
envía el valor tal cual vino del GET. El frontend lo corrige en la rama
`fix/m02-segunda-evaluacion` (también limpia el error al cerrar el modal, la otra
mitad del reporte); debe desplegarse después de este backend: sin él, `null`
responde `400`.

## Verificación

- 4 tests nuevos en `tests/configuration/test_rf15_editar_especie_sin_fecha_actualizacion.py`
  (DTO acepta `null`; primera edición con `null` → OK; `null` sobre especie editada → 412;
  hora del cliente sobre especie sin editar → 412).
- Base local `sgpmp_dev`: 3 de las 9 especies, activas, tienen `fecha_actualizacion`
  `NULL` — la condición afecta a toda especie registrada y no editada.
