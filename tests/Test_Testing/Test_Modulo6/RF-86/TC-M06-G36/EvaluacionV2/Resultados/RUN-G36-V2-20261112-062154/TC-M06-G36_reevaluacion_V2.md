# TC-M06-G36 — APROBADO

## Identificación

Grupo G36; casos TC-M06-009 y TC-M06-010; RF-86, restricción 5, CA-12 y CA-13; versión 2, intento 3; RUN `RUN-G36-V2-20261112-062154`; ambiente TEST; autorización `AUT-G36-V2-20261112`. Commit de TEST informado por el responsable QA: `453277e4`, no comprobado en vivo. Herramientas registradas: Node v22.15.1 y Newman 6.2.2. Cypress: cero pruebas; la matriz prescribe solo API.

## Veredictos y oficialidad

| Caso | Veredicto | Fundamento |
|---|---|---|
| TC-M06-009 | APROBADO | Nueve modificaciones bloqueadas con orientación al correctivo; variación y línea sin cambios. |
| TC-M06-010 | APROBADO | Solicitud pendiente sin efecto previo, aprobación, historial y línea inversa acreditados. |

El RUN es **oficial** porque el rollback figura verificado, los dos casos están decididos, Newman terminó sin fallos y se usaron 119 de las 150 solicitudes permitidas. Tres inicios de sesión se ejecutaron fuera del RUN.

## Preflight vivo

| Requisito | Esperado | Observado | ¿Cumple? |
|---|---|---|---|
| Período actual | ABIERTO | La comprobación encontró períodos cerrados y abiertos; el período usado, 241, consta como ABIERTO. | Sí |
| Activos elegibles | Al menos dos bovinos | Se seleccionaron los activos 1627 y 1831. | Sí |
| Precio vigente | Precio `PESO_KG` vigente | Precio 18 para ambos activos. | Sí |
| Matriz contable | Asignaciones de transformación biológica y precio de mercado | La matriz incluye `VARIACION_VR_TB` y `VARIACION_VR_PM`. | Sí |
| Acceso del segundo Contador | Consulta de activos con HTTP 200 | Se acreditó el acceso a los activos 1627 y 1831. | Sí |

Los cinco requisitos bloqueantes figuran cumplidos en [preflight.json](preflight.json).

## Detalle por caso

### TC-M06-009

**Qué se verifica.** La matriz de casos, fila 379, y RF-86 CA-12 y restricción 5 exigen bloquear la modificación o eliminación de una variación y su línea, orientar al correctivo y conservar ambos registros idénticos campo a campo.

**Preparación.** En este RUN se usaron el activo bovino 1627, período abierto 241 y precio vigente 18. El evento M02 1644 originó la variación 411 y la línea contable 5646. La evidencia no conserva el importe numérico de esa variación.

**Qué se hizo.**

1. Se consultaron la variación 411 y la línea 5646 para fijar sus estados iniciales.
2. Se intentaron `PUT`, `PATCH` y `DELETE` en las dos rutas de variación y en la ruta de la línea: nueve intentos en total.
3. Se volvieron a consultar ambos registros y se compararon sus campos y huellas SHA-256.

**Qué se esperaba.** Los nueve intentos debían quedar bloqueados con orientación al correctivo; la variación y la línea debían conservar sus valores originales.

**Qué se observó.**

| Ruta | Método | HTTP | Código de error |
|---|---|---:|---|
| `/finanzas/variaciones/411` | PUT | 409 | `VARIACION_INMUTABLE` |
| `/finanzas/variaciones/411` | PATCH | 409 | `VARIACION_INMUTABLE` |
| `/finanzas/variaciones/411` | DELETE | 409 | `VARIACION_INMUTABLE` |
| `/finanzas/periodos/241/variaciones/411` | PUT | 409 | `VARIACION_INMUTABLE` |
| `/finanzas/periodos/241/variaciones/411` | PATCH | 409 | `VARIACION_INMUTABLE` |
| `/finanzas/periodos/241/variaciones/411` | DELETE | 409 | `VARIACION_INMUTABLE` |
| `/finanzas/lineas/5646` | PUT | 409 | `LINEA_ASIENTO_INMUTABLE` |
| `/finanzas/lineas/5646` | PATCH | 409 | `LINEA_ASIENTO_INMUTABLE` |
| `/finanzas/lineas/5646` | DELETE | 409 | `LINEA_ASIENTO_INMUTABLE` |

