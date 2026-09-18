# TC-M09-G91 (#312) — Migración de TEST bloqueada, causa probable de HTTP 500 en sesiones

Fecha: 2026-09-18

## Síntoma reportado

Durante la reevaluación de TC-M09-G91/RF-27 en el ambiente TEST, `POST /sesiones/`
respondió `HTTP 500`, impidiendo obtener un token válido y bloqueando la
validación funcional de la jerarquía de resolución del tema.

## Lo que NO encontré (investigación honesta)

No pude reproducir un 500 en login/refresh contra el código actual:

```
TEST_DATABASE_URL=postgresql://postgres:dev@localhost:5432/pruebas \
  pytest tests/integration/test_sesiones_jwt.py tests/integration/test_refresh_token.py \
  tests/integration/test_rf06_bloqueo_invalida_sesiones.py -q
# 11 passed
```

Tampoco tengo acceso directo a `TEST_DATABASE_URL`/`DEV_DATABASE_URL` (secrets
de GitHub Actions) ni a los logs reales del backend desplegado en TEST — solo
a lo que exponen los workflows de CI.

## Lo que sí encontré: la cadena de migraciones de TEST está rota desde hace 2 semanas

`gh run list --workflow="Deploy Migrations - test"` muestra que el workflow
viene **fallando desde 2026-09-04** (4 de los últimos 5 runs en la rama `test`
fallan; el último éxito fue 2026-09-08). El log del run más reciente
(`gh run view 34773280750 --log`, 2026-09-13T18:00Z) da la causa exacta:

```
alembic current  →  6993cca9d95e         (TEST varada acá)
Running upgrade 281e99d58ecb -> ...      (nunca llega, falla antes)

sqlalchemy.exc.IntegrityError: (psycopg2.errors.CheckViolation)
new row for relation "metricas_produccion" violates check constraint
"chk_metricas_tipo_medicion"
DETAIL: Failing row contains (1, Peso promedio individual, g, manual, ...)
```

La migración que falla es `b92f7e1a4c63` (RF-16, agrega `tipo_dato`/`es_obligatorio`
a `metricas_produccion`). Su `UPDATE ... WHERE tipo_dato IS NULL` toca todas las
filas de la tabla, y Postgres revalida el `CHECK` en cada `UPDATE` — el
constraint es `NOT VALID` (confirmado con `pg_get_constraintdef` en la BD
local), así que nunca validó datos preexistentes. Una fila con
`tipo_medicion='manual'` (dato inválido, cargado antes de que el constraint
empezara a aplicarse) hace fallar el `UPDATE`.

**Reproducido y verificado el fix contra Postgres real** (BD local `sgpmp`,
en una transacción con `DROP`/`ADD CONSTRAINT ... NOT VALID` + insert +
`ROLLBACK`/limpieza, sin dejar rastro): el `UPDATE` original revienta con el
mismo `CheckViolation`; agregando la normalización defensiva antes, pasa.

## Cadena de razonamiento hacia el 500 de sesiones (hipótesis, no confirmación)

Con la cadena de migraciones bloqueada en `6993cca9d95e` desde el 4 de
septiembre, el esquema de TEST quedó **muchas migraciones detrás** del código
que corre ahí (el backend de TEST presumiblemente despliega desde una rama
que sigue a `dev`/código reciente, mientras su BD no recibió ninguna migración
nueva en 2 semanas). Si alguna de esas migraciones bloqueadas tocaba tablas
que usa el flujo de login/sesión, el código actual podría fallar contra el
esquema viejo. **Esto es la hipótesis mejor sustentada con la evidencia
disponible (logs de CI), no una confirmación con logs reales del error 500.**

## Fix aplicado

Se edita la migración ya mergeada `b92f7e1a4c63` para agregar, antes del
`UPDATE` que revienta, una normalización defensiva:

```sql
UPDATE modulo9.metricas_produccion
SET tipo_medicion = 'OTRO'
WHERE upper(tipo_medicion) NOT IN ('PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO');
```

**Por qué es seguro editar una migración ya mergeada:** Alembic identifica
cada migración por su `revision` y no la re-ejecuta donde ya quedó registrada
como aplicada (`dev`, `pruebas`/`sgpmp` locales) — el cambio solo afecta la
próxima vez que alguien la aplique donde todavía no llegó, que es
exactamente el caso roto (TEST).

## Pendiente, fuera de lo que puedo hacer desde este repo

- **Requiere autorización de DBA** antes de mergear (modifica una migración).
- No puedo confirmar que esto resuelve el 500 de sesiones específicamente sin
  acceso a los logs reales de TEST. Quien tenga acceso debería, tras mergear:
  1. Re-disparar el workflow "Deploy Migrations - test" (o esperar el próximo
     push a `test`) y confirmar que `alembic upgrade head` llega hasta el
     final sin errores.
  2. Si el 500 de login persiste después de eso, la causa es otra y esta
     ficha debe reabrirse con esa evidencia nueva.
