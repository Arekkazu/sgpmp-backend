# TC-M04-G060 — BLOQUEADO

## Decisión del caso

Grupo TC-M04-G060, RF-69 v2.1; originales TC-M04-166, TC-M04-167, TC-M04-168 y TC-M04-169. El responsable QA decidió **BLOQUEADO** el 2026-10-28. El sandbox de TEST ejecuta todas las peticiones de un mismo RUN sobre una única conexión y sesión de base de datos, por lo que no puede reproducir activaciones concurrentes reales; hacerlas fuera del sandbox dejaría cambios irreversibles en TEST.

| Caso | Qué se quería comprobar | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-166 | Dos versiones de la misma llave activadas a la vez desde dos sesiones: solo una debe prosperar. | BLOQUEADO | El RUN no proporciona dos transacciones independientes para competir por la misma llave. |
| TC-M04-167 | Dos solicitudes simultáneas para activar la misma versión: una activación y ningún evento duplicado. | BLOQUEADO | La concurrencia real tampoco puede reproducirse en la sesión compartida. |
| TC-M04-168 | Cinco versiones de la misma llave a la vez, diez veces: siempre una sola ACTIVO. | BLOQUEADO | La ráfaga exige transacciones separadas y un estado final fiable. |
| TC-M04-169 | Cuatro llaves diferentes activadas a la vez: las cuatro deben prosperar. | BLOQUEADO | El sandbox comparte la conexión incluso cuando las llaves son diferentes. |

**RUN oficial: no.** `resultado.json` conserva `oficial=false`, las cuatro comprobaciones API en BLOQUEADO y ninguna incidencia de producto. **Qué falta:** un entorno que permita transacciones concurrentes reales con limpieza garantizada (ver «Desbloqueo»).

## Qué se quería probar

