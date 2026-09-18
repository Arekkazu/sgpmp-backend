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

## Decisión (revisión posterior — se aisló la causa raíz)

La revisión inicial (arriba) dejó pendiente identificar el trigger exacto sin acceso a los datos
reales del lote 130. Una revisión posterior sí pudo aislarlo con acceso al MCP de postgres:

**Confirmado por inspección directa de `pg_trigger`/`pg_proc` en `modulo2`:**
`detalles_activos_biologicos_poblacionales` tiene el trigger `trg_poblacional_cantidad_inmutable`
(`BEFORE UPDATE`), que ejecuta `modulo2.trg_fn_poblacional_cantidad_inmutable()`:

```sql
IF NEW.cantidad_inicial <> OLD.cantidad_inicial THEN
    RAISE EXCEPTION 'IMMUTABLE_FIELD: ...' USING ERRCODE = 'P0210';
END IF;
IF NEW.cantidad_actual < 0 THEN
    RAISE EXCEPTION 'INVALID_VALUE: ...' USING ERRCODE = 'P0210';
END IF;
```

`P0210` **no estaba en la lista de códigos ya sospechados** (`P0216`–`P0218`) de la primera
revisión, pero es el único trigger de todo `modulo2` que escribe exactamente sobre la tabla que
`actualizar_detalle_poblacional()` actualiza.

**Confirmado empíricamente (no solo por lectura del trigger)** con un probe directo de
SQLAlchemy contra Postgres: una excepción `RAISE ... USING ERRCODE = 'P0210'` se clasifica como
`sqlalchemy.exc.InternalError` — **no** `IntegrityError`, `DataError` ni `OperationalError` — así
que ninguna de las ramas `isinstance` de `raise_from_db_error` la reconoce y cae al catch-all
final:

```python
raise InfrastructureError(code="ERROR_INTERNO", message="Error inesperado en base de datos", ...)
```

Ese mensaje es **literal, palabra por palabra, el que reporta QA** en el issue. Es decir: incluso
con el fix original (envolver `actualizar_detalle_poblacional` en `raise_from_db_error`) ya
aplicado, una violación de `P0210` seguía devolviendo exactamente el mismo `500 ERROR_INTERNO /
Error inesperado en base de datos` — el wrap por sí solo no alcanzaba a resolver el síntoma
reportado si esta era la causa real.

Se agregó el mapeo de `P0210` en `db_error_translator.py` (mismo patrón que `P0104`, `P0109`,
`P0130`, `P0140`, `P0215`, `P0220`) → `ValidationError` (400, `VALOR_NO_PERMITIDO`), consistente
con la restricción `CHECK` gemela `chk_poblacional_cantidad_actual_no_negativa` que ya cubre la
misma regla de negocio cuando la violación llega por otra vía.

**Verificado end-to-end contra la base local `pruebas`** (activo POBLACIONAL real registrado en
una transacción con rollback, `cantidad_actual` forzada a negativo): sin el mapeo, la prueba
efectivamente falla con `InfrastructureError: Error inesperado en base de datos`; con el mapeo,
pasa con `ValidationError` 400 / `VALOR_NO_PERMITIDO`.

## Fix

1. `SqlAlchemyActivoBiologicoRepository.actualizar_detalle_poblacional()` envuelve el
   `flush()`/`refresh()` en `try/except` y traduce con `raise_from_db_error()`, igual que el resto
   de métodos de escritura del repositorio (fix original).
2. `src/shared/db_error_translator.py` agrega el mapeo de `P0210` →
   `ValidationError(code="VALOR_NO_PERMITIDO")` (fix complementario, causa raíz).

## Pruebas

- `tests/shared/test_db_error_translator.py`: nuevo caso unitario para `P0210`, mismo patrón que
  los demás ERRCODEs `P0xxx` documentados en ese archivo.
- `tests/integration/test_inc_m02_100_g31_actualizar_detalle_poblacional_error_db.py`: dos casos
  contra la base real —
  1. `chk_poblacional_cantidad_actual_coherente` (CHECK nativo, ya cubierto por el fix original).
  2. `trg_fn_poblacional_cantidad_inmutable` / `P0210` (el trigger, causa raíz de este incidente).
  Ambos ejecutados y verificados contra `pruebas` (local): **passed**. La fixture original de este
  archivo (`especie_e_infra`) tenía nombres de finca/infraestructura con dígitos y guiones
  (`'Finca Prueba INC-M02-100-G31'`), que `trg_fn_finca_nombre_unique` rechaza (solo letras y
  espacios); se corrigieron a nombres válidos para poder ejecutar la prueba.
- Suite completa no-integración: 711 passed, mismos 2 fallos preexistentes en
  `test_registrar_transferencia_use_case.py` (no relacionados). Suite de integración completa:
  173 passed, mismos 8 fallos preexistentes en `fix/m02` sin relación con este cambio.

## Alcance

Se mapeó únicamente `P0210`, el código confirmado como causa raíz de este incidente. La
inspección de `pg_proc` en `modulo2` para este trabajo encontró que **la enorme mayoría de los
ERRCODE `P02xx` de ese esquema siguen sin mapear** (`P0202`–`P0209`, `P0211`–`P0214`,
`P0216`–`P0219`, `P0221`–`P0233` — más de 25 códigos, cubriendo desde inmutabilidad de activos
hasta transiciones de estado y secuencias de eventos reproductivos/sanitarios). Mapear todos esos
códigos no corresponde al alcance de este incidente puntual (#262) y se deja fuera de este PR;
queda documentado aquí como hallazgo para una tarea de deuda técnica separada, priorizando cuando
un incidente real vuelva a aterrizar en uno de ellos — igual que ocurrió con `P0210` en este caso.
