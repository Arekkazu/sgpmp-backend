Retest aprobado el 20-nov-2026 en TEST (backend rc.80).

Corrección: Nombre de cliente único sin distinguir mayúsculas ni espacios: `409 CLIENTE_DUPLICADO` en `nombre` (#1170, dentro de #1190, rc.80; índice `uq_cliente_externo_nombre`, migración `b4d2f8e61c07`).

Verificación: El nombre repetido (idéntico, en mayúsculas y con espacios sobrantes) responde 409; un nombre nuevo sigue respondiendo 201 (verificacion_nombre_duplicado.json, con rollback). El caso TC-M07-G043 pasa 31 de 31 y el conteo de clientes no cambia.

RUN: `RUN-G043-V2-20261120-105748`. Evidencia en `incidencias/INC-M07-373-G043/retest/`. Se puede cerrar.
