# TC-M06-G41 - reevaluacion V2 de RF-87

## Preparación ORD-G41-018 (ronda 4)

TC-M06-019 conserva los oráculos de la matriz. Dentro de un RUN autorizado, el ejecutor registra un precio nuevo por cada especie presente en los activos a valor razonable, con la fuente y categoría del precio vigente y una variación calculada bajo el umbral configurado; confirma la desviación solo cuando el mínimo de 0,01 alcanza ese umbral. Comprueba mediante GET que cada precio nuevo quedó vigente antes del cierre. Así, el 1572, si sigue en VR con especie 423, recibe variación como los activos de especie 422 en V1. `resultado.json` conserva por activo VR el precio usado y la variación de precio unitario esperada, no cero; la medición de cierre con los campos exigidos sigue siendo el oráculo.

El DELETE se verifica con lecturas sin cabeceras del RUN para todas las especies VR: ningún precio nuevo debe persistir y el vigente de cada especie debe volver al de la base. El aviso de cierre a cada Contador y las alertas NIC 41 que puedan emitir los precios nuevos, una por especie, además de la alerta del párrafo 30, pueden persistir. La preparación local no consulta TEST ni crea un RUN.

## Adaptación local ORD-G41-015 (ronda 3)

Este apartado describe el estado de la ronda 3; la preparación vigente es ORD-G41-018, indicada arriba.

TC-M06-019 conserva el criterio de RF-87. Según la consulta de solo lectura entregada por QA el 2026-11-12, un Contador cambió el activo 1572 de costo a valor razonable el 2026-11-10; su valoración por costo quedó inactiva aunque el reconocimiento histórico conserva ese indicador. El activo 1573 sigue por costo. El preflight lee el método vigente de cada activo en la lista y contrasta el historial individual con la valoración por costo activa. Forma VR con 1569, 1570 y cada uno de 1572/1573 que esté a valor razonable; forma COSTO con los restantes de 1572/1573. El 1571 se da de baja dentro del RUN y queda excluido del cierre. Exige precio vigente para cada especie presente en VR antes de cualquier escritura; no crea un precio para la especie 423. El oráculo exige medición de cierre y campos de RF-87 para VR, ausencia de medición de cierre para COSTO y ausencia de revaluación para el activo dado de baja.

`resultado.json` guarda la clasificación con su origen y los datos leídos que motivaron cualquier aborto del preflight en `observado.preflight_vivo`; el informe los cita en prosa. Persisten potencialmente el aviso de cierre a todos los Contadores y alertas NIC 41, incluida la del párrafo 30 si el 1573 tiene precio de su especie. Esta preparación no ejecutó TEST ni creó un RUN.

## Alcance y archivos vigentes

ORD-G41-012, fase preparar, ronda 1 de 2. V2 prueba solo TC-M06-019. TC-M06-020 quedo APROBADO en V1, RUN-G41-V1-20261109-175216, y no se ejecuta ni evalua aqui. El informe V1 y su evidencia permanecen en Resultados/ sin cambios.

- g41.mjs: ejecutor canonico; --capacidades y --comprobar son locales.
- lib/g41_core.mjs: oraculos de 019 y prevalidacion.
- G41.postman_collection.json: unica coleccion Newman vigente, cuatro lecturas finales.
- pruebas/newman_hijo.mjs: reportes Newman saneados.
- pruebas/registro_qa.mjs: contrato del registro QA.
- pruebas/g41_local.test.mjs y pruebas/contrato_g41.json: ensayos locales y contrato.
- pruebas/g41_dto.test.py: contraste local de DTO.
- preparacion_ORD-G41-009.md: preparacion historica V1; no es informe de RUN.

No hay spec Cypress: la matriz exige solo API. El ejecutor produce un unico Markdown oficial en EvaluacionV2/Resultados/RUN-G41-V2-<timestamp>/TC-M06-G41_reevaluacion_V2.md, junto con resultado.json, preflight.json y los reportes Newman realmente generados.

## Fuentes revisadas

Casos_Prueba(Modulo6Agrup).csv, linea 384, Windows-1252; ANALISIS-G41-V2.md, decisiones D1-D4; informe y resultado V1 del RUN 175216. Rutas de codigo consultadas con git show origin/test:src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py, git show origin/test:src/identity_access/domain/value_objects/evento_categoria.py y git show origin/test:src/financial_valuation/infrastructure/adapters/notificacion_financiera_m01_adapter.py. Para el patron de contexto V2 se leyo TC-M06-G40/g40.mjs. No se consulto TEST en esta preparacion.

## Decisiones D1-D4

D1: todos los criterios a-f de 019, un solo cierre del periodo 220; el segundo cierre de diciembre servia a 020 y se retiro. D2: se conserva la preparacion dentro del RUN de los activos 1569-1573, la baja RF-45 de 1571, los eventos y pendientes, y un precio vigente. D3: el aviso debe tener id nuevo respecto de la bandeja completa del Contador QA y el texto exacto del mes cerrado, tolerando solo el punto final. D4: un aviso de cierre para cada Contador del sistema, sin filtro de finca, persiste despues del DELETE aunque el periodo 220 vuelva a ABIERTO. Tambien pueden persistir las alertas NIC 41 y de precio emitidas.

## Preflight y cierre

