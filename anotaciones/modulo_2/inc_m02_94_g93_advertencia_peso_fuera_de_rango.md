# INC-M02-94-G93 — `metricas_actuales` sin indicar peso fuera del rango solicitado (issue #392)

**RF:** RF-50 — Disponibilidad de datos para módulos analíticos
**CU:** CU12 / **Caso relacionado:** TC-M02-157 / **Grupo:** TC-M02-G93
**Endpoint:** `GET /activos-biologicos/{id_activo}/datos-consolidados`
**Tipo:** Observación / investigación funcional (no es la ejecución oficial de TC-M02-157, que sigue bloqueada hasta usar la identidad M06 — ya sembrada en INC-M02-93-G93/#391)

---

## Diagnóstico de QA (resumen)

Con activo 279 y rango `2026-06-01 → 2026-08-31` (0 métricas PESO dentro del
rango, 4 fuera — en septiembre), `GET .../datos-consolidados?tipo_dato=metricas`
respondía `200 OK` con `historial_eventos: []` (correcto, sí respeta el
rango) pero `metricas_actuales.peso_actual=250.0` y
`.fecha_ultimo_peso=2026-09-10` — un valor de fuera del rango solicitado, sin
ninguna indicación de que no pertenece al periodo pedido. QA marcó el riesgo:
un consumidor de valoración NIC-41 podría interpretar ese peso como
representativo del rango consultado.

QA pidió confirmar contractualmente 5 puntos antes de implementar. Este
documento responde cada uno con su decisión y justificación.

---

## Paso 0 — Investigación del código real

`_obtener_metricas()` en `indicadores_repository.py` no recibía
`fecha_inicio`/`fecha_fin` en absoluto: consulta
`modulo2.vw_rf47_ficha_integral_activo`, una vista que siempre trae el
**peso más reciente jamás registrado** del activo (`ORDER BY ea.fecha DESC
... LIMIT 1`, sin filtro de fecha), sin importar qué rango pida el
consumidor.

## Decisiones (respuesta a los 5 puntos que pidió QA)

1. **¿`metricas_actuales` ignora deliberadamente `fecha_inicio`/`fecha_fin`?**
   Sí, y se mantiene así — es el significado del propio nombre del campo
   (`peso_*actual*`, `fecha_ultimo_peso`: el estado *actual/más reciente*
   del activo, no un valor del periodo). Filtrarlo por rango cambiaría su
   semántica para cualquier consumidor que lo use para "¿cuál es el peso de
   este activo ahora?" combinado con un rango que solo aplica a
   `historial_eventos` (uso legítimo y ya soportado hoy).
2. **¿Debe señalarse que la métrica queda fuera del periodo consultado?**
   Sí — es el fix de este ticket: nueva clave opcional
   `advertencia_peso_fuera_de_rango: str` dentro de `metricas_actuales`,
   presente solo cuando se pidió un rango (`fecha_inicio` y/o `fecha_fin`) y
   `fecha_ultimo_peso` cae fuera de él.
3. **¿`metricas_actuales` debería respetar también el filtro temporal?**
   No (ver punto 1) — se prefirió advertir en vez de filtrar/ocultar, para
   no romper el caso de uso "estado actual" y para que el consumidor decida
   qué hacer con el dato en vez de que el backend se lo oculte en silencio.
4. **¿Dónde debe implementarse la regla de suficiencia de métricas PESO?**
   Ya resuelto en INC-M02-93-G93 (#391, mismo grupo de issues): existe
   `IndicadoresRepository.contar_metricas_peso_en_rango()` + la validación en
   `ConsultarDatosConsolidadosUseCase`, acotada a M06 (consistencia fuerte).
   Este ticket no duplica esa regla — la complementa (ver "Interacción con
   INC-M02-93-G93" abajo).
5. **¿En qué condiciones debe devolverse HTTP 422?** Sin cambios respecto a
   INC-M02-93-G93: solo cuando el consumidor es M06 y no hay **ninguna**
   métrica PESO dentro del rango. Este ticket no amplía el 422 a otros
   consumidores — ver justificación abajo.

### Por qué el 422 no se amplía a todos los consumidores

El propio riesgo que reporta QA está enmarcado explícitamente en valoración
NIC-41 (*"Si esta respuesta fuese consumida directamente para una valoración
NIC-41..."*), y RF-50 distingue "consistencia fuerte" (M06) de "consistencia
eventual" (resto, ej. dashboards M08) como una diferenciación intencional,
no un descuido. Rechazar con 422 a un consumidor de "consistencia eventual"
por no tener peso en un rango arbitrario sería más estricto de lo que el
propio RF pide para ese tipo de consumo, y regresionaría el comportamiento
actual (200 con métricas) para Administrador/Productor/Veterinario/Ingeniero
de Campo sin que el RF lo exija. En su lugar, la advertencia explícita
(punto 2) resuelve el riesgo real señalado — "que se interprete sin
indicación" — sin ese costo.

### Interacción con INC-M02-93-G93 (#391)

Ambos fixes son complementarios, no redundantes: la validación de #391 cubre
el caso "cero métricas PESO en todo el rango" (rechaza con 422 antes de
construir la respuesta, solo para M06). Este ticket cubre un caso distinto
que #391 no resuelve por sí solo: si el activo **sí** tiene alguna métrica
PESO dentro del rango (pasa la validación de #391, sin 422) pero **también**
tiene una medición más reciente fuera del rango, `peso_actual` seguiría
mostrando esa medición más reciente (no la del rango) — incluyendo para M06.
La advertencia de este ticket cubre ese caso para **todos** los
consumidores, M06 incluido.

## Código

- `src/biological_assets/infrastructure/repositories/indicadores_repository.py`:
  `_obtener_metricas()` ahora recibe `fecha_inicio`/`fecha_fin` (opcionales,
  `None` por defecto) y agrega `advertencia_peso_fuera_de_rango` al dict
  resultado cuando aplica. `obtener_datos_consolidados()` le pasa el rango
  que ya recibe como parámetro.
- Sin cambios en el puerto de dominio (`_obtener_metricas` es privado) ni en
  el schema de respuesta (`metricas_actuales` ya era `dict` libre en
  `DatosConsolidadosResponse` — la clave nueva no requiere migración de
  schema).

## Fuera de alcance

- **`cantidad_actual`/`biomasa_total`** (equivalentes poblacionales de
  `peso_actual`) no tienen su propio campo de fecha en la vista
  `vw_rf47_ficha_integral_activo`, así que no se les puede aplicar la misma
  advertencia sin cambiar esa vista — fuera de alcance de este ticket, que
  se ciñe a lo que QA reportó (peso).
- **Inconsistencia menor detectada de paso**: la vista `vw_rf47_ficha_integral_activo`
  identifica "peso" con `lower(tipo_medicion) ~~ '%peso%'` (LIKE parcial),
  mientras que `_calcular_ganancia_peso` y `contar_metricas_peso_en_rango`
  (INC-M02-93-G93) usan `lower(tipo_medicion) = 'peso'` (exacto). En la
  práctica no cambia el resultado con los datos de catálogo actuales (no
  existe ningún `tipo_medicion` que contenga "peso" como substring sin ser
  exactamente "peso"), pero es una divergencia preexistente entre la vista y
  el código de aplicación que vale la pena unificar en un ticket aparte.
- No se modifica el 422 existente de INC-M02-93-G93 ni se extiende a otros
  `tipo_dato` o consumidores — ver justificación arriba.
