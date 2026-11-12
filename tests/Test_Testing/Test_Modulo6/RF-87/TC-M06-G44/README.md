# TC-M06-G44 / RF-87 / ORD-G44-010

Preparacion local V2 para TC-M06-028, 029 y 030. Solo API. La fuente del oraculo sigue siendo la matriz original `Casos_Prueba(Modulo6Agrup).csv`, RF-87 v1.1, RF-86 CA-21 y CU06; el codigo no cambia el esperado. La orden actual aporta los datos TEST verificados por el responsable QA el 2026-11-10. No se accede a TEST en esta fase.

## Archivos activos

`g44.mjs` es el ejecutor; `G44.postman_collection.json` es la coleccion Newman; `lib/g44_core.mjs` evalua criterios; `lib/informe.mjs` genera el unico informe oficial dentro del RUN; `pruebas/g44_escenarios.test.mjs` simula la API; `pruebas/verificar.mjs` ejecuta validaciones locales. No hay spec Cypress: estos casos exigen API. `Resultados/` V1 y el RUN V2 anterior quedan intactos.

## Secuencia para un RUN V2 autorizado externamente

1. Cuatro logins y lecturas previas. `preflight_datos` registra por separado estado de 7/8/219/220/260, NIT de 219/260, linea 17 del 8, prevalidaciones de 220/260, titulares de 466/467 y matrices 34/49. GET `/finanzas/activos` con el token del Contador registra 1572 y 1573 como datos informativos no bloqueantes. El requisito bloqueante `finca_467_activo_por_costo` exige al menos un activo de la finca 467 con `valorado_por_costo === true` y `vida_util_meses > 0`; los ids se guardan en `activos_por_costo_467` y sustentan 028-b. Solo un requisito bloqueante incumplido produce `PREFLIGHT_DATOS_NO_CONCLUYENTE` y detiene las escrituras de producto. El DELETE del RUN y las lecturas poscierre sin cabeceras se hacen igualmente para comprobar rollback frente a las bases.
2. 029: tres roles intentan cerrar 220; Administrador consulta periodos y prevalidacion 220.
3. 030: POST de 7 CERRADO y observacion adicional de 219 CERRADO, cuyo `ultimo_cierre` aporta el ejecutor 141; dos POST de 8 sin autorizacion.
4. 028-a: DELETE matriz 34; costo MANO_OBRA_PROPIA 103.00 con fecha actual en caprino 1569 de NIT-C/220; linea PENDIENTE_CUENTA; prevalidacion y cierre 220 deben listar faltantes y mantenerlo ABIERTO.
5. Restaurar matriz 34 con la asignacion generica 158405/250505; comprobar linea resuelta y prevalidacion 220 sin bloqueos. Si no se limpia, 028-b queda NO_CONCLUYENTE sin DELETE 49 ni cierre.
6. 028-b: DELETE matriz 49; cierre 220 debe bloquear depreciacion sin cuenta y dejarlo ABIERTO.
7. 028-c, independiente de 220: PUT de los cuatro campos tributarios de 466 a null; prevalidacion y cierre 260 deben informar finca sin titular y dejarlo ABIERTO. Un PUT 4xx deja 028-c NO_CONCLUYENTE.
8. Newman, DELETE del RUN y lecturas sin cabeceras. Se comparan matrices, costo, titular, estados, lineas, comprobantes, variaciones y lista de periodos.

Cada POST de cierre guarda el cuerpo saneado en `respuestas_cierre`; ante 200, guarda tambien comprobantes y lineas. Las incidencias V1 01/02/03/05 conservan seguimiento REPRODUCIDA/NO_REPRODUCIDA; 06 conserva NUEVA_CONFIRMADA_EN_V2/NO_CONFIRMADA_EN_V2. No se atribuye causa raiz a partir de codigo local.

Efectos TEST previstos: 4 logins; un GET `/finanzas/activos`; DELETE 34 y 49; un costo en 220; un POST matriz; un PUT titular 466; POST cierre en 7 x1, 219 x1, 8 x2, 220 x5 y 260 x1; DELETE del RUN. Solo el lanzador externo autorizado puede ejecutar estos efectos. El informe oficial V2 pertenece a `EvaluacionV2/Resultados/RUN-G44-V2-<timestamp>/TC-M06-G44_reevaluacion_V2.md` con `resultado.json` y Newman real. Esta preparacion no crea RUN.

`node pruebas/verificar.mjs` valida localmente 20 simulaciones con y sin campos inyectados, sintaxis, CLI, Newman, DTO, contrato y `--comprobar`, sin red remota.
