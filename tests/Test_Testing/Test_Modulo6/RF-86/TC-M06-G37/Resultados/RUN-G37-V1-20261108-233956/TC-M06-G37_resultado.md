# TC-M06-G37 — RECHAZADO

## Identificación

Casos: TC-M06-011, TC-M06-012, TC-M06-013. RF-86 con RF-93, RF-94 y RF-91. Versión 1, intento 8; RUN RUN-G37-V1-20261108-233956. Ambiente TEST. Autorización AUT-G37-V1-R8-20261108. Commit: no consultado en este ejecutor. Herramientas: Node v22.15.1; Newman 6.2.2.

## Decisión del caso

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-011 | RECHAZADO | RF-93 rechazó generar el estado antes de variaciones en período ABIERTO: PERIODO_NO_CERRADO. |
| TC-M06-012 | APROBADO | Cada variación tiene una entrada RF-94 con identificador, activo, tipo, monto y período. |
| TC-M06-013 | RECHAZADO | POST RF-91 HTTP 500 (ERROR_INTERNO); el log del backend confirma la misma causa de INC-M06-G32-01. |

## Detalle por caso

### TC-M06-011

- **Preparación:** período 8 ABIERTO; se consultó la lista de estados y se intentó generar la versión previa antes de registrar las variaciones.
- **Esperado:** Según RF-86 CA-3, CA-9, Proceso paso 8 y Postcondición 1, el acumulado del período cambia sin recálculo manual: ganancias en ingresos, pérdidas en gastos y sin sumar otro período.
- **Observado:** La lista GET de estados del período estaba vacía antes y después. POST `/finanzas/periodos/8/estados-resultados` respondió HTTP 422, `PERIODO_NO_CERRADO`: «Período no cerrado; ejecute el cierre antes de generar el estado».
- **Qué se cumplió:** Se comprobó la respuesta de la API pública y se registraron las variaciones posteriores para los demás casos.
- **Qué falló y por qué:** No hubo estado previo ni posterior comparable ni otra ruta pública de acumulado abierto. RF-93 exige CERRADO para generar el estado; existe un posible conflicto con el período ABIERTO y la actualización sin recálculo manual exigidos por RF-86. Véase INC-M06-G37-01.
- **Decisión:** RECHAZADO; se conserva el veredicto de la matriz.

### TC-M06-012

- **Preparación:** período 8 ABIERTO; cinco variaciones de los cuatro tipos de ganancia y pérdida. El activo 945 pasó a EN_TRATAMIENTO después del pesaje; se registraron precios 441 y 442 para los escenarios de mercado.
- **Esperado:** RF-86 CA-10 y Proceso paso 9: exactamente una entrada `VARIACION_REGISTRADA` RF-94 por variación, con identificador, activo, tipo, monto y período coincidentes.
- **Observado:** Se registraron cinco variaciones nuevas del paso y seis auditorías nuevas en el período; la adicional corresponde a la variación 253, rebase anterior a la línea base del paso. La consulta RF-94 usó filtro de período y paginación.

| Variación | Activo | Tipo | Monto | Evento M02 | Línea | Auditoría RF-94 |
|---|---:|---|---:|---:|---:|---|
| 254 | 943 | GANANCIA_TRANSFORMACION_BIOLOGICA | +62265.60 | 1298 | 901 | Entrada coincidente; ID individual no conservado |
| 255 | 945 | PERDIDA_TRANSFORMACION_BIOLOGICA | -55226.88 | 1299 | 902 | Entrada coincidente; ID individual no conservado |
| 256 | 944 | GANANCIA_TRANSFORMACION_BIOLOGICA | +272615.04 | 1300 | 903 | Entrada coincidente; ID individual no conservado |
| 257 | 944 | PERDIDA_PRECIO_MERCADO | -53805.60 | 1300 | 904 | Entrada coincidente; ID individual no conservado |
| 258 | 946 | GANANCIA_PRECIO_MERCADO | +241956.00 | 1301 | 905 | Entrada coincidente; ID individual no conservado |

Los IDs RF-94 nuevos conservados son 7083, 7085, 7087, 7091, 7092 y 7096. `resultado.json` guarda el conjunto y el resultado del oráculo, pero no la correspondencia individual ID→variación; no se asigna una por inferencia.

- **Qué se cumplió:** El oráculo de RF-94 confirmó una sola entrada coincidente en referencia, activo, tipo, monto y período para cada una de las cinco variaciones del paso.
- **Qué falló y por qué:** Ninguna discrepancia observada frente a CA-10.
- **Decisión:** APROBADO.

### TC-M06-013

