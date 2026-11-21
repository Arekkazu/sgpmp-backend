# RF-80 — Rechazar rangos temporales invertidos en auditoría · INC-M05-276-G38

## Desvío identificado

| RF/CU exige | Antes | Ahora |
|---|---|---|
| TC-M05-044.1 / CU06 FA-01: pedir corregir filtros inválidos sin consultar el repositorio | Rango invertido devolvía 200 con lista vacía | Devuelve 400 VAL_ENTRADA y un mensaje para corregir las fechas |
| Distinguir consulta inválida de ausencia de eventos | Ambas devolvían la misma respuesta | Rango válido sin coincidencias conserva 200 y lista vacía |
| Aplicación consistente de filtros | Consulta y exportación permitían invertir fechas | Comparten la misma validación previa |

Referencias: #961, INC-M05-276-G38, RF-80, TC-M05-G38, TC-M05-044.1 y checkpoint B01.

Closes #961

## Causa raíz

Los parámetros se normalizaban individualmente a UTC, pero no se validaba su orden. Los casos de uso enviaban el rango invertido al repositorio, cuyas condiciones AND devolvían cero coincidencias.

## Cambios implementados

- Validar el orden al construir FiltrosAuditoriaSuministro, compartido por listado y exportación.
- Comparar instantes UTC y conservar la admisión de extremos iguales, fechas sin zona tratadas como UTC y límites omitidos.
- Responder con el error compartido de validación y mensaje explicativo, antes de consultar la bitácora o generar archivos.
- Documentar 400 en OpenAPI del listado; exportación ya lo contemplaba.

## Migración

No requiere migración ni cambios de permisos, RLS, índices o triggers. Se reutilizan los errores y handlers existentes.

## Contrato resultante

- fecha_desde > fecha_hasta: HTTP 400, error_code VAL_ENTRADA, field fecha_hasta y mensaje “El inicio del rango no puede ser posterior al final. Corrige las fechas e intenta de nuevo.”
- Rango válido sin eventos: HTTP 200 con items=[] y total=0.
- Extremos iguales o filtros temporales abiertos: admitidos.
- Formato de fecha inválido: conserva el 400 VAL_ENTRADA del handler existente.
- Listado y exportación rechazan el rango inválido antes de leer; autenticación y autorización mantienen sus consultas y precedencia.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/supplies: 22 nuevas y 18 existentes, con fakes/dominio | 40 | 0 | 0 |
| Integración HTTP/PostgreSQL 18 real | 24 | 0 | 0 |
| Total distinto | 64 | 0 | 0 |

La integración usa sgpmp_app sin superusuario/BYPASSRLS y mantiene restricciones/triggers activos. Verifica validación antes de leer, consulta y exportación, formatos inválidos, límites inclusivos, offsets, igualdad, filtros abiertos, paginación, CSV y detalle, JWT y los lectores autorizados reales. Productor/Veterinario conservan 403.

## Integración con sgpmp_dev

Rama creada desde dev actualizada a 3251d78d2c5822624dde988a94a37331610d1cef:

`fix/inc-m05-276-g38-rango-auditoria-rf80`

Validación en una base local exclusiva migrada a b7e2d94c1a68. No se ejecutaron escrituras ni despliegues en TEST o DEV oficiales. Las ACL locales del fixture no acreditan las ACL desplegadas.

## Dependencias y pendientes

- Reejecutar el checkpoint B01 de G38 en TEST tras integrar y desplegar.
- El adjunto también reporta B02 (autoauditoría de consultas) y C02 (registro de acceso denegado). Son hallazgos distintos, fuera de #961; no se afirma aprobación de todo G38.
- No depende de #960 ni arrastra cambios de ramas anteriores.

## Alcance del commit

Entrega prevista: dos archivos de producción, dos archivos de pruebas y dos informes Markdown. Se excluyen evidencias temporales y archivos locales ajenos. Esta descripción preparada no implica commit, push ni PR publicado.

## Revisión contra dev

La validación reside en el objeto de filtros del dominio; el router mantiene su función de entrada/salida. No se modifican casos de uso, repositorios, SQL, schemas exitosos, permisos ni transacciones. Se conservan los contratos de consulta válida y detalle.
