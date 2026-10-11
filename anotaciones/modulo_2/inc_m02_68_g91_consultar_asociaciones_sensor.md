# INC-M02-68-G91 — No existe endpoint para consultar asociaciones sensor↔activo

**RF:** RF-49 (CU11).

## Qué reportó QA

`GET /activos-biologicos/{id_activo}/sensores` responde `405 Method Not
Allowed`. El criterio de aceptación del RF-49 "el sistema refleja la
asociación en consultas posteriores" no se cumple: la asociación se persiste
correctamente en `modulo2.asociaciones_activos_sensores`, pero es invisible
para todos los consumidores externos (frontend, M03, M04, reportes).

## Investigación

El router (`activo_biologico_router.py`) solo declaraba `POST
/{id_activo}/sensores` (crear) y `PATCH /{id_activo}/sensores/{id_asociacion}`
(cambiar estado) — nunca un `GET`. `GET` sobre una ruta sin ese método
registrado es exactamente el `405` que reportó QA (FastAPI/Starlette
responden así, no `404`, cuando la ruta existe para otros métodos).

`api_reference_m02_activos_biologicos.md` documentaba (incorrectamente) que
"la lectura de asociaciones de sensor se expone desde el módulo
`configuration`" — se verificó que eso nunca se implementó
(`src/configuration/` no tiene ningún endpoint ni referencia a
`asociaciones_activos_sensores`). El permiso `R` sobre el recurso 30 ya
estaba sembrado para Productor y Veterinario (ver `cu11_gaps_bd_rf49.md`),
así que el gap era puramente de aplicación: RBAC listo, endpoint faltante.

## Fix

- **Puerto** (`AsociacionSensorActivoRepository`): nuevo método
  `listar_todas_por_activo(id_activo)` — historial completo sin filtrar por
  estado (el método existente, `listar_activas_por_activo`, ya servía para
  el caso `ACTIVA`).
- **Use case nuevo** `ConsultarAsociacionesSensorUseCase`
  (`application/use_cases/gestion/`): valida que el activo exista (404 si
  no), valida `tipo_consulta` (`ACTIVA` default | `HISTORIAL`, 400 si otro
  valor), delega al método del repo correspondiente, y registra el acceso en
  la bitácora RF-52 (`ASOCIACIONES_SENSOR_CONSULTADAS`, best-effort, no
  bloquea la respuesta si falla).
- **Endpoint nuevo** `GET /activos-biologicos/{id_activo}/sensores`, mismo
  recurso RBAC 30 con acción R (2) ya sembrada — sin DML de permisos nuevo.
  Sigue el mismo patrón `ACTIVA`/`HISTORIAL` que ya usa
  `GET /{id_activo}/infraestructura` (RF-34), para consistencia dentro del
  mismo router.
- **Schema nuevo** `ConsultaAsociacionesSensorResponse`: `id_activo_biologico,
  tipo_consulta, asociaciones: list[AsociacionSensorActivoResponse]` (reutiliza
  el schema de respuesta que ya usan `POST`/`PATCH`).

Se corrigió también la nota incorrecta en `api_reference_m02_activos_biologicos.md`
sobre que la lectura se exponía desde `configuration`.

## Pruebas

`tests/biological_assets/test_consultar_asociaciones_sensor_use_case.py` —
7 casos nuevos, fakes escritos a mano, sin BD: `ACTIVA` filtra correctamente,
`HISTORIAL` incluye `SUPERADA`, activo inexistente → 404, `tipo_consulta`
inválido → 400, lista vacía sin error, propagación del alcance de finca
(RF-25) al repositorio de activos, y registro en bitácora RF-52.

Se agregó también la ruta nueva a la whitelist de `test_rf52_auditoria_rbac.py`
(`test_todas_las_rutas_m02_protegidas_auditan_el_rf_que_las_origina`).

Suite completa sin regresiones: 643 passed (636 previos + 7 nuevos), mismos 2
fallos preexistentes en `test_registrar_transferencia_use_case.py` (no
relacionados, confirmados fallando igual en `origin/dev` sin este cambio).

## Alcance

No se tocó `AsociarSensorActivoUseCase` ni `CambiarEstadoAsociacionSensorUseCase`
— este fix es puramente de lectura, agregado sobre el puerto y el router
existentes.

## Adenda — informe TC-M02-G91 (QA)

El caso agrupado `TC-M02-G91` cubre dos subcasos relacionados con este mismo
router:

- **TC-M02-223** (`INC-M02-G91-01`, el mismo defecto que este documento): `POST`
  crea la asociación correctamente, pero `GET` respondía 405 — exactamente lo
  que corrige este fix. La aserción de QA describe "cuerpo es un array"; se
  decidió **mantener el objeto envolvente** (`{id_activo_biologico,
  tipo_consulta, asociaciones: [...]}`) en vez de un array plano en la raíz,
  por consistencia con `GET /{id_activo}/infraestructura` (mismo patrón
  `ACTIVA`/`HISTORIAL` en este mismo router). Si el retest automatizado de QA
  (`retest_tc_m02_223.ps1`) verifica literalmente que la raíz de la respuesta
  sea un array, va a necesitar actualizarse para leer `response.asociaciones`
  en vez de `response` directamente.
- **TC-M02-222** (`OBS-M02-G91-01`, severidad baja, no bloqueante): `DELETE`
  sobre una asociación puntual y sobre la ruta base deben seguir rechazándose
  (Restricción 8, append-only). La aserción de QA acepta `404` o `405`
  indistintamente. Verificado que agregar el `GET` no habilita `DELETE` en
  ninguna de las dos rutas — sigue devolviendo `405` en ambas (test nuevo:
  `test_inc_m02_68_g91_sensores_delete_no_permitido.py`). La sugerencia de
  QA de exponer un error de negocio explícito para el `DELETE` (en vez de
  404/405 genéricos) queda fuera de alcance de este fix — es una observación
  de calidad de contrato, no del criterio de cierre de `INC-M02-G91-01`.
