# Plan de prueba multiespecie - E2 Cerdo

Estado: borrador del 2026-10-27. Clasificacion sujeta a confirmacion donde diga *por confirmar*.

## 1. Ficha

| Campo | Valor |
|---|---|
| Especie | Cerdo |
| Grupo de manejo | PORCINOS |
| Paradigma | **POBLACIONAL** |
| Confianza de la clasificacion | Alta |
| Especies compañeras | Ninguna otra de la lista pertenece a PORCINOS: el flujo multiespecie se prueba con una segunda especie porcina de apoyo (p. ej. `Marranos`, id 113) o solo como negativo cruzado |

## 2. Estado en TEST (consultado 2026-10-27)

Existe `Marranos` (113, PORCINOS, densidad 10) y cientos de `Porcinos ...` de pruebas automaticas (no usar). Crear `Cerdo` nuevo en sandbox.

## 3. Paradigma y consecuencias para la prueba

Se gestiona por lote (activo LOTE) con conteo; admite `tipo_agregacion`. Modelo poblacional versionado por componente.

Densidad en ind/m2; con superficie fija validar `floor(MIN densidad x superficie)`.

## 4. Precondiciones y datos semilla

- Sandbox transaccional activo (`X-Test-Run-Id` + `X-Sandbox-Secret`, rollback final con `DELETE /test-control/runs/{id}`); el secreto sale de variable de entorno, nunca del plan.
- Crear la especie **Cerdo** (RF-15) con `grupo_manejo` y `densidad_poblacional_max`.
- Etapas y patologias de la especie (RF-16) y umbrales (RF-17).
- Finca y area productiva con superficie conocida (RF-19, RF-20).
- Dispositivos y sensores asociados al area (RF-21, RF-22).
- Credencial de Administrador; para Productor, variables `QA_PROD_*` en `.env.test`.

## 5. Flujo extremo a extremo

| Fase | Modulo | Accion | Resultado esperado | TC |
|---|---|---|---|---|
| F1 | M09 RF-15 | Registrar Cerdo con grupo y densidad | 201; `tipo_modelo` derivado del grupo | por asignar |
| F2 | M09 RF-16/17 | Etapas, patologias y umbrales | 201/200 | por asignar |
| F3 | M09 RF-20 | Area con Cerdo sola | 201; capacidad = floor(densidad x superficie) | por asignar |
| F4 | M09 RF-20 | Area multiespecie (con una especie porcina de apoyo, p. ej. Marranos) | 201; capacidad con la MENOR densidad | por asignar |
| F5 | M09 RF-21/22 | Dispositivo y sensor asociados al area | 201 | por asignar |
| F6 | M02 | Registrar activo LOTE con conteo | 201; respeta la capacidad | por asignar |
| F7 | M03 RF-53 | Ingesta de lecturas del sensor (requiere sensor asociado y token del broker) | 202/201 | por asignar |
| F8 | M03 RF-57/58/59 | Alerta por umbral, estado y historial correlacionado | alerta visible con sus 6 campos | por asignar |
| F9 | M09 RF-24 | Calibracion de vision | una linea base por cada par (area, especie) | por asignar |
| F10 | M04 | Prediccion con el modelo del grupo | resultado coherente con el paradigma | por asignar |
| F11 | Cierre | Rollback del sandbox | BD sin cambios | por asignar |

## 6. Casos especificos de esta especie

- Lote que supera la capacidad del area -> 422 CAPACIDAD_EXCEDIDA.
- Evento de crecimiento con `tipo_agregacion` valido para lote.
- Ficha del lote (`/activos-biologicos/{id}/ficha-lote`).
- Prediccion con `MODELO_PORCINOS` y sus 4 componentes.

## 7. Casos negativos comunes

- Grupos distintos en la misma area -> 422 `GRUPOS_MANEJO_INCOMPATIBLES`.
- Carga mayor que la capacidad -> 422 `CAPACIDAD_EXCEDIDA`.
- Reducir superficie por debajo de la carga -> 422 `CAPACIDAD_EXCEDIDA`.
- Retirar especie con activos alojados -> 422 `ESPECIE_CON_ACTIVOS_ALOJADOS`.
- Especie sin densidad con activos alojados -> 422 `ESPECIE_SIN_DENSIDAD`.
- Lista de especies vacia o repetida (la repetida se depura conservando el orden).

## 8. Criterios de aceptacion

- Todas las fases F1-F11 aprobadas, o con incidencia registrada en Taiga.
- Ningun dato queda en TEST tras el rollback.
- El paradigma observado en la API coincide con **POBLACIONAL**.

## 9. Riesgos y notas

- Las lecturas con hora actual fallan dentro del sandbox (`now()` congelado) y los eventos de auditoria (RF-63) no se emiten en sandbox: esas verificaciones van aparte.
- La ingesta devuelve 401 enganoso si el sensor no estaba asociado al momento de la captura.
- Alertas DESCARTADAS antiguas de TEST apuntan a lecturas que el historial no devuelve (ver G117): no usarlas como semilla.
