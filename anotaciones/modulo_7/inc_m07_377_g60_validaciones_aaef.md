# INC-M07-377-G60 · Validaciones de la consulta AAEF y del anexo

Incidencia [#1187](https://github.com/Arekkazu/sgpmp-backend/issues/1187) · TC-M07-273 y TC-M07-276, grupo TC-M07-G060. Rama basada en `origin/dev` `5be1c26e`.

## Contraste con los requisitos

- RF-95 §5.2, FA-2 y RNF-95.3 (hoja «Modulo 7» del Excel, B9, B21 y B25) prohíben credenciales en la URL. RF-AE01 §5.5 y RNF-AE01.3 (B258 y B266) remiten a esa prohibición. El listado de RF-95 no menciona `password` por nombre. Se aplica la prohibición general a ese parámetro.
- RF-95 FA-3 y FA-4 (B21), junto con §5.3, distinguen un token no válido para el canal de identidad de un cliente autenticado que no tiene habilitado el canal de consulta. La variante de TC-M07-271 que usa un cliente con solo `IDENTIDAD_M2M` debe esperar HTTP 403 `CLIENTE_NO_AUTORIZADO`. Los tokens inválidos o de sesión web corresponden a HTTP 401.
- RF-AE02 §5.10, FA-2 y CA-5 (B278, B282 y B285) exigen bloquear la revisión ante fallos de estructura, cobertura, cuadre de documento o resumen, cuentas y fechas. El Anexo AAEF v3.0 define los conteos y sumas del resumen.

## Causa y cambio

El filtro de la consulta no reconocía `password`. La comprobación ignora mayúsculas y audita el rechazo con HTTP 400 `CREDENCIALES_EN_URL` sin incorporar el valor en el evento. El filtro de acceso de Uvicorn conserva método, ruta y estado de las consultas AAEF y excluye la cadena de parámetros. La configuración de logs del proxy queda por comprobar en TEST.

El validador del anexo recorría diccionarios parcialmente validados al comprobar cuentas y fechas. Cuando faltaba `Lines`, se producía un `KeyError` antes de registrar el rechazo. Los controles de cuentas y fechas ahora trabajan sobre el documento validado. Un campo requerido ausente se informa como problema de estructura y cobertura. La prueba de cobertura también exige que la muestra genere los documentos 02 y 06 con líneas.

El cuadre del resumen contrasta `TotalInvoices`, `TotalDocuments`, `TotalGrossAmount` y `TotalNet` con los documentos de prueba. Los importes se comprueban antes de serializarlos. Cualquier control fallido devuelve HTTP 422 `ANEXO_VALIDACION_FALLIDA`, conserva el estado `BORRADOR` y registra el evento con los controles fallidos.

La corrección utiliza las tablas, los permisos y los eventos existentes. No requiere migración.

## Evidencia local

Se reprodujeron los tres resultados con el código anterior. La consulta con `password` devolvió 200. El anexo sin `Lines` devolvió 500. El anexo con `TotalNet` alterado devolvió 200 y pasó a revisión.

La corrida final registró 20 pruebas sin BD y 14 integraciones HTTP aprobadas, sin fallidas ni omitidas. La base PostgreSQL 18 se migró desde cero y sus conexiones se alinearon con la configuración UTC de la API. Las solicitudes HTTP usaron JWT, los permisos de M07 y el rol `sgpmp_app`. Se comprobó cada uno de los cuatro totales del resumen, la falta de líneas o de un tipo de documento, los demás controles del anexo, su transición válida, la consulta válida y los rechazos de credenciales y de autorización. Se verificó el filtro de acceso con una petición a Uvicorn en loopback y una credencial sintética.

## Re-prueba

Tras desplegar en TEST, repetir TC-M07-273 y TC-M07-276. Verificar en auditoría el rechazo de credenciales con valores sintéticos, revisar que los logs de infraestructura no incluyan esos valores y comprobar que el anexo solo pasa a revisión con una muestra válida. Ajustar la expectativa de TC-M07-271 para el cliente autenticado con solo `IDENTIDAD_M2M`.
