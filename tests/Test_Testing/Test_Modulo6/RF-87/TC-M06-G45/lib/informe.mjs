const limpiar=x=>String(x??'').replace(/\|/g,'\\|').replace(/[\r\n]+/g,' ').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+|\bQA-[A-Z0-9-]{4,}\b|\b\d{8,12}\b/g,'[RESERVADO]').slice(0,800);
export function informe(r){
  const casos=Object.keys(r.casos??{});
  const completo=casos.every(k=>r.casos[k].estado==='APROBADO');
  const rechazado=casos.some(k=>r.casos[k].estado==='RECHAZADO');
  const titulo=r.oficial?'TC-M06-G45 — reevaluación V2 oficial - '+(completo?'APROBADO':'RECHAZADO'):'TC-M06-G45 — reevaluación V2 NO OFICIAL';
  const filas=['# '+titulo,'',
    'Grupo G45 · '+casos.join(', ')+' · '+r.rf+' · V'+r.version+' · '+r.run_id+' · TEST. Autorización: '+limpiar(r.autorizacion_referencia)+'. Commit de referencia informado: '+limpiar(r.commit_referencia)+'.','',
    '## Resumen de veredictos','',
    '| Caso | Estado | Motivo |','|---|---|---|',
    ...casos.map(c=>'| '+c+' | '+r.casos[c].estado+' | '+limpiar(r.casos[c].motivo)+' |'),'',
    '## Preflight de datos y permisos','',
    '| Requisito | Esperado | Observado | Cumple | Bloqueante |','|---|---|---|---|---|',
    ...(r.preflight_datos??[]).map(x=>'| '+limpiar(x.requisito)+' | '+limpiar(x.esperado)+' | '+limpiar(JSON.stringify(x.observado))+' | '+(x.cumple?'Sí':'No')+' | '+(x.bloqueante?'Sí':'No')+' |'),'',
    'Período elegido para 031 y causa de pausa: '+limpiar(JSON.stringify(r.periodo_031??'ninguno'))+'.','',
    '## Esperado y observado por caso',''];
  for(const caso of casos){
    filas.push('### '+caso+' — '+r.casos[caso].estado,'');
    for(const x of r.casos[caso].comprobaciones??[])filas.push('- '+x.id+': se esperaba '+limpiar(x.esperado)+'. Se observó '+limpiar(x.observado)+'. Estado '+x.estado+'. Evidencia '+limpiar(x.evidencia??'resultado.json')+'.');
    filas.push('');
  }
  filas.push('Las comprobaciones son solo API; no hay UI obligatoria para este grupo.','',
    '## Respuestas, integridad y seguimiento V1','',
    'Respuestas saneadas: '+limpiar(JSON.stringify(r.respuestas??{}))+'.',
    'Bases: '+limpiar(JSON.stringify(r.bases??{}))+'.',
    'Seguimiento de INC-M06-G45-01, 02 y 03: '+limpiar(JSON.stringify(r.seguimiento_v1??'pendiente'))+'.',
    'Rutas M02 revisadas y motivo: '+limpiar(JSON.stringify(r.m02??'sin evaluación'))+'.','',
    '## Incidencias de producto','');
  if(!r.incidencias?.length)filas.push('Ninguna discrepancia de producto acreditada en este RUN.');
  for(const x of r.incidencias??[])filas.push('### '+x.id,'',
    'Esperado: '+limpiar(x.esperado)+'.',
    'Observado: '+limpiar(x.obtenido)+'.',
    'Evidencia: '+limpiar(x.evidencia)+'; comprobaciones '+(r.casos[x.casos[0]].comprobaciones??[]).filter(y=>y.estado==='RECHAZADO').map(y=>y.evidencia??y.id).join(', ')+'.',
    'Equipo inicial: '+x.equipo+'. Fundamento: '+limpiar(x.fundamento),
    'Severidad: '+x.severidad+'. '+limpiar(x.justificacion_severidad)+' Certeza: '+x.certeza+'. Causa raíz: '+limpiar(x.causa_raiz),
    'Acción: '+limpiar(x.accion),'');
  filas.push('## Evidencias y herramientas','',
    'Node '+limpiar(r.herramientas.node)+'; Newman '+limpiar(r.herramientas.newman?.codigo??'no ejecutado')+'; Cypress no aplica (0 pruebas); solicitudes '+(r.total_solicitudes_api??0)+'.',
    ...(r.evidencias??[]).map(x=>'- '+limpiar(x)),'',
    '## Problemas técnicos','',
    ...(r.problemas_tecnicos?.length?r.problemas_tecnicos.map(x=>'- '+limpiar(x)):['Ninguno registrado.']),'',
    '## Observaciones','',
    ...(r.observaciones??[]).map(x=>'- '+limpiar(x)),'',
    '## Cierre y rollback','',
    'DELETE del RUN: HTTP '+(r.cierre?.run?.cierre_http??'no confirmado')+'. Rollback verificado: '+(r.rollback?.verificado?'sí':'no')+'. '+limpiar(r.rollback?.motivo),
    'Registro '+(r.oficial?'OFICIAL':'NO OFICIAL')+'. '+(!r.oficial?'QA debe resolver la precondición, herramienta o rollback pendiente antes de oficializar.':rechazado?'Desarrollo debe revisar las discrepancias acreditadas; QA decidirá una nueva reevaluación.':completo?'Los tres casos cumplen las comprobaciones ejecutadas.':'QA debe revisar el resultado antes de evaluar de nuevo.'),'');
  return filas.join('\n');
}
