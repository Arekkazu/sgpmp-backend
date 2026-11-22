# INC-M05-277-G20 · RF-77 — Promedio no calculable

Fecha: 2026-11-08. Identidad Git consultada: Leandro.
Issue: [#963](https://github.com/Arekkazu/sgpmp-backend/issues/963).
Rama: `fix/inc-m05-277-g20-promedio-no-calculable-rf77`.
Base: dev actualizada mediante fetch/fast-forward a `3251d78d2c5822624dde988a94a37331610d1cef` antes de crear la rama. No se arrastraron #958, #960 ni #961.

## Evidencia y definición aplicable

Se leyeron resultado_TC-M05-G20.json y resultado_TC-M05-G20.html de Downloads. El JSON registra 7 checkpoints: 6 correctos y un fallo B02 / TC-M05-015. La issue no tenía comentarios adicionales al revisarla.

RF-77 Restricción 6 exige usar la cantidad actual del lote al generar el reporte y, si es cero, informar gasto_promedio_individuo = NO_CALCULABLE con la causa “La cantidad actual del lote es cero. No es posible calcular el promedio por individuo.” Se confirmó ese texto en Especificacion-Requerimientos-Modulo5.md. No fue necesario redefinir el requisito.

## Diagnóstico confirmado

Se revisó el flujo HTTP, DTO, caso de uso, entidad, puertos M02, calculadora, repositorio de reporte, ORM/JSON, consulta, historial, regeneración, resultado asíncrono y exportación.

El generador ya evita dividir por cero y asigna correctamente la causa. El dominio representa ese estado mediante promedio=None más causa explícita. ReporteGastoResponse solo admitía Decimal o None y propagaba el null al JSON público. La reproducción inicial falla exactamente porque obtiene None en lugar de NO_CALCULABLE; se conserva su JUnit temporal.

También se confirmó una pérdida al recuperar el reporte: el snapshot guardaba encabezado, total y filtros, pero no el promedio ni la causa. Una corrección limitada al POST volvería a perder ese estado en GET e historial.

## Cambios implementados

1. El schema admite Decimal, el literal cerrado NO_CALCULABLE y None. Convierte None al literal únicamente cuando existe una causa explícita. Un promedio no aplicable conserva null y un promedio calculable conserva su precisión y serialización decimal.
2. El dominio y el motor siguen usando Decimal/None. No se cambian fórmulas, denominadores, tipos de activo, reglas de baja ni totales.
3. La reconstrucción del resultado async delega al schema la validación del valor. Admite resultados previos con null + causa, resultados con el literal y valores numéricos.
4. El repositorio conserva promedio y causa en resumen_promedio dentro del json_parametros existente, y los hidrata al recuperar el snapshot. Los parámetros de regeneración se mantienen; el lector de filtros ignora el resumen adicional. No se modifica el objeto de filtros original al guardar.
5. El snapshot conserva el promedio de la fecha de generación aunque cambie después la población. Regenerar calcula con la cantidad actual, como establece el flujo existente.

La ampliación JSON evita nuevas columnas y no almacena el literal en un campo monetario. El repositorio continúa usando flush()/refresh(); el commit y rollback permanecen en el caso de uso.

## Contrato resultante

| Condición | gasto_promedio_individuo | causa |
|---|---|---|
| Lote con cantidad cero y causa explícita | NO_CALCULABLE | Se conserva la causa informada |
| Lote con población vigente | Decimal serializado como antes | null |
| Promedio calculable igual a cero | Cero numérico serializado como antes | null |
| Individual o agregado sin promedio aplicable | null | null |

El estado se mantiene en generación, consulta de nuevos snapshots, historial, regeneración y polling. OpenAPI del schema incorpora el literal como alternativa cerrada; no se acepta cualquier cadena.

No se cambian códigos HTTP, rutas, permisos ni contratos de exportación. CSV conserva sus columnas de detalle; PDF y CSV se prueban por ejecución y descarga. No se agrega el literal técnico a textos de archivos ni se hace una revisión visual del PDF, cuyo generador no cambió.

## BD y RBAC

La base exclusiva local se migró desde cero a b7e2d94c1a68. Se inspeccionaron columnas de reporte_gastos_acumulados (incluido JSONB), triggers, versión, enums y permisos de los recursos 51/57. No se requiere migración ni backfill. No se modifican restricciones, funciones, triggers, RLS o permisos de producción.

Las tablas M05 inspeccionadas no tienen RLS en esta revisión de dev; no se atribuye a esta corrección aislamiento de filas nuevo. La generación conserva el alcance existente por finca mediante M02 y sus adaptadores. La integración HTTP usa sgpmp_app, sin superusuario/BYPASSRLS, con JWT real y restricciones activas.

## Pruebas finales

| Grupo distinto | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/supplies: dominio, schema y fakes | 31 | 0 | 0 |
| Integración HTTP/PostgreSQL 18 real | 13 | 0 | 0 |
| Total sin repetir corridas | 44 | 0 | 0 |

Las 31 incluyen 13 regresiones nuevas y 18 pruebas existentes. Las reproducciones y repeticiones no se suman.

La integración cubre:

- Semilla de lote con 50 individuos; POST de medicamento por 50.000 COP; POST RF-45 de baja de 50; verificación SQL de cantidad_actual=0 y estado BAJA; POST de reporte con literal, causa y total/desglose conservados.
- GET de reporte, historial y regeneración con el mismo estado.
- Cantidades vigentes de 50 y 20: promedio 1.000 y 2.500, respectivamente, con nota de bajas cuando corresponde.
- Snapshot numérico generado antes de una baja total: consulta conserva el promedio original y regeneración refleja el estado actual.
- Individual y agregado: promedio no aplicable null.
- Resultado async persistido mediante repositorios reales y lectura HTTP de polling, tanto para null + causa como para el literal. No se ejecuta el scheduler ni la distribución de workers de producción.
- Exportación/descarga CSV y PDF sin errores por mezclar el literal con operaciones decimales.
- Productor propietario autorizado; Productor ajeno rechazado al generar; Veterinario sin permiso y JWT ausente.
- Sin gastos: distinción entre promedio cero calculable y población cero no calculable.
- Fallo controlado después del flush del snapshot: rollback del reporte/JSON y conservación del medicamento previo.

La prueba unitaria verifica precisión decimal, representación del resultado del worker, schema cerrado, snapshot sin mutación de parámetros y compatibilidad con snapshots antiguos sin resumen.

## Entorno, incidencias de preparación y límites

TEST_DATABASE_URL apunta únicamente a sgpmp_inc963_test en 127.0.0.1:55429; TEST_ROL_APP=sgpmp_app. Se mantienen las protecciones del fixture y use_insertmanyvalues=False. La siembra usa SQL local y las operaciones de medicamento, baja, reporte y lectura usan HTTP.

La primera preparación intentó modificar cantidad_inicial y fue rechazada por su trigger de inmutabilidad. Se corrigió la semilla para insertar directamente 50 individuos, sin desactivar controles. Se completaron en el lanzador local los permisos de INSERT de eventos de baja y UPDATE de detalle/fase necesarios para ejecutar RF-45; esas ACL locales no acreditan el estado de TEST o DEV. El shim fcntl está únicamente en los lanzadores de pytest por la dependencia existente del SDK en Windows.

Los reportes síncronos antiguos sin resumen no conservan la población histórica necesaria para reconstruir el promedio. Se leen sin inventar valores y pueden regenerarse con el estado actual. No se actualizan datos históricos ni se presenta regeneración como recuperación exacta del pasado.

Al finalizar se eliminó únicamente sgpmp_inc963_test y se detuvo el clúster local iniciado para estas pruebas. Se verificó que las demás bases permanecieran intactas y se conservaron logs, lanzadores y evidencias.

No se modificó UI ni se validó un despliegue. No se ejecutaron escrituras en TEST o DEV oficiales. Queda pendiente repetir B02 de TC-M05-G20 tras integrar/desplegar. La suite emitió únicamente el aviso existente de deprecación Starlette/httpx.

## Entrega

Dos archivos de producción, dos de pruebas y dos informes:

- src/supplies/infrastructure/schema/reporte_gasto_schema.py
- src/supplies/infrastructure/repositories/reporte_gasto_repository.py
- tests/supplies/test_inc_m05_277_g20_promedio_no_calculable.py
- tests/integration/test_inc_m05_277_g20_promedio_no_calculable_integration.py
- anotaciones/modulo_5/inc_m05_277_g20_rf77_diagnostico.md
- anotaciones/modulo_5/inc_m05_277_g20_pr_preparado.md

Cabeceras con fecha real, identidad Git consultada y tarea/RF; filas previas y archivos ajenos preservados. Evidencias temporales excluidas del commit: .pytest_cache/inc963_reproduccion.xml, inc963_unit.xml, inc963_integracion.xml, inc963_preflight.json, inc963_evidencia_final.json, inc963_postgres.log y lanzadores inc963_*.py.

No se realiza commit, push ni publicación de PR sin la instrucción correspondiente del usuario para esta entrega.