- **Preparación:** variación 254 del activo 943, dispositivo 849, período 8; cadena inicial de la línea 901 consultada con HTTP 200. La lectura 120011 estaba visible en el historial del sensor 1311.
- **Esperado:** RF-86 CA-2, CA-11 y Proceso paso 10: `VERIFICACION_PENDIENTE` al crear; con `CADENA_COMPLETA`, estado `VERIFICADO` y navegación hasta el evento M02 1298 y la lectura M03 120011.
- **Observado:** La variación quedó inicialmente en `VERIFICACION_PENDIENTE`. POST `/finanzas/periodos/8/trazabilidad` respondió HTTP 500 `ERROR_INTERNO`; el log del backend TEST aportado por el responsable QA identifica una cadena heredada de período cerrado que abortó la transacción.
- **Qué se cumplió:** Se comprobó el estado inicial, se obtuvo la cadena inicial por API pública y se constató la lectura 120011 en el historial del sensor.
- **Qué falló y por qué:** No se pudo comprobar `VERIFICADO` ni navegar desde la variación hasta M02 y M03. El log confirma la misma causa de INC-M06-G32-01: la verificación conjunta del período intenta insertar sobre una cadena inmutable heredada.
- **Decisión:** RECHAZADO; se vincula a INC-M06-G32-01, sin abrir una incidencia nueva.

## Comprobaciones API/UI

| ID | Caso | Estado | Observación | Evidencia |
|---|---|---|---|---|
| G37-API-011-01 | TC-M06-011 | RECHAZADO | RF-93 rechazó generar el estado antes de variaciones en período ABIERTO: PERIODO_NO_CERRADO. | resultado.json |
| G37-API-012-01 | TC-M06-012 | APROBADO | Cada variación tiene una entrada RF-94 con identificador, activo, tipo, monto y período. | resultado.json |
| G37-API-013-01 | TC-M06-013 | RECHAZADO | La comprobación registrada por el ejecutor observó HTTP 500 (ERROR_INTERNO). El log aportado después por QA confirmó la misma causa de INC-M06-G32-01; véase la incidencia reutilizada. | resultado.json y log aportado por QA |

UI: no exigida por la matriz original (API Postman/Newman).

## Contraste de contrato