La matriz original de G060 (`tests/Test_Testing/Test_Modulo4/Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila TC-M04-G060) pide: **166**, dos versiones APROBADAS con notas de la misma llave, activadas desde dos sesiones al mismo tiempo; solo una activación exitosa, la otra cancelada y revertida, una ACTIVO y conflicto auditado. **167**, dos solicitudes idénticas a una versión APROBADA con notas; una sola activación, sin eventos duplicados, doble deprecación ni estados parciales. **168**, cinco versiones APROBADAS de la misma llave activadas juntas, en diez repeticiones; exactamente una ACTIVO en cada repetición, sin estados intermedios inconsistentes. **169**, cuatro versiones de cuatro llaves distintas activadas juntas; las cuatro completadas y exactamente una ACTIVO por llave. Son comprobaciones de API; la matriz no exige UI para este grupo.

El requisito da el oráculo, no el comportamiento observado en este intento:

- **Restricción 12, RF-69 v2.1, líneas 1908-1909:** «No se permite la activación simultánea de múltiples versiones del mismo tipo de modelo en procesos concurrentes.»
- **Fase 5, líneas 2078-2080:** «El sistema verifica concurrencia: no puede haber otra operación de activación en curso para el mismo tipo_modelo.»
- **RNF-02, líneas 2354-2356:** «Garantía fuerte: nunca dos versiones ACTIVO del mismo tipo_modelo simultáneamente.»
- **E5, líneas 2183-2192:** «Ambas en la misma transacción; si alguna falla, se revierte todo.» También exige registrar ambos eventos en RF-73 con el mismo `correlacion_id`.
- **RFC-009, líneas 1784 y 2410:** la unicidad y la validación de concurrencia se aplican por la llave «(`tipo_modelo`, `componente`)».

Fuente consultada: `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo4 (1).md`, líneas indicadas.

## Por qué no se puede probar hoy en TEST

El sandbox abre una transacción para cada RUN y la revierte al cerrarlo. Dentro de ese RUN, todas las peticiones reciben la **misma sesión y conexión** de base de datos. Esto se ve en `src/shared/rollback/infraestructure/testing_sandbox.py:35-68` de `origin/test` (`daefc3a5`): crea una conexión y una sesión para el RUN y devuelve esa misma sesión en las peticiones posteriores.

Por eso, enviar dos peticiones a la vez con el mismo RUN no crea dos transacciones independientes. Ambas usan a la vez la conexión compartida; esa interferencia impide medir si el producto protege una activación frente a otra. Dos RUN distintos tampoco sirven: sus transacciones aisladas no ven los cambios sin confirmar del otro RUN y no compiten por la misma versión ACTIVO preparada para el experimento. Fuera del sandbox, las activaciones escribirían cambios reales en TEST que esta orden no permite ejecutar ni limpiar con garantía.

**Clasificación:** impedimento del entorno de pruebas, con certeza **CONFIRMADA** para el diseño de `origin/test`; el estado exacto del despliegue en TEST no se verificó. El bloqueo tiene impacto **ALTO** porque deja sin comprobar una garantía relevante de unicidad y concurrencia, sin vía segura alternativa hoy. No es una incidencia ni un defecto confirmado del producto.

## Qué se observó en el intento

En `RUN-G060-V1-20261028-162607`, autorizado con `AUT-G060-V1-20261028`, `resultado.json` registró **72 solicitudes**: 55 con HTTP (31 respuestas 200, 13 respuestas 201 y 11 respuestas 500) y 17 sin respuesta de red. El ejecutor cortó la prueba tras tres respuestas 500 consecutivas; los cuatro casos quedaron BLOQUEADO y ninguna comprobación de concurrencia quedó concluida.

| Momento | Observación verificable | Alcance de la observación |
|---|---|---|
| Preparación | Se registraron las versiones 112-124 con HTTP 201. Las 112, 113, 115 y 114 terminaron fuera de orden porque los registros se lanzaron en paralelo. | La preparación ya compartía la sesión; no era todavía una prueba válida de activación concurrente. |
| Preparación y lecturas | Hubo respuestas 500 intermitentes en PATCH de notas de la 115, lecturas de auditoría y listados. | Los 500 impiden usar esas lecturas como verificación de estado o auditoría. |
| TC-M04-166 | Las activaciones de 116 y 117 se enviaron a la vez; recibieron HTTP 200 y 500, respectivamente. Las lecturas posteriores también tuvieron 500. | El solapamiento temporal está registrado, pero falta un estado final fiable; no hay veredicto de producto. |
| TC-M04-167 a 169 | La preparación avanzó parcialmente; la ráfaga de 168 y el DELETE quedaron sin respuesta de red tras el corte. | No hubo comprobación completa de esos casos; el cierre no quedó acreditado en ese intento. La recuperación posterior acreditó el rollback. |

Los 500 son **compatibles con la limitación del sandbox** al usar simultáneamente una sola conexión; la evidencia disponible no demuestra su causa exacta ni un defecto funcional. La automatización QA tenía además dos fallos ya corregidos en `ORD-G060-003`: los registros se lanzaban en paralelo y el DELETE no se intentó tras el corte. El ejecutor actual serializa la preparación y reserva el disparo simultáneo para las activaciones previstas; también intenta el cierre después de un corte. Esta corrección local no cambia la evidencia histórica ni elimina la limitación del sandbox.

## Riesgo que queda abierto (sin veredicto)

La lectura de `origin/test` (`daefc3a5`) muestra que `src/prediction/application/use_cases/versiones_modelo/activar_version_modelo_use_case.py:38-70` lee la versión ACTIVO previa, la depreca y activa la nueva; `src/prediction/infrastructure/repositories/version_modelo_repository.py:162-173` hace esa lectura sin un bloqueo por llave visible. La Fase 5 exige que no haya otra activación en curso para la misma llave. Esto se clasifica **DEFECTO_FUNCIONAL_CANDIDATO**, con certeza **NO DETERMINADA**: solo una prueba pública de activaciones concurrentes con transacciones separadas puede decidirlo.

La migración `alembic/versions/cf12e716a4ec_rfc006_rfc009_rfc011_taxonomia_camara_auditoria.py:128-130` define un índice único parcial para ACTIVO por (`tipo_modelo`, `componente`); `alembic/versions/a9d4d253ac97_fix_trg_unicidad_produccion_rfc009.py:23-48` ajusta el trigger de unicidad. No se comprobó si esas migraciones están aplicadas en TEST ni qué respuesta da la API ante un choque. El índice puede proteger el estado final, pero no acredita por sí solo la respuesta, auditoría y reversión exigidas. **Incidencias de producto: ninguna confirmada ni creada.** No se asigna equipo de producto ni causa raíz por esta hipótesis.

## Desbloqueo — qué se necesita y de quién

1. **DBA o Implementación:** habilitar un entorno donde las peticiones simultáneas usen conexiones y transacciones independientes sobre datos compartidos, con restauración garantizada después de la prueba. Opciones a evaluar: una base dedicada o restaurable por snapshot para QA; o autorización expresa para escrituras reales, con limpieza y comprobación a cargo de DBA. El responsable QA deberá autorizar el RUN correspondiente antes de ejecutarlo.
2. **Desarrollo:** valorar si el sandbox de `test-control` puede dar una conexión por petición sobre los datos compartidos del RUN y mantener una reversión fiable. Es una alternativa técnica por estudiar, no una solución verificada.
3. **DBA:** confirmar si el índice único parcial y el trigger de las migraciones citadas están aplicados en TEST. Esa comprobación no sustituye la prueba concurrente por API.

En un entorno apto, `g060.mjs` ya está preparado para disparar activaciones simultáneas con tiempos, comprobar el resultado por llave y repetir diez veces el escenario 168. Una nueva evaluación necesita decisión y autorización explícitas del responsable QA; esta orden solo documenta el bloqueo.

## Cierre y rollback del intento

En el intento V1, el DELETE de cierre no obtuvo respuesta de red; `resultado.json` conserva `cierre.run.cierre_http=null` y `cierre.rollback.verificado=false` como registro histórico de ese intento. El responsable QA autorizó y aprobó la recuperación **AUT-G060-V1-REC-20261028 (SOL-G060-005)**, ejecutada el **2026-10-29 a las 00:45 UTC**. En ella, `DELETE /test-control/runs/RUN-G060-V1-20261028-162607` respondió **HTTP 404** y `estaba_abierto=false`: el sandbox ya se había revertido por inactividad, conforme al mecanismo de `src/shared/rollback/infraestructure/testing_sandbox.py:13-33`.

La recuperación registró un inicio de sesión HTTP 200 y, fuera del RUN, **13 GET** de las versiones 112-124: todos respondieron **HTTP 404 `VERSION_MODELO_NO_ENCONTRADA`**, sin cabecera de RUN. Los cuatro listados ACTIVO respondieron HTTP 200 y coincidieron con la línea base: **MODELO_ESPECIES_GRANDES/SIN_COMPONENTE**, ninguna; **MODELO_ESPECIES_MEDIANAS/SIN_COMPONENTE**, 43; **MODELO_RIESGO_CONTAGIO/SIN_COMPONENTE**, 57; **MODELO_AVES/DETECTOR**, ninguna. La evidencia de recuperación consigna `rollback_verificado=true` y ninguna observación. Por tanto, **el rollback de los datos del RUN quedó acreditado**: no quedan en TEST las versiones 112-124 del RUN y las versiones ACTIVO de las cuatro llaves coinciden con la línea base. El registro QA cerró el RUN como **CERRADO**, con rollback **CONFIRMADO** y clasificación **TECNICO**; la operación auxiliar RECUPERAR quedó en **ROLLBACK_CONFIRMADO**.

Persisten **13 archivos ONNX** de las versiones 112-124 en `MODELOS_STORAGE_PATH`, fuera del rollback transaccional; no hay evidencia de correos enviados. La recuperación acredita la reversión de los datos comprobados, no la eliminación de esos archivos. La decisión **BLOQUEADO** permanece porque no se pudieron comprobar activaciones concurrentes reales.

## Evidencias

- [resultado.json](resultado.json): estados BLOQUEADO, 72 solicitudes y cierre no verificado en el intento V1; conserva el estado histórico previo a la recuperación.
- [preflight.json](preflight.json): preparación y Newman 6.2.2 verificados antes del intento.
- [contexto_operacion.json](contexto_operacion.json): autorización `AUT-G060-V1-20261028` y alcance V1.
- [newman/](newman/): reportes JSON y HTML realmente generados; no sustituyen las lecturas finales faltantes.
- [recuperacion-20261029004545.json](recuperacion-20261029004545.json) y [su contexto](recuperacion-20261029004544.contexto.json): recuperación autorizada, comprobaciones posteriores fuera del RUN y rollback acreditado.

Referencias de lectura local de código en `origin/test` (`daefc3a5`): `src/shared/rollback/infraestructure/testing_sandbox.py:14-68`; `src/prediction/application/use_cases/versiones_modelo/activar_version_modelo_use_case.py:38-70`; `src/prediction/infrastructure/repositories/version_modelo_repository.py:162-173`; migraciones `cf12e716a4ec:128-130` y `a9d4d253ac97:23-48`. No se consultó TEST para esta reescritura.
