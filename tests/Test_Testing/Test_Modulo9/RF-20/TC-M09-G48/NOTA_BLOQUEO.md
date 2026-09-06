# TC-M09-G48 (TC-M09-96) — BLOQUEADO por migración faltante en el entorno de test

**RF-20 / CU-04 — Gestionar Infraestructura Productiva**
**Estado: FALLA / BLOQUEADO** (no es un bug de código; es un gap de despliegue en el
servidor de test compartido).

## Qué se observó

`POST /configuracion/infraestructuras` con datos válidos (idénticos al ejemplo de
`curls_m09_cu04_infraestructura.md`) devuelve:

```json
{"error_code":"ERROR_INTERNO","message":"Ocurrió un error interno...","fields":[],...}
```

con status `500`, en vez de `201`. Reporte completo (con la traza del failure) en
`Resultados/reporte-TC-M09-G48.html`.

## Causa raíz confirmada

`registrar_infraestructura_use_case.py` valida `tipo_area` contra un catálogo administrable
(`modulo9.tipos_area`, vía `SqlAlchemyTipoAreaRepository`) en vez del enum fijo de Postgres
que documentaba `curls_m09_cu04_infraestructura.md`. Existe la migración
`alembic/versions/2dbb6d44046f_rf20_catalogo_tipos_area.py` que crea esa tabla, pero:

```sql
-- Verificado contra la BD de test compartida (sgpmp_test):
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'modulo9' AND table_name LIKE '%tipo%area%';
-- => 0 filas. modulo9.tipos_area NO existe en este entorno.
```

La migración nunca se aplicó a este servidor específico, aunque el código de la aplicación
ya asume que la tabla existe. Cualquier `SELECT` a una tabla inexistente sale como
`ProgrammingError` de SQLAlchemy, no capturado en el use case, y cae en el handler genérico
de 500 (`error_no_controlado_handler`) en vez de un 422/404 controlado.

Esto coincide exactamente con lo que ya anticipaba `tests/integration/test_rf20_tipos_area.py`
(se salta con `pytest.skip` si esa migración no está aplicada en la base de pruebas usada).

## Por qué no se puede resolver desde esta sesión

El usuario `member_qa` (credencial de solo consulta usada para verificar hallazgos de
auditoría en RF-18/RF-19) no tiene permisos DDL: `SELECT * FROM alembic_version` devuelve
`permission denied`. Aplicar la migración requiere una credencial con permisos de escritura
sobre el esquema, que está fuera del alcance de esta sesión de QA.

## Cómo desbloquear

Aplicar la migración pendiente contra la base `sgpmp_test` del servidor de test:

```bash
DATABASE_URL=postgresql://<usuario_con_permisos>:<clave>@158.69.200.27:5448/sgpmp_test \
  alembic upgrade head
```

Tras aplicarla, reejecutar sin cambios:

```bash
newman run "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G48/TC-M09-G48.postman_collection.json" \
  -r cli,htmlextra --reporter-htmlextra-export "tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G48/Resultados/reporte-TC-M09-G48.html"
```

## Alcance del bloqueo

Cualquier caso de RF-20 que registre o edite un área productiva (`POST`/`PATCH
/configuracion/infraestructuras`) muy probablemente falle igual mientras esta migración no
se aplique — vale la pena confirmarlo antes de invertir tiempo en más colecciones de RF-20.

**Casos afectados confirmados hasta ahora:**
- TC-M09-G48 (TC-M09-96) — bloqueado por completo (registrar).
- TC-M09-G49 (TC-M09-98 mitad de aceptación, TC-M09-99, TC-M09-100) — bloqueado parcialmente;
  TC-M09-97 y la mitad de rechazo de TC-M09-98 sí pasan porque se validan antes de tocar el
  catálogo. Ver `TC-M09-G49/Resultados/TC-M09-G49-resultados.md`.
- TC-M09-G50 (TC-M09-101) — bloqueado por completo (editar): `EditarInfraestructuraUseCase`
  también revalida `tipo_area` contra el catálogo en toda edición. Ver
  `TC-M09-G50/Resultados/TC-M09-G50-resultados.md`.
