# INC-M02-97-G95 (issue #244) — Datos consolidados se exponen ante inconsistencia jerárquica

**RF:** RF-50 · **CU:** CU12 · **Endpoint:** `GET /activos-biologicos/{id_activo}/datos-consolidados`

## Causa raíz

`ConsultarDatosConsolidadosUseCase.execute()` solo validaba que el activo existiera
(`activo_repo.obtener_por_id`) antes de delegar al repositorio de indicadores. La
consulta SQL de `obtener_datos_consolidados` hace `JOIN` contra
`modulo9.infraestructuras` sin filtrar por `es_activo`, así que un activo con una
asociación vigente (`fecha_fin IS NULL` en `modulo2.historial_infraestructura_activo`)
hacia una infraestructura ya inactivada seguía devolviendo `200` con el dataset
completo, sin ninguna señal de la inconsistencia.

Caso reportado por QA (TC-M02-310): activo 289 (`ACTIVO`) asociado vigente a la
infraestructura 49 (`es_activo = false`), con fase de gestión activa y cero cierres
registrados.

## Fix

- `HistorialInfraestructura` (entidad de dominio) gana el campo
  `es_activo_infraestructura: bool = True`, poblado en los tres puntos de construcción
  de `SqlAlchemyActivoBiologicoRepository` que ya hacían `JOIN` con
  `InfraestructuraModel` (`obtener_asociacion_activa`, `obtener_asociacion_en_fecha`,
  `obtener_historial_infraestructura`) — no se agregó ninguna consulta nueva.
- `ConsultarDatosConsolidadosUseCase.execute()` llama a
  `activo_repo.obtener_asociacion_activa(id_activo)` después de confirmar que el activo
  existe; si la asociación vigente apunta a una infraestructura inactiva, se rechaza con
  `ConflictError` → HTTP 409, código `INCONSISTENCIA_JERARQUICA`, antes de tocar el
  repositorio de indicadores (no se construye ni expone ningún dataset).
- Sin cambios de esquema de BD — la columna `es_activo` en `modulo9.infraestructuras`
  y la tabla `modulo2.historial_infraestructura_activo` ya existían.

## Alcance no cubierto (documentado, no bloqueante)

El issue también reporta una discrepancia documental entre la matriz de pruebas de QA
(`/activos-biologicos/{id}/datos-analiticos`) y el contrato OpenAPI real
(`/datos-consolidados`). Se documentó la aclaración en
`curls_m02_cu12_indicadores_datos.md`, pero actualizar la matriz de QA está fuera del
alcance de este repositorio.

## Pruebas

- `tests/biological_assets/test_consultar_datos_consolidados_use_case.py` (nuevo): 4
  casos — rechazo por infraestructura inactiva, éxito con infraestructura activa, éxito
  sin asociación vigente, 404 por activo inexistente.
- Suite completa del backend: 556 passed, 165 skipped, sin regresiones.

## Frontend

No requiere cambios — el defecto es de validación backend.
