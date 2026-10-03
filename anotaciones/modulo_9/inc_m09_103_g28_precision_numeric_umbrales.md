# INC-M09-103-G28 (#294) — Discrepancia entre tipo numérico especificado y esquema PostgreSQL

Reevaluación V2 de TC-M09-G28: TC-M09-60 (precisión) y TC-M09-61 (persistencia en nueva sesión)
quedaron **APROBADOS** — sin defecto funcional para los valores probados (35.57/39.23). QA dejó
una observación: RF-17 especifica `NUMERIC(5,2)` para `valor_min`/`valor_max`, pero el esquema
real en TEST tenía `NUMERIC(8,2)` — la escala (2) coincide, difiere la precisión total.

## Qué ya estaba resuelto al llegar a este issue

Antes de investigar, se confirmó que `dev` ya tiene mergeado (PR #381, migración `1147428cd8fb`,
mismo día) el cambio de `modulo9.umbrales_ambientales.valor_min`/`valor_max` de `NUMERIC(8,2)` a
`NUMERIC(5,2)`. Es decir: **la decisión "cuál es la definición oficial" ya se tomó** (RF-17 es
correcto) y el esquema de la tabla padre ya está alineado.

## Qué faltaba (esto sí lo resuelve este fix)

1. **El ORM seguía sin declarar la precisión.** QA lo señaló explícitamente: "la revisión local
   también muestra que el ORM utiliza `Numeric` sin fijar explícitamente una precisión/escala
   equivalente a la declarada por RF-17". `UmbralAmbientalModel.valor_min`/`valor_max` seguían
   como `Numeric` a secas incluso después de que la columna real ya fuera `NUMERIC(5,2)` — un
   `Numeric` sin argumentos en SQLAlchemy no valida ni refleja precisión, así que el modelo no
   documentaba lo que la BD realmente exige.

2. **Hallazgo adicional, no probado por QA pero real:** `niveles_alerta_ambientales
   .limite_inferior`/`limite_superior` seguían en `NUMERIC(8,2)`. Por regla de negocio
   (`_validar_rangos` en `registrar_umbral_use_case.py`), un nivel siempre cae dentro de
   `[valor_min, valor_max]` del umbral padre — la tabla hija debería tener la misma capacidad
   numérica que el padre. El PR #381 solo tocó la tabla padre; esta tabla quedó con la misma
   inconsistencia esquema/RF-17 que QA reportó, solo que en la tabla hija.

## Fix

- **ORM:** `UmbralAmbientalModel.valor_min`/`valor_max` y `NivelAlertaAmbientalModel
  .limite_inferior`/`limite_superior` ahora declaran `Numeric(5, 2)` explícito.
- **Migración `b9edb971f005`** (v5.4.0, sobre head `1147428cd8fb`): `niveles_alerta_ambientales
  .limite_inferior`/`limite_superior` de `NUMERIC(8,2)` a `NUMERIC(5,2)`. `downgrade()`
  simétrico.

### Complicación encontrada y resuelta: vista dependiente

`modulo9.vw_rf17_umbrales_detalle_niveles` agrega `limite_inferior`/`limite_superior` dentro de
un `json_build_object` en un `json_agg` — Postgres bloquea `ALTER COLUMN TYPE` mientras exista
esa dependencia (`cannot alter type of a column used by a view or rule`). La migración hace
`DROP VIEW` → `ALTER COLUMN` → `CREATE VIEW` (definición idéntica, verificada con
`pg_get_viewdef` antes de tocar nada).

**`DROP VIEW` no conserva los `GRANT` del objeto.** Al recrear la vista en la verificación real
contra `sgpmp_dev`, quedó sin ningún permiso (`relacl` vacío) hasta que se detectó comparando con
las vistas hermanas del módulo (`vw_rf17_umbral_activo_por_especie_variable`,
`vw_rf17_variables_configuracion_especie`, mismo patrón de permisos: `INSERT/SELECT/UPDATE/
DELETE` para `rol_dev`/`rol_impl`/`rol_migracion`, `INSERT/SELECT` para `rol_aiot`). La
migración ahora re-otorga esos mismos permisos explícitamente después de cada `CREATE VIEW`
(en `upgrade()` y en `downgrade()`), para que el round-trip sea realmente simétrico y no
regrese los permisos de la vista en ninguna dirección.

## Verificación real contra `sgpmp_dev`

Con credencial `dba` provista por el usuario:

| Comprobación | Resultado |
|---|---|
| `alembic upgrade head` | Falló la primera vez: `cannot alter type of a column used by a view or rule` (vista dependiente no detectada en el diseño inicial) |
| Corrección: `DROP VIEW` + `ALTER` + `CREATE VIEW` en la migración | `alembic upgrade head` aplicó limpio |
| Columnas tras upgrade | `limite_inferior`/`limite_superior` en `NUMERIC(5,2)` |
| Vista tras `CREATE VIEW` | Recreada, pero **sin permisos** (`relacl` vacío) — detectado comparando con vistas hermanas |
| `GRANT` de corrección aplicado manualmente, luego incorporado a la migración | Vista con los mismos permisos que las hermanas del módulo |
| `alembic downgrade 1147428cd8fb` | Revirtió limpio |
| Estado final | Columnas de vuelta en `NUMERIC(8,2)`, vista con permisos originales intactos, `alembic current` = `1147428cd8fb` — exactamente como antes |

Esta verificación no reemplaza la aprobación formal del DBA. El DBA debe correr
`alembic upgrade head` de forma definitiva y confirmar el resultado antes de mergear.

## Pruebas

- `tests/configuration/test_inc_m09_103_g28_precision_orm_numeric.py` (nuevo, 2 casos): confirma
  que `UmbralAmbientalModel` y `NivelAlertaAmbientalModel` declaran `Numeric(5, 2)`.
- Suite completa: 717 passed, mismos 2 fallos preexistentes en `test_registrar_transferencia_use_case.py`
  (módulo 2, no relacionados).

## Fuera de alcance

- No se re-versiona ni se toca `umbrales_ambientales.valor_min`/`valor_max` — ya corregido por
  el PR #381, ajeno a esta rama.
- No se investigó si otras vistas o funciones del sistema asumen la precisión anterior
  (`NUMERIC(8,2)`) de `niveles_alerta_ambientales` más allá de la única vista dependiente
  encontrada (`vw_rf17_umbrales_detalle_niveles`) — se verificó con `pg_depend` que es la única.
