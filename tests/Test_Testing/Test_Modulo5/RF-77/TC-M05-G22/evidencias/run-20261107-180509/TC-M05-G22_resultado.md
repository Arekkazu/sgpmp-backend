# Reporte de Resultados: TC-M05-G22

## Información General
- **Módulo:** Módulo 5 (Suministros y Alimentación) - RF-77
- **Endpoint Principal:** `POST /suministros/reportes-gastos`
- **Caso Agrupado:** TC-M05-G22 — Validación de rango y límites síncrono/asíncrono
- **Subcasos Cubiertos:** TC-M05-017 (validaciones E2, E3, E7, E9 y fecha futura), TC-M05-019 (límites de 12 meses individual y 6 meses agregado, E4 y E8)
- **Ambiente:** API Staging (`https://www.api.inmero.co/api-sgpmp-test`)
- **Cuenta Principal:** TEST_ADMIN
- **Veredicto Global:** **APROBADO** (12/12 superados, 0 fallas)

## Resumen de Ejecución
| Métrica | Valor |
|---------|-------|
| Total Checkpoints | 12 |
| Checkpoints Aprobados | 12 |
| Checkpoints Fallidos | 0 |
| Veredicto Computable | **Aprobado** |

## Detalle de Checkpoints
| Paso | Esperado | Obtenido | Estado |
|------|----------|----------|--------|
| T00 Línea base de historial del Administrador y setup de activo | HTTP 200 en GET /suministros/reportes-gastos/historial, activo individual creado con ciclo en 2025-08-01 | HTTP 200 en consulta de historial de Administrador y activo QA con ciclo antiguo creado exitosamente. Estado: OK. | **OK** |
| A01 Rango de fechas invertido (inicio > fin, E2) | HTTP 400, error_code 'RANGO_FECHAS_INVALIDO' y el historial de reportes no crece | HTTP 400 'RANGO_FECHAS_INVALIDO' obtenido; historial inalterado. Estado: OK. | **OK** |
| A02 Rango con fecha de fin futura (mañana, Restr. 2) | HTTP 400, error_code 'FECHA_FIN_FUTURA' y el historial de reportes no crece | HTTP 400 'FECHA_FIN_FUTURA' obtenido ante fecha de fin de mañana; historial inalterado. Estado: OK. | **OK** |
| A03 Fecha de inicio anterior al ciclo productivo (E3) | HTTP 400, error_code 'FECHA_INICIO_ANTERIOR_CICLO' y el historial de reportes no crece | HTTP 400 'FECHA_INICIO_ANTERIOR_CICLO' obtenido; historial inalterado. Estado: OK. | **OK** |
| A04 Activo biológico sin ciclo productivo registrado (E7) | HTTP 422, error_code 'ACTIVO_SIN_CICLO' y el historial de reportes no crece | HTTP 422 'ACTIVO_SIN_CICLO' obtenido sobre activo 9 (fecha_inicio_ciclo null); historial inalterado. Estado: OK. | **OK** |
| A05 Consulta agregada sin rango de fechas obligatorio (E9) | HTTP 400, error_code 'VAL_ENTRADA' y el historial de reportes no crece | HTTP 400 'VAL_ENTRADA' obtenido ante consulta agregada sin rango de fechas; historial inalterado. Estado: OK. | **OK** |
| B01 Límite síncrono para activo individual de 12 meses (<= 366 días) | HTTP 200 síncrono en tiempo <= 12 s (CA-7 / RNF) | Reporte individual de 12 meses respondió HTTP 200 síncrono en <= 12 s con id_reporte_gasto_acumulado generado. Estado: OK. | **OK** |
| B02 Umbral asíncrono para activo individual que supera 12 meses (E4) | HTTP 202 con id_cola, estado 'PENDIENTE' y mensaje explicativo del procesamiento asíncrono | Reporte individual de 380 días (> 12 meses) respondió HTTP 202 con id_cola y estado PENDIENTE. Estado: OK. | **OK** |
| B03 Límite síncrono para consulta agregada de 6 meses (<= 183 días) | HTTP 200 síncrono en tiempo <= 12 s (Restr. 13) | Consulta agregada de 6 meses respondió HTTP 200 síncrono en <= 12 s con id_reporte_gasto_acumulado generado. Estado: OK. | **OK** |
| B04 Umbral asíncrono para consulta agregada que supera 6 meses (E8) | HTTP 202 con id_cola, estado 'PENDIENTE' y mensaje explicativo del procesamiento asíncrono | Consulta agregada de 196 días (> 6 meses) respondió HTTP 202 con id_cola y estado PENDIENTE. Estado: OK. | **OK** |
| T98 Cierre ordenado de sandbox Administrador | DELETE /test-control/runs/<run_id> responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| T99 Verificación de inocuidad final e integridad de la base | Historial de reportes del Administrador fuera de sandbox coincide exactamente con la línea base capturada en T00 (0 efectos persistidos) | Verificación sin sandbox completada; historial final coincide 100% con línea base (0 efectos persistidos). Estado: OK. | **OK** |

