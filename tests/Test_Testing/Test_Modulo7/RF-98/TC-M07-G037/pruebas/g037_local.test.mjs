import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {CAPACIDADES,contexto,preflight,principal,sanitize,verificarRollback,mismoInstante} from '../g037.mjs';
import {simuladorG037} from './simulador_g037.mjs';
import {comprobarPaso6,comprobarPaso10} from './verificar.mjs';

test('contrato del lanzador y ausencia de UI',()=>{
  assert.equal(CAPACIDADES.contrato,'sigab-qa-ejecutor/1');assert.equal(CAPACIDADES.grupo,'G037');
  assert.deepEqual(CAPACIDADES.casos,['TC-M07-06','TC-M07-07','TC-M07-08']);
  assert.deepEqual(CAPACIDADES.operaciones,['evaluar','reintentar']);assert.deepEqual(CAPACIDADES.versiones,{min:1,max:1});
  assert(CAPACIDADES.limite.solicitudes_totales<=60);assert(CAPACIDADES.limite.duracion_segundos<=600);
  for(const caso of CAPACIDADES.casos){assert(CAPACIDADES.comprobaciones_obligatorias[caso].API.length);assert(!('UI' in CAPACIDADES.comprobaciones_obligatorias[caso]));}
});
test('contexto idéntico al lanzador y preflight de carpeta temporal',()=>{
  const raiz=fs.mkdtempSync(path.join(os.tmpdir(),'g037-contexto-'));
  try{const runId='RUN-G037-V1-20261117-000000',dir=path.join(raiz,runId);fs.mkdirSync(dir);const archivo=path.join(dir,'contexto_operacion.json');fs.writeFileSync(archivo,JSON.stringify({grupo:'G037',run_id:runId,version:1,intento:1,operacion:'EVALUAR',referencia:'AUT-LOCAL-SIN-TEST',casos:CAPACIDADES.casos}));const args=['--operacion','evaluar','--version','1','--intento','1','--run-id',runId,'--autorizacion','AUT-LOCAL-SIN-TEST','--contexto',archivo];const c=contexto(args,true);assert.equal(c.dir,dir);const p=preflight(c,{QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'a@local.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:'http://127.0.0.1:12345/api-sgpmp-test'});assert.equal(p.ok,true);}finally{fs.rmSync(raiz,{recursive:true,force:true});}
});
test('CLI en proceso escribe preflight, resultado e informe en RUN temporal precreado',async()=>{
  const raiz=fs.mkdtempSync(path.join(os.tmpdir(),'g037-cli-')),sim=await simuladorG037();
  try{const dir=path.join(raiz,sim.runId);fs.mkdirSync(dir);const contextoArchivo=path.join(dir,'contexto_operacion.json');fs.writeFileSync(contextoArchivo,JSON.stringify({grupo:'G037',run_id:sim.runId,version:1,intento:1,operacion:'EVALUAR',referencia:'AUT-LOCAL-SIN-TEST',casos:CAPACIDADES.casos,alcance_reevaluacion:null,version_anterior:null}));const args=['--operacion','evaluar','--version','1','--intento','1','--run-id',sim.runId,'--autorizacion','AUT-LOCAL-SIN-TEST','--contexto',contextoArchivo];const env={QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api};const z=await principal(args,{proceso:env,archivo:path.join(raiz,'sin-env'),prueba:true,dobles:{newman:async()=>({codigo:0,fallos:0,solicitudes:2,reportes:true})}});assert.equal(z.codigo,0);for(const f of ['preflight.json','resultado.json','TC-M07-G037_resultado.md'])assert(fs.existsSync(path.join(dir,f)));assert.equal(z.resultado.oficial,true);}finally{await sim.cerrar();fs.rmSync(raiz,{recursive:true,force:true});}
});
test('sanitización y rollback por id y estado',()=>{
  const s=JSON.stringify(sanitize({contrasena:'clave-real',correo:'a@b.com',client_secret:'secreto-real',token:'eyJ.eyJ.firma',mensaje:'a@b.com'}));for(const secreto of ['clave-real','a@b.com','secreto-real','eyJ.eyJ.firma'])assert(!s.includes(secreto));
  const a=[{id_version_contrato_aaef:1,estado:'ACTIVO'}],b=[{id_version_contrato_aaef:1,estado:'ACTIVO'}];assert(verificarRollback(a,b));assert(!verificarRollback(a,[{id_version_contrato_aaef:1,estado:'DEPRECADO'}]));
});
test('lectura M09 enmascara nombres en todos los archivos del RUN local',async()=>{
  const marcador='SENTINELA_LOCAL_NOMBRE';
  const raiz=fs.mkdtempSync(path.join(os.tmpdir(),'g037-nombre-')),sim=await simuladorG037({nombreUsuario:marcador});
  try{
    const dir=path.join(raiz,sim.runId);fs.mkdirSync(dir);
    await (await import('../g037.mjs')).ejecutar({ensayo:true,dir,runId:sim.runId,version:1,intento:1,referencia:'LOCAL',estricto:true},{QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api},fetch,{newman:async()=>({codigo:0,fallos:0,solicitudes:2,reportes:true})});
    const collection=JSON.parse(fs.readFileSync(new URL('../G037.postman_collection.json',import.meta.url),'utf8'));
    const reportes=await (await import('./newman_hijo.mjs')).ejecutar({salida:path.join(dir,'newman'),coleccion:collection,environment:{values:[['base_url',sim.api],['run_id',sim.runId],['sandbox_secret','LOCAL'],['admin_token','LOCAL']].map(([key,value])=>({key,value,enabled:true}))}});
    assert.equal(reportes.codigo,0);assert.equal(reportes.reportes,true);
    const revisar=carpeta=>{for(const entrada of fs.readdirSync(carpeta)){const archivo=path.join(carpeta,entrada);if(fs.statSync(archivo).isDirectory())revisar(archivo);else assert(!fs.readFileSync(archivo,'utf8').includes(marcador),entrada);}};revisar(dir);
    const resultado=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'),'utf8'));
    assert.equal(resultado.solicitudes.find(x=>x.ruta==='/configuracion/parametros').cuerpo_lectura.nombre_usuario,'[NOMBRE]');
    for(const campo of ['nombre','nombres','apellidos','nombre_completo'])assert.equal(sanitize({[campo]:marcador})[campo],'[NOMBRE]');
  }finally{await sim.cerrar();fs.rmSync(raiz,{recursive:true,force:true});}
});
test('fechas de formatos distintos representan el mismo instante',()=>{
  assert(mismoInstante('2026-12-18T12:00:00.000Z','2026-12-18T07:00:00-05:00'));
  assert(!mismoInstante('2026-12-18T12:00:00Z','2026-12-17T12:00:00Z'));
});
test('Newman se ejecuta con RUN abierto aun sin permiso M09',async()=>{
  const raiz=fs.mkdtempSync(path.join(os.tmpdir(),'g037-newman-obligatorio-')),sim=await simuladorG037({sinPermisoM09:true});
  try{const dir=path.join(raiz,sim.runId);fs.mkdirSync(dir);let llamadas=0,items=[];const r=await (await import('../g037.mjs')).ejecutar({ensayo:true,dir,runId:sim.runId,version:1,intento:1,referencia:'LOCAL',estricto:true},{QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api},fetch,{newman:async input=>{llamadas++;items=input.coleccion.item;return{codigo:0,fallos:0,solicitudes:1,reportes:true};}});assert.equal(llamadas,1);assert.equal(items.length,1);assert.equal(r.newman.solicitudes,1);assert.equal(r.oficial,false);assert(r.observaciones.some(v=>v.includes('omitido')));}finally{await sim.cerrar();fs.rmSync(raiz,{recursive:true,force:true});}
});
test('pasos 6 y 10 importados sobre todos los escenarios locales',()=>{
  const destino=process.env.QA_VERIFICAR_SALIDAS;if(!destino)return;
  const esc=JSON.parse(fs.readFileSync(new URL('./escenarios_g037.json',import.meta.url))).escenarios;
  for(const x of esc){const dir=path.join(destino,x.id,'RUN-G037-V1-20261117-000000');comprobarPaso6(dir,x,path.basename(dir));comprobarPaso10(dir,x.oficial?'OFICIAL':'TECNICO');}
});
