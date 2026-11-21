# TC-M07-G037 — Reevaluación V3 — APROBADO

## Identificación

TC-M07-G037, que agrupa TC-M07-06 a TC-M07-08: formato de la versión del contrato AAEF, período de gracia configurable en M09 y deprecación con gracia. RF-98 v1.2, apartados 5.8, RNF-98.10 y FA-10; criterio CA-7. Versión 3 (reevaluación del grupo completo). RUN RUN-G037-V3-20261120-213856, ambiente TEST, autorización AUT-G037-V3-20261120. Versión anterior: V2 oficial RUN-G037-V2-20261120-210522. Actor: Administrador QA. Commit desplegado en TEST no consultado; la rama origin/test del repositorio contiene la corrección 0553cefd. Herramientas: Node v22.15.1 y Newman (código 0); sin UI. RUN oficial, en una sola fase transaccional; 44 de 60 solicitudes.

## Motivo de la reevaluación

En la V1, el caso 07 salió RECHAZADO con severidad MEDIA (INC-M07-G037-01): el mínimo de 30 días y el valor por defecto de 90 eran constantes del código y M09 no permitía configurarlos, como exigen 5.8 y RNF-98.10. Desarrollo lo corrigió en 0553cefd (#1167) con la ruta `/configuracion/parametros-integracion-contable` de M09.

La V2 confirmó la corrección, pero volvió a rechazar el 07 por un error de QA: el oráculo del PATCH inválido exigía un código de error tomado de la implementación, que el RF-98 no fija. El oráculo se ajustó al requisito (un 400 que no cambia la gracia cumple; el código queda como observación) y, por decisión del responsable QA, la V3 repite los tres casos.

## Resumen de veredictos

| Caso | V1 | V2 | V3 | Motivo |
|---|---|---|---|---|
| TC-M07-06 | APROBADO | APROBADO | APROBADO | Los siete formatos mal formados se rechazaron sin alta y la 6.0 se registró en PENDIENTE. |
| TC-M07-07 | RECHAZADO | RECHAZADO (oráculo) | APROBADO | El registro aplica la gracia de M09, también después de cambiarla, y M09 no acepta una configuración incoherente. |
| TC-M07-08 | APROBADO | APROBADO | APROBADO | La deprecación de la 3.0 exige el mínimo configurado y fija la inactivación a +45 días exactos. |

## Preparación de los datos

El ejecutor eligió los datos en vivo antes de escribir: versiones libres desde la 6.0, el anexo APROBADO 7 y la versión ACTIVO del momento, la 3.0 (id 18). Leyó la gracia de M09: mínimo 30 y por defecto 90, ambos con fuente VALOR_BASE, es decir, sin configurar en TEST. Las altas usaron la vigencia 2027-12-25 para que el proceso automático no las activara.

Todo se hizo dentro del RUN: las altas, los dos PATCH de M09 y la deprecación. Primero se probó la gracia inicial, después el cambio de M09 y por último la deprecación, que así comprobó también el valor configurado.

## Detalle por caso

### TC-M07-06 — Formato de la versión

- **Preparación:** siete cuerpos válidos salvo `contrato_version`, con formatos distintos de MAJOR.MINOR; después, la versión libre 6.0 con el anexo 7.
- **Esperado:** según RF-98, la versión sigue el formato MAJOR.MINOR; un formato distinto se rechaza sin crear nada, y una versión válida queda en PENDIENTE.
- **Observado:** los siete intentos respondieron HTTP 400 VAL_ENTRADA en `contrato_version`, con el patrón `^\d{1,3}\.\d{1,3}$` (G037-007 a G037-013), y el listado no cambió. La 6.0 se registró con HTTP 201, id 34, estado PENDIENTE y la gracia por defecto de 90 días (G037-015).
- **Decisión: APROBADO.**

### TC-M07-07 — Período de gracia configurable en M09

- **Preparación:** lectura de la gracia efectiva en M09 (30 y 90); altas con 29 días, con 30 y sin gracia; PATCH de M09 a mínimo 45 y por defecto 120; altas con 44, con 45 y sin gracia; y un PATCH inválido con el valor por defecto en 44, menor que el mínimo.
- **Esperado:** según 5.8 y RNF-98.10, la gracia no puede ser menor que el mínimo y debe configurarse en M09; el valor por defecto se aplica cuando no se indica otro. Un cambio de M09 debe reflejarse en los registros siguientes, y una configuración inválida no debe aceptarse.
- **Observado:**
  - con la configuración base, 29 días se rechazó con HTTP 400 PERIODO_GRACIA_INVALIDO y el mensaje «El período de gracia debe ser de al menos 30 días.» (G037-018); 30 días creó la 6.1 con gracia 30 (G037-020); sin gracia, la 6.3 se creó con 90 (G037-022);
  - el PATCH respondió HTTP 200 y el GET devolvió 45 y 120 con fuente CONFIGURADO (G037-024 y G037-025);
  - con la nueva configuración, 44 días se rechazó con «al menos 45 días» (G037-027); 45 creó la 6.4 con gracia 45 (G037-029); sin gracia, la 6.6 se creó con 120 (G037-031);
  - el PATCH inválido respondió HTTP 400 con «El período de gracia por defecto no puede ser menor que el mínimo.», y el GET siguiente mostró 45 y 120 sin cambios (G037-033 y G037-034).
- **Decisión: APROBADO.** La corrección 0553cefd resuelve INC-M07-G037-01: el mínimo y el valor por defecto salen de M09 y no del código.

### TC-M07-08 — Deprecación con período de gracia

- **Preparación:** con la gracia de M09 en 45 y 120, deprecar la 3.0 (ACTIVO) con 44 días y después con 45.
- **Esperado:** según 5.8 y CA-7, la deprecación con menos del mínimo se rechaza y la versión sigue ACTIVO; con el mínimo pasa a DEPRECADO y la inactivación queda al final del plazo.
- **Observado:** con 44 días, HTTP 400 PERIODO_GRACIA_INVALIDO en `dias_gracia` con «al menos 45 días» (G037-036), y la 3.0 siguió ACTIVO. Con 45 días, HTTP 200: la 3.0 pasó a DEPRECADO con deprecación el 2026-11-20 a las 21:39:05 UTC e inactivación el 2027-01-04 a la misma hora, exactamente 45 días después (G037-038). La auditoría registró el evento de deprecación de la 3.0 (G037-040).
- **Decisión: APROBADO.**

## Comprobaciones API

- TC-M07-06 / formato_1 a formato_7: APROBADO; 400 VAL_ENTRADA sin alta; resultado.json.
- TC-M07-06 / registro_valido: APROBADO; 201 PENDIENTE; resultado.json.
- TC-M07-07 / gracia_inicial_baja, gracia_inicial_minima, gracia_inicial_defecto: APROBADO; resultado.json.
- TC-M07-07 / m09_configurable, gracia_configurada_baja, gracia_configurada_minima, gracia_configurada_defecto: APROBADO; resultado.json.
- TC-M07-07 / patch_invalido: APROBADO; 400 y gracia sin cambios; resultado.json.
- TC-M07-08 / deprecar_baja, deprecar_minima, inactivacion_exacta: APROBADO; resultado.json.

## Evidencias reales

resultado.json (con los resúmenes de los eventos de auditoría comparados: cinco registros, de la 6.0 a la 6.6, y la deprecación de la 3.0), preflight.json, contexto_operacion.json, newman/newman-G037.json y newman/newman-G037.html. Ningún archivo contiene correos, contraseñas, tokens ni el secreto del sandbox; los nombres de los parámetros de M09 aparecen saneados como «[NOMBRE]».

## Incidencias de producto

Ninguna. Las comprobaciones de la V3 muestran corregida en TEST INC-M07-G037-01 (V1); Desarrollo informó la corrección en 0553cefd.

## Observaciones

- **Código de error del PATCH inválido de M09 (para Desarrollo, sin incidencia).** El rechazo de un valor por defecto menor que el mínimo responde `PARAMETRO_MLOPS_INVALIDO` con `field` nulo, en lugar del código propio de la ruta, `PARAMETRO_INTEGRACION_CONTABLE_INVALIDO`, que sí usa para los nombres ajenos. Hipótesis por el código del repositorio: la validación cruzada del mínimo y el valor por defecto está en el caso de uso genérico de parámetros de M09 (`configurar_parametros_mlops_use_case.py`, líneas 99-114), que convierte cualquier error en su propio código. El RF-98 no fija este código, por lo que no afecta al veredicto; se sugiere unificarlo y señalar el campo.
- La configuración de la gracia en TEST sigue en sus valores base (30 y 90): el PATCH de la prueba solo existió dentro del RUN.

## Cierre y rollback

`DELETE /test-control/runs/RUN-G037-V3-20261120-213856` respondió HTTP 200. El ejecutor comparó las lecturas posteriores, sin las cabeceras del RUN, con la base y coincidieron: las versiones 6.0 a 6.6 ya no existen, la 3.0 sigue ACTIVO y la gracia de M09 sigue en 30 y 90 con fuente VALOR_BASE. Rollback verificado. El único efecto persistente es el inicio de sesión del Administrador QA antes del RUN.

## Conclusión y acciones

El formato de versión, el período de gracia y la deprecación cumplen RF-98, y la gracia ya se configura desde M09 como exigen 5.8 y RNF-98.10. Grupo APROBADO en la V3; INC-M07-G037-01 queda corregida en TEST, y su cierre administrativo corresponde al responsable QA. Se comunica a Desarrollo, como observación, el código genérico del PATCH inválido de M09.

## Historial del informe

Informe redactado por el orquestador QA (2026-11-20) a partir de resultado.json y newman/. Veredictos y evidencias sin cambios.
Corrección (2026-11-20): precisados la incidencia automática de resultado.json (V2) y el alcance de la corrección de INC-M07-G037-01 (V3); veredictos y evidencias sin cambios.
