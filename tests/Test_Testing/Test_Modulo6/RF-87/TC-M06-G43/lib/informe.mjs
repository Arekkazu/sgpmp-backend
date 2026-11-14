// Plantilla de informe extraída del ejecutor original del grupo; sin casos fijos.
const clean=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]').slice(0,240);
const cleanCompleto=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]');
export function informe(r){const CASOS=Object.keys(r.casos??{});
  const resultado=r.oficial?(CASOS.every(c=>r.casos[c].estado==='APROBADO')?'APROBADO':CASOS.some(c=>r.casos[c].estado==='RECHAZADO')?'RECHAZADO':'NO OFICIAL'):'NO OFICIAL';
  const titulo=r.version>=2?`TC-M06-${r.grupo} — reevaluación V${r.version}${r.oficial?` oficial - ${resultado}`:' NO OFICIAL'}`:`TC-M06-${r.grupo} — ${r.run_id}`;
  const lines=[
    `# ${titulo}`,'',
    `${r.grupo} | ${r.rf} | ${CASOS.join(', ')} | V${r.version} | ${r.run_id} | TEST | autorización ${r.autorizacion_referencia} | commit desplegado informado: 453277e4, no verificado en este RUN.`,'',
    '## Resumen','',
    '| Caso | Estado | Motivo |','|---|---|---|',
    ...CASOS.map(c=>`| ${c} | ${r.casos[c]?.estado??'NO_CONCLUYENTE'} | ${clean(r.casos[c]?.motivo??'')} |`),'',
    '## Criterios API y UI','',
    '| Caso | Criterio | Esperado | Observado | Cumple |','|---|---|---|---|---|',
  ];
  for(const c of CASOS)for(const z of r.casos[c]?.comprobaciones??[])lines.push(`| ${c} | ${z.id} | ${clean(z.esperado)} | ${clean(z.observado)} | ${z.estado} |`);
  if(r.version>=2)for(const c of CASOS){
    const z=r.casos[c],p=c.slice(-3),periodo=p==='024'||p==='027'?'8':p==='025'?'266':'siguiente de 266';
    lines.push('',`### ${c}`,'',`Qué se verifica: ${p==='026'?'RF-87 v1.2, estimación o exclusión por activo':p==='024'?'precio congelado durante la pausa':p==='025'?'advertencia y exclusión de activos sin precio':'autorización de la exclusión por trazabilidad'}.`,`Preparación: período ${periodo}; preflight y línea base en resultado.json.`,`Qué se hizo: peticiones API y panel UI ${p==='024'?'027':p} registrados en las evidencias del RUN.`,`Esperado: ${(z?.comprobaciones??[]).map(x=>x.esperado).join('; ')}.`,`Observado: ${(z?.comprobaciones??[]).map(x=>x.observado).join('; ')||z?.motivo}.`,`Por qué se decide: ${z?.estado} — ${z?.motivo}.`);}
  if(r.version>=2){lines.push('','## Fichas de comprobaciones rechazadas','');for(const c of CASOS)for(const z of r.casos[c]?.comprobaciones??[]){if(z.estado!=='RECHAZADO')continue;const n=c.slice(-3),panel=n==='024'?'027':n,inc=r.incidencias.find(x=>x.casos?.includes(c));const solicitud=r.solicitudes.find(x=>n==='024'?/\/finanzas\/periodos\/8\//.test(x.ruta):n==='025'?/\/finanzas\/periodos\/266\//.test(x.ruta):n==='026'?/\/finanzas\/periodos\//.test(x.ruta):/\/finanzas\/periodos\/8\//.test(x.ruta));const p=r.precios[0],est=r.diagnostico?.estimacion_1644;lines.push(`### ${c} · ${z.id}`,'',`Criterio de matriz: ${n==='025'?'Antes de revaluar, advertencia con número, lista de activos y especies sin precio, y respuesta Sí/No.':n==='026'?'RF-87 v1.2: decisión por activo.':n==='027'?'Antes de continuar, lista de asientos y activos con eslabón incompleto y solicitud de autorización.':'Precio inicial congelado durante el cierre.'}`,`Esperado: ${cleanCompleto(z.esperado)}.`,`Observado: ${cleanCompleto(z.observado)}; HTTP ${solicitud?.http??'sin respuesta'}.`,...(n==='024'&&p?[`Precio inicial ${p.p_ini}/${p.p_ini_fecha}; precio nuevo ${p.p_nuevo}/${p.p_nuevo_fecha}; congelado ${p.congelado}/${p.congelado_fecha}.`]:[]),...(n==='026'&&est?[`Vías de estimación consultadas: ${JSON.stringify(est.vias)}; variación cero: ${est.auditoria_sin_variacion}; cálculos: ${JSON.stringify(est.calculos)}; auditoría: ${JSON.stringify(est.auditoria)}; alertas: ${JSON.stringify(est.alertas)}.`]:[]),`Evidencia: ${solicitud?.id??'solicitud no disponible'}; ${r.cypress?.paneles?.[panel]?.capturas_tramos?.map(x=>`cypress/${panel}/screenshots/g43.cy.js/${x}`).join(', ')||'captura no disponible'}; resultado.json.`,`Equipo inicial: ${inc?.equipo??'POR DETERMINAR'}. Severidad: ${inc?.severidad??'NO DETERMINADA'}; ${clean(inc?.justificacion_severidad??'pendiente de evidencia')}.`);}}
  lines.push('','## Precios','','| Especie | P_ini id/fecha | Fuente de P_ini | P_nuevo id/fecha | Congelado id/fecha |','|---|---|---|---|---|',
    ...r.precios.map(x=>`| ${x.especie} | ${x.p_ini??''} / ${x.p_ini_fecha??''} | ${clean(x.p_ini_origen??'')} | ${x.p_nuevo??''} / ${x.p_nuevo_fecha??''} | ${x.congelado??''} / ${x.congelado_fecha??''} |`),
    '','## Activos sin precio','','| Período | Prevalidación | Excluidos | Procesados |','|---|---|---|---|',
    ...r.activos.map(x=>`| ${x.periodo} | ${x.prevalidacion} | ${x.excluidos} | ${x.procesados} |`),
    '','## Líneas','','| Línea | Activo | Eslabón faltante | Excluida | Destino |','|---|---|---|---|---|',
    ...r.lineas.map(x=>`| ${x.id} | ${x.id_activo??''} | ${x.faltantes??''} | ${x.excluida} | ${x.destino} |`),
    '','## UI','','| Panel | Pruebas ejecutadas | Estado | Acta |','|---|---|---|---|',
    ...Object.entries(r.cypress?.paneles??{}).map(([k,x])=>`| ${k} | ${x.totalTests??0} | ${x.estado??'NO_CONCLUYENTE'} | ${clean(x.evidencia??'')} |`),
    '',...Object.entries(r.cypress?.paneles??{}).map(([k,x])=>`- Panel ${k}: controles citados: ${(x.controles_citados??[]).map(clean).join('; ')||'ninguno'}; ${clean(x.diagnostico??'')} Tramos: ${(x.capturas_tramos??[]).join(', ')||'sin captura'}.`),
    '','## Evidencia de estimación 1644','',
    `Vías: ${JSON.stringify(r.diagnostico?.estimacion_1644?.vias??{})}; auditoría sin variación: ${r.diagnostico?.estimacion_1644?.auditoria_sin_variacion??'no consultada'}; activos procesados: ${r.diagnostico?.estimacion_1644?.activos_procesados??'no consultado'}. Detalle saneado en resultado.json.`,
    '','## Incidencias','',
    ...r.incidencias.map(x=>`- ${x.id} (casos ${(x.casos??[]).join(',')}): esperado ${x.esperado}; obtenido ${x.obtenido}. Evidencia: ${x.evidencia}. Impacto: ${x.impacto}. Severidad ${x.severidad}: ${x.justificacion_severidad}; certeza ${x.certeza}. Equipo inicial ${x.equipo}: ${x.fundamento}. Hipótesis, sin atribuir causa raíz: ${x.hipotesis}. Acción: ${x.accion}.`),
    '','## Seguimiento de incidencias previas','',
    ...['INC-M06-G43-01','INC-M06-G43-02','INC-M06-G43-03','INC-M06-G32-01'].map(id=>`- ${id}: ${r.seguimiento?.[id]??'NO_CONCLUYENTE'}.`),
    '','## Herramientas y evidencias','',
    `Node ${r.herramientas.node}; Newman código ${r.herramientas.newman?.codigo??'no ejecutado'}; Cypress código ${r.herramientas.cypress?.codigo??'no ejecutado'}, pruebas ${r.herramientas.cypress?.totalTests??0}.`,
    ...r.evidencias.map(x=>`- ${x}`),
    '','## Problemas técnicos','',...r.problemas_tecnicos.map(x=>`- ${cleanCompleto(x)}`),
    '','## Observaciones','',
    ...(r.observaciones??[]).map(x=>`- ${clean(x)}`),
    ...(r.version>=2?['- OBS-G43-UI-01 (usabilidad, Desarrollo): en la pausa EN_CIERRE, la alerta indica “hasta que autorices las exclusiones”, mientras el único control es “Cancelar el cierre” y no se muestra la lista de trazabilidad. Evidencia histórica: ../RUN-G43-V2-20261113-070927/cypress/027/screenshots/g43.cy.js/G43-UI-027-tramo-1.png y ../RUN-G43-V2-20261113-070927/cypress/026/screenshots/g43.cy.js/G43-UI-026-tramo-1.png. No altera los veredictos de los casos.']:[]),
    '','## Condiciones de oficialidad','',
    ...Object.entries(r.condiciones_oficialidad??{}).map(([k,v])=>`- ${k}: ${v?'cumple':'no cumple'}.`),
    '','## Efectos persistentes','',
    ...(r.efectos_persistentes??[]).map(x=>`- Período ${x.periodo}, aviso ${x.id}: ${clean(x.texto)}.`),
    'Los avisos de cierre y las alertas NIC 41 pueden persistir fuera del rollback del sandbox.','',
    '','## Cierre, rollback y acción','',
    `Registro ${r.oficial?'OFICIAL':'NO OFICIAL'}. Rollback verificado: ${r.rollback.verificado?(r.version>=2?'sí':'si'):'no'}. ${clean(r.rollback.motivo??'')}`,
    'Las incidencias requieren corrección y reevaluación expresamente autorizada.',''
  );
  const texto=lines.join('\n');
  if(/\u00C3|\uFFFD/u.test(texto))throw Error('INFORME_UTF8_INVALIDO');
  return texto;
}