## Observaciones para Análisis y Arquitectura
1. **Validaciones de Reglas de Negocio (RF-77 E2, E3, E7, E9):**
   - E2: Rango invertido (`fecha_inicio > fecha_fin`) responde HTTP 400 (`RANGO_FECHAS_INVALIDO`).
   - E3: Fecha de inicio anterior al ciclo productivo responde HTTP 400 (`FECHA_INICIO_ANTERIOR_CICLO`).
   - E7: Activo biológico sin ciclo productivo (fecha_inicio_ciclo null, Activo 9) responde HTTP 422 (`ACTIVO_SIN_CICLO`).
   - E9: Consulta agregada sin rango de fechas responde HTTP 400 (`VAL_ENTRADA`).
   - En todos los casos de validación se comprobó que el historial de reportes no creció (cero reportes generados indebidamente).
2. **Fecha Fin Futura (Restricción 2):**
   - La especificación de RF-77 indica en la Restricción 2 que la fecha fin no puede ser futura, pero no asigna un código E formal en la tabla de flujos alternos. El backend responde consistentemente con HTTP 400 (`FECHA_FIN_FUTURA`). Se reporta esta omisión formal de la spec como observación de diseño.
3. **Umbrales Síncronos y Asíncronos (RF-77 E4 y E8):**
   - **Activo Individual:** Un rango de 12 meses exactos (365 días <= 366 días) se procesa síncronamente respondiendo HTTP 200 en <= 12 s (cumpliendo CA-7 / RNF). Al superar 12 meses (380 días > 366 días), el sistema responde HTTP 202 con `id_cola`, estado `PENDIENTE` y mensaje explicativo del encolamiento asíncrono.
   - **Consulta Agregada:** Un rango de 6 meses (181 días <= 183 días) responde HTTP 200 síncrono en <= 12 s. Al superar 6 meses (196 días > 183 días), responde HTTP 202 con `id_cola`.
   - **Conflicto en la Spec (E8 vs Restricción 13/RNF):** En la tabla de errores de la especificación, E8 dice "agregada que supera 12 meses", mientras que la Restricción 13 y el RNF fijan 6 meses para consultas agregadas. El backend implementa correctamente el límite más seguro y performante de 6 meses (183 días).
4. **Tiempo de Respuesta (CA-7 / RNF vs Restricción 8):**
   - La Restricción 8 menciona 15 s, mientras que CA-7 y RNF especifican 12 s. El backend responde ampliamente dentro de la norma más estricta (< 2 s en promedio).

## Verificación de Integridad de Código
- **SHA-256 TC-M05-G22 Script:** `cbd5b58f324f53df7298459add3e6bb7a608f68c0aa292de7fe630bca9b24000`
- **SHA-256 TC-M05-G21 Script:** `4f90a333eb7589feddadce6851bc3e4cdb0c7ea8b6831367b030c636fb0e146b`
- **SHA-256 TC-M05-G20 Script:** `bcb674ef267b6c45d7df2be8b0718589213395f9359d50dd5c6fb7fa4d969f61`
- **SHA-256 TC-M05-G25 Script:** `6c58e9b4963b0aaa93b55be903117957afe6d235a2252f8ce3eefdb473127cbe`
- **SHA-256 TC-M05-G24 Script:** `03c5b78f5de799e5afb83f8ebb81702fe0248e5f349953a9183e089238e6a9ea`
- **SHA-256 TC-M05-G19 Script:** `6a4496f457d044721a2bb2b19b7e348c467e142c49c333ca1259c7f0b049a92e`
- **SHA-256 TC-M05-G17 Script:** `1aa0483d04df67e1f3e4339492cbcbd3537fd23c800e594531202931b91d4043`
- **SHA-256 TC-M05-G16 Script:** `ecbc14e9eedd17ea1cf29a4ab97476055dd47b7e2bf0dc2f3ded552ae8801112`
- **SHA-256 TC-M05-G15 Script:** `8f4040b7c431305dcad8b46f59dbf7dcedb4bbc73fdfa6ed24fb2788992bf480`
- **SHA-256 TC-M05-G14 Script:** `a693e2df2229eb52501079e9bc9365b39e084c52c2c87699067db2f8079b680d`
