# Reporte de Resultados: TC-M05-G21

## Información General
- **Módulo:** Módulo 5 (Suministros y Alimentación) - RF-77
- **Endpoint Principal:** `POST /suministros/reportes-gastos`
- **Caso Agrupado:** TC-M05-G21 — Sin costo registrado, sin datos y análisis de tendencia
- **Subcasos Cubiertos:** TC-M05-016 (sin datos E1), TC-M05-018 (los 4 escenarios de tendencia a, b, c, d)
- **Ambiente:** API Staging (`https://www.api.inmero.co/api-sgpmp-test`)
- **Cuenta Principal:** TEST_ADMIN
- **Veredicto Global:** **APROBADO** (8/8 superados, 0 fallas)

## Resumen de Ejecución
| Métrica | Valor |
|---------|-------|
| Total Checkpoints | 8 |
| Checkpoints Aprobados | 8 |
| Checkpoints Fallidos | 0 |
| Veredicto Computable | **Aprobado** |

## Detalle de Checkpoints
| Paso | Esperado | Obtenido | Estado |
|------|----------|----------|--------|
| T00 Línea base de historial del Administrador | HTTP 200 en GET /suministros/reportes-gastos/historial, captura del total inicial de reportes | HTTP 200 en consulta de historial de Administrador. Estado: OK. | **OK** |
| A02 Rango de fechas sin registros con costo (E1) | HTTP 200; estado 'SIN_DATOS', sin_datos=True, gasto_total_acumulado = 0 COP y mensaje de RF-77 E1 | Reporte en rango sin gastos retornó HTTP 200; estado = 'SIN_DATOS', sin_datos = True, total = 0 COP y mensaje explicativo E1 presente. Estado: OK. | **OK** |
| B01 Tendencia escenario (a): anterior > 0 y actual > 0 | HTTP 200; estado 'CALCULADA', variación porcentual calculada exactamente según la fórmula (+50.00%) | Reporte con anterior=20.000 COP y actual=30.000 COP retornó HTTP 200; estado = 'CALCULADA', variacion_porcentual = +50.00% exacto según fórmula. Estado: OK. | **OK** |
| B02 Tendencia escenario (b): anterior = 0 y actual > 0 | HTTP 200; estado 'SIN_BASE_COMPARATIVA', variacion_porcentual=None y nota de ausencia de gastos en período anterior | Reporte con anterior=0 y actual=25.000 COP retornó HTTP 200; estado = 'SIN_BASE_COMPARATIVA', variacion_porcentual = None y nota normativa presente. Estado: OK. | **OK** |
| B03 Tendencia escenario (c): anterior = 0 y actual = 0 | HTTP 200; estado 'SIN_MOVIMIENTO' y variacion_porcentual=None | Reporte con anterior=0 y actual=0 retornó HTTP 200; estado = 'SIN_MOVIMIENTO' y variacion_porcentual = None. Estado: OK. | **OK** |
| B04 Tendencia escenario (d): período anterior recortado al ciclo | HTTP 200; estado 'CALCULADA', período recortado al inicio del ciclo y nota informativa con la fecha del ciclo | Reporte con período anterior recortado al ciclo (2026-08-10) retornó HTTP 200; estado = 'CALCULADA', anterior=10.000 COP, actual=15.000 COP (+50.00%) y nota de recorte presente. Estado: OK. | **OK** |
| T98 Cierre ordenado de sandbox Administrador | DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| T99 Verificación de inocuidad final e integridad de la base | Historial de reportes del Administrador fuera de sandbox coincide exactamente con la línea base capturada en T00 (0 efectos persistidos) | Verificación sin sandbox completada; historial final coincide 100% con línea base (0 efectos persistidos). Estado: OK. | **OK** |

## Cobertura No Ejecutada (Justificación Técnica de Portón P1)
- **A01 (TC-M05-016 - Registros sin costo unitario / SIN_COSTO_REGISTRADO):**
  Tanto `POST /suministros/consumo-alimentos` (RF-75) como `POST /suministros/medicamentos` (RF-76) validan estrictamente `costo_unitario > 0` a través de sus esquemas Pydantic (`RegistrarConsumoAlimentoDTO` y `RegistrarMedicamentoDTO`), respondiendo HTTP 400 (`VAL_ENTRADA`) ante valores `null` o `<= 0`.
  Dado que la API del producto no permite registrar insumos sin costo por ninguna vía legítima, este escenario no es alcanzable a través del contrato expuesto. Conforme a las instrucciones del manual y del prompt, este subcaso se declara formalmente como **COBERTURA NO EJECUTADA** sin simularlo artificialmente en base de datos.

## Observaciones para Análisis y Arquitectura
1. **Reporte SIN_DATOS (RF-77 E1):** Cuando no existen gastos con costo en el período consultado, el endpoint responde HTTP 200, asigna `estado = "SIN_DATOS"`, `sin_datos = True`, total monetario en cero y emite el mensaje explicativo estipulado por el requerimiento.
2. **Los Cuatro Escenarios de Tendencia (RF-77 Restr. 10):**
   - **Escenario (a) Calculada:** Con gasto anterior > 0 y actual > 0, calcula la variación porcentual exacta (+50.00%).
   - **Escenario (b) Sin Base Comparativa:** Con anterior = 0 y actual > 0, devuelve `estado = "SIN_BASE_COMPARATIVA"`, variación `null` y la nota explicativa formal.
   - **Escenario (c) Sin Movimiento:** Con anterior = 0 y actual = 0, devuelve `estado = "SIN_MOVIMIENTO"` y variación `null`.
   - **Escenario (d) Recorte de Período al Ciclo:** Cuando el período anterior cae antes de la fecha de inicio del ciclo productivo, el sistema lo recorta automáticamente al inicio del ciclo y añade la nota explicativa especificando la fecha exacta.
3. **Inconsistencia de la Especificación en Ejemplo de Período Anterior:** La especificación cita un ejemplo de 31 días (01/03 a 31/03) asignando como anterior "29/01 a 28/02" (que no tiene 31 días). La implementación real sigue correctamente la definición matemática formal ("misma cantidad de días inmediatamente antes").

## Verificación de Integridad de Código
- **SHA-256 TC-M05-G21 Script:** `4f90a333eb7589feddadce6851bc3e4cdb0c7ea8b6831367b030c636fb0e146b`
- **SHA-256 TC-M05-G20 Script:** `bcb674ef267b6c45d7df2be8b0718589213395f9359d50dd5c6fb7fa4d969f61`
- **SHA-256 TC-M05-G25 Script:** `6c58e9b4963b0aaa93b55be903117957afe6d235a2252f8ce3eefdb473127cbe`
- **SHA-256 TC-M05-G24 Script:** `03c5b78f5de799e5afb83f8ebb81702fe0248e5f349953a9183e089238e6a9ea`
- **SHA-256 TC-M05-G19 Script:** `6a4496f457d044721a2bb2b19b7e348c467e142c49c333ca1259c7f0b049a92e`
- **SHA-256 TC-M05-G17 Script:** `1aa0483d04df67e1f3e4339492cbcbd3537fd23c800e594531202931b91d4043`
- **SHA-256 TC-M05-G16 Script:** `ecbc14e9eedd17ea1cf29a4ab97476055dd47b7e2bf0dc2f3ded552ae8801112`
- **SHA-256 TC-M05-G15 Script:** `8f4040b7c431305dcad8b46f59dbf7dcedb4bbc73fdfa6ed24fb2788992bf480`
- **SHA-256 TC-M05-G14 Script:** `a693e2df2229eb52501079e9bc9365b39e084c52c2c87699067db2f8079b680d`
