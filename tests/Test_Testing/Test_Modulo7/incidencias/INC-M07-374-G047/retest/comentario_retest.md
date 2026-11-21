Retest aprobado el 20-nov-2026 en TEST (backend rc.80).

Corrección: Corrección de datos del DBA: credenciales de los clientes 1 y 2 re-emitidas con bcrypt (cost 12), incluida la credencial REVOCADA del cliente 1 (ahora `$2a$`, 60 caracteres).

Verificación: Las 20 credenciales de `modulo7.identificadores_apis` están en bcrypt (60 caracteres, prefijo `$2`); ninguna fila no bcrypt (verificacion_hashes.json, solo prefijo y largo). El caso TC-M07-G047 pasa 63 de 63. En un primer retest (10:59) quedaba 1 credencial revocada del cliente 1 con hash de 64 caracteres; el DBA la corrigió y el retest final aprobó.

RUN: `RUN-G047-V3-20261120-121219`. Evidencia en `incidencias/INC-M07-374-G047/retest/`. Se puede cerrar.
