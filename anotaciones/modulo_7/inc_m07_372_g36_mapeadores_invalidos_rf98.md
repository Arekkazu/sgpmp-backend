# INC-M07-372-G36 · RF-98 · Rechazo de mapeadores inválidos

Incidencia [#1166](https://github.com/Arekkazu/sgpmp-backend/issues/1166) · TC-M07-04, grupo TC-M07-G036. RF-98, hoja «Modulo 7» de la especificación, celda B113, establece el código `MAPPERS_INVALIDOS` en FA-3.

## Causa y contrato

En `POST /integracion/contratos`, las restricciones de longitud y catálogo del DTO generaban `400 VAL_ENTRADA` antes de ejecutar la validación de FA-3. La lista vacía también exponía un mensaje de Pydantic en inglés. Ambos resultados se reprodujeron en `dev` (`5be1c26e`).

El DTO exige una lista de cadenas y conserva en OpenAPI el mínimo de un elemento y el catálogo permitido. El caso de uso comprueba que la lista tenga valores válidos antes de consultar el anexo o escribir la versión y su auditoría.

| Entrada o condición | Contrato resultante |
|---|---|
| `[]`, `["MAPPER_X"]` o un nombre alterado con espacios | HTTP 400 `MAPPERS_INVALIDOS`, campo `mapeadores` y mensaje en español |
| Lista con elementos nulos | HTTP 400 `VAL_ENTRADA` |
| Solicitud del Contador | HTTP 403 |
| `COMPROBANTE_NIC41` con el envío deshabilitado | HTTP 422 `MAPPER_NO_DISPONIBLE`, protección específica del tipo 06 para SIGCON |
| `["COMPRAS"]` con un anexo utilizable y permiso de registro | HTTP 201, contrato `PENDIENTE` y evento `CONTRATO_REGISTRADO` |

La corrección se limita al DTO de registro y sus pruebas. No requiere migración.

## Validación y re-prueba

Las pruebas HTTP usan JWT, RBAC y PostgreSQL 18 aislado con `sgpmp_app`. Consultan directamente las tablas de contratos y auditoría para verificar que los rechazos dejan cero filas de la versión y cero eventos `CONTRATO_REGISTRADO`. El control válido registra la misma versión y su evento.

La corrida final registró 19 pruebas de M07 sin base aprobadas y 5 integraciones aprobadas, incluidas las 3 de esta incidencia. Una integración existente de AAEF falló en la verificación del indicador de integridad de RF-102. El mismo fallo se reprodujo con el DTO original de `origin/dev` y la misma base aislada. No hubo pruebas omitidas.

La reejecución oficial de TC-M07-04 queda pendiente del despliegue a TEST.