- /sesiones/me/permisos (contador, HTTP 200, ejecutor): coincide.
- /sesiones/me/permisos (admin, HTTP 200, ejecutor): coincide.
- /finanzas/activos (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos (contador, HTTP 200, ejecutor): coincide.
- /finanzas/precios?id_especie={especie} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/precios?id_especie={especie} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/precios?id_especie={especie} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/precios?id_especie={especie} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/precios?id_especie={especie} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/activos/{activo} (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/ficha-integral (admin, HTTP 200, ejecutor): coincide.
- /finanzas/activos/{activo} (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/ficha-integral (admin, HTTP 200, ejecutor): coincide.
- /finanzas/activos/{activo} (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/ficha-integral (admin, HTTP 200, ejecutor): coincide.
- /finanzas/activos/{activo} (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/ficha-integral (admin, HTTP 200, ejecutor): coincide.
- /finanzas/activos/{activo} (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/ficha-integral (admin, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/estados-resultados (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/estados-resultados (contador, HTTP 200, ejecutor): sin elementos para contrastar.
- /finanzas/auditoria?id_periodo_contable={periodo}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina={pagina}&tamano=500 (contador, HTTP 200, ejecutor): coincide.
- /iot/monitoreo/historial?fecha_inicio={inicio}&fecha_fin={fin}&sensor_id={sensor}&pagina={pagina}&por_pagina=100 (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/mediciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/lineas?id_periodo_contable={periodo} (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/ficha-integral (admin, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos (admin, HTTP 200, ejecutor): coincide.
- /finanzas/lineas/{linea}/cadena (contador, HTTP 200, ejecutor): coincide.
- /finanzas/estados-resultados/{estado} (contador, HTTP null, ejecutor): sin elementos para contrastar.
- /finanzas/periodos/{periodo}/estados-resultados (contador, HTTP 422, ejecutor): no_contrastable.
- /activos-biologicos/{activo}/eventos/crecimiento (admin, HTTP 201, ejecutor): coincide.
- /finanzas/eventos/procesar (contador, HTTP 200, ejecutor): coincide.
- /finanzas/activos/{activo} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos/crecimiento (admin, HTTP 201, ejecutor): coincide.
- /finanzas/eventos/procesar (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos/crecimiento (admin, HTTP 201, ejecutor): coincide.
- /activos-biologicos/{activo}/estado (admin, HTTP 200, ejecutor): coincide.
- /finanzas/eventos/procesar (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/precios (contador, HTTP 201, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos/crecimiento (admin, HTTP 201, ejecutor): coincide.
- /finanzas/eventos/procesar (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/precios (contador, HTTP 201, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos/crecimiento (admin, HTTP 201, ejecutor): coincide.
- /finanzas/eventos/procesar (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/lineas?id_periodo_contable={periodo} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/estados-resultados (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/mediciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/auditoria?id_periodo_contable={periodo}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina={pagina}&tamano=500 (contador, HTTP 200, ejecutor): coincide.
- /finanzas/lineas/{linea}/cadena (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/trazabilidad (contador, HTTP 500, ejecutor): no_contrastable.
- /finanzas/periodos/{periodo}/estados-resultados (contador, HTTP 200, Newman): coincide.
- /finanzas/auditoria?id_periodo_contable={periodo}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina={pagina}&tamano=500 (contador, HTTP 200, Newman): coincide.
- /finanzas/lineas/{linea}/cadena (contador, HTTP 200, Newman): coincide.
- /finanzas/periodos/{periodo}/variaciones (contador, HTTP 200, ejecutor): coincide.
- /finanzas/lineas?id_periodo_contable={periodo} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/estados-resultados (contador, HTTP 200, ejecutor): coincide.
- /finanzas/periodos/{periodo}/mediciones (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos (admin, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos (admin, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos (admin, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos (admin, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/eventos (admin, HTTP 200, ejecutor): coincide.
- /finanzas/precios?id_especie={especie} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/precios?id_especie={especie} (contador, HTTP 200, ejecutor): coincide.
- /finanzas/auditoria?id_periodo_contable={periodo}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina={pagina}&tamano=500 (contador, HTTP 200, ejecutor): coincide.
- /activos-biologicos/{activo}/ficha-integral (admin, HTTP 200, ejecutor): coincide.

Rutas previas contrastadas con elementos reales: /sesiones/me/permisos, /finanzas/activos, /finanzas/periodos, /finanzas/precios?id_especie={especie}, /finanzas/activos/{activo}, /activos-biologicos/{activo}/ficha-integral, /finanzas/auditoria?id_periodo_contable={periodo}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina={pagina}&tamano=500, /iot/monitoreo/historial?fecha_inicio={inicio}&fecha_fin={fin}&sensor_id={sensor}&pagina={pagina}&por_pagina=100, /finanzas/periodos/{periodo}/variaciones, /finanzas/periodos/{periodo}/mediciones, /finanzas/lineas?id_periodo_contable={periodo}, /activos-biologicos/{activo}/eventos, /finanzas/lineas/{linea}/cadena. Rutas sin elementos para contrastar: /finanzas/periodos/{periodo}/estados-resultados, /finanzas/estados-resultados/{estado}.

### Selección de candidatos

| Activo | Condiciones no cumplidas |
|---|---|
| 943 | ninguna |
| 944 | ninguna |
| 945 | ninguna |
| 946 | ninguna |
| 947 | ninguna |
| 948 | estado distinto de ACTIVO para pesaje; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 1567 | no es bovino; valorado por costo; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 951 | no es bovino; valorado por costo; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 1568 | no es bovino; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 1572 | no es bovino; valorado por costo; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 1573 | no es bovino; valorado por costo; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 1569 | no es bovino; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 1570 | no es bovino; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 1571 | no es bovino; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 950 | no es bovino; no es activo individual; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |
| 949 | no es bovino; no es activo individual; sin período destino ABIERTO; sin precio vigente; sin cálculo previo; sin peso actual positivo |

### Observación M03

La lectura 120011 es visible por sensor 1311; precede a la creación del activo 943 y a la asociación sensor-área 741. RF-91 enlaza por dispositivo 849, aptitud NIC41 y ventana del evento (trazabilidad_repository.py:59-75).

## Evidencias reales

newman/newman-G37.json, newman/newman-G37.html, resultado.json, TC-M06-G37_resultado.md.

## Incidencias

### INC-M06-G37-01: RF-93 no ofrece el acumulado del estado de resultados de un período abierto

- **Requisito:** RF-86 CA-3, CA-9, Proceso paso 8 y Postcondición 1; RF-93.
- **Pasos:** Con período 8 ABIERTO, consultar GET `/finanzas/periodos/8/estados-resultados`; antes de registrar variaciones, solicitar POST a la misma ruta; registrar las variaciones y consultar de nuevo la lista.
- **Esperado:** Acumulado del período abierto disponible antes y después, actualizado sin recálculo manual por ganancias e ingresos y pérdidas y gastos, sin incluir otro período.
- **Obtenido:** POST HTTP 422, `error_code=PERIODO_NO_CERRADO`, mensaje «Período no cerrado; ejecute el cierre antes de generar el estado». GET devolvió lista vacía antes y después. La revisión de rutas públicas en `m06_router.py:423-452` no identificó otro acumulado del período abierto.
- **Apoyo de código, sin atribuir causa:** `generar_estado_resultados_use_case.py:28-35` comprueba `_cerrado`; su docstring declara «Casos de uso RF-93. Solo sobre períodos CERRADOS (R1)».
- **Posible conflicto de requisitos:** La fila de la matriz exige período ABIERTO y «sin recálculo manual», mientras la implementación cita la regla R1 de RF-93 para CERRADOS. Desarrollo y el responsable de requisitos deben resolver la compatibilidad; el código por sí solo no cambia el oráculo ni el veredicto.
- **Impacto:** Impide comprobar el acumulado dinámico exigido por TC-M06-011 mediante API pública; afecta una función relevante sin alternativa comprobada.
- **Severidad:** ALTA, por bloqueo de la función relevante sin alternativa pública observada.
- **Equipo inicial:** Desarrollo, por la primera discrepancia confirmada en la API pública de M06; la causa raíz sigue sin determinarse.
- **Certeza:** CONFIRMADA para la respuesta y la ausencia del acumulado; causa raíz NO DETERMINADA.
- **Evidencias:** `resultado.json` (solicitud 422, GET y veredicto), `newman/newman-G37.json` (lectura GET), matriz original TC-M06-G37; apoyo de código indicado.

### Incidencia reutilizada: INC-M06-G32-01

- **Requisito:** RF-86 CA-2, CA-11, Proceso paso 10 y Salida; RF-91 Restricción 4.
- **Pasos:** Crear la variación TB+ 254 del activo 943; leer la cadena inicial de la línea 901; solicitar POST `/finanzas/periodos/8/trazabilidad`; intentar comprobar el estado final y la navegación al evento M02 1298 y la telemetría 120011.
- **Esperado:** Cadena completa, variación `VERIFICADO` y navegación hasta M02 y M03.
- **Obtenido:** Cadena inicial HTTP 200 y variación `VERIFICACION_PENDIENTE`; POST HTTP 500 `ERROR_INTERNO`. El log del backend TEST aportado por el responsable QA para ese POST dice: «[TGR-M06-26] La cadena de trazabilidad id=168 está vinculada a la variación id=4 que pertenece a un período contable CERRADO. Las cadenas de trazabilidad de períodos cerrados son inmutables… Operación: INSERT. Requerimiento RF-91, Restricción 4» (`modulo6.fn_tgr_m06_26_trazabilidad_periodo_cerrado`).
- **Causa confirmada por el log:** `VerificarTrazabilidadUseCase.execute` verifica todas las líneas del período en una transacción. Una línea heredada de un período cerrado aborta la verificación completa; es la misma causa de INC-M06-G32-01. La cita es evidencia aportada por el responsable QA, no un archivo de log guardado en este RUN.
- **Impacto:** No se pudo comprobar `VERIFICADO` ni navegar desde la variación 254 hasta el evento M02 1298 y la lectura M03 120011. La lectura sí era visible por sensor 1311.
- **Severidad y equipo heredados:** ALTA; Desarrollo. La primera discrepancia de este RUN fue la respuesta pública HTTP 500 y el log orienta el seguimiento de la incidencia existente.
- **Certeza:** CONFIRMADA para el error y la causa indicada por el log.
- **Evidencias:** `resultado.json` (solicitud 500 y estado inicial), `newman/newman-G37.json` (cadena), log del backend TEST aportado por el responsable QA en la orden ORD-G37-025.

## Análisis de causas

En 011 se confirmó la discrepancia de la API pública; el posible conflicto RF-86/RF-93 requiere resolución de requisitos y la causa raíz no está determinada. En 013, el log aportado confirma la causa ya registrada en INC-M06-G32-01. Problemas de automatización: ninguno observado.

## Conclusión y acciones

TC-M06-011 RECHAZADO por INC-M06-G37-01; TC-M06-012 APROBADO por correspondencia de las cinco variaciones con RF-94; TC-M06-013 RECHAZADO por la incidencia existente INC-M06-G32-01. Desarrollo debe resolver la disponibilidad del acumulado abierto junto con el responsable de requisitos y corregir la verificación de RF-91 sin intentar modificar cadenas cerradas. QA reevaluará 011 y 013 por API pública cuando existan correcciones y autorización específica; conservará 012 como aprobado de este RUN.

## Cierre y rollback

DELETE del RUN: HTTP 200. Rollback de datos del sandbox verificado: sí; IDs del RUN ausentes y estado M02 restaurado en lecturas públicas poscierre. Los precios 441 y 442 fueron revertidos por DELETE y las lecturas poscierre lo confirmaron. Según el mismo log aportado, el aviso `ALERTA_FINANCIERA_NIC41` no llegó a registrarse: «El tipo de evento 40 no tiene una categoría configurada». El rollback verificado se limita a los datos del sandbox.

Actualización del informe (2026-11-08): detalle por caso, incidencias completas y vínculo de 013 con INC-M06-G32-01 por log del backend; veredictos sin cambios.
