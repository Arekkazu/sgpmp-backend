# TC-M05-G15 — Resultado de ejecución (run-20261107-125738)

| Campo | Valor |
|---|---|
| Caso | TC-M05-G15 — Precondiciones del activo: estado, ciclo productivo y cantidad poblacional |
| Requerimiento | RF-76 (Registro de aplicación de medicamentos) |
| Caso de uso | CU03 (Gestión de Suministros) |
| Endpoint | `POST /suministros/medicamentos` |
| Ambiente | TEST (`TEST_BASE_URL` de `.env.test`) |
| Fecha | 2026-11-07 (corrida `run-20261107-125738`) |
| Evaluador | Juan Sebastian Gutierrez |
| Activos evaluados | 2 (INACTIVO), 12 (CERRADO), 10 (BAJA), 812 (AISLADO), 853 (ACTIVO sin ciclo), 462 (POBLACIONAL cantidad NULL), 999999999 (inexistente) |
| Herramienta | pytest + sandbox transaccional (`X-Test-Run-Id` / `X-Sandbox-Secret`, rollback por corrida) |
| Script / runner | `test_tc_m05_g15.py` (SHA-256 `8f4040b7c431305dcad8b46f59dbf7dcedb4bbc73fdfa6ed24fb2788992bf480`), `ejecutar_tc_m05_g15.ps1` |
| Reportes computables | `run-20261107-125738/resultado_TC-M05-G15.html` y `run-20261107-125738/resultado_TC-M05-G15.json` |
| Contexto | Ejecución oficial automatizada en sandbox transaccional. |

## Resultado

**10 tests: 10 passed / 0 failed / 0 error / 0 skipped.**
Todos los tests se ejecutaron en el orden de diseño estricto: Línea base (T00) → Precondiciones de estado e inexistencia (A01–A06) → Precondición poblacional (B01) → Cierre de sandbox (T98) → Inocuidad final sin sandbox (T99).

| Id | Paso | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| T00  | T00 Línea base de activos | HTTP 200 e inventario base registrado (medicamentos, estado, fases) para activos 2, 12, 10, 812, 853, 462 | Línea base capturada para 6 activos (HTTP 200 en todas las consultas) | **OK** |
| A01  | A01 INACTIVO (Activo 2) | HTTP 422, mensaje contiene 'INACTIVO', medicamento y estado sin cambios | HTTP 422 (ACTIVO_ESTADO_INVALIDO), mensaje validado, sin persistencia | **OK** |
| A02  | A02 CERRADO (Activo 12) | HTTP 422, mensaje contiene 'CERRADO', medicamento y estado sin cambios | HTTP 422 (ACTIVO_ESTADO_INVALIDO), mensaje validado, sin persistencia | **OK** |
| A03  | A03 BAJA (Activo 10) | HTTP 422, mensaje contiene 'BAJA', medicamento y estado sin cambios | HTTP 422 (ACTIVO_ESTADO_INVALIDO), mensaje validado, sin persistencia | **OK** |
| A04  | A04 AISLADO (Activo 812) | HTTP 422, mensaje contiene 'AISLADO', medicamento y estado sin cambios | HTTP 422 (ACTIVO_ESTADO_INVALIDO), mensaje validado, sin persistencia | **OK** |
| A05  | A05 SIN CICLO (Activo 853) | HTTP 422, mensaje contiene 'ciclo', medicamento y estado sin cambios | HTTP 422 (CICLO_NO_ABIERTO), mensaje validado, sin persistencia | **OK** |
| A06  | A06 ID INEXISTENTE (999999999) | HTTP 404, mensaje contiene 'no existe', sin persistencia | HTTP 404 (ACTIVO_NO_ENCONTRADO), mensaje validado, sin persistencia | **OK** |
| B01  | B01 POBLACIONAL cantidad NULL (Activo 462) | Fase abierta (201), HTTP 422 (o 400), mensaje contiene 'cantidad', medicamento y estado sin cambios | Fase HTTP 201, POST medicamento HTTP 422 (error_code: POBLACIONAL_SIN_CANTIDAD), sin persistencia | **OK** |
| T98  | T98 Cierre de corrida | DELETE /test-control/runs/<run_id> HTTP 200 Rollback exitoso | DELETE HTTP 200: {"status": "Rollback exitoso"} | **OK** |
| T99  | T99 Inocuidad final sin sandbox | Conteos de medicamentos, estados y fases coinciden 100% con T00 fuera de sandbox | Conteos, estados y fases verificados 100% idénticos fuera de sandbox | **OK** |

