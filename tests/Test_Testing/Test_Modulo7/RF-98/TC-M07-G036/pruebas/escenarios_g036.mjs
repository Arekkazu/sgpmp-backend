// Escenarios exclusivamente locales: servidor 127.0.0.1 y salidas bajo TEMP.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {ejecutar} from '../g036.mjs';
import {simuladorG036} from './simulador_g036.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';
import {cuerpo} from '../lib/g036_core.mjs';
const lista=JSON.parse(fs.readFileSync(new URL('./escenarios_g036.json',import.meta.url))).escenarios;
const salida=path.resolve(process.env.QA_VERIFICAR_SALIDAS||'');
assert(salida.startsWith(path.resolve(os.tmpdir())+path.sep),'SALIDA_FUERA_TEMP');
fs.mkdirSync(salida,{recursive:true});
const resultados=[];
for(const escenario of lista){
  const sim=await simuladorG036(escenario);
  try{
    const dir=path.join(salida,escenario.id,sim.runId);
    const c={ensayo:true,dir,runId:sim.runId,referencia:'AUT-LOCAL-SIN-TEST',estricto:true};
    const e={QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api,SIGAB_FRONT_TEST_BASE:sim.front};
    const r=await ejecutar(c,e,fetch,{
      newman:ejecutarNewman,
      lanzarCypress:async input=>{
        assert.equal(input.versiones.ACTIVO,'2.1');assert.equal(input.versiones.DEPRECADO,'2.0');assert.equal(input.versiones.INACTIVO,'1.0');
        const headers={'X-Test-Run-Id':input.runId,'X-Sandbox-Secret':input.secret,'Content-Type':'application/json'};
        if(!escenario.frontal404){const alta=await fetch(input.api+'/integracion/contratos',{method:'POST',headers,body:JSON.stringify(cuerpo('4.2',input.anexoId,input.fecha))});assert.equal(alta.status,201,`${escenario.id}: UI POST 4.2`);}
        const acta={caso:'TC-M07-05',http_registro:escenario.frontal404?null:201,version_4_2_visible:!escenario.frontal404,pendiente_activar:!escenario.frontal404,activo_deprecar:escenario.frontal404?null:!escenario.accionIncorrecta,deprecado_sin_accion:escenario.frontal404?null:true,inactivo_sin_accion:escenario.frontal404?null:true,subcomprobaciones_sin_dato:[],captura:!escenario.frontal404,video:!escenario.frontal404,peticiones:[],hitos:{frontal_cargado:!escenario.frontal404,login_interceptado:!escenario.frontal404,pantalla_contrato:!escenario.frontal404,modal_abierto:!escenario.frontal404,registro_enviado:!escenario.frontal404},error:escenario.frontal404?'cy.visit() failed trying to load /login: 404 Not Found':escenario.accionIncorrecta?'Expected ACTIVO to offer Retirar con plazo':null,asercion_producto:escenario.accionIncorrecta?'activo_deprecar':null};
        fs.mkdirSync(path.join(input.dir,'screenshots'),{recursive:true});fs.mkdirSync(path.join(input.dir,'videos'),{recursive:true});
        fs.writeFileSync(path.join(input.dir,'G036-UI-05.json'),JSON.stringify(acta));fs.writeFileSync(path.join(input.dir,'G036-cypress.json'),JSON.stringify({totalTests:1,simulacion:true}));fs.writeFileSync(path.join(input.dir,'G036-cypress-salida.log'),'SIMULACION_LOCAL_EN_PROCESO');fs.writeFileSync(path.join(input.dir,'screenshots','simulada.png'),'SIMULACION_LOCAL');fs.writeFileSync(path.join(input.dir,'videos','g036.cy.js.mp4'),'SIMULACION_LOCAL');
        const codigo=escenario.frontal404?2:escenario.accionIncorrecta?1:0;
        return{status:codigo,error:null,stdout:JSON.stringify({codigo,totalTests:1,acta})};
      }
    });
    assert(fs.existsSync(path.join(dir,'resultado.json')),`${escenario.id}: resultado ausente`);
    assert(fs.existsSync(path.join(dir,'TC-M07-G036_resultado.md')),`${escenario.id}: informe ausente`);
    assert.equal(r.cierre.http,200,`${escenario.id}: DELETE ausente`);
    assert.equal(r.cierre.rollback.verificado,!escenario.rollbackFallido,`${escenario.id}: rollback`);
    if(escenario.sinPermisos||escenario.sinAprobado){const faltan=r.preflight_datos.filter(x=>x.bloqueante&&!x.cumple).map(x=>x.requisito);assert(faltan.length>0);assert(faltan.some(x=>escenario.sinAprobado?x==='ANEXO_APROBADO':x.startsWith('PERMISO_')));}
    else assert(r.preflight_datos.every(x=>x.cumple||!x.bloqueante));
    assert.deepEqual(['01','02','03','04','05'].map(k=>r.veredictos[k]),escenario.esperado,`${escenario.id}: veredictos`);
    assert.equal(r.oficial,escenario.oficial,`${escenario.id}: oficial`);
    if(escenario.problemaTecnico){assert(r.problemas_tecnicos.some(x=>x.includes('cy.visit()')),`${escenario.id}: problema técnico ausente`);assert.equal(r.incidencias.filter(x=>x.caso==='TC-M07-05').length,0);assert.equal(r.pruebas['05_ui'],'NO_CONCLUYENTE');assert.equal(r.pruebas['05_api'],'NO_CONCLUYENTE');}
    else assert.deepEqual(r.problemas_tecnicos,[],`${escenario.id}: problemas técnicos`);
    if(escenario.accionIncorrecta){assert(r.incidencias.some(x=>x.caso==='TC-M07-05'&&x.regla==='UI_ACCIONES_INCORRECTAS'&&x.severidad==='MEDIA'));}
    if(escenario.sinAprobado||escenario.sinPermisos){assert.equal(sim.peticiones.filter(x=>x.metodo==='POST'&&x.ruta.startsWith('/integracion/')).length,0,`${escenario.id}: escrituras`);assert(sim.peticiones.some(x=>x.metodo==='DELETE'),`${escenario.id}: DELETE`);}
    if(escenario.fallar01){assert.equal(r.newman?.fallos,0,`${escenario.id}: Newman`);assert.equal(r.newman?.codigo,0,`${escenario.id}: Newman código`);}
    assert(r.solicitudes_total<=80,`${escenario.id}: límite de solicitudes`);
    resultados.push({id:escenario.id,dir,oficial:r.oficial,veredictos:r.veredictos,rollback:r.cierre.rollback.verificado,problemas_tecnicos:r.problemas_tecnicos,peticiones:r.solicitudes_total});
    process.stderr.write('OK escenario_'+escenario.id+'\n');
  }finally{await sim.cerrar();}
}
process.stdout.write(JSON.stringify(resultados));