Antes de escribir, el preflight vivo exige periodo 220 ABIERTO y del mes actual en America/Bogota; periodo siguiente inexistente o ABIERTO; activos 1569-1573 inicialmente ACTIVO; precio vigente coherente con simulacion; prevalidacion sin bloqueos, activos sin precio ni trazabilidad incompleta, y sin autorizacion requerida; ningun cierre previo o en curso. La prevalidacion de origin/test despues de 0fcde3bb revisa titular de finca y matriz para los hechos que el cierre registraria. Una falta deja 019 NO_CONCLUYENTE sin escrituras del escenario y se solicita DELETE. Un 409 EXCLUSION_REQUIERE_AUTORIZACION o un periodo EN_CIERRE tambien deja 019 NO_CONCLUYENTE: no se autorizan exclusiones.

El rollback se comprueba con GET sin cabeceras del RUN: periodo 220, siguiente, cinco activos, mediciones, variaciones, calculos, lineas, matriz, precios, eventos RF-45 y reportes. El DELETE 200 por si solo no confirma restauracion.

## Validacion local

node --check g41.mjs, node --check lib/g41_core.mjs, node --check pruebas/g41_local.test.mjs, node g41.mjs --comprobar y node pruebas/g41_local.test.mjs. La suite usa solo loopback local y no es evidencia de TEST. A4 intenta un ensayo en proceso hijo y, si el entorno permite spawn, copia el RUN local completo y capacidades.json a TEMP/g41-verificar-ejemplo e imprime las rutas. En esta ronda el hijo fue impedido por spawn EPERM; el test documenta la causa.

## Reglas y protecciones restauradas (ORD-G41-013)

V2 conserva un único cierre del período 220 para TC-M06-019. El lanzador externo aporta `contexto_operacion.json` y autorización particular; `--capacidades` declara solo `TC-M06-019` y `G41-API-019-01`. `--comprobar` comprueba dependencias locales. El preflight escribe `preflight.json` antes de toda petición y exige `QA_AUTORIZADO=SI`, host canónico y datos de acceso. La lectura de `.env.qa` está condicionada a esa autorización. Las pruebas locales usan valores ficticios en loopback.

Los permisos se derivan de las rutas realmente usadas. En M06, C=1, R=2 y E=5; el contador necesita `cierre_periodo:2,5`, `configuracion_contable:1,2`, `precios_mercado:1,2`, `valoracion_activos:2,5`, `estado_resultados:2`, `revelaciones_nic41:2` y `auditoria_financiera:2`. El administrador necesita `activos_biologicos:1,2,5` para eventos y estado. `/finanzas/periodos` admite permisos alternativos de lectura en el router actual; el cierre y la prevalidación siguen exigiendo `cierre_periodo`. Los faltantes se registran por actor. Sin permisos suficientes, 019 queda NO_CONCLUYENTE y no se hacen escrituras del escenario.

La guarda de rutas rechaza `undefined` y `null` antes de enviar una petición. Las solicitudes son seriales. El flujo selecciona activos por `id_activo_biologico`, no por posición de respuesta; la lista puede incluir otras fincas y especies mezcladas. El precio vigente debe corresponder a la especie y categoría configurada (`PESO_KG` o `POR_CABEZA`) y concordar con la simulación. El umbral se toma de `config.general.pct_umbral_desviacion_precio`; si el paso mínimo de 0,01 alcanza el umbral, se envía `confirmar_desviacion=true`.

Las asignaciones contables que faltan se crean a partir de una cuenta existente del mismo sentido y se guardan sus ids para comprobar el rollback. La auditoría se consulta con `tipo_evento` de inicio y fin, filtrada por período. El aviso se compara por texto exacto del mes cerrado y por id nuevo respecto de la bandeja previa; un aviso preexistente no satisface el criterio. El DELETE se sigue de lecturas sin cabeceras de RUN; un HTTP 200 aislado no acredita restauración.

Para 019(c), `valor_razonable_inicio` corresponde a `mediciones[].valor_razonable_anterior`, `valor_razonable_cierre` a `valor_razonable_actual`, `variacion_total` a `variacion_total`, las dos variaciones a `ganancia_perdida_transformacion` y `ganancia_perdida_precio_mercado`, y el método a `activos[].valorado_por_costo=false`. Las pruebas de decisión comprueban cada criterio de `evaluar019` por separado. Las líneas de baja RF-45 de 1571 y la depreciación por costo de 1572/1573 no incumplen por sí mismas el criterio b.

## Cobertura local V1 retirada de V2

La suite V1 de HEAD tenía 72 pruebas; ORD-G41-012 dejó 18. Esta ronda conserva las 18 y restaura la cobertura aplicable a 019, con 57 pruebas locales. Se retiraron las decisiones `inicio_distinto_rf82`, `inicio_distinto_anterior`, `total_incorrecto`, `componentes_incorrectos`, `rama_a_conforme`, `rama_b_conforme` y `rama_b_suma_incorrecta`, junto con `decimal exacto`: verificaban el cálculo acumulado y las ramas de TC-M06-020. Los escenarios `medicion_intermedia`, `segundo_inicio`, `inicio_rf82`, `componentes_mal` y `segundo_cierre_fallido` dependían de 020 o del cierre de diciembre. Las aserciones de 020 dentro de los escenarios compartidos se retiraron; las de 019 permanecen. Las pruebas de variantes de error de V1 se concentran en la tabla de decisión 019 y en los escenarios V2 vigentes. No se modificaron oráculos ni evidencias V1.

Rutas de lectura de código consultadas en esta ronda: `src/financial_valuation/infrastructure/routers/m06_router.py` y `src/biological_assets/infrastructure/routers/activo_biologico_router.py`. La revisión de protecciones se hizo en `g41.mjs` y `lib/g41_core.mjs`. No se consultó TEST.
