# Reporte de Ejecución: TC-M05-G25 (RF-77)

## 1. Identificación y Alcance
- **Caso de Prueba**: TC-M05-G25
- **Requerimiento**: RF-77 (Reporte de Gastos Acumulados por Activo)
- **Subcasos Evaluados**: TC-M05-024 (Roles y Permisos), TC-M05-025 (Auditoría de Generación y Exportación)
- **Veredicto Global**: **RECHAZADO** (12 OK, 6 FALLA)

## 2. Resumen Normativo de Checkpoints
| # | Paso Evaluado | Esperado (Fuente) | Obtenido | Estado |
|---|---------------|-------------------|----------|--------|
| 1 | A01 Generación de reporte sincrónico por Productor | HTTP 200, respuesta con id_reporte_gasto_acumulado y gasto acumulado calculado (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 200, respuesta con id_reporte_gasto_acumulado y gasto acumulado calculado) | **OK** |
| 2 | A02 Exportación de reporte a formato CSV por Productor | HTTP 201, generación de archivo CSV con vigencia de 24 horas y prefijo Gastos_ (Fuente: RF-77 RNF Exportación (TC-M05-024 / CU04)) | Falla: AssertionError: Exportación sin id_archivo_exportacion
assert None is not None | **FALLA** |
| 3 | A03 Exportación de reporte a formato PDF por Productor | HTTP 201, generación de archivo PDF con prefijo Reporte_Gastos_ (Fuente: RF-77 RNF Exportación (TC-M05-024 / CU04)) | Falla: AssertionError: Exportación sin id_archivo_exportacion
assert None is not None | **FALLA** |
| 4 | A04 Descarga de exportación propia por Productor | HTTP 200, Content-Type text/csv, Content-Disposition attachment (Fuente: RF-77 RNF Exportación (TC-M05-024)) | Falla: AssertionError: Precondición no cumplida: falta id_archivo_csv
assert None is not None | **FALLA** |
| 5 | A05 Restricción de acceso a auditoría de M05 para Productor | HTTP 403 ACCESO_DENEGADO (Recurso 57 restringido a Administrador/Contador) (Fuente: RF-80 / RBAC Centralizado) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO (Recurso 57 restringido a Administrador/Contador)) | **OK** |
| 6 | A98 Cierre ordenado de sandbox Productor y rollback | HTTP 200 con confirmación 'Rollback exitoso' (Fuente: Testing Harness / Sandbox Control) | Conforme con la especificación (HTTP 200 con confirmación 'Rollback exitoso') | **OK** |
| 7 | B01 Restricción de generación de reporte para Veterinario | HTTP 403 ACCESO_DENEGADO (Solo Productor y Administrador pueden generar) (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO (Solo Productor y Administrador pueden generar)) | **OK** |
| 8 | B02 Restricción de exportación de reporte para Veterinario | HTTP 403 ACCESO_DENEGADO (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO) | **OK** |
| 9 | B03 Restricción de descarga de exportación para Veterinario | HTTP 403 ACCESO_DENEGADO (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO) | **OK** |
| 10 | B04 Restricción de acceso a auditoría para Veterinario | HTTP 403 ACCESO_DENEGADO (Fuente: RF-80 / RBAC Centralizado) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO) | **OK** |
| 11 | B98 Cierre ordenado de sandbox Veterinario y rollback | HTTP 200 con confirmación 'Rollback exitoso' (Fuente: Testing Harness / Sandbox Control) | Conforme con la especificación (HTTP 200 con confirmación 'Rollback exitoso') | **OK** |
| 12 | C01 Generación y exportación de reporte por Administrador | HTTP 200 en generación y HTTP 201 en exportación CSV (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Falla: AssertionError: Exportación Admin sin id_archivo_exportacion
assert None is not None | **FALLA** |
| 13 | C02 Registro en bitácora de auditoría de M05 de generación/exportación | Presencia de evento de auditoría con usuario y timestamp (RF-77 CA-11 / Postcondición 3) (Fuente: RF-77 CA-11 / Postcondición 3 (TC-M05-025)) | Falla: AssertionError: DEFECTO_PRODUCTO: El evento de generación/exportación del reporte de gastos acumulados no fue registrado en la bitácora de auditoría de M05 (RF-77 CA-11 / Postcondición 3 / Caso TC-M05-025). Se consultaron los últimos 50 eventos y ninguno corresponde a entidad o tipo_operacion de RF- | **FALLA** |
| 14 | C98 Cierre ordenado de sandbox Administrador y rollback | HTTP 200 con confirmación 'Rollback exitoso' (Fuente: Testing Harness / Sandbox Control) | Conforme con la especificación (HTTP 200 con confirmación 'Rollback exitoso') | **OK** |
| 15 | D01 Rechazo de solicitudes no autenticadas | HTTP 401 NO_AUTENTICADO en endpoints de reporte, exportación, descarga, historial y auditoría (Fuente: RF-02 / Especificación Global de Seguridad) | Conforme con la especificación (HTTP 401 NO_AUTENTICADO en endpoints de reporte, exportación, descarga, historial y auditoría) | **OK** |
| 16 | D02 Prevención de IDOR en descarga de exportaciones ajenas | HTTP 403 ARCHIVO_DE_OTRO_USUARIO al intentar descargar archivo generado por otro usuario (Fuente: RF-77 RNF Seguridad / Aislamiento (TC-M05-024 / TC-M05-025)) | Conforme con la especificación (HTTP 403 ARCHIVO_DE_OTRO_USUARIO al intentar descargar archivo generado por otro usuario) | **OK** |
| 17 | D03 Validación de tipos y resistencia ante IDs inexistentes o inválidos | HTTP 404 en inexistentes, HTTP 422 en tipos inválidos; jamás HTTP 500 (Fuente: Guía de Pruebas / Robustez de la API) | Falla: AssertionError: Para ID negativo (/suministros/reportes-gastos/-1) se esperaba HTTP 422, obtenido: 404: {"error_code":"REPORTE_NO_ENCONTRADO","message":"El reporte de gastos -1 no existe.","fields":[{"fie
assert 404 == 422
 +  where 404 = <Response [404]>.status_code | **FALLA** |
| 18 | D04 Aislamiento estricto de historial por usuario | GET /historial filtra exclusivamente los reportes creados por el usuario autenticado (Fuente: RF-77 RNF Historial (TC-M05-023 / TC-M05-024)) | Conforme con la especificación (GET /historial filtra exclusivamente los reportes creados por el usuario autenticado) | **OK** |

## 3. Diagnóstico Técnico y Clasificación de Fallos
- **Total de Pruebas**: 18
- **Aprobadas**: 12
- **Fallidas**: 6

### Análisis de Roles y Permisos (TC-M05-024)
- **Productor**: Autorizado para generar reportes y exportar en CSV/PDF. No autorizado para ver auditoría de M05 (HTTP 403).
- **Veterinario**: Rechazado correctamente con HTTP 403 ACCESO_DENEGADO en generación de reportes, exportaciones, descargas y auditoría.
- **No Autenticado**: Rechazado con HTTP 401 NO_AUTENTICADO en todos los endpoints probados.
- **Aislamiento e IDOR**: Verificada la protección contra descarga de exportaciones de otros usuarios (HTTP 403 ARCHIVO_DE_OTRO_USUARIO) y resistencia a IDs inválidos (404/422, sin 500).

### Análisis de Auditoría (TC-M05-025 - CA-11 / Postcondición 3)
- La especificación RF-77 exige en CA-11 y Postcondición 3 que toda generación y exportación de reportes quede registrada de forma inmutable en la bitácora de auditoría con usuario y timestamp.
- **Hallazgo / Defecto de Producto**: La implementación actual del caso de uso (`GenerarReporteGastosUseCase` y `ExportarReporteGastosUseCase`) no invoca el puerto de auditoría (`auditoria_port.registrar`) durante la generación o exportación exitosa de reportes.
- **Clasificación**: DEFECTO DE PRODUCTO (GAP normativo frente a RF-77 CA-11 / Postcondición 3). No promovible a producción hasta que se implemente la auditoría de RF-77.
