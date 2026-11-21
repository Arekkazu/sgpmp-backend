# TC-M06-G44 — resultado oficial V1 (enmienda documental)

## 1. Identificación

| Campo | Dato |
| --- | --- |
| Proyecto y requisito | SGPMP; M06; RF-87, actualización v1.1; G44 |
| Casos | TC-M06-028, TC-M06-029, TC-M06-030 |
| Versión, ambiente, RUN | V1; TEST; `RUN-G44-V1-20261110-055212` |
| Autorización | `AUT-G44-V1-R2-20261110` |
| Commit | No consultado (Git prohibido en esta orden) |
| Herramientas registradas | Node v22.15.1; Newman código 0; Cypress no aplica (0 pruebas) |

Los oráculos proceden de la matriz original `Casos_Prueba(Modulo6Agrup).csv`, RF-87 v1.1 (incluida la actualización sobre lista de faltantes), RF-86 CA-21 y CU06, según la preparación de G44. Esta enmienda describe el RUN existente; no ejecutó TEST. Las lecturas de código local citadas se limitan a `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:304-320`, `src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py:100` y `src/financial_valuation/infrastructure/routers/m06_router.py:115-117`, conforme a la orden de reevaluación. El código local no sustituye los oráculos ni prueba el comportamiento desplegado.

## 2. Resumen ejecutivo

| Caso | Veredicto histórico en resultado.json | Alcance acreditado |
| --- | --- | --- |
| TC-M06-028 | RECHAZADO (`028_b, 028_c`) | 028-a APROBADO; 028-b RECHAZADO; **028-c NO EVALUADO** por error QA de diseño. El motivo histórico de `resultado.json` no se cambia. |
| TC-M06-029 | RECHAZADO (`029_mensaje`) | Acceso y consulta APROBADOS; mensaje RECHAZADO. |
| TC-M06-030 | RECHAZADO (`030_cerrado, 030_concurrencia`) | Dos mensajes RECHAZADOS; ausencia de segundo cierre APROBADA. |

El RUN V1 es OFICIAL según [resultado.json](resultado.json). La enmienda retira `INC-M06-G44-06` por falta de sustento y remite 028-c a V2, decidida expresamente por el responsable QA el 2026-11-10. No modifica veredictos históricos ni `resultado.json`.

## 3. Casos, criterios y comprobaciones

### TC-M06-028 — faltantes para el cierre

**Esperado (RF-87 v1.1):** ante línea sin cuenta, matriz incompleta o finca sin titular, bloquear el cierre con lista de faltantes que nombre la causa y conservar el período ABIERTO. Se usaron DELETE de asignaciones 34 y 49, un costo MANO_OBRA_PROPIA y PUT del titular de finca 466. Solo API; UI no exigida.

| Criterio | Esperado | Observado en V1 | Conclusión |
| --- | --- | --- | --- |
| 028-a | `PENDIENTE_CUENTA`, lista de faltantes y período 220 ABIERTO | POST cierre 220: HTTP 422 `CIERRE_BLOQUEADO`; mensaje sobre una línea de mano de obra propia sin cuentas; prevalidación `LINEAS_PENDIENTE_CUENTA`; 220 ABIERTO. | APROBADO, como `resultado.json`. |
| 028-b | Bloqueo con lista por matriz incompleta; 219 ABIERTO | DELETE `/finanzas/configuracion/matriz/49` → 204; POST `/finanzas/periodos/219/cierre` → 200 y 219 CERRADO. **El cuerpo del 200 no se conservó**. | RECHAZADO; `INC-M06-G44-05`. La causa concreta queda por confirmar en V2. |
| 028-c | Bloqueo con lista por finca sin titular; 219 ABIERTO | Tras el cierre de 028-b, POST cierre 219 → 409 `PERIODO_CERRADO`. No se observó el control de titular ausente. | **NO EVALUADO por error QA de diseño**; el `RECHAZADO` histórico de esta comprobación en `resultado.json` no es evidencia de defecto de producto. |

La generación de una línea `DEPRECIACION_ACTIVO_COSTO` del equino 1567 es **INFERENCIA** del código local `ejecutar_cierre_periodo_use_case.py:304-320` y del comprobante `DEPRECIACION-423` del período 219 en `RUN-G42-V1-20261109-212424`; no se verificó en el cuerpo del 200 de V1. Que una línea sin cuenta no bloquee, o que la asignación desactivada siga aplicándose, son **HIPÓTESIS**, no causas raíz demostradas. [Resultado V1](resultado.json).

### TC-M06-029 — acceso y explicación FA-4

**Esperado:** Administrador, Veterinario y Productor reciben 403 al intentar cerrar, sin alterar 219; cada mensaje explica FA-4 y nombra el rol. Administrador puede consultar período y prevalidación con 200. Solo API.

| Criterio | Observado | Conclusión |
| --- | --- | --- |
| `029_acceso` | Tres HTTP 403 y 219 sin cambios. | APROBADO. |
| `029_mensaje` | Los tres 403 dicen «Acceso denegado. Su rol no tiene permisos para realizar esta operación.»; no citan FA-4 ni el rol. | RECHAZADO; `INC-M06-G44-01`. |
| `029_admin` | GET período y prevalidación: 200/200. | APROBADO. |

**Veredicto: RECHAZADO**, conforme a [resultado.json](resultado.json).

### TC-M06-030 — período cerrado y concurrencia

**Esperado:** sobre 7 CERRADO, 409 «Periodo inmutable» con fecha y Contador ejecutor; segundo POST concurrente sobre 8 EN_CIERRE, 409 con hora y usuario del primero; sin segundo cierre y sin nuevos artefactos. Solo API.

