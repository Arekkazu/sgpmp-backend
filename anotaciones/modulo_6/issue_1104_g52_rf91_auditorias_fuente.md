# RF-91 — Comprobación de auditorías fuente · #1104

La revisión se hizo sobre `origin/dev` en `08e65db4`. La hoja **Modulo 6** de `ESPECIFICACION_REQUERIMIENTOS_COMPLETA.xlsx`, en el proceso RF-91 pasos 5–7 y restricción 7, define qué bitácora certifica cada origen y el tratamiento de fuentes temporalmente indisponibles.

| Evidencia de origen | Comprobación |
| --- | --- |
| `REGISTRO_MANUAL` | RF-52 debe referenciar el evento biológico de la línea y el mismo activo. |
| `IOT_DIRECTO` | Además de RF-52, una lectura apta en la evaluación vigente de RF-62 debe tener evidencia RF-63. Se usa la vinculación vigente de RF-61. Para lecturas sin esa vinculación se comprueba la asociación histórica del sensor al activo. |
| `EVENTO_SANITARIO` | RF-73 debe contener una inferencia exitosa del mismo activo y cubrir la fecha del evento sanitario. Se compara el día calendario de Bogotá y se elige la inferencia más cercana si hay varias. |

Los UUID de las auditorías comprobadas quedan en `eslabones.ids` en la respuesta de `GET /finanzas/lineas/{id}/cadena`. Si falta una evidencia requerida, la línea queda en `PENDIENTE_TRAZABILIDAD`. Un error recuperable al consultar la fuente deja `VERIFICACION_PENDIENTE` y un evento en RF-94 con resultado `FUENTE_NO_DISPONIBLE`.

Se vuelven a comprobar las líneas previamente verificadas con auditorías obligatorias al ejecutar RF-91 sobre un período abierto. El cierre excluye las líneas pendientes del comprobante y requiere autorización para continuar con su exclusión. Las líneas `REGISTRO_MANUAL` cuyos orígenes actuales no guardan vínculo a un evento biológico, como ciertos costos y reconocimientos, quedan pendientes bajo el criterio de #1104. No se les atribuye evidencia por coincidencia de activo. Los períodos cerrados conservan sus cadenas históricas.

La revisión Alembic `f110491a0001` concede a `sgpmp_app` las lecturas de las fuentes y los privilegios requeridos para consultar e insertar la cadena. Las consultas de fuentes utilizan la identidad de servicio existente y las políticas RLS vigentes. El descenso de revisión conserva los permisos para evitar revocar ACL previas propias del ambiente.

## Pruebas

- Suite `tests/financial_valuation` con 198 aprobadas, 0 fallidas y 0 omitidas.
- Integración con PostgreSQL 18 aislado con 22 aprobadas, 0 fallidas y 0 omitidas. Se probaron los tres orígenes, la recuperación de una fuente fallida y su auditoría RF-94, el cierre, la inmutabilidad de los períodos cerrados y los endpoints de RF-91 con JWT, RBAC y el rol `sgpmp_app`.
- Alembic aplicó `f110491a0001` en la base local. La revisión es la única cabeza.

Queda pendiente desplegar el backend con la revisión Alembic en TEST y repetir TC-M06-G52 con líneas de un período abierto. La prueba de QA debe incluir la auditoría RF-52 del evento exacto y una auditoría de un evento distinto del mismo activo, y comprobar ambas cadenas por HTTP.
