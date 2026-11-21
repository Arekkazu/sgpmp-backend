# Reporte de Prueba: TC-M05-G42 (RF-81)
## Validación de Filtros, Paginación y Niveles de Volumen
### Casos TC-M05-100 y TC-M05-101 (Agrupados 035 y 036)

> **Tipo de corrida:** evaluacion oficial; corrida realizada tras corregir el test; la corrida anterior queda archivada en evidencias/.

- **ID Caso:** TC-M05-G42 (Plano: 100, 101 | Agrupado: 035, 036)
- **Ambiente:** `https://www.api.inmero.co/api-sgpmp-test`
- **Veredicto Global:** **RECHAZADO** (4/6 OK, 2 Fallas)
- **Fecha:** 2026-11-07 22:07:26 (America/Bogota)
- **Run ID Sandbox:** `tc-m05-g42-adm-38882f2241f9`

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Setup de activos y línea base | Creación exitosa de activos A y B con fase productiva abierta y 3 registros de suministros en A (HTTP 201) | Activos A y B creados (HTTP 201), fases abiertas, 3 suministros en A (2 alimentos, 1 medicamento). Estado: OK. | **OK** |
| 2 | A01 Combinaciones inválidas de filtros (100 / 035) | HTTP 422 para cada combinación (fecha_fin < fecha_inicio, costo_max < costo_min, ciclo ajeno) con mensajes descriptivos específicos que difieren entre sí; sin items ni resumen | HTTP 422 para fecha_fin < fecha_inicio, costo_max < costo_min y ciclo ajeno; mensajes descriptivos y específicos; 0 datos devueltos. Estado: OK. | **OK** |
| 3 | A02 Validación de fecha futura y anterior al ciclo (100 / 035, caso CU04 FA-02) | HTTP 422 para fecha_fin_filtro futura (hoy+1) y fecha_inicio_filtro anterior al ciclo, con mensaje del conflicto específico | AssertionError: Defecto de producto / omisión en spec: la API respondió HTTP 200 en lugar de 422 al filtrar por fecha futura (hoy+1) y fecha anterior al ciclo. (Para decisión de Análisis: RF-81 no define estas validaciones). | **FALLA** |
| 4 | B01 Paginación sobre activo con >= 205 registros (101 / 036) | HTTP 200 con 200 items (param 200); param 201 aplica tope máximo retornando 200 items; metadatos coherentes; orden fecha_aplicacion DESC; suma de costo_registro igual a monto_total_filtrado; pág 2 sin duplicados de pág 1 | AssertionError: Defecto de producto: Restricción 5 estipula que 'el sistema aplica el límite máximo si se excede' (esperado HTTP 200 con 200 items para param=201), pero el backend responde HTTP 400 VAL_ENTRADA ('Input should be less than or equal to 200') debido a validación estricta de FastAPI/Pydantic en Query(le=200). | **FALLA** |
| 5 | T98 Cierre estricto de corrida sandbox | DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| 6 | T99 Inocuidad final fuera de sandbox | Verificación fuera de sandbox: activo propio responde HTTP 404 (0 efectos persistidos) | Verificación sin sandbox completada; activo A responde HTTP 404 (0 efectos persistidos). Estado: OK. | **OK** |

## Cobertura No Ejecutada
1. **Niveles de volumen N2, N3 y N4 (B02 / Restr. 11 / CA-17 / TC-M05-101 / 036):**
   - **Razón:** En el ambiente de pruebas, la tabla `modulo5.registro_suministro` contiene únicamente 467 registros totales en toda la base de datos. El activo con mayor volumen commiteado es el Activo 1042 con 263 registros, seguido del Activo 957 con 208 registros. No existe ningún activo con >= 10.001 registros (N2), >= 50.001 registros (N3) ni >= 200.001 registros (N4). De acuerdo con el protocolo del portón común P2, no se insertan miles de registros artificiales para evitar degradación de ambiente compartido; los subcasos de volumen mayor quedan declarados como cobertura no ejecutada.
2. **Pruebas de concurrencia masiva (CA-12 y CA-16 con 20/50 usuarios):**
   - **Razón:** Restricción de portón P7 para no degradar el ambiente compartido.
3. **Consulta asíncrona forzada por tiempo > 10 s (E7 / CA-14):**
   - **Razón:** No es posible forzar legítimamente un timeout de base de datos sin introducir fallas de infraestructura.

## Diagnóstico de Defectos de Producto
### 1. Defecto en A02 (Fecha futura y anterior al ciclo)
- **Hecho Observado:** `GET /suministros/historial` con `fecha_fin_filtro=hoy+1` responde HTTP 200 retornando registros. Con `fecha_inicio_filtro` anterior al inicio del ciclo productivo responde HTTP 200 retornando registros.
- **Ruta de Código (Inferencia):** `src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py:230` (`_validar_filtros()`). La función solo valida `fecha_fin < fecha_inicio`, `costo_max < costo_min` y que el ciclo pertenezca al activo. No contiene validación contra la fecha actual ni contra la fecha de inicio del ciclo.
- **Causa y Clasificación:** Especificación ambigua / discrepancia entre el caso de prueba CU04 FA-02 y la especificación técnica RF-81 (la especificación no definió estas validaciones; el caso sí las exige).

### 2. Defecto en B01 (Tope de registros_por_pagina = 201)
- **Hecho Observado:** `GET /suministros/historial?registros_por_pagina=201` responde HTTP 400 (`error_code: VAL_ENTRADA`, mensaje: `"Input should be less than or equal to 200"`).
- **Ruta de Código (Inferencia):** `src/supplies/infrastructure/routers/historial_suministros_router.py:65`: el parámetro query está definido como `registros_por_pagina: int = Query(default=50, ge=1, le=200)`. La validación declarativa de FastAPI/Pydantic interrumpe la petición con HTTP 400 antes de invocar la lógica de negocio.
- **Causa y Clasificación:** Defecto de producto respecto a la Restricción 5 / RNF-04, la cual estipula taxativamente: *"el sistema aplica el límite máximo si se excede"*, requiriendo clampear el valor a 200 y responder HTTP 200 con 200 items en lugar de rechazar con 400.
