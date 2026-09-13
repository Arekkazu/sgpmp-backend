# INC-M02-98-G96 — RF-51: indicadores inválidos no se rechazan y outlier publicado como válido

**Issue:** #246
**Endpoint:** `GET /activos-biologicos/{id_activo}/indicadores`

El reporte de QA (TC-M02-G96) documenta 4 hallazgos. Los 4 se atienden en este PR.

## Hallazgo 1 (TC-163) — Outlier crítico publicado como válido

**Causa raíz:** `_calcular_ganancia_peso` calculaba `(peso_final - peso_inicial) / dias`
y devolvía el resultado sin ningún control de plausibilidad biológica. Un salto de
+500 kg/día se publicaba con `disponible: true` y sin advertencia.

**Fix:** nuevo umbral `_GDP_MAXIMO_PLAUSIBLE_KG_DIA = 10` en
`SqlAlchemyIndicadoresRepository`. Si `abs(gpd)` lo excede, el indicador se devuelve
con `disponible: false` y advertencia `OUTLIER_CRITICO`, incluyendo el valor calculado
en `variables_usadas.valor_calculado_kg_dia` para trazabilidad.

**Decisión documentada:** el reporte de QA pide "HTTP 500 controlado" para este caso,
pero el propio reporte señala (Observación contractual 1) que el OpenAPI del endpoint
no declara 500, y que la matriz de pruebas y el contrato están desalineados en ese
punto. Devolver 500 (error de servidor) para una condición de calidad de dato
detectada correctamente sería semánticamente incorrecto (500 implica fallo no
controlado del backend, no una regla de negocio aplicada). Se optó por el mismo patrón
ya usado en todo este archivo para "no se puede publicar este indicador"
(`disponible: false` + advertencia), combinado con el fix del Hallazgo 3 (ver abajo):
si se pide `tipo_indicador=CRECIMIENTO` específicamente, la respuesta real es **422**
(`INDICADOR_NO_DISPONIBLE`), no 200 ni 500. Pendiente de alinear con Analisis/QA si
la matriz debe actualizarse en vez del contrato.

No existe en el sistema un catálogo de rangos fisiológicos por especie (RF-51 no lo
define), así que el umbral es global y conservador — ver comentario `ponytail:` en el
código. Si se necesita precisión por especie, requiere una tabla nueva en `modulo9`.

## Hallazgo 2 (TC-161) — Sin validación de compatibilidad especie/sexo

**Causa raíz:** `PRODUCCION` no validaba si el indicador aplica al activo. Un macho sin
eventos productivos recibía `DATOS_INSUFICIENTES` (200, disponible:false) en vez de un
rechazo por incompatibilidad biológica.

**Fix:** `ConsultarIndicadoresUseCase._validar_compatibilidad_biologica`, ejecutada
antes de calcular. Si `tipo_indicador='PRODUCCION'` y el activo es INDIVIDUAL con
`sexo='Macho'`, se rechaza con `ValidationError(code='INDICADOR_NO_APLICABLE_SEXO')`
→ HTTP 400 (como pide el reporte), independientemente de si hay o no datos.

**Decisión documentada:** el reporte pide un "catálogo indicador–especie/sexo" que
hoy no existe en la base de datos (confirmado: `modulo9.metricas_produccion` es un
catálogo de métricas de acuicultura/población — peso, biomasa, densidad, FCR — sin
ninguna noción de especie/sexo). Construir ese catálogo es una feature nueva, no un
bug fix puntual. Se implementó la regla que sí se puede derivar sin inventar
estructura nueva: `PRODUCCION` en este sistema mide salida productiva
(lactancia/postura), biológicamente exclusiva de hembras en cualquier especie que
trackea el módulo — de ahí el bloqueo por sexo. Si Análisis confirma que se necesita
granularidad por especie además de sexo, requiere diseño de catálogo aparte.

## Hallazgo 3 (TC-160) — Muestra insuficiente responde 200 en vez de 422

