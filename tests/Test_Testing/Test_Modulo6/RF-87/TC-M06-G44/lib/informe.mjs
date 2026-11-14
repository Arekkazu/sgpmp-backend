const safe=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]').replace(/\|/g,'/').slice(0,500);

export function informe(r){
  const casos=Object.keys(r.casos??{});
  const titulo=r.oficial?casos.some(c=>r.casos[c].estado==='RECHAZADO')?'reevaluación V3 oficial - RECHAZADO':'reevaluación V3 oficial - APROBADO':'reevaluación V3 NO OFICIAL';
  const out=[`# TC-M06-G44 — ${titulo}`,'',`Grupo G44; casos ${casos.join(', ')}; RF-87; versión ${r.version}; RUN ${r.run_id}; TEST; autorización ${safe(r.autorizacion_referencia)}.`,
    'Corrección informada: Desarrollo 0fcde3bb (#1065), origin/test 453277e4. El despliegue requiere verificación en RUN autorizado.','',
    '## Resumen','',...casos.map(c=>`- ${c}: ${r.casos[c].estado}. ${safe(r.casos[c].motivo)}`),'',
    '## Preflight de datos','', '| Requisito | Esperado | Observado | Cumple | Bloqueante |','|---|---|---|---|---|',
    ...(r.preflight_datos??[]).map(x=>`| ${x.requisito} | ${safe(x.esperado)} | ${safe(JSON.stringify(x.observado))} | ${x.cumple?'SÍ':'NO'} | ${x.bloqueante?'SÍ':'NO'} |`),'',
    '## Casos y comprobaciones API',''];
  for(const c of casos){out.push(`### ${c}`,'');for(const q of r.casos[c]?.comprobaciones??[]){
    const rutas={
      '028_a':['/finanzas/periodos/220/cierre'],'028_b':['/finanzas/periodos/260/cierre'],'028_c':['/finanzas/periodos/220/cierre'],
      '029_acceso':['/finanzas/periodos/220/cierre'],'029_mensaje':['/finanzas/periodos/220/cierre'],'029_admin':['/finanzas/periodos/220/prevalidacion'],
      '030_cerrado':['/finanzas/periodos/7/cierre'],'030_concurrencia':['/finanzas/periodos/8/cierre'],'030_sin_segundo':['/finanzas/periodos/8/cierre']};
    const ids=(r.solicitudes??[]).filter(s=>rutas[q.id]?.includes(s.ruta)).map(s=>s.id);
    out.push(`**${q.id} — ${q.estado}.** Se verifica ${safe(q.esperado)}. Preparación: preflight_datos. Solicitudes ${ids.join(', ')||'sin solicitud de cierre'}. Observado: ${safe(q.observado)}. Decisión: ${q.estado==='APROBADO'?'contenido y estado conformes':q.estado==='RECHAZADO'?'discrepancia del producto':'precondición insuficiente'}. Evidencia: resultado.json.`, '');
  }}
  out.push('## Seguimiento V2','',...(r.seguimiento_incidencias_v2??[]).map(x=>`- ${x.id}: ${x.estado_v3}.`),'',
    '## Incidencias de producto','');
  for(const x of r.incidencias??[])out.push(`### ${x.id}`,'',`Esperado: ${safe(x.esperado)}.`,`Observado: ${safe(x.obtenido)}.`,`Evidencia: ${safe(x.evidencia)}; solicitudes ${r.solicitudes.filter(s=>s.ruta?.includes('/cierre')).map(s=>s.id).join(', ')}.`,`Equipo inicial ${x.equipo}: ${safe(x.fundamento)}.`,`Severidad ${x.severidad} (${x.certeza}): ${safe(x.justificacion_severidad)}`,`Causa raíz no determinada. Acción: ${safe(x.accion)}`,'');
  out.push('## Observaciones','',...(r.observaciones??[]).map(x=>`- ${safe(x)}`),'',
    '## Herramientas y evidencias','',`Node ${safe(r.herramientas.node)}; Newman ${r.herramientas.newman?.codigo??'no ejecutado'}; Cypress no aplica.`,...(r.evidencias??[]).map(x=>`- ${safe(x)}`),'',
    '## Problemas técnicos','',...(r.problemas_tecnicos??[]).map(x=>`- ${safe(x)}`),'',
    '## Cierre, rollback y acciones','',`Registro ${r.oficial?'OFICIAL':'NO OFICIAL'}. Cierre del RUN HTTP ${r.cierre?.run?.cierre_http??'no comprobado'}. Rollback ${r.rollback?.verificado?'verificado':'no verificado'}: ${safe(r.rollback?.motivo)}.`,
    'Desarrollo revisa las discrepancias confirmadas. QA decide la siguiente acción con evidencia del RUN autorizado.','');
  return out.join('\n');
}
