# INC-M01-03-119 (continuación) — la BD de test nunca recibió el fix

## Contexto

El fix de aplicación para INC-M01-03-119 (`DELETE /roles/{id}` → 500) ya
estaba mergeado a `dev` vía PR #62, con su migración Alembic `c4a19e7d2b63`.
El reporte de Newman que QA reenvió seguía en rojo porque corresponde a una
corrida de las 18:06 UTC del 31 de agosto — el PR se mergeó a las 22:16 UTC,
casi 4 horas después. Pero al revisar el pipeline de CI, el job que aplica
las migraciones a la BD de test (`Deploy Migrations to Dev & Test DBs`)
seguía fallando después del merge:

```
ERROR [alembic.util.messaging] Can't locate revision identified by 'cf8df1369e08'
FAILED: Can't locate revision identified by 'cf8df1369e08'
```

## Causa raíz

La tabla `alembic_version` de `TEST_DATABASE_URL` quedó apuntando a una
revisión (`cf8df1369e08`) que no existe en ningún punto del historial de
`alembic/versions/` de este repo — probablemente una migración generada y
aplicada localmente contra esa BD compartida, y luego descartada sin
comitear. `DEV_DATABASE_URL` sufrió el mismo problema el 30 de agosto (PR
#56 de Copilot lo "reparó" con `alembic stamp head` a ciegas; el enfoque se
revirtió por peligroso, pero el `stamp` ya ejecutado dejó dev funcionando).
Test nunca recibió ese tratamiento y quedó varada.

## Diagnóstico (sin tocar la BD)

Antes de estampar nada, se agregó un modo `solo_diagnostico` al workflow
(`.github/workflows/migration-db.yml` + `.github/scripts/diagnosticar_migraciones.py`)
que compara `alembic_version` contra marcadores reales de esquema —
existencia de tablas/constraints/filas introducidas por cada migración
reciente — en vez de confiar en la tabla de control. Resultado:

| Migración | Marcador | dev | test |
|---|---|---|---|
| `f2c84d91a6e7` | permiso `admin_ejecutar_identificacion_completa` | SI | SI |
| `e8bb4f321a44` | trigger revoca tokens | SI | no |
| `d9a47c30e5b1` | `tipos_eventos` id 26 | SI | no |
| `f1c62d8b04a7` | tabla `cola_exportaciones_auditoria` | SI | no |
| `c4a19e7d2b63` | `fk_recurso_rol` ON DELETE CASCADE | SI | no |

Confirmado: `test` estaba realmente en `f2c84d91a6e7`, cuatro migraciones
detrás de `dev`.

## Corrección

- El input único `stamp` (que reestampaba dev y test con el mismo valor en
  una sola pasada) se separó en `stamp_dev` y `stamp_test`, cada uno con su
  propio paso y su propia `DATABASE_URL`. Con el mismo valor para ambas DBs
  se corría el riesgo de hacer retroceder una DB que ya estaba sana (como
  pasó con dev, que se reparó sola en un punto distinto al de test).
- Ejecutado en vivo vía `workflow_dispatch` con `stamp_test=f2c84d91a6e7`:
  el job reestampó `TEST_DATABASE_URL` a esa revisión y el `alembic upgrade
  head` que ya corre después aplicó de verdad las 4 migraciones pendientes.
- Verificado con el mismo diagnóstico de solo lectura: dev y test quedan en
  `c4a19e7d2b63` con los 5 marcadores en `SI`.

## Estado

`TEST_DATABASE_URL` (la BD contra la que corre el entorno de QA
`sigab-backendtest`) ya tiene el fix de INC-M01-03-119 aplicado de verdad.
El modo `solo_diagnostico` y los inputs `stamp_dev`/`stamp_test` quedan en
el workflow para el próximo incidente de este tipo — no son de un solo uso.
