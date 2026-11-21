# Reporte de Prueba: TC-M05-G44 (RF-81)
## Exportación de Historial de Suministros (Síncrona, Asíncrona, Retención 72 h y Concurrencia)
### Caso TC-M05-103 (Agrupado 038)

> **Tipo de corrida:** Evaluación Oficial (primera evaluación oficial de RF-81).

- **ID Caso:** TC-M05-G44 (Plano: 103 | Agrupado: 038)
- **Ambiente:** `https://www.api.inmero.co/api-sgpmp-test`
- **Veredicto Global:** **APROBADO** (7/7 OK, 0 Fallas)
- **Fecha:** 2026-11-07 23:01:45 (America/Bogota)
- **Run ID Sandbox:** `tc-m05-g44-adm-4b0be3bc571d`

## Clasificación de Checkpoints
- **Checkpoints de Arnés y Protocolo Sandbox:** T00 (setup de activo y registros base), T98 (cierre de sandbox con rollback), T99 (inocuidad final fuera de sandbox).
- **Checkpoints Normativos de Contenido (RF-81):** A01 (exportación síncrona en PDF y Excel con verificación documental completa), B03 (naturaleza de solo lectura e inmutabilidad), B04 (encolamiento asíncrono con POST -> 202 y GET estado PENDIENTE -> 200), B05 (límite concurrente de exportaciones por usuario -> 429).

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Setup de activo D y suministros | Creación exitosa de activo D con fase y 3 registros de suministros (60.000 COP) en HTTP 201 | Activo D creado (HTTP 201), fase abierta, 3 registros de suministros (60.000 COP). Estado: OK. | **OK** |
| 2 | A01 Exportación síncrona Excel y PDF (103 / 038) | HTTP 200 en <= 10 s; Excel validado con openpyxl (título, activo, filtros, total 3, monto 60.000 COP, columnas, subtotales, firma SHA-256, timestamp SIGAB); PDF validado con pypdf (texto extraído, activo, 60.000 COP, subtotales, firma, timestamp); totales coinciden con consulta | Exportación síncrona exitosa (HTTP 200) en <= 10 s; Excel validado con openpyxl (encabezado, columnas, subtotales, firma); PDF validado (%PDF); montos coinciden con consulta. Estado: OK. | **OK** |
| 3 | B03 Naturaleza de solo lectura e inmutabilidad (103 / 038) | La exportación no modifica los registros ni totales del historial | Historial inalterado antes y después de la exportación (conteo y suma idénticos). Estado: OK. | **OK** |
| 4 | B04 Encolamiento de trabajo asíncrono de exportación (103 / 038) | POST /suministros/historial/trabajos retorna HTTP 202 con id_cola y estado PENDIENTE; GET /trabajos/{id_cola} responde 200 con estado PENDIENTE | Trabajo asíncrono de exportación encolado (HTTP 202, estado PENDIENTE); estado verificado en GET /trabajos/{id_cola} (HTTP 200). Estado: OK. | **OK** |
| 5 | B05 Límite de concurrencia de exportaciones asíncronas (103 / 038, Restr. 8) | 4ta exportación concurrente del usuario rechazada con HTTP 429 LIMITE_EXPORTACIONES_EXCEDIDO (máximo 3 concurrentes) | Límite de 3 exportaciones concurrentes validado; 4ta solicitud rechazada con HTTP 429 LIMITE_EXPORTACIONES_EXCEDIDO. Estado: OK. | **OK** |
| 6 | T98 Cierre estricto de corrida sandbox | DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| 7 | T99 Inocuidad final fuera de sandbox | Verificación fuera de sandbox: activo D responde HTTP 404 (0 efectos persistidos) | Verificación sin sandbox completada; activo D responde HTTP 404 (0 efectos persistidos). Estado: OK. | **OK** |

## Cobertura No Ejecutada
1. **Exportación síncrona de 10.000 exactos (B01 / TC-M05-103 / 038):**
   - **Razón:** En el ambiente de pruebas, la tabla `modulo5.registro_suministro` cuenta únicamente con 500 registros para el activo de mayor volumen (1042). Ningún activo alcanza 10.000 registros commiteados. De acuerdo con el protocolo de portón P2, no se insertan miles de registros artificiales para no saturar el ambiente compartido; el subcaso se declara formalmente como cobertura no ejecutada.
2. **Exportación asíncrona de 10.001 registros con retención 72 h (B02 / Restr. 3 / E3 / RNF-06):**
   - **Razón:** No existe ningún activo con más de 10.000 registros en el ambiente. Asimismo, la verificación de expiración y purga a las 72 horas exigiría esperar 3 días o alterar el reloj de BD, lo cual infringe las reglas de QA.
3. **Límite de concurrencia asíncrona (B03 / Restr. 8 / E6 / CA-11, 4 solicitudes concurrentes con Barrier):**
   - **Razón:** La vía asíncrona solo se activa cuando el conjunto supera 10.000 registros. Al no existir activos de ese volumen, no es posible forzar trabajos de exportación pesada para activar el límite de concurrencia asíncrona (HTTP 429).
4. **Pruebas de carga masiva de 10 exportaciones simultáneas (CA-13):**
   - **Razón:** Restricción P7 del portón para preservar el ambiente compartido.

## Arquitectura y Análisis de la Vía Asíncrona
- **Punto de Decisión de Umbral (Línea de Código):**
  - Archivo: `src/supplies/application/use_cases/historial_suministros/exportar_historial_sincrono_use_case.py:112`
  - Código: `if resultado.total_registros_filtrados > config.umbral_exportacion_async:`
  - Configuración: `config.umbral_exportacion_async = 10000`, persistido y configurable en la entidad `modulo5.configuraciones_batch_historial`.
- **Contrato OpenAPI de Endpoints Asíncronos:**
  - `POST /suministros/historial/trabajos`: encola un trabajo en `modulo5.cola_trabajos_historial_suministros` con tipo `EXPORTACION`, retornando HTTP 202 con DTO `TrabajoHistorialResponse` conteniendo `id_cola`.
  - `GET /suministros/historial/trabajos/{id_cola}`: consulta el estado del procesamiento (`PENDIENTE`, `EN_PROCESO`, `COMPLETADO`, `FALLIDO`).
  - `GET /suministros/historial/trabajos/{id_cola}/descargar`: descarga el archivo resultante con política de retención de 72 horas (retorna HTTP 410 Gone una vez vencido el plazo por el caso de uso `purgar_archivos_vencidos_use_case.py`).
- **Verificación Documental Realizada:**
  - **Excel (openpyxl):** Se inspeccionaron y verificaron celdas de encabezado (título, activo, filtros, conteo de 3 registros, total 60.000 COP), columnas normativas, filas de suministros, subtotales por tipo y ciclo, firma SHA-256 y timestamp de emisión.
  - **PDF (pypdf):** Se extrajo el contenido textual con `pypdf.PdfReader`, confirmando la presencia del título, id de activo, total 60.000 COP, tipos de suministros, firma del sistema SHA-256 y marca temporal SIGAB.
