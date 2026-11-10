const limpiar=x=>String(x??'').replace(/\|/g,'\\|').replace(/[\r\n]+/g,' ').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+|\bQA-[A-Z0-9-]{4,}\b|\b\d{8,12}\b/g,'[RESERVADO]').slice(0,600);
export function informe(r){
  const casos=Object.keys(r.casos??{});
  const filas=[
    `# TC-M06-G45 — ${r.run_id}`,'',
    `Grupo G45 | casos ${casos.join(', ')} | ${r.rf} | V${r.version} | TEST | autorización ${limpiar(r.autorizacion_referencia)} | commit no consultado (Git prohibido).`,'',
    '## Resumen de veredictos','',
    '| Caso | Veredicto | Motivo |','|---|---|---|',
    ...casos.map(c=>`| ${c} | ${r.casos[c].estado} | ${limpiar(r.casos[c].motivo)} |`),'',
    '## Preflight de datos','',
    '| Requisito | Esperado | Observado | Cumple | Bloqueante |','|---|---|---|---|---|',
    ...(r.preflight_datos??[]).map(x=>`| ${limpiar(x.requisito)} | ${limpiar(x.esperado)} | ${limpiar(JSON.stringify(x.observado))} | ${x.cumple?'SI':'NO'} | ${x.bloqueante?'SI':'NO'} |`),'',
    '## Esperado y observado por comprobación API','',
    '| Caso | Comprobación | Esperado | Observado | Estado |','|---|---|---|---|---|',
    ...casos.flatMap(c=>(r.casos[c].comprobaciones??[]).map(x=>`| ${c} | ${x.id} | ${limpiar(x.esperado)} | ${limpiar(x.observado)} | ${x.estado} |`)),'',
    'No hay comprobaciones UI obligatorias en esta orden.','',
    '## Respuestas y lecturas de integridad','',
    'Los cuerpos saneados de cierre, costo y reversión constan en `resultado.json` (`respuestas`).',
    `Bases: ${limpiar(JSON.stringify(r.bases??{}))}.`,
    `Integridad final: ${limpiar(JSON.stringify(r.integridad??{}))}.`,
    `OpenAPI complementaria: ${limpiar(JSON.stringify(r.openapi??{}))}.`,'',
    '## Incidencias de producto','',
    ...(r.incidencias?.length?r.incidencias.map(x=>`- ${x.id} (${x.casos.join(', ')}): esperado ${limpiar(x.esperado)}; obtenido ${limpiar(x.obtenido)}. Evidencia: ${x.evidencia}. Severidad ${x.severidad}: ${limpiar(x.justificacion_severidad)}. Certeza ${x.certeza}. Equipo inicial ${x.equipo}: ${limpiar(x.fundamento)} Causa raíz ${limpiar(x.causa_raiz)} Acción: ${limpiar(x.accion)}${x.relacion?` Relacionada con ${x.relacion}.`:''}${x.clasificacion?` Clasificación ${x.clasificacion}.`:''}`):['- Ninguna discrepancia de producto acreditada.']),'',
    '## Evidencias y herramientas','',
    `Node ${r.herramientas.node}; Newman ${r.herramientas.newman?.codigo??'no ejecutado'}; Cypress no aplica (0 pruebas); solicitudes ${r.total_solicitudes_api??0}.`,
    ...(r.evidencias??[]).map(x=>`- ${limpiar(x)}`),'',
    '## Problemas técnicos','',
    ...(r.problemas_tecnicos?.length?r.problemas_tecnicos.map(x=>`- ${limpiar(x)}`):['- Ninguno registrado.']),'',
    '## Observaciones y alcance','',
    ...(r.observaciones??[]).map(x=>`- ${limpiar(x)}`),'',
    '## Cierre y rollback','',
    `DELETE del RUN: HTTP ${r.cierre?.run?.cierre_http??'no confirmado'}. Rollback verificado mediante lecturas posteriores: ${r.rollback?.verificado?'SI':'NO'}. ${limpiar(r.rollback?.motivo)}`,
    `Registro ${r.oficial?'OFICIAL':'NO OFICIAL'}. La próxima acción es revisar las incidencias acreditadas y decidir una reevaluación autorizada si procede.`,''];
  return filas.join('\n');
}
