# TC-M06-G44 / RF-87 / ORD-G44-012

Preparación local de la reevaluación V3 de TC-M06-028, 029 y 030. Los oráculos provienen de la fila TC-M06-G44 de `Casos_Prueba(Modulo6Agrup).csv`, RF-87 FA-4/FA-5 y la decisión D1 del responsable QA del 2026-11-13. Los mensajes se juzgan por el contenido exigido; una redacción diferente se registra como OBS-G44-01.

## Archivos vigentes

`g44.mjs` es el ejecutor canónico, `G44.postman_collection.json` la única colección Newman y `lib/informe.mjs` la plantilla del único informe oficial. `lib/g44_core.mjs`, `lib/infra.mjs` y `lib/contrato.mjs` contienen los criterios, las lecturas y el contrato. `pruebas/g44_escenarios.test.mjs` simula respuestas locales; `pruebas/verificar.mjs` es la validación local. Los casos de G44 solo requieren API. V1 y V2 son evidencia histórica de solo lectura.

## Secuencia V3 para un RUN autorizado externamente

1. Preflight sin escrituras: cuatro roles, permisos, períodos 7/8/219/220/260, prevalidaciones 220/260, siete líneas de 467 en 220, ausencia de líneas en 260, titulares completos 466/467, asignaciones 34/49 y activos al costo 1567/1573. El 8 se admite ABIERTO o EN_CIERRE con ejecución 67 EN_PROCESO en paso 3. Un requisito incumplido deja NO_CONCLUYENTE con detalle y sin escrituras de producto.
2. 029: Administrador, Veterinario y Productor intentan cerrar 220; se compara HTTP 403, rol, exclusividad del Contador y ausencia de cambios. El Administrador consulta períodos y prevalidación.
3. 030: POST de 7 CERRADO y observación de 219. Si 8 está en cierre, se cancela 67 dentro del RUN. Se exige línea 17, se hace primer POST sin autorización, se identifica la nueva ejecución X, se hace segundo POST y se comprueban HTTP 409, hora, ejecutor, mismo X y ausencia de artefactos nuevos. Se cancela X y se comprueba ABIERTO con líneas, comprobantes y variaciones originales.
4. 028_a: se elimina 34, se crea costo MANO_OBRA_PROPIA del día sobre 1569 si está en 467 o sobre otro activo de esa finca elegido en preflight, se exige LINEAS_PENDIENTE_CUENTA, lista de faltantes y 220 ABIERTO sin artefactos nuevos; se restaura 34 y se comprueba prevalidación limpia.
5. 028_b: en 260, se elimina 49, se exige MATRIZ_CONTABLE_INCOMPLETA por depreciación del activo al costo 1567, lista de faltantes y 260 ABIERTO sin artefactos nuevos; se restaura 49 y se comprueban 220/260 sin bloqueos.
6. 028_c: en 220, se anula temporalmente el titular de 467, se exige FINCA_SIN_TITULAR, lista de faltantes y 220 ABIERTO sin artefactos nuevos; se restaura el titular. Si un escenario previo cerró 220, 028_c es NO_CONCLUYENTE.
7. Newman real, DELETE del RUN y lecturas sin cabeceras incluso si se agotó el presupuesto. Se comparan los cinco períodos, ambas asignaciones, el costo creado, ambos titulares, líneas, comprobantes, variaciones y ausencia de períodos nuevos.

El informe, `resultado.json` y Newman JSON/HTML reales deben quedar en `EvaluacionV3/Resultados/RUN-G44-V3-<timestamp>/`. No se crea un RUN durante `preparar`. El código revisado para esta preparación fue `src/financial_valuation/infrastructure/routers/m06_router.py`, `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py`, `src/financial_valuation/infrastructure/repositories/periodo_repository.py`, `src/financial_valuation/infrastructure/repositories/asiento_repository.py`, `src/financial_valuation/infrastructure/adapters/activo_financiero_m02_adapter.py` y la referencia local G43 `lib/g43_v2.mjs`; el despliegue indicado por la orden no se verificó.

La simulación local cubre 16 situaciones con y sin campos adicionales (32 ensayos). En este entorno, `node pruebas/verificar.mjs` valida los escenarios, la forma y el contrato, pero sus pasos que crean procesos hijos reciben `spawn EPERM`; se ejecutan por separado sintaxis, CLI y DTO. El script `registro_qa.py` no está presente en el repositorio accesible, por lo que el ejemplo conforme se contrasta con `clasificarRegistro` local hasta que el lanzador externo ejecute su validación.
