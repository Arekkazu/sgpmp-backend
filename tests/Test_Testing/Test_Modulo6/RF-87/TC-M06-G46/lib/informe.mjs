const limpio=x=>String(x??'').replace(/\|/g,'\\|').replace(/[\r\n]+/g,' ').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+|\bQA-[A-Z0-9-]{4,}\b|\b\d{8,12}\b/g,'[RESERVADO]').slice(0,700);
export function informe(r){
  const caso='TC-M06-034',c=r.casos[caso];
  return [
    `# TC-M06-G46 — ${r.run_id}`,'',
    `Grupo G46 | caso ${caso} | ${r.rf} | V${r.version} | TEST | autorización ${limpio(r.autorizacion_referencia)} | commit no consultado (Git prohibido).`,'',
    '## Resumen de veredictos','',`| Caso | Veredicto | Motivo |`,`|---|---|---|`,`| ${caso} | ${c.estado} | ${limpio(c.motivo)} |`,'',
    '## Preflight de datos','',
    '| Requisito | Esperado | Observado | Cumple | Bloqueante |','|---|---|---|---|---|',
    ...r.preflight_datos.map(x=>`| ${limpio(x.requisito)} | ${limpio(x.esperado)} | ${limpio(JSON.stringify(x.observado))} | ${x.cumple?'SI':'NO'} | ${x.bloqueante?'SI':'NO'} |`),'',
    '## Esperado y observado por comprobación API','',
    '| Comprobación | Esperado | Observado | Estado |','|---|---|---|---|',
    ...c.comprobaciones.map(x=>`| ${x.id} | ${limpio(x.esperado)} | ${limpio(x.observado)} | ${x.estado} |`),'',
    'No hay comprobaciones UI obligatorias en esta orden. El cuerpo íntegro saneado del POST y los eventos consultados están en `resultado.json`. Los textos canónicos y hashes de discrepancias de recálculo están en `casos.TC-M06-034.comprobaciones`.', '',
    '## Evidencias y herramientas','',
    `Node ${limpio(r.herramientas.node)}; Newman ${r.herramientas.newman?.codigo??'no ejecutado'}; Cypress no aplica (0 pruebas); solicitudes ${r.total_solicitudes_api??0}.`,
    ...r.evidencias.map(x=>`- ${limpio(x)}`),'',
    '## Incidencias de producto','',
    ...(r.incidencias.length?r.incidencias.map(x=>`- ${x.id}: esperado ${limpio(x.esperado)}; obtenido ${limpio(x.obtenido)}. Evidencia ${x.evidencia}. Severidad ${x.severidad}: ${limpio(x.justificacion_severidad)}. Certeza ${x.certeza}. Equipo inicial ${x.equipo}: ${limpio(x.fundamento)} Causa raíz ${limpio(x.causa_raiz)} Acción: ${limpio(x.accion)}`):['- Ninguna discrepancia de producto acreditada.']),'',
    '## Problemas técnicos','',...(r.problemas_tecnicos.length?r.problemas_tecnicos.map(x=>`- ${limpio(x)}`):['- Ninguno registrado.']),'',
    '## Observaciones y alcance','',...r.observaciones.map(x=>`- ${limpio(x)}`),`- Lectura complementaria 7 y 219: ${limpio(JSON.stringify(r.complementario??[]))}.`,'',
    '## Cierre y rollback','',
    `DELETE del RUN: HTTP ${r.cierre?.run?.cierre_http??'no confirmado'}. Rollback verificado mediante lecturas posteriores: ${r.rollback?.verificado?'SI':'NO'}. ${limpio(r.rollback?.motivo)}`,
    `Registro ${r.oficial?'OFICIAL':'NO OFICIAL'}. QA revisa la evidencia y decide la próxima acción autorizada.`,''].join('\n');
}
