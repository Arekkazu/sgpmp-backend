# INC-M02-100-G31 — 500 ERROR_INTERNO en POST .../eventos/crecimiento (capa de persistencia)

**RF:** RF-36/RF-40 (Gestión Poblacional de Activos Biológicos, CU06 eventos de crecimiento).

## Qué reportó QA

`POST /activos-biologicos/{id}/eventos/crecimiento` sobre el lote poblacional `130` (TC-M02-196,
caso agrupado TC-M02-G31, RF-36) devolvía `500 ERROR_INTERNO` al registrar un evento con la
densidad del lote exactamente en el límite permitido (`densidad_actual == densidad_maxima`),
donde se esperaba `201 Created`. El reporte descarta explícitamente que sea:

- El bug de enum `'poblacional'`/`'POBLACIONAL'` del trigger `trg_fn_baja_cantidad_valida` (PR #254).
- El gap de fase activa de INC-M02-37-G24 (el lote 130 sí tiene `id_gestion_fases=35`).

Y confirma que el fallo queda registrado en bitácora M02 con `tipo_evento='EVENTO_CRECIMIENTO_FALLIDO'`.

## Investigación (Paso 0)

**Fecha de ejecución de QA:** 2026-09-11. El fix de densidad máxima por especie
(`9cbb4418`, INC-M02-38-G25) se mergeó el **2026-09-15**, después de esa ejecución — pero se
verificó su diff completo: solo agrega una validación de negocio en Python antes de mutar el
detalle poblacional, no toca nada de la capa de persistencia. No es la causa de este incidente.

**Verificado contra `sgpmp_dev` real (vía MCP de postgres, reconectado durante la investigación):**

- Se listaron y leyeron todos los triggers vigentes sobre `eventos_activos`, `eventos_crecimeinto`,
  `detalles_activos_biologicos_poblacionales` y `activos_biologicos`. Varios usan
  `RAISE EXCEPTION ... USING ERRCODE = 'P02xx'` (ej. `P0216`, `P0217`, `P0218`, `P0210`) que
  **no están mapeados** en `src/shared/db_error_translator.py` (que solo mapea `P0104`, `P0109`,
  `P0130`, `P0140`, `P0215`, `P0220`) — cualquiera de ellos, si se dispara sin haber pasado antes
  por la validación de aplicación, sale como 500 en vez del código de negocio correspondiente.
  Este es el mismo patrón que ya causó los incidentes INC-M09-107-G64, INC-M02-76-G55 e
  INC-M02-75-G53, cada uno resuelto agregando el ERRCODE faltante al traductor.
- **`SqlAlchemyActivoBiologicoRepository.actualizar_detalle_poblacional()`
  (`activo_biologico_repository.py:401`) no capturaba errores de base de datos ni los traducía
  con `raise_from_db_error`** — a diferencia de todos los demás métodos de escritura del mismo
  repositorio y de `SqlAlchemyEventoActivoRepository.guardar()` (que sí lo hace). Esto viola la
  regla no negociable del proyecto ("todo método de escritura en un repository debe capturar
  errores de DB y traducirlos"). Es el único punto de escritura sin envolver en la transacción de
  `RegistrarEventoCrecimientoUseCase._execute()` (líneas 200-207): cualquier excepción cruda que
  salga de ahí cae en la rama `except Exception` (no `except AppError`) del use case, se registra
  correctamente en bitácora como `EVENTO_CRECIMIENTO_FALLIDO`, pero se relanza **sin traducir** —
  coincide exactamente con la evidencia reportada por QA.
- **Repro controlado** (transacción con `ROLLBACK`, sin persistir nada) contra `sgpmp_dev`
  ejecutando la secuencia SQL exacta del backend (`INSERT eventos_activos` → `INSERT
  eventos_crecimeinto` → `UPDATE detalles_activos_biologicos_poblacionales`) sobre un lote
  poblacional real con `capacidad_maxima == cantidad_actual` (límite exacto de densidad, mismo
  escenario de TC-M02-196): **no se reprodujo ningún error** con los triggers vigentes en `dev`.
  No se pudo confirmar el trigger/constraint exacto que falla para el lote 130 en TEST porque
  sus valores reales (`superficie`, `capacidad_maxima`, `cantidad_actual`, `peso_promedio`) no
  están disponibles desde este entorno (el lote 130 no existe en `sgpmp_dev`; el MCP de postgres
  configurado solo alcanza `sgpmp_dev`, no `sgpmp_test`).

## Decisión

Dado que no se pudo aislar el trigger/constraint exacto sin acceso a los datos reales de TEST,
se corrige el defecto de arquitectura confirmado — que es, con la evidencia disponible, la causa
más probable de que un rechazo legítimo de base de datos se convierta en un 500 opaco en vez de
un código de dominio — y se deja documentado el patrón sistémico de ERRCODEs `P02xx` sin mapear
por si QA vuelve a reproducir el 500 tras este fix (en cuyo caso el error ya vendría bien
traducido, y su código de negocio permitiría identificar el trigger real disparado).

## Fix

`SqlAlchemyActivoBiologicoRepository.actualizar_detalle_poblacional()` ahora envuelve el
`flush()`/`refresh()` en `try/except` y traduce con `raise_from_db_error()`, igual que el resto
de métodos de escritura del repositorio.

## Pruebas

- `tests/integration/test_inc_m02_100_g31_actualizar_detalle_poblacional_error_db.py`: fuerza una
  violación real de `chk_poblacional_cantidad_actual_coherente` a través del método corregido y
  confirma que ahora se traduce a `ValidationError` (400) en vez de escapar como excepción cruda.
  **No se pudo ejecutar en este entorno**: los tests de integración de este proyecto exigen
  `TEST_DATABASE_URL` apuntando a una base cuyo nombre contenga `test` (o esté en la lista
  explícita `{"pruebas", "pruebas-integrador"}`) — protección de `tests/integration/conftest.py`
  que impide correrlos contra `sgpmp_dev` por accidente, y no hay una base así disponible en este
  entorno. Debe ejecutarse contra la base de pruebas real antes de mergear.
- Suite completa de `tests/biological_assets/`: 194 passed, mismos 2 fallos preexistentes en
  `test_registrar_transferencia_use_case.py` (no relacionados, ya documentados en el repo).

## Alcance

No se tocaron los triggers de base de datos ni se agregaron nuevos ERRCODEs al traductor: sin
los datos reales del lote 130 en TEST no hay forma de confirmar cuál trigger específico dispara
el error, y agregar un mapeo a ciegas arriesga ocultar un código de negocio distinto al correcto.
Si QA reproduce el mismo 500 después de este fix, el `error_code`/mensaje de la respuesta (ya
traducido) debería apuntar directo al trigger real.
