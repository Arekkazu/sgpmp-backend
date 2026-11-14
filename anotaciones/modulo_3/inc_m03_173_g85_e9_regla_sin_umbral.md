# INC-M03-173-G85 — RF-57 E9: evento de una variable sin umbrales configurados (TC-M03-G85)

**RF:** RF-57 E9, "Regla de negocio mal configurada o ausente": "No existen umbrales configurados para el
tipo_variable recibido" → no se genera alerta operativa, se registra `ERROR_CONFIGURACION_REGLA` en la
bitácora, se genera una alerta técnica al administrador y el evento queda en `PENDIENTE_EVALUACION`.
**Issue:** #752.
**Estado:** implementado y verificado con PostgreSQL real. El defecto se **reproduce** en `dev`. La
**reevaluación automática** del evento pendiente queda fuera de alcance, por decisión del equipo.

## Causa

`GenararAlertaUseCase` no consultaba umbrales: el tipo salía de una tabla fija por `tipo_variable`, así
que un evento sin regla se trataba como uno normal. Eso pasó con las alertas 375 (NH3) y 376 (TDS). No
existían ni `ERROR_CONFIGURACION_REGLA` ni `PENDIENTE_EVALUACION`.

## Qué cuenta como "umbral configurado"

Un **umbral activo de RF-17** (`modulo9.umbrales_ambientales`) de la variable, para **alguna especie del
área** (`modulo9.infraestructuras_especies`, RFC-012). Si no hay área identificada, basta un umbral de la
variable para cualquier especie. Es el criterio de QA ("amoniaco sin umbral en la especie").

| Motivo (`e9.motivo`) | Situación |
|---|---|
| `SIN_UMBRAL_PARA_LAS_ESPECIES` | Ninguna especie del área tiene umbral activo para la variable |
| `AREA_SIN_ESPECIES` | El área no tiene especies asociadas, así que no hay regla que aplicar |
| `VARIABLE_FUERA_DEL_CATALOGO` | La variable no está en el catálogo de M09 |

## Comportamiento (`POST /iot/alertas`, `origen_evento` distinto de IA)

- **Sin alerta operativa.** No aparece en `GET /iot/alertas` (productor y veterinario).
- **Bitácora RF-63:** `ERROR_CONFIGURACION_REGLA` (ADVERTENCIA), con el diagnóstico y el **evento completo**
  (`estado_evaluacion = PENDIENTE_EVALUACION`). Se registra una entrada por cada evento, así que **ninguno
  se pierde**.
- **Alerta técnica para el Administrador:** `tipo_alerta = TECNICA` y `tipo_variable =
  ERROR_CONFIGURACION_REGLA`, severidad MODERADO, visible en `GET /iot/alertas-tecnicas`. En
  `metadato_evento` guarda el diagnóstico (`e9`) y el evento (`evento_pendiente`).
  - **Consolidación:** hay una técnica abierta por sensor (ventana de 24 h); los eventos siguientes suman
    `frecuencia_evento`.
- **Respuesta:** 201 con `tipo_alerta: TECNICA` y `motivo_descarte`, que explica el E9 y el
  `PENDIENTE_EVALUACION`.

**Fuera del alcance de E9:** las predicciones de IA (PREDICCION_PATOLOGIA no depende de umbrales
ambientales) y los flujos internos que ya traen su umbral (RF-17 → RF-57 de DEV-41) o que evalúa el Edge
(RF-56): el puerto solo lo inyecta `POST /iot/alertas`.

**`PENDIENTE_EVALUACION` sin migración:** no existe en ningún enum de la BD. El estado del evento vive en el
evento conservado, tanto en la técnica como en la bitácora.

## Relación con G68 (#740)

G68, todavía sin mergear, evalúa la severidad con las bandas base de RF-57. **E9 se evalúa antes:** si el
área no tiene umbral de RF-17 para la variable, el evento no genera alerta operativa aunque exista una
banda base. Al unir ambas ramas, el orden queda así: FALLO_AMBIENTAL (G68) → E9 (este PR) → bandas y
severidad (G68). El conflicto esperado está en `generar_alerta_use_case.py` (constructor e imports).

## Pendiente (fuera de alcance, por decisión del equipo)

**Reevaluación automática:** cuando el administrador configure el umbral, reprocesar los eventos
`PENDIENTE_EVALUACION`. Esos eventos ya están conservados (en la técnica y en la bitácora) para
reprocesarlos en una tarea aparte. Por ahora, el administrador resuelve la técnica al corregir la
configuración.

## Cambios

- `src/telemetry/domain/repositories/umbral_configurado_port.py` (nuevo).
- `src/telemetry/infrastructure/adapters/umbral_configurado_m09_adapter.py` (nuevo).
- `generar_alerta_use_case.py`: la comprobación de E9 (`umbral_port`, opcional) y
  `_error_configuracion_regla`.
- `alerta_router.py`: inyecta `UmbralConfiguradoM09Adapter`.
- `tests/integration/test_dev49_alertas_historial_auditoria.py`: el caso que crea una alerta operativa por
  HTTP ahora siembra su umbral de RF-17. Sin él, el evento cae en E9, que es lo correcto.

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_173_g85_e9_regla_sin_umbral.py`, sin BD:
- **Sin umbral:** crea la técnica con el evento pendiente.
- **Con umbral:** sigue el flujo normal.
- **Técnica abierta:** se consolida.
- **Predicción de IA:** no consulta umbrales.

**Pruebas de integración.** `tests/integration/test_inc_m03_173_g85_e9_regla_sin_umbral.py`:

| Caso de QA | Prueba | Rama | `dev` |
|---|---|---|---|
| BUG-G85-01: NH3 25 ppm sin umbral | `test_g85_01_sin_umbral_no_hay_alerta_operativa_y_el_evento_queda_pendiente` | Técnica con `evento_pendiente` PENDIENTE_EVALUACION; nada en `/iot/alertas` | Falla (alerta operativa) |
| BUG-G85-02 | `test_g85_02_queda_error_configuracion_regla_en_la_bitacora` | 1 entrada con el evento | Falla (0) |
| BUG-G85-03 | `test_g85_03_el_administrador_ve_la_alerta_tecnica` | Aparece en `/iot/alertas-tecnicas` | Falla |
| Sin pérdida | `test_eventos_siguientes_del_sensor_se_consolidan_y_no_se_pierden` | `frecuencia_evento = 2`; los 2 eventos en la bitácora | Falla |
| Área sin especies | `test_area_sin_especies_tambien_es_e9` | `AREA_SIN_ESPECIES` | Falla |
| Control | `test_con_umbral_configurado_la_alerta_es_operativa` | SINDROME_RESPIRATORIO operativa, sin E9 | Pasa |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g85_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Integración (G85 + DEV-04, DEV-30, DEV-43, DEV-49, DEV-41, DEV-17)       100 passed, 6 skipped
Misma prueba de G85 sobre dev                                            5 failed, 1 passed  ← reproduce el defecto
Unitarias G85                                                            4 passed
Suite completa (sin red): 2268 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Para QA y despliegue

- **TC-M03-G85:** reejecutar. Un área necesita **especies asociadas y umbrales de RF-17** para las variables
  que sus sensores reportan; sin ellos, los eventos externos caen en E9.
- **Despliegue:** antes de desplegar, conviene revisar en TEST y PROD qué áreas con sensores activos no tienen
  umbrales para sus variables. Esas áreas empezarán a generar alertas técnicas `ERROR_CONFIGURACION_REGLA` en
  lugar de operativas.
