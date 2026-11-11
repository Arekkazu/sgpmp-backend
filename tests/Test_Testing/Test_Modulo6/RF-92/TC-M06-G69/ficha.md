# TC-M06-G69 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-11 (TC-92-064 a TC-92-072, TC-92-083). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Inmutabilidad, descarga restringida y control de acceso (CA-6, Restricciones 2 y 5, RFC-018 D-18.8): los informes APROBADOS y ARCHIVADOS no se editan ni por API ni en base de datos, las nuevas versiones no alteran el contenido base, solo los APROBADOS se descargan, el informe nunca aparece en el envelope AAEF, y el Auditor externo tiene acceso de solo lectura limitado a APROBADO y ARCHIVADO.

### TC-92-064 — Intentar editar un informe en estado APROBADO vía API
- **Tipo:** Seguridad / integridad · **Prioridad:** Crítica · **Ejecutable:** Sí, si existe un informe APROBADO.
- **Pasos:** «TC-92-064 Resolver un APROBADO -> 422 INFORME_NO_EDITABLE»; «TC-92-064 No existe edicion directa del informe -> 404/405».
- **Esperado (matriz):** rechazo.

### TC-92-065 — Intentar editar un informe en estado ARCHIVADO
- **Tipo:** Seguridad / integridad · **Prioridad:** Alta · **Ejecutable:** Sí, si existe un informe ARCHIVADO.
- **Pasos:** «TC-92-065 Resolver un ARCHIVADO -> 422 INFORME_NO_EDITABLE».
- **Esperado (matriz):** rechazo.

### TC-92-066 — Ejecutar UPDATE directo sobre un informe aprobado con el usuario de base de datos de la aplicación
- **Tipo:** Seguridad / integridad · **Prioridad:** Crítica · **Ejecutable:** Bloqueado: requiere acceso directo a la base de datos de TEST.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** denegación por permisos del motor.

### TC-92-067 — Generar la versión 2 y verificar que el contenido base de la versión 1 permanece inalterado
- **Tipo:** Funcional / integridad · **Prioridad:** Crítica · **Ejecutable:** Parcial: se comprueba que el hash del APROBADO no cambia; comparar v1 contra v2 requiere generar otra versión.
- **Pasos:** «TC-92-067 El contenido del APROBADO no cambia entre lecturas (hash)».

### TC-92-068 — Intentar descargar un informe en estado BORRADOR
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí, si existe un BORRADOR.
- **Pasos:** «TC-92-068 Descargar un BORRADOR -> 422».
- **Esperado (matriz):** bloqueo.

### TC-92-069 — Intentar descargar un informe en estado RECHAZADO
- **Tipo:** Negativo / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí, si existe un RECHAZADO.
- **Pasos:** «TC-92-069 Descargar un RECHAZADO -> 422».
- **Esperado (matriz):** bloqueo.

### TC-92-070 — Inspeccionar el envelope AAEF del período tras aprobar el informe
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Bloqueado: el envelope AAEF es de M07 y no se revisó su contrato.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** que el informe NO aparezca y no se exporte a la contabilidad externa.

### TC-92-071 — Auditor externo consultando un informe APROBADO o ARCHIVADO a través de M08
- **Tipo:** Seguridad / autorización · **Prioridad:** Alta · **Ejecutable:** Sí, con el auditor externo (Externo AgroFusion); la vista de M08 no existe en este backend. Según RF-92 (Actores) el auditor puede descargar copias de informes aprobados.
- **Pasos:** «TC-92-071 Auditor externo tiene lectura de informes (404 por id inexistente, no 403)»; «TC-92-071 Auditor externo consulta un APROBADO (permitido)»; «TC-92-071 Auditor externo descarga un APROBADO (permitido segun RF-92)».
- **Esperado (matriz):** acceso de solo lectura permitido.

### TC-92-072 — Auditor externo intentando aprobar, rechazar, exportar o consultar un BORRADOR
- **Tipo:** Seguridad / autorización · **Prioridad:** Crítica · **Ejecutable:** Sí, con el auditor externo. La matriz dice que no puede exportar, pero RF-92 permite descargar copias aprobadas: se prueba la descarga como permitida.
- **Pasos:** «TC-92-072 Auditor externo consulta un BORRADOR -> 403»; «TC-92-072 Auditor externo aprueba -> 403»; «TC-92-072 Auditor externo rechaza -> 403»; «TC-92-072 Auditor externo genera informe -> 403».
- **Esperado (matriz):** 403 en todos los casos.

### TC-92-083 — Verificar la matriz de roles de la guía: el Contador genera y aprueba; el Administrador y el Revisor Fiscal tienen solo lectura sobre Finanzas; el Productor solo lee revelaciones ya aprobadas
- **Tipo:** Seguridad / autorización · **Prioridad:** Crítica · **Ejecutable:** Sí. El Administrador lee según la guía (la matriz de permisos del código no le da lectura de revelaciones); el Productor lee según RF-92 Salida 3.
- **Pasos:** «TC-92-083 Contador genera (permitido; 404/422 por periodo inexistente)»; «TC-92-083 Administrador tiene lectura de informes segun la guia (404 por id inexistente, no 403)»; «TC-92-083 Productor tiene lectura de informes segun RF-92 Salida 3 (404 por id inexistente, no 403)»; «TC-92-083 Administrador consulta un APROBADO (solo lectura)»; «TC-92-083 Administrador aprueba -> 403»; «TC-92-083 Productor consulta un APROBADO (permitido segun la guia)»; «TC-92-083 Productor consulta un BORRADOR -> 403».
- **Esperado (matriz):** que una sección sin permiso no aparezca y que, entrando por URL, salga «Sin acceso».

## Ejecución automatizada
- Colección: `tc_m06_g69.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G69.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador, Administrador, Productor, Revisor Fiscal, Externo AgroFusion (auditor externo).
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
