# INC-M07-378-G61 · RF-AE02 — Importe mínimo del Mapper de Compras

Incidencia [#1188](https://github.com/Arekkazu/sgpmp-backend/issues/1188) · TC-M07-281, grupo TC-M07-G061. Rama basada en `origin/dev` `5be1c26e`.

## Contraste con RF-AE02 y SIGCON

RF-AE02 §5.3 y RF-96 (hoja «Modulo 7», B278 y B37) indican que el tipo 02 exporta el costo de origen a dos decimales por truncamiento. El requisito expresa `Value > 0` para el tipo 06. La restricción del receptor confirma por qué una compra tipo 02 de importe cero tampoco es contabilizable. SIGCON crea el asiento de la factura a partir de su importe y rechaza las líneas del asiento con débito y crédito simultáneamente en cero. Esta comprobación corresponde al código fuente de SIGCON, sin envío de datos al ambiente externo. [Importación de compras](https://github.com/Server-IA/Sigcon-Backend/blob/a9cd1dab4e76061379cd1f5277ab0b3315f2c6d7/src/main/java/com/sigcon/backend/invoices/domain/service/InvoiceService.java#L383-L409) · [Validación de líneas del asiento](https://github.com/Server-IA/Sigcon-Backend/blob/a9cd1dab4e76061379cd1f5277ab0b3315f2c6d7/src/main/java/com/sigcon/backend/general/accounting/journal/domain/service/JournalEntryService.java#L186-L201).

M06 acepta costos positivos de hasta cuatro decimales y persiste `monto_costo` en `numeric(18,4)`. Se reprodujo en PostgreSQL el caso de `0.0049`: el costo se registró y el período cerró. La consulta AAEF devolvió HTTP 200 con una factura cuyo `Value`, `Subtotal` y `TotalPayment` eran cero.

## Contrato de la corrección

El Mapper comprueba el valor de cada línea después del truncamiento. Una línea con valor menor o igual a cero produce `MAPPER_FALLIDO` en el campo `Value`, aunque otras líneas de la misma factura sean válidas. La consulta y la vista previa devuelven HTTP 422. RF-97, fase 4 y FA-4 (B76 y B77), establece que un fallo del Mapper cancela la salida completa. La consulta externa conserva el evento `SOLICITUD_RECHAZADA` con el código del error.

`0.01` se exporta como `0.01` y `100.999` como `100.99`. La precisión del costo original, la lógica del tipo 06 y los permisos siguen vigentes. No requiere migración.

## Evidencia local

La corrida final registró 25 pruebas sin BD y 4 integraciones HTTP aprobadas, sin fallidas ni omitidas. La integración preparó el costo con el DTO y el caso de uso de M06, cerró el período y ejercitó ambas rutas HTTP con JWT, RBAC y `sgpmp_app` en PostgreSQL 18 aislado. Comprobó que la consulta externa registra el rechazo sin hash de contenido y que M06 conserva `0.0049`. El flujo exitoso de AgroFusion siguió pasando.

## Re-prueba

Tras desplegar en TEST, repetir TC-M07-281 y TC-M07-282. Con un período cerrado de prueba que contenga una factura válida y un costo individual de `0.0049`, comprobar HTTP 422, campo `Value`, ausencia de documentos parciales y evento de rechazo. El importe original debe seguir en M06.
