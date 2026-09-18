# INC-M09-01-109 (#319) — Auditoría de consultas e intentos fallidos sobre plantillas

Fecha: 2026-09-18

## Síntoma reportado por QA

`GET /configuracion/plantillas/auditoria` (RF-30, CU-07 Flujo D) solo mostraba
filas de creación/versionado **exitosos**. Las consultas (listar, detalle,
historial) y cualquier intento fallido (creación, versionado, aplicación,
consulta) no quedaban registrados en ningún lugar consultable.

## Causa raíz

`modulo9.auditorias_plantillas` tenía dos restricciones que lo impedían:

1. `CHECK (tipo_operacion = 'CREATE')` — no admitía `READ` ni `APPLY`.
2. `id_plantilla NOT NULL` — imposible auditar un fallo ocurrido *antes* de
   que existiera un id (ej. nombre duplicado al crear).

Además, `registrar()` se llamaba con `flush()` dentro de la misma transacción
que la operación principal: si esa transacción hacía `rollback()`, el registro
de auditoría se perdía con ella — por diseño no había forma de auditar un
fallo aunque el esquema lo hubiera permitido.

## Gaps de BD (Paso 0) y solución aplicada

Migración Alembic `c461638a6714` (revisa `281e99d58ecb`, head al momento de
esta ficha):

```sql
ALTER TABLE modulo9.auditorias_plantillas
    ALTER COLUMN id_plantilla DROP NOT NULL,
    ADD COLUMN resultado VARCHAR(20) NOT NULL DEFAULT 'EXITOSO';

ALTER TABLE modulo9.auditorias_plantillas
    DROP CONSTRAINT auditorias_plantillas_tipo_operacion_check,
    ADD CONSTRAINT ck_auditoria_plantilla_tipo_operacion
        CHECK (tipo_operacion IN ('CREATE', 'READ', 'APPLY')),
    ADD CONSTRAINT ck_auditoria_plantilla_resultado
        CHECK (resultado IN ('EXITOSO', 'FALLIDO'));
```

Nota: el `CHECK` original en la BD real se llamaba
`auditorias_plantillas_tipo_operacion_check` (autogenerado por Postgres, la
tabla se creó con un `CHECK` inline sin nombre explícito) — no
`chk_tipo_operacion_plantilla` como decía el modelo ORM (`auditoria_plantilla_model.py`),
que nunca coincidió con la BD real. Se reemplaza por el nombre que exige
`anotaciones/convencion_nomenclatura_bd.md` (`ck_` + descriptivo), que además
ya lo cita textualmente como ejemplo.

**Requiere autorización de DBA antes de mergear** (modifica constraints de una
tabla existente).

## Cambio de aplicación

- `RegistrarPlantillaUseCase`, `VersionarPlantillaUseCase`, `AplicarPlantillaUseCase`:
  todo el `execute()` queda envuelto en un try/except que audita cualquier
  excepción (`tipo_operacion` correspondiente, `resultado=FALLIDO`) en una
  transacción propia (helper `_auditoria_comun.registrar_intento_fallido`),
  después de deshacer la operación principal. Cubre también INC-M09-02-115
  (#318, creación fallida) e INC-M09-04-124 (#316, aplicación fallida) como
  efecto directo del mismo mecanismo.
- `ConsultarPlantillasUseCase.listar_plantillas/obtener_plantilla/listar_historial`:
  ahora reciben `usuario_actual` y auditan cada consulta (`tipo_operacion=READ`).
  Los `GET` no comiteaban nada antes (`get_db()` no auto-comitea) — ahora cada
  uno hace su propio `commit()` tras auditar, igual que un use case de escritura.
  `listar_auditoria` y `consultar_esquema` quedan fuera: el primero es meta
  (auditar la propia consulta de auditoría no aporta), el segundo no lee de la
  tabla `plantillas`.
- Router: los 3 endpoints `GET` que no tenían `get_current_user` ahora lo
  requieren, para poder atribuir la consulta a un usuario.

## Verificación

- `tests/integration/test_rf30_auditoria_plantillas.py`: 3 casos nuevos (READ
  exitoso, READ fallido sobre id inexistente, CREATE fallido por nombre
  duplicado), más los 3 existentes — 6/6 verdes contra la BD local `pruebas`.
- `tests/configuration/test_rf30_rf31_esquema_plantilla.py` y
  `test_rf32_concurrencia_aplicar_plantilla.py`: assertions de `db.commits`
  actualizadas (antes esperaban `0` commits en el camino de fallo; ahora es
  `1`, el de la auditoría) — 63/63 verdes.
- `alembic upgrade head` / `alembic downgrade -1` probados contra `pruebas` y
  `sgpmp` locales.