## Veredicto

**APROBADO**

El sistema implementa rigurosamente el orden de precondiciones de negocio y rechaza todas las solicitudes no conformes con los códigos HTTP y mensajes esperados, garantizando no persistencia y no alteración de estado del activo.

## Defectos

- **Defectos de producto:** Ninguno.
- **Incidentes (INC):** Ninguno.

## Cobertura no alcanzable en el ambiente

- **POBLACIONAL ACTIVO con ciclo abierto y cantidad_actual = 0:**
  En la Fase 1 se demostró empíricamente a través de 10 intentos por API real (registrados en `trazas_c5_sondeo.jsonl`) que en la lógica de dominio de M02 cualquier evento de baja que reduzca la cantidad del lote a cero (`cantidad_actual = 0`) transiciona forzosamente el activo a estado `BAJA` (id_estado = 6) y cierra de inmediato la gestión de fase activa. Posteriormente, RF-44 prohíbe reactivar activos en BAJA (`ESTADO_BAJA_IRREVERSIBLE` 409) y el trigger de fases prohíbe aperturas (`ACTIVO_NO_OPERATIVO` 409). Por ende, el caso límite de cantidad igual a cero dentro de un ciclo abierto no es alcanzable por API. La precondición FA-08 de rechazo poblacional se valida limpiamente sobre lotes con cantidad NULL (Activo 462).

## Observaciones para Análisis (no son defectos)

1. **Estado AISLADO:** Se confirmó que el endpoint rechaza con HTTP 422 `ACTIVO_ESTADO_INVALIDO` sobre activos en estado AISLADO (Activo 812), conforme a la restricción E1 (que solo habilita ACTIVO y EN_TRATAMIENTO).
2. **Mensaje de Activo 462:** El backend responde *"El activo poblacional 462 no tiene registrada una cantidad actual válida en su detalle poblacional. Corrija el inventario del lote antes de registrar medicamentos."*, cumpliendo el requerimiento de negocio de indicar la necesidad de corregir el inventario.
3. **Activo 9 (observación de ambiente):** El Activo 9 presenta desincronización de datos entre `activos_biologicos.id_estado` (1) y `historial_estados_activos_biologicos` (CERRADO). No fue empleado en esta corrida para garantizar estabilidad determinista.

## Inocuidad

| Activo | Tipo | Medicamentos T00 | Medicamentos T99 | Estado T00 | Estado T99 | Fases Activas T00 | Fases Activas T99 |
|---|---|---|---|---|---|---|---|
| 2 | INDIVIDUAL | 0 | 0 | 2 (INACTIVO) | 2 (INACTIVO) | 0 | 0 |
| 12 | INDIVIDUAL | 0 | 0 | 3 (CERRADO) | 3 (CERRADO) | 0 | 0 |
| 10 | INDIVIDUAL | 0 | 0 | 6 (BAJA) | 6 (BAJA) | 0 | 0 |
| 812 | INDIVIDUAL | 0 | 0 | 4 (AISLADO) | 4 (AISLADO) | 0 | 0 |
| 853 | INDIVIDUAL | 0 | 0 | 1 (ACTIVO) | 1 (ACTIVO) | 0 | 0 |
| 462 | POBLACIONAL | 0 | 0 | 1 (ACTIVO) | 1 (ACTIVO) | 0 | 0 |

Se abrió fase dentro del sandbox sobre el Activo 462 y se enviaron 7 peticiones POST de medicamentos. Al cerrar la corrida con DELETE, el rollback revirtió la fase y todas las operaciones: **cero contaminación en base de datos.**

Teardown: Run `tc-m05-g15-94bbe511-8b3f-435c-abad-ee6446e040b0` cerrado con HTTP `200` (`{"status": "Rollback exitoso"}`).
