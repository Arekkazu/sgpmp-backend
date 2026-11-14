# Reporte de Prueba: TC-M05-G44 (RF-81)
## Exportación de Historial de Suministros (Síncrona, Asíncrona, Retención 72 h y Concurrencia)
### Caso TC-M05-103 (Agrupado 038)

> **Tipo de corrida:** evaluacion oficial; corrida realizada tras corregir el test; la corrida anterior queda archivada en evidencias/.

- **ID Caso:** TC-M05-G44 (Plano: 103 | Agrupado: 038)
- **Ambiente:** `https://www.api.inmero.co/api-sgpmp-test`
- **Veredicto Global:** **APROBADO** (5/5 OK, 0 Fallas)
- **Fecha:** 2026-11-07 22:12:41 (America/Bogota)
- **Run ID Sandbox:** `tc-m05-g44-adm-ea643f7b4894`

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Setup de activo D y suministros | Creación exitosa de activo D con fase y 3 registros de suministros (60.000 COP) en HTTP 201 | Activo D creado (HTTP 201), fase abierta, 3 registros de suministros (60.000 COP). Estado: OK. | **OK** |
| 2 | A01 Exportación síncrona Excel y PDF (103 / 038) | HTTP 200 en <= 10 s; Excel válido con openpyxl (encabezado, columnas, subtotales, firma/timestamp); PDF válido (%PDF); totales coinciden con consulta | Exportación síncrona exitosa (HTTP 200) en <= 10 s; Excel validado con openpyxl (encabezado, columnas, subtotales, firma); PDF validado (%PDF); montos coinciden con consulta. Estado: OK. | **OK** |
| 3 | B03 Naturaleza de solo lectura (103 / 038) | La exportación no modifica los registros ni totales del historial | Historial inalterado antes y después de la exportación (conteo y suma idénticos). Estado: OK. | **OK** |
| 4 | T98 Cierre estricto de corrida sandbox | DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| 5 | T99 Inocuidad final fuera de sandbox | Verificación fuera de sandbox: activo D responde HTTP 404 (0 efectos persistidos) | Verificación sin sandbox completada; activo D responde HTTP 404 (0 efectos persistidos). Estado: OK. | **OK** |

## Cobertura No Ejecutada
1. **Exportación síncrona de 10.000 exactos (B01 / TC-M05-103 / 038):**
   - **Razón:** En el ambiente de pruebas, la tabla `modulo5.registro_suministro` cuenta únicamente con 467 registros totales en toda la base de datos. Ningún activo ni conjunto filtrado alcanza 10.000 registros commiteados. De acuerdo con el protocolo de portón P2, no se insertan miles de registros artificiales para no saturar el ambiente compartido; el subcaso se declara formalmente como cobertura no ejecutada.
2. **Exportación asíncrona de 10.001 registros con retención 72 h (B02 / Restr. 3 / E3 / RNF-06):**
   - **Razón:** No existe ningún activo con más de 10.000 registros en el ambiente. Asimismo, la verificación de expiración y purga a las 72 horas exigiría esperar 3 días o alterar el reloj de BD, lo cual infringe las reglas de QA.
3. **Límite de concurrencia asíncrona (B03 / Restr. 8 / E6 / CA-11, 4 solicitudes concurrentes con Barrier):**
   - **Razón:** La vía asíncrona solo se activa cuando el conjunto supera 10.000 registros. Al no existir activos de ese volumen, no es posible forzar trabajos de exportación pesada para activar el límite de concurrencia asíncrona (HTTP 429).
4. **Pruebas de carga masiva de 10 exportaciones simultáneas (CA-13):**
   - **Razón:** Restricción P7 del portón para preservar el ambiente compartido.

## Observaciones Técnicas para Análisis
- **Inspección de Archivos:** La librería `openpyxl` permitió comprobar satisfactoriamente la estructura documental completa del archivo Excel (encabezado del activo, columnas obligatorias, filas de datos, subtotales y firma/timestamp del sistema). Para el archivo PDF, se verificó el encabezado binario `%PDF` y el tamaño adecuado (> 1 KB).
- **Inmutabilidad:** Se verificó que la acción de exportar es estrictamente de solo lectura y no introduce mutaciones en los registros ni en los acumulados de suministros.