Los seis intentos sobre la variación devolvieron el mismo mensaje, citado una sola vez: «Las variaciones de valor razonable no se modifican ni se eliminan: quedan como registro permanente. Para corregir una, solicite un correctivo; se registrará uno nuevo con el monto opuesto que referencia el original, y se aplicará cuando otro Contador lo apruebe.»

Los tres intentos sobre la línea devolvieron el mismo mensaje, citado una sola vez: «Las líneas de asiento no se modifican ni se eliminan. Si la línea viene de una variación errónea, solicite el correctivo de esa variación: al aprobarse se registra la línea inversa. Un reconocimiento inicial se corrige con su reversión.» Así, los nueve mensajes orientan al mecanismo de corrección.

La comparación campo a campo incluyó **21 campos de la variación** y **26 campos de la línea**; no se registraron campos alterados. La huella de la variación fue `4aa927f3ae6daf726ac6ba607e6b24899ef532b1cf97d139caad9a3c1f5e367a` antes y después. La de la línea fue `b595ba688ca6c319de951393008dceb7e65b708b3b08199c16f3ae382a2cb78d` antes y después.

**Por qué se decide así.** Los nueve bloqueos y sus mensajes satisfacen CA-12; la comparación y las huellas coincidentes acreditan que el original y su línea permanecieron intactos.

**Decisión.** APROBADO.

### TC-M06-010

**Qué se verifica.** La matriz, fila 379, y RF-86 CA-13 y restricción 5 exigen un correctivo nuevo de monto opuesto referido al original, sin efecto antes de su aprobación, con ambos registros visibles y una línea inversa de valor positivo y cuentas intercambiadas.

**Preparación.** En este RUN se usaron el activo bovino 1831, período abierto 241 y precio vigente 18. El evento M02 1645 originó la variación 412 y la línea 5647. El Contador QA solicitó la corrección. Fue necesario un segundo Contador porque el producto impide que quien solicita apruebe su propia solicitud; el usuario 169 se preparó por SQL con autorización del responsable QA, según el contexto autorizado de esta reevaluación. La evidencia no conserva el importe numérico de la variación original.

**Qué se hizo.**

1. **Solicitud:** el Contador QA envió `POST /finanzas/variaciones/412/correctivos`; recibió HTTP 201. Se creó la solicitud 1, pendiente según el resultado del caso.
2. **Estado previo:** antes de aprobar, las lecturas de variaciones, líneas y correctivos acreditaron que aún no había variación ni línea correctiva efectiva (`efectivo_antes: false`); la original 412 seguía visible.
3. **Autoaprobación:** el mismo Contador intentó `POST /finanzas/correctivos/1/aprobacion`; recibió HTTP 403 y `APROBADOR_DEBE_SER_OTRO`. Es una observación del doble control del producto, que RF-86 no exige y que no afecta al veredicto.
4. **Aprobación válida:** el segundo Contador, usuario 169, aprobó la solicitud 1 por esa ruta; recibió HTTP 200.
5. **Historial:** la consulta posterior acreditó que la original 412 y la correctiva 413 estaban visibles; ninguna se eliminó.
6. **Línea inversa:** el oráculo automatizado del RUN la acreditó (`linea_inversa: true`). El criterio exige valor positivo, cuentas intercambiadas y referencia a la línea original 5647. El resultado guardado no conserva el identificador, valor numérico ni las cuentas de la línea inversa; por ello, no se reproducen datos concretos y se cita la comprobación acreditada por el oráculo.

**Qué se esperaba.** Una solicitud pendiente sin efecto contable; tras la aprobación, variación correctiva de monto opuesto referida a la 412, ambas visibles y línea inversa positiva con las cuentas intercambiadas.

**Qué se observó.** La solicitud 1 recibió HTTP 201; antes de aprobar no era efectiva; el intento del solicitante recibió HTTP 403; la aprobación del segundo Contador recibió HTTP 200. La original 412 y la correctiva 413 quedaron visibles, y el oráculo marcó acreditada la línea inversa. El resultado no guarda el monto original o correctivo, la referencia de la variación correctiva ni el valor y las cuentas de la línea inversa; esas magnitudes y relaciones solo pueden citarse como comprobaciones aprobadas, sin afirmar valores concretos.

