# Reporte de Ejecución: TC-M05-G25 (RF-77)

## 1. Identificación y Alcance
- **Caso de Prueba**: TC-M05-G25
- **Requerimiento**: RF-77 (Reporte de Gastos Acumulados por Activo)
- **Subcasos Evaluados**: TC-M05-024 (Roles y Permisos / Aislamiento IDOR), TC-M05-025 (Auditoría de Generación y Exportación)
- **Trazas HTTP Registradas**: 59 (errores de conexión: 0)
- **Duración Medida**: 20.4 s
- **Veredicto Global**: **APROBADO** (23 OK, 0 FALLA)

## 2. Resumen Normativo de Checkpoints
| # | Paso Evaluado | Esperado (Fuente) | Obtenido | Estado |
|---|---------------|-------------------|----------|--------|
| 1 | A01 Generación de reporte sincrónico por Productor | HTTP 200, respuesta con id_reporte_gasto_acumulado y gasto acumulado calculado (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 200, respuesta con id_reporte_gasto_acumulado y gasto acumulado calculado) | **OK** |
| 2 | A02 Exportación de reporte a formato CSV por Productor | HTTP 201, generación de archivo CSV con vigencia de 24 horas y prefijo Gastos_ (Fuente: RF-77 RNF Exportación (TC-M05-024 / CU04)) | Conforme con la especificación (HTTP 201, generación de archivo CSV con vigencia de 24 horas y prefijo Gastos_) | **OK** |
| 3 | A03 Exportación de reporte a formato PDF por Productor | HTTP 201, generación de archivo PDF con prefijo Reporte_Gastos_ (Fuente: RF-77 RNF Exportación (TC-M05-024 / CU04)) | Conforme con la especificación (HTTP 201, generación de archivo PDF con prefijo Reporte_Gastos_) | **OK** |
| 4 | A04 Descarga de exportación propia por Productor | HTTP 200, Content-Type text/csv, Content-Disposition attachment (Fuente: RF-77 RNF Exportación (TC-M05-024)) | Conforme con la especificación (HTTP 200, Content-Type text/csv, Content-Disposition attachment) | **OK** |
| 5 | A05 Restricción de acceso a auditoría de M05 para Productor | HTTP 403 ACCESO_DENEGADO (Recurso 57 restringido a Administrador/Contador) (Fuente: RF-80 / RBAC Centralizado) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO (Recurso 57 restringido a Administrador/Contador)) | **OK** |
| 6 | A98 Cierre ordenado de sandbox Productor y rollback | HTTP 200 con confirmación 'Rollback exitoso' (Fuente: Testing Harness / Sandbox Control) | Conforme con la especificación (HTTP 200 con confirmación 'Rollback exitoso') | **OK** |
| 7 | B01 Restricción de generación de reporte para Veterinario | HTTP 403 ACCESO_DENEGADO (Solo Productor y Administrador pueden generar) (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO (Solo Productor y Administrador pueden generar)) | **OK** |
| 8 | B02 Restricción de exportación de reporte para Veterinario | HTTP 403 ACCESO_DENEGADO (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO) | **OK** |
| 9 | B03 Restricción de descarga de exportación real para Veterinario | HTTP 403 ACCESO_DENEGADO sin contenido CSV al descargar archivo real exportado por Administrador (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO sin contenido CSV al descargar archivo real exportado por Administrador) | **OK** |
| 10 | B04 Restricción de acceso a auditoría para Veterinario | HTTP 403 ACCESO_DENEGADO (Fuente: RF-80 / RBAC Centralizado) | Conforme con la especificación (HTTP 403 ACCESO_DENEGADO) | **OK** |
| 11 | B98 Cierre ordenado de sandbox Veterinario y rollback | HTTP 200 con confirmación 'Rollback exitoso' (Fuente: Testing Harness / Sandbox Control) | Conforme con la especificación (HTTP 200 con confirmación 'Rollback exitoso') | **OK** |
| 12 | C01 Generación y exportación de reporte por Administrador | HTTP 200 en generación y HTTP 201 en exportación CSV (Fuente: RF-77 RNF Seguridad (TC-M05-024)) | Conforme con la especificación (HTTP 200 en generación y HTTP 201 en exportación CSV) | **OK** |
| 13 | C02 Registro en bitácora de auditoría de M05 de generación y exportación de Admin | Exactamente 1 evento GENERACION y 1 evento EXPORTACION con actor Admin, fecha_evento y registro <= 2 s (Fuente: RF-77 CA-11 / Postcondición 3 (TC-M05-025)) | Conforme con la especificación (Exactamente 1 evento GENERACION y 1 evento EXPORTACION con actor Admin, fecha_evento y registro <= 2 s) | **OK** |
| 14 | C03 Registro en bitácora de auditoría de M05 de generación y exportación de Productor | Exactamente 1 evento GENERACION y 1 evento EXPORTACION con actor Productor, fecha_evento y registro <= 2 s (Fuente: RF-77 CA-11 / Postcondición 3 (TC-M05-025)) | Conforme con la especificación (Exactamente 1 evento GENERACION y 1 evento EXPORTACION con actor Productor, fecha_evento y registro <= 2 s) | **OK** |
| 15 | C98 Cierre ordenado de sandbox Administrador y rollback | HTTP 200 con confirmación 'Rollback exitoso' (Fuente: Testing Harness / Sandbox Control) | Conforme con la especificación (HTTP 200 con confirmación 'Rollback exitoso') | **OK** |
| 16 | D01 Rechazo de solicitudes no autenticadas | HTTP 401 sin Authorization (con cabeceras sandbox) en generación, exportación, descarga, historial y auditoría (Fuente: RF-02 / RF-77 RNF Seguridad) | Conforme con la especificación (HTTP 401 sin Authorization (con cabeceras sandbox) en generación, exportación, descarga, historial y auditoría) | **OK** |
| 17 | D02 Prevención de IDOR en descarga de exportaciones ajenas | HTTP 403 (ARCHIVO_DE_OTRO_USUARIO) o 404 (ARCHIVO_NO_ENCONTRADO por RLS de modulo5) sin contenido del archivo al descargar CSV exportado por otro usuario en el mismo sandbox (Fuente: RF-77 RNF Seguridad / TC-M05-024) | Conforme con la especificación (HTTP 403 (ARCHIVO_DE_OTRO_USUARIO) o 404 (ARCHIVO_NO_ENCONTRADO por RLS de modulo5) sin contenido del archivo al descargar CSV exportado por otro usuario en el mismo sandbox) | **OK** |
| 18 | D03 Validación de tipos y resistencia ante IDs inexistentes o inválidos | HTTP 404 en inexistentes, HTTP 400/422 en tipos inválidos; jamás HTTP 500 (Fuente: Guía de Pruebas / Robustez de la API) | Conforme con la especificación (HTTP 404 en inexistentes, HTTP 400/422 en tipos inválidos; jamás HTTP 500) | **OK** |
| 19 | D04 Aislamiento estricto de historial por usuario | GET /historial devuelve los reportes propios del usuario y excluye por completo los de otro usuario (Fuente: RF-77 RNF Historial (TC-M05-024)) | Conforme con la especificación (GET /historial devuelve los reportes propios del usuario y excluye por completo los de otro usuario) | **OK** |
| 20 | D05a Prevención de IDOR al consultar reporte de otro usuario | HTTP 403 o 404 sin datos del reporte ajeno ni eventos indebidos en auditoría (Fuente: RF-77 RNF Seguridad / TC-M05-024) | Conforme con la especificación (HTTP 403 o 404 sin datos del reporte ajeno ni eventos indebidos en auditoría) | **OK** |
| 21 | D05b Prevención de IDOR al regenerar reporte de otro usuario | HTTP 403 o 404 sin datos del reporte ajeno ni evento REGENERACION en auditoría (Fuente: RF-77 RNF Seguridad / TC-M05-024) | Conforme con la especificación (HTTP 403 o 404 sin datos del reporte ajeno ni evento REGENERACION en auditoría) | **OK** |
| 22 | D05c Prevención de IDOR al exportar reporte de otro usuario | HTTP 403 o 404 sin creación de archivo ni evento EXPORTACION en auditoría (Fuente: RF-77 RNF Seguridad / TC-M05-024) | Conforme con la especificación (HTTP 403 o 404 sin creación de archivo ni evento EXPORTACION en auditoría) | **OK** |
| 23 | D98 Cierre ordenado de sandbox IDOR/Aislamiento y rollback | HTTP 200 con confirmación 'Rollback exitoso' (Fuente: Testing Harness / Sandbox Control) | Conforme con la especificación (HTTP 200 con confirmación 'Rollback exitoso') | **OK** |

## 3. Diagnóstico Técnico y Clasificación Derivada de Resultados
- **Total de Pruebas**: 23
- **Aprobadas**: 23
- **Fallidas**: 0
- **Clasificación Global**: **CONFORME** (todos los checkpoints aprobaron en JUnit/trazas).
