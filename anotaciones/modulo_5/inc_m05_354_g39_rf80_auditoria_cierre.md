# INC-M05-354-G39 · RF-80 — Auditoría del ICA al cerrar el ciclo

El cierre RF-38 calcula y persiste el resultado final de RF-74 antes de cerrar la fase. El trigger de `resultado_ica` escribía directamente en la bitácora de M05 con `fecha_evento` y el identificador del activo. Omitía `fecha_emision` y el ciclo. El sellado calculaba el hash de esa fila, que quedaba visible en la API con ambos campos nulos. El caso TC-M05-G39 A02 del reintento de QA registró este comportamiento.

La revisión `a107980ae001` se aplica sobre `603631775892` y cubre los cuatro emisores SQL. Usa `clock_timestamp()` al emitir el evento, conserva la fase en los nuevos resultados ICA y recupera el ciclo de esa fase. Consumo y medicamento toman el ciclo y la fase del registro original del ledger mediante el UUID de origen. Costos productivos toma el ciclo de su propia fila.

La bitácora identifica la ausencia de activo o ciclo antes de calcular el hash. Conserva el detalle existente y agrega los campos faltantes. PostgreSQL rechaza nuevas filas que carezcan de fecha de emisión y mantiene las restricciones de tipo, resultado y causa de registros incompletos. Los `CHECK NOT VALID` se aplican a nuevas escrituras y preservan el contenido y los sellos del historial.

El mismo contrato de lista y detalle permite verificar el evento de cierre y filtrarlo por activo y ciclo. Los controles de permisos y el alcance por finca se mantienen en las políticas existentes.

## Validación

- En `dev` (`dfc4a682`), el cierre respondió HTTP 200 y el evento ICA apareció con `fecha_emision` nula en la lista.
- Con la revisión aplicada, el flujo de costeo, cierre, ICA y bitácora pasó en PostgreSQL 18 con JWT y el rol `sgpmp_app`. La prueba comprobó el cierre de la fase, el filtro por activo y ciclo, el detalle del evento, su sello y la actualización posterior del ICA asociada a la misma fase.
- Las regresiones verificaron los emisores de alimento, medicamento y costos productivos, el rechazo de una emisión sin fecha, la causa para contexto faltante, la deduplicación concurrente y la conservación de los sellos históricos V1 y V2.
- Pasaron 100 casos distintos de integración y 57 pruebas focalizadas de auditoría con dobles. Las tres verificaciones pendientes de la primera corrida de integración pasaron tras sembrar el estado ACTIVO en el caso de costos y usar una copia local del esquema migrado para las dos pruebas que requieren una base efímera.

Queda pendiente desplegar la revisión en TEST y repetir TC-M05-G39 A02.

Referencia [issue #1079](https://github.com/Arekkazu/sgpmp-backend/issues/1079).
