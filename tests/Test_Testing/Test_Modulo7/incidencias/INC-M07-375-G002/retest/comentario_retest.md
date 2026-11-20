Retest aprobado el 20-nov-2026 en TEST (backend rc.80).

Corrección: Todo error trae `field` (el primer campo de `fields`, o `null`), además de `error_code`, `message`, `fields` y `timestamp` (#1169, dentro de #1190/#1189, rc.80).

Verificación: Las 3 solicitudes inválidas devuelven `error_code`, `field`, `fields`, `message` y `timestamp` (verificacion_cuerpo_error.json). El caso TC-M07-G002 pasa 62 de 62; la comprobación «el cuerpo trae field» ya aprueba.

RUN: `RUN-G002-V2-20261120-105634`. Evidencia en `incidencias/INC-M07-375-G002/retest/`. Se puede cerrar.
