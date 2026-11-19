import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {validarLecturas,validarError} from '../lib/contrato.mjs';
import {CAPACIDADES,contexto,principal,decisionLogin,preflight,ejecutar,verificarRollback,esOficial,completarResultado,sanitize} from '../g036.mjs';
import os from 'node:os';
import vm from 'node:vm';
import {simuladorG036} from './simulador_g036.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';
import {precondiciones,porVersion,estados,cuerpo,evaluarRechazo,clasificarRechazo,severidadRegla,evaluarRegistro,evaluarAuditoria,evaluarUI,clasificarUI,veredictos,fechaFutura} from '../lib/g036_core.mjs';
const fixture=JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)),'fixture_g036.json'),'utf8'));
test('saneado recursivo de login, respuesta, error y acta',()=>{
  const login={solicitudes:[{cuerpo_solicitud:{contrasena:'LOCAL_FICTICIA',correo_electronico:'local@example.invalid',client_secret:'FICTICIO'},cuerpo_respuesta:{access_key:'FICTICIO',refresh:'FICTICIO'},cuerpo_error:{clave:'FICTICIO',contraseña:'FICTICIA'}}],acta:{email:'local@example.invalid',password:'FICTICIA'}};
  const limpio=sanitize(login);
  assert.equal(limpio.solicitudes[0].cuerpo_solicitud.contrasena,'[RESERVADO]');
  assert.equal(limpio.solicitudes[0].cuerpo_solicitud.correo_electronico,'[CORREO]');
  assert.equal(limpio.solicitudes[0].cuerpo_solicitud.client_secret,'[RESERVADO]');
  assert.equal(limpio.solicitudes[0].cuerpo_respuesta.access_key,'[RESERVADO]');
  assert.equal(limpio.solicitudes[0].cuerpo_respuesta.refresh,'[RESERVADO]');
  assert.equal(limpio.solicitudes[0].cuerpo_error.clave,'[RESERVADO]');
  assert.equal(limpio.solicitudes[0].cuerpo_error.contraseña,'[RESERVADO]');
  assert.equal(limpio.acta.email,'[CORREO]');
  assert.equal(limpio.acta.password,'[RESERVADO]');
});
test('05: hitos distinguen visita técnica de aserción de producto',()=>{
  const vacia={hitos:{frontal_cargado:false,login_interceptado:false,pantalla_contrato:false,modal_abierto:false,registro_enviado:false},error:'cy.visit() failed: 404 Not Found'};
  assert.deepEqual(clasificarUI(vacia,2),{ui:'NO_CONCLUYENTE',api:'NO_CONCLUYENTE',problema:vacia.error});
  const pantalla={hitos:{frontal_cargado:true,login_interceptado:true,pantalla_contrato:true,modal_abierto:false,registro_enviado:false},asercion_producto:'activo_deprecar',activo_deprecar:false,error:'Expected Retirar con plazo',http_registro:null};
  assert.equal(clasificarUI(pantalla,1).ui,false);
  assert.equal(clasificarUI(pantalla,1).api,'NO_CONCLUYENTE');
  assert.equal(clasificarUI({...pantalla,asercion_producto:null,error:'network failed'},1).ui,'NO_CONCLUYENTE');
  assert.equal(clasificarUI({...pantalla,asercion_producto:null,error:'navigation selector missing'},1).ui,'NO_CONCLUYENTE');
  assert.equal(clasificarUI({...pantalla,asercion_producto:null,error:null},0).ui,'NO_CONCLUYENTE');
});
test('ningún archivo vigente del grupo conserva el frontal con www',()=>{
  const base=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  const revisar=dir=>{for(const x of fs.readdirSync(dir,{withFileTypes:true})){if(['Resultados','EvaluacionV2'].includes(x.name))continue;const ruta=path.join(dir,x.name);if(x.isDirectory())revisar(ruta);else if(/\.(?:mjs|js|cjs|json|md)$/.test(x.name))assert(!fs.readFileSync(ruta,'utf8').includes('www.api.inmero.co/'+'sigab-test'),ruta);}};
  revisar(base);
});
test('lanzador: capacidades y CLI con RUN precreado en TEMP',async()=>{
  assert.equal(CAPACIDADES.contrato,'sigab-qa-ejecutor/1');
  assert.deepEqual(Object.keys(CAPACIDADES.comprobaciones_obligatorias).sort(),CAPACIDADES.casos.slice().sort());
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g036-cli-'));
  try{
    const runId='RUN-G036-V1-20261117-000000',dir=path.join(tmp,runId);fs.mkdirSync(dir);
    const archivo=path.join(dir,'contexto_operacion.json');
    fs.writeFileSync(archivo,JSON.stringify({grupo:'G036',version:1,intento:1,run_id:runId,operacion:'EVALUAR',referencia:'REF-LOCAL',casos:CAPACIDADES.casos}));
    const args=['--autorizacion','REF-LOCAL','--operacion','evaluar','--version','1','--intento','1','--run-id',runId,'--contexto',archivo];
    assert.equal(contexto(args,true).dir,dir);
    const z=await principal(args,{proceso:{QA_AUTORIZADO:'NO'},archivo:path.join(tmp,'sin-env'),prueba:true});
    assert.equal(z.codigo,2);assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'preflight.json'))).ok,false);
    assert.equal(fs.existsSync(path.join(dir,'resultado.json')),false);
    const sim=await simuladorG036();
    try{
      const proceso={QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api,SIGAB_FRONT_TEST_BASE:sim.front};
      const cypress=async input=>{
        const headers={'X-Test-Run-Id':input.runId,'X-Sandbox-Secret':input.secret,'Content-Type':'application/json'};
        const alta=await fetch(input.api+'/integracion/contratos',{method:'POST',headers,body:JSON.stringify(cuerpo('4.2',input.anexoId,input.fecha))});assert.equal(alta.status,201);
        const acta={caso:'TC-M07-05',http_registro:201,version_4_2_visible:true,pendiente_activar:true,activo_deprecar:true,deprecado_sin_accion:true,inactivo_sin_accion:true,captura:true,video:true,hitos:{frontal_cargado:true,login_interceptado:true,pantalla_contrato:true,modal_abierto:true,registro_enviado:true}};
        fs.mkdirSync(path.join(input.dir,'screenshots'),{recursive:true});fs.mkdirSync(path.join(input.dir,'videos'),{recursive:true});
        fs.writeFileSync(path.join(input.dir,'G036-UI-05.json'),JSON.stringify(acta));fs.writeFileSync(path.join(input.dir,'screenshots','simulada.png'),'SIMULACION_LOCAL');fs.writeFileSync(path.join(input.dir,'videos','g036.cy.js.mp4'),'SIMULACION_LOCAL');
        return{codigo:0,totalTests:1,acta};
      };
      const listo=await principal(args,{proceso,archivo:path.join(tmp,'sin-env'),prueba:true,dobles:{newman:ejecutarNewman,cypress}});
      assert.equal(listo.codigo,0);assert.equal(listo.preflight.ok,true);assert.equal(listo.resultado.cierre.rollback.verificado,true);
      assert(fs.existsSync(path.join(dir,'resultado.json')));assert.equal(fs.readdirSync(dir).filter(x=>x.endsWith('.md')).length,1);
    }finally{await sim.cerrar();}
  }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('reglas de incidencia por comprobación y creación real',()=>{
  const resultado=(pruebas,solicitudes=[])=>{const r={cierre:{rollback:{verificado:false}},solicitudes,pruebas,veredictos:{'01':'RECHAZADO','04':'RECHAZADO'},incidencias:[],evidencias:[],oficial:false};completarResultado(r,{referencia:'LOCAL',ensayo:true});return r;};
  const auditoria=resultado({'01_registro':true,'01_auditoria':false});
  assert.deepEqual(auditoria.incidencias.filter(x=>x.caso==='TC-M07-01').map(x=>[x.regla,x.severidad]),[['AUDITORIA_AUSENTE','MEDIA']]);
  const post=(http)=>({metodo:'POST',ruta:'/integracion/contratos',http,cuerpo_solicitud:{mapeadores:[]}});
  const creado=resultado({'04a':'RECHAZADO'},[post(201)]);
  assert.deepEqual(creado.incidencias.filter(x=>x.caso==='TC-M07-04').map(x=>[x.regla,x.severidad]),[['RECHAZO_CREO_VERSION','ALTA']]);
  const entrada=resultado({'04a':'RECHAZADO'},[post(422)]);
  assert.deepEqual(entrada.incidencias.filter(x=>x.caso==='TC-M07-04').map(x=>[x.regla,x.severidad]),[['CODIGO_DISTINTO_SIN_CREACION','BAJA']]);
});
const permisos=[{nombre_recurso:'contratos_aaef',id_accion:1},{nombre_recurso:'contratos_aaef',id_accion:2},{nombre_recurso:'auditoria_integracion',id_accion:2}];
const p=()=>precondiciones(fixture.anexos,fixture.contratos,permisos);
const fecha=fechaFutura(new Date('2026-11-17T12:00:00Z'));
const nuevo=(version='4.0',anexo=2)=>({id_version_contrato_aaef:9,...cuerpo(version,anexo,fecha),endpoint_asociado:'/integracion/aaef/productores/{nit}',descripcion:null,estado:'PENDIENTE',fecha_activacion:null,fecha_deprecacion:null,fecha_inactivacion:null});
const error=code=>({http:code==='VERSION_DUPLICADA'?409:422,data:{error_code:code,message:'rechazo',fields:[],timestamp:'2026-11-17T12:00:00Z'}});
test('contrato: fixture con extras y listas barajadas',()=>{const a=validarLecturas(fixture.anexos,'GET','/integracion/anexos');const c=validarLecturas(fixture.contratos,'GET','/integracion/contratos');assert.equal(a.find(x=>x.estado==='OBSOLETO').id_mapeo_anexo_aaef,1);assert.equal(c.find(x=>x.estado==='INACTIVO').id_mapeo_anexo_aaef,null);assert.equal(c.find(x=>x.estado==='INACTIVO').mapeadores.length,0);assert.equal(p().aprobado.id_mapeo_anexo_aaef,2);assert.equal(p().revision.id_mapeo_anexo_aaef,3);assert.equal(p().existente.contrato_version,'2.1');});
test('contrato: lectura fuera rompe en estricto',()=>{const a=validarLecturas(fixture.anexos,'GET','/integracion/anexos',{estricto:true});assert.throws(()=>a[0].campo_desconocido,/LECTURA_FUERA_CONTRATO/);assert.equal(a[0].estado,'EN_REVISION');});
test('contrato: campo tipado roto',()=>{const x=[{...fixture.anexos[0],id_mapeo_anexo_aaef:'mal'}];assert.throws(()=>validarLecturas(x,'GET','/integracion/anexos')[0].id_mapeo_anexo_aaef,/TIPO_INVALIDO/);});
test('contrato: error estandar',()=>{assert.equal(validarError(error('VAL_ENTRADA').data),true);assert.equal(validarError({...error('VAL_ENTRADA').data,fields:[{field:'mapeadores',message:'inválido'}]}),true);assert.equal(validarError({...error('VAL_ENTRADA').data,fields:[{message:'sin campo'}]}),false);assert.equal(validarError({error_code:'X'}),false);});
test('R1: 01 rechazado conserva Newman sin fallos y oficialidad',()=>{
  const coleccion=JSON.parse(fs.readFileSync(new URL('../G036.postman_collection.json',import.meta.url),'utf8'));
  const scripts=coleccion.item.find(x=>x.name.startsWith('G036-N-02')).event[0].script.exec;
  let fallos=0;
  const pm={response:{status:200,json:()=>fixture.contratos,headers:{get:()=> 'RUN-LOCAL'} ,to:{have:{status:n=>assert.equal(n,200)}}},environment:{get:()=> 'RUN-LOCAL'},expect:v=>({to:{be:{an:t=>assert.equal(Array.isArray(v),t==='array')},eql:x=>assert.equal(v,x)}}),test:(_nombre,fn)=>{try{fn();}catch{fallos++;}}};
  for(const script of scripts)vm.runInNewContext(script,{pm});
  const veredictosCaso=veredictos({r01:false,r02:true,r03a:true,r03b:true,r03c:true,r04a:true,r04b:true,r05:true});
  assert.equal(veredictosCaso['01'],'RECHAZADO');
  assert.equal(fallos,0);
  assert.equal(esOficial({veredictos:veredictosCaso,newman:{codigo:0,fallos,reportes:true,solicitudes:3},cypress:{codigo:0},cierre:{rollback:{verificado:true}},solicitudes:[]},Date.now()+60000),true);
});
test('R2: rollback compara ids y estados, tolera otros campos y rechaza residuos',()=>{
  const contratos=structuredClone(fixture.contratos),anexos=structuredClone(fixture.anexos);
  const posterioresC=structuredClone(contratos),posterioresA=structuredClone(anexos);
  posterioresC[0].descripcion='Cambio ajeno al RUN';
  posterioresA[0].fecha_aprobacion='2026-11-18T12:00:00Z';
  const baseC=validarLecturas(contratos,'GET','/integracion/contratos',{estricto:true});
  const baseA=validarLecturas(anexos,'GET','/integracion/anexos',{estricto:true});
  const despuesC=validarLecturas(posterioresC,'GET','/integracion/contratos',{estricto:true});
  const despuesA=validarLecturas(posterioresA,'GET','/integracion/anexos',{estricto:true});
  assert.equal(verificarRollback(baseC,despuesC,baseA,despuesA),true);
  const qaAnexo=structuredClone(posterioresA);qaAnexo[0].codigo_anexo='QA-G036-BORRADOR';
  assert.equal(verificarRollback(baseC,despuesC,baseA,validarLecturas(qaAnexo,'GET','/integracion/anexos',{estricto:true})),false);
  for(const version of ['4.0','4.1','4.2']){const qaVersion=structuredClone(posterioresC);qaVersion[0].contrato_version=version;assert.equal(verificarRollback(baseC,validarLecturas(qaVersion,'GET','/integracion/contratos',{estricto:true}),baseA,despuesA),false);}
  const cambiado=structuredClone(posterioresC);cambiado[0].estado='PENDIENTE';
  assert.equal(verificarRollback(baseC,validarLecturas(cambiado,'GET','/integracion/contratos',{estricto:true}),baseA,despuesA),false);
  const inyectadosC=validarLecturas(contratos.map(x=>({...x,campo_inyectado:1n})),'GET','/integracion/contratos',{estricto:true});
  const inyectadosA=validarLecturas(anexos.map(x=>({...x,campo_inyectado:1n})),'GET','/integracion/anexos',{estricto:true});
  assert.doesNotThrow(()=>verificarRollback(inyectadosC,inyectadosC,inyectadosA,inyectadosA));
  assert.equal(verificarRollback(inyectadosC,inyectadosC,inyectadosA,inyectadosA),true);
});
const tabla=[
  ['login antes del RUN permitido',()=>decisionLogin({})==='PERMITIDO'],
  ['login dentro del RUN bloqueado',()=>decisionLogin({runAbierto:true})==='LOGIN_DENTRO_RUN'],
  ['segundo login bloqueado',()=>decisionLogin({loginIntentado:true})==='SEGUNDO_LOGIN'],
  ['login fallido termina sin reintento',()=>decisionLogin({loginFallido:true,loginIntentado:true})==='LOGIN_FALLIDO_SIN_REINTENTO'],
  ['permisos ausentes',()=>precondiciones(fixture.anexos,fixture.contratos,[]).faltan.length===3],
  ['sin aprobado',()=>precondiciones(fixture.anexos.filter(x=>x.estado!=='APROBADO'),fixture.contratos,permisos).faltan.includes('ANEXO_APROBADO')],
  ['sin duplicado',()=>precondiciones(fixture.anexos,[],permisos).faltan.includes('VERSION_DUPLICADO')],
  ['4.0 ya existe',()=>precondiciones(fixture.anexos,[...fixture.contratos,nuevo()],permisos).faltan.includes('VERSION_4_0_AUSENTE')],
  ['sin revision',()=>precondiciones(fixture.anexos.filter(x=>x.estado!=='EN_REVISION'),fixture.contratos,permisos).revision===null],
  ['id inexistente ocupado',()=>precondiciones([...fixture.anexos,{...fixture.anexos[0],id_mapeo_anexo_aaef:999999}],fixture.contratos,permisos).faltan.includes('ANEXO_999999_AUSENTE')],
  ['02 codigo esperado',()=>evaluarRechazo(error('VERSION_DUPLICADA'),'VERSION_DUPLICADA',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['02 otro codigo',()=>!evaluarRechazo(error('OTRO'),'VERSION_DUPLICADA',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['03a codigo esperado',()=>evaluarRechazo(error('ANEXO_MAPEO_INVALIDO'),'ANEXO_MAPEO_INVALIDO',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['03a otro codigo',()=>!evaluarRechazo(error('VAL_ENTRADA'),'ANEXO_MAPEO_INVALIDO',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['03b codigo esperado',()=>evaluarRechazo(error('ANEXO_MAPEO_INVALIDO'),'ANEXO_MAPEO_INVALIDO',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['03b otro codigo',()=>!evaluarRechazo(error('OTRO'),'ANEXO_MAPEO_INVALIDO',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['04a codigo esperado',()=>evaluarRechazo(error('MAPPERS_INVALIDOS'),'MAPPERS_INVALIDOS',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['04a otro codigo',()=>!evaluarRechazo(error('OTRO'),'MAPPERS_INVALIDOS',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['04b codigo esperado',()=>evaluarRechazo(error('MAPPERS_INVALIDOS'),'MAPPERS_INVALIDOS',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['04b otro codigo',()=>!evaluarRechazo(error('OTRO'),'MAPPERS_INVALIDOS',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['04 VAL_ENTRADA',()=>!evaluarRechazo(error('VAL_ENTRADA'),'MAPPERS_INVALIDOS',estados(fixture.contratos),fixture.contratos,'4.0')],
  ['version creada tras rechazo',()=>!evaluarRechazo(error('ANEXO_MAPEO_INVALIDO'),'ANEXO_MAPEO_INVALIDO',estados(fixture.contratos),[...fixture.contratos,nuevo()],'4.0')],
  ['01 correcto',()=>evaluarRegistro({http:201,data:nuevo()},[...fixture.contratos,nuevo()],cuerpo('4.0',2,fecha))],
  ['01 activo',()=>!evaluarRegistro({http:201,data:{...nuevo(),estado:'ACTIVO'}},[...fixture.contratos,nuevo()],cuerpo('4.0',2,fecha))],
  ['01 sin endpoint',()=>!evaluarRegistro({http:201,data:{...nuevo(),endpoint_asociado:''}},[...fixture.contratos,nuevo()],cuerpo('4.0',2,fecha))],
  ['auditoria ausente',()=>!evaluarAuditoria([],[],'4.0',7)],
  ['3c rechazada',()=>veredictos({r01:true,r02:true,r03a:true,r03b:true,r03c:false,r04a:true,r04b:true,r05:true})['03']==='RECHAZADO'],
  ['UI sin version',()=>!evaluarUI({version_4_2_visible:false})],
  ['UI acciones incorrectas',()=>!evaluarUI({http_registro:201,version_4_2_visible:true,pendiente_activar:false,activo_deprecar:true,deprecado_sin_accion:true,inactivo_sin_accion:true,captura:true,video:true})],
  ['UI sin versión ACTIVO queda no concluyente',()=>evaluarUI({http_registro:201,version_4_2_visible:true,pendiente_activar:true,activo_deprecar:null,deprecado_sin_accion:true,inactivo_sin_accion:true,captura:true,video:true})==='NO_CONCLUYENTE'],
  ['rollback fallido',()=>{const oficial=(rollback,newman,cypress)=>rollback&&newman&&cypress;return oficial(false,true,true)===false;}],
  ['Newman fallido',()=>{const oficial=(rollback,newman,cypress)=>rollback&&newman&&cypress;return oficial(true,false,true)===false;}],
  ['Cypress fallido',()=>{const oficial=(rollback,newman,cypress)=>rollback&&newman&&cypress;return oficial(true,true,false)===false;}]
  ,['preflight observado por requisito',()=>p().preflight_datos.every(x=>Object.keys(x).sort().join(',')==='bloqueante,cumple,esperado,observado,requisito')]
  ,['preflight revision no bloqueante',()=>precondiciones(fixture.anexos.filter(x=>x.estado!=='EN_REVISION'),fixture.contratos,permisos).preflight_datos.find(x=>x.requisito==='ANEXO_EN_REVISION').bloqueante===false]
  ,['4.1 presente bloquea',()=>precondiciones(fixture.anexos,[...fixture.contratos,nuevo('4.1')],permisos).faltan.includes('VERSION_4_1_AUSENTE')]
  ,['4.2 presente bloquea',()=>precondiciones(fixture.anexos,[...fixture.contratos,nuevo('4.2')],permisos).faltan.includes('VERSION_4_2_AUSENTE')]
  ,['02 codigo ajeno inconcluyente',()=>clasificarRechazo(error('OTRO'),'VERSION_DUPLICADA',estados(fixture.contratos),fixture.contratos,'4.0')==='NO_CONCLUYENTE']
  ,['02 401 inconcluyente',()=>clasificarRechazo({http:401,data:{error_code:'SIN_SESION'}},'VERSION_DUPLICADA',estados(fixture.contratos),fixture.contratos,'4.0')==='NO_CONCLUYENTE']
  ,['03 403 inconcluyente',()=>clasificarRechazo({http:403,data:{error_code:'ACCESO_DENEGADO'}},'ANEXO_MAPEO_INVALIDO',estados(fixture.contratos),fixture.contratos,'4.0')==='NO_CONCLUYENTE']
  ,['03 codigo ajeno inconcluyente',()=>clasificarRechazo(error('VAL_ENTRADA'),'ANEXO_MAPEO_INVALIDO',estados(fixture.contratos),fixture.contratos,'4.0')==='NO_CONCLUYENTE']
  ,['04 VAL_ENTRADA solo mapeadores discrepancia',()=>clasificarRechazo({http:422,data:{error_code:'VAL_ENTRADA',fields:[{field:'mapeadores.0'}]}},'MAPPERS_INVALIDOS',estados(fixture.contratos),fixture.contratos,'4.0')==='RECHAZADO']
  ,['04 VAL_ENTRADA otro campo inconcluyente',()=>clasificarRechazo({http:422,data:{error_code:'VAL_ENTRADA',fields:[{field:'fecha_vigencia'}]}},'MAPPERS_INVALIDOS',estados(fixture.contratos),fixture.contratos,'4.0')==='NO_CONCLUYENTE']
  ,['201 indebido rechazado',()=>clasificarRechazo({http:201,data:nuevo()},'ANEXO_MAPEO_INVALIDO',estados(fixture.contratos),fixture.contratos,'4.0')==='RECHAZADO']
  ,['severidad registro invalido ALTA',()=>severidadRegla('REGISTRO_ACTIVO')==='ALTA']
  ,['severidad rechazo que crea version ALTA',()=>severidadRegla('RECHAZO_CREO_VERSION')==='ALTA']
  ,['severidad revision MEDIA',()=>severidadRegla('REVISION_RECHAZADA')==='MEDIA']
  ,['severidad codigo distinto BAJA',()=>severidadRegla('CODIGO_DISTINTO_SIN_CREACION')==='BAJA']
];
for(const [nombre,fn] of tabla)test(`decision: ${nombre}`,()=>assert.equal(fn(),true));
test('fecha Bogota +400 dias',()=>assert.equal(fecha,'2027-12-22'));
test('simulador M07: orden, forma y rollback local',async()=>{const sim=await simuladorG036({barajar:true,inyectar:true});try{const h={'Content-Type':'application/json','X-Test-Run-Id':sim.runId};const post=async body=>{const z=await fetch(sim.api+'/integracion/contratos',{method:'POST',headers:h,body:JSON.stringify(body)});return{http:z.status,data:await z.json()};};const invalido=await post(cuerpo('4.0',999999,fecha,[]));assert.equal(invalido.data.error_code,'VAL_ENTRADA');assert.deepEqual(invalido.data.fields.map(x=>x.field),['mapeadores']);const anexo=await post(cuerpo('4.0',999999,fecha));assert.equal(anexo.data.error_code,'ANEXO_MAPEO_INVALIDO');const ok=await post(cuerpo('4.0',2,fecha));assert.equal(ok.http,201);assert.equal(ok.data.estado,'PENDIENTE');const dup=await post(cuerpo('4.0',2,fecha));assert.equal(dup.data.error_code,'VERSION_DUPLICADA');const audit=await(await fetch(sim.api+'/integracion/auditoria?pagina=1&tamano=100',{headers:h})).json();assert.equal(audit.total,1);assert.equal(audit.items[0].version_contrato,'4.0');const del=await fetch(sim.api+'/test-control/runs/'+sim.runId,{method:'DELETE'});assert.equal(del.status,200);const despues=await(await fetch(sim.api+'/integracion/contratos')).json();assert(!despues.some(x=>x.contrato_version==='4.0'));}finally{await sim.cerrar();}});
test('runner local: preflight bloqueante, DELETE, informe UTF-8 y lecturas sin RUN',async()=>{const sim=await simuladorG036({sinPermisos:true});const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g036-local-'));try{const dir=path.join(tmp,sim.runId);const r=await ejecutar({ensayo:true,dir,runId:sim.runId,referencia:'LOCAL'},{QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api,SIGAB_FRONT_TEST_BASE:sim.front});assert.equal(r.oficial,false);assert.equal(r.cierre.http,200);assert.equal(r.cierre.rollback.verificado,true);assert(r.preflight_datos.some(x=>x.bloqueante&&!x.cumple));assert.equal(r.casos['TC-M07-01'].estado,'NO_CONCLUYENTE');assert(fs.existsSync(path.join(dir,'resultado.json')));const guardado=JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'),'utf8'));const sesion=guardado.solicitudes.find(x=>x.ruta==='/sesiones/');assert.equal(sesion.cuerpo_solicitud.contrasena,'[RESERVADO]');assert.equal(sesion.cuerpo_solicitud.correo_electronico,'[CORREO]');const informe=fs.readFileSync(path.join(dir,'TC-M07-G036_resultado.md'),'utf8');assert(informe.includes('versión'));assert(informe.includes('NO_CONCLUYENTE'));assert(!informe.includes('local@example.invalid'));assert.equal(informe.replace(/https?:\/\/\S+/g,'' ).includes('?'),false);assert(sim.peticiones.some(x=>x.metodo==='DELETE'));assert(sim.peticiones.slice(-2).every(x=>x.metodo==='GET'&&!x.run));}finally{await sim.cerrar();fs.rmSync(tmp,{recursive:true,force:true});}});
test('R4: ejecutor estricto en proceso lee 01-04 y auditoría, con y sin campos inyectados',async()=>{
  for(const inyectar of [false,true]){
    const sim=await simuladorG036({inyectar}),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g036-estricto-'));
    try{
      const dir=path.join(tmp,sim.runId);
      const r=await ejecutar({ensayo:true,estricto:true,dir,runId:sim.runId,referencia:'LOCAL'},
        {QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api,SIGAB_FRONT_TEST_BASE:sim.front},
        (url,init)=>fetch(url,init),{newman:async()=>({codigo:0,fallos:0,reportes:false,solicitudes:0}),cypress:async()=>({codigo:2,totalTests:0})});
      assert(r.problemas_tecnicos.some(x=>x.includes('Cypress no gener')),`inyectar=${inyectar}`);
      assert.deepEqual(['01','02','03','04'].map(k=>r.veredictos[k]),['APROBADO','APROBADO','APROBADO','RECHAZADO']);
      assert.equal(r.pruebas['01_auditoria'],true);
      assert.equal(r.cierre.http,200);
      assert.equal(r.cierre.rollback.verificado,true);
      assert(fs.existsSync(path.join(dir,'resultado.json')));
    }finally{await sim.cerrar();fs.rmSync(tmp,{recursive:true,force:true});}
  }
});
test('a_conforme: informe M06 completo con incidencia consolidada',async()=>{
  const sim=await simuladorG036(),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g036-r6-'));
  let llamado=false;
  try{
    const dir=path.join(tmp,sim.runId);
    const r=await ejecutar({ensayo:true,estricto:true,dir,runId:sim.runId,referencia:'LOCAL'},
      {QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api,SIGAB_FRONT_TEST_BASE:sim.front},
      fetch,{
        newman:async input=>{fs.mkdirSync(input.salida,{recursive:true});for(const file of ['newman-G036.json','newman-G036.html'])fs.writeFileSync(path.join(input.salida,file),'SIMULACION_LOCAL');return{codigo:0,fallos:0,solicitudes:3,reportes:true};},
        lanzarCypress:async input=>{
          llamado=true;
          const headers={'X-Test-Run-Id':input.runId,'X-Sandbox-Secret':input.secret,'Content-Type':'application/json'};
          const antes=await fetch(input.api+'/integracion/contratos',{headers});
          assert.equal(antes.status,200);
          assert((await antes.json()).some(x=>x.estado==='ACTIVO'));
          const alta=await fetch(input.api+'/integracion/contratos',{method:'POST',headers,body:JSON.stringify(cuerpo('4.2',input.anexoId,input.fecha))});
          assert.equal(alta.status,201);
          assert.equal((await alta.json()).estado,'PENDIENTE');
          const acta={caso:'TC-M07-05',http_registro:201,version_4_2_visible:true,pendiente_activar:true,activo_deprecar:true,deprecado_sin_accion:true,inactivo_sin_accion:true,captura:true,video:true,hitos:{frontal_cargado:true,login_interceptado:true,pantalla_contrato:true,modal_abierto:true,registro_enviado:true}};
          fs.mkdirSync(path.join(input.dir,'screenshots'),{recursive:true});
          fs.mkdirSync(path.join(input.dir,'videos'),{recursive:true});
          fs.writeFileSync(path.join(input.dir,'G036-UI-05.json'),JSON.stringify(acta));
          fs.writeFileSync(path.join(input.dir,'G036-cypress.json'),JSON.stringify({totalTests:1}));
          fs.writeFileSync(path.join(input.dir,'G036-cypress-salida.log'),'SIMULACION_LOCAL');
          fs.writeFileSync(path.join(input.dir,'screenshots','simulada.png'),'SIMULACION_LOCAL');
          fs.writeFileSync(path.join(input.dir,'videos','g036.cy.js.mp4'),'SIMULACION_LOCAL');
          return{status:0,error:null,stdout:JSON.stringify({codigo:0,totalTests:1,acta})};
        }
      });
    assert.equal(llamado,true,'el lanzador inyectado debe ejecutarse; la versión spawnSync ignora esta inyección');
    assert.deepEqual(['01','02','03','04','05'].map(k=>r.veredictos[k]),['APROBADO','APROBADO','APROBADO','RECHAZADO','APROBADO']);
    assert.equal(r.oficial,true);
    assert.deepEqual(r.problemas_tecnicos,[]);
    assert.equal(r.cierre.rollback.verificado,true);
    assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'resultado.json'))).oficial,true);
    assert.equal(fs.readdirSync(dir).filter(x=>x.endsWith('.md')).length,1);
    const informeLocal=fs.readFileSync(path.join(dir,'TC-M07-G036_resultado.md'),'utf8');
    for(const seccion of ['## Identificación','## Resumen de veredictos','## Detalle por caso','## Comprobaciones API y UI','## Evidencias reales','## Incidencias de producto','## Observaciones','## Problemas técnicos','## Cierre y rollback','## Conclusión y acciones'])assert(informeLocal.includes(seccion),seccion);
    for(const apartado of ['**Requisito:**','**Pasos para reproducir:**','**Esperado:**','**Obtenido:**','**Apoyo de código leído','**Impacto y severidad:**','**Certeza:**','**Causa raíz:**','**Primera atención:**','**Evidencias:**'])assert(informeLocal.includes(apartado),apartado);
    assert.equal(informeLocal.match(/### INC-M07-G036-01/g)?.length,1);
    const resumen=informeLocal.split('## Resumen de veredictos')[1].split('## Detalle por caso')[0];
    assert(!/\{"(?:01_registro|02|03a|04a|05_api)"/.test(resumen));
  }finally{await sim.cerrar();fs.rmSync(tmp,{recursive:true,force:true});}
});
test('doble de ContratosView: ruta y script de pantalla sintacticos',async()=>{const sim=await simuladorG036();try{const z=await fetch(sim.front+'/integracion/contrato');assert.equal(z.status,200);const html=await z.text();const js=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];assert(js);new vm.Script(js);assert.match(html,/Registrar versión/);assert.match(html,/Plazo de retiro/);}finally{await sim.cerrar();}});

