# RF-62 — Validación de consultas y parámetros auditables · INC-M03-103-G164

Referencia: [issue #625](https://github.com/Arekkazu/sgpmp-backend/issues/625), TC-M03-G164, RF-62 CA-9/CA-15 y RNF-07. Fecha: 2026-10-26.

## Desvío y causa raíz

| Contrato | Antes | Corrección |
|---|---|---|
| `clasificacion` pertenece al catálogo del dominio | Texto libre; filtro inválido devolvía lista vacía | La entrada HTTP utiliza `ClasificacionCalidad`: APTO, APTO_CON_RESERVA, NO_APTO, INDETERMINADA |
| `estado_evaluacion` admite VIGENTE/SUPERADA | Texto libre; ACTIVA se aceptaba | La entrada utiliza `EstadoEvaluacion`; ACTIVA y valores vacíos se rechazan |
| `fecha_desde <= fecha_hasta` | El caso de uso delegaba sin comprobar coherencia | Se compara en UTC antes de llamar al repositorio; igualdad y extremos individuales siguen permitidos |
| Paginación inválida produce 422 VAL_ENTRADA | FastAPI detectaba el error; el handler global lo convertía en 400 | El listado declara 422 mediante metadatos de operación; el handler reutiliza el cuerpo estándar y conserva 400 por defecto en otras operaciones |
| Cada cálculo conserva sus parámetros reales | La rama FUERA_DE_RANGO guardaba `{}` | Persiste la regla FUERA_DE_RANGO_RF53, índice fijo cero y omisión del análisis estadístico |

Las demás ramas del cálculo ya persistían `k`, `M`, `N`, `umbral_drift`, `P` y `frecuencia_muestreo_min`. Repositorio y schema transportan el JSON persistido; no se rellenan valores al leer. No se añade una dependencia de configuración estadística a la rama FUERA_DE_RANGO, porque CA-9 omite ese análisis.

## Flujo y compatibilidad

- Se mantiene Router → caso de uso → puerto → repositorio → ORM/PostgreSQL.
- La validación de enums es de entrada; la coherencia temporal pertenece al caso de uso.
- El listado documenta 422 con `ErrorResponse`; el formato sigue siendo `error_code`, `message`, `fields`, `timestamp`.
- Los defaults siguen siendo `pagina=1`, `por_pagina=50`; el límite sigue en 200.
- Las fechas con zona se convierten a UTC; las fechas sin zona que el contrato ya aceptaba se interpretan explícitamente como UTC, sin añadir un rechazo nuevo.
- JWT, estado de cuenta y RBAC(38, R/E) se conservan. No se cambian permisos, políticas, triggers ni la semántica VIGENTE/SUPERADA.
- La evaluación conserva sus límites de commit/rollback y la inmutabilidad de RF-53. La auditoría existente no se sustituye.

## Inspección previa de la BD oficial

Conexión a `sgpmp_dev`, usuario `member_dev`, transacción de solo lectura. No se ejecutó DDL/DML.

Se verificaron columnas, defaults, FK, índices y ausencia de triggers propios en `modulo3.telemetria_calidad`. `parametros_aplicados` es JSONB NOT NULL con default `{}`; no existe una restricción que garantice su contenido. No hace falta migración para corregir este flujo.

La lectura de los permisos oficiales quedó impedida por `permission denied for function fn_id_rol_actual`; no se alteraron permisos ni se trató esa falta de visibilidad como ausencia de datos RBAC.

## Pruebas

Resultado consolidado por ID de prueba, tomando su última ejecución y sin sumar dos veces las repeticiones:

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Telemetría, utilidades compartidas y parámetros dinámicos DEV-14: unitarias y contratos con fakes | 476 | 0 | 0 |
| PostgreSQL 18.4 real: 13 pruebas nuevas HTTP/JWT/RBAC y 12 regresiones de persistencia RF-62 | 25 | 0 | 0 |
| **Total distinto** | **501** | **0** | **0** |

Las 37 pruebas nuevas con fakes están incluidas en el primer grupo. No se cuentan adicionalmente como otras 37 aprobaciones.

La corrida ampliada original dio 475 aprobadas y un fallo en `test_lo_ingerido_permite_publicar_la_linea_base_vision`. Sus dobles aún usaban la especie singular y una firma `listar` sin filtro por área, anteriores a DEV-24. Se actualizaron exclusivamente esos dobles a `id_especies=[4]` y `listar(..., id_infraestructura=...)`, manteniendo el escenario monoespecie y sus aserciones. La repetición final del caso pasó. No se cambió producción de RF-24 ni se volvió a ejecutar toda la suite ampliada tras ese ajuste local del doble.

La primera corrida PostgreSQL detectó falta del privilegio local de actualización de `cuentas_usuarios.ultimo_acceso`. Se provisionó solo ese privilegio adicional de la autenticación, sin modificar políticas ni usar BYPASSRLS. La siguiente corrida confirmó los seis rechazos HTTP 422 y detectó que la base recién migrada no tenía configuración administrativa de RF-62. Las pruebas que calculan calidad ahora configuran explícitamente `rf62_k/m/n/umbral_drift/p` por el caso de uso administrativo existente de DEV-14 y preparan el muestreo de M09 en su transacción de prueba. No se añadieron defaults silenciosos a producción. Una prueba adicional verifica el 503 y la ausencia de evaluación persistida cuando falta esa configuración.

La corrida PostgreSQL definitiva terminó con 25 aprobadas, 0 fallidas y 0 omitidas. Los HTTP se ejecutaron con `TEST_ROL_APP=sgpmp_app`, sin superusuario ni BYPASSRLS. La siembra de datos y las aserciones administrativas se realizaron con la conexión del fixture; las otras 12 regresiones ejercitan directamente casos de uso y repositorios contra PostgreSQL, incluyendo rollback e inmutabilidad de RF-53.

Se validaron filtros combinados, rangos inclusivos, equivalencia entre zonas horarias, paginación, consulta de VIGENTE/SUPERADA, persistencia y lectura exactas del JSON, cambio real de configuración sin alterar snapshots anteriores, motivo y enlace de sustitución, JWT, RBAC y rechazo de parámetros inválidos antes de consultar el repositorio. `git diff --check` no reportó errores.

Evidencias temporales, no incluidas en la entrega Git:

- `.pytest_cache/g164_regresion.xml`: corrida ampliada original.
- `.pytest_cache/g164_vision_final.xml`: repetición aprobada del caso cuyo doble se actualizó.
- `.pytest_cache/g164_postgresql_validado.xml`: integración definitiva.
- `.pytest_cache/g164_resultados_consolidados.json`: 501 IDs únicos con su resultado final y fuente.

La preparación local aplicó las migraciones del repositorio hasta `e5a3c9b17d42` en `127.0.0.1:55426/sgpmp_g164_test`, utilizó `TEST_DATABASE_URL`, las protecciones del fixture de integración y transacciones exteriores con rollback. El clúster quedó detenido al finalizar. Los intentos iniciales bloqueados por el sandbox no se cuentan como pruebas aprobadas. El shim `fcntl` de Windows vive exclusivamente en el lanzador temporal de pruebas.

## Datos históricos y límites

La corrección garantiza metadatos para las nuevas evaluaciones de esta rama. Una evaluación histórica que ya contiene `{}` conserva ese dato: ni GET ni una migración inventan qué configuración se aplicó en el pasado. Su reparación requiere una operación de evaluación trazable y autorizada; no se actualizaron datos de la base oficial.

El archivo aportado de TC-M03-G164 informa 41 comprobaciones, 33 aprobadas y 8 fallidas. Además de las siete comprobaciones asociadas a los síntomas descritos en #625, contiene un fallo de `motivo_reevaluacion` en SUPERADA. Se comprueba que las evaluaciones nuevas sustituidas conservan motivo; no se realiza un backfill sobre registros históricos.

`openapi_test_snapshot.json` no está incluido en los adjuntos ni se encontró en el repositorio. Se verifica el OpenAPI generado y el contrato explícito de la issue; no se presenta esa comprobación como una ejecución del snapshot privado de QA.

El usuario autorizó el commit y el push de esta corrección, sin publicar PR. No se ejecutaron pruebas de escritura sobre el entorno oficial ni se certifica un despliegue.

## Alcance local

Rama `fix/inc-m03-103-g164-calidad-rf62`, reconstruida desde `dev` actualizado (`18b4ce67e8d23ed57fdfd108d44e0c2601e66604`). Solo se traslada la corrección de #625; no se arrastran los commits previos de DEV-22/DEV-24 como trabajo nuevo. El alcance frente a esa base es de siete archivos: cuatro de producción, dos de pruebas y este informe. La adaptación de los dobles de visión ya está integrada en `dev` y no forma parte del diff final. El usuario creó el PR #787 y autorizó corregir su rama; este trabajo no crea otro PR.

Se preservaron los archivos locales ajenos: `AGENTS.md`, `anotaciones/modulo_3/pendientes_integracion_aiot_por_tarea_y_pr.md` y `anotaciones/modulo_3/pendientes_por_area/`.

## Integración de la corrección con dev actualizado

Se preservan las cabeceras de otros autores, el alcance por finca incorporado por USAB-M03, el tipo `FechaHoraUtc` de PR-667 y las mejoras de contexto temporal, alertas y metadatos de DEV-43. `FUERA_DE_RANGO` conserva además `id_variable`, agregado por el motor actual. Los dobles HTTP y las aserciones del JSON se adaptan a esos contratos, sin retirar sus controles de producción.

La revalidación PostgreSQL utiliza una base nueva `sgpmp_g167_test`, creada desde cero con todas las migraciones de `dev` hasta la head `30168ab97bd4`, sin aplicar dependencias manuales. HTTP utiliza `TEST_ROL_APP=sgpmp_app`, sin superusuario ni BYPASSRLS. La primera corrida dio 22 aprobadas y tres fallidas por falta de SELECT local sobre el contexto de DEV-43. Se completaron únicamente los privilegios de lectura de `modulo3.periodos_inactividad` y `modulo9.variables_ambientales` en la base desechable; la repetición de esos tres casos terminó aprobada. No se modificaron políticas RLS ni bases oficiales.

Resultado consolidado de integración tras actualizar la base: 25 pruebas distintas aprobadas, cero fallidas y cero omitidas. Evidencias: `.pytest_cache/g164_rebase_pg.xml` y `.pytest_cache/g164_rebase_pg_final.xml`; los tres casos repetidos no se contabilizan de nuevo. Los resultados de 501 pruebas de la sección anterior corresponden a la entrega inicial y no se presentan como una ejecución sobre el nuevo padre.

La regresión ampliada sobre `dev` comprende 857 pruebas de telemetría, utilidades compartidas y parámetros DEV-14. Su primera corrida dio 851 aprobadas, una fallida y cinco errores de preparación: faltaba `tzdata`, ya fijada por el repositorio en `requirements.txt` como `tzdata==2026.5`. Se instaló esa versión únicamente en la `.venv` local y las seis pruebas afectadas pasaron al repetirlas; no se modificaron dependencias del proyecto ni se desactivaron verificaciones de zona horaria.

**Resultado final sobre dev actualizado: 882 pruebas distintas aprobadas (857 unitarias/HTTP y 25 PostgreSQL), 0 fallidas y 0 omitidas, considerando el último resultado de cada ID.** No se suman las ejecuciones anteriores ni los intentos interrumpidos del lanzador Windows. Evidencias adicionales: `.pytest_cache/g164_rebase_unit_final.xml`, `.pytest_cache/g164_rebase_tzdata_final.xml` y `.pytest_cache/g164_rebase_resultados_consolidados.json`.
