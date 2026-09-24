# TC-M09-G103 (#311) — Auditoría de cambio de idioma personal

Fecha: 2026-09-18

## Síntoma reportado

`PATCH /configuracion/personalizacion/idioma` persistía correctamente el
cambio (es-CO → en-US) y `GET /configuracion/personalizacion/idioma` lo
confirmaba, pero no existía ningún registro de auditoría consultable con
usuario/sesión, fecha, valor anterior y nuevo. `GET /auditoria/` respondía
200 pero sin ningún evento asociado; un endpoint dedicado
`GET /configuracion/personalizacion/idioma/auditoria` no existe (404).

## Causa

`GuardarIdiomaPersonalUseCase` nunca llamaba a `EventoRepository.registrar()`
— gap real, no falso positivo. El mecanismo de auditoría de módulo 1
(`modulo1.eventos`, expuesto en `GET /auditoria/`) ya cubre "todos los
módulos del sistema" por diseño (comentario de la propia tabla) y ya lo usan
otros cambios de configuración personal (ej. `ACTUALIZACION_PERFIL`, tipo 9)
— solo faltaba el tipo de evento y la llamada.

## Decisión: reusar `modulo1.eventos`, no crear tabla propia de módulo 9

A diferencia de `auditorias_plantillas` (RF-30/31/32, tabla propia de
módulo 9 desde antes de esta tarea), la preferencia de idioma es una
configuración del propio usuario, con RBAC bajo `modulo1.recursos` (26/27) —
más cerca de "perfil" que de un agregado de negocio de módulo 9. Se reusa el
mecanismo ya construido en vez de levantar infraestructura nueva.

## Fix aplicado

- Migración Alembic `5c844a858bde` (mismo patrón que `d9a47c30e5b1`/`a3b7c1d95e40`):
  `modulo1.tipos_eventos` id=27, `CAMBIO_IDIOMA_PERSONAL`.
- `evento_categoria.py`: `27 → EventoCategoria.MODIFICACION` (mismo criterio
  que `ACTUALIZACION_PERFIL`).
- `GuardarIdiomaPersonalUseCase`: recibe `EventoRepository`, registra el
  evento (`locale_anterior`, `locale_nuevo` en el detalle) antes del `commit()`.
- Router: inyecta `SqlAlchemyEventoRepository(db)`.

## Fuera de alcance (anotado, no corregido)

`GuardarIdiomaGlobalUseCase` (idioma por defecto del sistema, solo Admin)
tiene el mismo gap — nunca audita. El issue reportado (TC-M09-197) es
específicamente sobre idioma **personal**; no se toca el global sin que se
pida aparte.

## Pruebas

- `tests/configuration/test_rf29_preferencia_idioma.py`: 20/20 verdes (fakes
  actualizados con `eventos_repo`).
- `tests/integration/test_tc_m09_g103_auditoria_idioma.py` (nuevo): PATCH
  idioma personal + `GET /auditoria/?tipo_evento=27` end-to-end contra
  Postgres real — verde.
- `tests/identity_access/test_rf10_categorias_eventos.py`: catálogo de
  categorías/tipos actualizado (27 agregado a MODIFICACION y al total) — 13/13
  verdes.
- Suite completa: sin regresiones nuevas (los 10 fallos preexistentes en
  `tests/` no están relacionados — confirmado antes de empezar esta rama).
