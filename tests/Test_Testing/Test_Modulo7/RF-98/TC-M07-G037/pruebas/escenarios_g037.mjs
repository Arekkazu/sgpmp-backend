// Escenarios en proceso con servidor local; salidas exclusivamente bajo TEMP.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {ejecutar} from '../g037.mjs';
import {simuladorG037} from './simulador_g037.mjs';
const lista=JSON.parse(fs.readFileSync(new URL('./escenarios_g037.json',import.meta.url))).escenarios;
const salida=path.resolve(process.env.QA_VERIFICAR_SALIDAS||'');
assert(salida.startsWith(path.resolve(os.tmpdir())+path.sep),'SALIDA_FUERA_TEMP');
fs.mkdirSync(salida,{recursive:true});
const resultados=[];
for(const x of lista){
  const sim=await simuladorG037(x);
  try{
    const dir=path.resolve(salida,x.id,sim.runId);
    assert(dir.startsWith(path.resolve(os.tmpdir())+path.sep),'RUN_LOCAL_FUERA_TEMP');
    if(fs.existsSync(dir))fs.rmSync(dir,{recursive:true,force:true});
    fs.mkdirSync(dir,{recursive:true});
    const c={ensayo:true,dir,runId:sim.runId,version:1,intento:1,referencia:'AUT-LOCAL-SIN-TEST',estricto:true};
    const e={QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api};
    const r=await ejecutar(c,e,fetch,{newman:async()=>({codigo:0,fallos:0,solicitudes:2,reportes:true,simulacion_local:true})});
    assert.deepEqual(['06','07','08'].map(k=>r.veredictos[k]),x.esperado,x.id);
    assert.equal(r.oficial,x.oficial,x.id+' oficial');
    assert.equal(r.cierre.run.cierre_http,200,x.id+' DELETE');
    assert.equal(r.cierre.rollback.verificado,!x.rollbackFallido,x.id+' rollback');
    assert(r.solicitudes_total<=60,x.id+' presupuesto');
    if(x.sinPermisos){assert.equal(sim.peticiones.filter(p=>p.metodo==='POST'&&p.ruta.startsWith('/integracion/')).length,0);assert(sim.peticiones.some(p=>p.metodo==='DELETE'));}
    assert(r.newman&&r.newman.codigo===0,x.id+' Newman obligatorio con RUN abierto');
    if(x.sinPermisoM09)assert.equal(r.comprobaciones.find(v=>v.id==='m09_configurable').estado,'NO_CONCLUYENTE');
    if(x.deprecar29Aceptado){assert.deepEqual(r.pruebas['TC-M07-08'].slice(1),['NO_CONCLUYENTE','NO_CONCLUYENTE']);assert(r.observaciones.some(v=>v.includes('no hay otra versión ACTIVO')));assert.deepEqual(r.problemas_tecnicos,[]);}
    if(x.formatoAceptado)assert(r.incidencias.some(v=>v.regla==='FORMATO_ACEPTADO'&&v.severidad==='ALTA'));
    if(x.gracia29Aceptada)assert(r.incidencias.some(v=>v.regla==='GRACIA_29_ACEPTADA'&&v.severidad==='ALTA'));
    if(x.deprecar29Aceptado)assert(r.incidencias.some(v=>v.regla==='DEPRECAR_29_ACEPTADO'&&v.severidad==='ALTA'));
    if(x.inactivacionIncorrecta)assert(r.incidencias.some(v=>v.regla==='INACTIVACION_INCORRECTA'&&v.severidad==='MEDIA'));
    const report=path.join(dir,'resultado.json');assert(fs.existsSync(report));
    resultados.push({id:x.id,dir,oficial:r.oficial,veredictos:r.veredictos,solicitudes:r.solicitudes_total});
    process.stdout.write(`OK escenario_${x.id}: 06=${r.veredictos['06']} 07=${r.veredictos['07']} 08=${r.veredictos['08']} oficial=${r.oficial} solicitudes=${r.solicitudes_total}/60\n`);
  }finally{await sim.cerrar();}
}
fs.writeFileSync(path.join(salida,'resumen_escenarios.json'),JSON.stringify(resultados,null,2));
