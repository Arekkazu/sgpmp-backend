import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {randomInt} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {contexto,preflight,leerEnv,conPeticiones,fetchEnContexto,CAPACIDADES,verificarPermisos,
  principal,contrastarRespuesta,comprobar} from '../g39.mjs';
import {clasificarRegistro} from './registro_qa.mjs';
import {CONTRATO,CASOS,mock,validarMock,validarActor,resolverMatriz,truncar2,igual} from '../lib/g39_core.mjs';
import {directorioNewman,sanearReporte} from './newman_hijo.mjs';

const GRUPO=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const args=(runId,archivo)=>['--operacion','evaluar','--version','1','--intento','1','--run-id',runId,
  '--autorizacion','AUT-LOCAL','--contexto',archivo];
const escribirContexto=(archivo,runId)=>fs.writeFileSync(archivo,JSON.stringify({grupo:'G39',run_id:runId,
  version:1,intento:1,operacion:'EVALUAR',referencia:'AUT-LOCAL',casos:CASOS}));

test('lector de entorno exige autorización antes de abrir archivo',()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g39-env-'));
  const file=path.join(tmp,'.env.qa');fs.writeFileSync(file,'QA_SANDBOX_SECRET=archivo\n');
  try{
    assert.equal(leerEnv({QA_AUTORIZADO:'NO'},file).QA_SANDBOX_SECRET,undefined);
    assert.equal(leerEnv({QA_AUTORIZADO:'SI'},file).QA_SANDBOX_SECRET,'archivo');
    assert.equal(leerEnv({QA_AUTORIZADO:'SI',QA_SANDBOX_SECRET:'proceso'},file).QA_SANDBOX_SECRET,'proceso');
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('contexto y preflight bloquean URL remota en ensayo y huella incorrecta',()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g39-ctx-'));
  const runId='RUN-G39-V1-20261108-123456',dir=path.join(tmp,runId);fs.mkdirSync(dir);
  const file=path.join(dir,'contexto_operacion.json');fs.writeFileSync(file,JSON.stringify({grupo:'G39',run_id:runId,
    version:1,intento:1,operacion:'EVALUAR',referencia:'AUT-LOCAL',casos:CAPACIDADES.casos}));
  const argv=['--operacion','evaluar','--version','1','--intento','1','--run-id',runId,'--autorizacion','AUT-LOCAL','--contexto',file];
  try{
    const c=contexto(argv,true);assert.equal(c.runId,runId);
    assert.throws(()=>contexto(argv,false),/Contexto fuera del RUN/);
    const e={QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:'https://www.api.inmero.co/api-sgpmp-test',
      QA_SANDBOX_SECRET:'local',QA_CONTADOR_EMAIL:'local',QA_CONTADOR_PASSWORD:'local',QA_ADMIN_EMAIL:'local',QA_ADMIN_PASSWORD:'local'};
    assert.ok(preflight(c,e,'6.2.2').barreras.includes('API_NO_CANONICA'));
    assert.equal(preflight(c,{...e,SIGAB_API_TEST_BASE:'http://127.0.0.1:9999'},'6.2.2').ok,true);
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('salvaguarda PETICION_CONCURRENTE detecta solapamiento',async()=>{
  let soltar;const pendiente=new Promise(resolve=>soltar=resolve);
  await conPeticiones(async()=>{await pendiente;return{status:200,json:async()=>({}),headers:new Headers()};},async()=>{
    const p=fetchEnContexto('http://127.0.0.1:1');
    await assert.rejects(fetchEnContexto('http://127.0.0.1:1'),/PETICION_CONCURRENTE/);
    soltar();await p;
  });
});
test('permisos de ambos actores y costos C/R antes de escritura',()=>{
  for(const actor of ['contador','admin']){
    const permisos=Object.entries(CONTRATO.roles[actor].permisos).flatMap(([nombre_recurso,acciones])=>
      acciones.map(id_accion=>({id_recurso:1,id_accion,nombre_recurso})));
    assert.equal(verificarPermisos({permisos},actor),true);
  }
  const permisos=Object.entries(CONTRATO.roles.contador.permisos).filter(([k])=>k!=='costos_activos')
    .flatMap(([nombre_recurso,acciones])=>acciones.map(id_accion=>({id_recurso:1,id_accion,nombre_recurso})));
  assert.throws(()=>verificarPermisos({permisos},'contador'),/costos_activos/);
});
test('contrato usa formas reales y decimal exacto',()=>{
  for(const p of CONTRATO.peticiones){assert.ok(p.router.includes(':'));assert.ok(p.respuesta.includes(':'));
    if(p.tipo==='array'||p.tipo==='object')assert.equal(validarMock(p.id,mock(p.id)),true);}
  assert.equal(truncar2('1000.9999'),'1000.99');assert.equal(igual('123.45',123.45),true);
  const m=[{tipo_hecho:'BAJA_ACTIVO',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'613505'},
    {tipo_hecho:'BAJA_ACTIVO',sentido:'UNICO',id_especie:39,subtipo_costo:null,cuenta_debito:'613506'}];
  assert.equal(resolverMatriz(m,'BAJA_ACTIVO','UNICO',39).cuenta_debito,'613506');
});
test('registro QA exige informe y Newman dentro del RUN',()=>{
  const cap=CAPACIDADES,runId='RUN-G39-V1-20261108-123456',ctx={runId,referencia:'AUT',version:1};
  const r={run_id:runId,autorizacion_referencia:'AUT',version:1,oficial:true,consume_version:true,
    cierre:{run:{cierre_http:200},rollback:{verificado:true}},
    casos:Object.fromEntries(cap.casos.map(c=>[c,{estado:'APROBADO'}])),
    herramientas:{newman:{iteraciones:1}},cypress:{total_pruebas:0},
    comprobaciones:cap.casos.map((caso,i)=>({caso,fuente:'API',id:cap.comprobaciones_obligatorias[caso].API[0],
      tipo:'ASSERT',estado:'APROBADO',evidencia:'resultado.json'})),
    evidencias:['resultado.json','TC-M06-G39_resultado.md','newman/newman-G39.json','newman/newman-G39.html']};
  const presentes=new Set(r.evidencias);assert.equal(clasificarRegistro(cap,r,presentes,ctx),true);
  presentes.delete('newman/newman-G39.html');assert.equal(clasificarRegistro(cap,r,presentes,ctx),false);
});

test('CLI real sin autorizacion escribe solo preflight y limpia RUN sintetico',t=>{
  const raiz=path.join(GRUPO,'Resultados');
  let runId,dir;
  do{runId=`RUN-G39-V1-20261108-${String(randomInt(1000000)).padStart(6,'0')}`;
    dir=path.join(raiz,runId);}while(fs.existsSync(dir));
  assert.equal(path.dirname(path.resolve(dir)),path.resolve(raiz));
  const habiaRaiz=fs.existsSync(raiz);
  try{
    fs.mkdirSync(dir,{recursive:true});
    const archivo=path.join(dir,'contexto_operacion.json');escribirContexto(archivo,runId);
    const x=spawnSync(process.execPath,[path.join(GRUPO,'g39.mjs'),...args(runId,archivo)],
      {cwd:GRUPO,env:{...process.env,QA_AUTORIZADO:'NO'},windowsHide:true,encoding:'utf8'});
    if(x.error?.code==='EPERM'){t.skip('PENDIENTE Windows: spawn EPERM');return;}
    assert.ifError(x.error);assert.equal(x.status,2,x.stderr);
    const p=JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'),'utf8'));
    assert.equal(p.ok,false);assert.ok(p.barreras.includes('QA_AUTORIZADO'));
    assert.equal(fs.existsSync(path.join(dir,'resultado.json')),false);
  }finally{
    fs.rmSync(dir,{recursive:true,force:true});
    if(!habiaRaiz&&fs.existsSync(raiz)&&fs.readdirSync(raiz).length===0)fs.rmdirSync(raiz);
  }
});
test('CLI real rechaza contexto temporal externo sin escribir resultados',t=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g39-cli-contexto-'));
  const runId='RUN-G39-V1-20261108-000001',archivo=path.join(tmp,'contexto_operacion.json');
  const destino=path.join(GRUPO,'Resultados',runId),existia=fs.existsSync(destino);
  try{
    escribirContexto(archivo,runId);
    const x=spawnSync(process.execPath,[path.join(GRUPO,'g39.mjs'),...args(runId,archivo)],
      {cwd:GRUPO,env:{...process.env,QA_AUTORIZADO:'NO'},windowsHide:true,encoding:'utf8'});
    if(x.error?.code==='EPERM'){t.skip('PENDIENTE Windows: spawn EPERM');return;}
    assert.ifError(x.error);assert.equal(x.status,2);
    assert.match(x.stderr,/Contexto fuera del RUN/);
    assert.deepEqual(fs.readdirSync(tmp),['contexto_operacion.json']);
    assert.equal(fs.existsSync(destino),existia);
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('principal sin secreto escribe preflight y no hace peticiones',async()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g39-sin-secreto-'));
  const runId='RUN-G39-V1-20261108-000002',dir=path.join(tmp,runId);
  try{
    fs.mkdirSync(dir);const archivo=path.join(dir,'contexto_operacion.json');escribirContexto(archivo,runId);
    let peticiones=0;
    const salida=await principal(args(runId,archivo),{ensayo:true,archivoEnv:path.join(tmp,'inexistente'),
      proceso:{QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:'http://127.0.0.1:1'},
      fetcher:async()=>{peticiones++;throw Error('No debe llamarse');}});
    assert.equal(salida.exitCode,2);assert.equal(peticiones,0);
    assert.ok(salida.preflight.barreras.includes('QA_SANDBOX_SECRET'));
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'),'utf8')).ok,false);
    assert.equal(fs.existsSync(path.join(dir,'resultado.json')),false);
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('todos los actores, mocks y negativos estrictos del contrato',()=>{
  for(const p of CONTRATO.peticiones){
    assert.equal(validarActor(p.id,p.actor),true,p.id);
    assert.throws(()=>validarActor(p.id,p.actor==='contador'?'admin':'contador'),/Actor sin permiso/);
    const cuerpo=mock(p.id);assert.equal(validarMock(p.id,cuerpo),true,p.id);
    const r={contraste_contrato:[],discrepancias_contrato:[],problemas_tecnicos:[]};
    assert.equal(contrastarRespuesta(r,p.id,p.actor,p.http??200,cuerpo),true,p.id);
    assert.equal(contrastarRespuesta(r,p.id,p.actor,p.http??200,null),false,p.id);
    if(Object.keys(p.campos).length===0)continue;
    const malo=structuredClone(cuerpo),fila=Array.isArray(malo)?malo[0]:malo;
    const campo=Object.keys(fila)[0];delete fila[campo];
    assert.throws(()=>validarMock(p.id,malo),/Campo ausente/,p.id);
    assert.equal(contrastarRespuesta(r,p.id,p.actor,p.http??200,malo),false,p.id);
    const cambiado=structuredClone(cuerpo);
    const alterar=(v,prioritario=true)=>{
      if(Array.isArray(v))return v.some(x=>alterar(x,prioritario));
      if(!v||typeof v!=='object')return false;
      for(const [k,x] of Object.entries(v))if((!prioritario||k.startsWith('id_')||k==='estado'||k==='tipo')&&
        (typeof x==='number'||typeof x==='string')){v[k]=typeof x==='number'?'texto':42;return true;}
      return Object.values(v).some(x=>alterar(x,prioritario));
    };
    assert.ok(alterar(cambiado)||alterar(cambiado,false),`Sin campo tipado en ${p.id}`);
    assert.throws(()=>validarMock(p.id,cambiado),/Tipo fuera del contrato/);
    assert.equal(contrastarRespuesta(r,p.id,p.actor,p.http??200,cambiado),false,p.id);
    assert.equal(r.discrepancias_contrato.length,3,p.id);
  }
});
test('ruta y version Newman, permisos de coleccion y saneamiento',()=>{
  assert.ok(path.isAbsolute(directorioNewman));
  assert.match(directorioNewman,/newman/);
  const version=JSON.parse(fs.readFileSync(path.join(directorioNewman,'package.json'),'utf8')).version;
  assert.match(version,/^\d+\.\d+\.\d+$/);
  assert.equal(comprobar(),0);
  const col=JSON.parse(fs.readFileSync(path.join(GRUPO,'G39.postman_collection.json'),'utf8'));
  assert.equal(col.item.length,3);
  for(const item of col.item){
    const p=CONTRATO.peticiones.find(x=>x.id===item.name);
    assert.equal(p.actor,'contador');
    assert.ok(item.request.header.some(h=>h.key==='X-Test-Run-Id'&&h.value==='{{run_id}}'));
    assert.ok(item.request.header.some(h=>h.key==='Authorization'&&h.value==='Bearer {{contador_token}}'));
  }
  const saneado=sanearReporte(JSON.stringify({headers:{authorization:'token-ficticio'},body:'privado',
    email:'usuario@ejemplo.invalid',valor:'token-ficticio'}),['token-ficticio'],true);
  assert.ok(!saneado.includes('token-ficticio')&&!saneado.includes('usuario@ejemplo.invalid'));
  assert.match(saneado,/REDACTADO/);
});
test('baja acepta forma EventoActivoResponse con subtipo o null',()=>{
  for(const baja of [{tipo:'venta',motivo:null},null]){
    const cuerpo={id_eventos:501,id_activo_biologico:100,fecha:'2026-11-08T12:00:00Z',
      descripcion:null,id_usuario:null,baja};
    const r={contraste_contrato:[],discrepancias_contrato:[],problemas_tecnicos:[]};
    assert.equal(contrastarRespuesta(r,'baja','admin',201,cuerpo),true);
    assert.equal(r.discrepancias_contrato.length,0);
  }
});
test('GET costos acepta fila real con opcionales null',()=>{
  const fila={id_registro_costo:101,naturaleza_costo:'MANTENIMIENTO',subtipo_costo:null,
    origen_costo:'MANO_OBRA_PROPIA',vehiculo_contable:'ASIENTO_NIC41',id_activo_biologico:100,
    activo:'BOV-100',monto_costo:'123.45',fecha_costo:'2026-11-08',id_periodo_contable:8,
    estado:'REGISTRADO',politica_capitalizacion:'GASTO',justificacion:null,id_origen_m05:null,
    tercero_nit:null,tercero_dv:null,tercero_razon_social:null,factura_prefijo:null,
    factura_numero:null,fecha_factura:null,fecha_vencimiento_factura:null,id_grupo_reparto:null,
    metodo_reparto:null,cuenta_debito:null,cuenta_credito:null,es_cuenta_manual:false,
    es_reverso:false,id_usuario:null,fecha_registro:'2026-11-08T12:00:00Z',id_especie:39,
    id_infraestructura:1,id_finca:1,especie:'Bovino',finca:'Local'};
  const r={contraste_contrato:[],discrepancias_contrato:[],problemas_tecnicos:[]};
  assert.equal(contrastarRespuesta(r,'costos_get','contador',200,[fila]),true);
  assert.equal(r.discrepancias_contrato.length,0);
});
