# Reporte de Prueba: TC-M05-G42 (RF-81)
## Validación de Filtros, Paginación y Niveles de Volumen
### Casos TC-M05-100 y TC-M05-101 (Agrupados 035 y 036)

- **ID Caso:** TC-M05-G42 (Plano: 100, 101 | Agrupado: 035, 036)
- **Ambiente:** `https://www.api.inmero.co/api-sgpmp-test`
- **Veredicto Global:** **RECHAZADO** (3/6 OK, 3 Fallas)
- **Fecha:** 2026-11-07 22:04:23 (America/Bogota)
- **Run ID Sandbox:** `tc-m05-g42-adm-829b1fa1a264`

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Setup de activos y línea base | Creación exitosa de activos A y B con fase productiva abierta y 3 registros de suministros en A (HTTP 201) | Activos A y B creados (HTTP 201), fases abiertas, 3 suministros en A. Estado: FALLA. | **FALLA** |
| 2 | A01 Combinaciones inválidas de filtros (100 / 035) | HTTP 422 para cada combinación (fecha_fin < fecha_inicio, costo_max < costo_min, ciclo ajeno) con mensajes descriptivos específicos que difieren entre sí; sin items ni resumen | HTTP 422 para fecha_fin < fecha_inicio, costo_max < costo_min y ciclo ajeno; mensajes descriptivos y específicos; 0 datos devueltos. Estado: OK. | **OK** |
| 3 | A02 Validación de fecha futura y anterior al ciclo (100 / 035, caso CU04 FA-02) | HTTP 422 para fecha_fin_filtro futura (hoy+1) y fecha_inicio_filtro anterior al ciclo, con mensaje del conflicto específico | AssertionError: Defecto de producto / omisión en spec: la API respondió HTTP 200 en lugar de 422 al filtrar por fecha futura (hoy+1) y fecha anterior al ciclo. (Para decisión de Análisis: RF-81 no define estas validaciones). | **FALLA** |
| 4 | B01 Paginación sobre activo con >= 205 registros (101 / 036) | HTTP 200 con 200 items (param 200); param 201 aplica tope máximo retornando 200 items; metadatos coherentes; orden fecha_aplicacion DESC; suma de costo_registro igual a monto_total_filtrado; pág 2 sin duplicados de pág 1 | Paginación sobre activo 1042 (263 registros): param=200 devolvió 200 items; param=201 aplicó tope devolviendo 200 items; metadatos coherentes; orden DESC; suma calculada coincide con monto_total_filtrado; pág 2 sin duplicados. Estado: FALLA. | **FALLA** |
| 5 | T98 Cierre estricto de corrida sandbox | DELETE /test-control/runs/{run_id} responde HTTP 200 con 'Rollback exitoso' | DELETE /test-control/runs respondió HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| 6 | T99 Inocuidad final fuera de sandbox | Verificación fuera de sandbox: activo propio responde HTTP 404 (0 efectos persistidos) | Verificación sin sandbox completada; activo A responde HTTP 404 (0 efectos persistidos). Estado: OK. | **OK** |

## Cobertura No Ejecutada
1. **Niveles de volumen N2, N3 y N4 (B02 / Restr. 11 / CA-17 / TC-M05-101 / 036):**
   - **Razón:** En el ambiente de pruebas, la tabla `modulo5.registro_suministro` contiene únicamente 467 registros totales en toda la base de datos. El activo con mayor volumen commiteado es el Activo 1042 con 263 registros, seguido del Activo 957 con 208 registros. No existe ningún activo con >= 10.001 registros (N2), >= 50.001 registros (N3) ni >= 200.001 registros (N4). De acuerdo con el protocolo del portón común P2, no se insertan miles de registros artificiales para evitar degradación de ambiente compartido; los subcasos de volumen mayor quedan declarados como cobertura no ejecutada.
2. **Pruebas de concurrencia masiva (CA-12 y CA-16 con 20/50 usuarios):**
   - **Razón:** Restricción de portón P7 para no degradar el ambiente compartido.
3. **Consulta asíncrona forzada por tiempo > 10 s (E7 / CA-14):**
   - **Razón:** No es posible forzar legítimamente un timeout de base de datos sin introducir fallas de infraestructura.

## Observaciones Técnicas para Análisis
- **A02 (Fecha futura y anterior al ciclo):** El caso de prueba derivado de CU04 FA-02 exige rechazar con HTTP 422 fechas futuras (`hoy+1`) y fechas anteriores al inicio del ciclo productivo. Sin embargo, el texto de la especificación técnica RF-81 (Restricción 7 / E5) no contempla explícitamente estas dos validaciones, limitándose a validar `fecha_fin < fecha_inicio`, `costo_max < costo_min` y correspondencia del ciclo. El backend responde HTTP 200 retornando los registros filtrados dentro del rango existente. Se reporta como FALLA por discrepancia entre caso y backend, para decisión de Análisis/Diseño.
- **Límites no definidos:** El envío de `registros_por_pagina=0` y `pagina=0` es manejado por el framework (FastAPI/Pydantic valida `pagina >= 1` devolviendo 422, y `registros_por_pagina=0` valida `>= 1` devolviendo 422).
- **Tipos de Identificador:** La especificación RF-81 menciona UUID en la narrativa de entidades pero el contrato OpenAPI y la base de datos usan enteros (`id_activo_biologico: int`, `id_ciclo_productivo: int`).