| Criterio | Observado | Conclusión |
| --- | --- | --- |
| `030_cerrado` | POST cierre 7 → 409 `PERIODO_CERRADO`, sin «Periodo inmutable» ni ejecutor; 7 sin cambios. | RECHAZADO; `INC-M06-G44-02`. |
| `030_concurrencia` | Primero y segundo POST sobre 8 → 409 `EXCLUSION_REQUIERE_AUTORIZACION`, sin conflicto de concurrencia; relacionado con `INC-M06-G43-01`. | RECHAZADO; `INC-M06-G44-03`. |
| `030_sin_segundo` | 8 ABIERTO, sin comprobantes nuevos y líneas conservadas. | APROBADO. |

**Veredicto: RECHAZADO**, conforme a [resultado.json](resultado.json).

## 4. Incidencias de producto

| ID | Esperado / obtenido y evidencia | Impacto, severidad y certeza | Equipo inicial y fundamento | Causa y acción |
| --- | --- | --- | --- | --- |
| INC-M06-G44-01 | FA-4 y rol en cada 403 / mensaje genérico en los tres. [Resultado](resultado.json). | Explicación de acceso incompleta; **MEDIA, CONFIRMADA** por API. | **Desarrollo**: primera discrepancia en respuesta pública de cierre. | Causa raíz no determinada; corregir mensaje y repetir 029 en V2. |
| INC-M06-G44-02 | 409 «Periodo inmutable» con fecha y ejecutor / `PERIODO_CERRADO` sin esos datos. [Resultado](resultado.json). | Auditoría visible incompleta; **MEDIA, CONFIRMADA**. | **Desarrollo**: primera discrepancia en respuesta pública de cierre. | Causa raíz no determinada; corregir respuesta y repetir 030. |
| INC-M06-G44-03 | Segundo 409 de concurrencia con hora y usuario / 409 `EXCLUSION_REQUIERE_AUTORIZACION`. [Resultado](resultado.json). | Concurrencia no informada; **MEDIA, CONFIRMADA** para la respuesta observada. | **Desarrollo**: primera discrepancia en API de cierre; relacionada con `INC-M06-G43-01`. | Causa raíz no determinada; revisar transición EN_CIERRE y repetir 030. |
| INC-M06-G44-05 | Bloqueo con lista por matriz incompleta / DELETE 49 → 204 y cierre 219 → 200 CERRADO. [Resultado](resultado.json). | Control relevante permitió completar el cierre sin informar el faltante; **ALTA, CONFIRMADA** para el 200 y CERRADO. | **Desarrollo**: primera discrepancia en API de cierre. | El mecanismo exacto es **HIPÓTESIS**; conservar cuerpo completo del cierre y líneas/comprobantes en V2. |

`INC-M06-G44-06` se **RETIRA** en esta enmienda: 028-c no fue evaluado. La retirada no altera el registro histórico ni otros artefactos del RUN.

## 5. Análisis de fallos y problemas técnicos

El diseño V1 hizo depender 028-c del mismo período 219 que 028-b. Como 028-b cerró 219, el 409 posterior solo demuestra que no puede recerrarse; no prueba el requisito de finca sin titular. Es un **error QA de diseño**. El ejecutor tampoco conservó el cuerpo de la respuesta 200 de 028-b, por lo que no permite inspeccionar activos, líneas excluidas ni comprobantes de ese cierre. La V2 separa escenarios y captura esos cuerpos.

`RUN-G44-V1-20261110-054638` fue un intento técnico: preflight sin `QA_VETERINARIO_PASSWORD`; no realizó peticiones a TEST. No es evidencia funcional ni V2.

## 6. Herramientas, evidencias y rollback

Evidencias reales del RUN: [resultado.json](resultado.json), [preflight.json](preflight.json), [contexto_operacion.json](contexto_operacion.json), [Newman JSON](newman/newman-G44.json) y [Newman HTML](newman/newman-G44.html). Newman figura con código 0; ello no confirma funcionalidad por sí solo. Cypress no aplica a estos tres casos API. El ejecutor V1 quedó identificado por SHA-256 `e52c0e6f23397f0d728e949c139b2239bc3c1fbba7b833a6478491bdecbd417c`.

[Resultado](resultado.json) registra DELETE del RUN HTTP 200 y rollback `verificado=true`: lecturas posteriores sin cabeceras comprobaron matriz, costo ausente, titular, períodos, líneas y artefactos frente a la base. Esta enmienda no repite esas comprobaciones ni afirma más alcance del registrado.

## 7. Conclusión y acción

Se mantienen los tres veredictos oficiales V1. Desarrollo recibe las cuatro incidencias sustentadas; QA debe reevaluar los tres casos en V2 con autorización específica de ejecución, períodos separados y cuerpos completos de cada POST de cierre. 028-c queda pendiente de comprobación de producto.

## 8. Actualización

Enmienda documental `ORD-G44-005`, 2026-11-10, conforme a ESTÁNDAR §8. Copia byte a byte anterior: [historial_informes/TC-M06-G44_resultado.RUN-G44-V1-20261110-055212.antes-enmienda.md](../../historial_informes/TC-M06-G44_resultado.RUN-G44-V1-20261110-055212.antes-enmienda.md), SHA-256 `ab159186fd4e2bf08c59250a2461c59ddbd0cdd734d5166173f957b15f72561e`. `resultado.json` permanece sin cambios, SHA-256 `d1883c8b7dd5ff324481269b53eb9a7575fdba2acbe99aa8c63acfed09bca5b7`. Se corrigió la interpretación de 028-c y se retiró `INC-M06-G44-06`; no se cambiaron veredictos, resultado.json, evidencias, registro ni rollback.

