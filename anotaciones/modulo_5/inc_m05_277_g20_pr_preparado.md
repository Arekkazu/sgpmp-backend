# RF-77 — Representar el promedio no calculable del lote · INC-M05-277-G20

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Restricción 6: cantidad actual cero implica NO_CALCULABLE con causa | POST devolvía null y la causa en otro campo | Devuelve el literal NO_CALCULABLE y conserva la causa |
| Consultar el reporte generado | El snapshot no conservaba promedio ni causa | Guarda ambos en el JSON existente y los recupera en consulta e historial |
| Mantener promedios calculables | Valores decimales | Conserva fórmula, precisión y serialización decimal |

Referencias: #963, INC-M05-277-G20, RF-77 Restricción 6, TC-M05-G20 / TC-M05-015 / checkpoint B02.

Closes #963

## Causa raíz

El generador ya evitaba la división por cero, pero el schema solo admitía Decimal/None y propagaba null. Además, el repositorio perdía promedio y causa al recuperar el snapshot.

## Cambios implementados

- Ampliar el schema con el literal cerrado NO_CALCULABLE y representarlo cuando el dominio informa una causa explícita.
- Mantener Decimal/None en el dominio para preservar cálculos y exportación.
- Conservar promedio y causa en resumen_promedio del JSON existente del snapshot, sin mutar los filtros originales.
- Permitir que el resultado async se represente igual, incluyendo resultados anteriores con null + causa.
- Preservar la distinción entre promedio no calculable, no aplicable y cero calculable.

## Migración

No requiere migración ni backfill. Se reutiliza json_parametros JSONB. No se cambian columnas monetarias, permisos, RLS ni triggers.

## Contrato resultante

Lote con cantidad cero: gasto_promedio_individuo = NO_CALCULABLE y causa informada. Lote con población vigente: promedio decimal como antes. Individual/agregado sin promedio aplicable: null.

El estado se conserva en POST, consulta de nuevos snapshots, historial, regeneración y polling. Un snapshot mantiene el promedio de su generación; regenerar utiliza la población actual.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/supplies: 13 nuevas y 18 existentes, dominio/schema/fakes | 31 | 0 | 0 |
| Integración HTTP/PostgreSQL 18 real | 13 | 0 | 0 |
| Total distinto | 44 | 0 | 0 |

Se prueba la cadena real de medicamento por 50.000 COP, baja total de 50 individuos y reporte, seguida de consulta/historial/regeneración. También promedios vigentes, valores cero, snapshot previo a la baja, polling de JSON persistido, exportación/descarga PDF/CSV, JWT/RBAC, alcance del Productor y rollback tras un fallo posterior al flush.

HTTP usa sgpmp_app sin superusuario/BYPASSRLS, con triggers y restricciones activos. El polling se verifica con resultados persistidos mediante repositorios reales; no se afirma ejecución del scheduler de producción.

## Integración con sgpmp_dev

Rama creada desde dev actualizada a 3251d78d2c5822624dde988a94a37331610d1cef:

`fix/inc-m05-277-g20-promedio-no-calculable-rf77`

Validación en sgpmp_inc963_test local exclusiva, migrada hasta b7e2d94c1a68. Sin escrituras ni despliegue en TEST/DEV oficiales. Las ACL locales de preparación no acreditan las desplegadas.

## Dependencias y pendientes

- Repetir B02 de TC-M05-G20 en TEST tras integrar y desplegar.
- Los snapshots síncronos antiguos sin resumen no pueden recuperar la población histórica; mantienen su lectura compatible y pueden regenerarse con datos actuales, sin modificar el pasado.
- No se rediseña la exportación ni se modifica UI. CSV/PDF conservan su contrato; se verifica ejecución y descarga.
- No depende de #958, #960 o #961 ni incorpora cambios de sus ramas.

## Alcance del commit

Entrega prevista: dos archivos de producción, dos de pruebas y dos informes Markdown. Excluir .pytest_cache y archivos locales ajenos. Descripción preparada; no implica commit, push ni PR publicado.

## Revisión contra dev

La corrección se limita a la representación pública y al mapeo de persistencia del snapshot. Se conservan arquitectura hexagonal, fórmulas de dominio, contratos HTTP restantes, RBAC y control transaccional del caso de uso.
