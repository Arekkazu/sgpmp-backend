# TC-M06-G38 — APROBADO

## Identificación

Grupo G38; casos TC-M06-014 y TC-M06-015; RF-86 v2.0. RUN: RUN-G38-V1-20261109-025651; versión 1; intento 1; autorización AUT-G38-V1-20261108; ambiente: TEST; commit: no consultado (sin Git). Herramientas verificadas en el RUN: Node v22.15.1, Newman 6.2.2. Registro QA: OFICIAL.

## Decisión del caso

| Caso | Estado | Fundamento |
| --- | --- | --- |
| TC-M06-014 | APROBADO | Dos líneas, cuentas de matriz y valores positivos truncados coinciden. |
| TC-M06-015 | APROBADO | Estructura, identidad y truncado discriminante correctos. |

## Detalle por caso

### TC-M06-014

- Preparación: período 8 ABIERTO, bovino 945 (especie 39) con cálculo previo al precio vigente, sin rebase. La matriz RF-109 se leyó antes de escribir: asignaciones genéricas TB/GANANCIA 158405 → 424805 y PM/PERDIDA 539505 → 158405. El predictor eligió precio MERCADO_ACTIVO 9120.01 y peso 309.06 kg.
- Esperado según la matriz de casos: líneas TB/GANANCIA y PM/PERDIDA del mismo período, valor positivo truncado del componente real y pares de cuentas de la matriz RF-109 vigente. Los importes 4.600.000 y 600.000 son ejemplos de la fila.
- Observado: POST del precio HTTP 201, POST de crecimiento del 945 HTTP 201 y procesamiento HTTP 200. La medición 201 devolvió TB 26232.7968 y PM -138064.3236, exactamente como predijo el predictor. Se crearon las variaciones 259 (ganancia por transformación biológica) y 260 (pérdida por precio de mercado).

| ID | Tipo de hecho | Sentido | Débito | Crédito | Valor | Estado | Variación de origen |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| 906 | VARIACION_VR_TB | GANANCIA | 158405 | 424805 | 26232.79 | REGISTRADA | 259 (GANANCIA_TRANSFORMACION_BIOLOGICA) |
| 907 | VARIACION_VR_PM | PERDIDA | 539505 | 158405 | 138064.32 | REGISTRADA | 260 (PERDIDA_PRECIO_MERCADO) |

- Comparación: la línea 906 debita la cuenta del activo 158405 y acredita ingreso 424805; la 907 debita pérdida 539505 y acredita el activo 158405. Ambas coinciden con los pares de la matriz leída antes del hecho. Los valores 26232.79 y 138064.32 son positivos y corresponden a los componentes de la medición truncados a dos decimales; la pérdida se expresa mediante la inversión de cuentas. Por eso aprueba.
- Decisión: **APROBADO**.

### TC-M06-015

- Preparación: mismo hecho del caso 014 y consulta de todas las líneas del período 8.
- Esperado según la matriz de casos: estructura completa, ID único e inmutable, valor positivo truncado a dos decimales; para el componente discriminante, truncar debe dar un valor distinto de redondear. Equivalencias: id_linea = id_linea_asiento_nic41; nit_titular = numero_id_tributaria; indicador_estimacion = es_estimacion.
- Observado: predicción TB 26232.7968 y PM -138064.3236; medición TB 26232.7968 y PM -138064.3236. El precio elegido fue 9120.01 y el peso 309.06 kg.

| Componente de 4 decimales | Truncado | Redondeado | Valor de la línea |
| --- | ---: | ---: | ---: |
| TB: 26232.7968 | 26232.79 | 26232.80 | 26232.79 |
| PM: -138064.3236 | 138064.32 | 138064.32 | 138064.32 |

- Estructura e identidad: el ejecutor recorrió todas las líneas devueltas para el período 8 y comprobó los campos y tipos exigidos, el valor positivo de dos decimales, la unicidad de cada ID y la inmutabilidad de las líneas previas entre las lecturas anterior y posterior. **El total de líneas del período no se conservó en `resultado.json`**; las dos líneas nuevas acreditadas son 906 y 907. La comprobación aprobó, pero no es posible recuperar un total exacto de los artefactos saneados sin inventarlo. TB distingue truncado (26232.79) de redondeo (26232.80); la línea 906 usa el primero. PM da 138064.32 por ambos métodos.
- Decisión: **APROBADO**; Estructura, identidad y truncado discriminante correctos.

Comprobaciones: 2 API, 0 UI (casos definidos solo para API); solicitudes del ejecutor: 29/150. Newman: 1 iteración, 3 solicitudes, 9 aserciones y 0 fallos.

## Contraste de contrato

- `/finanzas/activos` (ejecutor): coincide, HTTP 200.
- `/finanzas/periodos` (ejecutor): coincide, HTTP 200.
- `/finanzas/precios?id_especie={especie}` (ejecutor): coincide, HTTP 200.
- `/finanzas/activos/{activo}` (ejecutor): coincide, HTTP 200.
- `/activos-biologicos/{activo}/ficha-integral` (ejecutor): coincide, HTTP 200.
- `/finanzas/configuracion` (ejecutor): coincide, HTTP 200.
- `/finanzas/periodos/{periodo}/variaciones` (ejecutor): coincide, HTTP 200.
- `/finanzas/periodos/{periodo}/mediciones` (ejecutor): coincide, HTTP 200.
- `/finanzas/lineas?id_periodo_contable={periodo}` (ejecutor): coincide, HTTP 200.
- `/finanzas/precios` (ejecutor): coincide, HTTP 201.
- `/activos-biologicos/{activo}/eventos/crecimiento` (ejecutor): coincide, HTTP 201.
- `/finanzas/eventos/procesar` (ejecutor): coincide, HTTP 200.
- `/finanzas/configuracion` (Newman): coincide, HTTP 200.
- `/finanzas/lineas?id_periodo_contable={periodo}` (Newman): coincide, HTTP 200.
- `/finanzas/periodos/{periodo}/mediciones` (Newman): coincide, HTTP 200.

Discrepancias registradas: 0.

## Evidencias reales

- resultado.json
- TC-M06-G38_resultado.md
- newman/newman-G38.json
- newman/newman-G38.html

## Incidencias

Ninguna incidencia de producto.

Problemas técnicos: ninguno. Sin discrepancia de producto acreditada; no se asigna severidad ni equipo.

## Cierre y rollback

DELETE HTTP 200; rollback verificado: IDs del RUN ausentes en lecturas públicas. Lecturas poscierre: `/finanzas/periodos/8/variaciones` HTTP 200; `/finanzas/periodos/8/mediciones` HTTP 200; `/finanzas/lineas?id_periodo_contable=8` HTTP 200; `/finanzas/precios?id_especie=39` HTTP 200; `/activos-biologicos/945/eventos` HTTP 200. El precio con centavos registrado durante el RUN queda comprendido en la reversión comprobada mediante la lectura de precios. Según el comportamiento observado en G37, el aviso NIC41 puede no registrarse; se informa aparte y no se atribuye a este RUN.

## Conclusión

Veredictos y cierre según resultado.json; registro OFICIAL. Sin acción correctiva de producto derivada de estos casos.
