// Plantilla de informe extraída del ejecutor original del grupo; sin casos fijos.
const clean=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]').slice(0,240);
export function informe(r){const CASOS=Object.keys(r.casos??{});
  const lines=[
    `# TC-M06-${r.grupo} — ${r.run_id}`,'',
    `${r.grupo} | ${r.rf} | ${CASOS.join(', ')} | V${r.version} | TEST | autorización ${r.autorizacion_referencia} | commit no consultado (Git prohibido).`,'',
    '## Preflight de datos','',
    '| Requisito | Esperado | Observado | Cumple | Bloqueante |','|---|---|---|---|---|',
    ...(r.preflight_datos??[]).map(x=>`| ${x.requisito} | ${clean(x.esperado)} | ${clean(JSON.stringify(x.observado))} | ${x.cumple?'SI':'NO'} | ${x.bloqueante?'SI':'NO'} |`),'',
    `028-b depende de los activos por costo de finca 467: ${clean(JSON.stringify(r.activos_por_costo_467??[]))}.`,'',
    '## Resumen','',
    '| Caso | Estado | Motivo |','|---|---|---|',
    ...CASOS.map(c=>`| ${c} | ${r.casos[c]?.estado??'NO_CONCLUYENTE'} | ${clean(r.casos[c]?.motivo??'')} |`),'',
    '## Criterios API y UI','',
    '| Caso | Criterio | Esperado | Observado | Cumple |','|---|---|---|---|---|',
  ];
  for(const c of CASOS)for(const z of r.casos[c]?.comprobaciones??[])lines.push(`| ${c} | ${z.id} | ${clean(z.esperado)} | ${clean(z.observado)} | ${z.estado} |`);
  lines.push('','## Precios','','| Especie | P_ini id/fecha | P_nuevo id/fecha | Congelado id/fecha |','|---|---|---|---|',
    ...r.precios.map(x=>`| ${x.especie} | ${x.p_ini??''} / ${x.p_ini_fecha??''} | ${x.p_nuevo??''} / ${x.p_nuevo_fecha??''} | ${x.congelado??''} / ${x.congelado_fecha??''} |`),
    '','## Activos sin precio','','| Periodo | Prevalidacion | Excluidos | Procesados |','|---|---|---|---|',
    ...r.activos.map(x=>`| ${x.periodo} | ${x.prevalidacion} | ${x.excluidos} | ${x.procesados} |`),
    '','## Lineas','','| Linea | Activo | Eslabon faltante | Excluida | Destino |','|---|---|---|---|---|',
    ...r.lineas.map(x=>`| ${x.id} | ${x.id_activo??''} | ${x.faltantes??''} | ${x.excluida} | ${x.destino} |`),
    '','## UI','','| Panel | Pruebas ejecutadas | Estado | Acta |','|---|---|---|---|',
    ...Object.entries(r.cypress?.paneles??{}).map(([k,x])=>`| ${k} | ${x.totalTests??0} | ${x.estado??'NO_CONCLUYENTE'} | ${clean(x.evidencia??'')} |`),
    '','## Incidencias','',
    ...r.incidencias.map(x=>`- ${x.id} (casos ${(x.casos??[]).join(',')}): esperado ${x.esperado}; obtenido ${x.obtenido}. Evidencia: ${x.evidencia}. Impacto: ${x.impacto}. Severidad ${x.severidad}: ${x.justificacion_severidad}; certeza ${x.certeza}. Equipo inicial ${x.equipo}: ${x.fundamento}. Hipótesis, sin atribuir causa raíz: ${x.hipotesis}. Acción: ${x.accion}.`),
    '','## Herramientas y evidencias','',
    `Node ${r.herramientas.node}; Newman codigo ${r.herramientas.newman?.codigo??'no ejecutado'}; Cypress codigo ${r.herramientas.cypress?.codigo??'no ejecutado'}, pruebas ${r.herramientas.cypress?.totalTests??0}.`,
    ...r.evidencias.map(x=>`- ${x}`),
    '','## Problemas tecnicos','',...r.problemas_tecnicos.map(x=>`- ${clean(x)}`),
    '','## Observaciones','',
    ...(r.observaciones??[]).map(x=>`- ${clean(x)}`),
    '','## Cierre, rollback y accion','',
    `Registro ${r.oficial?'OFICIAL':'NO OFICIAL'}. Rollback verificado: ${r.rollback.verificado?'si':'no'}. ${clean(r.rollback.motivo??'')}`,
    'Las incidencias requieren correccion y reevaluacion expresamente autorizada.',''
  );
  const texto=lines.join('\n');
  if(/\u00C3|\uFFFD/u.test(texto))throw Error('INFORME_UTF8_INVALIDO');
  return texto;
}