**Por qué se decide así.** La secuencia registrada acredita solicitud sin efecto previo, aprobación y conservación del original. El resultado y las comprobaciones API marcan cumplido el oráculo de la corrección y la línea inversa; la falta de valores detallados limita su reproducción documental, sin cambiar la decisión registrada.

**Decisión.** APROBADO.

## Comprobaciones API y evidencias

| Comprobación | Caso | Resultado | Evidencia |
|---|---|---|---|
| `G36-API-009-01` | TC-M06-009 | APROBADO; bloqueo y orientación al correctivo. | [resultado.json](resultado.json) y [Newman JSON](newman/newman-G36.json) |
| `G36-API-009-02` | TC-M06-009 | APROBADO; inmutabilidad de la línea. | [resultado.json](resultado.json) y [Newman JSON](newman/newman-G36.json) |
| `G36-API-010-01` | TC-M06-010 | APROBADO; solicitud, aprobación e historial. | [resultado.json](resultado.json) y [Newman JSON](newman/newman-G36.json) |
| `G36-API-010-02` | TC-M06-010 | APROBADO; línea inversa acreditada. | [resultado.json](resultado.json) y [Newman JSON](newman/newman-G36.json) |

Newman registró cuatro solicitudes de comprobación y ocho aserciones, sin fallos; su [reporte HTML](newman/newman-G36.html) está en el mismo RUN. Las lecturas y veredictos están en [resultado.json](resultado.json); preparación y contexto constan en [preflight.json](preflight.json) y [contexto_operacion.json](contexto_operacion.json). La matriz prescribe solo API, por lo que no hay comprobaciones ni capturas Cypress.

## Incidencias, certeza y causas

La incidencia V1 `INC-M06-G36-01` figura **CORREGIDA** en esta V2: ambos casos pasaron a APROBADO. No se comprobaron incidencias nuevas de producto ni problemas técnicos de automatización. No se asignan severidad ni equipo a una incidencia nueva inexistente. La evidencia de TEST confirma la corrección observada; no demuestra una causa raíz técnica. El rechazo de autoaprobación es una regla adicional del producto, observada sin discrepancia frente al oráculo de RF-86.

## Cierre y rollback

El cierre del RUN devolvió HTTP 200. [resultado.json](resultado.json) registra rollback verificado mediante lecturas públicas posteriores: ambos activos volvieron a `ACTIVO`, con peso restaurado y sin residuos del RUN en eventos M02, solicitudes correctivas, variaciones, líneas, cálculos ni auditoría consultados. Esta verificación se limita a esas lecturas; no acredita reversión de archivos o notificaciones externas.

## Conclusión y acciones

CA-12 y CA-13 cumplen según los dos casos APROBADOS en TEST; la incidencia V1 `INC-M06-G36-01` queda **CORREGIDA** en esta reevaluación. No queda un criterio de estos dos casos pendiente de evaluación. El doble control que impide la autoaprobación se conserva como observación del producto y no como exigencia adicional de RF-86. La siguiente acción es cerrar la incidencia V1 en el sistema de seguimiento, si corresponde al flujo del responsable QA; no hay incidencias nuevas que derivar.

## Enmienda documental (2026-11-12)

La orden `ORD-G36-010` dispuso aclarar únicamente este Markdown. La copia previa byte a byte está en [historial_informes/TC-M06-G36_reevaluacion_V2.RUN-G36-V2-20261112-062154.antes-enmienda.md](../../../historial_informes/TC-M06-G36_reevaluacion_V2.RUN-G36-V2-20261112-062154.antes-enmienda.md), con SHA-256 `F5C1A2DC8CEF7696B340DFB01D5C641C220C59F69378E5E60D429B5BE1693396`. [resultado.json](resultado.json) conserva SHA-256 `82FB41947541A2F39D96E616A89B20CCEDC2F1A3D125686527B03A14A998CEB3`.

Se redactaron en prosa la preparación, los pasos, las observaciones y la justificación de cada caso; se resumió el preflight; se aclararon la oficialidad, las limitaciones de los datos guardados y las acciones de cierre; se corrigió la ortografía española. No cambian los veredictos, la oficialidad, el rollback ni las evidencias del RUN.
