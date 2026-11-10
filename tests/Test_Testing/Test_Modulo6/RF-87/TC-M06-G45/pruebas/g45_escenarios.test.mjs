import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {ejecutar} from '../g45.mjs';
import {simuladorG45} from './simulador_g45.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';

const base=path.dirname(fileURLToPath(import.meta.url));
const config=JSON.parse(fs.readFileSync(path.join(base,'escenarios_g45.json'),'utf8'));
const salidas=process.env.QA_VERIFICAR_SALIDAS??fs.mkdtempSync(path.join(os.tmpdir(),'g45-escenarios-'));
fs.mkdirSync(salidas,{recursive:true});
let total=0;
for(const modo of config.escenarios)for(const variante of config.variantes){
  const nombre=`${modo}_${variante}`;
  const dir=path.join(salidas,nombre,`RUN-G45-V1-20261110-000000`);
  fs.mkdirSync(dir,{recursive:true});
  const sim=await simuladorG45(modo,variante==='campos_inyectados');
  try{
    const c={dir,runId:path.basename(dir),version:1,ref:'LOCAL_SIMULADO'};
    const hijo=async(_script,input)=>{const data=await ejecutarNewman(input);return{code:data.codigo||data.fallos?2:0,data};};
    const r=await ejecutar(c,{QA_SANDBOX_SECRET:'LOCAL',QA_CONTADOR_EMAIL:'local@example.invalid',QA_CONTADOR_PASSWORD:'LOCAL'},{ensayo:true,api:sim.url,hijo});
    assert(!/identificador|numero_id_tributaria|razon_social/i.test(JSON.stringify({preflight_datos:r.preflight_datos,bases:r.bases})),nombre);
    const s=k=>r.casos[`TC-M06-${k}`].estado;
    const writes=sim.peticiones.filter(x=>x.metodo==='POST'&&x.ruta!=='/sesiones/');
    assert.equal(sim.peticiones.filter(x=>x.ruta==='/sesiones/').length,1,nombre);
    assert.equal(sim.peticiones.filter(x=>x.metodo==='DELETE').length,1,nombre);
    if(['7_abierto','8_sin_trazabilidad','949_sin_reconocimiento','944_otro_periodo'].includes(modo)){
      assert.deepEqual([s('031'),s('032'),s('033')],['NO_CONCLUYENTE','NO_CONCLUYENTE','NO_CONCLUYENTE'],nombre);
      assert.equal(writes.length,0,nombre);
      assert.equal(r.oficial,false,nombre);
      assert(r.preflight_datos.some(x=>!x.cumple&&x.requisito.includes(modo==='7_abierto'?'periodo_7':modo==='8_sin_trazabilidad'?'linea_sin_trazabilidad':modo==='944_otro_periodo'?'944_reconocimiento':'949')),nombre);
    }else{
      assert.equal(writes.length,3,nombre);
      assert.deepEqual(writes.map(x=>x.ruta),['/finanzas/periodos/8/cierre','/finanzas/costos','/finanzas/reconocimientos/949/reversion'],nombre);
      assert(!writes[0].body.autorizar_exclusiones,nombre);
      if(modo==='conforme')assert.deepEqual([s('031'),s('032'),s('033')],['APROBADO','APROBADO','APROBADO'],nombre);
      if(modo==='codigo_actual'){
        assert.deepEqual([s('031'),s('032'),s('033')],['RECHAZADO','RECHAZADO','RECHAZADO'],nombre);
        assert.equal(r.casos['TC-M06-032'].comprobaciones.find(x=>x.id==='032_eliminar_reconocimiento').estado,'APROBADO');
        assert.equal(r.casos['TC-M06-032'].comprobaciones.find(x=>x.id==='032_integridad').estado,'APROBADO');
      }
      if(modo==='cierre_200')assert.equal(s('031'),'NO_CONCLUYENTE');
      if(modo==='costo_201'){
        assert.equal(s('032'),'RECHAZADO');
        assert.equal(r.incidencias.find(x=>x.id==='INC-M06-G45-02').severidad,'ALTA');
      }
      if(['costo_422_validacion','reversion_400_motivo'].includes(modo)){
        assert.equal(s('032'),'NO_CONCLUYENTE',nombre);
        assert.equal(r.incidencias.some(x=>x.id==='INC-M06-G45-02'),false,nombre);
      }
      if(modo==='openapi_404')assert.deepEqual([s('031'),s('032'),s('033')],['RECHAZADO','APROBADO','RECHAZADO']);
      if(modo==='delete_fallido')assert.equal(r.oficial,false);
      if(['conforme','codigo_actual','openapi_404','costo_201'].includes(modo))assert.equal(r.oficial,true,`${nombre}: ${r.problemas_tecnicos.join('; ')}`);
    }
    assert(fs.existsSync(path.join(dir,'resultado.json')),nombre);
    assert(fs.existsSync(path.join(dir,'TC-M06-G45_resultado.md')),nombre);
    assert.equal(fs.readdirSync(dir).filter(x=>x.endsWith('.md')).length,1,nombre);
    if(process.env.QA_VERIFICAR_SALIDAS)for(const entrada of fs.readdirSync(dir))fs.cpSync(path.join(dir,entrada),path.join(salidas,nombre,entrada),{recursive:true});
    total++;
  }finally{await sim.cerrar();}
}
assert.equal(total,config.integrales);
console.log(JSON.stringify({escenarios:total,estado:'OK',salidas}));
