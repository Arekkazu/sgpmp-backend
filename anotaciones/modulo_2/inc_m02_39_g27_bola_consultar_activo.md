# INC-M02-39-G27 — GET /activos-biologicos/{id_activo} no filtraba por finca (BOLA, OWASP API1)

**RF:** RF-36 (Gestión Poblacional de Activos Biológicos).
**Endpoint:** `GET /activos-biologicos/{id_activo}`.
**Categoría:** OWASP API1:2023 (Broken Object Level Authorization).

## Qué reportó QA/seguridad

`TC-M02-G27` (`TC-M02-058`): un Productor (`m2m.nuevo@ejemplo.com`, Finca 1)
consultaba el lote `8` (Finca 2, Tilapia Roja) y recibía `HTTP 200 OK` con
toda la información del lote ajeno — especie, `cantidad_actual`,
`peso_promedio`, `biomasa_total`, `densidad`, `costo_adquisicion` y
`soporte_documental` — en vez del `403`/`404` esperado. El propio informe de
QA señalaba como hipótesis que el filtro de alcance de finca (RF-25) "no se
encuentra desplegado en la versión activa del contenedor de TEST" o que el
repository no restringía por finca.

## Investigación (Paso 0)

Se verificó el estado actual de `dev` (no de `sgpmp_test`, el entorno donde
corrió QA) antes de tocar nada:

- `activo_biologico_router.py` — el endpoint `consultar_activo` ya calcula
  `ids_fincas_permitidas=_ids_fincas_alcance(db, usuario_actual)` y se lo pasa
  al use case.
- `ConsultarActivoUseCase.execute()` ya recibe `ids_fincas_permitidas` y lo
  propaga a `repo.obtener_por_id(id_activo, ids_fincas_permitidas=...)`.
- `SqlAlchemyActivoBiologicoRepository.obtener_por_id()` ya verifica
  `_pertenece_a_fincas(orm.id_infraestructura, ids_fincas_permitidas)` y
  devuelve `None` (no un error que distinga "existe pero no es tuyo") cuando
  la infraestructura del activo no pertenece a ninguna finca del alcance del
  usuario; el use case traduce ese `None` a `404 ACTIVO_NO_ENCONTRADO`.

Este filtro fue introducido por el commit `6ca29b5a` ("feat(rf25): restringir
activos biológicos a la finca del usuario"), fechado **2026-09-08** — el mismo
día en que QA ejecutó `TC-M02-058` contra `sgpmp_test`. La hipótesis del
propio informe de QA es la causa real: el entorno de TEST corría una revisión
anterior a ese commit; `dev` ya tiene el fix.

## Conclusión

**No se requiere cambio de código.** El comportamiento reportado como
vulnerable ya no existe en `dev`. Este INC se documenta y se agrega cobertura
de regresión para dejar constancia explícita de este endpoint específico (el
commit `6ca29b5a` corrigió ocho endpoints de lectura a la vez sin un test
dedicado por endpoint).

## Pruebas

`tests/biological_assets/test_consultar_activo_use_case_alcance_finca.py` —
3 casos nuevos, fakes escritos a mano, sin BD:

- Lote de otra finca (el caso reportado, lote 8 / Finca 2, usuario de Finca 1)
  → `404 ACTIVO_NO_ENCONTRADO`, no `200`.
- Lote de la propia finca → se consulta normalmente.
- Alcance global (`ids_fincas_permitidas=None`, ej. Administrador) → no
  filtra.

Suite completa sin regresiones: 664 passed (661 previos + 3 nuevos), mismos 2
fallos preexistentes en `test_registrar_transferencia_use_case.py` (no
relacionados, confirmados fallando igual en `origin/dev` sin este cambio).

## Fuera de alcance

Ninguna acción sobre el entorno `sgpmp_test` — es responsabilidad de
despliegue/DevOps actualizar ese contenedor a una revisión de `dev` posterior
a `6ca29b5a`, no de este repositorio.
