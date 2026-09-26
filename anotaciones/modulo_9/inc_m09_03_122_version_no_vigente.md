# INC-M09-03-122 (#317) — Se permitía aplicar una versión superada de una plantilla

Fecha: 2026-09-18

## Síntoma reportado

`POST /configuracion/plantillas/{id_plantilla}/aplicar` aplicaba cualquier
`id_plantilla` válido sin comprobar si era la versión vigente (la de mayor
número) para su `template_name`. Una vez generada la v2 de una plantilla
(Flujo G), la v1 seguía pudiendo aplicarse exactamente igual que la vigente —
el versionado no cumplía su propósito de control de cambios.

## Causa

`AplicarPlantillaUseCase` cargaba la plantilla por id y validaba compatibilidad
de esquema y existencia/estado de la especie destino, pero nunca comparaba la
versión de la plantilla contra la última versión existente para ese
`template_name`.

## Fix

- `PlantillaRepository` (puerto + SQLAlchemy): nuevo método
  `obtener_ultima_version(template_name) -> Optional[Plantilla]`, con la misma
  normalización (`lower(trim(...))`) que `existe_nombre`, para no divergir del
  trigger `trg_fn_plantilla_version_incremental`.
- `AplicarPlantillaUseCase._ejecutar()`: tras cargar la plantilla, compara su
  `version` contra `obtener_ultima_version(...).version`. Si no coinciden,
  `BusinessRuleError(code="PLANTILLA_VERSION_NO_VIGENTE")` → **422**.

## Nota sobre el código HTTP (decisión propia, no está en el texto del RF)

El "Flujo alterno" de RF-32 no nombra este escenario exacto con un HTTP
específico — los casos que sí trae son "Incompatibilidad de esquema (Versión
Legacy)" (422) y "Conflicto de modificación concurrente" (409), ninguno es
literalmente "esto ya no es lo último". Elegí **422** por consistencia con el
otro caso de "esta plantilla no es apta para aplicar tal cual" (incompatibilidad
de esquema, también 422 en RF-32). Queda marcado explícitamente para que
Análisis/QA lo confirme o lo corrija si esperaban otro código.

## Hallazgo relacionado, fuera de alcance de esta ficha

Mientras se trabajaba en este mismo use case (`aplicar_plantilla_use_case.py`),
se encontró `anotaciones/modulo_9/gaps_flujo_alterno_modulo9.md` (documento
existente del usuario, no generado en esta sesión) que ya señala dos
inconsistencias de HTTP en el mismo archivo, no relacionadas con este issue:
- Incompatibilidad de esquema (legacy): el código usa `412` y el texto de
  RF-32 pide `422`.
- Conflicto de modificación concurrente: el código usa `412` y el texto de
  RF-32 pide `409`.

No se tocan en esta rama — son parte de un relevamiento más amplio del
usuario sobre el módulo completo, no de los 4 INC de plantillas de esta
tarea. Se deja anotado para que se decida aparte si se corrigen.

## Pruebas

`tests/integration/test_rf32_version_no_vigente.py`: crea v1, genera v2
(Flujo G), aplica v1 → `422 PLANTILLA_VERSION_NO_VIGENTE`; aplica v2 → `200`.
Suite completa de plantillas: 70/70 verdes contra `pruebas` local.
