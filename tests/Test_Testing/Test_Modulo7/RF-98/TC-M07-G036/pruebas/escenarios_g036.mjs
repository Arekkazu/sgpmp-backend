// Escenarios locales, únicamente 127.0.0.1 y salidas de TEMP.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {ejecutar} from '../g036.mjs';
import {simuladorG036} from './simulador_g036.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';
import {cuerpo} from '../lib/g036_core.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const lista=JSON.parse(fs.readFileSync(path.join(dir,'escenarios_g036.json'),'utf8')).escenarios;
export async function ejecutarEscenarios(salida){
  const destino=path.resolve(salida);
  assert(destino.startsWith(path.resolve(os.tmpdir())+path.sep),'SALIDA_FUERA_TEMP');
  fs.mkdirSync(destino,{recursive:true});
  const resultados=[];
  for(const escenario of lista){
    const sim=await simuladorG036(escenario);
    try{
      if(escenario.id==='h_concurrencia'){
        const headers={'X-Test-Run-Id':sim.runId,'X-Sandbox-Secret':'LOCAL'};
        const respuestas=await Promise.all([fetch(sim.api+'/integracion/contratos',{headers}),fetch(sim.api+'/integracion/anexos',{headers})]);
        assert(respuestas.some(x=>x.status===409),'doble rechaza concurrencia del mismo run');
        assert(sim.peticiones.some(x=>x.concurrente),'concurrencia registrada');
      }
      const runDir=path.join(destino,escenario.id,sim.runId);fs.mkdirSync(runDir,{recursive:true});
      const c={ensayo:true,dir:runDir,runId:sim.runId,version:2,referencia:'AUT-LOCAL-SIN-TEST',estricto:true};
      const e={QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api,SIGAB_FRONT_TEST_BASE:sim.front};
      const r=await ejecutar(c,e,fetch,{
        newman:ejecutarNewman,
        cypress:async input=>{
          const headers={'X-Test-Run-Id':input.runId,'X-Sandbox-Secret':input.secret,'Content-Type':'application/json'};
          if(!escenario.frontal404){
            const alta=await fetch(input.api+'/integracion/contratos',{method:'POST',headers,body:JSON.stringify(cuerpo(input.versionLibre,input.anexoId,input.fecha))});
            assert.equal(alta.status,201,'UI POST local');
          }
          const ok=!escenario.frontal404;
          const lecturaHeaders=escenario.id==='g_lectura_sin_sandbox'?{}:headers;
          const listado=ok?await(await fetch(input.api+'/integracion/contratos',{headers:lecturaHeaders})).json():[];
          const visible=listado.some(x=>x.contrato_version===input.versionLibre);
          const motivo=listado.find(x=>x.contrato_version===input.versionLibre)?.motivo_no_activable;
          const habilitado=ok&&(escenario.activarHabilitado||!motivo);
          const pendiente=ok&&(motivo?!habilitado:habilitado);
          const acta={caso:'TC-M07-05',http_registro:ok?201:null,version_visible:visible,pendiente_activar:pendiente,activar_visible:ok,activar_deshabilitado:ok?!habilitado:null,motivo_servidor_visible:ok&&!!motivo&&!habilitado,activo_deprecar:ok?!escenario.accionIncorrecta:null,deprecado_sin_accion:ok&&!escenario.menosVigentes?true:null,inactivo_sin_accion:ok?true:null,captura:ok,peticiones:[],hitos:{frontal_cargado:ok,login_interceptado:ok,refresh_interceptado:ok,pantalla_contrato:ok,modal_abierto:ok,registro_enviado:ok},error:escenario.frontal404?'cy.visit() failed: 404':null,asercion_producto:escenario.id==='g_lectura_sin_sandbox'?'version_visible':escenario.activarHabilitado?'pendiente_activar':escenario.accionIncorrecta?'activo_deprecar':null};
          fs.mkdirSync(path.join(input.dir,'screenshots'),{recursive:true});
          fs.writeFileSync(path.join(input.dir,'G036-UI-05.json'),JSON.stringify(acta));
          fs.writeFileSync(path.join(input.dir,'G036-cypress.json'),JSON.stringify({totalTests:1,simulacion_local:true}));
          fs.writeFileSync(path.join(input.dir,'G036-cypress-salida.log'),'SIMULACION_LOCAL');
          if(ok)fs.writeFileSync(path.join(input.dir,'screenshots','simulada.png'),Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==','base64'));
          return{codigo:escenario.frontal404?2:escenario.activarHabilitado||escenario.accionIncorrecta||!visible?1:0,totalTests:1,acta};
        }
      });
      assert.deepEqual(['01','02','03','04','05'].map(k=>r.veredictos[k]),escenario.esperado,escenario.id);
      assert.equal(r.oficial,escenario.oficial,escenario.id);
      assert.equal(r.cierre.rollback.verificado,!escenario.rollbackFallido&&!(escenario.loginInvalido),escenario.id);
      if(escenario.sinAprobado)assert(sim.peticiones.some(x=>x.metodo==='DELETE'),'DELETE preflight');
      if(escenario.loginInvalido)assert.equal(r.consume_version,false);
      if(escenario.sinBorrador)assert(r.solicitudes.some(x=>x.metodo==='POST'&&x.ruta==='/integracion/anexos'&&x.http===201),'BORRADOR creado dentro del RUN local');
      if(escenario.menosVigentes){assert.equal(r.preflight_datos.find(x=>x.requisito==='CUPO_VIGENTES_OBSERVADO')?.observado,1);assert.deepEqual(['01','02','03','04'].map(k=>r.veredictos[k]),['APROBADO','APROBADO','APROBADO','APROBADO']);}
      assert(fs.existsSync(path.join(runDir,'resultado.json')));
      assert(fs.existsSync(path.join(runDir,'TC-M07-G036_reevaluacion_V2.md')));
      resultados.push({id:escenario.id,dir:runDir,veredictos:r.veredictos,oficial:r.oficial,rollback:r.cierre.rollback.verificado});
    }finally{await sim.cerrar();}
  }
  fs.writeFileSync(path.join(destino,'resumen_escenarios.json'),JSON.stringify(resultados,null,2));
  return resultados;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const salida=process.env.QA_VERIFICAR_SALIDAS||path.join(os.tmpdir(),'g036-escenarios-locales');
  const r=await ejecutarEscenarios(salida);process.stdout.write(JSON.stringify(r));
}

