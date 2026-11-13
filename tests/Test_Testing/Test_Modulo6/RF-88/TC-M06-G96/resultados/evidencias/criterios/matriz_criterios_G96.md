# Matriz de criterios — TC-M06-G96

| Criterio | Componente responsable | Prueba | Resultado esperado | Evidencia | Demostrado en A+B | Requiere E2E TEST API |
|---|---|---|---|---|---|---|
| 05: libros = 7.000.000 | `valor_libros_calculado` + piso `max(0,…)` / `valor_por_costo` | `test_tc_m06_g96_dominio_A.py` | 7.000.000 | `resultado_dominio.json` · HTML dominio | **Sí (A)** | Opcional si el proyecto exige HTTP |
| 06: libros = 0 solo dep | mismo dominio | dominio A | 0 | dominio | **Sí (A)** | Opcional |
| 07: calculado = −2.000.000 | `valor_libros_calculado` | dominio A + integración #968 | −2.000.000 | dominio + `evidencia_alerta.json` | **Sí (A+B)** | Opcional |
| 07: aplicado = 0 (límite) | `max(CERO, calculado)` en `RegistrarDeterioroUseCase` / `valor_por_costo` | A + `test_valor_en_libros_negativo_…` | 0 | dominio + integración | **Sí (A+B)** | Opcional |
| 07: genera alerta `VALOR_LIBROS_AJUSTADO_A_CERO` | `evento_valor_libros_cero` + `auditar` | integración #968 | 1 evento WARNING | `evidencia_alerta.json` · pytest B | **Sí (B aislada)** | **Sí** si AC exige API TEST |
| 07: alerta consultable | `ConsultarAuditoriaFinancieraUseCase` | integración #968 | payload valor_calculado/aplicado | evidencia | **Sí (B aislada)** | **Sí** vía `GET /finanzas/auditoria` en TEST |
| 07: distinta de `DETERIORO_REGISTRADO` | tipo de evento dedicado | integración #968 | tipo específico | pytest B | **Sí (B)** | Sí en TEST |
| No libros negativos en persistencia | trigger/check + use case | integración | valor_contable ≥ 0 | B | **Sí (B)** | Sí |
| Aislamiento seed 2126/66/886/411 | N/A (no usados) | proceso A+B | sin tocar | diagnóstico | **Sí** | N/A |

## Distinción de capas

| Capacidad | A dominio | B integración aislada | API TEST compartido |
|---|---|---|---|
| Cálculo matemático | Sí | Sí | Pendiente si se exige |
| Regla de límite (≥0) | Sí | Sí | Pendiente |
| Generación de alerta | No | **Sí** | Pendiente |
| Persistencia consultable | No | **Sí** (BD temporal + rollback) | Pendiente |
| Permisos Contador / HTTP real | No | Parcial (stack local) | Pendiente |
