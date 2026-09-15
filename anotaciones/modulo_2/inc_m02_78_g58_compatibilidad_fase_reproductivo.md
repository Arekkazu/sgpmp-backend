# INC-M02-78-G58 — No existe validación de compatibilidad de fase en eventos reproductivos

**RF:** RF-42 — Registrar eventos reproductivos (CU08).
**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/reproductivo`.

## Qué reportó QA

`RegistrarEventoReproductivoUseCase` no recibe ningún repositorio/puerto de
fases en su constructor (a diferencia de `RegistrarEventoProductivoUseCase`,
que sí valida E-02/E-04). Un evento reproductivo se acepta sin importar la
fase (o ausencia de fase) del activo — RF-42 no tiene ninguna regla de
compatibilidad de fase implementada, ni en Python ni en trigger de BD.

## Texto exacto del RF-42 (aportado para este fix)

- **Precondición:** "El activo debe estar en una fase productiva compatible
  con reproducción."
- **Flujo alterno:** "Fase productiva incompatible — HTTP 409 Conflict.
  Mensaje: 'La fase productiva del activo no permite registrar este tipo de
  evento.'"

## Investigación del criterio de compatibilidad (Paso 0)

El RF no define qué hace a una fase "compatible con reproducción", y no hay
ninguna columna en el esquema que distinga tipos de fase. Antes de
implementar cualquier cosa se verificó contra datos reales de `sgpmp_dev`
(vía MCP de postgres) para no inventar una regla:

```sql
SELECT nombre, id_especie FROM modulo9.ciclos_biologicos ORDER BY id_especie;
```

Las 13 fases configuradas, para las 5 especies del sistema (tilapia, trucha,
camarón, cachama, mojarra), son etapas de crecimiento secuenciales: `Fase
larval`, `Fase juvenil`, `Fase engorde` — ninguna se llama ni se aproxima a
"reproductiva". Y las 19 gestiones de fase reales en `modulo2.gestiones_fases`
están **todas** en la fase "engorde" de su especie.

**Conclusión:** si "compatible con reproducción" exigiera un tipo de fase
específico, el RF-42 sería inaplicable al 100% de los datos reales — no
existe tal distinción en el modelo. La única lectura consistente con los
datos es que la compatibilidad exigida es la misma que la **E-02 de RF-43**
(`RegistrarEventoProductivoUseCase`): debe existir una **gestión de fase
activa**, sin importar cuál. `ActivoBiologicoRepository.obtener_fase_activa(id_activo)`
ya existe y ya lo usa RF-43 — `RegistrarEventoReproductivoUseCase` nunca lo
llamaba, pese a recibir `activo_repo` (el mismo puerto) en su constructor.
Por eso no hizo falta agregar ninguna dependencia nueva.

## Fix

`RegistrarEventoReproductivoUseCase._execute()`: después de
`validar_estado_permite_eventos(activo)`, se agrega:

```python
if self.activo_repo.obtener_fase_activa(id_activo) is None:
    raise ConflictError(
        code='FASE_NO_COMPATIBLE_REPRODUCCION',
        message='La fase productiva del activo no permite registrar este tipo de evento.',
    )
```

Se ejecuta antes que cualquier validación de categoría/secuencia — bloquea
incluso `nacimiento` en un activo POBLACIONAL sin fase activa. Mensaje
literal del RF. `409 Conflict` agregado a las respuestas documentadas del
endpoint en el router (antes solo listaba 400/401/403/404/422, pese a que
`ESTADO_NO_PERMITE_EVENTOS` ya usaba 409 también — omisión preexistente en
la documentación de OpenAPI, no introducida por este fix).

## Hallazgo relacionado, fuera de alcance de este fix

RF-42 dice explícitamente "El activo debe encontrarse en estado ACTIVO" (no
EN_TRATAMIENTO ni AISLADO), pero `validar_estado_permite_eventos` (compartida
con otros tipos de evento) permite los tres estados. Esta discrepancia ya
existe en `dev` independientemente de este INC, no es introducida ni
corregida aquí — el reporte de este issue es específicamente sobre fase, no
sobre estado.

## Pruebas

`tests/biological_assets/test_registrar_evento_reproductivo_use_case.py` —
3 casos nuevos (más el fake `ActivoRepoFake.obtener_fase_activa`, que por
defecto simula una fase activa para no romper los 10 tests existentes):

- Activo sin fase activa → `409 FASE_NO_COMPATIBLE_REPRODUCCION`, para
  cualquier categoría.
- La validación bloquea incluso `nacimiento` en un POBLACIONAL sin fase
  activa (corre antes que FA-04 y las reglas de secuencia).
- Con fase activa (comportamiento por defecto del fake), el camino feliz
  existente sigue funcionando sin cambios — no regresión.

Suite completa sin regresiones: 639 passed (636 previos + 3 nuevos), mismos
2 fallos preexistentes en `test_registrar_transferencia_use_case.py` (no
relacionados, confirmados fallando igual en `origin/dev` sin este cambio).
