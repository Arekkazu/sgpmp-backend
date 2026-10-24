# Narrativa de Diseño y Ejecución — TC-M04-G098

## Resumen Ejecutivo
El grupo TC-M04-G098 contempla la verificación de requerimientos no funcionales de alta criticidad para el Módulo 4 (RF-73): disponibilidad del 99.5% y latencia P95 <= 2 segundos en consultas sobre un volumen histórico de 50 millones de eventos.

## FASE SEPARADA — DISPONIBILIDAD Y VOLUMEN
1. Disponibilidad (TC-M04-054): Un indicador de 99.5% exige una observación en ventana larga (semanas/meses). En el sandbox transaccional de 120s se realiza una evaluación proxy de estabilidad inmediata utilizando checks de salud y consulta constante con tasa de error < 0.5%.
2. Volumen Extremo (TC-M04-055): 50 millones de registros no pueden residir ni ser inyectados en la base de datos de sandbox sin desbordar los límites de almacenamiento y tiempo de ejecución. Este subcaso queda formalmente delegado a la FASE SEPARADA con ambiente de staging pre-poblado.

## Hallazgos Arquitectónicos
- Se identificó la falta de particionamiento declarativo en PostgreSQL para la entidad `modulo4.eventos_auditoria_m04`. Para garantizar un P95 <= 2s con 50M de registros, el particionamiento por rango de fecha es imperativo.
