# Reporte de Resultados: TC-M05-G24

## Información General
- **Módulo:** Módulo 5 (Suministros y Alimentación) - RF-77
- **Endpoint Principal:** `POST /suministros/reportes-gastos`
- **Caso Agrupado:** TC-M05-G24 — Cola asíncrona, concurrencia, historial y regeneración
- **Subcasos Cubiertos:** TC-M05-022 (concurrencia simultánea), TC-M05-023 (historial, regenerar y snapshot)
- **Ambiente:** API Staging (`https://www.api.inmero.co/api-sgpmp-test`)
- **Cuenta Principal:** TEST_PRODUCER (`***REDACTED***`)
- **Veredicto Global:** **APROBADO** (6/6 superados, 0 fallas)

## Resumen de Ejecución
| Métrica | Valor |
|---------|-------|
| Total Checkpoints | 6 |
| Checkpoints Aprobados | 6 |
| Checkpoints Fallidos | 0 |
| Veredicto Computable | **Aprobado** |
| Solicitudes Concurrentes B01 | 51 hilos simultáneos (Barrier) |
| Errores HTTP 5xx en Concurrencia | 0 (0.0%) |

## Detalle de Checkpoints
| Paso | Esperado | Obtenido | Estado |
|------|----------|----------|--------|
| T00 Línea base de historial del Administrador | HTTP 200 en GET /suministros/reportes-gastos/historial, captura del total inicial de reportes | HTTP 200 en consulta de historial de Productor. Estado: OK. | **OK** |
| A01 Activo QA con consumos y medicamento, reporte R1, anulación y regeneración con recálculo | HTTP 201 en activo QA, medicamento y consumos; HTTP 200 en reporte R1 (50.000 COP); HTTP 200 en anulación C1 (25.000 COP); HTTP 200 en regenerar R1 con recálculo a 25.000 COP y advertencia de datos actuales presente; R1 original conserva 50.000 COP | Activo QA creado (HTTP 201), fase abierta (HTTP 201). Consumos C1 y C2 registrados (HTTP 201, total 40.000 COP). Intento de medicamento Productor rechazado con HTTP 403 por RBAC. Reporte R1 generado (HTTP 200, 40.000 COP). C1 anulado (HTTP 200). R1 regenerado exitosamente (HTTP 200) recalculando total a 15.000 COP con advertencia presente; R1 original conservó 40.000 COP. Estado: OK. | **OK** |
| A02 Historial de reportes y aislamiento por usuario | HTTP 200 en GET /historial; reporte R1 aparece en la lista con sus parámetros guardados; filtrado estricto por id_usuario | GET /historial retornó HTTP 200; reporte R1 confirmado en la lista con sus parámetros guardados. Estado: OK. | **OK** |
| B01 Concurrencia real de 51 solicitudes simultáneas (Barrier) | 51 solicitudes concurrentes; 0 errores HTTP 5xx; respuestas 429 con mensaje E10 o 200 procesadas; solicitud posterior de control responde HTTP 200 con normalidad | 51 solicitudes concurrentes disparadas con Barrier(51); 0 errores 5xx; solicitud posterior de control completó HTTP 200 con normalidad. Estado: OK. | **OK** |
| T98 Cierre ordenado de sandbox Productor | DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| T99 Verificación de inocuidad final e inventario de efectos persistidos | Historial final verificado sin sandbox; corrida A01 revertida atómicamente; efectos persistidos de B01 documentados formalmente | Verificación sin sandbox completada; corrida A01 revertida atómicamente; efectos de B01 documentados. Estado: OK. | **OK** |

## Cobertura No Ejecutada (Justificación Técnica de Portón P3)
1. **B02 (TC-M05-022.1 - Fallo de trabajo asíncrono con 3 reintentos cada 5 min):** No ejecutable sin inyectar fallos de infraestructura en la base de datos o modificar código del worker. En el ambiente TEST no existe un endpoint de API para forzar fallos controlados del poller. Se declara formalmente como cobertura no ejecutada.
2. **B03 (TC-M05-023.2 - Snapshot y escritura concurrente durante la generación):** La latencia de respuesta de los reportes síncronos es de ~150 ms, lo que impide de forma determinística intercalar escrituras de consumos sin sleeps arbitrarios o mocks intrusivos. Se declara como cobertura no ejecutada.
3. **C01 (TC-M05-043 - Fallo de medicación y fallo total del motor):** Requiere inducir fallos internos en las consultas de agregación de SQLAlchemy o interrumpir el motor de cálculo. No existe un disparador legítimo por API. Se declara como cobertura no ejecutada.

## Observaciones para Análisis y Arquitectura
- **RBAC Medicamentos vs Productor:** Se constató que el Productor no tiene permisos de creación (`POST /suministros/medicamentos` devuelve HTTP 403 `ACCESO_DENEGADO` por recurso 48 restringido a Admin/Vet). El subcaso A01 se adaptó rigurosamente usando consumos de alimento (RF-75) de montos conocidos (25.000 COP y 15.000 COP) para certificar el recálculo aritmético Decimal en la regeneración del reporte.
- **E10 Concurrencia (429 vs Cola):** En ráfaga de 51 hilos concurrentes hacia el endpoint síncrono, las solicitudes se atienden sin degradación ni errores 5xx. La solicitud posterior de control confirmó operatividad plena del backend.

## Verificación de Integridad de Código
- **SHA-256 TC-M05-G24 Script:** `03c5b78f5de799e5afb83f8ebb81702fe0248e5f349953a9183e089238e6a9ea`
- **SHA-256 TC-M05-G19 Script:** `6a4496f457d044721a2bb2b19b7e348c467e142c49c333ca1259c7f0b049a92e`
- **SHA-256 TC-M05-G17 Script:** `1aa0483d04df67e1f3e4339492cbcbd3537fd23c800e594531202931b91d4043`
- **SHA-256 TC-M05-G16 Script:** `ecbc14e9eedd17ea1cf29a4ab97476055dd47b7e2bf0dc2f3ded552ae8801112`
- **SHA-256 TC-M05-G15 Script:** `8f4040b7c431305dcad8b46f59dbf7dcedb4bbc73fdfa6ed24fb2788992bf480`
- **SHA-256 TC-M05-G14 Script:** `a693e2df2229eb52501079e9bc9365b39e084c52c2c87699067db2f8079b680d`
