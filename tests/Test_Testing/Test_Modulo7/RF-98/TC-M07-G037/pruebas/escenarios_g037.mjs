// Escenarios integrales contra loopback; los RUN simulados viven solo en TEMP.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {ejecutar} from '../g037.mjs';
import {simuladorG037} from './simulador_g037.mjs';
const lista=JSON.parse(fs.readFileSync(new URL('./escenarios_g037.json',import.meta.url))).escenarios;
export async function ejecutarEscenarios(salida){
  const raiz=path.resolve(salida);
  assert(raiz.startsWith(path.resolve(os.tmpdir())+path.sep),'SALIDA_FUERA_TEMP');
  fs.mkdirSync(raiz,{recursive:true});const resultados=[];
  for(const x of lista){
    const sim=await simuladorG037(x);
    try{
      const dir=path.join(raiz,x.id,sim.runId);
      assert(dir.startsWith(path.resolve(os.tmpdir())+path.sep));
      if(fs.existsSync(dir))fs.rmSync(dir,{recursive:true,force:true});
      fs.mkdirSync(dir,{recursive:true});
      const c={ensayo:true,dir,runId:sim.runId,version:3,intento:1,referencia:'AUT-LOCAL-SIN-TEST',estricto:true};
      const e={QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api};
      const r=await ejecutar(c,e,fetch,{newman:async()=>({codigo:0,fallos:0,solicitudes:2,reportes:true,simulacion_local:true})});
      assert.deepEqual(['06','07','08'].map(k=>r.veredictos[k]),x.esperado,x.id);
      assert.equal(r.oficial,x.oficial,x.id+' oficial');
      assert.equal(r.cierre.run.cierre_http,x.loginInvalido?null:x.deleteHttp??200,x.id+' cierre');
      assert.equal(r.cierre.rollback.verificado,!x.rollbackFallido&&!x.loginInvalido&&!x.sinPermisos&&!x.deleteHttp,x.id+' rollback');
      assert(r.solicitudes_total<=60,x.id+' presupuesto');
      if(x.sinPermisos){assert.equal(sim.peticiones.filter(p=>p.metodo==='POST'&&p.ruta.startsWith('/integracion/')).length,0);assert.equal(r.newman,null);}
      if(x.sinPermisoCrear)assert.equal(sim.peticiones.filter(p=>p.metodo==='POST'&&p.ruta==='/integracion/contratos').length,0);
      if(x.sinPermisoDeprecar)assert.equal(sim.peticiones.filter(p=>p.metodo==='POST'&&p.ruta.includes('/deprecar')).length,0);
      if(x.sinPermisoU)assert.equal(r.comprobaciones.find(v=>v.id==='m09_configurable').estado,'NO_CONCLUYENTE');
      if(x.graciaFija)assert(r.incidencias.some(v=>v.caso==='TC-M07-07'&&v.severidad==='MEDIA'));
      if(x.m09SinRuta)assert(r.incidencias.some(v=>v.regla==='M09_NO_CONFIGURABLE'&&v.severidad==='MEDIA'));
      if(x.fechasMal)assert(r.incidencias.some(v=>v.regla==='INACTIVACION_INCORRECTA'));
      if(x.formatoAceptado)assert(r.incidencias.some(v=>v.regla==='FORMATO_ACEPTADO'));
      if(x.patchInvalidoCodigoGenerico){
        assert.equal(r.comprobaciones.find(v=>v.id==='patch_invalido').estado,'APROBADO');
        assert(r.observaciones.some(v=>v.includes('PARAMETRO_MLOPS_INVALIDO')&&v.includes('field=null')));
        assert(!r.incidencias.some(v=>v.caso==='TC-M07-07'));
        assert(fs.readFileSync(path.join(dir,'TC-M07-G037_reevaluacion_V3.md'),'utf8').includes('PARAMETRO_MLOPS_INVALIDO'));
      }
      if(x.patchInvalidoAceptado)assert(r.incidencias.some(v=>v.regla==='PATCH_INVALIDO_SIN_RECHAZO'));
      if(x.patchInvalidoCambiaGracia)assert(r.incidencias.some(v=>v.regla==='GRACIA_MODIFICADA_POR_PATCH_INVALIDO'));
      if(x.patchInvalido422){assert.equal(r.comprobaciones.find(v=>v.id==='patch_invalido').estado,'NO_CONCLUYENTE');assert(!r.incidencias.some(v=>v.regla.startsWith('PATCH_INVALIDO_')));}
      if(x.nombreUsuario){
        for(const archivo of ['resultado.json','TC-M07-G037_reevaluacion_V3.md'])assert(!fs.readFileSync(path.join(dir,archivo),'utf8').includes(x.nombreUsuario));
      }
      const linea=`OK escenario_${x.id}: 06=${r.veredictos['06']} 07=${r.veredictos['07']} 08=${r.veredictos['08']} oficial=${r.oficial}`;
      resultados.push({id:x.id,dir,oficial:r.oficial,veredictos:r.veredictos,solicitudes:r.solicitudes_total,linea});
      process.stdout.write(linea+'\n');
    }finally{await sim.cerrar();}
  }
  fs.writeFileSync(path.join(raiz,'resumen_escenarios.json'),JSON.stringify(resultados,null,2));
  return resultados;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  await ejecutarEscenarios(process.env.QA_VERIFICAR_SALIDAS||path.join(os.tmpdir(),'g037-escenarios-local'));
}
