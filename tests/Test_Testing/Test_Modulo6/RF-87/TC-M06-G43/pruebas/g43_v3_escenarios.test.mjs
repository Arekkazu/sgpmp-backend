import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {ejecutar,CAPACIDADES} from '../g43.mjs';
import {fixture,hijo} from './g43_v2_escenarios.test.mjs';

const RUN='RUN-G43-V3-20261113-000000';
for(const [modo,estado024,via] of [
  ['v3_respuesta','APROBADO','respuesta'],
  ['v3_auditoria','APROBADO','auditoria'],
  ['v3_calculo','APROBADO','calculo'],
  ['v3_lineas_026','APROBADO','calculo'],
  ['v3_etiqueta_generica','APROBADO','calculo'],
  ['v3_precio_nuevo','RECHAZADO','calculo']
]){
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'g43-v3-sim-'));
  const dir=path.join(temp,RUN),sim=fixture(modo,RUN);fs.mkdirSync(dir);
  try{
    await new Promise(ok=>sim.server.listen(0,'127.0.0.1',ok));
    const api=`http://127.0.0.1:${sim.server.address().port}/api`;
    const r=await ejecutar({dir,runId:RUN,version:3,ref:'LOCAL',operacion:'REEVALUAR'},{QA_SANDBOX_SECRET:'LOCAL',QA_CONTADOR_EMAIL:'local@example.invalid',QA_CONTADOR_PASSWORD:'LOCAL'},{ensayo:true,api,hijo:hijo(modo)});
    assert.equal(r.casos['TC-M06-024'].estado,estado024,`${modo}: ${JSON.stringify({problemas:r.problemas_tecnicos,casos:r.casos,clasificacion:r.clasificacion_fallo})}`);
    assert.equal(r.casos['TC-M06-026'].estado,'APROBADO',modo);
    assert.equal(r.diagnostico.estimacion_1644.vias[via],true,modo);
    if(modo==='v3_lineas_026'){
      assert.deepEqual(r.diagnostico.prevalidacion_cierre_026.lineas_sin_trazabilidad.map(x=>x.id_linea),[3726]);
      assert.equal(r.diagnostico.prevalidacion_cierre_026.autorizar_exclusiones,true);
      assert(sim.escrituras.some(x=>x.ruta==='/finanzas/periodos/267/cierre'&&x.body.activos_estimados?.includes(1644)&&x.body.autorizar_exclusiones===true));
    }
    if(modo==='v3_etiqueta_generica'){
      assert.equal(r.casos['TC-M06-027'].estado,'APROBADO');
      assert(r.observaciones.some(x=>x.includes('OBS-G43-UI-02')&&x.includes('auditoria_m03')));
    }
    assert(r.diagnostico.estimacion_1644.evidencia_vias[via],modo);
    assert.equal(r.precios[0].congelado_pausa_segundo.id_precio_mercado,18,modo);
    assert.equal(r.seguimiento['INC-M06-G43-05'],estado024==='APROBADO'?'CORREGIDA':'REPRODUCIDA',`${modo}: ${JSON.stringify({caso:r.casos['TC-M06-024'],problemas:r.problemas_tecnicos,seguimiento:r.seguimiento})}`);
    assert.equal(r.seguimiento['INC-M06-G43-03'],'CORREGIDA',`${modo}: ${JSON.stringify({caso:r.casos['TC-M06-026'],problemas:r.problemas_tecnicos})}`);
    assert(r.solicitudes.some(x=>x.http===400&&Array.isArray(x.cuerpo_saneado?.activos_estimados)),`${modo}: cuerpo saneado de escritura 400`);
    assert.equal(r.oficial,true,`${modo}: ${JSON.stringify(r.condiciones_oficialidad)} ${r.problemas_tecnicos.join(',')}`);
    const informe=fs.readFileSync(path.join(dir,'TC-M06-G43_reevaluacion_V3.md'),'utf8');
    assert(informe.startsWith(`# TC-M06-G43 — reevaluación V3 oficial - ${estado024==='APROBADO'?'APROBADO':'RECHAZADO'}`));
    assert.equal(fs.readdirSync(dir).filter(x=>x.endsWith('.md')).length,1);
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'))).version,3);
    if(modo==='v3_respuesta'&&process.env.QA_VERIFICAR_EJEMPLO){
      const destino=path.resolve(process.env.QA_VERIFICAR_EJEMPLO);
      assert(destino.startsWith(path.resolve(os.tmpdir())+path.sep),'EJEMPLO_FUERA_TEMPORAL');
      fs.mkdirSync(destino,{recursive:true});fs.cpSync(dir,path.join(destino,RUN),{recursive:true,force:true});
      fs.writeFileSync(path.join(destino,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));
    }
    console.log(`OK ${modo}: 024=${estado024} 026=${via} V3 oficial`);
  }finally{
    await new Promise(ok=>sim.server.close(ok));
    assert(path.resolve(temp).startsWith(path.resolve(os.tmpdir())+path.sep));fs.rmSync(temp,{recursive:true,force:true});
  }
}