**Causa raíz:** todo el archivo usa un único patrón para "no se pudo calcular":
`disponible: false` + advertencia, siempre HTTP 200 — sin distinguir si el llamador
pidió un indicador específico (donde la ausencia de dato es la única respuesta) o
`TODOS` (donde otros indicadores del mismo request sí pueden tener datos).

**Fix:** en `ConsultarIndicadoresUseCase.execute`, después de calcular: si
`tipo_indicador != 'TODOS'` y ningún indicador resultante quedó `disponible=True`,
se lanza `BusinessRuleError(code='INDICADOR_NO_DISPONIBLE')` → HTTP 422.

**Por qué no cambiar el contrato para `TODOS`:** forzar 422 también en ese caso
descartaría indicadores válidos junto con los no disponibles en la misma respuesta
(ej. `ganancia_peso` sin datos pero `tasa_morbilidad` sí disponible) — el formato
200 + `disponible` por indicador sigue siendo la única forma correcta de exponer un
resultado mixto. Esto también resuelve el caso del outlier del Hallazgo 1 cuando se
pide `tipo_indicador=CRECIMIENTO` en solitario.

## Hallazgo 4 (TC-162) — `conversion_alimenticia` nunca calculaba (REQUIERE_M05)

**Causa raíz:** el indicador se construía como constante `disponible: false` con
advertencia `REQUIERE_M05`, sin consultar nunca `modulo5.registros_consumo_alimentos`
pese a que la tabla y los datos ya existen (M05 sí está implementado).

**Fix:** nuevo método `_calcular_conversion_alimenticia`:
1. Reutiliza `_calcular_ganancia_peso` para la ganancia neta de peso en el período
   (`peso_final_kg - peso_inicial_kg`); si no hay ganancia válida (incluye el caso
   outlier del Hallazgo 1), devuelve `DATOS_INSUFICIENTES`.
2. Si la ganancia es <= 0, devuelve `DATOS_INSUFICIENTES` (no puede dividirse).
3. Suma `cantidad_suministrada` de `modulo5.registros_consumo_alimentos` con
   `estado_registro='VALIDADO'` y `tipo_unidad` en kg, en el rango de fechas.
4. Si el consumo es 0, devuelve `DATOS_INSUFICIENTES` (evita división por cero sin
   lanzar excepción).
5. En caso contrario: `FCR = kg_alimento / kg_ganancia`.

**Alcance limitado documentado:** solo se suman registros cuyo `tipo_unidad` ya está
en kg (`kg`, `kilogramo`, `kilogramos`); registros en otras unidades se ignoran en
vez de convertirse, para no introducir una tabla de conversión de unidades no pedida
por este issue. Si se necesitan otras unidades, es una extensión aparte.

## Archivos

- `src/biological_assets/infrastructure/repositories/indicadores_repository.py` — umbral outlier, `_calcular_conversion_alimenticia`
- `src/biological_assets/application/use_cases/gestion/consultar_indicadores_use_case.py` — `_validar_compatibilidad_biologica`, regla 422 por indicador específico
- `tests/biological_assets/test_indicadores_repository.py` — nuevo (outlier, FCR, división por cero)
- `tests/biological_assets/test_consultar_indicadores_use_case.py` — 4 casos nuevos
- `anotaciones/modulo_2/curls_m02_cu12_indicadores_datos.md` — E-06, E-07, E-08 + actualización de Flujo A

## Verificación

- `pytest tests/biological_assets/` — 70 passed (62 existentes tras el PR #270 de
  #247 + 4 nuevos en `test_consultar_indicadores_use_case.py` + 4 nuevos en
  `test_indicadores_repository.py`).

## Fuera de alcance

Las observaciones contractuales del reporte (alinear OpenAPI vs. matriz de QA en
códigos 409/500, y alinear la granularidad de indicadores de la matriz vs. el
contrato `CRECIMIENTO/PRODUCCION/SANITARIO/EFICIENCIA`) son decisiones de
documentación/proceso, no de código — quedan pendientes de acuerdo con Análisis/QA.
