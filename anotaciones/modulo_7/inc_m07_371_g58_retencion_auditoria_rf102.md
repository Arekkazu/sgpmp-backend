# RF-102 — Retención y archivado histórico de auditoría · #1165

La ficha de RF-102 en la hoja **Modulo 7** del Excel establece cinco años en almacenamiento primario para eventos generales y diez para `PAQUETE_AAEF_CONSULTADO`, `VISTA_AAEF_GENERADA` y `CONTRATO_ACTIVADO`. La restricción 4.7, la fase 10, FA-5 y CA-14 a CA-16 prevén traslado controlado, conservación del SHA-256, consulta posterior y alerta en caso de fallo. En `dev` la tabla que usa RF-102 ya protegía los registros activos contra modificaciones y eliminaciones. Faltaban la política temporal y el ciclo de archivado.

La política de base de datos toma la fecha más reciente entre ocurrencia y registro, en UTC. Esto evita descontar el tiempo anterior a la persistencia de un evento asíncrono. El traslado se habilita una vez superado el plazo en años calendario. La tabla histórica conserva las columnas originales y el mismo UUID y hash. Un registro de identidades reserva cada UUID también después del traslado.

El trabajo se ejecuta al arrancar el backend y se repite cada hora. Ante fallo reintenta en 15 minutos. Cada transacción procesa hasta 100 eventos y usa un bloqueo transaccional para que otra réplica omita el mismo lote. Ante un hash de origen inválido, la fila se mantiene activa y el recorrido puede continuar con las demás. Si la copia difiere o la transacción falla, el lote se revierte. El trabajo escribe un log crítico e intenta dejar una alerta crítica en M01 para los Administradores con permiso de auditoría. Si M01 está inaccesible, queda el log de servidor como evidencia del fallo.

La migración `a7c3e91f5b20 → f11651020001` crea el archivo lógico en PostgreSQL. Solo la identidad de servicio puede ejecutar la función de traslado. Esta comprueba el plazo y el trigger exige una copia idéntica antes de retirar la fila activa. El rol de la API tiene acceso de lectura al archivo y a la vista de historial, sin permisos de escritura sobre ellos. El descenso de revisión se bloquea si el histórico contiene registros.

La consulta y exportación de `/integracion/auditoria` usan ambos almacenes con el mismo contrato, permisos, filtros e indicador de integridad. La tabla histórica forma parte de los respaldos del mismo PostgreSQL. Las pruebas locales verifican los límites con antigüedad simulada. El cumplimiento a lo largo de años también requiere conservar los respaldos y verificar su restauración en el ambiente de operación.

## Evidencia local

19 pruebas de M07 sin base y 8 integraciones distintas aprobadas en PostgreSQL 18. Las integraciones incluyen cinco casos de la incidencia y tres regresiones de la integración AAEF. Se comprobaron los límites de ambas categorías, la consulta y exportación bajo JWT, el rechazo de accesos y mutaciones, la concurrencia, el rollback posterior a la copia, el reintento, el registro corrupto y los avisos críticos independientes por Administrador. Se completaron en la base aislada las concesiones preexistentes de M01, M02, M06 y M09 necesarias para ejecutar las pruebas con `sgpmp_app`.

La revisión se aplicó desde cero y también sobre la cabeza previa mediante descenso con el histórico vacío y nueva aplicación. Alembic reportó una sola cabeza.

Para repetir TC-M07-G058 en TEST, aplicar la revisión y desplegar el backend. Usar un entorno de pruebas aislado con eventos de edad controlada a ambos lados de los límites. Verificar el traslado y los UUID y hashes en consulta, y provocar un fallo controlado antes del commit para comprobar el rollback, el aviso y el reintento. La validación local se realizó sin escrituras sobre DEV o TEST oficiales.
