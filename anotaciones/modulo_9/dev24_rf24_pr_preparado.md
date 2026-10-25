# RF-24 — Línea base por cada especie presente en el área · DEV-24

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Resolver las especies por la relación N:M de DB-06 | RF-24 leía `area.id_especie`, incompatible con varias especies | Recorre `area.id_especies`, hidratado desde la puente oficial |
| Área con dos especies → dos líneas base | Se calculaba un único resultado | Calcula y persiste un resultado por `(área, especie)` |
| Área monoespecie compatible | Respuesta individual y reglas RF-24 existentes | Conserva el objeto individual, el algoritmo, las validaciones y el historial |

**Referencias:** Historia #3697 · Tareas #3788 y #3789 · Épica #3662 · RFC-012, evidencia §3.

**Dependencia de integración:** DB-06 (#613) y su adaptación ORM en DEV-22 (#619). La base DEV-22 también requiere `nivel_criticidad` de DB-07 (#614). Este cambio no incorpora ni modifica sus migraciones.

## Causa raíz

La persistencia ya identifica las líneas por área y especie. El flujo manual, el automático y la consulta todavía seleccionaban la propiedad singular del área, que deja de representar su composición con RFC-012.

## Cambios implementados

### Cálculo y persistencia por par

Se obtienen las especies desde DB-06 mediante el repositorio de infraestructura y se ejecuta el cálculo RF-24 existente para cada ID distinto. Cada par tiene su intento, línea vigente y auditoría. No se elige una especie arbitraria ni se duplica la tabla de asociaciones.

### Integridad e historial

La publicación de los pares utiliza una sola transacción. Un fallo en el segundo par revierte toda la publicación; los cálculos fallidos conservan su historial y las líneas anteriores. Las recalibraciones conservan los intentos previos y reemplazan cada vigente según la semántica existente.

Se serializan calibraciones de la misma área mediante un bloqueo transaccional PostgreSQL. Esto permite la primera publicación concurrente sin exigir al Ingeniero de Campo permisos de edición de infraestructura ni modificar RLS.

### Consulta y compatibilidad

Se publica explícitamente la colección de resultados multiespecie y se conserva el objeto monoespecie. La consulta puede seleccionar un par mediante `especie_id`. Se mantienen JWT, RBAC, alcance por finca y `modo_calibracion` obligatorio.

Las observaciones se limitan al área, cámara y ventana solicitadas. El dato de visión mantiene su contrato agregado por área; DEV-24 no incorpora clasificación de muestras por especie ni modifica las fórmulas.

## Migración

No se añade migración propia. La prueba PostgreSQL utiliza las migraciones exactas de DB-06 y DB-07 sobre una base local aislada. Integrar esta entrega requiere que las dependencias se encuentren disponibles en el entorno destino.

## Contrato resultante

| Operación | Resultado |
|---|---|
| Calibrar área monoespecie | Una línea base y respuesta individual existente |
| Calibrar área con dos especies | Dos líneas por par y respuesta `{total, items}` |
| Consultar vigentes de área multiespecie | Colección de las líneas vigentes de sus especies asociadas |
| Consultar con `especie_id` | Línea individual del par solicitado |

## Pruebas realizadas

**663 pruebas distintas aprobadas; 0 fallidas y 0 omitidas.** Las repeticiones de pruebas enfocadas no se suman nuevamente.

| Grupo | Aprobadas | Verificación |
|---|---:|---|
| `tests/configuration` | 651 | Regresión RF-24 SENSOR/VISION, disparos M02, casos multiespecie y contrato compatible |
| Integración DEV-24 con PostgreSQL 18 | 12 | Dos especies → dos pares persistidos y recuperados; monoespecie; historial; rollback; concurrencia; HTTP/JWT/RBAC/RLS |

Las pruebas HTTP se ejecutaron con `sgpmp_app`, incluyendo un Ingeniero de Campo asignado a la finca. Se conservaron triggers, restricciones y RLS. No se desactivaron controles para ejecutar las pruebas.

## Integración con `sgpmp_dev`

Solo se inspeccionó la base oficial en modo lectura. No se aplicaron migraciones ni se ejecutaron calibraciones en ella. La evidencia de persistencia corresponde a PostgreSQL local con la relación DB-06 real.

## Dependencias y pendientes

- Integrar DB-06 y la adaptación ORM de DEV-22; resolver el grafo de migraciones dependientes antes del despliegue.
- QA sobre el entorno integrado y adopción del contrato de colección por consumidores multiespecie.

Los criterios de desarrollo de la ficha breve están verificados: dos especies producen dos líneas y una especie conserva el comportamiento anterior.

## Alcance del commit

Por instrucción del usuario, la entrega reúne en un único commit siete archivos de producción, cuatro de pruebas y los dos informes Markdown de DEV-24. Este texto prepara la descripción del PR; no implica que el PR ya se haya creado. Las evidencias crudas y los temporales de prueba permanecen locales.

## Revisión contra `dev`

La rama `fix/dev24-calibracion-vision-multiespecie` parte de DEV-22 `851db2ba`, sobre `origin/dev` `6113a388`. El usuario autorizó el commit y push de la entrega completa de DEV-24. El PR debe declarar la dependencia de #619 o esperar su integración para que el diff propio de DEV-24 quede separado de los 24 archivos de DEV-22. El PR no se ha creado.
